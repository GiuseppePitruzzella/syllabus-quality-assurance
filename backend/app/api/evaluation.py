"""Evaluation HTTP endpoints (Phase 5.4.H.2).

The endpoints are thin glue: they fetch an :class:`AsyncEvaluationService`
via dependency injection, delegate, and translate exceptions into
HTTP errors. The async service does the real work (kick off the
graph, publish SSE events).

In production the dependency is provided by :func:`get_async_service`
which builds a singleton wired to the production graph_invoker. Tests
override it with ``app.dependency_overrides`` to inject a fake service
that uses an in-memory DB and a hand-built graph_invoker.
"""
from __future__ import annotations

import asyncio
import functools
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sse_starlette.sse import EventSourceResponse

from app.database import SessionLocal
from app.evaluation.async_service import AsyncEvaluationService
from app.evaluation.registry import evaluation_registry
from app.evaluation.service import (
    EvaluationNotFoundError,
    EvaluationService,
    InvalidSelectedDocumentIdsError,
    SyllabusNotFoundError,
)
from app.schemas.evaluation import (
    EvaluateRequest,
    EvaluationCreated,
    EvaluationDetail,
    EvaluationSummary,
    ExtendedCriteriaResultPayload,
    ExternalDocumentUsedPayload,
    ResolutionPreview,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api", tags=["evaluation"])


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _production_async_service() -> AsyncEvaluationService:
    """Lazily build the production async service.

    The graph_invoker is wired here so the heavy Vertex AI / ChromaDB
    setup happens on first use rather than at import time. Tests don't
    hit this path — they override the dependency entirely.
    """
    import chromadb

    from app.config import settings
    from app.evaluation.agents.llm_client import VertexAILLMClient
    from app.evaluation.orchestrator import build_graph
    from app.evaluation.rag.embeddings import VertexAIEmbeddings
    from app.evaluation.rag.external_retriever import ExternalDocumentRetriever
    from app.evaluation.rag.retriever import NormativeRetriever

    project_id, location = settings.require_vertex_ai_config()
    sci = settings.scientific

    chroma = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    embeddings = VertexAIEmbeddings(
        project_id=project_id,
        location=location,
        model_name=sci.embedding_model,
        output_dimensionality=sci.embedding_output_dimensionality,
    )
    retriever = NormativeRetriever(chroma, embeddings, sci)
    # Phase 9.C.5.2: build the external retriever lazily so a fresh
    # install with no ``external_documents`` collection cannot crash
    # the startup path. The retriever itself returns [] on a missing
    # collection; instantiation is cheap and side-effect-free.
    external_retriever = ExternalDocumentRetriever(chroma, embeddings, sci)
    llm_client = VertexAILLMClient(
        project_id=project_id,
        location=location,
        scientific=sci,
    )

    def _graph_invoker(
        initial_state: dict[str, Any],
        *,
        progress_publisher: Any | None = None,
    ) -> dict[str, Any]:
        graph = build_graph(
            retriever=retriever,
            llm_client=llm_client,
            external_retriever=external_retriever,
            progress_publisher=progress_publisher,
        )
        return graph.invoke(initial_state)

    sync_service = EvaluationService(
        session_factory=SessionLocal,
        graph_invoker=_graph_invoker,
    )
    return AsyncEvaluationService(
        sync_service=sync_service, registry=evaluation_registry
    )


def get_async_service() -> AsyncEvaluationService:
    """FastAPI dependency. Override in tests via ``app.dependency_overrides``."""
    return _production_async_service()


def get_sync_service(
    svc: AsyncEvaluationService = Depends(get_async_service),
) -> EvaluationService:
    """Read-only path uses the underlying sync service directly."""
    return svc._sync  # noqa: SLF001 — intentional reuse


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/evaluate/{seuid}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=EvaluationCreated,
)
async def evaluate_syllabus(
    seuid: str,
    body: EvaluateRequest | None = None,
    service: AsyncEvaluationService = Depends(get_async_service),
) -> EvaluationCreated:
    """Kick off a new evaluation. Returns the UUID immediately (202).

    Phase 9.E.1: the optional body lets the caller pin specific
    ``LocalDocument`` versions via ``selected_document_ids``. The
    list is *additive* — criteria not covered by any explicit id
    continue to be resolved automatically through the standard
    precedence ladder. Validation runs server-side and surfaces a
    structured 422 on the first violation (see
    :class:`InvalidSelectedDocumentIdsError.code`).
    """
    selected_ids = body.selected_document_ids if body is not None else None
    try:
        evaluation_uuid = await service.start_evaluation(
            seuid, selected_document_ids=selected_ids,
        )
    except SyllabusNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidSelectedDocumentIdsError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    return EvaluationCreated(evaluation_uuid=evaluation_uuid)


@router.get(
    "/syllabi/{seuid}/resolution-preview",
    response_model=ResolutionPreview,
)
async def resolution_preview(
    seuid: str,
    sync_service: EvaluationService = Depends(get_sync_service),
) -> ResolutionPreview:
    """Phase 9.E.1 — show how the resolver would resolve E1-E5 for
    this syllabus, plus the alternatives the user can select.

    Deterministic and side-effect-free: the same syllabus + registry
    state always yields the same preview. The endpoint is the
    single source of truth for the precedence ladder — the
    frontend dropdown builds off this response, never
    re-implementing the ladder client-side.
    """
    try:
        payload = await asyncio.to_thread(
            sync_service.build_resolution_preview, seuid,
        )
    except SyllabusNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ResolutionPreview.model_validate(payload)


@router.get(
    "/evaluations/{evaluation_uuid}",
    response_model=EvaluationDetail,
)
async def get_evaluation(
    evaluation_uuid: str,
    sync_service: EvaluationService = Depends(get_sync_service),
) -> EvaluationDetail:
    """Fetch one evaluation by UUID (any status: pending / running / done).

    Phase 9.D.1: the detail payload now also carries
    ``extended_criteria_result`` in its typed, compact shape and
    ``external_documents_used`` (the audit-table view) so the frontend
    can render the E1-E5 section without doing JSON archaeology.
    """
    try:
        record = await asyncio.to_thread(sync_service.get_evaluation, evaluation_uuid)
        external_used = await asyncio.to_thread(
            sync_service.list_external_documents_used, evaluation_uuid,
        )
    except EvaluationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    detail = EvaluationDetail.model_validate(record, from_attributes=True)
    # The base ``model_validate`` reads ``extended_criteria_result`` as
    # the raw dict from the DB column. Re-shape it into the compact
    # payload that lifts ``judgments`` / ``handler_prompt_versions``
    # out of the ``agent_output`` envelope.
    detail.extended_criteria_result = ExtendedCriteriaResultPayload.from_dump(
        record.extended_criteria_result,
    )
    detail.external_documents_used = [
        ExternalDocumentUsedPayload(**row) for row in external_used
    ]
    return detail


@router.get("/evaluations/{evaluation_uuid}/stream")
async def stream_evaluation(
    evaluation_uuid: str,
    request: Request,
    service: AsyncEvaluationService = Depends(get_async_service),
):
    """Server-Sent Events stream of progress events for one evaluation."""
    state = service.registry.get(evaluation_uuid)
    if state is None:
        raise HTTPException(status_code=404, detail="Evaluation stream not found")

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            event = await state.queue.get()
            if event is None:  # sentinel = stream completed
                break
            yield {"data": event.model_dump_json()}

    return EventSourceResponse(event_generator())


@router.get(
    "/syllabi/{seuid}/evaluations",
    response_model=list[EvaluationSummary],
)
async def list_evaluations_for_syllabus(
    seuid: str,
    limit: int = 20,
    sync_service: EvaluationService = Depends(get_sync_service),
) -> list[EvaluationSummary]:
    """History of evaluations for a syllabus, most recent first (D038)."""
    try:
        rows = await asyncio.to_thread(
            sync_service.list_evaluations_for_syllabus, seuid, limit=limit
        )
    except SyllabusNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [EvaluationSummary.model_validate(r, from_attributes=True) for r in rows]
