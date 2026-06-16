from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import AuthSession, User

PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 210_000
SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return (
        f"pbkdf2_{PBKDF2_ALGORITHM}"
        f"${PBKDF2_ITERATIONS}"
        f"${salt.hex()}"
        f"${digest.hex()}"
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, iterations_s, salt_hex, expected_hex = password_hash.split("$", 3)
        if scheme != f"pbkdf2_{PBKDF2_ALGORITHM}":
            return False
        iterations = int(iterations_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def make_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, user: User) -> tuple[str, AuthSession]:
    token = make_session_token()
    expires_at = datetime.utcnow() + timedelta(days=settings.auth_session_days)
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return token, session


def get_user_for_session_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    now = datetime.utcnow()
    session = (
        db.query(AuthSession)
        .filter(AuthSession.token_hash == hash_session_token(token))
        .filter(AuthSession.revoked_at.is_(None))
        .filter(AuthSession.expires_at > now)
        .first()
    )
    if session is None or session.user is None or not session.user.is_active:
        return None
    session.last_seen_at = now
    db.commit()
    return session.user


def revoke_session_token(db: Session, token: str | None) -> None:
    if not token:
        return
    session = (
        db.query(AuthSession)
        .filter(AuthSession.token_hash == hash_session_token(token))
        .filter(AuthSession.revoked_at.is_(None))
        .first()
    )
    if session is None:
        return
    session.revoked_at = datetime.utcnow()
    db.commit()
