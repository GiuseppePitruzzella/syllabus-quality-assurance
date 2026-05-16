"""LangGraph orchestrator for the multi-agent evaluation pipeline.

Sequential fan-out → fan-in (D015): the four agents A1..A4 run one
after the other; an aggregator collapses their outputs into an
``AggregatedResult``; a deterministic synthesizer produces the
Markdown report; a ``persist_stub`` records the run via structlog
without touching the DB (the real persistence lives in Phase 5.4.H).

Graph topology::

    START -> prepare_context
          -> a1 -> a2 -> a3 -> a4
          -> aggregate -> synthesize -> persist_stub -> END

Every agent node is independent: a crash in one agent is caught,
recorded in ``state.agent_errors`` and the graph proceeds. The
aggregate node will translate the missing agents into NA tecnico
(``source="agent_error"``) per the rules in :mod:`aggregator`.

The agent classes are looked up via :func:`_default_agent_factory`,
which the tests can monkeypatch to inject ``FakeAgent`` instances
without touching Vertex AI.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import structlog
from langgraph.graph import END, START, StateGraph

from app.evaluation.agents.a1_completeness import CompletenessAgent
from app.evaluation.agents.a2_learning_outcomes import PedagogicalAgent
from app.evaluation.agents.a3_coherence import DidacticConsistencyAgent
from app.evaluation.agents.a4_editorial import EditorialCareAgent
from app.evaluation.aggregator import aggregate
from app.evaluation.state import (
    EvaluationState,
    merge_agent_error,
    merge_agent_output,
)
from app.evaluation.synthesizer import synthesize_report

logger = structlog.get_logger(__name__)


# Sequential order of the agent nodes. The fan-out is logical (D015):
# every agent is independent, but for cost / rate-limit / debuggability
# we run them in series.
_AGENT_NODE_ORDER: tuple[str, ...] = ("a1", "a2", "a3", "a4")

# Agent codes -> agent classes. Indirected through a factory so tests
# can inject fakes without monkey-patching the class imports.
AgentFactory = Callable[[str, Any, Any], Any]


def _default_agent_factory(agent_code: str, retriever: Any, llm_client: Any) -> Any:
    """Default agent factory: returns a real BaseAgent subclass instance.

    Replace via the ``agent_factory`` parameter of :func:`build_graph`
    in tests.
    """
    if agent_code == "A1":
        return CompletenessAgent(retriever=retriever, llm_client=llm_client)
    if agent_code == "A2":
        return PedagogicalAgent(retriever=retriever, llm_client=llm_client)
    if agent_code == "A3":
        return DidacticConsistencyAgent(retriever=retriever, llm_client=llm_client)
    if agent_code == "A4":
        return EditorialCareAgent(retriever=retriever, llm_client=llm_client)
    raise ValueError(f"unknown agent_code: {agent_code!r}")


def build_graph(
    retriever: Any,
    llm_client: Any,
    *,
    agent_factory: AgentFactory = _default_agent_factory,
):
    """Build the compiled LangGraph for a single-syllabus evaluation.

    Args:
        retriever: A :class:`NormativeRetriever` instance (or duck-type
            equivalent) used by every agent for RAG retrieval.
        llm_client: An :class:`LLMClient` callable (or duck-type) used
            by every agent for the LLM call. In tests pass a fake
            object — the agents themselves are also stubbed via
            ``agent_factory``.
        agent_factory: Function ``(agent_code, retriever, llm_client) ->
            BaseAgent``. Defaults to :func:`_default_agent_factory`,
            which returns the production A1..A4 classes. Tests override
            this to inject :class:`FakeAgent` instances.

    Returns:
        A compiled LangGraph. Invoke it with::

            graph = build_graph(retriever, llm_client)
            final_state = graph.invoke(
                {"syllabus_seuid": "...", "syllabus_snapshot": {...},
                 "course_name": "..."}
            )
    """
    g: StateGraph = StateGraph(EvaluationState)

    g.add_node("prepare_context", _prepare_context_node)
    for code in _AGENT_NODE_ORDER:
        g.add_node(
            code,
            _make_agent_node(code.upper(), retriever, llm_client, agent_factory),
        )
    g.add_node("aggregate", _aggregate_node)
    g.add_node("synthesize", _synthesize_node)
    g.add_node("persist_stub", _persist_stub_node)

    # Linear edges. Each agent node feeds the next; the aggregate node
    # depends on all four agent outputs being present.
    g.add_edge(START, "prepare_context")
    g.add_edge("prepare_context", "a1")
    g.add_edge("a1", "a2")
    g.add_edge("a2", "a3")
    g.add_edge("a3", "a4")
    g.add_edge("a4", "aggregate")
    g.add_edge("aggregate", "synthesize")
    g.add_edge("synthesize", "persist_stub")
    g.add_edge("persist_stub", END)

    return g.compile()


# === nodes ==================================================================


def _prepare_context_node(state: EvaluationState) -> dict[str, Any]:
    """Initialise per-run metadata.

    The caller is responsible for producing ``syllabus_snapshot`` (use
    :func:`app.evaluation.state.snapshot_syllabus` on the SQLAlchemy row
    BEFORE invoking the graph). The orchestrator never touches the DB
    session: this keeps the graph reproducible, easy to mock and
    decoupled from persistence.

    Always sets ``status="running"``, ``started_at`` and initialises
    the empty maps for the agent contributions.
    """
    syllabus_snapshot = state.get("syllabus_snapshot")
    if not syllabus_snapshot:
        raise ValueError(
            "prepare_context: 'syllabus_snapshot' must be supplied in the initial state. "
            "Call app.evaluation.state.snapshot_syllabus() on the syllabus row before "
            "invoking the graph."
        )

    seuid = state.get("syllabus_seuid", "")
    course_name = state.get("course_name") or syllabus_snapshot.get("course_name") or "(senza titolo)"

    logger.info(
        "evaluation_started",
        seuid=seuid,
        course_name=course_name,
    )

    return {
        "syllabus_seuid": seuid,
        "course_name": course_name,
        "syllabus_snapshot": syllabus_snapshot,
        "agent_outputs": {},
        "agent_errors": {},
        "started_at": datetime.now(timezone.utc),
        "status": "running",
    }


def _make_agent_node(
    agent_code: str,
    retriever: Any,
    llm_client: Any,
    factory: AgentFactory,
) -> Callable[[EvaluationState], dict[str, Any]]:
    """Build a closure that runs one agent and merges its result into the state."""

    def _agent_node(state: EvaluationState) -> dict[str, Any]:
        started = time.time()
        try:
            agent = factory(agent_code, retriever, llm_client)
            output = agent.evaluate(state["syllabus_snapshot"])
            latency_ms = int((time.time() - started) * 1000)
            logger.info(
                "agent_completed",
                agent_code=agent_code,
                seuid=state.get("syllabus_seuid"),
                latency_ms=latency_ms,
                n_judgments=len(output.judgments),
            )
            return merge_agent_output(state, agent_code, output)
        except Exception as exc:  # noqa: BLE001 — intentional: never break the graph
            latency_ms = int((time.time() - started) * 1000)
            logger.error(
                "agent_failed",
                agent_code=agent_code,
                seuid=state.get("syllabus_seuid"),
                latency_ms=latency_ms,
                error_type=type(exc).__name__,
                error_message=str(exc),
                exc_info=True,
            )
            return merge_agent_error(
                state, agent_code, f"{type(exc).__name__}: {exc}"
            )

    _agent_node.__name__ = f"{agent_code.lower()}_node"
    return _agent_node


def _aggregate_node(state: EvaluationState) -> dict[str, Any]:
    """Collapse the four agent outputs into an :class:`AggregatedResult`.

    Status returned by :func:`aggregate` propagates into the graph
    state, so downstream consumers (and the eventual persistence layer)
    can read it directly from ``state["status"]``.
    """
    agent_outputs = state.get("agent_outputs") or {}
    agent_errors = state.get("agent_errors") or {}
    result = aggregate(agent_outputs, agent_errors)
    logger.info(
        "aggregation_completed",
        seuid=state.get("syllabus_seuid"),
        status=result.status,
        core_score=result.core_score,
        coverage=result.coverage,
        n_na=len(result.na_criteria),
    )
    return {"aggregation": result, "status": result.status}


def _synthesize_node(state: EvaluationState) -> dict[str, Any]:
    """Compose the deterministic Markdown report.

    The synthesizer is a pure function: it cannot fail under valid
    inputs. Defensive try/except still wraps it so an unforeseen bug
    here doesn't take down the whole graph — instead, it leaves
    ``final_report=None`` and the persist node will log a warning.
    """
    aggregation = state.get("aggregation")
    if aggregation is None:
        logger.warning(
            "synthesize_skipped_missing_aggregation",
            seuid=state.get("syllabus_seuid"),
        )
        return {"final_report": None}

    course_name = state.get("course_name", "(senza titolo)")
    agent_outputs = state.get("agent_outputs") or {}

    try:
        report = synthesize_report(course_name, aggregation, agent_outputs)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "synthesize_failed",
            seuid=state.get("syllabus_seuid"),
            error_type=type(exc).__name__,
            error_message=str(exc),
            exc_info=True,
        )
        return {"final_report": None}

    logger.info(
        "report_synthesized",
        seuid=state.get("syllabus_seuid"),
        report_chars=len(report),
    )
    return {"final_report": report}


def _persist_stub_node(state: EvaluationState) -> dict[str, Any]:
    """Stub persistence: log a structured event and set ``finished_at``.

    Phase 5.4.H will replace this node with one that writes the run to
    ``EvaluationResult`` (per the expanded schema in Appendix C of the
    plan). Keeping the stub here means the graph topology is final and
    the only change later is the body of one node.
    """
    aggregation = state.get("aggregation")
    finished_at = datetime.now(timezone.utc)
    started_at = state.get("started_at")
    duration_ms = (
        int((finished_at - started_at).total_seconds() * 1000) if started_at else None
    )

    logger.info(
        "evaluation_persisted_stub",
        seuid=state.get("syllabus_seuid"),
        status=state.get("status"),
        core_score=aggregation.core_score if aggregation else None,
        coverage=aggregation.coverage if aggregation else None,
        n_na=len(aggregation.na_criteria) if aggregation else None,
        report_chars=len(state["final_report"]) if state.get("final_report") else 0,
        duration_ms=duration_ms,
    )
    return {"finished_at": finished_at}
