"""LangGraph orchestrator for the multi-agent evaluation pipeline.

Sequential fan-out → fan-in (D015): the four agents A1..A4 run one
after the other; an aggregator collapses their outputs into an
``AggregatedResult``; a deterministic synthesizer produces the
Markdown report; a ``finalize`` node sets ``finished_at`` (real
persistence happens OUTSIDE the graph in
:mod:`app.evaluation.service`).

Graph topology::

    START -> prepare_context
          -> a1 -> a2 -> a3 -> a4
          -> aggregate -> synthesize -> finalize -> END

Every agent node is independent: a crash in one agent is caught,
recorded in ``state.agent_errors`` and the graph proceeds. The
aggregate node will translate the missing agents into NA tecnico
(``source="agent_error"``) per the rules in :mod:`aggregator`.

Progress events are emitted through an optional ``progress_publisher``
callable. The publisher is a plain ``dict -> None``: the graph never
imports the SSE / FastAPI layer. The async wrapper supplies a
publisher that marshals events onto an asyncio queue.

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
from app.evaluation.agents.external_consistency_agent import (
    ExternalConsistencyAgent,
    build_default_handlers,
    resolver_na_map,
)
from app.evaluation.aggregator import aggregate
from app.evaluation.extended_aggregator import aggregate_extended
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
# A separate factory for the A5 ExternalConsistencyAgent. Kept apart
# from ``AgentFactory`` because A5's constructor and ``evaluate``
# signatures differ from A1-A4 (it consumes ``ResolverOutput`` +
# ``cdl_id``; it produces ``ExtendedAgentOutput`` rather than
# ``AgentOutput``). Forcing it through ``_default_agent_factory``
# would dilute the abstraction.
ExternalAgentFactory = Callable[[Any, Any], "ExternalConsistencyAgent | None"]
ProgressPublisher = Callable[[dict[str, Any]], None]


def _default_agent_factory(agent_code: str, retriever: Any, llm_client: Any) -> Any:
    """Default agent factory: returns a real BaseAgent subclass instance."""
    if agent_code == "A1":
        return CompletenessAgent(retriever=retriever, llm_client=llm_client)
    if agent_code == "A2":
        return PedagogicalAgent(retriever=retriever, llm_client=llm_client)
    if agent_code == "A3":
        return DidacticConsistencyAgent(retriever=retriever, llm_client=llm_client)
    if agent_code == "A4":
        return EditorialCareAgent(retriever=retriever, llm_client=llm_client)
    raise ValueError(f"unknown agent_code: {agent_code!r}")


def _default_external_agent_factory(
    llm_client: Any, external_retriever: Any,
) -> "ExternalConsistencyAgent | None":
    """Build the A5 coordinator with default handlers.

    Returns ``None`` when ``external_retriever`` is ``None`` — that
    cleanly turns off the A5 path on a fresh install whose
    ``external_documents`` Chroma collection has never been created.
    The orchestrator detects ``None`` and skips the a5 node entirely.
    """
    if external_retriever is None:
        return None
    handlers = build_default_handlers(
        llm_client=llm_client, external_retriever=external_retriever,
    )
    return ExternalConsistencyAgent(handlers=handlers)


def build_graph(
    retriever: Any,
    llm_client: Any,
    *,
    external_retriever: Any = None,
    agent_factory: AgentFactory = _default_agent_factory,
    external_agent_factory: ExternalAgentFactory = _default_external_agent_factory,
    progress_publisher: ProgressPublisher | None = None,
):
    """Build the compiled LangGraph for a single-syllabus evaluation.

    Args:
        retriever: A :class:`NormativeRetriever` instance (or duck-type
            equivalent) used by every agent for RAG retrieval.
        llm_client: An :class:`LLMClient` callable (or duck-type) used
            by every agent for the LLM call. In tests pass a fake
            object — the agents themselves are also stubbed via
            ``agent_factory``.
        external_retriever: Optional :class:`ExternalDocumentRetriever`
            instance. ``None`` (the default) turns off the A5 path
            entirely, which keeps a fresh install with no
            ``external_documents`` Chroma collection from breaking the
            graph. When wired, A5 runs after A4 and produces an
            ``extended_agent_output`` distinct from the core
            ``agent_outputs`` map.
        agent_factory: Function ``(agent_code, retriever, llm_client) ->
            BaseAgent``. Defaults to :func:`_default_agent_factory`,
            which returns the production A1..A4 classes.
        external_agent_factory: Function ``(llm_client, external_retriever)
            -> ExternalConsistencyAgent | None`` for A5. Defaults to
            :func:`_default_external_agent_factory`, which returns the
            production coordinator with the standard E1..E5 handlers,
            or ``None`` when ``external_retriever`` is ``None``.
        progress_publisher: Optional ``dict -> None`` callback. When
            present, the agent / aggregate / synthesize nodes call it
            to publish lifecycle events (agent_started, agent_completed,
            agent_failed, aggregation_completed, report_synthesized).
            See :class:`app.schemas.evaluation_event.ProgressEvent` for
            the payload contract.
    """
    publisher: ProgressPublisher = progress_publisher or _noop_publisher

    g: StateGraph = StateGraph(EvaluationState)

    g.add_node("prepare_context", _prepare_context_node)
    for code in _AGENT_NODE_ORDER:
        g.add_node(
            code,
            _make_agent_node(
                code.upper(), retriever, llm_client, agent_factory, publisher
            ),
        )
    g.add_node(
        "a5",
        _make_a5_node(
            llm_client=llm_client,
            external_retriever=external_retriever,
            factory=external_agent_factory,
            publisher=publisher,
        ),
    )
    g.add_node("aggregate", _make_aggregate_node(publisher))
    g.add_node("synthesize", _make_synthesize_node(publisher))
    g.add_node("finalize", _finalize_node)

    g.add_edge(START, "prepare_context")
    g.add_edge("prepare_context", "a1")
    g.add_edge("a1", "a2")
    g.add_edge("a2", "a3")
    g.add_edge("a3", "a4")
    g.add_edge("a4", "a5")
    g.add_edge("a5", "aggregate")
    g.add_edge("aggregate", "synthesize")
    g.add_edge("synthesize", "finalize")
    g.add_edge("finalize", END)

    return g.compile()


def _noop_publisher(_event: dict[str, Any]) -> None:
    return None


# === nodes ==================================================================


def _prepare_context_node(state: EvaluationState) -> dict[str, Any]:
    """Initialise per-run metadata.

    The caller is responsible for producing ``syllabus_snapshot`` (use
    :func:`app.evaluation.state.snapshot_syllabus` on the SQLAlchemy row
    BEFORE invoking the graph). The orchestrator never touches the DB
    session: this keeps the graph reproducible, easy to mock and
    decoupled from persistence.
    """
    syllabus_snapshot = state.get("syllabus_snapshot")
    if not syllabus_snapshot:
        raise ValueError(
            "prepare_context: 'syllabus_snapshot' must be supplied in the initial state. "
            "Call app.evaluation.state.snapshot_syllabus() on the syllabus row before "
            "invoking the graph."
        )

    seuid = state.get("syllabus_seuid", "")
    course_name = (
        state.get("course_name")
        or syllabus_snapshot.get("course_name")
        or "(senza titolo)"
    )

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
    publisher: ProgressPublisher,
) -> Callable[[EvaluationState], dict[str, Any]]:
    """Build a closure that runs one agent and merges its result into the state."""

    def _agent_node(state: EvaluationState) -> dict[str, Any]:
        seuid = state.get("syllabus_seuid")
        publisher({"type": "agent_started", "agent_code": agent_code, "seuid": seuid})
        started = time.time()
        try:
            agent = factory(agent_code, retriever, llm_client)
            output = agent.evaluate(state["syllabus_snapshot"])
            latency_ms = int((time.time() - started) * 1000)
            logger.info(
                "agent_completed",
                agent_code=agent_code,
                seuid=seuid,
                latency_ms=latency_ms,
                n_judgments=len(output.judgments),
            )
            publisher(
                {
                    "type": "agent_completed",
                    "agent_code": agent_code,
                    "seuid": seuid,
                    "latency_ms": latency_ms,
                    "n_judgments": len(output.judgments),
                }
            )
            return merge_agent_output(state, agent_code, output)
        except Exception as exc:  # noqa: BLE001 — intentional: never break the graph
            latency_ms = int((time.time() - started) * 1000)
            logger.error(
                "agent_failed",
                agent_code=agent_code,
                seuid=seuid,
                latency_ms=latency_ms,
                error_type=type(exc).__name__,
                error_message=str(exc),
                exc_info=True,
            )
            publisher(
                {
                    "type": "agent_failed",
                    "agent_code": agent_code,
                    "seuid": seuid,
                    "latency_ms": latency_ms,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
            return merge_agent_error(
                state, agent_code, f"{type(exc).__name__}: {exc}"
            )

    _agent_node.__name__ = f"{agent_code.lower()}_node"
    return _agent_node


def _make_a5_node(
    *,
    llm_client: Any,
    external_retriever: Any,
    factory: ExternalAgentFactory,
    publisher: ProgressPublisher,
) -> Callable[[EvaluationState], dict[str, Any]]:
    """Build the closure that runs A5.

    Skip semantics:
      - ``resolver_output`` missing from the state → A5 never ran (this
        is the legacy four-agent-only path; e.g. an existing test that
        didn't seed the resolver). Return ``{}`` so the state is left
        untouched.
      - factory returns ``None`` (e.g. ``external_retriever is None``
        on a fresh install) → same: A5 cannot run, return ``{}``.

    Failure isolation: any exception raised by the coordinator is
    caught, logged and turned into ``extended_agent_output=None``. The
    aggregate node downstream still produces an ``extended_result``
    with ``status="failed"`` for the audit trail, and the core
    ``status`` field stays untouched.
    """

    def _a5_node(state: EvaluationState) -> dict[str, Any]:
        resolver_output = state.get("resolver_output")
        if resolver_output is None:
            # Backwards-compatible no-op: legacy invocations (most
            # orchestrator tests) don't seed a resolver.
            return {}

        try:
            agent = factory(llm_client, external_retriever)
        except Exception as exc:  # noqa: BLE001 — factory must not break the graph
            logger.warning(
                "a5_factory_failed",
                seuid=state.get("syllabus_seuid"),
                error=str(exc),
                exc_info=True,
            )
            return {"extended_agent_output": None}
        if agent is None:
            return {}

        seuid = state.get("syllabus_seuid")
        publisher({"type": "agent_started", "agent_code": "A5", "seuid": seuid})
        started = time.time()
        try:
            output = agent.evaluate(
                syllabus=state["syllabus_snapshot"],
                cdl_id=int(state.get("cdl_id") or 0),
                resolver_output=resolver_output,
            )
            latency_ms = int((time.time() - started) * 1000)
            logger.info(
                "agent_completed",
                agent_code="A5",
                seuid=seuid,
                latency_ms=latency_ms,
                n_judgments=len(output.judgments),
                handlers_invoked=output.execution_metadata.get(
                    "handlers_invoked", [],
                ),
            )
            publisher(
                {
                    "type": "agent_completed",
                    "agent_code": "A5",
                    "seuid": seuid,
                    "latency_ms": latency_ms,
                    "n_judgments": len(output.judgments),
                }
            )
            return {"extended_agent_output": output}
        except Exception as exc:  # noqa: BLE001 — never break the core flow
            latency_ms = int((time.time() - started) * 1000)
            logger.error(
                "agent_failed",
                agent_code="A5",
                seuid=seuid,
                latency_ms=latency_ms,
                error_type=type(exc).__name__,
                error_message=str(exc),
                exc_info=True,
            )
            publisher(
                {
                    "type": "agent_failed",
                    "agent_code": "A5",
                    "seuid": seuid,
                    "latency_ms": latency_ms,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
            return {"extended_agent_output": None}

    _a5_node.__name__ = "a5_node"
    return _a5_node


def _make_aggregate_node(
    publisher: ProgressPublisher,
) -> Callable[[EvaluationState], dict[str, Any]]:
    def _aggregate_node(state: EvaluationState) -> dict[str, Any]:
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
        publisher(
            {
                "type": "aggregation_completed",
                "seuid": state.get("syllabus_seuid"),
                "status": result.status,
                "core_score": result.core_score,
                "coverage": result.coverage,
                "n_na": len(result.na_criteria),
            }
        )
        patch: dict[str, Any] = {
            "aggregation": result,
            # ``status`` is set by the CORE aggregator only. Any A5
            # outcome (success / partial / failed) is recorded
            # separately on ``extended_result`` and never feeds back
            # into the core run status.
            "status": result.status,
        }

        resolver_output = state.get("resolver_output")
        if resolver_output is not None:
            extended = aggregate_extended(
                state.get("extended_agent_output"),
                resolver_na=resolver_na_map(resolver_output),
            )
            patch["extended_result"] = extended
            logger.info(
                "extended_aggregation_completed",
                seuid=state.get("syllabus_seuid"),
                extended_status=extended.status,
                handler_errors=list(extended.handler_errors.keys()),
                resolver_na_count=sum(
                    1 for r in extended.na_criteria if r.source == "resolver"
                ),
            )
        return patch

    return _aggregate_node


def _make_synthesize_node(
    publisher: ProgressPublisher,
) -> Callable[[EvaluationState], dict[str, Any]]:
    def _synthesize_node(state: EvaluationState) -> dict[str, Any]:
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
        publisher(
            {
                "type": "report_synthesized",
                "seuid": state.get("syllabus_seuid"),
                "report_chars": len(report),
            }
        )
        return {"final_report": report}

    return _synthesize_node


def _finalize_node(state: EvaluationState) -> dict[str, Any]:
    """Stamp ``finished_at`` on the state.

    Persistence happens OUTSIDE the graph — :class:`EvaluationService`
    reads the final state and writes the row. This node only computes
    the timestamp so the service can derive ``duration_ms`` from a
    consistent source.
    """
    aggregation = state.get("aggregation")
    finished_at = datetime.now(timezone.utc)
    started_at = state.get("started_at")
    duration_ms = (
        int((finished_at - started_at).total_seconds() * 1000) if started_at else None
    )

    logger.info(
        "evaluation_graph_finalize",
        seuid=state.get("syllabus_seuid"),
        status=state.get("status"),
        core_score=aggregation.core_score if aggregation else None,
        coverage=aggregation.coverage if aggregation else None,
        n_na=len(aggregation.na_criteria) if aggregation else None,
        report_chars=len(state["final_report"]) if state.get("final_report") else 0,
        duration_ms=duration_ms,
    )
    return {"finished_at": finished_at}
