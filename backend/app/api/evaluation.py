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
    SyllabusNotFoundError,
)
from app.schemas.evaluation import (
    EvaluationCreated,
    EvaluationDetail,
    EvaluationSummary,
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
    service: AsyncEvaluationService = Depends(get_async_service),
) -> EvaluationCreated:
    """Kick off a new evaluation. Returns the UUID immediately (202)."""
    try:
        evaluation_uuid = await service.start_evaluation(seuid)
    except SyllabusNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return EvaluationCreated(evaluation_uuid=evaluation_uuid)


@router.get(
    "/evaluations/{evaluation_uuid}",
    response_model=EvaluationDetail,
)
async def get_evaluation(
    evaluation_uuid: str,
    sync_service: EvaluationService = Depends(get_sync_service),
) -> EvaluationDetail:
    """Fetch one evaluation by UUID (any status: pending / running / done)."""
    try:
        record = await asyncio.to_thread(sync_service.get_evaluation, evaluation_uuid)
    except EvaluationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return EvaluationDetail.model_validate(record, from_attributes=True)


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
