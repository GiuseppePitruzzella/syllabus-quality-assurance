"""HTTP integration tests for the evaluation endpoints (Phase 5.4.H.2).

The FastAPI ``app`` is exercised through ``TestClient`` with the
``get_async_service`` dependency overridden by an offline implementation:
StaticPool in-memory SQLite + a fake graph_invoker that emits the
full sequence of progress events. No Vertex AI, no ChromaDB.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.evaluation import get_async_service
from app.config import Settings
from app.database import Base
from app.evaluation.agents.schemas import (
    AgentOutput,
    CriterionEvidence,
    CriterionJudgment,
)
from app.evaluation.aggregator import aggregate
from app.evaluation.async_service import AsyncEvaluationService
from app.evaluation.registry import EvaluationRegistry
from app.evaluation.service import EvaluationService
from app.evaluation.synthesizer import synthesize_report
from app.main import app
from app.models import CorsoDiLaurea, Department, Syllabus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _judgment(code: str, score: int = 2) -> CriterionJudgment:
    return CriterionJudgment(
        criterion_code=code,
        score=score,
        is_na=False,
        justification=f"Giustificazione per {code} sufficientemente articolata.",
        evidences=[CriterionEvidence(text=f"q-{code}", source_field="course_content_it")],
        confidence="medium",
    )


def _full_outputs() -> dict[str, AgentOutput]:
    return {
        "A1": AgentOutput(
            agent_code="A1",
            judgments=[_judgment("C1"), _judgment("C2"), _judgment("C5")],
            execution_metadata={"retry_count": 0},
        ),
        "A2": AgentOutput(
            agent_code="A2",
            judgments=[_judgment("C3"), _judgment("C4")],
            execution_metadata={"retry_count": 0},
        ),
        "A3": AgentOutput(
            agent_code="A3",
            judgments=[_judgment("C6"), _judgment("C7"), _judgment("C8")],
            execution_metadata={"retry_count": 0},
        ),
        "A4": AgentOutput(
            agent_code="A4",
            judgments=[_judgment("C9")],
            execution_metadata={"retry_count": 0},
        ),
    }


def _fake_invoker():
    outputs = _full_outputs()

    def _invoke(initial_state: dict[str, Any], *, progress_publisher=None):
        pub = progress_publisher or (lambda _e: None)
        seuid = initial_state.get("syllabus_seuid")
        for code in ("A1", "A2", "A3", "A4"):
            pub({"type": "agent_started", "agent_code": code, "seuid": seuid})
            pub(
                {
                    "type": "agent_completed",
                    "agent_code": code,
                    "seuid": seuid,
                    "latency_ms": 10,
                    "n_judgments": len(outputs[code].judgments),
                }
            )
        agg = aggregate(outputs, {})
        pub(
            {
                "type": "aggregation_completed",
                "seuid": seuid,
                "status": agg.status,
                "core_score": agg.core_score,
                "coverage": agg.coverage,
                "n_na": len(agg.na_criteria),
            }
        )
        report = synthesize_report(
            initial_state.get("course_name", "X"), agg, outputs
        )
        pub(
            {
                "type": "report_synthesized",
                "seuid": seuid,
                "report_chars": len(report),
            }
        )
        return {
            **initial_state,
            "agent_outputs": outputs,
            "agent_errors": {},
            "aggregation": agg,
            "final_report": report,
            "status": agg.status,
            "started_at": datetime.now(timezone.utc),
            "finished_at": datetime.now(timezone.utc),
        }

    return _invoke


def _seed_syllabus(Session, seuid: str = "SEUID-HTTP") -> str:
    with Session() as session:
        now = datetime(2026, 5, 18, tzinfo=timezone.utc)
        session.add_all(
            [
                Department(
                    id=1,
                    name="DMI",
                    area="Scientifica",
                    website_url="https://x",
                    email="dmi@example",
                    phone="000",
                    director="X",
                    scraped_at=now,
                ),
                CorsoDiLaurea(
                    id=1,
                    department_id=1,
                    name="LM-18",
                    code="LM-18",
                    type="laurea_magistrale",
                    academic_year="2025/2026",
                    url="https://x",
                    scraped_at=now,
                ),
            ]
        )
        session.flush()
        syllabus = Syllabus(
            cdl_id=1,
            seuid=seuid,
            course_code="9999",
            course_name="Deep Learning",
            teacher="Mario Rossi",
            academic_year="2025/2026",
            year_of_study="2",
            url_it="https://x/it",
            url_en="https://x/en",
            has_english=True,
            scraped_at=now,
            learning_outcomes_it="RA",
            dublin_knowledge_it="K",
            dublin_applying_it="A",
            dublin_judgement_it="J",
            dublin_communication_it="C",
            dublin_learning_it="L",
            teaching_methods_it="Lezioni",
            prerequisites_it="Pre",
            attendance_it="Att",
            course_content_it="Cont",
            references_it="Ref",
            assessment_methods_it="Verifica",
            sample_questions_it="Esempi",
        )
        session.add(syllabus)
        session.commit()
        return seuid


# ---------------------------------------------------------------------------
# App fixture with dependency override
# ---------------------------------------------------------------------------


@pytest.fixture()
def client_and_seuid():
    """TestClient + seeded seuid + isolated AsyncEvaluationService.

    Each test gets its own in-memory DB so they don't leak state.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    seuid = _seed_syllabus(Session)

    settings = Settings(gcp_project_id="test-project", gcp_location="europe-west1")
    sync = EvaluationService(
        session_factory=Session, graph_invoker=_fake_invoker(), settings=settings
    )
    async_svc = AsyncEvaluationService(
        sync_service=sync, registry=EvaluationRegistry(), settings=settings
    )

    app.dependency_overrides[get_async_service] = lambda: async_svc
    with TestClient(app) as client:
        yield client, seuid, async_svc
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_post_evaluate_returns_202_with_uuid(client_and_seuid):
    client, seuid, _ = client_and_seuid
    response = client.post(f"/api/evaluate/{seuid}")
    assert response.status_code == 202
    body = response.json()
    assert "evaluation_uuid" in body
    assert body["evaluation_uuid"]


def test_post_evaluate_unknown_seuid_returns_404(client_and_seuid):
    client, _, _ = client_and_seuid
    response = client.post("/api/evaluate/DOES-NOT-EXIST")
    assert response.status_code == 404


def test_get_evaluation_stream_yields_full_event_sequence(client_and_seuid):
    client, seuid, _ = client_and_seuid
    post = client.post(f"/api/evaluate/{seuid}")
    evaluation_uuid = post.json()["evaluation_uuid"]

    # Drain the SSE stream. TestClient surfaces SSE frames as
    # ``data: {...}`` lines in the streamed body.
    with client.stream(
        "GET", f"/api/evaluations/{evaluation_uuid}/stream"
    ) as response:
        assert response.status_code == 200
        events: list[dict[str, Any]] = []
        for line in response.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            payload = json.loads(line[len("data:") :].strip())
            events.append(payload)

    types = [e["type"] for e in events]
    assert types[0] == "evaluation_started"
    assert types[-1] == "evaluation_completed"
    assert types.count("agent_started") == 4
    assert types.count("agent_completed") == 4
    assert "aggregation_completed" in types
    assert "report_synthesized" in types
    # Every event carries the same UUID.
    assert {e["evaluation_uuid"] for e in events} == {evaluation_uuid}


def test_get_evaluation_returns_persisted_row(client_and_seuid):
    client, seuid, _ = client_and_seuid
    post = client.post(f"/api/evaluate/{seuid}")
    evaluation_uuid = post.json()["evaluation_uuid"]

    # Drain the stream first to ensure the worker finished.
    with client.stream(
        "GET", f"/api/evaluations/{evaluation_uuid}/stream"
    ) as response:
        for _ in response.iter_lines():
            pass

    get = client.get(f"/api/evaluations/{evaluation_uuid}")
    assert get.status_code == 200
    body = get.json()
    assert body["evaluation_uuid"] == evaluation_uuid
    assert body["status"] == "completed"
    assert body["core_score"] == 2.0
    assert body["coverage"] == 1.0
    assert body["final_report"].startswith("# Report di valutazione")
    assert body["criterion_scores"]["C1"] == 2
    assert body["llm_model"] == "gemini-2.5-flash"
    assert body["gcp_project_id"] == "test-project"
    # Phase 9.C.5.3: A5 coordinator version is now tracked alongside A1-A4.
    assert set(body["prompt_versions"].keys()) == {"A1", "A2", "A3", "A4", "A5"}


def test_get_evaluation_unknown_uuid_returns_404(client_and_seuid):
    client, _, _ = client_and_seuid
    response = client.get("/api/evaluations/does-not-exist")
    assert response.status_code == 404


def test_get_stream_unknown_uuid_returns_404(client_and_seuid):
    client, _, _ = client_and_seuid
    response = client.get("/api/evaluations/does-not-exist/stream")
    assert response.status_code == 404


def test_list_evaluations_history_orders_most_recent_first(client_and_seuid):
    client, seuid, _ = client_and_seuid
    uuids: list[str] = []
    for _ in range(3):
        post = client.post(f"/api/evaluate/{seuid}")
        evaluation_uuid = post.json()["evaluation_uuid"]
        uuids.append(evaluation_uuid)
        # Drain to ensure each row reaches "completed" before the next POST.
        with client.stream(
            "GET", f"/api/evaluations/{evaluation_uuid}/stream"
        ) as response:
            for _ in response.iter_lines():
                pass

    response = client.get(f"/api/syllabi/{seuid}/evaluations")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 3
    assert [r["evaluation_uuid"] for r in rows] == list(reversed(uuids))


def test_list_evaluations_unknown_seuid_returns_404(client_and_seuid):
    client, _, _ = client_and_seuid
    response = client.get("/api/syllabi/MISSING/evaluations")
    assert response.status_code == 404


def test_list_evaluations_respects_limit(client_and_seuid):
    client, seuid, _ = client_and_seuid
    for _ in range(3):
        post = client.post(f"/api/evaluate/{seuid}")
        with client.stream(
            "GET", f"/api/evaluations/{post.json()['evaluation_uuid']}/stream"
        ) as response:
            for _ in response.iter_lines():
                pass
    response = client.get(f"/api/syllabi/{seuid}/evaluations?limit=2")
    assert response.status_code == 200
    assert len(response.json()) == 2
