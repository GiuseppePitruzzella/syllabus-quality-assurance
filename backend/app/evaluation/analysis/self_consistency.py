"""Descriptive intra-system reliability metrics for repeated evaluation runs.

Pure functions. No Vertex AI, no DB, no LangGraph. Consumes the
structured per-run fields only (scores / NA / CoreScore / coverage /
status / agent_errors) — never the report text — per the experiment
spec (2026-06-20).
"""
from __future__ import annotations

import statistics
from collections import Counter

from pydantic import BaseModel

CRITERIA_ORDER: tuple[str, ...] = (
    "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9",
)


class RunRecord(BaseModel):
    """One evaluation run of one syllabus (structured fields only)."""

    seuid: str
    run_index: int
    status: str
    criterion_scores: dict[str, int | None]
    core_score: float | None
    coverage: float
    agent_errors: dict[str, str] = {}


class ItemCriterionStat(BaseModel):
    """Stability of one criterion on one syllabus across its N runs."""

    seuid: str
    criterion: str
    n: int
    n_na: int
    modal_score: int | None
    modal_agreement: float | None
    unanimous: bool
    score_range: int | None
    stdev: float | None
    na_flip: bool


def item_criterion_stat(
    seuid: str, criterion: str, scores: list[int | None]
) -> ItemCriterionStat:
    """Compute within-item stability for one criterion across N runs.

    ``scores`` is one value per run, in {0, 1, 2} or ``None`` (NA).
    Modal agreement uses N (all runs) as denominator, with NA treated
    as its own category; numeric stats (range, stdev) use the non-NA
    subset. ``na_flip`` flags evaluability instability (some NA, some
    not). ``unanimous`` means all N runs equal AND non-NA.
    """
    n = len(scores)
    numeric = [s for s in scores if s is not None]
    n_na = n - len(numeric)

    counter = Counter(scores)
    modal_value, modal_count = counter.most_common(1)[0]
    modal_agreement = modal_count / n if n else None

    return ItemCriterionStat(
        seuid=seuid,
        criterion=criterion,
        n=n,
        n_na=n_na,
        modal_score=modal_value,
        modal_agreement=modal_agreement,
        unanimous=(modal_count == n and modal_value is not None),
        score_range=(max(numeric) - min(numeric)) if numeric else None,
        stdev=statistics.pstdev(numeric) if numeric else None,
        na_flip=0 < n_na < n,
    )


class CriterionAggregate(BaseModel):
    """Per-criterion stability across the sampled syllabi."""

    criterion: str
    n_items: int
    unanimity_rate: float
    mean_stdev: float
    flip_rate: float
    max_swing: int
    na_flip_count: int


class CoreScoreItemStat(BaseModel):
    """CoreScore stability for one syllabus across its N runs."""

    seuid: str
    n: int
    mean: float | None
    stdev: float | None
    score_range: float | None


class CoreScoreAggregate(BaseModel):
    n_items: int
    mean_stdev: float
    max_swing: float


class RunStatusCounts(BaseModel):
    total: int
    completed: int
    partial: int
    failed: int
    other: int
    agent_error_incidence: int


class SelfConsistencyMetrics(BaseModel):
    n_seuids: int
    n_runs_per_seuid: dict[str, int]
    per_item_criterion: list[ItemCriterionStat]
    criterion_aggregates: list[CriterionAggregate]
    corescore_items: list[CoreScoreItemStat]
    corescore_aggregate: CoreScoreAggregate
    run_status: RunStatusCounts


def _ordered_seuids(records: list[RunRecord]) -> list[str]:
    seen: list[str] = []
    for r in records:
        if r.seuid not in seen:
            seen.append(r.seuid)
    return seen


def _runs_for(records: list[RunRecord], seuid: str) -> list[RunRecord]:
    return sorted(
        (r for r in records if r.seuid == seuid), key=lambda r: r.run_index
    )


def _criterion_aggregate(
    criterion: str, stats: list[ItemCriterionStat]
) -> CriterionAggregate:
    n_items = len(stats)
    unanimity_rate = (
        sum(1 for s in stats if s.unanimous) / n_items if n_items else 0.0
    )
    stdevs = [s.stdev for s in stats if s.stdev is not None]
    mean_stdev = sum(stdevs) / len(stdevs) if stdevs else 0.0
    flips = [1.0 - s.modal_agreement for s in stats if s.modal_agreement is not None]
    flip_rate = sum(flips) / len(flips) if flips else 0.0
    ranges = [s.score_range for s in stats if s.score_range is not None]
    max_swing = max(ranges) if ranges else 0
    na_flip_count = sum(1 for s in stats if s.na_flip)
    return CriterionAggregate(
        criterion=criterion,
        n_items=n_items,
        unanimity_rate=round(unanimity_rate, 4),
        mean_stdev=round(mean_stdev, 4),
        flip_rate=round(flip_rate, 4),
        max_swing=max_swing,
        na_flip_count=na_flip_count,
    )


def _corescore_item(seuid: str, runs: list[RunRecord]) -> CoreScoreItemStat:
    values = [r.core_score for r in runs if r.core_score is not None]
    return CoreScoreItemStat(
        seuid=seuid,
        n=len(runs),
        mean=round(statistics.mean(values), 4) if values else None,
        stdev=round(statistics.pstdev(values), 4) if values else None,
        score_range=round(max(values) - min(values), 4) if values else None,
    )


def compute_self_consistency(records: list[RunRecord]) -> SelfConsistencyMetrics:
    """Aggregate descriptive run-to-run stability metrics over all records."""
    seuids = _ordered_seuids(records)

    per_item: list[ItemCriterionStat] = []
    per_crit_stats: dict[str, list[ItemCriterionStat]] = {c: [] for c in CRITERIA_ORDER}
    corescore_items: list[CoreScoreItemStat] = []
    n_runs_per_seuid: dict[str, int] = {}

    for seuid in seuids:
        runs = _runs_for(records, seuid)
        n_runs_per_seuid[seuid] = len(runs)
        for criterion in CRITERIA_ORDER:
            scores = [r.criterion_scores.get(criterion) for r in runs]
            stat = item_criterion_stat(seuid, criterion, scores)
            per_item.append(stat)
            per_crit_stats[criterion].append(stat)
        corescore_items.append(_corescore_item(seuid, runs))

    criterion_aggregates = [
        _criterion_aggregate(c, per_crit_stats[c]) for c in CRITERIA_ORDER
    ]

    cs_stdevs = [it.stdev for it in corescore_items if it.stdev is not None]
    cs_ranges = [it.score_range for it in corescore_items if it.score_range is not None]
    corescore_aggregate = CoreScoreAggregate(
        n_items=len(corescore_items),
        mean_stdev=round(sum(cs_stdevs) / len(cs_stdevs), 4) if cs_stdevs else 0.0,
        max_swing=round(max(cs_ranges), 4) if cs_ranges else 0.0,
    )

    status_counter = Counter(r.status for r in records)
    run_status = RunStatusCounts(
        total=len(records),
        completed=status_counter.get("completed", 0),
        partial=status_counter.get("partial", 0),
        failed=status_counter.get("failed", 0),
        other=len(records)
        - status_counter.get("completed", 0)
        - status_counter.get("partial", 0)
        - status_counter.get("failed", 0),
        agent_error_incidence=sum(1 for r in records if r.agent_errors),
    )

    return SelfConsistencyMetrics(
        n_seuids=len(seuids),
        n_runs_per_seuid=n_runs_per_seuid,
        per_item_criterion=per_item,
        criterion_aggregates=criterion_aggregates,
        corescore_items=corescore_items,
        corescore_aggregate=corescore_aggregate,
        run_status=run_status,
    )
