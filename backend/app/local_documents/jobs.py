"""Async wrapper around the sync indexing service (Phase 8.C).

`LocalDocumentIndexingService` stays purely synchronous: this
module is the only place that touches the JobRegistry / SSE
machinery, so the service can keep its straight-line semantics
and be reused by future CLI / batch tools without dragging an
asyncio dependency along.

Pattern mirrors `app/api/cdl.py::start_scrape_cdl` (the scraping
async-job dance): create a job_id, run the sync work inside
`loop.run_in_executor`, publish `progress` events as the service
transitions, then publish a terminal `done` or `error` and call
`job_registry.complete`.

The scheduler is constructed by a FastAPI dependency provider so
the test suite can swap in a stub that returns a job_id without
actually scheduling a thread.
"""
from __future__ import annotations

import asyncio
from typing import Callable

import chromadb
import structlog

from app.database import SessionLocal
from app.jobs import job_registry
from app.local_documents.ingester import (
    EmbeddingsClient,
    ExternalDocumentIngester,
)
from app.local_documents.service import (
    IndexingError,
    LocalDocumentIndexingService,
)
from app.schemas.job import SseEvent

logger = structlog.get_logger(__name__)


class IndexingJobScheduler:
    """Dispatch a sync indexing run to a worker thread and stream
    progress / completion events on a JobRegistry job_id.

    A new SQLAlchemy session is created inside the worker (the
    request session is bound to the HTTP request and closes
    before the executor runs), and the same ChromaDB client and
    embeddings client are reused — both are process-wide
    singletons surfaced by the dependency providers.
    """

    def __init__(
        self,
        chroma_client: chromadb.api.client.Client,
        embeddings: EmbeddingsClient,
        loop: asyncio.AbstractEventLoop | None = None,
        db_session_factory: Callable[[], object] = SessionLocal,
    ) -> None:
        self._chroma_client = chroma_client
        self._embeddings = embeddings
        # The loop is captured at scheduler construction time. The
        # dependency provider obtains it from the request's async
        # context so a worker thread spawned by `loop.run_in_executor`
        # can publish back via `call_soon_threadsafe` even though
        # the thread itself has no loop.
        self._loop = loop
        self._db_session_factory = db_session_factory

    def schedule(self, document_id: int) -> str:
        """Schedule an indexing run for ``document_id`` and return
        the job id the caller can stream events from.

        The progress channel emits one ``SseEvent(type="progress",
        message=target)`` per state transition (`extracting`,
        `chunking`, `indexing`), then either:

          - ``SseEvent(type="done", scraped=chunks_written)`` on
            success, or
          - ``SseEvent(type="error", message=str(exc))`` on
            failure (the service has already stamped
            ``status="failed"`` + ``failure_reason`` on the row,
            so the DB carries the same info).

        After the terminal event the registry's
        ``complete(job_id, loop)`` enqueues the SSE sentinel and
        schedules the registry-side cleanup (10 min default).
        """
        job_id = job_registry.create_job()
        loop = self._loop if self._loop is not None else asyncio.get_event_loop()

        chroma_client = self._chroma_client
        embeddings = self._embeddings
        session_factory = self._db_session_factory

        def _publish(event: SseEvent) -> None:
            job_registry.publish(job_id, event, loop)

        def _publisher(target: str) -> None:
            _publish(SseEvent(type="progress", message=target))

        def _run() -> None:
            db = session_factory()
            try:
                ingester = ExternalDocumentIngester(chroma_client, embeddings)
                service = LocalDocumentIndexingService(
                    db, ingester, progress_publisher=_publisher,
                )
                try:
                    result = service.index_document(document_id)
                    _publish(
                        SseEvent(
                            type="done",
                            scraped=result.chunks_written,
                        )
                    )
                except IndexingError as exc:
                    _publish(SseEvent(type="error", message=str(exc)))
                except Exception as exc:  # noqa: BLE001 — surface any failure
                    logger.exception(
                        "local_document_indexing_unexpected_error",
                        document_id=document_id,
                        error=str(exc),
                    )
                    _publish(
                        SseEvent(
                            type="error",
                            message=f"unexpected: {exc}",
                        )
                    )
            finally:
                # close() is idempotent in SQLAlchemy
                try:
                    db.close()  # type: ignore[attr-defined]
                except Exception:
                    pass
                job_registry.complete(job_id, loop)

        loop.run_in_executor(None, _run)
        return job_id


__all__ = ["IndexingJobScheduler"]
