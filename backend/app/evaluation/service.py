"""Synchronous EvaluationService (Phase 5.4.H).

The service is the single module that touches both the LangGraph
orchestrator and the database. The flow is split in two halves so the
async layer can return ``evaluation_uuid`` immediately (HTTP 202) and
keep the heavy graph run in a background thread:

1. :meth:`create_pending_run` — opens a session, snapshots the
   syllabus, inserts an ``EvaluationResult`` row in ``status="pending"``
   with a fresh UUID and the full scientific-config snapshot, commits,
   and returns a :class:`PendingRun` that the caller can hand back to
   :meth:`execute_pending_run`.
2. :meth:`execute_pending_run` — invokes the graph (blocking) outside
   any DB session, then persists the final state onto the row.

:meth:`evaluate` is the convenience wrapper for tests and offline /
batch usage: it runs both halves sequentially and returns the
persisted row.

Persistence is intentionally OUTSIDE the graph (per the 5.4.H design
checkpoint): ``graph.invoke()`` returns the final ``EvaluationState``
and this service writes it. The orchestrator stays DB-free and
trivially testable.

The graph is injected as a callable ``graph_invoker(initial_state, *,
progress_publisher=None) -> final_state`` rather than a compiled
LangGraph directly. Tests pass a fake invoker that returns hand-built
final states; the production wiring will pass a closure that builds /
invokes the LangGraph and forwards the publisher.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.config import Settings, settings as default_settings
from app.evaluation.aggregator import AggregatedResult
from app.evaluation.state import EvaluationState, snapshot_syllabus
from app.local_documents.resolver import (
    REGISTRY_SERVED,
    ExternalDocumentResolver,
    ResolverInput,
    ResolverOutput,
)
from app.models import CorsoDiLaurea, Department, EvaluationResult, Syllabus
from app.models.evaluation_external_document import EvaluationExternalDocument
from app.models.local_document import LocalDocument

logger = structlog.get_logger(__name__)


# Per-agent prompt_version snapshot baked into every persisted record
# (D026: each run must be independently reproducible).
#
# A5 is added in Phase 9.C.5.3 as ``"a5_v1"`` — the coordinator-level
# version. The per-criterion handler versions
# (``e1_v1``..``e5_v1``) are recorded separately on
# ``EvaluationResult.extended_criteria_result["agent_output"]
# ["handler_prompt_versions"]`` so a single core
# ``prompt_versions`` snapshot does not have to carry five extra
# keys on every run.
DEFAULT_PROMPT_VERSIONS: dict[str, str] = {
    "A1": "a1_v5",
    "A2": "a2_v1",
    "A3": "a3_v1",
    "A4": "a4_v2",
    "A5": "a5_v1",
}

CORE_CRITERIA: tuple[str, ...] = tuple(f"C{i}" for i in range(1, 10))
TERMINAL_STATUSES: tuple[str, ...] = ("completed", "partial", "failed")


SessionFactory = Callable[[], Session]
ProgressPublisher = Callable[[dict[str, Any]], None]
# A graph invoker accepts the initial state and an optional
# progress_publisher. The publisher is a plain ``dict -> None`` so the
# graph never imports the SSE / FastAPI layer.
GraphInvoker = Callable[..., dict[str, Any]]


class SyllabusNotFoundError(LookupError):
    """Raised when ``create_pending_run(seuid)`` cannot find the syllabus."""


class EvaluationNotFoundError(LookupError):
    """Raised when an ``evaluation_uuid`` is unknown to the service."""


class InvalidSelectedDocumentIdsError(ValueError):
    """Raised when ``selected_document_ids`` violates a 9.E.1 rule.

    ``code`` is a short machine-readable token the API endpoint
    surfaces so clients can branch (``duplicate``, ``unknown``,
    ``not_indexed``, ``archived``, ``wrong_cdl``,
    ``no_enabled_criteria``).
    """

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def _normalise_score(value: Any) -> int | None:
    """Return ``0`` / ``1`` / ``2`` for persisted JSON score values."""
    if value in (0, 1, 2):
        return int(value)
    if value in ("0", "1", "2"):
        return int(value)
    return None


def _core_score_counts(scores: Any) -> dict[str, int]:
    """Count C1-C9 outcomes for one evaluation row.

    Missing/non-dict scores are treated as unavailable — this is the
    expected shape for failed runs, which the Results page reports via
    status rather than pretending all nine criteria were NA.
    """
    out = {
        "critical_count": 0,
        "improvable_count": 0,
        "adequate_count": 0,
        "na_count": 0,
    }
    if not isinstance(scores, dict):
        return out
    for code in CORE_CRITERIA:
        score = _normalise_score(scores.get(code))
        if score == 0:
            out["critical_count"] += 1
        elif score == 1:
            out["improvable_count"] += 1
        elif score == 2:
            out["adequate_count"] += 1
        else:
            out["na_count"] += 1
    return out


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


@dataclass(frozen=True)
class PendingRun:
    """Everything :meth:`EvaluationService.execute_pending_run` needs.

    Returned by :meth:`EvaluationService.create_pending_run` so the
    async layer can publish ``evaluation_started`` and schedule the
    blocking graph execution without re-opening the DB session.

    ``cdl_id`` and ``resolver_output`` are added in Phase 9.C.5.1 so
    the A5 coordinator (wired in 9.C.5.2) can drive its
    per-criterion handlers off the already-computed resolver verdict
    without re-running it inside the graph.
    """

    evaluation_uuid: str
    seuid: str
    course_name: str
    syllabus_snapshot: dict[str, Any]
    cdl_id: int
    resolver_output: ResolverOutput


class EvaluationService:
    """Sync evaluation service.

    Construct once at application startup with the production
    ``graph_invoker`` and reuse across requests. Each call to
    :meth:`create_pending_run` / :meth:`execute_pending_run` opens its
    own short-lived DB session.
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

    def create_pending_run(
        self,
        seuid: str,
        *,
        selected_document_ids: list[int] | None = None,
    ) -> PendingRun:
        """Pre-allocate the run row and snapshot the syllabus.

        Phase 9.C.5.1 extends this method so the entire pre-graph
        bookkeeping happens in one transaction:

          1. load the syllabus;
          2. INSERT the ``evaluation_results`` pending row + flush;
          3. run :class:`ExternalDocumentResolver` against the same
             session;
          4. INSERT one ``evaluation_external_documents`` row per
             *resolved* document (E4 contributes none; resolver
             hard-NA contributes none);
          5. ``COMMIT``.

        Any exception raised anywhere in this block triggers a
        ``ROLLBACK``: there must never be a pending evaluation row
        without its audit context, and conversely never an audit
        row without a parent evaluation.

        ``selected_document_ids`` lets callers (a future
        ``POST /evaluations`` endpoint) pin specific registry
        versions for this run. ``None`` means "let the resolver
        apply the academic-year ladder".

        Commits before returning so a parallel reader (the SSE
        stream endpoint in Phase 5.4.H.2) can observe the
        ``pending`` row while the graph runs in a worker thread.

        Raises:
            SyllabusNotFoundError: if no syllabus matches ``seuid``.
            InvalidSelectedDocumentIdsError: if ``selected_document_ids``
                violates a 9.E.1 rule (the API endpoint runs this
                check separately for early-422 reporting, but the
                service runs it again here as a hard guard against
                callers that bypass the endpoint).
        """
        if selected_document_ids:
            self.validate_selected_document_ids(seuid, selected_document_ids)
        with self._session_factory() as session:
            try:
                syllabus = (
                    session.query(Syllabus).filter_by(seuid=seuid).one_or_none()
                )
                if syllabus is None:
                    raise SyllabusNotFoundError(
                        f"syllabus not found: seuid={seuid!r}",
                    )

                record = self._create_pending_record(session, syllabus)
                evaluation_uuid = record.evaluation_uuid
                course_name = record.course_name_snapshot
                syllabus_snapshot = snapshot_syllabus(syllabus)
                cdl_id = syllabus.cdl_id

                resolver = ExternalDocumentResolver(session)
                resolver_output = resolver.resolve(
                    ResolverInput(
                        cdl_id=cdl_id,
                        academic_year=syllabus.academic_year,
                        has_english=syllabus.has_english,
                        selected_document_ids=selected_document_ids,
                    ),
                )

                audit_rows_count = self._persist_external_documents(
                    session,
                    evaluation_result_id=record.id,
                    resolver_output=resolver_output,
                )

                session.commit()
            except Exception:
                session.rollback()
                raise

            logger.info(
                "evaluation_pending_committed",
                evaluation_uuid=evaluation_uuid,
                seuid=seuid,
                cdl_id=cdl_id,
                external_documents_audited=audit_rows_count,
            )

        return PendingRun(
            evaluation_uuid=evaluation_uuid,
            seuid=seuid,
            course_name=course_name,
            syllabus_snapshot=syllabus_snapshot,
            cdl_id=cdl_id,
            resolver_output=resolver_output,
        )

    def execute_pending_run(
        self,
        pending: PendingRun,
        *,
        progress_publisher: ProgressPublisher | None = None,
    ) -> None:
        """Run the graph for an already-created pending row and persist.

        Blocking; meant to be called either directly (offline / tests)
        or via ``asyncio.to_thread`` from the async layer. Any exception
        raised by the graph is caught and persisted as
        ``status="failed"`` — the method never raises for graph errors.
        """
        try:
            final_state = self._run_graph(
                pending=pending,
                progress_publisher=progress_publisher,
            )
            terminal_status = final_state.get("status") or "completed"
            self._persist_success(pending.evaluation_uuid, final_state, terminal_status)
        except Exception as exc:  # noqa: BLE001 — service-level safety net
            logger.error(
                "evaluation_failed",
                evaluation_uuid=pending.evaluation_uuid,
                seuid=pending.seuid,
                error_type=type(exc).__name__,
                error_message=str(exc),
                exc_info=True,
            )
            self._persist_failure(pending.evaluation_uuid, exc)

    def evaluate(
        self,
        seuid: str,
        *,
        progress_publisher: ProgressPublisher | None = None,
    ) -> EvaluationResult:
        """Run a single-syllabus evaluation end to end (sync, convenience).

        Used by tests and the offline / batch entry points. The HTTP
        endpoint uses :meth:`create_pending_run` +
        :meth:`execute_pending_run` directly so the 202 response can
        return the UUID before the graph starts.
        """
        pending = self.create_pending_run(seuid)
        self.execute_pending_run(pending, progress_publisher=progress_publisher)
        return self.get_evaluation(pending.evaluation_uuid)

    def get_evaluation(self, evaluation_uuid: str) -> EvaluationResult:
        """Fetch one ``EvaluationResult`` by UUID. Raises if absent."""
        with self._session_factory() as session:
            record = (
                session.query(EvaluationResult)
                .filter_by(evaluation_uuid=evaluation_uuid)
                .one_or_none()
            )
            if record is None:
                raise EvaluationNotFoundError(
                    f"evaluation not found: {evaluation_uuid!r}"
                )
            session.expunge(record)
            return record

    def validate_selected_document_ids(
        self, seuid: str, selected_document_ids: list[int],
    ) -> None:
        """Apply the 9.E.1 rules; raise :class:`InvalidSelectedDocumentIdsError`
        on the first violation.

        Run by the HTTP endpoint *before* ``create_pending_run`` so a
        bad request never reaches the resolver / graph. Idempotent and
        cheap: only one DB round trip.
        """
        if len(set(selected_document_ids)) != len(selected_document_ids):
            raise InvalidSelectedDocumentIdsError(
                "selected_document_ids contains duplicates",
                code="duplicate",
            )
        with self._session_factory() as session:
            syllabus = (
                session.query(Syllabus).filter_by(seuid=seuid).one_or_none()
            )
            if syllabus is None:
                raise SyllabusNotFoundError(
                    f"syllabus not found: seuid={seuid!r}",
                )
            cdl_id = int(syllabus.cdl_id)
            docs = (
                session.query(LocalDocument)
                .filter(LocalDocument.id.in_(selected_document_ids))
                .all()
            )
            found_ids = {d.id for d in docs}
            missing = sorted(set(selected_document_ids) - found_ids)
            if missing:
                raise InvalidSelectedDocumentIdsError(
                    f"unknown local_document id(s): {missing}",
                    code="unknown",
                )
            for d in docs:
                if d.status != "indexed":
                    raise InvalidSelectedDocumentIdsError(
                        f"local_document id={d.id} is not indexed "
                        f"(status={d.status!r})",
                        code="not_indexed",
                    )
                if d.deleted_at is not None:
                    raise InvalidSelectedDocumentIdsError(
                        f"local_document id={d.id} is archived "
                        "(soft-deleted) and cannot feed a new evaluation",
                        code="archived",
                    )
                if int(d.cdl_id) != cdl_id:
                    raise InvalidSelectedDocumentIdsError(
                        f"local_document id={d.id} belongs to "
                        f"cdl_id={d.cdl_id} but syllabus is on cdl_id={cdl_id}",
                        code="wrong_cdl",
                    )
                if not (d.enabled_criteria or []):
                    raise InvalidSelectedDocumentIdsError(
                        f"local_document id={d.id} has no enabled_criteria; "
                        "cannot serve any extended criterion",
                        code="no_enabled_criteria",
                    )

    def build_resolution_preview(self, seuid: str) -> dict[str, Any]:
        """Compute the per-criterion preview returned by
        ``GET /api/syllabi/{seuid}/resolution-preview``.

        The shape matches :class:`ResolutionPreview` in
        ``app/schemas/evaluation.py`` but the service returns a
        plain dict so the HTTP layer can wrap it into the typed
        Pydantic without the service depending on schemas.

        Deterministic: same syllabus + registry state → same
        preview. Single source of truth for the precedence ladder
        — the frontend dropdown is built off this response, never
        re-implementing the ladder client-side.
        """
        with self._session_factory() as session:
            syllabus = (
                session.query(Syllabus).filter_by(seuid=seuid).one_or_none()
            )
            if syllabus is None:
                raise SyllabusNotFoundError(
                    f"syllabus not found: seuid={seuid!r}",
                )
            cdl_id = int(syllabus.cdl_id)
            academic_year = syllabus.academic_year
            has_english = bool(syllabus.has_english)

            resolver = ExternalDocumentResolver(session)
            resolver_output = resolver.resolve(
                ResolverInput(
                    cdl_id=cdl_id,
                    academic_year=academic_year,
                    has_english=has_english,
                    selected_document_ids=None,
                ),
            )

            by_criterion: dict[str, Any] = {}
            for code in ("E1", "E2", "E3", "E4", "E5"):
                resolution = resolver_output.by_criterion[code]
                if code == "E4":
                    by_criterion[code] = _preview_e4(resolution)
                else:
                    candidates = _preview_registry_candidates(
                        session, cdl_id=cdl_id, criterion_code=code,
                        resolution=resolution,
                    )
                    by_criterion[code] = {
                        "criterion_code": code,
                        "served_by": "registry",
                        "applicable": resolution.applicable,
                        "na_reason": resolution.na_reason,
                        "candidates": candidates,
                    }

        return {
            "seuid": seuid,
            "cdl_id": cdl_id,
            "academic_year": academic_year,
            "has_english": has_english,
            "by_criterion": by_criterion,
        }

    def list_external_documents_used(
        self, evaluation_uuid: str,
    ) -> list[dict[str, Any]]:
        """Return one entry per ``EvaluationExternalDocument`` row for the
        given run, each enriched with the live ``LocalDocument`` title
        and ``deleted_at`` flag.

        Phase 9.D.1: callers (the API endpoint) wrap the entries in
        :class:`ExternalDocumentUsedPayload` and attach them to
        :class:`EvaluationDetail`. The shape is deliberately a plain
        ``list[dict]`` here so the service layer stays free of
        HTTP-schema imports.

        Order is deterministic: by ``criterion_code`` ascending then
        by ``local_document_id`` ascending. E4 cannot appear because
        the audit table never receives E4 rows by construction
        (C.5.1).
        """
        with self._session_factory() as session:
            evaluation = (
                session.query(EvaluationResult)
                .filter_by(evaluation_uuid=evaluation_uuid)
                .one_or_none()
            )
            if evaluation is None:
                raise EvaluationNotFoundError(
                    f"evaluation not found: {evaluation_uuid!r}",
                )
            rows = (
                session.query(EvaluationExternalDocument, LocalDocument)
                .outerjoin(
                    LocalDocument,
                    LocalDocument.id == EvaluationExternalDocument.local_document_id,
                )
                .filter(
                    EvaluationExternalDocument.evaluation_result_id == evaluation.id,
                )
                .order_by(
                    EvaluationExternalDocument.criterion_code.asc(),
                    EvaluationExternalDocument.local_document_id.asc(),
                )
                .all()
            )
            out: list[dict[str, Any]] = []
            for audit, doc in rows:
                out.append(
                    {
                        "criterion_code": audit.criterion_code,
                        "local_document_id": audit.local_document_id,
                        "document_type": audit.document_type_snapshot,
                        "document_version": audit.document_version_snapshot,
                        "file_hash": audit.file_hash_snapshot,
                        "resolution_reason": audit.resolution_reason,
                        "title": doc.title if doc is not None else None,
                        "deleted_at": doc.deleted_at if doc is not None else None,
                    },
                )
            return out

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

    def build_results_summary(self) -> dict[str, Any]:
        """Aggregate the latest terminal evaluation per syllabus.

        Phase 12 uses this method as the single source of truth for the
        Results page. The method intentionally works over terminal runs
        only (``completed`` / ``partial`` / ``failed``):

          * the latest terminal run per syllabus defines the current
            experimental picture;
          * failed runs are counted in status totals and shown in the
            table, but excluded from CoreScore/coverage averages and
            per-criterion distributions;
          * repeated historical runs do not inflate the distribution.
        """
        with self._session_factory() as session:
            rows = (
                session.query(EvaluationResult, Syllabus, CorsoDiLaurea, Department)
                .join(Syllabus, EvaluationResult.syllabus_id == Syllabus.id)
                .join(CorsoDiLaurea, Syllabus.cdl_id == CorsoDiLaurea.id)
                .join(Department, CorsoDiLaurea.department_id == Department.id)
                .filter(EvaluationResult.status.in_(TERMINAL_STATUSES))
                .order_by(
                    EvaluationResult.started_at.desc(),
                    EvaluationResult.id.desc(),
                )
                .all()
            )

            latest_by_syllabus: dict[int, tuple[
                EvaluationResult, Syllabus, CorsoDiLaurea, Department,
            ]] = {}
            for evaluation, syllabus, cdl, department in rows:
                latest_by_syllabus.setdefault(
                    evaluation.syllabus_id,
                    (evaluation, syllabus, cdl, department),
                )

            latest_rows = list(latest_by_syllabus.values())
            status_counts = {status: 0 for status in TERMINAL_STATUSES}
            core_scores: list[float] = []
            coverages: list[float] = []
            criteria = {
                code: {"criterion_code": code, "score_0": 0, "score_1": 0,
                       "score_2": 0, "na": 0}
                for code in CORE_CRITERIA
            }
            table_rows: list[dict[str, Any]] = []
            total_critical = 0
            total_improvable = 0
            total_na = 0

            for evaluation, syllabus, cdl, department in latest_rows:
                status_counts[evaluation.status] = (
                    status_counts.get(evaluation.status, 0) + 1
                )
                counts = _core_score_counts(evaluation.criterion_scores)
                total_critical += counts["critical_count"]
                total_improvable += counts["improvable_count"]
                if evaluation.status != "failed" and isinstance(
                    evaluation.criterion_scores, dict
                ):
                    total_na += counts["na_count"]
                    for code in CORE_CRITERIA:
                        score = _normalise_score(
                            evaluation.criterion_scores.get(code),
                        )
                        if score is None:
                            criteria[code]["na"] += 1
                        else:
                            criteria[code][f"score_{score}"] += 1
                    if evaluation.core_score is not None:
                        core_scores.append(float(evaluation.core_score))
                    if evaluation.coverage is not None:
                        coverages.append(float(evaluation.coverage))

                table_rows.append(
                    {
                        "evaluation_uuid": evaluation.evaluation_uuid,
                        "syllabus_seuid": evaluation.syllabus_seuid_snapshot,
                        "course_name": evaluation.course_name_snapshot,
                        "cdl_name": cdl.name,
                        "cdl_code": cdl.code,
                        "department_name": department.name,
                        "status": evaluation.status,
                        "started_at": evaluation.started_at,
                        "finished_at": evaluation.finished_at,
                        "core_score": evaluation.core_score,
                        "coverage": evaluation.coverage,
                        **counts,
                    },
                )

            return {
                "generated_at": datetime.now(timezone.utc),
                "overview": {
                    "latest_evaluations_count": len(latest_rows),
                    "terminal_runs_count": len(rows),
                    "completed_count": status_counts.get("completed", 0),
                    "partial_count": status_counts.get("partial", 0),
                    "failed_count": status_counts.get("failed", 0),
                    "average_core_score": _mean_or_none(core_scores),
                    "average_coverage": _mean_or_none(coverages),
                    "total_critical_criteria": total_critical,
                    "total_improvable_criteria": total_improvable,
                    "total_na_criteria": total_na,
                },
                "criteria": list(criteria.values()),
                "evaluations": table_rows,
                "human_validation": {
                    "status": "in_preparation",
                    "title": "Validazione umana in preparazione",
                    "description": (
                        "La sezione raccoglierà il confronto tra giudizi del "
                        "sistema e valutazione esperta: accordo per criterio, "
                        "errore medio e casi di maggiore disaccordo."
                    ),
                },
            }

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
        session.flush()
        return record

    def _persist_external_documents(
        self,
        session: Session,
        *,
        evaluation_result_id: int,
        resolver_output: ResolverOutput,
    ) -> int:
        """Insert one audit row per resolved external document.

        Skips E4 entirely (E4 is served by the syllabus's own
        ``*_en`` fields, never by a registry document). Skips
        criteria that the resolver reported as ``applicable=False``
        (they contribute zero documents). Returns the inserted row
        count so callers can log a summary; raises if the
        ``evaluation_external_documents`` table refuses the row
        (unlikely — the unique constraint cannot fire on a fresh
        pending record).
        """
        count = 0
        for code in REGISTRY_SERVED:  # ("E1", "E2", "E3", "E5") — E4 excluded
            resolution = resolver_output.by_criterion.get(code)
            if resolution is None or not resolution.applicable:
                continue
            for doc in resolution.documents:
                session.add(
                    EvaluationExternalDocument(
                        evaluation_result_id=evaluation_result_id,
                        local_document_id=doc.local_document_id,
                        criterion_code=code,
                        document_version_snapshot=doc.document_version_snapshot,
                        file_hash_snapshot=doc.file_hash_snapshot,
                        document_type_snapshot=doc.document_type_snapshot,
                        resolution_reason=doc.resolution_reason,
                    ),
                )
                count += 1
        if count:
            session.flush()
        return count

    def _run_graph(
        self,
        *,
        pending: PendingRun,
        progress_publisher: ProgressPublisher | None,
    ) -> EvaluationState:
        initial_state: dict[str, Any] = {
            "syllabus_seuid": pending.seuid,
            "course_name": pending.course_name,
            "syllabus_snapshot": pending.syllabus_snapshot,
            # 9.C.5.2: A5 inputs. The orchestrator skips the a5 node
            # when ``resolver_output`` is absent, so passing both
            # keys here is what turns A5 ON for a real run.
            "cdl_id": pending.cdl_id,
            "resolver_output": pending.resolver_output,
        }
        logger.info(
            "evaluation_graph_started",
            evaluation_uuid=pending.evaluation_uuid,
            seuid=pending.seuid,
        )
        final_state = _invoke_graph(
            self._graph_invoker, initial_state, progress_publisher
        )
        logger.info(
            "evaluation_graph_completed",
            evaluation_uuid=pending.evaluation_uuid,
            seuid=pending.seuid,
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
            record.extended_criteria_result = _dump_extended_result(
                final_state.get("extended_result"),
                final_state.get("extended_agent_output"),
            )
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


def _invoke_graph(
    invoker: GraphInvoker,
    initial_state: dict[str, Any],
    progress_publisher: ProgressPublisher | None,
) -> EvaluationState:
    """Call ``invoker`` either with or without ``progress_publisher``.

    The legacy test fakes only accept ``(initial_state)``. Production
    invokers built by :func:`make_graph_invoker` accept the keyword
    too. Probing avoids forcing every test to update its fake.
    """
    try:
        return invoker(initial_state, progress_publisher=progress_publisher)
    except TypeError as exc:
        # Only swallow the specific "unexpected keyword argument" — any
        # other TypeError raised inside the graph must bubble up.
        if "progress_publisher" not in str(exc):
            raise
        return invoker(initial_state)


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
    """Aggregate the per-agent ``retrieved_chunks`` by criterion code."""
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


def _preview_e4(resolution: Any) -> dict[str, Any]:
    """Build the E4 preview entry. E4 is served by the syllabus
    itself, so the candidates list is always empty and
    ``served_by`` reflects whether the syllabus has English
    content at all."""
    if not resolution.applicable:
        return {
            "criterion_code": "E4",
            "served_by": "none",
            "applicable": False,
            "na_reason": resolution.na_reason,
            "candidates": [],
        }
    return {
        "criterion_code": "E4",
        "served_by": "syllabus",
        "applicable": True,
        "na_reason": None,
        "candidates": [],
    }


def _preview_registry_candidates(
    session: Session,
    *,
    cdl_id: int,
    criterion_code: str,
    resolution: Any,
) -> list[dict[str, Any]]:
    """List every LocalDocument the user could pick for this criterion.

    Includes archived rows (``deleted_at`` set) flagged
    ``selectable=False`` so the UI can show them as historical
    context without allowing them to feed a new run. Ordered by
    ``local_document_id`` ascending for determinism.

    The auto-resolved ids (the ones the resolver actually picked)
    are flagged ``is_auto_resolved=True`` and carry the
    ``resolution_reason`` from the precedence ladder; alternatives
    leave both fields empty.
    """
    auto_by_id = {
        d.local_document_id: d for d in (resolution.documents or [])
    }
    candidates_rows = (
        session.query(LocalDocument)
        .filter(LocalDocument.cdl_id == cdl_id)
        .filter(LocalDocument.status == "indexed")
        .order_by(LocalDocument.id.asc())
        .all()
    )
    out: list[dict[str, Any]] = []
    for row in candidates_rows:
        enabled = list(row.enabled_criteria or [])
        if criterion_code not in enabled:
            continue
        auto = auto_by_id.get(row.id)
        out.append(
            {
                "local_document_id": int(row.id),
                # 9.E.2.fix: stable chain identifier, identical to the
                # resolver's chain key minus the cdl_id (which is
                # implicit in the request).
                "chain_key": f"{row.document_type}::{row.normalized_title}",
                "title": row.title,
                "document_type": row.document_type,
                "version": int(row.version),
                "file_hash": row.file_hash,
                "academic_year": row.academic_year,
                "enabled_criteria": enabled,
                "is_auto_resolved": auto is not None,
                "resolution_reason": (
                    auto.resolution_reason if auto is not None else None
                ),
                "deleted_at": row.deleted_at,
                "selectable": row.deleted_at is None,
            },
        )
    return out


def _dump_extended_result(
    extended_result: Any | None,
    extended_agent_output: Any | None,
) -> dict[str, Any] | None:
    """Serialise the Phase 9.C.5.3 ``extended_criteria_result`` column.

    Returns ``None`` when the run did not invoke A5 at all (legacy
    runs, or fresh installs without a resolver supplied). Otherwise
    returns a JSON-safe dict carrying the aggregated extended result
    plus the raw ``ExtendedAgentOutput`` for full reproducibility.

    Shape contract::

        {
            "criterion_scores": {"E1": int|None, ..., "E5": int|None},
            "na_criteria":     [{"criterion_code": str,
                                 "source":         "resolver"|"handler_na"|"handler_error",
                                 "reason":         str}, ...],
            "handler_errors":  {<E*>: <error message>, ...},
            "status":          "completed" | "partial" | "failed",
            "agent_output":    <ExtendedAgentOutput.model_dump()> | None
        }
    """
    if extended_result is None and extended_agent_output is None:
        return None
    payload: dict[str, Any] = {}
    if extended_result is not None:
        payload["criterion_scores"] = dict(
            getattr(extended_result, "criterion_scores", {}) or {},
        )
        payload["na_criteria"] = [
            {
                "criterion_code": r.criterion_code,
                "source": r.source,
                "reason": r.reason,
            }
            for r in getattr(extended_result, "na_criteria", []) or []
        ]
        payload["handler_errors"] = dict(
            getattr(extended_result, "handler_errors", {}) or {},
        )
        payload["status"] = getattr(extended_result, "status", None)
    if extended_agent_output is not None and hasattr(
        extended_agent_output, "model_dump",
    ):
        payload["agent_output"] = extended_agent_output.model_dump(mode="json")
    elif extended_agent_output is not None:
        payload["agent_output"] = extended_agent_output  # already dict-shaped
    else:
        payload["agent_output"] = None
    return payload
