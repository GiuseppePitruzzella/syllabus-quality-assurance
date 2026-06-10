"""Regression tests for the Phase 9.C.5.3 extended-criteria
persistence layer.

These tests exercise the full ``EvaluationService.evaluate`` round
trip with a fake graph invoker that mimics A1..A5 (and the
aggregator) without touching Vertex / Chroma. The focus is on the
core / extended decoupling required by the user contract:

  * the core ``status`` / ``core_score`` / ``coverage`` /
    ``criterion_scores`` / ``na_criteria`` columns NEVER change
    because A5 ran (or failed);
  * the new ``extended_criteria_result`` JSON column carries the
    full E* outcome, including ``status``, ``criterion_scores``,
    ``na_criteria``, ``handler_errors`` and a dump of the raw
    ``ExtendedAgentOutput`` (handler prompt versions included);
  * legacy runs (no resolver supplied) leave the column ``None``;
  * a complete A5 failure produces ``extended_criteria_result
    .status == "failed"`` but the run's ``status`` remains
    ``completed``.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base
from app.evaluation.agents.external_schemas import (
    ExtendedAgentOutput,
    ExtendedCriterionJudgment,
)
from app.evaluation.agents.schemas import (
    AgentOutput,
    CriterionEvidence,
    CriterionJudgment,
)
from app.evaluation.aggregator import aggregate
from app.evaluation.extended_aggregator import aggregate_extended
from app.evaluation.service import EvaluationService
from app.evaluation.synthesizer import synthesize_report
from app.local_documents.resolver import (
    CriterionResolution,
    ResolvedDocument,
    ResolverOutput,
)
from app.models import (
    CorsoDiLaurea,
    Department,
    Syllabus,
)
from app.models.local_document import LocalDocument


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session_factory():
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
def fake_settings():
    return Settings(gcp_project_id="test-project", gcp_location="europe-west1")


def _seed_syllabus(session_factory, *, has_english: bool = True) -> str:
    now = datetime(2026, 5, 17, tzinfo=timezone.utc)
    with session_factory() as session:
        dept = Department(
            id=1, name="DMI", area="Scientifica", website_url="https://x",
            email="dmi@example", phone="000", director="X", scraped_at=now,
        )
        cdl = CorsoDiLaurea(
            id=1, department_id=1, name="LM-18", code="LM-18",
            type="laurea_magistrale", academic_year="2025/2026",
            url="https://x", scraped_at=now,
        )
        syl = Syllabus(
            cdl_id=1, seuid="SEUID-X", course_code="9999",
            course_name="Deep Learning", teacher="M. Rossi",
            academic_year="2025/2026", year_of_study="2",
            url_it="https://x/it", url_en="https://x/en",
            has_english=has_english, scraped_at=now,
            learning_outcomes_it="RA",
            dublin_knowledge_it="K", dublin_applying_it="A",
            dublin_judgement_it="J", dublin_communication_it="C",
            dublin_learning_it="L", teaching_methods_it="L",
            prerequisites_it="P", attendance_it="A",
            course_content_it="C", references_it="R",
            assessment_methods_it="V", sample_questions_it="E",
        )
        session.add_all([dept, cdl, syl])
        session.commit()
        return syl.seuid


def _seed_local_document(session_factory, **overrides) -> int:
    now = datetime(2026, 5, 17, tzinfo=timezone.utc)
    base = {
        "cdl_id": 1,
        "document_type": "sua_cds",
        "title": "SUA",
        "normalized_title": "sua",
        "version": 1,
        "file_hash": "hash",
        "file_path": "/x.md",
        "file_extension": "md",
        "file_size": 1024,
        "academic_year": "2025-2026",
        "enabled_criteria": ["E1"],
        "status": "indexed",
        "uploaded_at": now,
        "indexed_at": now,
    }
    base.update(overrides)
    with session_factory() as session:
        doc = LocalDocument(**base)
        session.add(doc)
        session.commit()
        return doc.id


# ---------------------------------------------------------------------------
# Helpers — canned core outputs and extended outputs
# ---------------------------------------------------------------------------


def _judgment(code: str, *, score: int = 2):
    return CriterionJudgment(
        criterion_code=code,
        score=score,
        is_na=False,
        justification=(
            f"Giudizio per {code} sufficientemente articolato per il validator."
        ),
        evidences=[
            CriterionEvidence(text=f"q-{code}", source_field="course_content_it"),
        ],
        confidence="medium",
    )


def _core_outputs(score: int = 2) -> dict[str, AgentOutput]:
    return {
        "A1": AgentOutput(
            agent_code="A1",
            judgments=[
                _judgment("C1", score=score),
                _judgment("C2", score=score),
                _judgment("C5", score=score),
            ],
            execution_metadata={"retry_count": 0},
        ),
        "A2": AgentOutput(
            agent_code="A2",
            judgments=[_judgment("C3", score=score), _judgment("C4", score=score)],
            execution_metadata={"retry_count": 0},
        ),
        "A3": AgentOutput(
            agent_code="A3",
            judgments=[
                _judgment("C6", score=score),
                _judgment("C7", score=score),
                _judgment("C8", score=score),
            ],
            execution_metadata={"retry_count": 0},
        ),
        "A4": AgentOutput(
            agent_code="A4",
            judgments=[_judgment("C9", score=score)],
            execution_metadata={"retry_count": 0},
        ),
    }


def _ext_output_success() -> ExtendedAgentOutput:
    js = []
    for code, score in (("E1", 2), ("E2", 1), ("E3", 2), ("E4", 2), ("E5", 1)):
        if code == "E4":
            evidences = [
                {"text": "RA", "source_field": "learning_outcomes_it"},
                {"text": "LO", "source_field": "learning_outcomes_en"},
            ]
        else:
            evidences = [
                {"text": "syllabus q", "source_field": "learning_outcomes_it"},
                {"text": "external q", "source_document_id": 42},
            ]
        js.append(
            ExtendedCriterionJudgment(
                criterion_code=code,
                score=score,
                is_na=False,
                is_na_technical=False,
                justification=(
                    f"{code} è allineato in modo sostanziale alle evidenze raccolte."
                ),
                evidences=evidences,
                confidence="high",
            ),
        )
    return ExtendedAgentOutput(
        agent_code="A5",
        judgments=js,
        handler_prompt_versions={
            "E1": "e1_v1", "E2": "e2_v1", "E3": "e3_v1",
            "E4": "e4_v1", "E5": "e5_v1",
        },
        handler_errors={},
        execution_metadata={"handlers_invoked": ["E1", "E2", "E3", "E4", "E5"]},
    )


def _resolved(code: str, doc_id: int) -> ResolvedDocument:
    return ResolvedDocument(
        criterion_code=code,
        local_document_id=doc_id,
        document_version_snapshot=1,
        file_hash_snapshot="h",
        document_type_snapshot="sua_cds",
        resolution_reason="academic_year_match",
    )


def _resolver_e1_only(doc_id: int) -> ResolverOutput:
    return ResolverOutput(
        by_criterion={
            "E1": CriterionResolution(
                criterion_code="E1", applicable=True,
                documents=[_resolved("E1", doc_id)],
            ),
            "E2": CriterionResolution(criterion_code="E2", applicable=False,
                                       na_reason="no matrice"),
            "E3": CriterionResolution(criterion_code="E3", applicable=False,
                                       na_reason="no regolamento"),
            "E4": CriterionResolution(criterion_code="E4", applicable=True,
                                       documents=[]),
            "E5": CriterionResolution(criterion_code="E5", applicable=False,
                                       na_reason="no local doc"),
        },
    )


def _resolver_all_applicable() -> ResolverOutput:
    return ResolverOutput(
        by_criterion={
            "E1": CriterionResolution(
                criterion_code="E1", applicable=True,
                documents=[_resolved("E1", 42)],
            ),
            "E2": CriterionResolution(
                criterion_code="E2", applicable=True,
                documents=[_resolved("E2", 51)],
            ),
            "E3": CriterionResolution(
                criterion_code="E3", applicable=True,
                documents=[_resolved("E3", 77)],
            ),
            "E4": CriterionResolution(
                criterion_code="E4", applicable=True, documents=[],
            ),
            "E5": CriterionResolution(
                criterion_code="E5", applicable=True,
                documents=[_resolved("E5", 11)],
            ),
        },
    )


# ---------------------------------------------------------------------------
# Graph invokers
# ---------------------------------------------------------------------------


def _make_invoker_full_success(
    *,
    extended_output: ExtendedAgentOutput | None,
    resolver_override: ResolverOutput | None = None,
):
    """Mimic prepare_context → A1..A4 → a5 → aggregate → synthesize → finalize.

    Uses the real aggregate / aggregate_extended / synthesize helpers so
    we're testing the persistence path end-to-end against deterministic
    inputs. ``resolver_override`` lets a test pin a specific resolver
    shape regardless of what the service-side resolver derived from
    the seeded DB.
    """
    core = _core_outputs(score=2)

    def _invoker(initial_state, progress_publisher=None):
        agent_outputs = dict(core)
        aggregation = aggregate(agent_outputs, {})
        resolver_output = resolver_override or initial_state.get("resolver_output")
        extended_result = None
        if resolver_output is not None:
            from app.evaluation.agents.external_consistency_agent import (
                resolver_na_map,
            )
            extended_result = aggregate_extended(
                extended_output, resolver_na=resolver_na_map(resolver_output),
            )
        report = synthesize_report(
            initial_state.get("course_name", "Test"),
            aggregation,
            agent_outputs,
        )
        return {
            **initial_state,
            "agent_outputs": agent_outputs,
            "agent_errors": {},
            "aggregation": aggregation,
            "status": aggregation.status,
            "extended_agent_output": extended_output,
            "extended_result": extended_result,
            "final_report": report,
            "finished_at": datetime.now(timezone.utc),
        }

    return _invoker


# ---------------------------------------------------------------------------
# Happy path — A5 fully successful
# ---------------------------------------------------------------------------


def test_evaluate_persists_extended_criteria_result_on_full_success(
    session_factory, fake_settings,
):
    seuid = _seed_syllabus(session_factory)
    _seed_local_document(session_factory)  # SUA-CdS for E1

    svc = EvaluationService(
        session_factory=session_factory,
        graph_invoker=_make_invoker_full_success(
            extended_output=_ext_output_success(),
            resolver_override=_resolver_all_applicable(),
        ),
        settings=fake_settings,
    )
    record = svc.evaluate(seuid)

    # Core columns untouched by A5.
    assert record.status == "completed"
    assert record.core_score == 2.0
    assert record.coverage == 1.0
    # Extended column populated.
    ext = record.extended_criteria_result
    assert ext is not None
    assert ext["status"] == "completed"
    assert ext["criterion_scores"]["E1"] == 2
    assert ext["criterion_scores"]["E5"] == 1
    assert ext["handler_errors"] == {}
    # Per-E* prompt versions captured under agent_output.
    assert ext["agent_output"]["handler_prompt_versions"] == {
        "E1": "e1_v1", "E2": "e2_v1", "E3": "e3_v1",
        "E4": "e4_v1", "E5": "e5_v1",
    }
    # No resolver-NA entries when every criterion is applicable.
    assert ext["na_criteria"] == []


# ---------------------------------------------------------------------------
# Core decoupling — A5 failure does NOT demote core completed
# ---------------------------------------------------------------------------


def test_a5_complete_failure_keeps_core_status_completed(
    session_factory, fake_settings,
):
    """A5 returns no output AND the resolver said some criteria were
    applicable → extended_result.status == 'failed'. But core.status
    must stay 'completed'."""
    seuid = _seed_syllabus(session_factory)
    _seed_local_document(session_factory)  # SUA-CdS for E1
    svc = EvaluationService(
        session_factory=session_factory,
        graph_invoker=_make_invoker_full_success(extended_output=None),
        settings=fake_settings,
    )
    record = svc.evaluate(seuid)
    assert record.status == "completed"
    assert record.core_score == 2.0
    assert record.extended_criteria_result["status"] == "failed"


# ---------------------------------------------------------------------------
# Legacy path — no resolver in initial state
# ---------------------------------------------------------------------------


def test_legacy_invoker_without_resolver_leaves_extended_column_null(
    session_factory, fake_settings,
):
    """A graph invoker that returns no resolver_output / no extended
    fields (e.g. a legacy unit-test scaffold or a future fresh-DB
    branch) must persist ``extended_criteria_result == None`` rather
    than crash. Core columns are still populated normally."""
    seuid = _seed_syllabus(session_factory)
    core = _core_outputs(score=2)

    def _legacy_invoker(initial_state, progress_publisher=None):
        agg = aggregate(core, {})
        report = synthesize_report("Test", agg, core)
        # Note: deliberately NO extended_* keys, even though
        # initial_state carries resolver_output (the legacy invoker
        # simply doesn't propagate it).
        return {
            **initial_state,
            "agent_outputs": core,
            "agent_errors": {},
            "aggregation": agg,
            "status": agg.status,
            "final_report": report,
            "finished_at": datetime.now(timezone.utc),
        }

    svc = EvaluationService(
        session_factory=session_factory,
        graph_invoker=_legacy_invoker,
        settings=fake_settings,
    )
    record = svc.evaluate(seuid)
    assert record.status == "completed"
    assert record.extended_criteria_result is None


# ---------------------------------------------------------------------------
# Fresh DB without external collection
# ---------------------------------------------------------------------------


def test_no_local_documents_and_no_english_yields_all_resolver_na(
    session_factory, fake_settings,
):
    """No registry entries + has_english=False → resolver hard-NA on
    every E1..E5. The aggregator collapses that to a completed
    extended status (per Phase 9.C.1.fix), and the core run is
    untouched."""
    seuid = _seed_syllabus(session_factory, has_english=False)
    svc = EvaluationService(
        session_factory=session_factory,
        graph_invoker=_make_invoker_full_success(
            # The "A5 ran but produced no judgments" case is the canonical
            # signal of "everything was resolver-NA, coordinator
            # short-circuited or produced an empty output".
            extended_output=ExtendedAgentOutput(
                agent_code="A5",
                judgments=[],
                handler_prompt_versions={},
                handler_errors={},
                execution_metadata={},
            ),
        ),
        settings=fake_settings,
    )
    record = svc.evaluate(seuid)
    assert record.status == "completed"
    ext = record.extended_criteria_result
    # All five criteria are resolver-NA → completed extended status.
    assert ext["status"] == "completed"
    assert all(s is None for s in ext["criterion_scores"].values())
    assert {r["source"] for r in ext["na_criteria"]} == {"resolver"}


# ---------------------------------------------------------------------------
# Same A1-A4 output pre/post wiring → identical CoreScore + coverage
# ---------------------------------------------------------------------------


def test_core_score_and_coverage_unchanged_with_a5_active(
    session_factory, fake_settings,
):
    """Regression: persisting extended fields must not perturb the
    core CoreScore / coverage / criterion_scores / na_criteria
    columns. We compare a run with A5 active against a manual
    aggregate of the same A1-A4 outputs."""
    seuid = _seed_syllabus(session_factory)
    _seed_local_document(session_factory)

    expected = aggregate(_core_outputs(score=2), {})
    svc = EvaluationService(
        session_factory=session_factory,
        graph_invoker=_make_invoker_full_success(
            extended_output=_ext_output_success(),
        ),
        settings=fake_settings,
    )
    record = svc.evaluate(seuid)
    assert record.core_score == expected.core_score
    assert record.coverage == expected.coverage
    assert record.criterion_scores == expected.criterion_scores
    # na_criteria column matches the core aggregator's exactly.
    assert (record.na_criteria or []) == [r.model_dump() for r in expected.na_criteria]
