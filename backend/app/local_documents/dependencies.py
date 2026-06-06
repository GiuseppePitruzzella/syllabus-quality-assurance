"""FastAPI dependency providers for the local-document registry
(Phase 8.B.3).

The DELETE and PATCH endpoints need to talk to ChromaDB (delete the
chunks for a deleted row; reindex a row after enabled_criteria
changes). Wrapping the wiring in `Depends()` providers lets the
test suite swap in stubs without monkeypatching modules.

Singletons are created lazily on first use:

  - ``get_chroma_client``    — heavy, opens a persistent connection.
  - ``get_embeddings``       — heavier, calls ``vertexai.init`` and
                               fetches the model. Only the PATCH
                               auto-reindex path needs it; DELETE
                               does not.
  - ``get_external_ingester`` — depends on the client + embeddings.
  - ``get_indexing_service`` — depends on the active DB session +
                               the ingester.

The two heavy singletons live in the module globals; the FastAPI
dependency-overrides mechanism replaces the *resolver* in tests, so
the real Vertex / Chroma instances are never instantiated in unit
tests.
"""
from __future__ import annotations

import asyncio
from typing import Annotated

import chromadb
from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.evaluation.rag.embeddings import VertexAIEmbeddings
from app.local_documents.ingester import (
    EmbeddingsClient,
    ExternalDocumentIngester,
)
from app.local_documents.jobs import IndexingJobScheduler
from app.local_documents.service import LocalDocumentIndexingService

_chroma_client_singleton: chromadb.api.client.Client | None = None
_embeddings_singleton: VertexAIEmbeddings | None = None


def get_chroma_client() -> chromadb.api.client.Client:
    """Persistent Chroma client rooted at ``settings.chroma_persist_dir``.

    Created on first call, reused thereafter. The same client backs
    both the corpus collection (Phase 5) and the
    ``external_documents`` collection (Phase 8).
    """
    global _chroma_client_singleton
    if _chroma_client_singleton is None:
        _chroma_client_singleton = chromadb.PersistentClient(
            path=str(settings.chroma_persist_dir),
        )
    return _chroma_client_singleton


def get_embeddings() -> EmbeddingsClient:
    """Vertex AI embeddings client.

    Lazy: not instantiated until the first endpoint that needs it
    is hit (typically the PATCH auto-reindex). Endpoints that only
    need the chunk store (e.g. DELETE) should depend on
    :func:`get_external_ingester` and never end up triggering this
    provider.

    Raises:
        RuntimeError: if ``GCP_PROJECT_ID`` is not configured.
            FastAPI surfaces this as 500; the caller's logs will
            show the missing-env message.
    """
    global _embeddings_singleton
    if _embeddings_singleton is None:
        project, location = settings.require_vertex_ai_config()
        _embeddings_singleton = VertexAIEmbeddings(project, location)
    return _embeddings_singleton


def get_external_ingester(
    chroma: Annotated[chromadb.api.client.Client, Depends(get_chroma_client)],
) -> ExternalDocumentIngester:
    """Ingester wired to the live Chroma client.

    Note that this provider DOES NOT depend on
    :func:`get_embeddings`: the embeddings client is attached only
    inside :func:`get_indexing_service`. The DELETE endpoint
    consumes this provider directly and therefore never instantiates
    Vertex AI — it only needs ``delete_for()``, which is
    embedding-free.
    """
    # Embeddings are wired later by the service; for the ingester's
    # delete-only path we don't need a real embedder. Passing a
    # never-called stub keeps the type signature happy.
    return ExternalDocumentIngester(chroma, _NoEmbedder())


async def get_indexing_job_scheduler(
    chroma: Annotated[chromadb.api.client.Client, Depends(get_chroma_client)],
    embeddings: Annotated[EmbeddingsClient, Depends(get_embeddings)],
) -> IndexingJobScheduler:
    """Scheduler used by upload (auto-trigger), PATCH (auto-reindex),
    and POST /reindex. Wraps the sync service in a JobRegistry job
    and streams SSE progress on a dedicated job_id.

    The provider itself must be async so FastAPI resolves it on the
    request event loop rather than in the AnyIO worker thread used
    by sync endpoints. Capturing that loop here lets PATCH and
    POST /reindex schedule work safely via `call_soon_threadsafe`.
    """
    loop = asyncio.get_running_loop()
    return IndexingJobScheduler(chroma, embeddings, loop=loop)


def get_indexing_service(
    db: Annotated[Session, Depends(get_db)],
    chroma: Annotated[chromadb.api.client.Client, Depends(get_chroma_client)],
    embeddings: Annotated[EmbeddingsClient, Depends(get_embeddings)],
) -> LocalDocumentIndexingService:
    """Synchronous indexing service used by the PATCH auto-reindex.

    Builds a fresh ingester with the real embeddings client so the
    PATCH path runs the full pipeline. The DELETE path uses
    :func:`get_external_ingester` and never sees Vertex.
    """
    ingester = ExternalDocumentIngester(chroma, embeddings)
    return LocalDocumentIndexingService(db, ingester)


class _NoEmbedder:
    """Sentinel embedder used by the DELETE-only path.

    DELETE never calls ``embed_documents``, but the ingester
    constructor requires *some* object that satisfies
    :class:`EmbeddingsClient`. Raising on call makes a future
    accidental misuse loud rather than silently calling Vertex on
    a delete.
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError(
            "EmbeddingsClient was not provided to this ingester. "
            "Use `get_indexing_service` for paths that need to embed.",
        )
