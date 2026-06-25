from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import CorsoDiLaurea, Department, EvaluationResult, Syllabus


@pytest.fixture()
def client_and_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    _seed(Session)

    def _get_db():
        with Session() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    try:
        with TestClient(app) as client:
            yield client, Session
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)


def test_single_export_returns_docx_attachment(client_and_session):
    client, _ = client_and_session

    response = client.get("/api/exports/evaluations/latest.docx")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument"
    )
    assert "LM_18__Course_1" in response.headers["content-disposition"]
    with ZipFile(BytesIO(response.content)) as archive:
        assert "word/document.xml" in archive.namelist()


def test_failed_single_export_is_not_available(client_and_session):
    client, _ = client_and_session

    response = client.get("/api/exports/evaluations/failed.docx")

    assert response.status_code == 404


def test_cdl_export_returns_zip_with_latest_non_failed_per_syllabus(
    client_and_session,
):
    client, _ = client_and_session

    response = client.get("/api/exports/cdl/1.zip")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    with ZipFile(BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert len(names) == 2
        assert len(set(names)) == 2
        assert any("__2.docx" in name for name in names)
        assert all(name.endswith(".docx") for name in names)
        assert not any("old" in name or "failed" in name for name in names)


def _seed(Session) -> None:
    now = datetime(2026, 6, 25, tzinfo=timezone.utc)
    with Session() as session:
        session.add(
            Department(
                id=1,
                name="DMI",
                area="Scientifica",
                website_url="https://example.test",
                email="dmi@example.test",
                phone="0",
                director="Direttore",
                scraped_at=now,
            )
        )
        session.add(
            CorsoDiLaurea(
                id=1,
                department_id=1,
                name="Informatica",
                code="LM-18",
                type="Magistrale",
                academic_year="2025/2026",
                url="https://example.test/lm18",
                scraped_at=now,
            )
        )
        for syllabus_id in (1, 2):
            fields = {
                "id": syllabus_id,
                "cdl_id": 1,
                "seuid": f"SEUID-{syllabus_id}",
                "course_code": f"CODE-{syllabus_id}",
                "course_name": "Course 1",
                "teacher": "Docente",
                "academic_year": "2025/2026",
                "year_of_study": "1",
                "url_it": "https://example.test/it",
                "url_en": "https://example.test/en",
                "has_english": False,
                "scraped_at": now,
            }
            for field in (
                "learning_outcomes_it", "dublin_knowledge_it",
                "dublin_applying_it", "dublin_judgement_it",
                "dublin_communication_it", "dublin_learning_it",
                "teaching_methods_it", "prerequisites_it", "attendance_it",
                "course_content_it", "references_it", "assessment_methods_it",
                "sample_questions_it",
            ):
                fields[field] = f"Testo {field}"
            session.add(Syllabus(**fields))
        session.flush()
        _add_evaluation(
            session, uuid="old", syllabus_id=1, status="completed",
            started=now - timedelta(days=2),
        )
        _add_evaluation(
            session, uuid="latest", syllabus_id=1, status="partial",
            started=now,
        )
        _add_evaluation(
            session, uuid="failed", syllabus_id=1, status="failed",
            started=now + timedelta(hours=1),
        )
        _add_evaluation(
            session, uuid="second-course", syllabus_id=2, status="completed",
            started=now,
        )
        session.commit()


def _add_evaluation(
    session,
    *,
    uuid: str,
    syllabus_id: int,
    status: str,
    started: datetime,
) -> None:
    session.add(
        EvaluationResult(
            evaluation_uuid=uuid,
            syllabus_id=syllabus_id,
            syllabus_seuid_snapshot=f"SEUID-{syllabus_id}",
            course_name_snapshot="Course 1",
            status=status,
            started_at=started,
            finished_at=started + timedelta(seconds=5),
            duration_ms=5000,
            llm_model="gemini-2.5-flash",
            embedding_model="gemini-embedding-001",
            embedding_dim=3072,
            llm_temperature=0.1,
            llm_max_output_tokens=8192,
            rag_top_k=5,
            rag_final_k=3,
            rag_similarity_threshold=0.6,
            gcp_project_id="test",
            gcp_location="europe-west8",
            prompt_versions={},
            core_score=None if status == "failed" else 2.0,
            coverage=None if status == "failed" else 1.0,
            criterion_scores=None if status == "failed" else {
                f"C{i}": 2 for i in range(1, 10)
            },
            na_criteria=[],
            agent_outputs={},
            agent_errors={},
            retrieved_chunks={},
            final_report="Report",
        )
    )
