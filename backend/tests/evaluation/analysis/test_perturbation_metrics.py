from app.evaluation.analysis.perturbation import (
    classify_verdict,
    compute_perturbation_metrics,
    compute_side_effects,
    perturbation_by_id,
)
from app.evaluation.analysis.self_consistency import RunRecord


def test_pass_robust_when_drop_exceeds_base_noise():
    # base stable at 2, variant at 1 -> delta -1, base_range 0
    v = classify_verdict("C1", [2, 2, 2], [1, 1, 1])
    assert v.delta == -1.0
    assert v.noise_floor == 0.0
    assert v.verdict == "PASS"
    assert v.passed is True


def test_weak_when_drop_within_base_noise():
    # base wobbles 1..2 (range 1); variant mean drops by ~0.67 < range
    v = classify_verdict("C7", [2, 1, 2], [1, 1, 1])
    assert v.verdict == "WEAK"
    assert v.passed is False


def test_fail_when_direction_wrong():
    v = classify_verdict("C6", [1, 1, 1], [2, 2, 2])
    assert v.verdict == "FAIL"
    assert v.passed is False


def test_fail_when_delta_below_half_point():
    v = classify_verdict("C9", [2, 2, 2], [2, 2, 1])  # delta -0.33
    assert v.verdict == "FAIL"


def test_target_became_na():
    v = classify_verdict("C2", [2, 2, 2], [None, None, 1])
    assert v.verdict == "TARGET_BECAME_NA"
    assert v.delta is None


def test_insufficient_base_data():
    v = classify_verdict("C5", [None, None, 1], [0, 0, 0])
    assert v.verdict == "insufficient_base_data"
    assert v.passed is False


def _matrix(**cols):
    # cols: criterion -> list of 3 scores; missing criteria default to [2,2,2]
    base = {c: [2, 2, 2] for c in
            ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9")}
    base.update(cols)
    return base


def test_side_effects_flag_and_classify():
    base = _matrix()
    pert = _matrix(C1=[0, 0, 0], C7=[1, 1, 1], C2=[1, 1, 1])
    effects, all_deltas = compute_side_effects(
        base, pert, target_criteria=("C1",), coupling=("C7", "C8", "C9"),
    )
    by_crit = {e.criterion: e for e in effects}
    assert "C1" not in by_crit               # target, not a side effect
    assert by_crit["C7"].classification == "expected_coupling"
    assert by_crit["C2"].classification == "spurious"
    assert all_deltas["C1"] == -2.0


def _records(scores_per_run, seuid="BASE"):
    return [
        RunRecord(seuid=seuid, run_index=i + 1, status="completed",
                  criterion_scores=s, core_score=None, coverage=1.0)
        for i, s in enumerate(scores_per_run)
    ]


def test_compute_metrics_end_to_end_single_variant():
    full2 = {c: 2 for c in ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9")}
    base_records = _records([full2, full2, full2])
    c6_low = {**full2, "C6": 0}
    variant_records = {"C6_strip_assessment": _records([c6_low, c6_low, c6_low])}

    metrics = compute_perturbation_metrics(
        base_records, variant_records,
        perturbations=(perturbation_by_id("C6_strip_assessment"),),
        base_seuid="DL", n_runs=3,
    )
    assert metrics.base_seuid == "DL"
    vr = metrics.variants[0]
    assert vr.variant_id == "C6_strip_assessment"
    assert vr.primary_target == "C6"
    assert vr.passed is True
    assert vr.target_verdicts[0].delta == -2.0
    assert vr.all_deltas["C6"] == -2.0
