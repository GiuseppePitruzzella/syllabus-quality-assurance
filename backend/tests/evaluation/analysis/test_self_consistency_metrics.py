from app.evaluation.analysis.self_consistency import (
    CRITERIA_ORDER,
    RunRecord,
    SelfConsistencyMetrics,
    compute_self_consistency,
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


def _record(seuid, idx, scores, status="completed", core=None, coverage=1.0,
            agent_errors=None):
    return RunRecord(
        seuid=seuid, run_index=idx, status=status, criterion_scores=scores,
        core_score=core, coverage=coverage, agent_errors=agent_errors or {},
    )


def _full_scores(value):
    return {c: value for c in CRITERIA_ORDER}


def test_compute_aggregates_two_syllabi():
    # S1: perfectly stable at 2 everywhere. S2: C2 flips once.
    records = []
    for i in range(1, 6):
        records.append(_record("S1", i, _full_scores(2), core=2.0))
    for i in range(1, 6):
        sc = _full_scores(1)
        if i == 5:
            sc["C2"] = 2
        records.append(_record("S2", i, sc, core=round((1 * 8 + (2 if i == 5 else 1)) / 9, 2)))

    metrics = compute_self_consistency(records)
    assert isinstance(metrics, SelfConsistencyMetrics)
    assert metrics.n_seuids == 2

    by_crit = {ca.criterion: ca for ca in metrics.criterion_aggregates}
    # C1 is unanimous on both items -> unanimity rate 1.0, flip rate 0.
    assert by_crit["C1"].unanimity_rate == 1.0
    assert by_crit["C1"].flip_rate == 0.0
    assert by_crit["C1"].max_swing == 0
    # C2 unanimous on S1 only (1 of 2 items) -> 0.5; one flip on S2.
    assert by_crit["C2"].unanimity_rate == 0.5
    assert round(by_crit["C2"].flip_rate, 3) == round((0.0 + 0.2) / 2, 3)
    assert by_crit["C2"].max_swing == 1
    assert by_crit["C2"].na_flip_count == 0

    assert metrics.run_status.total == 10
    assert metrics.run_status.completed == 10


def test_run_status_counts_partial_and_agent_errors():
    records = [
        _record("S1", 1, _full_scores(2), status="completed", core=2.0),
        _record("S1", 2, {**_full_scores(2), "C9": None}, status="partial",
                core=2.0, coverage=0.89, agent_errors={"A4": "boom"}),
    ]
    metrics = compute_self_consistency(records)
    assert metrics.run_status.total == 2
    assert metrics.run_status.completed == 1
    assert metrics.run_status.partial == 1
    assert metrics.run_status.agent_error_incidence == 1


def test_corescore_aggregate():
    records = [_record("S1", i, _full_scores(2), core=c)
               for i, c in enumerate([1.5, 1.6, 1.5, 1.7, 1.5], start=1)]
    metrics = compute_self_consistency(records)
    item = next(it for it in metrics.corescore_items if it.seuid == "S1")
    assert item.n == 5
    assert round(item.score_range, 4) == 0.2
    assert metrics.corescore_aggregate.max_swing >= 0.2
