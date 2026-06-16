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
