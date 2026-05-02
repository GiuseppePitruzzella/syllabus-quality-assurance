"""Unit tests for CorpusIngester.

Tests run with mocked Vertex AI embeddings and a real (but throwaway)
ChromaDB on a tmp_path. ChromaDB persistence is fast enough that we
don't need to mock it — running it for real also exercises metadata
type validation.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from app.evaluation.rag.chunker import MarkdownChunker
from app.evaluation.rag.ingester import (
    CorpusIngester,
    IngestionReport,
    _clean_metadata,
)
from app.evaluation.rag.tagging_rules import TaggingRules


def _make_rules() -> TaggingRules:
    return TaggingRules(
        {
            "documents": {
                "doc1": {
                    "document_title": "Doc One",
                    "document_version": "1.0",
                    "source_type": "linea_guida_ateneo",
                    "document_priority": 2,
                    "section_tags": {
                        "1": {"criterion_tags": ["C1"], "agent_tags": ["A1"]},
                        "2": {"criterion_tags": ["C3"], "agent_tags": ["A2"]},
                    },
                },
                "doc2": {
                    "document_title": "Doc Two",
                    "document_version": "1.0",
                    "source_type": "linea_guida_ateneo",
                    "document_priority": 2,
                    "section_tags": {
                        "1": {"criterion_tags": ["C5"], "agent_tags": ["A1"]},
                    },
                },
            }
        }
    )


def _write_corpus(corpus_dir: Path) -> None:
    (corpus_dir / "doc1.md").write_text(
        "# Title\n\n## 1. Section One\n\nFirst section body.\n\n## 2. Section Two\n\nSecond.\n",
        encoding="utf-8",
    )
    (corpus_dir / "doc2.md").write_text(
        "# Title 2\n\n## 1. Solo\n\nBody of the only section.\n",
        encoding="utf-8",
    )


def _fake_embeddings(dim: int = 8) -> MagicMock:
    """A minimal stand-in that returns deterministic dummy vectors."""
    fake = MagicMock()
    fake.embed_documents.side_effect = lambda texts: [[0.1] * dim for _ in texts]
    fake.embed_query.side_effect = lambda text: [0.2] * dim
    fake.output_dimensionality = dim
    fake.model_name = "fake-model"
    return fake


# ---------------------------------------------------------------------------
# _clean_metadata
# ---------------------------------------------------------------------------


def test_clean_metadata_passes_primitives():
    cleaned = _clean_metadata({"s": "x", "i": 1, "f": 1.5, "b": True})
    assert cleaned == {"s": "x", "i": 1, "f": 1.5, "b": True}


def test_clean_metadata_replaces_none_with_empty_string():
    cleaned = _clean_metadata({"k": None})
    assert cleaned == {"k": ""}


def test_clean_metadata_drops_non_primitives():
    cleaned = _clean_metadata({"a": 1, "b": [1, 2, 3], "c": {"nested": True}})
    assert cleaned == {"a": 1}


# ---------------------------------------------------------------------------
# produce_chunks: chunker + tagger pipeline (no embeddings, no chromadb)
# ---------------------------------------------------------------------------


def test_produce_chunks_runs_chunker_and_tagger(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    _write_corpus(corpus)

    ingester = CorpusIngester(
        corpus_dir=corpus,
        chroma_persist_dir=tmp_path / "chroma",
        rules=_make_rules(),
        embeddings=_fake_embeddings(),
        chunker=MarkdownChunker(),
    )
    chunks = ingester.produce_chunks()

    # 2 sections from doc1 + 1 section from doc2 = 3 chunks total.
    assert len(chunks) == 3
    by_doc = {c.metadata["document_id"]: [] for c in chunks}
    for c in chunks:
        by_doc[c.metadata["document_id"]].append(c)
    assert len(by_doc["doc1"]) == 2
    assert len(by_doc["doc2"]) == 1

    # doc1 §1 has C1/A1, §2 has C3/A2.
    doc1_section1 = next(c for c in by_doc["doc1"] if c.metadata["section_ref"] == "1")
    assert doc1_section1.metadata["tag_C1"] is True
    assert doc1_section1.metadata["tag_A1"] is True
    assert doc1_section1.metadata["tag_C3"] is False


# ---------------------------------------------------------------------------
# ingest_all: full pipeline against real ChromaDB
# ---------------------------------------------------------------------------


def test_ingest_all_writes_to_chroma(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    _write_corpus(corpus)

    embeddings = _fake_embeddings()
    ingester = CorpusIngester(
        corpus_dir=corpus,
        chroma_persist_dir=tmp_path / "chroma",
        rules=_make_rules(),
        embeddings=embeddings,
    )

    report = ingester.ingest_all()
    assert isinstance(report, IngestionReport)
    assert report.total_chunks == 3
    assert report.ingested_chunks == 3
    assert report.skipped_chunks == 0
    assert report.errors == []
    assert ingester.collection_count() == 3
    # 3 chunks => 3 embedding API calls (gemini-embedding-001 batch=1).
    embeddings.embed_documents.assert_called_once()
    args, _ = embeddings.embed_documents.call_args
    assert len(args[0]) == 3


def test_ingest_all_is_idempotent(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    _write_corpus(corpus)

    embeddings = _fake_embeddings()
    ingester = CorpusIngester(
        corpus_dir=corpus,
        chroma_persist_dir=tmp_path / "chroma",
        rules=_make_rules(),
        embeddings=embeddings,
    )

    first = ingester.ingest_all()
    assert first.ingested_chunks == 3

    # Reset the embedding mock to count second-pass calls.
    embeddings.embed_documents.reset_mock()

    second = ingester.ingest_all()
    assert second.total_chunks == 3
    assert second.ingested_chunks == 0
    assert second.skipped_chunks == 3
    embeddings.embed_documents.assert_not_called()


def test_ingest_all_force_reingest_calls_upsert(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    _write_corpus(corpus)

    embeddings = _fake_embeddings()
    ingester = CorpusIngester(
        corpus_dir=corpus,
        chroma_persist_dir=tmp_path / "chroma",
        rules=_make_rules(),
        embeddings=embeddings,
    )
    ingester.ingest_all()
    embeddings.embed_documents.reset_mock()

    forced = ingester.ingest_all(force_reingest=True)
    assert forced.ingested_chunks == 3
    assert forced.skipped_chunks == 0
    # Force re-embeds every chunk
    embeddings.embed_documents.assert_called_once()


def test_ingest_all_records_per_criterion_distribution(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    _write_corpus(corpus)
    ingester = CorpusIngester(
        corpus_dir=corpus,
        chroma_persist_dir=tmp_path / "chroma",
        rules=_make_rules(),
        embeddings=_fake_embeddings(),
    )
    report = ingester.ingest_all()
    # doc1 §1 -> C1, doc1 §2 -> C3, doc2 §1 -> C5
    assert report.chunks_by_criterion["C1"] == 1
    assert report.chunks_by_criterion["C3"] == 1
    assert report.chunks_by_criterion["C5"] == 1
    assert report.chunks_by_criterion["C2"] == 0  # not used in test rules
    # No untagged chunks: every test section has a rule
    assert report.untagged_chunks == 0


def test_ingest_all_empty_corpus_returns_empty_report(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    embeddings = _fake_embeddings()
    ingester = CorpusIngester(
        corpus_dir=corpus,
        chroma_persist_dir=tmp_path / "chroma",
        rules=_make_rules(),
        embeddings=embeddings,
    )
    report = ingester.ingest_all()
    assert report.total_chunks == 0
    assert report.ingested_chunks == 0
    embeddings.embed_documents.assert_not_called()


def test_ingest_all_records_embedding_failure_in_report(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    _write_corpus(corpus)

    embeddings = _fake_embeddings()
    embeddings.embed_documents.side_effect = RuntimeError("vertex blew up")

    ingester = CorpusIngester(
        corpus_dir=corpus,
        chroma_persist_dir=tmp_path / "chroma",
        rules=_make_rules(),
        embeddings=embeddings,
    )
    report = ingester.ingest_all()
    assert report.total_chunks == 3
    assert report.ingested_chunks == 0
    assert any("embedding_failed" in e for e in report.errors)
    # ChromaDB collection should still be empty after failure
    assert ingester.collection_count() == 0


def test_report_as_dict_is_serialisable():
    """as_dict() yields plain dicts/lists for JSON output of the CLI."""
    report = IngestionReport(
        total_chunks=10,
        ingested_chunks=8,
        skipped_chunks=2,
        chunks_by_document={"doc1": 5, "doc2": 5},
        chunks_by_criterion={"C1": 3},
        chunks_by_agent={"A1": 3},
        untagged_chunks=2,
        errors=["one error"],
    )
    import json

    json.dumps(report.as_dict())  # must not raise


def test_ingest_uses_get_or_create_collection_with_default_name(tmp_path: Path):
    """Default collection name is 'normative_corpus' (per D010)."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    _write_corpus(corpus)
    ingester = CorpusIngester(
        corpus_dir=corpus,
        chroma_persist_dir=tmp_path / "chroma",
        rules=_make_rules(),
        embeddings=_fake_embeddings(),
    )
    ingester.ingest_all()
    # Re-open the ChromaDB client and verify the collection name exists.
    import chromadb
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    names = [c.name for c in client.list_collections()]
    assert "normative_corpus" in names
