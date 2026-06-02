"""Aggregation of per-agent judgments into a single AggregatedResult.

Pure functions. No I/O, no LangGraph, no Vertex AI. The aggregator
collapses the four per-agent ``AgentOutput`` objects (or their absence
when an agent failed) into the rubric-level scoring documented in
D017 (CoreScore = mean of valid scores) and D018 (NA distinct from 0).

Status decision rules (validated with Giuseppe in the 5.4.G design):

- ``completed``: every agent ran successfully (no entry in
  ``agent_errors``). NA judgments produced *by the agents themselves*
  (``CriterionJudgment.is_na=True``) are still compatible with
  ``completed`` — they represent legitimate non-evaluability, not a
  technical failure.
- ``partial``: at least one agent failed (entry in ``agent_errors``)
  but at least one other agent succeeded. The criteria of the failed
  agents go into NA with ``source="agent_error"``.
- ``failed``: every agent failed. The result has zero coverage.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.evaluation.agents.schemas import AgentOutput

# Static mapping from agent code to criteria the agent owns.
# Single source of truth for the orchestrator and the aggregator.
AGENT_CRITERIA: dict[str, tuple[str, ...]] = {
    "A1": ("C1", "C2", "C5"),
    "A2": ("C3", "C4"),
    "A3": ("C6", "C7", "C8"),
    "A4": ("C9",),
}

# Flat list of all core criteria covered by the rubric (C1..C9).
ALL_CORE_CRITERIA: tuple[str, ...] = tuple(
    code for codes in AGENT_CRITERIA.values() for code in codes
)


class NACriterionRecord(BaseModel):
    """Why a criterion did not produce a numeric score.

    ``source`` distinguishes:
    - ``"agent"``: the agent explicitly marked the criterion ``is_na=True``;
      ``reason`` carries the agent's ``na_reason``.
    - ``"agent_error"``: the agent crashed; ``reason`` carries the caught
      exception message and the criterion inherits NA from the failure.
    - ``"technical"``: every other technical reason (e.g. an agent
      returned a malformed payload that survived schema validation
      but lacks the expected criterion).
    """

    criterion_code: str = Field(..., pattern=r"^C[1-9]$")
    reason: str = Field(..., min_length=1)
    source: Literal["agent", "agent_error", "technical"]


RunStatus = Literal["completed", "partial", "failed"]


class AggregatedResult(BaseModel):
    """Rubric-level aggregation of the four agent outputs.

    Attributes:
        criterion_scores: One entry per C1..C9. ``None`` means the
            criterion is NA (look in ``na_criteria`` for the reason).
        core_score: Arithmetic mean of the non-NA scores, in [0, 2].
            ``None`` when ``coverage == 0``.
        coverage: Fraction of criteria with a numeric score, in [0, 1].
        na_criteria: One record per NA criterion. Length equals
            ``9 - non_na_count``.
        status: ``completed`` / ``partial`` / ``failed`` per the rules
            above.
        agent_statuses: Per-agent ``"ok"`` / ``"error"`` summary.
    """

    criterion_scores: dict[str, int | None]
    core_score: float | None
    coverage: float
    na_criteria: list[NACriterionRecord]
    status: RunStatus
    agent_statuses: dict[str, Literal["ok", "error"]]


def aggregate(
    agent_outputs: dict[str, AgentOutput | None],
    agent_errors: dict[str, str],
) -> AggregatedResult:
    """Collapse the four agent outputs into an AggregatedResult.

    ``agent_outputs`` may contain ``None`` for agents that ran but
    crashed (in which case ``agent_errors`` carries the message).
    Agents that never ran at all are simply absent from both maps —
    the aggregator treats them as errors too (status will be ``partial``
    or ``failed`` accordingly).
    """
    agent_statuses, agent_failures = _summarise_agents(agent_outputs, agent_errors)

    criterion_scores: dict[str, int | None] = dict.fromkeys(ALL_CORE_CRITERIA)
    na_records: list[NACriterionRecord] = []
    seen_criteria: set[str] = set()

    # 1. Walk the successful agents and pull each judgment.
    for agent_code, owned_criteria in AGENT_CRITERIA.items():
        if agent_statuses[agent_code] != "ok":
            continue
        output = agent_outputs[agent_code]
        if output is None:  # defensive — agent_statuses already screened this
            continue
        for judgment in output.judgments:
            code = judgment.criterion_code
            if code not in owned_criteria:
                # Out-of-scope judgment from an agent; ignore for safety.
                continue
            seen_criteria.add(code)
            if judgment.is_na:
                criterion_scores[code] = None
                na_records.append(
                    NACriterionRecord(
                        criterion_code=code,
                        reason=judgment.na_reason or "non motivata",
                        source="agent",
                    )
                )
            else:
                criterion_scores[code] = judgment.score

    # 2. Agents that failed contribute NA tecnico for each of their owned criteria.
    for agent_code, owned_criteria in AGENT_CRITERIA.items():
        if agent_statuses[agent_code] == "ok":
            continue
        reason = agent_failures.get(agent_code, "agent did not run")
        for code in owned_criteria:
            if code in seen_criteria:
                continue
            criterion_scores[code] = None
            na_records.append(
                NACriterionRecord(
                    criterion_code=code,
                    reason=f"{agent_code} failed: {reason}",
                    source="agent_error",
                )
            )
            seen_criteria.add(code)

    # 3. Defensive: criteria the rubric expects but no agent reported on.
    for code in ALL_CORE_CRITERIA:
        if code in seen_criteria:
            continue
        criterion_scores[code] = None
        na_records.append(
            NACriterionRecord(
                criterion_code=code,
                reason="nessun agente ha prodotto un giudizio per questo criterio",
                source="technical",
            )
        )

    # 4. CoreScore + coverage.
    valid_scores = [s for s in criterion_scores.values() if s is not None]
    coverage = len(valid_scores) / len(ALL_CORE_CRITERIA)
    core_score = (
        round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else None
    )

    # 5. Status.
    n_ok = sum(1 for status in agent_statuses.values() if status == "ok")
    if n_ok == len(AGENT_CRITERIA):
        status: RunStatus = "completed"
    elif n_ok == 0:
        status = "failed"
    else:
        status = "partial"

    return AggregatedResult(
        criterion_scores=criterion_scores,
        core_score=core_score,
        coverage=coverage,
        na_criteria=na_records,
        status=status,
        agent_statuses=agent_statuses,
    )


def _summarise_agents(
    agent_outputs: dict[str, AgentOutput | None],
    agent_errors: dict[str, str],
) -> tuple[dict[str, Literal["ok", "error"]], dict[str, str]]:
    """Return (agent_statuses, agent_failures) keyed by agent code.

    An agent is considered ``ok`` if and only if:
    - it has a non-None entry in ``agent_outputs``, AND
    - it has NO entry in ``agent_errors``.

    The second map carries the failure reason for agents that are NOT
    ok, with a synthetic message for agents that never produced
    anything (key missing from both maps).
    """
    statuses: dict[str, Literal["ok", "error"]] = {}
    failures: dict[str, str] = {}
    for agent_code in AGENT_CRITERIA:
        output = agent_outputs.get(agent_code)
        error = agent_errors.get(agent_code)
        if output is not None and error is None:
            statuses[agent_code] = "ok"
        else:
            statuses[agent_code] = "error"
            failures[agent_code] = error or "agent did not run"
    return statuses, failures
