"""Retriever for the ``external_documents`` collection (Phase 9.C.2).

Distinct from ``NormativeRetriever``. The two paths are kept
deliberately separate because their requirements diverge in three
fundamental ways:

  - **Filter rigidity.** The normative retriever has a fallback
    chain (criterion+agent -> criterion-only -> agent-only -> no
    filter) so it can answer queries even when the corpus has
    sparse coverage. The external retriever MUST not relax filters
    under any condition: a leak from a different ``cdl_id``, from
    a different ``tag_E*`` or from a stale ``document_id`` would
    silently break the document-to-criterion contract from 9.A.

  - **Scope per call.** Each call targets exactly one
    ``(cdl_id, criterion, document_id)`` triple. The A5 coordinator
    is responsible for issuing one call per resolved document —
    so a multi-document E5 query yields N independent retrieval
    rounds, sharing the embedding only.

  - **No dedup / diversification.** The corpus retriever
    deduplicates across logical sections and diversifies across
    distinct documents because the normative corpus has many
    sources per criterion. The external retriever runs against a
    single document at a time, so neither step applies.

The result type is :class:`ExternalRetrievedChunk` rather than
``RetrievedChunk`` to keep the two paths type-checked independently
and to surface the registry-side ``local_document_id`` /
``document_version`` as first-class fields rather than dict
lookups buried inside ``metadata``.
"""
from __future__ import annotations

import time
from typing import Any

import chromadb
import structlog
from pydantic import BaseModel, Field

from app.config import ScientificConfig
from app.evaluation.agents.external_schemas import ExtendedCriterionCode
from app.evaluation.rag.embeddings import VertexAIEmbeddings
from app.local_documents.ingester import (
    DEFAULT_COLLECTION_NAME as EXTERNAL_COLLECTION,
)

logger = structlog.get_logger(__name__)


class ExternalRetrievedChunk(BaseModel):
    """One chunk returned by the external retriever."""

    chunk_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    metadata: dict[str, Any]
    similarity_score: float
    # Lifted from metadata for ergonomics — A5 handlers will use
    # these to build evidences and to fill ExternalRetrievedChunkRef.
    local_document_id: int
    document_type: str
    document_version: int


class ExternalDocumentRetriever:
    """Apply the strict ``(cdl_id, tag_E*, document_id)`` filter on the
    ``external_documents`` collection. No fallback, no leak.

    The collection is created on first ingest by
    :class:`ExternalDocumentIngester`. If it does not exist yet
    (registry empty), every retrieval returns an empty list —
    callers should treat that as "no evidence available", which
    typically translates to a technical NA at the judgment layer.
    """

    def __init__(
        self,
        chroma_client: chromadb.api.client.Client,
        embeddings: VertexAIEmbeddings,
        scientific_config: ScientificConfig,
        collection_name: str = EXTERNAL_COLLECTION,
    ) -> None:
        self._client = chroma_client
        self._embeddings = embeddings
        self._config = scientific_config
        self._collection_name = collection_name
        # Lazily resolved on first retrieval so an empty registry
        # doesn't abort the whole evaluation graph at construction.
        self._collection: Any | None = None

    # ---- public API ----

    def retrieve_for(
        self,
        *,
        criterion: ExtendedCriterionCode,
        cdl_id: int,
        local_document_id: int,
        query: str,
        top_k_initial: int | None = None,
        top_k_final: int | None = None,
    ) -> list[ExternalRetrievedChunk]:
        """Retrieve chunks for a single criterion / single document.

        Filter is rigid: ``cdl_id == cdl_id`` AND
        ``tag_{criterion} == True`` AND
        ``document_id == local_document_id``. No relaxation.

        Above-threshold filter applies as on the corpus path.
        Underfill is logged as a warning but does NOT trigger a
        fallback — the caller decides whether an underfilled set
        is enough to write a judgment.

        For E5 multi-document scenarios, the A5 coordinator calls
        this method once per resolved document. The embedding is
        an LLM call that costs money; if the coordinator runs
        multiple retrievals for the same query, it should embed
        the query ONCE and pass it as ``query_embedding`` once we
        introduce that overload — not in 9.C.2 (the embed_query
        call here is already amortised: the same query text on
        the same client is a cache-friendly call).
        """
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        if criterion not in ("E1", "E2", "E3", "E4", "E5"):
            raise ValueError(f"unknown criterion: {criterion!r}")
        if criterion == "E4":
            # Defensive: E4 is served by the syllabus itself; the A5
            # E4 handler must never reach the retriever.
            raise ValueError(
                "E4 is served by the syllabus's own *_en fields, "
                "not by the registry. The handler should never call the retriever.",
            )

        top_k_initial = top_k_initial or self._config.rag_top_k
        top_k_final = top_k_final or self._config.rag_final_k
        threshold = self._config.rag_similarity_threshold

        collection = self._get_collection()
        if collection is None:
            logger.warning(
                "external_retrieval_collection_missing",
                criterion=criterion,
                cdl_id=cdl_id,
                local_document_id=local_document_id,
            )
            return []

        started = time.time()
        query_embedding = self._embeddings.embed_query(query)

        where = {
            "$and": [
                {"cdl_id": {"$eq": int(cdl_id)}},
                {f"tag_{criterion}": {"$eq": True}},
                {"document_id": {"$eq": int(local_document_id)}},
            ]
        }
        try:
            result = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k_initial,
                where=where,
            )
        except Exception as exc:
            logger.warning(
                "external_retrieval_query_failed",
                criterion=criterion,
                cdl_id=cdl_id,
                local_document_id=local_document_id,
                error=str(exc),
            )
            return []

        candidates = _result_to_external_chunks(
            result, default_doc_id=local_document_id,
        )
        kept = [c for c in candidates if c.similarity_score >= threshold]

        if len(kept) < top_k_final:
            # NO fallback chain. We log and return what we have.
            logger.warning(
                "external_retrieval_underfilled",
                criterion=criterion,
                cdl_id=cdl_id,
                local_document_id=local_document_id,
                kept=len(kept),
                wanted=top_k_final,
            )

        final = kept[:top_k_final]

        latency_ms = int((time.time() - started) * 1000)
        logger.info(
            "external_retrieval_completed",
            criterion=criterion,
            cdl_id=cdl_id,
            local_document_id=local_document_id,
            query=query[:200],
            candidates_count=len(candidates),
            final_chunks_count=len(final),
            final_chunk_ids=[c.chunk_id for c in final],
            latency_ms=latency_ms,
        )
        return final

    # ---- internals ----

    def _get_collection(self) -> Any | None:
        if self._collection is not None:
            return self._collection
        try:
            self._collection = self._client.get_collection(self._collection_name)
        except Exception:
            # Collection doesn't exist yet (no document has ever
            # been ingested). Return None so retrievals are no-ops.
            return None
        return self._collection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _distance_to_similarity(distance: float) -> float:
    """L2-squared -> cosine-like, same conversion as the corpus retriever."""
    return 1.0 - distance / 2.0


def _result_to_external_chunks(
    result: dict[str, Any], *, default_doc_id: int,
) -> list[ExternalRetrievedChunk]:
    """Flatten a ChromaDB ``query`` result into ExternalRetrievedChunks."""
    if not result.get("ids") or not result["ids"][0]:
        return []
    ids = result["ids"][0]
    docs = result["documents"][0]
    metas = result["metadatas"][0]
    distances = result["distances"][0]
    out: list[ExternalRetrievedChunk] = []
    for cid, text, meta, dist in zip(ids, docs, metas, distances, strict=True):
        meta = meta or {}
        out.append(
            ExternalRetrievedChunk(
                chunk_id=cid,
                text=text,
                metadata=meta,
                similarity_score=_distance_to_similarity(dist),
                local_document_id=int(meta.get("document_id", default_doc_id)),
                document_type=str(meta.get("document_type", "")),
                document_version=int(meta.get("version", 0)),
            )
        )
    return out


__all__ = [
    "ExternalDocumentRetriever",
    "ExternalRetrievedChunk",
]
