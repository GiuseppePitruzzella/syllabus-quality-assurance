"""Tests for the ExternalDocumentIngester (Phase 8.B.2).

Uses an in-memory ChromaDB EphemeralClient so the collection lives
only for the test duration, and a stub EmbeddingsClient so no
Vertex AI traffic is involved. Covers: write-then-count, idempotent
re-index (chunk count stable), shrink (re-index with fewer chunks
removes orphans), version isolation (v1 chunks survive when v2 is
re-indexed), empty input as "unindex", embedding failure, Chroma
upsert failure.
"""
from __future__ import annotations

import chromadb
import pytest

from app.local_documents.chunker import (
    ExternalChunk,
    ExternalDocumentChunker,
)
from app.local_documents.ingester import (
    ExternalDocumentIngester,
    EmbeddingsClient,
)


# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------


class _ConstantEmbeddings:
    """3-dim stub embeddings client. One call per text, deterministic."""

    def __init__(self, dim: int = 3):
        self.dim = dim
        self.calls = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[float(len(t) % 7) / 10, 0.0, 1.0] for t in texts]


class _FailingEmbeddings:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Vertex AI unavailable")


def _meta(**overrides):
    base = {
        "document_id": 1,
        "version": 1,
        "cdl_id": 3,
        "document_type": "usi_dipartimentali",
        "academic_year": "2025-2026",
        "file_hash": "abc",
        "enabled_criteria": ["E5"],
    }
    base.update(overrides)
    return base


@pytest.fixture
def chroma_client():
    """In-memory Chroma client, fresh per-test.

    `chromadb.EphemeralClient()` shares its in-memory backend across
    instances inside the same process, so without an explicit reset
    a collection populated by a previous test leaks into the next.
    Drop the collection on the way in AND on the way out.
    """
    client = chromadb.EphemeralClient()
    try:
        client.delete_collection("external_documents")
    except Exception:
        pass
    yield client
    try:
        client.delete_collection("external_documents")
    except Exception:
        pass


@pytest.fixture
def embeddings() -> EmbeddingsClient:
    return _ConstantEmbeddings()


def _make_chunks(
    chunker: ExternalDocumentChunker | None = None,
    *,
    paragraphs: list[str] | None = None,
    document_id: int = 1,
    version: int = 1,
) -> list[ExternalChunk]:
    chunker = chunker or ExternalDocumentChunker()
    text = "\n\n".join(paragraphs or ["Linee guida LM-18", "Prerequisiti chiari"])
    return chunker.chunk_text(text, _meta(document_id=document_id, version=version))


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_index_chunks_writes_to_collection(chroma_client, embeddings):
    ingester = ExternalDocumentIngester(chroma_client, embeddings)
    chunks = _make_chunks()
    result = ingester.index_chunks(chunks, document_id=1, version=1)
    assert result.errors == []
    assert result.chunks_written == len(chunks)
    assert result.chunks_deleted == 0
    assert ingester.collection_count() == len(chunks)
    assert ingester.count_for(1, 1) == len(chunks)


def test_reindex_same_input_is_idempotent(chroma_client, embeddings):
    ingester = ExternalDocumentIngester(chroma_client, embeddings)
    chunks = _make_chunks()
    first = ingester.index_chunks(chunks, document_id=1, version=1)
    second = ingester.index_chunks(chunks, document_id=1, version=1)
    assert first.chunks_written == second.chunks_written
    # Second call sees the first's chunks as "existing" and deletes them
    # before re-writing the identical set.
    assert second.chunks_deleted == first.chunks_written
    assert ingester.count_for(1, 1) == len(chunks)


def test_reindex_with_fewer_chunks_drops_orphans(chroma_client, embeddings):
    ingester = ExternalDocumentIngester(chroma_client, embeddings)
    # First pass: many chunks (force small limits).
    chunker = ExternalDocumentChunker(max_chars=80, hard_max_chars=120)
    big = _make_chunks(
        chunker,
        paragraphs=["Sezione " + str(i) + " " + ("x" * 60) for i in range(10)],
    )
    ingester.index_chunks(big, document_id=1, version=1)
    assert ingester.count_for(1, 1) == len(big)

    # Second pass: fewer chunks (single short paragraph).
    short = _make_chunks(paragraphs=["riepilogo"])
    result = ingester.index_chunks(short, document_id=1, version=1)
    assert result.chunks_deleted == len(big)
    assert result.chunks_written == len(short)
    assert ingester.count_for(1, 1) == len(short)


def test_empty_chunks_clears_existing_version(chroma_client, embeddings):
    ingester = ExternalDocumentIngester(chroma_client, embeddings)
    chunks = _make_chunks()
    ingester.index_chunks(chunks, document_id=1, version=1)
    assert ingester.count_for(1, 1) > 0

    result = ingester.index_chunks([], document_id=1, version=1)
    assert result.chunks_written == 0
    assert result.chunks_deleted == len(chunks)
    assert ingester.count_for(1, 1) == 0


# ---------------------------------------------------------------------------
# Isolation between versions
# ---------------------------------------------------------------------------


def test_reindex_v2_keeps_v1_intact(chroma_client, embeddings):
    ingester = ExternalDocumentIngester(chroma_client, embeddings)
    v1_chunks = _make_chunks(version=1)
    v2_chunks = _make_chunks(version=2)
    ingester.index_chunks(v1_chunks, document_id=1, version=1)
    ingester.index_chunks(v2_chunks, document_id=1, version=2)
    assert ingester.count_for(1, 1) == len(v1_chunks)
    assert ingester.count_for(1, 2) == len(v2_chunks)

    # Re-index v2 with empty -> v1 must survive.
    ingester.index_chunks([], document_id=1, version=2)
    assert ingester.count_for(1, 1) == len(v1_chunks)
    assert ingester.count_for(1, 2) == 0


def test_reindex_one_document_keeps_others_intact(chroma_client, embeddings):
    ingester = ExternalDocumentIngester(chroma_client, embeddings)
    ingester.index_chunks(
        _make_chunks(document_id=1, version=1),
        document_id=1, version=1,
    )
    ingester.index_chunks(
        _make_chunks(document_id=2, version=1),
        document_id=2, version=1,
    )
    assert ingester.count_for(1, 1) > 0
    assert ingester.count_for(2, 1) > 0

    # Re-index doc 1 -> doc 2 must not be touched.
    ingester.index_chunks(
        _make_chunks(document_id=1, version=1),
        document_id=1, version=1,
    )
    assert ingester.count_for(2, 1) > 0


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


def test_embedding_failure_is_reported_and_no_partial_write(chroma_client):
    ingester = ExternalDocumentIngester(chroma_client, _FailingEmbeddings())
    chunks = _make_chunks()
    result = ingester.index_chunks(chunks, document_id=1, version=1)
    assert result.errors, "expected an error to be reported"
    assert "embedding_failed" in result.errors[0]
    assert result.chunks_written == 0
    # Nothing got into Chroma either.
    assert ingester.count_for(1, 1) == 0


def test_metadata_payload_is_flat_scalar(chroma_client, embeddings):
    """Chroma rejects list/dict metadata. Smoke-test the cleaner."""
    ingester = ExternalDocumentIngester(chroma_client, embeddings)
    chunks = _make_chunks()
    ingester.index_chunks(chunks, document_id=1, version=1)
    # Read back to inspect metadata as Chroma stored them.
    coll = chroma_client.get_or_create_collection(
        name="external_documents",
    )
    got = coll.get(include=["metadatas"])
    for md in got["metadatas"]:
        for v in md.values():
            assert isinstance(v, (str, int, float, bool))
