"""Regression tests for the e4_v2 follow-up runner.

Covers the outcome-classification and per-case verdict logic so
the campaign's pass/fail semantics is verified offline. The
Vertex / Chroma / HTTP path is exercised by the runner itself
end-to-end and shares the baseline runner's plumbing, which has
its own tests.
"""
from __future__ import annotations

from scripts.calibrate_phase_9_f_e4_v2_followup import (
    EXPECTED_E4_PROMPT_VERSION,
    FOLLOWUP_SAMPLE,
    Expectation,
    _classify_e4_outcome,
    _verdict_text,
)


# ---------------------------------------------------------------------------
# Sample shape
# ---------------------------------------------------------------------------


def test_sample_has_five_entries_and_one_synthetic():
    assert len(FOLLOWUP_SAMPLE) == 5
    synth = [e for e in FOLLOWUP_SAMPLE if e.role == "synthetic_positive_control"]
    assert len(synth) == 1
    real = [e for e in FOLLOWUP_SAMPLE if e.role == "real"]
    assert len(real) == 4


def test_sample_expected_e4_targets():
    by_label = {e.course_label: e for e in FOLLOWUP_SAMPLE}
    assert by_label["Advanced Computer Graphics"].expected_e4 == "score:1"
    assert by_label["Deep Learning"].expected_e4 == "score:2"
    assert by_label["Internet of Things"].expected_e4 == "NA-handler_na"
    assert by_label["Machine Learning"].expected_e4 == "score:0"
    assert by_label["Sistemi distribuiti avanzati (ctrl)"].expected_e4 == "score:2"


def test_expected_e4_prompt_version_is_v2():
    assert EXPECTED_E4_PROMPT_VERSION == "e4_v2"


# ---------------------------------------------------------------------------
# _classify_e4_outcome
# ---------------------------------------------------------------------------


def _ext(judgment=None, na_criteria=()):
    return {"judgments": [judgment] if judgment else [], "na_criteria": list(na_criteria)}


def test_classify_numeric_score():
    j = {"criterion_code": "E4", "score": 2, "is_na": False}
    assert _classify_e4_outcome(_ext(judgment=j), j) == "score:2"
    j["score"] = 1
    assert _classify_e4_outcome(_ext(judgment=j), j) == "score:1"
    j["score"] = 0
    assert _classify_e4_outcome(_ext(judgment=j), j) == "score:0"


def test_classify_na_resolver_via_na_criteria():
    ext = _ext(na_criteria=[{"criterion_code": "E4", "source": "resolver", "reason": "x"}])
    assert _classify_e4_outcome(ext, None) == "NA-resolver"


def test_classify_na_handler_na_via_na_criteria():
    ext = _ext(na_criteria=[{"criterion_code": "E4", "source": "handler_na", "reason": "x"}])
    assert _classify_e4_outcome(ext, None) == "NA-handler_na"


def test_classify_na_handler_error_via_na_criteria():
    ext = _ext(na_criteria=[{"criterion_code": "E4", "source": "handler_error", "reason": "x"}])
    assert _classify_e4_outcome(ext, None) == "NA-handler_error"


def test_classify_falls_back_to_judgment_flags_when_na_criteria_absent():
    """Defensive: if for some reason the na_criteria entry was
    not added but the judgment carries is_na/is_na_technical, the
    classification still resolves correctly."""
    j_sem = {
        "criterion_code": "E4", "score": None,
        "is_na": True, "is_na_technical": False,
    }
    j_tec = {
        "criterion_code": "E4", "score": None,
        "is_na": True, "is_na_technical": True,
    }
    assert _classify_e4_outcome(_ext(judgment=j_sem), j_sem) == "NA-handler_na"
    assert _classify_e4_outcome(_ext(judgment=j_tec), j_tec) == "NA-handler_error"


# ---------------------------------------------------------------------------
# _verdict_text
# ---------------------------------------------------------------------------


def _expectation(*, accepted: frozenset[str], expected: str = "score:1") -> Expectation:
    return Expectation(
        seuid="X",
        course_label="X",
        role="real",
        expected_e4=expected,
        accepted_e4=accepted,
        note="",
    )


def test_verdict_ok_when_observed_in_accepted_set():
    exp = _expectation(accepted=frozenset({"score:0", "score:1"}))
    assert _verdict_text(exp, "score:1").startswith("OK")


def test_verdict_fail_when_observed_outside_accepted_set():
    exp = _expectation(accepted=frozenset({"score:0", "score:1"}))
    verdict = _verdict_text(exp, "score:2")
    assert verdict.startswith("FAIL")
    assert "score:2" in verdict
    assert "score:1" in verdict  # the expected reference is surfaced


def test_acg_acceptance_set_rejects_score_2():
    """Regression guard for the campaign's central failure mode:
    ACG accepting score 0 or 1, but never 2."""
    acg = next(
        e for e in FOLLOWUP_SAMPLE
        if e.course_label == "Advanced Computer Graphics"
    )
    assert "score:2" not in acg.accepted_e4
    assert "score:0" in acg.accepted_e4
    assert "score:1" in acg.accepted_e4


def test_ml_regression_guard_accepts_only_zero():
    ml = next(
        e for e in FOLLOWUP_SAMPLE if e.course_label == "Machine Learning"
    )
    assert ml.accepted_e4 == frozenset({"score:0"})


def test_iot_accepts_resolver_or_handler_na_but_not_handler_error():
    iot = next(
        e for e in FOLLOWUP_SAMPLE
        if e.course_label == "Internet of Things"
    )
    assert "NA-resolver" in iot.accepted_e4
    assert "NA-handler_na" in iot.accepted_e4
    assert "NA-handler_error" not in iot.accepted_e4


def test_deep_learning_and_synthetic_require_exact_score_2():
    for label in ("Deep Learning", "Sistemi distribuiti avanzati (ctrl)"):
        e = next(x for x in FOLLOWUP_SAMPLE if x.course_label == label)
        assert e.accepted_e4 == frozenset({"score:2"})
