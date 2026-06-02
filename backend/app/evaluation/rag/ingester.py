"""Ingest the normative corpus into ChromaDB.

The ingester glues together the chunker, the tagging rules and the
embedding wrapper, producing a populated single-collection vector store
under ``settings.chroma_persist_dir``.

Idempotency is keyed on ``chunk_id`` (the deterministic identifier
emitted by the chunker). When ``force_reingest=False`` (default), any
chunk whose ``chunk_id`` already exists in the collection is skipped:
no embedding API call, no ChromaDB write. With ``force_reingest=True``
all chunks are re-embedded and ``upsert``ed.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import chromadb
import structlog

from app.evaluation.rag.chunker import Chunk, MarkdownChunker
from app.evaluation.rag.embeddings import VertexAIEmbeddings
from app.evaluation.rag.tagging_rules import ALL_AGENTS, ALL_CRITERIA, TaggingRules

logger = structlog.get_logger(__name__)

DEFAULT_COLLECTION_NAME = "normative_corpus"


@dataclass
class IngestionReport:
    """Summary of one ingestion run."""

    total_chunks: int = 0
    ingested_chunks: int = 0
    skipped_chunks: int = 0
    chunks_by_document: dict[str, int] = field(default_factory=dict)
    chunks_by_criterion: dict[str, int] = field(default_factory=dict)
    chunks_by_agent: dict[str, int] = field(default_factory=dict)
    untagged_chunks: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_chunks": self.total_chunks,
            "ingested_chunks": self.ingested_chunks,
            "skipped_chunks": self.skipped_chunks,
            "chunks_by_document": dict(self.chunks_by_document),
            "chunks_by_criterion": dict(self.chunks_by_criterion),
            "chunks_by_agent": dict(self.chunks_by_agent),
            "untagged_chunks": self.untagged_chunks,
            "errors": list(self.errors),
        }


class CorpusIngester:
    """Drive the chunker → tagger → embedder → ChromaDB pipeline."""

    def __init__(
        self,
        corpus_dir: Path,
        chroma_persist_dir: Path,
        rules: TaggingRules,
        embeddings: VertexAIEmbeddings,
        chunker: MarkdownChunker | None = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
    ) -> None:
        self._corpus_dir = corpus_dir
        self._chroma_persist_dir = chroma_persist_dir
        self._rules = rules
        self._embeddings = embeddings
        self._chunker = chunker or MarkdownChunker()
        self._collection_name = collection_name
        self._client: chromadb.api.client.Client | None = None
        self._collection: chromadb.api.models.Collection.Collection | None = None

    # ---- public API ----

    def produce_chunks(self) -> list[Chunk]:
        """Run chunker + tagger over every Markdown file in ``corpus_dir``.

        Returns the tagged chunks without touching ChromaDB or Vertex AI;
        useful for the ``--preview`` mode of the CLI.
        """
        chunks: list[Chunk] = []
        for md_file in sorted(self._corpus_dir.glob("*.md")):
            doc_id = md_file.stem
            doc_meta = self._rules.document_metadata(doc_id)
            doc_meta["language"] = doc_meta.get("language", "it")
            raw = self._chunker.chunk_document(md_file, doc_meta)
            tagged = [self._rules.apply(c) for c in raw]
            chunks.extend(tagged)
            logger.info(
                "document_chunked",
                document_id=doc_id,
                chunks=len(tagged),
            )
        return chunks

    def ingest_all(self, force_reingest: bool = False) -> IngestionReport:
        """Run the full ingestion pipeline and return a summary report."""
        report = IngestionReport()
        chunks = self.produce_chunks()
        report.total_chunks = len(chunks)

        # Stats over the full chunk set (regardless of skip status).
        report.chunks_by_document = dict(
            Counter(c.metadata["document_id"] for c in chunks)
        )
        report.chunks_by_criterion = {
            code: sum(1 for c in chunks if c.metadata.get(f"tag_{code}"))
            for code in sorted(ALL_CRITERIA)
        }
        report.chunks_by_agent = {
            code: sum(1 for c in chunks if c.metadata.get(f"tag_{code}"))
            for code in sorted(ALL_AGENTS)
        }
        report.untagged_chunks = sum(
            1
            for c in chunks
            if not any(c.metadata.get(f"tag_{x}") for x in ALL_CRITERIA)
        )

        collection = self._get_collection()

        # Pre-fetch existing ids in one round-trip when not forcing.
        existing_ids: set[str] = set()
        if not force_reingest and chunks:
            chunk_ids = [c.chunk_id for c in chunks]
            existing = collection.get(ids=chunk_ids)
            existing_ids = set(existing.get("ids") or [])

        to_ingest = [c for c in chunks if force_reingest or c.chunk_id not in existing_ids]
        report.skipped_chunks = len(chunks) - len(to_ingest)

        if not to_ingest:
            logger.info(
                "ingestion_complete",
                ingested=0,
                skipped=report.skipped_chunks,
                total=report.total_chunks,
            )
            return report

        # Embed every text. gemini-embedding-001 batch=1, so this is
        # naturally O(n) API calls. The embedding wrapper handles retries.
        try:
            vectors = self._embeddings.embed_documents([c.text for c in to_ingest])
        except Exception as exc:  # noqa: BLE001 — bubble any failure up via report
            report.errors.append(f"embedding_failed: {exc}")
            logger.error("embedding_failed", error=str(exc))
            return report

        # ChromaDB metadata must be flat scalars (str / int / float / bool).
        # Our tag_* fields and provenance fields already satisfy this.
        ids = [c.chunk_id for c in to_ingest]
        documents = [c.text for c in to_ingest]
        metadatas = [_clean_metadata(c.metadata) for c in to_ingest]

        if force_reingest:
            collection.upsert(
                ids=ids,
                embeddings=vectors,
                documents=documents,
                metadatas=metadatas,
            )
        else:
            collection.add(
                ids=ids,
                embeddings=vectors,
                documents=documents,
                metadatas=metadatas,
            )
        report.ingested_chunks = len(to_ingest)

        logger.info(
            "ingestion_complete",
            ingested=report.ingested_chunks,
            skipped=report.skipped_chunks,
            total=report.total_chunks,
        )
        return report

    def collection_count(self) -> int:
        """Number of chunks currently in the collection. Useful for diagnostics."""
        return self._get_collection().count()

    # ---- internals ----

    def _get_collection(self):
        if self._collection is not None:
            return self._collection
        self._chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self._chroma_persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name
        )
        return self._collection


def _clean_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Coerce metadata to ChromaDB-compatible primitive types.

    ChromaDB rejects list / dict / None values in metadata. Today every
    key in chunk metadata is already a primitive (str/int/bool), but
    this guard prevents future regressions: ``None`` becomes ``""``
    and any non-primitive is dropped (with a warning log).
    """
    cleaned: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if isinstance(value, (bool, int, float, str)):
            # bool first because bool is a subclass of int — both branches
            # produce a valid value, the order is just for clarity.
            cleaned[key] = value
        elif value is None:
            cleaned[key] = ""
        else:
            logger.warning(
                "metadata_value_dropped",
                key=key,
                type=type(value).__name__,
            )
    return cleaned
