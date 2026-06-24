"""Shared state for the LangGraph evaluation pipeline (Phase 5.4.G).

The state is a ``TypedDict`` because LangGraph patches it by returning
partial dicts from each node. ``total=False`` lets us write nodes that
only set the fields they touch.

The state holds a plain-dict ``syllabus_snapshot`` (not the SQLAlchemy
row) on purpose: once the graph starts running, the orchestrator must
not touch the DB session for read-after-write surprises, lazy-loading
across thread boundaries, or persistence concerns. A Pydantic-validated
snapshot makes the graph reproducible and easy to test with synthetic
inputs.

The four-agent fan-out is modelled as TWO maps keyed by agent code:

- ``agent_outputs: dict[str, AgentOutput | None]`` — successful runs.
- ``agent_errors:  dict[str, str]`` — caught exceptions per agent.

Each agent node MUST merge into the existing maps (rather than replace
them) so the previous nodes' contributions survive the patch.
"""
from datetime import datetime
from typing import Any, Literal, Optional, TypedDict

from app.evaluation.agents.external_schemas import ExtendedAgentOutput
from app.evaluation.agents.schemas import AgentOutput
from app.evaluation.aggregator import AggregatedResult
from app.evaluation.extended_aggregator import ExtendedCriteriaResult
from app.local_documents.resolver import ResolverOutput


RunStatus = Literal["pending", "running", "completed", "partial", "failed"]


# NOTE: LangGraph evaluates the TypedDict annotations at runtime to
# wire the state graph, so the type aliases used here MUST be real
# objects, not strings, and ``from __future__ import annotations`` is
# intentionally NOT enabled in this module. PEP 604 unions (``A | B``)
# would also turn the annotations into UnionType objects that
# LangGraph rejects in some code paths, so we use ``Optional`` /
# ``Union`` from the typing module explicitly.
class EvaluationState(TypedDict, total=False):
    """LangGraph state for a single-syllabus evaluation run.

    ``total=False`` because each node returns a partial patch.
    """

    # === Input (set by prepare_context, immutable afterwards) ===
    syllabus_seuid: str
    course_name: str
    syllabus_snapshot: dict

    # === Per-agent contributions (merged by each aX_node) ===
    agent_outputs: dict
    agent_errors: dict

    # === Aggregation + report (filled by aggregate_node / synthesize_node) ===
    aggregation: Optional[AggregatedResult]
    final_report: Optional[str]

    # === A5 / extended criteria (Phase 9.C.5.2) ===
    # ``cdl_id`` / ``resolver_output`` are inputs supplied by
    # ``EvaluationService._run_graph`` from the :class:`PendingRun`.
    # When absent, the a5 node is a no-op so legacy four-agent test
    # invocations keep working unchanged.
    cdl_id: int
    resolver_output: Optional[ResolverOutput]
    # Output of the A5 coordinator, kept distinct from
    # ``agent_outputs`` so the core aggregator never mistakes it for
    # a C1-C9 contribution.
    extended_agent_output: Optional[ExtendedAgentOutput]
    # Aggregated E* result. Computed alongside ``aggregation`` but
    # never influences ``status`` or the core CoreScore.
    extended_result: Optional[ExtendedCriteriaResult]

    # === Run metadata ===
    started_at: datetime
    finished_at: Optional[datetime]
    status: RunStatus


# Public helper: turn an SQLAlchemy Syllabus row into a plain-dict
# snapshot the agents and the report can consume freely. Lives here
# (next to the state schema) rather than in orchestrator.py so it can
# be unit-tested without LangGraph.

# Editorial + content fields A1..A4 may need. Union of A1..A4
# relevant_fields, kept explicit so the snapshot is self-describing.
_SNAPSHOT_FIELDS: tuple[str, ...] = (
    # Editorial metadata (used by A4)
    "course_code",
    "course_name",
    "course_name_en",
    "module",
    "teacher",
    "academic_year",
    "year_of_study",
    "has_english",
    # Italian content
    "learning_outcomes_it",
    "dublin_knowledge_it",
    "dublin_applying_it",
    "dublin_judgement_it",
    "dublin_communication_it",
    "dublin_learning_it",
    "teaching_methods_it",
    "prerequisites_it",
    "attendance_it",
    "course_content_it",
    "references_it",
    "schedule_it",
    "assessment_methods_it",
    "sample_questions_it",
    # English content
    "learning_outcomes_en",
    "dublin_knowledge_en",
    "dublin_applying_en",
    "dublin_judgement_en",
    "dublin_communication_en",
    "dublin_learning_en",
    "teaching_methods_en",
    "prerequisites_en",
    "attendance_en",
    "course_content_en",
    "references_en",
    "schedule_en",
    "assessment_methods_en",
    "sample_questions_en",
)


def snapshot_syllabus(syllabus: Any) -> dict[str, Any]:
    """Return a JSON-serialisable snapshot of the syllabus row.

    Works with either an SQLAlchemy ``Syllabus`` instance or a plain
    dict (useful for tests). Missing attributes default to ``None``.

    The agents still apply their own ``get_relevant_syllabus_fields``
    filter on top of this snapshot, so over-including a field here is
    safe — under-including is not.
    """
    out: dict[str, Any] = {}
    for field in _SNAPSHOT_FIELDS:
        if isinstance(syllabus, dict):
            value = syllabus.get(field)
        else:
            value = getattr(syllabus, field, None)
        out[field] = _coerce(value)
    return out


def _coerce(value: Any) -> Any:
    """Coerce a syllabus field to a JSON-serialisable primitive."""
    if value is None or isinstance(value, (str, bool, int, float, list, dict)):
        return value
    return str(value)


def merge_agent_output(
    state: EvaluationState, agent_code: str, output: AgentOutput
) -> dict[str, Any]:
    """Return a patch that adds ``output`` to ``state.agent_outputs``.

    Used by the agent nodes to avoid clobbering the contributions of
    the agents that ran before them. Returns a dict suitable to be
    yielded directly from a LangGraph node function.
    """
    existing = state.get("agent_outputs") or {}
    return {"agent_outputs": {**existing, agent_code: output}}


def merge_agent_error(
    state: EvaluationState, agent_code: str, error_message: str
) -> dict[str, Any]:
    """Return a patch that adds an error entry for ``agent_code``.

    Marks the agent_outputs entry as ``None`` AND adds to agent_errors,
    so downstream consumers (aggregate_node) can distinguish "didn't
    run yet" (key missing) from "ran but failed" (key present with
    value None + entry in agent_errors).
    """
    existing_outputs = state.get("agent_outputs") or {}
    existing_errors = state.get("agent_errors") or {}
    return {
        "agent_outputs": {**existing_outputs, agent_code: None},
        "agent_errors": {**existing_errors, agent_code: error_message},
    }
