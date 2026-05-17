"""Synchronous EvaluationService (Phase 5.4.H.1).

The service is the single module that touches both the LangGraph
orchestrator and the database. It pre-allocates an
``EvaluationResult`` row in status=``pending``, runs the graph, then
persists the final state. Phase 5.4.H.2 will add async / SSE on top
without touching this core flow.

Persistence is intentionally OUTSIDE the graph (per the 5.4.H design
checkpoint): ``graph.invoke()`` returns the final ``EvaluationState``
and this service writes it. The orchestrator stays DB-free and
trivially testable.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.config import Settings, settings as default_settings
from app.evaluation.aggregator import AggregatedResult
from app.evaluation.state import EvaluationState, snapshot_syllabus
from app.models import EvaluationResult, Syllabus

logger = structlog.get_logger(__name__)


# Per-agent prompt_version snapshot baked into every persisted record
# (D026: each run must be independently reproducible).
DEFAULT_PROMPT_VERSIONS: dict[str, str] = {
    "A1": "a1_v4",
    "A2": "a2_v1",
    "A3": "a3_v1",
    "A4": "a4_v2",
}


SessionFactory = Callable[[], Session]
GraphInvoker = Callable[[dict[str, Any]], dict[str, Any]]


class SyllabusNotFoundError(LookupError):
    """Raised when ``evaluate(seuid)`` cannot find the syllabus."""


class EvaluationService:
    """Sync evaluation service.

    The graph is injected as a callable ``graph_invoker(initial_state)
    -> final_state`` rather than a compiled LangGraph directly: this
    makes the service trivially testable with a fake invoker that
    returns hand-built final states. The production wiring will pass
    ``compiled_graph.invoke``.
    """

    def __init__(
        self,
        session_factory: SessionFactory,
        graph_invoker: GraphInvoker,
        *,
        settings: Settings | None = None,
        prompt_versions: dict[str, str] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._graph_invoker = graph_invoker
        self._settings = settings or default_settings
        self._prompt_versions = dict(prompt_versions or DEFAULT_PROMPT_VERSIONS)

    # ---- public API ----

    def evaluate(self, seuid: str) -> EvaluationResult:
        """Run a single-syllabus evaluation end to end (sync).

        Steps:
        1. Open a session, find the Syllabus by ``seuid``.
        2. Insert an ``EvaluationResult(status="pending")`` with a fresh
           UUID and the full scientific configuration snapshot.
        3. Build the syllabus snapshot.
        4. Invoke the graph (blocking).
        5. Persist the final state on the same row.
        6. Return the row.

        Raises:
            SyllabusNotFoundError: if no syllabus matches ``seuid``.
        """
        with self._session_factory() as session:
            syllabus = session.query(Syllabus).filter_by(seuid=seuid).one_or_none()
            if syllabus is None:
                raise SyllabusNotFoundError(f"syllabus not found: seuid={seuid!r}")

            record = self._create_pending_record(session, syllabus)
            evaluation_uuid = record.evaluation_uuid
            course_name = record.course_name_snapshot
            syllabus_snapshot = snapshot_syllabus(syllabus)

            # The pending record is committed here so a parallel reader
            # (Phase 5.4.H.2 SSE) can observe the row while the graph runs.
            session.commit()

            logger.info(
                "evaluation_pending_committed",
                evaluation_uuid=evaluation_uuid,
                seuid=seuid,
            )

        # Run the graph OUTSIDE the DB session. The graph is DB-free by design.
        try:
            final_state = self._run_graph(
                evaluation_uuid=evaluation_uuid,
                seuid=seuid,
                course_name=course_name,
                syllabus_snapshot=syllabus_snapshot,
            )
            terminal_status = final_state.get("status") or "completed"
            self._persist_success(evaluation_uuid, final_state, terminal_status)
        except Exception as exc:  # noqa: BLE001 — service-level safety net
            logger.error(
                "evaluation_failed",
                evaluation_uuid=evaluation_uuid,
                seuid=seuid,
                error_type=type(exc).__name__,
                error_message=str(exc),
                exc_info=True,
            )
            self._persist_failure(evaluation_uuid, exc)

        return self.get_evaluation(evaluation_uuid)

    def get_evaluation(self, evaluation_uuid: str) -> EvaluationResult:
        """Fetch one ``EvaluationResult`` by UUID. Raises if absent."""
        with self._session_factory() as session:
            record = (
                session.query(EvaluationResult)
                .filter_by(evaluation_uuid=evaluation_uuid)
                .one_or_none()
            )
            if record is None:
                raise LookupError(f"evaluation not found: {evaluation_uuid!r}")
            # Force loading of all attributes BEFORE the session closes.
            session.expunge(record)
            return record

    def list_evaluations_for_syllabus(
        self, seuid: str, *, limit: int = 20
    ) -> list[EvaluationResult]:
        """History of runs for a syllabus, most recent first (D038)."""
        with self._session_factory() as session:
            syllabus = session.query(Syllabus).filter_by(seuid=seuid).one_or_none()
            if syllabus is None:
                raise SyllabusNotFoundError(f"syllabus not found: seuid={seuid!r}")
            rows = (
                session.query(EvaluationResult)
                .filter_by(syllabus_id=syllabus.id)
                .order_by(EvaluationResult.started_at.desc())
                .limit(limit)
                .all()
            )
            for r in rows:
                session.expunge(r)
            return rows

    # ---- internals ----

    def _create_pending_record(
        self, session: Session, syllabus: Syllabus
    ) -> EvaluationResult:
        sci = self._settings.scientific
        project_id, location = self._settings.require_vertex_ai_config()
        evaluation_uuid = str(uuid.uuid4())
        record = EvaluationResult(
            evaluation_uuid=evaluation_uuid,
            syllabus_id=syllabus.id,
            syllabus_seuid_snapshot=syllabus.seuid,
            course_name_snapshot=syllabus.course_name,
            status="pending",
            started_at=datetime.now(timezone.utc),
            llm_model=sci.llm_model,
            embedding_model=sci.embedding_model,
            embedding_dim=sci.embedding_output_dimensionality,
            llm_temperature=sci.llm_temperature,
            llm_max_output_tokens=sci.llm_max_output_tokens,
            rag_top_k=sci.rag_top_k,
            rag_final_k=sci.rag_final_k,
            rag_similarity_threshold=sci.rag_similarity_threshold,
            gcp_project_id=project_id,
            gcp_location=location,
            prompt_versions=dict(self._prompt_versions),
        )
        session.add(record)
        session.flush()  # populate id
        return record

    def _run_graph(
        self,
        *,
        evaluation_uuid: str,
        seuid: str,
        course_name: str,
        syllabus_snapshot: dict[str, Any],
    ) -> EvaluationState:
        initial_state: dict[str, Any] = {
            "syllabus_seuid": seuid,
            "course_name": course_name,
            "syllabus_snapshot": syllabus_snapshot,
        }
        logger.info(
            "evaluation_graph_started",
            evaluation_uuid=evaluation_uuid,
            seuid=seuid,
        )
        final_state = self._graph_invoker(initial_state)
        logger.info(
            "evaluation_graph_completed",
            evaluation_uuid=evaluation_uuid,
            seuid=seuid,
            status=final_state.get("status"),
        )
        return final_state

    def _persist_success(
        self,
        evaluation_uuid: str,
        final_state: EvaluationState,
        terminal_status: str,
    ) -> None:
        with self._session_factory() as session:
            record = (
                session.query(EvaluationResult)
                .filter_by(evaluation_uuid=evaluation_uuid)
                .one()
            )
            aggregation: AggregatedResult | None = final_state.get("aggregation")
            agent_outputs = final_state.get("agent_outputs") or {}
            agent_errors = final_state.get("agent_errors") or {}
            started_at = record.started_at
            finished_at = final_state.get("finished_at") or datetime.now(timezone.utc)
            duration_ms = _duration_ms(started_at, finished_at)

            record.status = terminal_status
            record.finished_at = finished_at
            record.duration_ms = duration_ms
            record.core_score = aggregation.core_score if aggregation else None
            record.coverage = aggregation.coverage if aggregation else None
            record.criterion_scores = (
                aggregation.criterion_scores if aggregation else None
            )
            record.na_criteria = (
                [r.model_dump() for r in aggregation.na_criteria]
                if aggregation
                else None
            )
            record.agent_outputs = _dump_agent_outputs(agent_outputs)
            record.agent_errors = dict(agent_errors) if agent_errors else None
            record.retrieved_chunks = _index_chunks_by_criterion(agent_outputs)
            record.final_report = final_state.get("final_report")
            session.commit()

    def _persist_failure(
        self,
        evaluation_uuid: str,
        exc: BaseException,
    ) -> None:
        with self._session_factory() as session:
            record = (
                session.query(EvaluationResult)
                .filter_by(evaluation_uuid=evaluation_uuid)
                .one()
            )
            finished_at = datetime.now(timezone.utc)
            record.status = "failed"
            record.finished_at = finished_at
            record.duration_ms = _duration_ms(record.started_at, finished_at)
            record.error_message = f"{type(exc).__name__}: {exc}"
            session.commit()


# === helpers ================================================================


def _duration_ms(started: datetime | None, finished: datetime) -> int | None:
    if started is None:
        return None
    # Datetimes coming from SQLite may be naive while finished_at is UTC-aware.
    # Compare as naive UTC to avoid a TypeError on subtraction.
    if started.tzinfo is None and finished.tzinfo is not None:
        finished = finished.replace(tzinfo=None)
    elif started.tzinfo is not None and finished.tzinfo is None:
        started = started.replace(tzinfo=None)
    return int((finished - started).total_seconds() * 1000)


def _dump_agent_outputs(outputs: dict[str, Any]) -> dict[str, Any]:
    """Serialise each AgentOutput to a JSON-compatible dict, or None."""
    serialised: dict[str, Any] = {}
    for code, output in outputs.items():
        if output is None:
            serialised[code] = None
        elif hasattr(output, "model_dump"):
            serialised[code] = output.model_dump(mode="json")
        else:
            serialised[code] = output  # already a dict
    return serialised


def _index_chunks_by_criterion(
    agent_outputs: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Aggregate the per-agent ``retrieved_chunks`` by criterion code.

    Returns a dict like::

        {"C1": [{"chunk_id": "...", "document_id": "lg_unict",
                 "section_ref": "2", "similarity_score": 0.79}, ...],
         "C3": [...], ...}

    Useful for the persistence layer and the future frontend, which
    will want to look up the chunks per criterion rather than per
    agent.
    """
    by_criterion: dict[str, list[dict[str, Any]]] = {}
    for output in agent_outputs.values():
        if output is None:
            continue
        chunks = getattr(output, "retrieved_chunks", None) or []
        for ref in chunks:
            ref_dict = ref.model_dump() if hasattr(ref, "model_dump") else dict(ref)
            criterion = ref_dict.get("criterion_code") or "_unknown"
            by_criterion.setdefault(criterion, []).append(ref_dict)
    return by_criterion
