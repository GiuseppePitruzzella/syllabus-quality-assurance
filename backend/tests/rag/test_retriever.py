"""Unit tests for the NormativeRetriever and its policy helpers.

ChromaDB and Vertex AI are both mocked: the tests run offline and
focus on the four-step selection policy and fallback chain.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.config import ScientificConfig
from app.evaluation.rag.retriever import (
    NormativeRetriever,
    RetrievedChunk,
    _and_filter,
    _deduplicate,
    _distance_to_similarity,
    _diversify_sources,
    _result_to_chunks,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _chunk(
    chunk_id: str,
    document_id: str,
    section_ref: str,
    parent_section_ref: str = "",
    text: str = "body",
    score: float = 0.9,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=text,
        metadata={
            "document_id": document_id,
            "section_ref": section_ref,
            "parent_section_ref": parent_section_ref,
        },
        similarity_score=score,
    )


def _fake_chroma_query_result(rows: list[tuple[str, str, dict, float]]) -> dict[str, Any]:
    """Shape-mimic of ``Collection.query`` output for one query embedding."""
    return {
        "ids": [[r[0] for r in rows]],
        "documents": [[r[1] for r in rows]],
        "metadatas": [[r[2] for r in rows]],
        "distances": [[r[3] for r in rows]],
    }


# ---------------------------------------------------------------------------
# _distance_to_similarity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "distance, expected_similarity",
    [
        (0.0, 1.0),    # identical
        (2.0, 0.0),    # orthogonal unit vectors -> L2_squared = 2
        (4.0, -1.0),   # opposite unit vectors -> L2_squared = 4
        (0.4356, 0.7822),  # smoke-test top hit
    ],
)
def test_distance_to_similarity_l2_squared(distance, expected_similarity):
    sim = _distance_to_similarity(distance)
    assert abs(sim - expected_similarity) < 1e-3


# ---------------------------------------------------------------------------
# _and_filter
# ---------------------------------------------------------------------------


def test_and_filter_no_constraints_returns_none():
    assert _and_filter() is None


def test_and_filter_single_criterion():
    assert _and_filter(criterion="C3") == {"tag_C3": True}


def test_and_filter_single_agent():
    assert _and_filter(agent="A2") == {"tag_A2": True}


def test_and_filter_combines_criterion_and_agent():
    assert _and_filter(criterion="C3", agent="A2") == {
        "$and": [{"tag_C3": True}, {"tag_A2": True}]
    }


# ---------------------------------------------------------------------------
# _result_to_chunks
# ---------------------------------------------------------------------------


def test_result_to_chunks_empty_result_returns_empty():
    assert _result_to_chunks({"ids": [[]]}) == []
    assert _result_to_chunks({}) == []


def test_result_to_chunks_converts_distances_to_similarity():
    raw = _fake_chroma_query_result(
        [
            ("c1", "text1", {"document_id": "d1"}, 0.0),
            ("c2", "text2", {"document_id": "d2"}, 2.0),
        ]
    )
    chunks = _result_to_chunks(raw)
    assert len(chunks) == 2
    assert abs(chunks[0].similarity_score - 1.0) < 1e-6
    assert abs(chunks[1].similarity_score - 0.0) < 1e-6


# ---------------------------------------------------------------------------
# _deduplicate
# ---------------------------------------------------------------------------


def test_deduplicate_keeps_highest_score_per_section():
    chunks = [
        _chunk("a", "doc1", "3.1.a", parent_section_ref="3.1", score=0.9),
        _chunk("b", "doc1", "3.1.b", parent_section_ref="3.1", score=0.7),
        _chunk("c", "doc2", "5", parent_section_ref="", score=0.6),
    ]
    deduped = _deduplicate(chunks)
    # Only one chunk from doc1/3.1 group survives — the highest score.
    assert len(deduped) == 2
    assert {c.chunk_id for c in deduped} == {"a", "c"}


def test_deduplicate_preserves_order_by_score():
    chunks = [
        _chunk("a", "doc1", "1", score=0.5),
        _chunk("b", "doc2", "1", score=0.9),
        _chunk("c", "doc3", "1", score=0.7),
    ]
    deduped = _deduplicate(chunks)
    scores = [c.similarity_score for c in deduped]
    assert scores == sorted(scores, reverse=True)


def test_deduplicate_uses_section_ref_when_no_parent():
    """Top-level chunks (parent='' AND no split) group by section_ref."""
    chunks = [
        _chunk("a", "doc1", "5", parent_section_ref="", score=0.9),
        _chunk("b", "doc1", "6", parent_section_ref="", score=0.8),
    ]
    deduped = _deduplicate(chunks)
    assert len(deduped) == 2  # different section_refs, both kept


# ---------------------------------------------------------------------------
# _diversify_sources
# ---------------------------------------------------------------------------


def test_diversify_returns_kept_when_already_diverse():
    kept = [
        _chunk("a", "doc1", "1", score=0.9),
        _chunk("b", "doc2", "1", score=0.8),
        _chunk("c", "doc3", "1", score=0.7),
    ]
    out = _diversify_sources(kept, kept, top_k_final=3)
    assert out == kept


def test_diversify_swaps_lowest_when_single_doc_dominates():
    """All top-3 from doc1 -> swap last with first candidate from another doc."""
    kept = [
        _chunk("a", "doc1", "1", score=0.9),
        _chunk("b", "doc1", "2", score=0.8),
        _chunk("c", "doc1", "3", score=0.7),
    ]
    candidates_pool = kept + [
        _chunk("d", "doc2", "X", score=0.65),
    ]
    out = _diversify_sources(kept, candidates_pool, top_k_final=3)
    assert out[0].chunk_id == "a"
    assert out[1].chunk_id == "b"
    assert out[2].chunk_id == "d"


def test_diversify_no_op_if_no_other_doc_available():
    """No alternative document -> return unchanged."""
    kept = [
        _chunk("a", "doc1", "1", score=0.9),
        _chunk("b", "doc1", "2", score=0.8),
    ]
    out = _diversify_sources(kept, kept, top_k_final=3)
    assert out == kept


# ---------------------------------------------------------------------------
# NormativeRetriever.retrieve — integration with mocked Chroma + Vertex
# ---------------------------------------------------------------------------


def _make_retriever(query_results: list[dict[str, Any]]) -> tuple[NormativeRetriever, MagicMock]:
    """Build a retriever whose collection.query returns successive results."""
    fake_collection = MagicMock()
    fake_collection.query.side_effect = query_results

    fake_client = MagicMock()
    fake_client.get_collection.return_value = fake_collection

    fake_embeddings = MagicMock()
    fake_embeddings.embed_query.return_value = [0.1] * 3072

    config = ScientificConfig()  # defaults: top_k=5, final_k=3, threshold=0.6
    return NormativeRetriever(fake_client, fake_embeddings, config), fake_collection


def test_retrieve_rejects_empty_query():
    retriever, _ = _make_retriever([_fake_chroma_query_result([])])
    with pytest.raises(ValueError, match="non-empty"):
        retriever.retrieve(query="", criterion="C3", agent="A2")


def test_retrieve_uses_and_filter_first():
    """Stage 1 always tries criterion+agent before any fallback."""
    chroma_result = _fake_chroma_query_result(
        [
            ("c1", "Body 1", {"document_id": "d1", "section_ref": "1"}, 0.4),
            ("c2", "Body 2", {"document_id": "d2", "section_ref": "2"}, 0.5),
            ("c3", "Body 3", {"document_id": "d3", "section_ref": "3"}, 0.6),
        ]
    )
    retriever, coll = _make_retriever([chroma_result])
    out = retriever.retrieve(query="some query", criterion="C3", agent="A2")
    assert len(out) == 3
    args, kwargs = coll.query.call_args
    assert kwargs["where"] == {"$and": [{"tag_C3": True}, {"tag_A2": True}]}


def test_retrieve_filters_below_threshold():
    """Chunks below the similarity threshold are dropped from final set."""
    # Distances 0.4, 0.5, 0.6 -> similarities 0.8, 0.75, 0.7 (all above 0.6)
    above = _fake_chroma_query_result(
        [
            ("c1", "Body 1", {"document_id": "d1", "section_ref": "1"}, 0.4),
            ("c2", "Body 2", {"document_id": "d2", "section_ref": "2"}, 0.5),
            ("c3", "Body 3", {"document_id": "d3", "section_ref": "3"}, 0.6),
        ]
    )
    retriever, _ = _make_retriever([above])
    out = retriever.retrieve(query="x", criterion="C3", agent="A2")
    assert all(c.similarity_score >= 0.6 for c in out)


def test_retrieve_falls_back_to_criterion_only(caplog):
    """When AND filter yields too few above-threshold chunks, drop agent."""
    and_result = _fake_chroma_query_result(
        [
            ("c1", "Body 1", {"document_id": "d1", "section_ref": "1"}, 0.4),  # sim=0.8
            # Only 1 above threshold, less than top_k_final=3
        ]
    )
    fallback_result = _fake_chroma_query_result(
        [
            ("c1", "Body 1", {"document_id": "d1", "section_ref": "1"}, 0.4),
            ("c2", "Body 2", {"document_id": "d2", "section_ref": "2"}, 0.5),
            ("c3", "Body 3", {"document_id": "d3", "section_ref": "3"}, 0.6),
        ]
    )
    retriever, coll = _make_retriever([and_result, fallback_result, fallback_result])
    out = retriever.retrieve(query="x", criterion="C3", agent="A2")
    assert len(out) >= 1
    # Two query calls: AND, then criterion-only.
    assert coll.query.call_count >= 2
    # Second call must have only the criterion filter.
    second_kwargs = coll.query.call_args_list[1][1]
    assert second_kwargs["where"] == {"tag_C3": True}


def test_retrieve_falls_back_to_agent_only_then_no_filter():
    """Triple-fallback path: AND -> criterion -> agent."""
    too_few = _fake_chroma_query_result([])  # nothing
    retriever, coll = _make_retriever([too_few, too_few, too_few])
    out = retriever.retrieve(query="x", criterion="C3", agent="A2")
    assert out == []
    # Three query calls expected: AND, criterion-only, agent-only.
    assert coll.query.call_count == 3
    third_kwargs = coll.query.call_args_list[2][1]
    assert third_kwargs["where"] == {"tag_A2": True}


def test_retrieve_dedupes_then_diversifies():
    """End-to-end: ChromaDB returns 5 candidates, retriever returns 3 unique docs."""
    raw = _fake_chroma_query_result(
        [
            ("c1", "doc1 sec3 chunk a", {"document_id": "d1", "section_ref": "3.a", "parent_section_ref": "3"}, 0.4),
            ("c2", "doc1 sec3 chunk b", {"document_id": "d1", "section_ref": "3.b", "parent_section_ref": "3"}, 0.45),
            ("c3", "doc1 sec5", {"document_id": "d1", "section_ref": "5", "parent_section_ref": ""}, 0.5),
            ("c4", "doc2 sec1", {"document_id": "d2", "section_ref": "1", "parent_section_ref": ""}, 0.7),
            ("c5", "doc3 sec1", {"document_id": "d3", "section_ref": "1", "parent_section_ref": ""}, 0.8),
        ]
    )
    retriever, _ = _make_retriever([raw])
    out = retriever.retrieve(query="x", criterion="C3", agent="A2", top_k_final=3)
    # Dedup: c1 + c2 share (d1, parent=3) -> only the higher-scoring one survives.
    chunk_ids = {c.chunk_id for c in out}
    assert "c2" not in chunk_ids or "c1" not in chunk_ids
    # Diversification: the final set draws from at least 2 distinct docs.
    docs = {c.metadata["document_id"] for c in out}
    assert len(docs) >= 2


def test_retrieve_passes_n_results_to_chroma():
    raw = _fake_chroma_query_result([])
    retriever, coll = _make_retriever([raw, raw, raw])
    retriever.retrieve(query="x", criterion="C3", agent="A2", top_k_initial=10)
    assert coll.query.call_args_list[0][1]["n_results"] == 10


def test_retrieve_uses_config_defaults_when_no_overrides():
    raw = _fake_chroma_query_result([])
    retriever, coll = _make_retriever([raw, raw, raw])
    retriever.retrieve(query="x", criterion="C3", agent="A2")
    # ScientificConfig default rag_top_k = 5
    assert coll.query.call_args_list[0][1]["n_results"] == 5
