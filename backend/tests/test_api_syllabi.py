"""Tests for syllabi API and stats endpoints."""
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
from app.models.syllabus import Syllabus


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dept(db, name="DMI"):
    dept = Department(
        name=name,
        area="Scienze",
        website_url="https://web.dmi.unict.it",
        email="dmi@unict.it",
        phone="095123",
        director="Direttore",
        scraped_at=datetime.now(timezone.utc),
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


def _make_cdl(db, dept_id, name="Informatica", code="lm-18"):
    cdl = CorsoDiLaurea(
        department_id=dept_id,
        name=name,
        code=code,
        type="Magistrale",
        academic_year=None,
        url=f"https://web.dmi.unict.it/corsi/{code}",
        scraped_at=datetime.now(timezone.utc),
    )
    db.add(cdl)
    db.commit()
    db.refresh(cdl)
    return cdl


_EMPTY_CONTENT = {
    "dublin_knowledge_it": "",
    "dublin_applying_it": "",
    "dublin_judgement_it": "",
    "dublin_communication_it": "",
    "dublin_learning_it": "",
    "teaching_methods_it": "",
    "prerequisites_it": "",
    "attendance_it": "",
    "course_content_it": "",
    "references_it": "",
    "assessment_methods_it": "",
    "sample_questions_it": "",
    "schedule_it": None,
}


def _make_syllabus(
    db,
    cdl_id: int,
    seuid: str,
    course_code: str = "9799580",
    course_name: str = "Advanced Computer Graphics",
    year_of_study: str = "1",
    has_english: bool = False,
):
    syl = Syllabus(
        cdl_id=cdl_id,
        seuid=seuid,
        course_code=course_code,
        course_name=course_name,
        module=None,
        teacher="GALLO GIOVANNI",
        academic_year="",
        year_of_study=year_of_study,
        url_it=f"https://web.dmi.unict.it/corsi/lm-18/insegnamenti?seuid={seuid}",
        url_en=f"https://web.dmi.unict.it/corsi/lm-18/insegnamenti?seuid={seuid}&eng",
        has_english=has_english,
        scraped_at=datetime.now(timezone.utc),
        **_EMPTY_CONTENT,
    )
    db.add(syl)
    db.commit()
    db.refresh(syl)
    return syl


# ---------------------------------------------------------------------------
# GET /api/cdl/{cdl_id}/syllabi
# ---------------------------------------------------------------------------


def test_list_syllabi_empty(client, test_db):
    dept = _make_dept(test_db)
    cdl = _make_cdl(test_db, dept.id)
    resp = client.get(f"/api/cdl/{cdl.id}/syllabi")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_syllabi_with_data(client, test_db):
    dept = _make_dept(test_db)
    cdl = _make_cdl(test_db, dept.id)
    _make_syllabus(test_db, cdl.id, seuid="AAAA-1111")
    resp = client.get(f"/api/cdl/{cdl.id}/syllabi")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["seuid"] == "AAAA-1111"
    assert data[0]["course_name"] == "Advanced Computer Graphics"


def test_list_syllabi_ordered_by_year_then_name(client, test_db):
    dept = _make_dept(test_db)
    cdl = _make_cdl(test_db, dept.id)
    _make_syllabus(test_db, cdl.id, "BBBB-2222", course_name="Zeta Course", year_of_study="1")
    _make_syllabus(test_db, cdl.id, "CCCC-3333", course_name="Alpha Course", year_of_study="2")
    _make_syllabus(test_db, cdl.id, "DDDD-4444", course_name="Beta Course", year_of_study="1")

    resp = client.get(f"/api/cdl/{cdl.id}/syllabi")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    # year 1 comes first
    assert data[0]["year_of_study"] == "1"
    assert data[1]["year_of_study"] == "1"
    # Within year 1: alphabetical by name
    assert data[0]["course_name"] == "Beta Course"
    assert data[1]["course_name"] == "Zeta Course"
    # year 2 last
    assert data[2]["year_of_study"] == "2"


def test_list_syllabi_search_by_name(client, test_db):
    dept = _make_dept(test_db)
    cdl = _make_cdl(test_db, dept.id)
    _make_syllabus(test_db, cdl.id, "AAAA-0001", course_name="Deep Learning")
    _make_syllabus(test_db, cdl.id, "AAAA-0002", course_name="Machine Learning")
    _make_syllabus(test_db, cdl.id, "AAAA-0003", course_name="Computer Vision")

    resp = client.get(f"/api/cdl/{cdl.id}/syllabi?search=learning")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    names = {d["course_name"] for d in data}
    assert "Deep Learning" in names
    assert "Machine Learning" in names


def test_list_syllabi_search_by_code(client, test_db):
    dept = _make_dept(test_db)
    cdl = _make_cdl(test_db, dept.id)
    _make_syllabus(test_db, cdl.id, "AAAA-0001", course_code="9799580", course_name="Deep Learning")
    _make_syllabus(test_db, cdl.id, "AAAA-0002", course_code="1234567", course_name="Other Course")

    resp = client.get(f"/api/cdl/{cdl.id}/syllabi?search=9799580")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["course_code"] == "9799580"


def test_list_syllabi_search_case_insensitive(client, test_db):
    dept = _make_dept(test_db)
    cdl = _make_cdl(test_db, dept.id)
    _make_syllabus(test_db, cdl.id, "AAAA-0001", course_name="Deep Learning")

    resp = client.get(f"/api/cdl/{cdl.id}/syllabi?search=DEEP")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_syllabi_404_nonexistent_cdl(client):
    resp = client.get("/api/cdl/9999/syllabi")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/syllabi/{seuid}
# ---------------------------------------------------------------------------


def test_get_syllabus_detail(client, test_db):
    dept = _make_dept(test_db)
    cdl = _make_cdl(test_db, dept.id)
    _make_syllabus(test_db, cdl.id, seuid="BEEF-DEAD")

    resp = client.get("/api/syllabi/BEEF-DEAD")
    assert resp.status_code == 200
    data = resp.json()
    assert data["seuid"] == "BEEF-DEAD"
    assert data["course_name"] == "Advanced Computer Graphics"
    # Content fields present in detail
    assert "dublin_knowledge_it" in data


def test_get_syllabus_404(client):
    resp = client.get("/api/syllabi/DOES-NOT-EXIST")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Phase 3 stubs
# ---------------------------------------------------------------------------


def test_scrape_single_syllabus_returns_501(client):
    resp = client.post("/api/scrape/syllabi/some-seuid")
    assert resp.status_code == 501


def test_scrape_all_syllabi_returns_501(client):
    resp = client.post("/api/scrape/cdl/1/syllabi/all")
    assert resp.status_code == 501


# ---------------------------------------------------------------------------
# GET /api/stats
# ---------------------------------------------------------------------------


def test_stats_empty_db(client):
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"departments": 0, "cdl": 0, "syllabi": 0, "with_english": 0}


def test_stats_with_data(client, test_db):
    dept = _make_dept(test_db)
    cdl = _make_cdl(test_db, dept.id)
    _make_syllabus(test_db, cdl.id, seuid="AAAA-0001", has_english=False)
    _make_syllabus(test_db, cdl.id, seuid="AAAA-0002", has_english=True)

    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["departments"] == 1
    assert data["cdl"] == 1
    assert data["syllabi"] == 2
    assert data["with_english"] == 1
