from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from datetime import datetime

from app.auth import (
    create_session,
    get_user_for_session_token,
    hash_session_token,
    hash_password,
    revoke_session_token,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.models.user import AuthSession, User
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    UserAdminUpdateRequest,
    UserPublic,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

ADMIN_ROLE = "admin"


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_session_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_user_for_session_token(
        db,
        request.cookies.get(settings.auth_cookie_name),
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != ADMIN_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return user


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    role = ADMIN_ROLE if db.query(User).count() == 0 else payload.role
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token, _ = create_session(db, user)
    _set_session_cookie(response, token)
    return AuthResponse(user=UserPublic.model_validate(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token, _ = create_session(db, user)
    _set_session_cookie(response, token)
    return AuthResponse(user=UserPublic.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    revoke_session_token(db, request.cookies.get(settings.auth_cookie_name))
    _clear_session_cookie(response)
    return None


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(current_user)):
    return UserPublic.model_validate(user)


@router.get("/users", response_model=list[UserPublic])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[User]:
    return db.query(User).order_by(User.created_at.asc(), User.id.asc()).all()


@router.post("/change-password", response_model=UserPublic)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is not valid",
        )
    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(
            status_code=422,
            detail="New password must be different from the current password",
        )

    token = request.cookies.get(settings.auth_cookie_name)
    current_hash = hash_session_token(token) if token else None
    now = datetime.utcnow()

    user.password_hash = hash_password(payload.new_password)
    (
        db.query(AuthSession)
        .filter(AuthSession.user_id == user.id)
        .filter(AuthSession.revoked_at.is_(None))
        .filter(AuthSession.token_hash != current_hash)
        .update({AuthSession.revoked_at: now}, synchronize_session=False)
    )
    db.commit()
    db.refresh(user)
    return UserPublic.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserPublic)
def update_user(
    user_id: int,
    payload: UserAdminUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserPublic:
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.role is None and payload.is_active is None:
        return UserPublic.model_validate(target)

    if target.id == admin.id and (
        payload.is_active is False
        or (payload.role is not None and payload.role != ADMIN_ROLE)
    ):
        raise HTTPException(
            status_code=422,
            detail="Administrators cannot deactivate or demote their own account",
        )

    next_role = payload.role if payload.role is not None else target.role
    next_active = (
        payload.is_active if payload.is_active is not None else target.is_active
    )
    if target.role == ADMIN_ROLE and (
        next_role != ADMIN_ROLE or not next_active
    ) and not _has_other_active_admin(db, target.id):
        raise HTTPException(
            status_code=422,
            detail="At least one active administrator is required",
        )

    if payload.role is not None:
        target.role = payload.role
    if payload.is_active is not None:
        target.is_active = payload.is_active
        if not payload.is_active:
            now = datetime.utcnow()
            (
                db.query(AuthSession)
                .filter(AuthSession.user_id == target.id)
                .filter(AuthSession.revoked_at.is_(None))
                .update({AuthSession.revoked_at: now}, synchronize_session=False)
            )
    db.commit()
    db.refresh(target)
    return UserPublic.model_validate(target)


def _has_other_active_admin(db: Session, user_id: int) -> bool:
    return (
        db.query(User)
        .filter(User.id != user_id)
        .filter(User.role == ADMIN_ROLE)
        .filter(User.is_active.is_(True))
        .first()
        is not None
    )
