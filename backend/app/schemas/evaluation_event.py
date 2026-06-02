"""SSE event schema for the evaluation pipeline (Phase 5.4.H.2).

Eight typed events describe the lifecycle of a single graph run as
seen by the frontend. The shape is deliberately flat: SSE consumers
read a JSON object per line, so we avoid nested payloads and use
``Optional`` fields for the per-type extras.

Emission contract:

==============================  =======================================
Event                           Emitted by
==============================  =======================================
``evaluation_started``          AsyncEvaluationService, after the
                                pending row is committed.
``agent_started``               Graph: orchestrator agent node, before
                                ``agent.evaluate()``.
``agent_completed``             Graph: orchestrator agent node, on
                                successful return.
``agent_failed``                Graph: orchestrator agent node, on
                                caught exception.
``aggregation_completed``       Graph: aggregate node, after
                                :func:`aggregate`.
``report_synthesized``          Graph: synthesize node, after the
                                Markdown report is built.
``evaluation_completed``        AsyncEvaluationService, after the
                                worker thread finishes successfully.
``error``                       AsyncEvaluationService, on worker
                                exception or timeout.
==============================  =======================================

We deliberately do NOT emit a per-chunk retrieval event (D043): the
retrieved chunks are persisted on the final row and can be inspected
once the evaluation completes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


EventType = Literal[
    "evaluation_started",
    "agent_started",
    "agent_completed",
    "agent_failed",
    "aggregation_completed",
    "report_synthesized",
    "evaluation_completed",
    "error",
]


class ProgressEvent(BaseModel):
    """One SSE frame sent to the evaluation stream consumer."""

    type: EventType
    evaluation_uuid: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # --- per-type fields (all optional) ---
    seuid: str | None = None
    course_name: str | None = None
    agent_code: str | None = None  # agent_started / agent_completed / agent_failed
    latency_ms: int | None = None  # agent_completed / agent_failed
    n_judgments: int | None = None  # agent_completed
    status: str | None = None  # aggregation_completed / evaluation_completed
    core_score: float | None = None  # aggregation_completed
    coverage: float | None = None  # aggregation_completed
    n_na: int | None = None  # aggregation_completed
    report_chars: int | None = None  # report_synthesized
    duration_ms: int | None = None  # evaluation_completed
    error_type: str | None = None  # agent_failed / error
    error_message: str | None = None  # agent_failed / error


# Sentinel used by the SSE stream endpoint to close the response after
# emitting the terminal event. Not serialised: the registry puts
# ``None`` on the queue and the event generator breaks out of the
# loop.
