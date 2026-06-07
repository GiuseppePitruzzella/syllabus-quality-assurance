"""ChromaDB ingester for external/local documents (Phase 8.B.2).

Distinct from the corpus ingester:

  - dedicated collection ``external_documents``;
  - no tagging-rules step (the tag_E* flags are decided at upload
    time via ``enabled_criteria`` and travel with the chunk
    metadata produced by :class:`ExternalDocumentChunker`);
  - idempotent per (document_id, version): a re-index ALWAYS deletes
    every chunk whose id starts with the
    ``external_{document_id}_v{version}__`` prefix before adding
    the new ones, so a re-extraction that produces fewer chunks
    can't leave orphans behind.

The Vertex AI embeddings client is injected; the ingester is
purely about glueing chunker -> embeddings -> Chroma. The async
job wrapping this (Phase 8.C) and the UI (Phase 8.D) consume the
same surface.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import chromadb
import structlog

from app.local_documents.chunker import (
    ExternalChunk,
    chunk_id_prefix,
)

logger = structlog.get_logger(__name__)

DEFAULT_COLLECTION_NAME = "external_documents"


class EmbeddingsClient(Protocol):
    """Subset of the Vertex AI embeddings interface we depend on.

    Injecting a Protocol lets unit tests pass a tiny stub instead
    of mocking Vertex AI's SDK.
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...


@dataclass
class IngestionResult:
    """Summary of one ingestion run for a single document version."""

    document_id: int
    version: int
    chunks_written: int = 0
    chunks_deleted: int = 0
    errors: list[str] = field(default_factory=list)


class ExternalDocumentIngester:
    """Push a set of chunks into the ``external_documents`` collection."""

    def __init__(
        self,
        chroma_client: chromadb.api.client.Client,
        embeddings: EmbeddingsClient,
        collection_name: str = DEFAULT_COLLECTION_NAME,
    ) -> None:
        self._client = chroma_client
        self._embeddings = embeddings
        self._collection_name = collection_name
        self._collection: Any | None = None

    # ------------------------------------------------------------------
    # Public surface
    # ------------------------------------------------------------------

    def index_chunks(
        self,
        chunks: list[ExternalChunk],
        document_id: int,
        version: int,
    ) -> IngestionResult:
        """Replace every chunk for (document_id, version) with ``chunks``.

        The delete-by-prefix step runs unconditionally so the
        invocation is idempotent: calling ``index_chunks`` twice
        with the same input yields the same final state.

        Empty ``chunks`` is a valid input: it removes any existing
        chunks for the (document, version) pair without writing
        anything new. Used to "unindex" a document that, after
        re-extraction, yields no usable text.
        """
        result = IngestionResult(document_id=document_id, version=version)
        collection = self._get_collection()

        # Step 1: delete every previous chunk for this (document, version).
        # Chroma's where-by-prefix isn't directly supported on `chunk_id`,
        # but we use deterministic IDs so we can filter on metadata.
        result.chunks_deleted = self._delete_existing(
            collection, document_id, version,
        )

        # Step 2: if nothing to write, we're done. The delete-only path
        # is intentional — see docstring.
        if not chunks:
            logger.info(
                "external_indexing_complete",
                document_id=document_id,
                version=version,
                written=0,
                deleted=result.chunks_deleted,
            )
            return result

        # Step 3: embed + write.
        try:
            vectors = self._embeddings.embed_documents([c.text for c in chunks])
        except Exception as exc:
            result.errors.append(f"embedding_failed: {exc}")
            logger.error(
                "external_embedding_failed",
                document_id=document_id,
                version=version,
                error=str(exc),
            )
            return result

        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [_clean_metadata(c.metadata) for c in chunks]
        try:
            collection.upsert(
                ids=ids,
                embeddings=vectors,
                documents=documents,
                metadatas=metadatas,
            )
        except Exception as exc:
            result.errors.append(f"chroma_upsert_failed: {exc}")
            logger.error(
                "external_upsert_failed",
                document_id=document_id,
                version=version,
                error=str(exc),
            )
            return result

        result.chunks_written = len(chunks)
        logger.info(
            "external_indexing_complete",
            document_id=document_id,
            version=version,
            written=result.chunks_written,
            deleted=result.chunks_deleted,
        )
        return result

    def delete_for(self, document_id: int, version: int) -> int:
        """Remove every chunk for a (document_id, version) pair.

        Used by ``DELETE /api/local-documents/{id}`` to keep the
        Chroma collection in sync with the registry: when the
        registry row goes away, the embedded chunks must go with
        it. Returns the number of chunks removed.

        Embedding-free: no Vertex AI call. Safe to invoke at boot /
        on every request without a GCP project configured.
        """
        return self._delete_existing(
            self._get_collection(), document_id, version,
        )

    def collection_count(self) -> int:
        """Number of chunks currently in the collection (diagnostics)."""
        return self._get_collection().count()

    def count_for(self, document_id: int, version: int) -> int:
        """Number of chunks present for a (document, version) pair."""
        collection = self._get_collection()
        try:
            res = collection.get(
                where=_match_where(document_id, version),
                include=[],
            )
        except Exception as exc:
            logger.warning(
                "external_count_failed",
                document_id=document_id,
                version=version,
                error=str(exc),
            )
            return 0
        ids = res.get("ids") or []
        return len(ids)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_collection(self) -> Any:
        if self._collection is not None:
            return self._collection
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
        )
        return self._collection

    def _delete_existing(
        self, collection: Any, document_id: int, version: int,
    ) -> int:
        """Delete every chunk for (document_id, version). Returns the count.

        We could rely on Chroma's `where=` clause exclusively, but we
        prefix-match too: a corrupted metadata row could otherwise
        pin orphans in place. The two paths are redundant by design.
        """
        prefix = chunk_id_prefix(document_id, version)
        try:
            existing = collection.get(
                where=_match_where(document_id, version),
                include=[],
            )
        except Exception as exc:
            logger.warning(
                "external_pre_delete_query_failed",
                document_id=document_id,
                version=version,
                error=str(exc),
            )
            return 0

        ids = list(existing.get("ids") or [])
        # Belt-and-braces: keep only the ids with the expected prefix.
        ids = [i for i in ids if i.startswith(prefix)]
        if not ids:
            return 0
        try:
            collection.delete(ids=ids)
        except Exception as exc:
            logger.warning(
                "external_delete_failed",
                document_id=document_id,
                version=version,
                error=str(exc),
            )
            return 0
        return len(ids)


def _match_where(document_id: int, version: int) -> dict[str, Any]:
    """Build the Chroma `where=` filter for a (document, version) pair."""
    return {
        "$and": [
            {"document_id": {"$eq": int(document_id)}},
            {"version": {"$eq": int(version)}},
        ]
    }


def _clean_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Coerce metadata to ChromaDB-compatible primitive types.

    The chunker already emits only scalars (str/int/bool); the guard
    is defensive against future regressions or hand-built test
    payloads. ``None`` becomes ``""``; any non-primitive value is
    dropped with a warning log instead of silently corrupting the
    stored payload.
    """
    cleaned: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if isinstance(value, (bool, int, float, str)):
            cleaned[key] = value
        elif value is None:
            cleaned[key] = ""
        else:
            logger.warning(
                "external_metadata_value_dropped",
                key=key,
                type=type(value).__name__,
            )
    return cleaned
