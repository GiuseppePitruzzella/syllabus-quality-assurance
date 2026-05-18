"""Tests for the AsyncEvaluationService + EvaluationRegistry (Phase 5.4.H.2).

Offline: no FastAPI, no Vertex AI. The sync service is wrapped in
the async layer; the graph is replaced by a fake invoker that calls
the publisher with synthetic events. The registry is exercised
through the wrapper.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
from app.evaluation.service import EvaluationService, SyllabusNotFoundError
from app.evaluation.synthesizer import synthesize_report
from app.models import CorsoDiLaurea, Department, Syllabus
from app.schemas.evaluation_event import ProgressEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session_factory():
    # StaticPool keeps a single connection across all sessions so the
    # in-memory DB stays consistent when ``asyncio.to_thread`` opens a
    # session from a worker thread (each new connection on ``:memory:``
    # otherwise gets a fresh empty DB).
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield Session
    finally:
        Base.metadata.drop_all(engine)


@pytest.fixture()
def seeded_seuid(session_factory):
    with session_factory() as session:
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
            seuid="SEUID-ASYNC",
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
        return syllabus.seuid


@pytest.fixture()
def fake_settings():
    return Settings(gcp_project_id="test-project", gcp_location="europe-west1")


# ---------------------------------------------------------------------------
# Fakes
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


def _make_invoker_emitting_events(outputs: dict[str, AgentOutput]):
    """Fake graph_invoker that emits the 5 graph-side events through the publisher."""

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


def _make_invoker_raising(exc: Exception):
    def _invoke(initial_state: dict[str, Any], *, progress_publisher=None):
        raise exc

    return _invoke


def _make_invoker_slow(delay_s: float):
    """Invoker that simply sleeps; used to test timeout."""

    def _invoke(initial_state: dict[str, Any], *, progress_publisher=None):
        import time

        time.sleep(delay_s)
        return {
            **initial_state,
            "agent_outputs": {},
            "agent_errors": {},
            "aggregation": None,
            "final_report": None,
            "status": "completed",
            "started_at": datetime.now(timezone.utc),
            "finished_at": datetime.now(timezone.utc),
        }

    return _invoke


def _build_services(session_factory, settings, invoker):
    sync = EvaluationService(
        session_factory=session_factory, graph_invoker=invoker, settings=settings
    )
    return AsyncEvaluationService(
        sync_service=sync, registry=EvaluationRegistry(), settings=settings
    )


async def _drain(state, max_events: int = 20) -> list[ProgressEvent]:
    events: list[ProgressEvent] = []
    while len(events) < max_events:
        item = await asyncio.wait_for(state.queue.get(), timeout=5.0)
        if item is None:
            break
        events.append(item)
    return events


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_evaluation_returns_uuid_immediately(
    session_factory, seeded_seuid, fake_settings
):
    svc = _build_services(
        session_factory,
        fake_settings,
        _make_invoker_emitting_events(_full_outputs()),
    )
    evaluation_uuid = await svc.start_evaluation(seeded_seuid)
    assert evaluation_uuid
    # Drain to let the background task complete and clean up.
    state = svc.registry.get(evaluation_uuid)
    await _drain(state)
    await asyncio.gather(*svc._tasks, return_exceptions=True)  # noqa: SLF001


@pytest.mark.asyncio
async def test_full_event_sequence_is_emitted(
    session_factory, seeded_seuid, fake_settings
):
    svc = _build_services(
        session_factory,
        fake_settings,
        _make_invoker_emitting_events(_full_outputs()),
    )
    evaluation_uuid = await svc.start_evaluation(seeded_seuid)
    state = svc.registry.get(evaluation_uuid)
    events = await _drain(state)
    types = [e.type for e in events]
    # First event must be evaluation_started, last must be evaluation_completed.
    assert types[0] == "evaluation_started"
    assert types[-1] == "evaluation_completed"
    # Each of the 4 agents should show up with started + completed.
    assert types.count("agent_started") == 4
    assert types.count("agent_completed") == 4
    # One aggregation + one synthesis.
    assert types.count("aggregation_completed") == 1
    assert types.count("report_synthesized") == 1
    # Final event carries the score + coverage.
    final = events[-1]
    assert final.status == "completed"
    assert final.coverage == 1.0
    assert final.core_score is not None
    assert final.duration_ms is not None
    await asyncio.gather(*svc._tasks, return_exceptions=True)  # noqa: SLF001


@pytest.mark.asyncio
async def test_graph_exception_yields_error_event_and_failed_row(
    session_factory, seeded_seuid, fake_settings
):
    svc = _build_services(
        session_factory,
        fake_settings,
        _make_invoker_raising(RuntimeError("graph blew up")),
    )
    evaluation_uuid = await svc.start_evaluation(seeded_seuid)
    state = svc.registry.get(evaluation_uuid)
    events = await _drain(state)
    types = [e.type for e in events]
    assert types[0] == "evaluation_started"
    # The sync service catches the exception and persists "failed",
    # so the worker thread completes normally and the async wrapper
    # emits ``evaluation_completed`` (not ``error``). The row carries
    # the failure marker — verified via the underlying sync service.
    assert "evaluation_completed" in types
    row = svc._sync.get_evaluation(evaluation_uuid)  # noqa: SLF001
    assert row.status == "failed"
    assert "RuntimeError" in row.error_message
    await asyncio.gather(*svc._tasks, return_exceptions=True)  # noqa: SLF001


@pytest.mark.asyncio
async def test_unknown_seuid_raises_before_scheduling(
    session_factory, fake_settings
):
    svc = _build_services(
        session_factory,
        fake_settings,
        _make_invoker_emitting_events(_full_outputs()),
    )
    with pytest.raises(SyllabusNotFoundError):
        await svc.start_evaluation("DOES-NOT-EXIST")
    # No background task should have been created.
    assert not svc._tasks  # noqa: SLF001


@pytest.mark.asyncio
async def test_timeout_marks_row_failed_and_emits_error(
    session_factory, seeded_seuid
):
    short_timeout_settings = Settings(
        gcp_project_id="test-project",
        gcp_location="europe-west1",
        evaluation_timeout_seconds=1,
    )
    svc = _build_services(
        session_factory,
        short_timeout_settings,
        _make_invoker_slow(delay_s=5.0),
    )
    evaluation_uuid = await svc.start_evaluation(seeded_seuid)
    state = svc.registry.get(evaluation_uuid)
    events = await _drain(state)
    types = [e.type for e in events]
    assert types[0] == "evaluation_started"
    # Last event is ``error`` with TimeoutError.
    assert types[-1] == "error"
    assert events[-1].error_type == "TimeoutError"
    # Row is marked failed with timeout message.
    row = svc._sync.get_evaluation(evaluation_uuid)  # noqa: SLF001
    assert row.status == "failed"
    assert "timeout" in row.error_message.lower()
    await asyncio.gather(*svc._tasks, return_exceptions=True)  # noqa: SLF001


@pytest.mark.asyncio
async def test_registry_cleanup_sentinel_is_enqueued(
    session_factory, seeded_seuid, fake_settings
):
    svc = _build_services(
        session_factory,
        fake_settings,
        _make_invoker_emitting_events(_full_outputs()),
    )
    evaluation_uuid = await svc.start_evaluation(seeded_seuid)
    state = svc.registry.get(evaluation_uuid)
    # Drain until the sentinel; if the registry forgot to enqueue it,
    # this test would block forever (asyncio.wait_for keeps us safe).
    await _drain(state)
    # After the sentinel the queue is logically closed: completed_at is set.
    assert state.completed_at is not None
    await asyncio.gather(*svc._tasks, return_exceptions=True)  # noqa: SLF001


@pytest.mark.asyncio
async def test_publisher_drops_malformed_events_without_crashing(
    session_factory, seeded_seuid, fake_settings
):
    def _bad_invoker(initial_state, *, progress_publisher=None):
        # Send a payload missing the ``type`` field — must be dropped silently.
        if progress_publisher:
            progress_publisher({"agent_code": "A1"})
        return {
            **initial_state,
            "agent_outputs": _full_outputs(),
            "agent_errors": {},
            "aggregation": aggregate(_full_outputs(), {}),
            "final_report": "ok",
            "status": "completed",
            "started_at": datetime.now(timezone.utc),
            "finished_at": datetime.now(timezone.utc),
        }

    svc = _build_services(session_factory, fake_settings, _bad_invoker)
    evaluation_uuid = await svc.start_evaluation(seeded_seuid)
    state = svc.registry.get(evaluation_uuid)
    events = await _drain(state)
    types = [e.type for e in events]
    # First + last events are still well-formed; the malformed mid-event was dropped.
    assert types[0] == "evaluation_started"
    assert types[-1] == "evaluation_completed"
    await asyncio.gather(*svc._tasks, return_exceptions=True)  # noqa: SLF001
