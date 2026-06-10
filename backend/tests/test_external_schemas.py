"""Schemas + aggregator tests for the A5 path (Phase 9.C.1).

Covers the dual-source rule (E1/E2/E3/E5 require syllabus+document
evidence on numeric scores; E4 requires IT+EN syllabus evidences),
the NA validators (is_na_technical only with is_na=true; na_reason
mandatory), and the aggregator's three-way status (completed /
partial / failed) plus its four NA provenance branches (resolver,
handler_na, handler_error, missing-judgment).
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.evaluation.agents.external_schemas import (
    ExtendedAgentOutput,
    ExtendedCriterionJudgment,
    ExtendedEvidence,
)
from app.evaluation.extended_aggregator import (
    ExtendedCriteriaResult,
    aggregate_extended,
)


# ---------------------------------------------------------------------------
# ExtendedEvidence
# ---------------------------------------------------------------------------


def test_evidence_requires_at_least_one_source():
    with pytest.raises(ValidationError):
        ExtendedEvidence(text="quote", source_field=None, source_document_id=None)


def test_evidence_accepts_syllabus_source():
    ev = ExtendedEvidence(text="x", source_field="learning_outcomes_it")
    assert ev.source_field == "learning_outcomes_it"


def test_evidence_accepts_document_source():
    ev = ExtendedEvidence(text="x", source_document_id=42, source_chunk_id="c0")
    assert ev.source_document_id == 42


# ---------------------------------------------------------------------------
# ExtendedCriterionJudgment — NA validators
# ---------------------------------------------------------------------------


def _na_judgment(code: str, **extra) -> ExtendedCriterionJudgment:
    return ExtendedCriterionJudgment(
        criterion_code=code,
        score=None,
        is_na=True,
        na_reason="not applicable for this run",
        justification="x" * 40,
        confidence="low",
        **extra,
    )


def test_na_judgment_accepts_no_evidence():
    j = _na_judgment("E1")
    assert j.is_na is True
    assert j.is_na_technical is False


def test_na_judgment_with_technical_flag():
    j = _na_judgment("E1", is_na_technical=True)
    assert j.is_na_technical is True


def test_technical_na_rejected_without_is_na():
    """`is_na_technical=true` is invalid alongside `is_na=false`."""
    with pytest.raises(ValidationError, match="is_na_technical=true requires is_na=true"):
        ExtendedCriterionJudgment(
            criterion_code="E1",
            score=1,
            is_na=False,
            is_na_technical=True,  # contradiction
            justification="x" * 40,
            evidences=[
                ExtendedEvidence(text="a", source_field="learning_outcomes_it"),
                ExtendedEvidence(text="b", source_document_id=1),
            ],
            confidence="medium",
        )


def test_semantic_na_keeps_technical_flag_false_by_default():
    """Default technical flag is false; explicit semantic NA is the
    common case for resolver-driven hard NA (when persisted via
    the coordinator, not the resolver short-circuit)."""
    j = _na_judgment("E1")
    assert j.is_na is True
    assert j.is_na_technical is False


def test_technical_na_paired_with_is_na_true_is_accepted():
    j = ExtendedCriterionJudgment(
        criterion_code="E1",
        score=None,
        is_na=True,
        na_reason="handler crashed after retries",
        is_na_technical=True,
        justification="x" * 40,
        confidence="low",
    )
    assert j.is_na is True
    assert j.is_na_technical is True


def test_score_required_when_not_na():
    with pytest.raises(ValidationError):
        ExtendedCriterionJudgment(
            criterion_code="E1",
            score=None,
            is_na=False,
            justification="x" * 40,
            confidence="medium",
        )


def test_na_reason_required_when_is_na():
    with pytest.raises(ValidationError):
        ExtendedCriterionJudgment(
            criterion_code="E1",
            score=None,
            is_na=True,
            na_reason=None,
            justification="x" * 40,
            confidence="medium",
        )


# ---------------------------------------------------------------------------
# ExtendedCriterionJudgment — dual-source rule (E1/E2/E3/E5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", ["E1", "E2", "E3", "E5"])
def test_registry_served_score_requires_dual_source(code):
    with pytest.raises(ValidationError):
        ExtendedCriterionJudgment(
            criterion_code=code,
            score=2,
            justification="x" * 40,
            evidences=[
                ExtendedEvidence(text="a", source_field="learning_outcomes_it"),
            ],  # missing external document evidence
            confidence="high",
        )


@pytest.mark.parametrize("code", ["E1", "E2", "E3", "E5"])
def test_registry_served_score_accepts_dual_source(code):
    j = ExtendedCriterionJudgment(
        criterion_code=code,
        score=2,
        justification="x" * 40,
        evidences=[
            ExtendedEvidence(text="a", source_field="learning_outcomes_it"),
            ExtendedEvidence(text="b", source_document_id=7, source_chunk_id="c1"),
        ],
        confidence="high",
    )
    assert j.score == 2


def test_registry_score_rejects_only_document_evidence():
    with pytest.raises(ValidationError):
        ExtendedCriterionJudgment(
            criterion_code="E1",
            score=1,
            justification="x" * 40,
            evidences=[
                ExtendedEvidence(text="a", source_document_id=1),
                ExtendedEvidence(text="b", source_document_id=2),
            ],
            confidence="medium",
        )


# ---------------------------------------------------------------------------
# ExtendedCriterionJudgment — dual-source rule (E4 special case)
# ---------------------------------------------------------------------------


def test_e4_score_requires_paired_prefix():
    """E4 numeric score accepts an evidence pair that shares the
    same field prefix on the IT and EN sides."""
    j = ExtendedCriterionJudgment(
        criterion_code="E4",
        score=1,
        justification="x" * 40,
        evidences=[
            ExtendedEvidence(text="i", source_field="learning_outcomes_it"),
            ExtendedEvidence(text="e", source_field="learning_outcomes_en"),
        ],
        confidence="medium",
    )
    assert j.score == 1


def test_e4_score_rejects_unrelated_it_en():
    """Phase 9.C tightening: an `*_it` evidence and an `*_en`
    evidence on UNRELATED fields don't actually demonstrate
    cross-lingua coherence."""
    with pytest.raises(ValidationError, match="paired"):
        ExtendedCriterionJudgment(
            criterion_code="E4",
            score=1,
            justification="x" * 40,
            evidences=[
                ExtendedEvidence(text="a", source_field="learning_outcomes_it"),
                ExtendedEvidence(text="b", source_field="prerequisites_en"),
            ],
            confidence="medium",
        )


def test_e4_score_rejects_only_it_side():
    """No EN-side evidence at all — no paired prefix possible."""
    with pytest.raises(ValidationError, match="paired"):
        ExtendedCriterionJudgment(
            criterion_code="E4",
            score=1,
            justification="x" * 40,
            evidences=[
                ExtendedEvidence(text="a", source_field="learning_outcomes_it"),
                ExtendedEvidence(text="b", source_field="prerequisites_it"),
            ],
            confidence="medium",
        )


def test_e4_score_accepts_pair_amid_other_evidences():
    """A pair anywhere in the evidence list is enough — extra
    unrelated evidences don't disqualify the judgment."""
    j = ExtendedCriterionJudgment(
        criterion_code="E4",
        score=2,
        justification="x" * 40,
        evidences=[
            ExtendedEvidence(text="extra it", source_field="prerequisites_it"),
            ExtendedEvidence(text="i", source_field="learning_outcomes_it"),
            ExtendedEvidence(text="e", source_field="learning_outcomes_en"),
        ],
        confidence="high",
    )
    assert j.score == 2


def test_e4_score_rejects_external_document_evidence():
    """E4 must never cite a registry document — the second source
    is the syllabus's own EN side. A document-side evidence on E4
    fails the paired-prefix rule, because the EN counterpart is
    missing.
    """
    with pytest.raises(ValidationError, match="paired"):
        ExtendedCriterionJudgment(
            criterion_code="E4",
            score=2,
            justification="x" * 40,
            evidences=[
                ExtendedEvidence(text="i", source_field="learning_outcomes_it"),
                ExtendedEvidence(text="d", source_document_id=1),
            ],
            confidence="medium",
        )


def test_na_judgment_skips_dual_source_check():
    """NA judgments don't need evidence — the validator must not
    fire on them even when no evidence is supplied."""
    j = _na_judgment("E1")
    assert j.evidences == []


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


def _ok_judgment(code: str, score: int = 2) -> ExtendedCriterionJudgment:
    if code == "E4":
        return ExtendedCriterionJudgment(
            criterion_code=code,
            score=score,
            justification="x" * 40,
            evidences=[
                ExtendedEvidence(text="i", source_field="learning_outcomes_it"),
                ExtendedEvidence(text="e", source_field="learning_outcomes_en"),
            ],
            confidence="high",
        )
    return ExtendedCriterionJudgment(
        criterion_code=code,
        score=score,
        justification="x" * 40,
        evidences=[
            ExtendedEvidence(text="a", source_field="learning_outcomes_it"),
            ExtendedEvidence(text="b", source_document_id=1),
        ],
        confidence="high",
    )


def test_aggregator_completed_when_no_errors():
    out = ExtendedAgentOutput(
        judgments=[_ok_judgment(c) for c in ("E1", "E2", "E3", "E4", "E5")],
    )
    result = aggregate_extended(out)
    assert isinstance(result, ExtendedCriteriaResult)
    assert result.status == "completed"
    assert result.criterion_scores == {"E1": 2, "E2": 2, "E3": 2, "E4": 2, "E5": 2}
    assert result.na_criteria == []
    assert result.handler_errors == {}


def test_aggregator_resolver_na_short_circuits_judgment():
    """If the resolver said NA, the aggregator records the
    resolver reason regardless of what the agent output may carry."""
    out = ExtendedAgentOutput(
        judgments=[
            _ok_judgment(c) for c in ("E2", "E3", "E5")
        ],  # E1 / E4 missing on purpose
    )
    result = aggregate_extended(
        out,
        resolver_na={
            "E1": "no SUA-CdS document enabled",
            "E4": "syllabus has no English version available",
        },
    )
    assert result.criterion_scores == {
        "E1": None, "E2": 2, "E3": 2, "E4": None, "E5": 2,
    }
    sources = {n.criterion_code: n.source for n in result.na_criteria}
    assert sources["E1"] == "resolver"
    assert sources["E4"] == "resolver"


def test_aggregator_handler_na_is_recorded_as_handler_na():
    out = ExtendedAgentOutput(
        judgments=[
            ExtendedCriterionJudgment(
                criterion_code="E5",
                score=None,
                is_na=True,
                na_reason="document carries no local rules applicable to this syllabus",
                justification="x" * 40,
                confidence="low",
            ),
            _ok_judgment("E1"),
            _ok_judgment("E2"),
            _ok_judgment("E3"),
            _ok_judgment("E4"),
        ],
    )
    result = aggregate_extended(out)
    assert result.criterion_scores["E5"] is None
    e5 = next(n for n in result.na_criteria if n.criterion_code == "E5")
    assert e5.source == "handler_na"
    assert "no local rules" in e5.reason
    # status stays completed: NA is a valid outcome.
    assert result.status == "completed"


def test_aggregator_handler_error_becomes_technical_na_and_partial_status():
    out = ExtendedAgentOutput(
        judgments=[
            _ok_judgment("E1"),
            _ok_judgment("E2"),
            _ok_judgment("E3"),
            _ok_judgment("E4"),
        ],
        handler_errors={"E5": "ValidationError: missing dual-source evidence"},
    )
    result = aggregate_extended(out)
    assert result.criterion_scores["E5"] is None
    e5 = next(n for n in result.na_criteria if n.criterion_code == "E5")
    assert e5.source == "handler_error"
    assert "ValidationError" in e5.reason
    assert result.handler_errors == {"E5": e5.reason}
    assert result.status == "partial"


def test_aggregator_missing_judgment_treated_as_technical_na():
    """A criterion absent from both judgments and handler_errors
    shouldn't happen, but the aggregator still produces a sane
    result."""
    out = ExtendedAgentOutput(judgments=[_ok_judgment("E1")])
    result = aggregate_extended(out)
    for code in ("E2", "E3", "E4", "E5"):
        assert result.criterion_scores[code] is None
    # All four missing -> partial (not failed, because E1 succeeded).
    assert result.status == "partial"


def test_aggregator_failed_when_every_criterion_errored():
    out = ExtendedAgentOutput(
        judgments=[],
        handler_errors={c: "boom" for c in ("E1", "E2", "E3", "E4", "E5")},
    )
    result = aggregate_extended(out)
    assert result.status == "failed"
    assert all(v is None for v in result.criterion_scores.values())


def test_aggregator_when_agent_output_is_none():
    """A5 itself crashed before producing any output."""
    result = aggregate_extended(None)
    assert result.status == "failed"
    assert all(v is None for v in result.criterion_scores.values())
    assert all(n.source == "handler_error" for n in result.na_criteria)


def test_aggregator_all_resolver_na_with_none_output_is_completed():
    """Phase 9.C clarification: when the resolver hard-NAs every
    criterion, A5 is legitimately never invoked. Output is None
    but the status must be `completed` — nothing failed."""
    result = aggregate_extended(
        None,
        resolver_na={
            "E1": "no SUA-CdS",
            "E2": "no matrice tuning",
            "E3": "no regolamento",
            "E4": "no English content",
            "E5": "no local document",
        },
    )
    assert result.status == "completed"
    assert all(v is None for v in result.criterion_scores.values())
    assert all(n.source == "resolver" for n in result.na_criteria)


def test_aggregator_resolver_na_plus_handler_error_can_be_failed():
    """One criterion handler-errored; the other four were resolver-
    NAs. There's no remaining criterion with a non-technical
    outcome, so the status is `failed`."""
    out = ExtendedAgentOutput(
        judgments=[],
        handler_errors={"E5": "boom"},
    )
    result = aggregate_extended(
        out,
        resolver_na={
            "E1": "no SUA-CdS",
            "E2": "no matrice tuning",
            "E3": "no regolamento",
            "E4": "no English content",
        },
    )
    assert result.status == "failed"


def test_aggregator_resolver_na_plus_handler_error_can_be_partial():
    """Same scenario but with one successful handler — the status
    becomes `partial`."""
    out = ExtendedAgentOutput(
        judgments=[_ok_judgment("E5")],
        handler_errors={"E3": "boom"},
    )
    result = aggregate_extended(
        out,
        resolver_na={
            "E1": "no SUA-CdS",
            "E2": "no matrice tuning",
            "E4": "no English content",
        },
    )
    assert result.status == "partial"
