from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import pytest

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.user import AuthSession, User


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_register_creates_user_hashes_password_and_sets_session_cookie(client, test_db):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Giuseppe Pitruzzella",
            "email": "GIUSEPPE@example.com",
            "password": "super-secret-password",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user"]["email"] == "giuseppe@example.com"
    assert body["user"]["full_name"] == "Giuseppe Pitruzzella"
    assert body["user"]["role"] == "quality_reviewer"
    assert settings.auth_cookie_name in response.cookies

    user = test_db.query(User).one()
    assert user.password_hash != "super-secret-password"
    assert user.password_hash.startswith("pbkdf2_sha256$")
    assert test_db.query(AuthSession).count() == 1


def test_me_returns_current_user_after_register(client):
    register = client.post(
        "/api/auth/register",
        json={
            "full_name": "Docente Demo",
            "email": "docente@example.com",
            "password": "password-demo-123",
        },
    )
    assert register.status_code == 201

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "docente@example.com"


def test_register_rejects_duplicate_email_case_insensitive(client):
    payload = {
        "full_name": "Docente Demo",
        "email": "docente@example.com",
        "password": "password-demo-123",
    }
    assert client.post("/api/auth/register", json=payload).status_code == 201

    duplicate = client.post(
        "/api/auth/register",
        json={**payload, "email": "DOCENTE@example.com"},
    )

    assert duplicate.status_code == 409


def test_login_sets_new_session_cookie(client, test_db):
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Docente Demo",
            "email": "docente@example.com",
            "password": "password-demo-123",
        },
    )
    client.cookies.clear()

    response = client.post(
        "/api/auth/login",
        json={"email": "docente@example.com", "password": "password-demo-123"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["user"]["email"] == "docente@example.com"
    assert settings.auth_cookie_name in response.cookies
    assert test_db.query(AuthSession).count() == 2


def test_login_rejects_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Docente Demo",
            "email": "docente@example.com",
            "password": "password-demo-123",
        },
    )
    client.cookies.clear()

    response = client.post(
        "/api/auth/login",
        json={"email": "docente@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert settings.auth_cookie_name not in response.cookies


def test_me_requires_session(client):
    client.cookies.clear()

    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_logout_revokes_session_and_clears_cookie(client, test_db):
    register = client.post(
        "/api/auth/register",
        json={
            "full_name": "Docente Demo",
            "email": "docente@example.com",
            "password": "password-demo-123",
        },
    )
    assert register.status_code == 201

    logout = client.post("/api/auth/logout")

    assert logout.status_code == 204
    assert test_db.query(AuthSession).one().revoked_at is not None
    assert client.get("/api/auth/me").status_code == 401


def test_change_password_requires_session(client):
    client.cookies.clear()

    response = client.post(
        "/api/auth/change-password",
        json={
            "current_password": "password-demo-123",
            "new_password": "password-demo-456",
        },
    )

    assert response.status_code == 401


def test_change_password_rejects_wrong_current_password(client):
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Docente Demo",
            "email": "docente@example.com",
            "password": "password-demo-123",
        },
    )

    response = client.post(
        "/api/auth/change-password",
        json={
            "current_password": "wrong-password",
            "new_password": "password-demo-456",
        },
    )

    assert response.status_code == 401


def test_change_password_rejects_same_password(client):
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Docente Demo",
            "email": "docente@example.com",
            "password": "password-demo-123",
        },
    )

    response = client.post(
        "/api/auth/change-password",
        json={
            "current_password": "password-demo-123",
            "new_password": "password-demo-123",
        },
    )

    assert response.status_code == 422


def test_change_password_updates_hash_and_login_credentials(client, test_db):
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Docente Demo",
            "email": "docente@example.com",
            "password": "password-demo-123",
        },
    )
    original_hash = test_db.query(User).one().password_hash

    response = client.post(
        "/api/auth/change-password",
        json={
            "current_password": "password-demo-123",
            "new_password": "password-demo-456",
        },
    )

    assert response.status_code == 200
    assert response.json()["email"] == "docente@example.com"
    assert test_db.query(User).one().password_hash != original_hash

    client.cookies.clear()
    old_login = client.post(
        "/api/auth/login",
        json={"email": "docente@example.com", "password": "password-demo-123"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/login",
        json={"email": "docente@example.com", "password": "password-demo-456"},
    )
    assert new_login.status_code == 200


def test_change_password_revokes_other_sessions(client, test_db):
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Docente Demo",
            "email": "docente@example.com",
            "password": "password-demo-123",
        },
    )
    primary_cookie = client.cookies.get(settings.auth_cookie_name)

    with TestClient(app) as other:
        other.cookies.clear()
        other_login = other.post(
            "/api/auth/login",
            json={"email": "docente@example.com", "password": "password-demo-123"},
        )
        assert other_login.status_code == 200
        other_cookie = other.cookies.get(settings.auth_cookie_name)
        assert other_cookie != primary_cookie

        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "password-demo-123",
                "new_password": "password-demo-456",
            },
        )

        assert response.status_code == 200
        assert client.get("/api/auth/me").status_code == 200
        assert other.get("/api/auth/me").status_code == 401
    revoked = [s for s in test_db.query(AuthSession).all() if s.revoked_at is not None]
    assert len(revoked) == 1
