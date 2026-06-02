"""Tests for the deterministic aggregator (no LangGraph, no Vertex AI)."""
from __future__ import annotations

import pytest

from app.evaluation.agents.schemas import (
    AgentOutput,
    CriterionEvidence,
    CriterionJudgment,
)
from app.evaluation.aggregator import (
    AGENT_CRITERIA,
    ALL_CORE_CRITERIA,
    aggregate,
)


def _judgment(
    code: str,
    *,
    score: int | None = None,
    is_na: bool = False,
    na_reason: str | None = None,
) -> CriterionJudgment:
    """Build a valid CriterionJudgment with a fixed evidence."""
    return CriterionJudgment(
        criterion_code=code,
        score=score,
        is_na=is_na,
        na_reason=na_reason,
        justification=(
            f"Giudizio sintetico per il criterio {code} a fini di test, "
            "lunghezza sufficiente per superare il min_length del modello."
        ),
        evidences=[
            CriterionEvidence(
                text=f"evidenza-{code}", source_field="course_content_it"
            )
        ],
        confidence="medium",
    )


def _output(agent_code: str, *judgments: CriterionJudgment) -> AgentOutput:
    return AgentOutput(
        agent_code=agent_code,
        judgments=list(judgments),
        execution_metadata={"retry_count": 0},
    )


def _all_agents_ok_outputs() -> dict[str, AgentOutput]:
    """Helper: 4 agents, every criterion scored 2."""
    return {
        "A1": _output(
            "A1",
            _judgment("C1", score=2),
            _judgment("C2", score=2),
            _judgment("C5", score=2),
        ),
        "A2": _output(
            "A2",
            _judgment("C3", score=2),
            _judgment("C4", score=2),
        ),
        "A3": _output(
            "A3",
            _judgment("C6", score=2),
            _judgment("C7", score=2),
            _judgment("C8", score=2),
        ),
        "A4": _output("A4", _judgment("C9", score=2)),
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_aggregate_all_twos_yields_core_score_2_and_completed():
    result = aggregate(_all_agents_ok_outputs(), {})
    assert result.status == "completed"
    assert result.coverage == 1.0
    assert result.core_score == 2.0
    assert result.na_criteria == []
    assert all(s == 2 for s in result.criterion_scores.values())
    assert set(result.criterion_scores.keys()) == set(ALL_CORE_CRITERIA)


def test_aggregate_mixed_scores_yields_mean_core_score():
    outputs = {
        "A1": _output(
            "A1",
            _judgment("C1", score=2),
            _judgment("C2", score=0),
            _judgment("C5", score=1),
        ),
        "A2": _output(
            "A2",
            _judgment("C3", score=2),
            _judgment("C4", score=1),
        ),
        "A3": _output(
            "A3",
            _judgment("C6", score=2),
            _judgment("C7", score=1),
            _judgment("C8", score=2),
        ),
        "A4": _output("A4", _judgment("C9", score=1)),
    }
    result = aggregate(outputs, {})
    # scores = [2,0,1,2,1,2,1,2,1] -> sum=12, mean=1.333...
    assert result.core_score == 1.33
    assert result.coverage == 1.0
    assert result.status == "completed"
    assert result.criterion_scores["C2"] == 0
    assert result.criterion_scores["C5"] == 1


# ---------------------------------------------------------------------------
# NA esplicito dell'agente
# ---------------------------------------------------------------------------


def test_aggregate_agent_explicit_na_excluded_from_core_score():
    outputs = _all_agents_ok_outputs()
    # Replace C2 with an explicit NA from A1.
    outputs["A1"] = _output(
        "A1",
        _judgment("C1", score=2),
        _judgment(
            "C2",
            score=None,
            is_na=True,
            na_reason="campo learning_outcomes_en non recuperabile dal parser",
        ),
        _judgment("C5", score=2),
    )
    result = aggregate(outputs, {})
    assert result.status == "completed"  # all agents ran -> still completed
    assert result.criterion_scores["C2"] is None
    assert result.coverage == 8 / 9
    # Core score is mean of 8 twos = 2.0
    assert result.core_score == 2.0
    # NA record is present with source="agent"
    assert len(result.na_criteria) == 1
    record = result.na_criteria[0]
    assert record.criterion_code == "C2"
    assert record.source == "agent"
    assert "non recuperabile" in record.reason


# ---------------------------------------------------------------------------
# Agent error (partial)
# ---------------------------------------------------------------------------


def test_aggregate_agent_error_marks_owned_criteria_na_technical():
    outputs = _all_agents_ok_outputs()
    outputs["A2"] = None  # A2 failed
    agent_errors = {"A2": "LLMSafetyBlockedError: SAFETY"}

    result = aggregate(outputs, agent_errors)
    assert result.status == "partial"
    assert result.agent_statuses["A1"] == "ok"
    assert result.agent_statuses["A2"] == "error"
    # C3 and C4 are owned by A2 — both must be NA tecnico.
    assert result.criterion_scores["C3"] is None
    assert result.criterion_scores["C4"] is None
    na_codes = {r.criterion_code: r for r in result.na_criteria}
    assert na_codes["C3"].source == "agent_error"
    assert na_codes["C4"].source == "agent_error"
    assert "A2" in na_codes["C3"].reason
    assert "SAFETY" in na_codes["C3"].reason


def test_aggregate_partial_status_when_at_least_one_agent_runs():
    outputs = {
        "A1": _all_agents_ok_outputs()["A1"],
        # A2, A3, A4 missing
    }
    errors = {
        "A2": "ValueError: parse failure",
        "A3": "ValueError: parse failure",
        "A4": "ValueError: parse failure",
    }
    result = aggregate(outputs, errors)
    assert result.status == "partial"
    assert result.agent_statuses["A1"] == "ok"
    # Six criteria in NA tecnico (C3, C4, C6, C7, C8, C9).
    assert sum(1 for s in result.criterion_scores.values() if s is None) == 6


# ---------------------------------------------------------------------------
# Tutti gli agenti falliscono (failed)
# ---------------------------------------------------------------------------


def test_aggregate_all_agents_fail_yields_failed_status():
    errors = {
        "A1": "RuntimeError: a",
        "A2": "RuntimeError: b",
        "A3": "RuntimeError: c",
        "A4": "RuntimeError: d",
    }
    result = aggregate({}, errors)
    assert result.status == "failed"
    assert result.coverage == 0.0
    assert result.core_score is None
    assert all(s is None for s in result.criterion_scores.values())
    assert len(result.na_criteria) == 9
    assert {r.source for r in result.na_criteria} == {"agent_error"}


# ---------------------------------------------------------------------------
# Defensive: missing criteria
# ---------------------------------------------------------------------------


def test_aggregate_missing_criterion_marked_technical_na():
    """If an agent runs successfully but does not report on one of its
    owned criteria (defensive coding), the missing criterion ends up
    as NA tecnico with source='technical'."""
    outputs = _all_agents_ok_outputs()
    outputs["A1"] = _output(
        "A1",
        _judgment("C1", score=2),
        # C2 missing on purpose
        _judgment("C5", score=2),
    )
    result = aggregate(outputs, {})
    # Status is still "completed" because every AGENT ran.
    assert result.status == "completed"
    assert result.criterion_scores["C2"] is None
    na_records = {r.criterion_code: r for r in result.na_criteria}
    assert na_records["C2"].source == "technical"


# ---------------------------------------------------------------------------
# Sanity on the AGENT_CRITERIA constant
# ---------------------------------------------------------------------------


def test_agent_criteria_covers_c1_to_c9_exactly_once():
    flat = [code for codes in AGENT_CRITERIA.values() for code in codes]
    assert sorted(flat) == sorted(ALL_CORE_CRITERIA)
    assert len(flat) == 9
    assert len(set(flat)) == 9


@pytest.mark.parametrize("agent_code", ["A1", "A2", "A3", "A4"])
def test_each_agent_has_at_least_one_criterion(agent_code):
    assert len(AGENT_CRITERIA[agent_code]) >= 1
