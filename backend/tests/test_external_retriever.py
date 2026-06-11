"""Tests for the ExternalDocumentRetriever (Phase 9.C.2).

Verifies the strict filter contract: every retrieval call hits
the ChromaDB collection with the exact `cdl_id + tag_E* +
document_id` triple, no relaxation chain, no leak when the
filter would underfill. The collection itself is replaced by a
spy / fake that records the call args and returns canned chunks,
so the tests run offline and incur no Vertex / Chroma cost.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config import ScientificConfig
from app.evaluation.rag.external_retriever import (
    ExternalDocumentRetriever,
    _distance_to_similarity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scientific(**overrides) -> ScientificConfig:
    base = {
        "llm_model": "gemini-2.5-flash",
        "embedding_model": "gemini-embedding-001",
        "embedding_output_dimensionality": 3072,
        "llm_temperature": 0.1,
        "llm_max_output_tokens": 8192,
        "rag_top_k": 5,
        "rag_final_k": 3,
        "rag_similarity_threshold": 0.6,
    }
    base.update(overrides)
    return ScientificConfig(**base)


def _fake_chroma_result(
    *,
    n: int = 3,
    distances: list[float] | None = None,
    metas: list[dict] | None = None,
    ids: list[str] | None = None,
):
    """Mimic the shape of a ChromaDB `collection.query(...)` result."""
    distances = distances or [0.4, 0.6, 0.8][:n]
    metas = metas or [
        {"document_id": 7, "document_type": "sua_cds", "version": 2}
        for _ in range(n)
    ]
    ids = ids or [f"external_7_v2__chunk_{i:04d}" for i in range(n)]
    docs = [f"chunk text {i}" for i in range(n)]
    return {
        "ids": [ids],
        "documents": [docs],
        "metadatas": [metas],
        "distances": [distances],
    }


def _make_retriever(
    *,
    collection_result=None,
    collection_missing: bool = False,
    embeddings_dim: int = 3072,
):
    """Build an ExternalDocumentRetriever with fake Chroma + embeddings."""
    fake_collection = MagicMock()
    if collection_result is not None:
        fake_collection.query.return_value = collection_result
    else:
        fake_collection.query.return_value = _fake_chroma_result(n=3)

    fake_client = MagicMock()
    if collection_missing:
        fake_client.get_collection.side_effect = ValueError("no such collection")
    else:
        fake_client.get_collection.return_value = fake_collection

    fake_embeddings = MagicMock()
    fake_embeddings.embed_query.return_value = [0.1] * embeddings_dim

    return (
        ExternalDocumentRetriever(
            fake_client, fake_embeddings, _scientific(),
        ),
        fake_client,
        fake_collection,
        fake_embeddings,
    )


# ---------------------------------------------------------------------------
# Filter rigidity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("criterion", ["E1", "E2", "E3", "E5"])
def test_retrieve_for_uses_strict_triple_filter(criterion):
    retriever, _, collection, _ = _make_retriever()
    retriever.retrieve_for(
        criterion=criterion,
        cdl_id=3,
        local_document_id=7,
        query="qualunque",
    )
    args, kwargs = collection.query.call_args
    where = kwargs["where"]
    # Expected shape: $and[ cdl_id, tag_E*, document_id ]
    assert "$and" in where
    clauses = where["$and"]
    assert {"cdl_id": {"$eq": 3}} in clauses
    assert {f"tag_{criterion}": {"$eq": True}} in clauses
    assert {"document_id": {"$eq": 7}} in clauses


def test_retrieve_e4_is_refused():
    """E4 is served by the syllabus itself; the retriever must
    refuse to be called for it (defensive)."""
    retriever, _, _, _ = _make_retriever()
    with pytest.raises(ValueError, match="E4"):
        retriever.retrieve_for(
            criterion="E4",
            cdl_id=3,
            local_document_id=7,
            query="qualunque",
        )


def test_retrieve_rejects_empty_query():
    retriever, _, _, _ = _make_retriever()
    with pytest.raises(ValueError, match="non-empty"):
        retriever.retrieve_for(
            criterion="E1",
            cdl_id=3,
            local_document_id=7,
            query="",
        )
    with pytest.raises(ValueError, match="non-empty"):
        retriever.retrieve_for(
            criterion="E1",
            cdl_id=3,
            local_document_id=7,
            query="   \n\t ",
        )


def test_retrieve_rejects_unknown_criterion():
    retriever, _, _, _ = _make_retriever()
    with pytest.raises(ValueError, match="unknown criterion"):
        retriever.retrieve_for(
            criterion="C7",  # core code; never accepted here
            cdl_id=3,
            local_document_id=7,
            query="x",
        )


def test_no_fallback_when_filter_underfills():
    """If the filtered query returns fewer than top_k_final
    above-threshold chunks, the retriever logs and returns what
    it has — it must NOT relax the filter (no second query call)."""
    only_one_above = _fake_chroma_result(
        n=2, distances=[0.4, 1.6],  # second one below threshold
    )
    retriever, _, collection, _ = _make_retriever(
        collection_result=only_one_above,
    )
    out = retriever.retrieve_for(
        criterion="E1",
        cdl_id=3,
        local_document_id=7,
        query="x",
    )
    assert len(out) == 1  # below-threshold one dropped
    # Single query call only — no fallback round-trip.
    assert collection.query.call_count == 1


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


def test_retrieved_chunks_lift_registry_fields_from_metadata():
    metas = [
        {"document_id": 7, "document_type": "sua_cds", "version": 2,
         "chunk_order": 0, "tag_E1": True},
    ]
    result = _fake_chroma_result(n=1, metas=metas)
    retriever, _, _, _ = _make_retriever(collection_result=result)
    out = retriever.retrieve_for(
        criterion="E1",
        cdl_id=3,
        local_document_id=7,
        query="x",
    )
    assert len(out) == 1
    chunk = out[0]
    assert chunk.local_document_id == 7
    assert chunk.document_type == "sua_cds"
    assert chunk.document_version == 2
    assert chunk.similarity_score > 0  # 0.4 -> 0.8


def test_similarity_threshold_drops_below_threshold_chunks():
    distances = [0.4, 0.6, 1.4, 1.8]  # last two below threshold 0.6
    result = _fake_chroma_result(n=4, distances=distances)
    retriever, _, _, _ = _make_retriever(collection_result=result)
    out = retriever.retrieve_for(
        criterion="E1",
        cdl_id=3,
        local_document_id=7,
        query="x",
    )
    # threshold=0.6 -> chunks with d<=0.8 are kept.
    assert len(out) == 2


def test_top_k_final_caps_output():
    result = _fake_chroma_result(n=5, distances=[0.1, 0.2, 0.3, 0.4, 0.5])
    retriever, _, _, _ = _make_retriever(collection_result=result)
    out = retriever.retrieve_for(
        criterion="E1",
        cdl_id=3,
        local_document_id=7,
        query="x",
    )
    # scientific config: rag_final_k=3
    assert len(out) == 3


# ---------------------------------------------------------------------------
# Collection missing / query error
# ---------------------------------------------------------------------------


def test_retrieve_returns_empty_when_collection_missing():
    """If the registry has never been ingested, the
    `external_documents` collection doesn't exist yet.
    The retriever must return [] without raising."""
    retriever, _, _, embeddings = _make_retriever(collection_missing=True)
    out = retriever.retrieve_for(
        criterion="E1",
        cdl_id=3,
        local_document_id=7,
        query="x",
    )
    assert out == []
    # No embedding call wasted: the collection-missing branch
    # short-circuits before embedding.
    embeddings.embed_query.assert_not_called()


def test_retrieve_returns_empty_when_query_raises():
    retriever, _, collection, _ = _make_retriever()
    collection.query.side_effect = RuntimeError("chroma down")
    out = retriever.retrieve_for(
        criterion="E1",
        cdl_id=3,
        local_document_id=7,
        query="x",
    )
    assert out == []


# ---------------------------------------------------------------------------
# Similarity conversion sanity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "distance, expected",
    [(0.0, 1.0), (0.4, 0.8), (1.0, 0.5), (2.0, 0.0)],
)
def test_distance_to_similarity_table(distance, expected):
    assert _distance_to_similarity(distance) == pytest.approx(expected)
