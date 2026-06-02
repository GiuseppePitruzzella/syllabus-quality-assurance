"""Tests for the sync EvaluationService (Phase 5.4.H.1).

Everything is offline: no Vertex AI, no LangGraph, no ChromaDB. The
graph is replaced by a fake invoker that returns hand-crafted
``EvaluationState`` dicts. The service is exercised against an
in-memory SQLite DB.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import ScientificConfig, Settings
from app.database import Base
from app.evaluation.agents.schemas import (
    AgentOutput,
    CriterionEvidence,
    CriterionJudgment,
    RetrievedChunkRef,
)
from app.evaluation.aggregator import aggregate
from app.evaluation.service import (
    DEFAULT_PROMPT_VERSIONS,
    EvaluationService,
    SyllabusNotFoundError,
)
from app.evaluation.synthesizer import synthesize_report
from app.models import CorsoDiLaurea, Department, Syllabus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session_factory():
    """In-memory SQLite session factory shared between service and tests."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield Session
    finally:
        Base.metadata.drop_all(engine)


@pytest.fixture()
def seeded_syllabus(session_factory):
    with session_factory() as session:
        now = datetime(2026, 5, 17, tzinfo=timezone.utc)
        dept = Department(
            id=1,
            name="DMI",
            area="Scientifica",
            website_url="https://x",
            email="dmi@example",
            phone="000",
            director="X",
            scraped_at=now,
        )
        cdl = CorsoDiLaurea(
            id=1,
            department_id=1,
            name="LM-18",
            code="LM-18",
            type="laurea_magistrale",
            academic_year="2025/2026",
            url="https://x",
            scraped_at=now,
        )
        session.add_all([dept, cdl])
        session.flush()
        syllabus = Syllabus(
            cdl_id=1,
            seuid="SEUID-A",
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
    """A Settings object that already satisfies require_vertex_ai_config()."""
    s = Settings(gcp_project_id="test-project", gcp_location="europe-west1")
    return s


# ---------------------------------------------------------------------------
# Graph invokers (fakes)
# ---------------------------------------------------------------------------


def _judgment(code: str, *, score: int | None = 2, is_na: bool = False, na_reason: str | None = None):
    return CriterionJudgment(
        criterion_code=code,
        score=score,
        is_na=is_na,
        na_reason=na_reason,
        justification=f"Giudizio per {code} sufficientemente lungo per la validation.",
        evidences=[CriterionEvidence(text=f"q-{code}", source_field="course_content_it")],
        confidence="medium",
    )


def _agent_output(agent_code: str, *judgments, chunks: list[RetrievedChunkRef] | None = None) -> AgentOutput:
    return AgentOutput(
        agent_code=agent_code,
        judgments=list(judgments),
        execution_metadata={"retry_count": 0, "prompt_version": "fake_v1"},
        retrieved_chunks=chunks or [],
    )


def _full_outputs() -> dict[str, AgentOutput]:
    return {
        "A1": _agent_output(
            "A1",
            _judgment("C1"),
            _judgment("C2", score=1),
            _judgment("C5", score=1),
            chunks=[
                RetrievedChunkRef(
                    criterion_code="C1",
                    chunk_id="lg_unict__2__0",
                    document_id="lg_unict",
                    section_ref="2",
                    similarity_score=0.78,
                )
            ],
        ),
        "A2": _agent_output(
            "A2",
            _judgment("C3"),
            _judgment("C4"),
            chunks=[
                RetrievedChunkRef(
                    criterion_code="C3",
                    chunk_id="lg_unict__3.1__0",
                    document_id="lg_unict",
                    section_ref="3.1",
                    similarity_score=0.80,
                )
            ],
        ),
        "A3": _agent_output(
            "A3",
            _judgment("C6"),
            _judgment("C7"),
            _judgment("C8"),
        ),
        "A4": _agent_output("A4", _judgment("C9", score=1)),
    }


def _make_invoker(
    outputs: dict[str, AgentOutput],
    errors: dict[str, str] | None = None,
    raise_exc: Exception | None = None,
):
    """Return a fake graph_invoker producing a synthesised final_state."""
    errors = errors or {}

    def _invoke(initial_state: dict[str, Any]) -> dict[str, Any]:
        if raise_exc is not None:
            raise raise_exc
        agg = aggregate(outputs, errors)
        report = synthesize_report(
            initial_state.get("course_name", "X"), agg, outputs
        )
        return {
            **initial_state,
            "agent_outputs": outputs,
            "agent_errors": errors,
            "aggregation": agg,
            "final_report": report,
            "status": agg.status,
            "started_at": datetime.now(timezone.utc),
            "finished_at": datetime.now(timezone.utc),
        }

    return _invoke


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_evaluate_creates_pending_record_then_persists_completed(
    session_factory, seeded_syllabus, fake_settings
):
    outputs = _full_outputs()
    svc = EvaluationService(
        session_factory=session_factory,
        graph_invoker=_make_invoker(outputs),
        settings=fake_settings,
    )

    record = svc.evaluate(seeded_syllabus)
    assert record.status == "completed"
    assert record.evaluation_uuid
    assert record.core_score is not None
    assert record.coverage == 1.0
    assert record.criterion_scores["C1"] == 2
    assert record.criterion_scores["C2"] == 1
    assert record.final_report.startswith("# Report di valutazione")
    assert record.duration_ms is not None
    assert record.duration_ms >= 0
    # Snapshots are populated
    assert record.syllabus_seuid_snapshot == seeded_syllabus
    assert record.course_name_snapshot == "Deep Learning"


def test_evaluate_records_scientific_configuration(
    session_factory, seeded_syllabus, fake_settings
):
    """Every persisted record carries the full ScientificConfig snapshot
    (D025 + D026 + D027 + D030)."""
    svc = EvaluationService(
        session_factory=session_factory,
        graph_invoker=_make_invoker(_full_outputs()),
        settings=fake_settings,
    )
    record = svc.evaluate(seeded_syllabus)
    sci = ScientificConfig()
    assert record.llm_model == sci.llm_model
    assert record.embedding_model == sci.embedding_model
    assert record.embedding_dim == sci.embedding_output_dimensionality
    assert record.llm_temperature == sci.llm_temperature
    assert record.llm_max_output_tokens == sci.llm_max_output_tokens
    assert record.rag_top_k == sci.rag_top_k
    assert record.rag_final_k == sci.rag_final_k
    assert record.rag_similarity_threshold == sci.rag_similarity_threshold
    assert record.gcp_project_id == "test-project"
    assert record.gcp_location == "europe-west1"
    # Per-agent prompt versions snapshot
    assert set(record.prompt_versions.keys()) == {"A1", "A2", "A3", "A4"}


def test_evaluate_persists_retrieved_chunks_grouped_by_criterion(
    session_factory, seeded_syllabus, fake_settings
):
    svc = EvaluationService(
        session_factory=session_factory,
        graph_invoker=_make_invoker(_full_outputs()),
        settings=fake_settings,
    )
    record = svc.evaluate(seeded_syllabus)
    assert "C1" in record.retrieved_chunks
    assert "C3" in record.retrieved_chunks
    assert record.retrieved_chunks["C1"][0]["chunk_id"] == "lg_unict__2__0"
    assert record.retrieved_chunks["C3"][0]["section_ref"] == "3.1"


def test_evaluate_partial_status_persists_agent_errors(
    session_factory, seeded_syllabus, fake_settings
):
    outputs = _full_outputs()
    outputs["A2"] = None
    errors = {"A2": "LLMSafetyBlockedError: SAFETY"}
    svc = EvaluationService(
        session_factory=session_factory,
        graph_invoker=_make_invoker(outputs, errors),
        settings=fake_settings,
    )
    record = svc.evaluate(seeded_syllabus)
    assert record.status == "partial"
    assert record.agent_errors == {"A2": "LLMSafetyBlockedError: SAFETY"}
    # C3 + C4 NA tecnico
    assert record.criterion_scores["C3"] is None
    assert record.criterion_scores["C4"] is None
    # NA records carry the agent_error source
    sources = {r["source"] for r in record.na_criteria}
    assert "agent_error" in sources


def test_evaluate_graph_exception_marks_record_failed(
    session_factory, seeded_syllabus, fake_settings
):
    svc = EvaluationService(
        session_factory=session_factory,
        graph_invoker=_make_invoker(
            _full_outputs(), raise_exc=RuntimeError("graph blew up")
        ),
        settings=fake_settings,
    )
    record = svc.evaluate(seeded_syllabus)
    assert record.status == "failed"
    assert "RuntimeError" in record.error_message
    assert "graph blew up" in record.error_message
    assert record.duration_ms is not None  # still recorded


def test_evaluate_unknown_seuid_raises(session_factory, fake_settings):
    svc = EvaluationService(
        session_factory=session_factory,
        graph_invoker=_make_invoker(_full_outputs()),
        settings=fake_settings,
    )
    with pytest.raises(SyllabusNotFoundError):
        svc.evaluate("DOES-NOT-EXIST")


def test_get_evaluation_returns_persisted_row(
    session_factory, seeded_syllabus, fake_settings
):
    svc = EvaluationService(
        session_factory=session_factory,
        graph_invoker=_make_invoker(_full_outputs()),
        settings=fake_settings,
    )
    written = svc.evaluate(seeded_syllabus)
    fetched = svc.get_evaluation(written.evaluation_uuid)
    assert fetched.evaluation_uuid == written.evaluation_uuid
    assert fetched.core_score == written.core_score


def test_get_evaluation_unknown_uuid_raises(session_factory, fake_settings):
    svc = EvaluationService(
        session_factory=session_factory,
        graph_invoker=_make_invoker(_full_outputs()),
        settings=fake_settings,
    )
    with pytest.raises(LookupError):
        svc.get_evaluation("nonexistent-uuid")


def test_list_evaluations_for_syllabus_orders_most_recent_first(
    session_factory, seeded_syllabus, fake_settings
):
    svc = EvaluationService(
        session_factory=session_factory,
        graph_invoker=_make_invoker(_full_outputs()),
        settings=fake_settings,
    )
    first = svc.evaluate(seeded_syllabus)
    second = svc.evaluate(seeded_syllabus)
    third = svc.evaluate(seeded_syllabus)

    rows = svc.list_evaluations_for_syllabus(seeded_syllabus)
    assert [r.evaluation_uuid for r in rows] == [
        third.evaluation_uuid,
        second.evaluation_uuid,
        first.evaluation_uuid,
    ]


def test_list_evaluations_for_syllabus_respects_limit(
    session_factory, seeded_syllabus, fake_settings
):
    svc = EvaluationService(
        session_factory=session_factory,
        graph_invoker=_make_invoker(_full_outputs()),
        settings=fake_settings,
    )
    for _ in range(5):
        svc.evaluate(seeded_syllabus)
    rows = svc.list_evaluations_for_syllabus(seeded_syllabus, limit=2)
    assert len(rows) == 2


def test_list_evaluations_for_unknown_seuid_raises(session_factory, fake_settings):
    svc = EvaluationService(
        session_factory=session_factory,
        graph_invoker=_make_invoker(_full_outputs()),
        settings=fake_settings,
    )
    with pytest.raises(SyllabusNotFoundError):
        svc.list_evaluations_for_syllabus("MISSING")


def test_default_prompt_versions_track_current_agent_releases():
    """The dict baked into every persisted record is the policy under test.

    A bump on any agent (e.g. a1_v5 in 5.4.J) must be reflected here so
    that ``EvaluationResult.prompt_versions`` records the version that
    actually produced the run. D026 / D043.
    """
    assert DEFAULT_PROMPT_VERSIONS == {
        "A1": "a1_v5",
        "A2": "a2_v1",
        "A3": "a3_v1",
        "A4": "a4_v2",
    }
