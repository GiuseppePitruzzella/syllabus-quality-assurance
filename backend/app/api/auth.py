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
    UserPublic,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


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


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
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
