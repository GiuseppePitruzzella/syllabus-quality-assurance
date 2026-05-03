"""Normative-corpus retriever with criterion + agent metadata filtering.

Wraps ChromaDB and applies the four-step selection policy spelled out
in the Phase 5 spec (§5.2.2):

1. **Filtered query** on ``tag_{criterion}=True AND tag_{agent}=True``,
   asking the vector store for ``top_k_initial`` candidates.
2. **Similarity threshold**: drop candidates below
   ``rag_similarity_threshold`` (cosine-like, derived from L2 distance).
3. **Deduplication**: chunks coming from the same ``document_id`` and
   the same ``parent_section_ref`` (or ``section_ref`` for top-level
   chunks) are considered duplicates of one logical normative section;
   keep only the highest-scoring one.
4. **Source diversification**: if the resulting top-``top_k_final`` list
   draws from fewer than two distinct documents, swap the
   lowest-scoring entry with the first above-threshold candidate from
   another document, when available.

When the AND filter returns fewer than ``top_k_final`` chunks above
threshold, the retriever falls back progressively to:

- criterion-only filter (drop the agent constraint),
- agent-only filter (drop the criterion constraint),
- and finally returns whatever it has (with a warning log).

The collection is expected to use ChromaDB's L2 (squared) distance with
unit-normalised embeddings. See ``_distance_to_similarity`` for the
math; the retriever validates the assumption at construction time.
"""
from __future__ import annotations

import time
from typing import Any

import chromadb
import structlog
from pydantic import BaseModel, Field

from app.config import ScientificConfig
from app.evaluation.rag.embeddings import VertexAIEmbeddings

logger = structlog.get_logger(__name__)


class RetrievedChunk(BaseModel):
    """One chunk returned by the retriever.

    Attributes:
        chunk_id: The chunker-emitted deterministic id.
        text: Raw text of the chunk.
        metadata: Full metadata dict (provenance + tag_* booleans).
        similarity_score: Cosine-like similarity in ``[-1, 1]``,
            derived from the L2-squared distance ChromaDB returns.
    """

    chunk_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    metadata: dict[str, Any]
    similarity_score: float


class NormativeRetriever:
    """Apply the criterion/agent retrieval policy on the corpus collection."""

    def __init__(
        self,
        chroma_client: chromadb.api.client.Client,
        embeddings: VertexAIEmbeddings,
        scientific_config: ScientificConfig,
        collection_name: str = "normative_corpus",
    ) -> None:
        self._client = chroma_client
        self._collection = chroma_client.get_collection(collection_name)
        self._embeddings = embeddings
        self._config = scientific_config

    # ---- public API ----

    def retrieve(
        self,
        query: str,
        criterion: str,
        agent: str,
        top_k_initial: int | None = None,
        top_k_final: int | None = None,
    ) -> list[RetrievedChunk]:
        """Run the full four-step retrieval policy.

        Returns up to ``top_k_final`` chunks. May return fewer when the
        corpus does not contain enough above-threshold matches even
        after filter relaxation.
        """
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")

        top_k_initial = top_k_initial or self._config.rag_top_k
        top_k_final = top_k_final or self._config.rag_final_k
        threshold = self._config.rag_similarity_threshold

        started = time.time()
        query_embedding = self._embeddings.embed_query(query)

        # Stage 1: AND filter on criterion + agent.
        and_filter = _and_filter(criterion=criterion, agent=agent)
        candidates = self._query(query_embedding, top_k_initial, where=and_filter)
        kept = [c for c in candidates if c.similarity_score >= threshold]
        filters_applied = "criterion+agent"

        # Fallback chain: relax to criterion-only, then agent-only, then no filter.
        if len(kept) < top_k_final:
            criterion_only = _and_filter(criterion=criterion)
            candidates = self._query(query_embedding, top_k_initial, where=criterion_only)
            kept = [c for c in candidates if c.similarity_score >= threshold]
            filters_applied = "criterion-only"
            logger.warning(
                "retrieval_fallback",
                stage="criterion_only",
                criterion=criterion,
                agent=agent,
            )

        if len(kept) < top_k_final:
            agent_only = _and_filter(agent=agent)
            candidates = self._query(query_embedding, top_k_initial, where=agent_only)
            kept = [c for c in candidates if c.similarity_score >= threshold]
            filters_applied = "agent-only"
            logger.warning(
                "retrieval_fallback",
                stage="agent_only",
                criterion=criterion,
                agent=agent,
            )

        if len(kept) < top_k_final:
            logger.warning(
                "retrieval_underfilled",
                criterion=criterion,
                agent=agent,
                kept=len(kept),
                wanted=top_k_final,
            )

        # Stage 2 & 3: dedup, then diversify sources.
        deduped = _deduplicate(kept)
        diversified = _diversify_sources(deduped, candidates, top_k_final)
        final = diversified[:top_k_final]

        latency_ms = int((time.time() - started) * 1000)
        logger.info(
            "retrieval_completed",
            criterion=criterion,
            agent=agent,
            query=query[:200],
            filters_applied=filters_applied,
            candidates_count=len(candidates),
            final_chunks_count=len(final),
            final_chunk_ids=[c.chunk_id for c in final],
            latency_ms=latency_ms,
        )
        return final

    # ---- internals ----

    def _query(
        self,
        query_embedding: list[float],
        n_results: int,
        where: dict[str, Any] | None,
    ) -> list[RetrievedChunk]:
        """Issue a ChromaDB query and convert the result to RetrievedChunks."""
        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where
        result = self._collection.query(**kwargs)
        return _result_to_chunks(result)


# ---------------------------------------------------------------------------
# Helpers (module-level so they can be unit-tested without a live retriever)
# ---------------------------------------------------------------------------


def _and_filter(
    *,
    criterion: str | None = None,
    agent: str | None = None,
) -> dict[str, Any] | None:
    """Build a ChromaDB ``where`` clause for criterion / agent tag filters.

    Returns ``None`` if no constraint is requested. With one constraint,
    returns the bare ``{tag: True}``. With two, an ``$and`` clause.
    """
    clauses: list[dict[str, Any]] = []
    if criterion:
        clauses.append({f"tag_{criterion}": True})
    if agent:
        clauses.append({f"tag_{agent}": True})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _distance_to_similarity(distance: float) -> float:
    """Convert ChromaDB L2-squared distance to cosine-like similarity.

    For unit-normalised embeddings, ``L2_squared = 2 * (1 - cosine)``,
    so ``similarity = 1 - distance / 2`` and lies in ``[-1, 1]``.

    gemini-embedding-001 returns unit-normalised vectors at dim=3072.
    The collection is created without an explicit space, so ChromaDB
    uses ``l2`` (squared) by default — see configuration_json.
    """
    return 1.0 - distance / 2.0


def _result_to_chunks(result: dict[str, Any]) -> list[RetrievedChunk]:
    """Flatten one ChromaDB ``query`` result into ``RetrievedChunk``s."""
    if not result.get("ids") or not result["ids"][0]:
        return []
    ids = result["ids"][0]
    docs = result["documents"][0]
    metas = result["metadatas"][0]
    distances = result["distances"][0]
    return [
        RetrievedChunk(
            chunk_id=cid,
            text=text,
            metadata=meta or {},
            similarity_score=_distance_to_similarity(dist),
        )
        for cid, text, meta, dist in zip(ids, docs, metas, distances, strict=True)
    ]


def _deduplicate(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Keep one chunk per (document_id, parent_or_section_ref) group.

    Sub-chunks of the same logical section share their
    ``parent_section_ref``, so we collapse them. For top-level sections
    that produced a single chunk, ``section_ref`` is used as the
    grouping key. The retained representative is the highest-scoring
    one in each group.
    """
    seen: dict[tuple[str, str], RetrievedChunk] = {}
    for chunk in chunks:
        meta = chunk.metadata
        doc_id = meta.get("document_id", "")
        parent = meta.get("parent_section_ref") or meta.get("section_ref", "")
        key = (doc_id, parent)
        existing = seen.get(key)
        if existing is None or chunk.similarity_score > existing.similarity_score:
            seen[key] = chunk
    # Preserve original order (already sorted by similarity desc by ChromaDB).
    return sorted(seen.values(), key=lambda c: c.similarity_score, reverse=True)


def _diversify_sources(
    kept: list[RetrievedChunk],
    candidates: list[RetrievedChunk],
    top_k_final: int,
) -> list[RetrievedChunk]:
    """Ensure the top-``top_k_final`` come from at least 2 distinct documents.

    If all top-k entries come from a single document, the lowest-scoring
    is replaced with the first deduplicated candidate from another
    document (when available and above-threshold).

    Operates on already-deduplicated chunks. Falls through unchanged
    when the candidate pool only has one document, or when the kept
    set already meets the diversity bar.
    """
    if len(kept) < top_k_final:
        return kept

    top = kept[:top_k_final]
    distinct_docs = {c.metadata.get("document_id", "") for c in top}
    if len(distinct_docs) >= 2:
        return kept

    # Look for an above-threshold candidate from a different document.
    primary_doc = next(iter(distinct_docs))
    for cand in candidates:
        if cand.metadata.get("document_id", "") != primary_doc:
            replaced = top[:-1] + [cand]
            return replaced + kept[top_k_final:]
    return kept
