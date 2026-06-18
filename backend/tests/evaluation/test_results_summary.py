"""Regression tests for Phase 12 results summary endpoint."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.evaluation import get_sync_service
from app.database import Base
from app.evaluation.service import EvaluationService
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
    _seed_catalog(Session)

    def _noop_invoker(initial_state, *, progress_publisher=None):
        return initial_state

    service = EvaluationService(
        session_factory=Session,
        graph_invoker=_noop_invoker,
    )
    app.dependency_overrides[get_sync_service] = lambda: service
    try:
        with TestClient(app) as client:
            yield client, Session
    finally:
        app.dependency_overrides.pop(get_sync_service, None)
        Base.metadata.drop_all(engine)


def test_results_summary_uses_latest_terminal_run_per_syllabus(client_and_session):
    client, Session = client_and_session
    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    _seed_evaluation(
        Session,
        syllabus_id=1,
        uuid="old-completed",
        status="completed",
        started_at=now - timedelta(days=2),
        core_score=2.0,
        coverage=1.0,
        scores={f"C{i}": 2 for i in range(1, 10)},
    )
    _seed_evaluation(
        Session,
        syllabus_id=1,
        uuid="latest-partial",
        status="partial",
        started_at=now,
        core_score=1.5,
        coverage=1.0,
        scores={
            "C1": 0,
            "C2": 1,
            "C3": 2,
            "C4": 2,
            "C5": 2,
            "C6": 2,
            "C7": 2,
            "C8": 2,
            "C9": 2,
        },
    )
    _seed_evaluation(
        Session,
        syllabus_id=2,
        uuid="failed-run",
        status="failed",
        started_at=now - timedelta(hours=1),
        core_score=None,
        coverage=None,
        scores=None,
    )
    _seed_evaluation(
        Session,
        syllabus_id=3,
        uuid="running-ignored",
        status="running",
        started_at=now,
        core_score=None,
        coverage=None,
        scores=None,
    )

    response = client.get("/api/results/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["overview"]["latest_evaluations_count"] == 2
    assert payload["overview"]["terminal_runs_count"] == 3
    assert payload["overview"]["completed_count"] == 0
    assert payload["overview"]["partial_count"] == 1
    assert payload["overview"]["failed_count"] == 1
    assert payload["overview"]["average_core_score"] == 1.5
    assert payload["overview"]["average_coverage"] == 1.0
    assert payload["overview"]["total_critical_criteria"] == 1
    assert payload["overview"]["total_improvable_criteria"] == 1
    rows = {row["evaluation_uuid"]: row for row in payload["evaluations"]}
    assert set(rows) == {"latest-partial", "failed-run"}
    assert rows["latest-partial"]["critical_count"] == 1
    assert rows["failed-run"]["critical_count"] == 0


def test_results_summary_distribution_excludes_failed_and_counts_na(
    client_and_session,
):
    client, Session = client_and_session
    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    scores = {f"C{i}": 2 for i in range(1, 10)}
    scores["C4"] = None
    _seed_evaluation(
        Session,
        syllabus_id=1,
        uuid="scored-run",
        status="completed",
        started_at=now,
        core_score=2.0,
        coverage=8 / 9,
        scores=scores,
    )
    _seed_evaluation(
        Session,
        syllabus_id=2,
        uuid="failed-run",
        status="failed",
        started_at=now,
        core_score=None,
        coverage=None,
        scores=None,
    )

    response = client.get("/api/results/summary")

    assert response.status_code == 200
    criteria = {row["criterion_code"]: row for row in response.json()["criteria"]}
    assert criteria["C1"]["score_2"] == 1
    assert criteria["C1"]["evaluated"] == 1
    assert criteria["C4"]["na"] == 1
    assert criteria["C4"]["evaluated"] == 0
    assert response.json()["overview"]["total_na_criteria"] == 1


def _seed_catalog(Session) -> None:
    now = datetime(2026, 6, 18, tzinfo=timezone.utc)
    with Session() as session:
        dept = Department(
            id=1,
            name="Dipartimento di Matematica e Informatica",
            area="Scientifica",
            website_url="https://dmi.example",
            email="dmi@example",
            phone="0",
            director="Direttore",
            scraped_at=now,
        )
        cdl = CorsoDiLaurea(
            id=1,
            department_id=1,
            name="Informatica",
            code="LM-18",
            type="Laurea magistrale",
            academic_year="2025/2026",
            url="https://lm18.example",
            scraped_at=now,
        )
        session.add_all([dept, cdl])
        session.flush()
        for idx in range(1, 4):
            session.add(
                Syllabus(
                    id=idx,
                    cdl_id=1,
                    seuid=f"SEUID-{idx}",
                    course_code=f"CODE-{idx}",
                    course_name=f"Course {idx}",
                    teacher="Docente",
                    academic_year="2025/2026",
                    year_of_study="1",
                    url_it="https://it.example",
                    url_en="https://en.example",
                    has_english=True,
                    scraped_at=now,
                    learning_outcomes_it="RA",
                    dublin_knowledge_it="K",
                    dublin_applying_it="A",
                    dublin_judgement_it="J",
                    dublin_communication_it="C",
                    dublin_learning_it="L",
                    teaching_methods_it="M",
                    prerequisites_it="P",
                    attendance_it="A",
                    course_content_it="C",
                    references_it="R",
                    assessment_methods_it="V",
                    sample_questions_it="Q",
                ),
            )
        session.commit()


def _seed_evaluation(
    Session,
    *,
    syllabus_id: int,
    uuid: str,
    status: str,
    started_at: datetime,
    core_score: float | None,
    coverage: float | None,
    scores: dict[str, Any] | None,
) -> None:
    with Session() as session:
        session.add(
            EvaluationResult(
                evaluation_uuid=uuid,
                syllabus_id=syllabus_id,
                syllabus_seuid_snapshot=f"SEUID-{syllabus_id}",
                course_name_snapshot=f"Course {syllabus_id}",
                status=status,
                started_at=started_at,
                finished_at=started_at + timedelta(seconds=10),
                duration_ms=10_000,
                llm_model="gemini-2.5-flash",
                embedding_model="gemini-embedding-001",
                embedding_dim=3072,
                llm_temperature=0.1,
                llm_max_output_tokens=8192,
                rag_top_k=5,
                rag_final_k=3,
                rag_similarity_threshold=0.6,
                gcp_project_id="test-project",
                gcp_location="europe-west1",
                prompt_versions={"A1": "a1_v5"},
                core_score=core_score,
                coverage=coverage,
                criterion_scores=scores,
                na_criteria=[] if scores is not None else None,
                agent_outputs=None,
                agent_errors=None,
                retrieved_chunks=None,
                final_report=None,
            ),
        )
        session.commit()
