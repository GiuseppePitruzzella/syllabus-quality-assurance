"""Tests for GET /api/departments/{dept_id}/cdl."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.cdl import CorsoDiLaurea
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


def _make_dept(db, name="DMI", url="https://web.dmi.unict.it"):
    dept = Department(
        name=name,
        area="Scienze",
        website_url=url,
        email="dmi@unict.it",
        phone="095123",
        director="Direttore",
        scraped_at=datetime.now(timezone.utc),
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


def _make_cdl(db, dept_id, name, cdl_type, code="l-99"):
    cdl = CorsoDiLaurea(
        department_id=dept_id,
        name=name,
        code=code,
        type=cdl_type,
        academic_year=None,
        url=f"https://example.com/corsi/{code}",
        scraped_at=datetime.now(timezone.utc),
    )
    db.add(cdl)
    db.commit()
    db.refresh(cdl)
    return cdl


# ---------------------------------------------------------------------------
# GET /api/departments/{dept_id}/cdl
# ---------------------------------------------------------------------------


def test_list_cdl_empty(client, test_db):
    dept = _make_dept(test_db)
    resp = client.get(f"/api/departments/{dept.id}/cdl")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_cdl_with_data(client, test_db):
    dept = _make_dept(test_db)
    _make_cdl(test_db, dept.id, "Informatica", "Triennale", code="l-31")
    resp = client.get(f"/api/departments/{dept.id}/cdl")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Informatica"
    assert data[0]["type"] == "Triennale"


def test_list_cdl_ordering_type_then_name(client, test_db):
    """Triennale comes before Magistrale; within same type, alphabetical by name."""
    dept = _make_dept(test_db)
    _make_cdl(test_db, dept.id, "Matematica", "Magistrale", code="lm-40")
    _make_cdl(test_db, dept.id, "Informatica", "Magistrale", code="lm-18")
    _make_cdl(test_db, dept.id, "Matematica", "Triennale", code="l-35")
    _make_cdl(test_db, dept.id, "Informatica", "Triennale", code="l-31")

    resp = client.get(f"/api/departments/{dept.id}/cdl")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4

    # First two must be Triennale
    assert data[0]["type"] == "Triennale"
    assert data[1]["type"] == "Triennale"
    # Within Triennale: alphabetical (Informatica < Matematica)
    assert data[0]["name"] == "Informatica"
    assert data[1]["name"] == "Matematica"

    # Last two must be Magistrale
    assert data[2]["type"] == "Magistrale"
    assert data[3]["type"] == "Magistrale"
    assert data[2]["name"] == "Informatica"
    assert data[3]["name"] == "Matematica"


def test_list_cdl_ciclo_unico_last(client, test_db):
    dept = _make_dept(test_db)
    _make_cdl(test_db, dept.id, "Medicina", "Ciclo Unico", code="lmg-41")
    _make_cdl(test_db, dept.id, "Informatica", "Triennale", code="l-31")

    resp = client.get(f"/api/departments/{dept.id}/cdl")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["type"] == "Triennale"
    assert data[1]["type"] == "Ciclo Unico"


def test_list_cdl_404_nonexistent_dept(client):
    resp = client.get("/api/departments/9999/cdl")
    assert resp.status_code == 404


def test_list_cdl_does_not_return_other_dept(client, test_db):
    dept1 = _make_dept(test_db, name="DMI")
    dept2 = _make_dept(test_db, name="DICAR")
    _make_cdl(test_db, dept1.id, "Informatica", "Triennale", code="l-31")
    _make_cdl(test_db, dept2.id, "Architettura", "Triennale", code="l-17")

    resp = client.get(f"/api/departments/{dept1.id}/cdl")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Informatica"
