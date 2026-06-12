"""Regression tests for the targeted Phase 9.F runner.

Covers the two helpers that encode the campaign's interpretation
contract (the decision tree) and the synthetic-syllabus drift
guard. The Vertex / Chroma / API path is not exercised here — it's
the same as the baseline runner, which has its own end-to-end
smoke.
"""
from __future__ import annotations

from scripts.calibrate_phase_9_f_targeted import (
    _SYNTHETIC_CONTENT_FIELDS,
    _expected_syllabus_fields,
    _interpret,
)


# ---------------------------------------------------------------------------
# _expected_syllabus_fields
# ---------------------------------------------------------------------------


def test_expected_syllabus_fields_strips_meta_block():
    payload = {
        "_meta": {"synthetic_fixture_version": "v1", "purpose": "..."},
        "seuid": "SYNTHETIC-9F-POSITIVE-E5-V1",
        "course_name": "Sistemi distribuiti avanzati",
        "prerequisites_it": "...",
    }
    out = _expected_syllabus_fields(payload)
    assert "_meta" not in out
    assert out["seuid"] == "SYNTHETIC-9F-POSITIVE-E5-V1"
    assert out["course_name"] == "Sistemi distribuiti avanzati"


def test_expected_syllabus_fields_returns_none_for_missing_keys():
    payload = {"seuid": "X"}
    out = _expected_syllabus_fields(payload)
    # Every declared field is present, possibly None.
    for f in _SYNTHETIC_CONTENT_FIELDS:
        assert f in out
    assert out["course_name"] is None


# ---------------------------------------------------------------------------
# _interpret — decision tree
# ---------------------------------------------------------------------------


def _row(score, role="real"):
    return {"role": role, "e5": {"score": score, "outcome": "score"}}


def test_interpret_well_calibrated_when_synthetic_max_and_real_boundary_one():
    synthetic = _row(2, role="synthetic_positive_control")
    real = [_row(1), _row(1)]
    out = _interpret(synthetic, real)
    assert out["synthetic_e5_score"] == 2
    assert out["real_e5_scores"] == [1, 1]
    assert "well-calibrated" in out["verdict"].lower()


def test_interpret_aggregation_issue_when_all_real_collapse_to_zero():
    synthetic = _row(2, role="synthetic_positive_control")
    real = [_row(0), _row(0)]
    out = _interpret(synthetic, real)
    assert "aggregation" in out["verdict"].lower()
    assert "e5_v2" in out["verdict"]


def test_interpret_partial_aggregation_when_real_boundaries_mixed():
    synthetic = _row(2, role="synthetic_positive_control")
    real = [_row(0), _row(1)]
    out = _interpret(synthetic, real)
    assert "discriminates" in out["verdict"].lower()
    assert "not urgent" in out["verdict"].lower()


def test_interpret_structurally_severe_when_synthetic_below_max():
    synthetic = _row(1, role="synthetic_positive_control")
    real = [_row(0), _row(1)]
    out = _interpret(synthetic, real)
    assert "structurally severe" in out["verdict"].lower()
    assert "e5_v2 is warranted" in out["verdict"]


def test_interpret_synthetic_na_branch_when_score_none():
    synthetic = _row(None, role="synthetic_positive_control")
    real = [_row(1)]
    out = _interpret(synthetic, real)
    assert out["synthetic_e5_score"] is None
    assert "review the" in out["verdict"].lower()


def test_interpret_handles_missing_synthetic_row():
    out = _interpret(None, [_row(1)])
    assert out["synthetic_e5_score"] is None
