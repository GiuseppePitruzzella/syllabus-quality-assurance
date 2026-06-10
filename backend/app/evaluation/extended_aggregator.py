"""Aggregator for the A5 ExternalConsistencyAgent (Phase 9.C.1).

Keeps the extended-criteria result strictly separate from the
core ``AggregatedResult``: A5's contribution to the run is
collected here, into an ``ExtendedCriteriaResult`` that mirrors
the shape callers expect but never influences the C1-C9
CoreScore. A failure inside any E* handler — or even a complete
A5 outage — produces a degraded but valid ``ExtendedCriteriaResult``
without changing the core run's ``status`` field.

The function lives next to the existing core ``aggregator.py`` for
symmetry, but it does NOT import from it and is never called by
the core aggregator. The two paths are deliberately decoupled.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.evaluation.agents.external_schemas import (
    ExtendedAgentOutput,
    ExtendedCriterionCode,
    ExtendedCriterionJudgment,
)

ExtendedStatus = Literal["completed", "partial", "failed"]

_ALL_EXTENDED: tuple[ExtendedCriterionCode, ...] = ("E1", "E2", "E3", "E4", "E5")


@dataclass(frozen=True)
class NAExtendedCriterion:
    """A single E* criterion reported NA, with its provenance."""

    criterion_code: ExtendedCriterionCode
    # "resolver"     — resolver said the criterion was not applicable
    #                  (e.g. no SUA-CdS document enabled for E1, or
    #                   has_english=False for E4). A5 was never asked.
    # "handler_na"   — the handler ran and decided the criterion is
    #                  semantically NA (e.g. the SUA-CdS section has
    #                  no information bearing on this syllabus).
    # "handler_error" — the handler crashed or repeatedly failed
    #                   validation. NA tecnico.
    source: Literal["resolver", "handler_na", "handler_error"]
    reason: str


@dataclass(frozen=True)
class ExtendedCriteriaResult:
    """Aggregated A5 output for a run.

    ``status`` semantics:
      - ``completed``: every E* criterion produced a judgment,
        regardless of whether each is numeric or NA. No handler
        crash.
      - ``partial``: at least one handler crashed (the run has
        ``handler_errors``) but at least one criterion produced
        a non-technical judgment.
      - ``failed``: every criterion ended in handler_error.
        The run can still ship its core C1-C9 ``completed``
        status; this only tags the A5 section as unusable.
    """

    criterion_scores: dict[str, int | None] = field(default_factory=dict)
    na_criteria: list[NAExtendedCriterion] = field(default_factory=list)
    handler_errors: dict[str, str] = field(default_factory=dict)
    status: ExtendedStatus = "completed"


def aggregate_extended(
    output: ExtendedAgentOutput | None,
    *,
    resolver_na: dict[str, str] | None = None,
) -> ExtendedCriteriaResult:
    """Collapse the A5 output (and any resolver-side NA reasons)
    into an ``ExtendedCriteriaResult``.

    Args:
        output: The :class:`ExtendedAgentOutput` returned by the A5
            coordinator. ``None`` means A5 itself crashed or was
            skipped entirely; every criterion is reported with a
            ``handler_error`` NA, and ``status`` is ``failed``.
        resolver_na: Optional map ``criterion -> reason`` for
            criteria the resolver already flagged as NA before
            calling A5. These short-circuit the per-criterion
            judgments and are recorded with ``source="resolver"``.
            The coordinator is expected to skip the handler for
            these criteria entirely, so they should NOT appear in
            ``output.judgments``.

    The result fields:
      - ``criterion_scores``: ``E* -> int | None`` for the five
        codes. Numeric for OK judgments, ``None`` for NA.
      - ``na_criteria``: structured per-criterion NA records with
        the source (resolver / handler / error).
      - ``handler_errors``: copy of ``output.handler_errors`` so
        consumers can audit without re-fetching the agent output.
      - ``status``: completed / partial / failed by the rules
        documented on :class:`ExtendedCriteriaResult`.
    """
    resolver_na = resolver_na or {}

    scores: dict[str, int | None] = {}
    na_records: list[NAExtendedCriterion] = []
    handler_errors: dict[str, str] = (
        dict(output.handler_errors) if output is not None else {}
    )

    # Index the agent output (if any) by criterion code for quick lookup.
    judgments_by_code: dict[str, ExtendedCriterionJudgment] = {}
    if output is not None:
        for j in output.judgments:
            judgments_by_code[j.criterion_code] = j

    for code in _ALL_EXTENDED:
        # 1. Resolver said NA. The coordinator should not have called
        #    the handler; we honour that even if a judgment slipped
        #    through (defensive).
        if code in resolver_na:
            scores[code] = None
            na_records.append(
                NAExtendedCriterion(
                    criterion_code=code,
                    source="resolver",
                    reason=resolver_na[code],
                )
            )
            continue

        # 2. Handler explicitly raised — coordinator records the
        #    exception in ``handler_errors``. We map it to a
        #    technical NA so the criterion is present in the result.
        if code in handler_errors:
            scores[code] = None
            na_records.append(
                NAExtendedCriterion(
                    criterion_code=code,
                    source="handler_error",
                    reason=handler_errors[code],
                )
            )
            continue

        # 3. Handler produced a judgment.
        judgment = judgments_by_code.get(code)
        if judgment is None:
            # A5 was somehow skipped for this criterion but didn't
            # record an error. Treat as a technical NA so the
            # downstream consumer always sees the criterion.
            scores[code] = None
            na_records.append(
                NAExtendedCriterion(
                    criterion_code=code,
                    source="handler_error",
                    reason="no judgment produced",
                )
            )
            continue

        if judgment.is_na:
            scores[code] = None
            na_records.append(
                NAExtendedCriterion(
                    criterion_code=code,
                    source=(
                        "handler_error"
                        if judgment.is_na_technical
                        else "handler_na"
                    ),
                    reason=judgment.na_reason or "",
                )
            )
            continue

        scores[code] = judgment.score

    status = _compute_status(output, na_records)
    return ExtendedCriteriaResult(
        criterion_scores=scores,
        na_criteria=na_records,
        handler_errors=handler_errors,
        status=status,
    )


def _compute_status(
    output: ExtendedAgentOutput | None,
    na_records: list[NAExtendedCriterion],
) -> ExtendedStatus:
    """Status tri-state per the 9.C clarification.

    - ``completed``: no technical failure on any criterion. This
      includes the legitimate case where every criterion is hard-
      NA from the resolver — A5 is never invoked, output is
      ``None``, and the status must still be ``completed``
      because nothing failed; A5 simply had nothing to do.
    - ``partial``: at least one criterion failed technically, but
      at least one criterion produced a non-technical outcome
      (numeric score or semantic NA).
    - ``failed``: every applicable criterion failed technically,
      or A5 was expected to run but its output is ``None``.
    """
    total = len(_ALL_EXTENDED)
    resolver_count = sum(1 for r in na_records if r.source == "resolver")
    crashed = sum(1 for r in na_records if r.source == "handler_error")

    # All criteria short-circuited by the resolver — A5 is allowed
    # to be skipped entirely. Nothing failed.
    if resolver_count == total:
        return "completed"

    if output is None:
        # A5 was expected to run on at least one criterion but
        # produced no output at all: that IS a failure.
        return "failed"

    if crashed == 0:
        return "completed"
    if crashed + resolver_count >= total:
        # Every criterion not short-circuited by the resolver
        # ended in a handler error.
        return "failed"
    return "partial"


__all__ = [
    "ExtendedCriteriaResult",
    "NAExtendedCriterion",
    "ExtendedStatus",
    "aggregate_extended",
]
