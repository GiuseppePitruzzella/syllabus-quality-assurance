from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.department import Department


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


def test_get_departments_empty(client):
    resp = client.get("/api/departments")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_departments_with_data(client, test_db):
    dept = Department(
        name="Matematica e Informatica",
        area="Area scientifica",
        website_url="https://web.dmi.unict.it",
        email="dmi@unict.it",
        phone="095123",
        director="Mario Rossi",
        scraped_at=datetime.now(timezone.utc),
    )
    test_db.add(dept)
    test_db.commit()

    resp = client.get("/api/departments")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Matematica e Informatica"
    assert data[0]["area"] == "Area scientifica"


