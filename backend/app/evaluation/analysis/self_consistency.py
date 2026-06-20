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
