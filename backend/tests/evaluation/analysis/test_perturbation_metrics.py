from app.evaluation.analysis.perturbation import classify_verdict


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
