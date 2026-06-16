import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


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


def _register(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Authorized Reviewer",
            "email": "reviewer@example.com",
            "password": "password-demo-123",
        },
    )
    assert response.status_code == 201, response.text


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/departments"),
        ("GET", "/api/stats"),
        ("GET", "/api/departments/1/cdl"),
        ("GET", "/api/cdl/1/syllabi"),
        ("GET", "/api/syllabi/SEUID-DEMO"),
        ("GET", "/api/syllabi/SEUID-DEMO/resolution-preview"),
        ("GET", "/api/syllabi/SEUID-DEMO/evaluations"),
        ("GET", "/api/evaluations/eval-demo"),
        ("GET", "/api/evaluations/eval-demo/stream"),
        ("GET", "/api/local-documents"),
        ("GET", "/api/local-documents/stream/job-demo"),
        ("POST", "/api/evaluate/SEUID-DEMO"),
        ("POST", "/api/scrape/departments"),
        ("POST", "/api/scrape/departments/1/cdl"),
        ("POST", "/api/scrape/cdl/1/syllabi"),
    ],
)
def test_application_api_requires_session(client, method, path):
    response = client.request(method, path)

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_protected_api_allows_valid_session(client):
    _register(client)

    response = client.get("/api/stats")

    assert response.status_code == 200
    assert response.json() == {
        "departments": 0,
        "cdl": 0,
        "syllabi": 0,
        "with_english": 0,
    }


def test_logout_revokes_access_to_protected_api(client):
    _register(client)
    assert client.get("/api/stats").status_code == 200

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204

    response = client.get("/api/stats")
    assert response.status_code == 401
