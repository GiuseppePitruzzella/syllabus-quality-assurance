from app.evaluation.analysis.self_consistency import (
    CRITERIA_ORDER,
    item_criterion_stat,
)


def test_unanimous_numeric_scores():
    stat = item_criterion_stat("S1", "C1", [2, 2, 2, 2, 2])
    assert stat.n == 5
    assert stat.n_na == 0
    assert stat.modal_score == 2
    assert stat.modal_agreement == 1.0
    assert stat.unanimous is True
    assert stat.score_range == 0
    assert stat.stdev == 0.0
    assert stat.na_flip is False


def test_single_flip_breaks_unanimity():
    stat = item_criterion_stat("S1", "C2", [1, 1, 1, 1, 2])
    assert stat.modal_score == 1
    assert stat.modal_agreement == 0.8
    assert stat.unanimous is False
    assert stat.score_range == 1
    assert round(stat.stdev, 4) == 0.4  # pstdev of [1,1,1,1,2]
    assert stat.na_flip is False


def test_na_flip_mixed_na_and_numeric():
    stat = item_criterion_stat("S1", "C9", [1, 1, None, 1, None])
    assert stat.n == 5
    assert stat.n_na == 2
    assert stat.na_flip is True
    assert stat.unanimous is False
    assert stat.modal_score == 1
    assert stat.modal_agreement == 0.6  # mode count 3 over N=5
    assert stat.score_range == 0
    assert stat.stdev == 0.0


def test_all_na_item():
    stat = item_criterion_stat("S1", "C5", [None, None, None, None, None])
    assert stat.n_na == 5
    assert stat.na_flip is False  # not a flip: uniformly NA
    assert stat.modal_score is None
    assert stat.unanimous is False
    assert stat.score_range is None
    assert stat.stdev is None


def test_criteria_order_is_c1_to_c9():
    assert CRITERIA_ORDER == ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9")
