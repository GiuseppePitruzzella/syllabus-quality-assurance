"""Read-only manifest for the versioned normative corpus.

The evaluation graph consumes the corpus through ChromaDB, but the
user-facing UI needs a deterministic inventory of the source documents
without touching Vertex AI or the vector store. This module derives that
inventory directly from the Markdown files and the YAML tagging rules.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import cast

from app.evaluation.rag.chunker import MarkdownChunker
from app.evaluation.rag.tagging_rules import TaggingRules
from app.schemas.normative_corpus import NormativeCorpusDocument

CORE_CRITERIA: tuple[str, ...] = tuple(f"C{i}" for i in range(1, 10))
CORE_AGENTS: tuple[str, ...] = tuple(f"A{i}" for i in range(1, 5))


def list_normative_corpus_documents(
    *,
    corpus_dir: Path,
    tagging_rules_file: Path,
) -> list[NormativeCorpusDocument]:
    """Return the eight corpus documents with criterion/agent coverage.

    Sorting is stable and user-oriented: higher-priority documents first,
    then the document id. Untagged/context documents remain visible so the
    inventory matches the corpus on disk instead of silently hiding files.
    """

    rules = TaggingRules.from_yaml(tagging_rules_file)
    chunker = MarkdownChunker()
    documents: list[NormativeCorpusDocument] = []

    for path in sorted(corpus_dir.glob("*.md")):
        document_id = path.stem
        metadata = rules.document_metadata(document_id)
        metadata["language"] = metadata.get("language", "it")
        chunks = [
            rules.apply(chunk)
            for chunk in chunker.chunk_document(path, metadata)
        ]

        core_criteria = [
            code
            for code in CORE_CRITERIA
            if any(chunk.metadata.get(f"tag_{code}") for chunk in chunks)
        ]
        agents = [
            code
            for code in CORE_AGENTS
            if any(chunk.metadata.get(f"tag_{code}") for chunk in chunks)
        ]
        core_chunk_count = sum(
            1
            for chunk in chunks
            if any(chunk.metadata.get(f"tag_{code}") for code in CORE_CRITERIA)
        )

        documents.append(
            NormativeCorpusDocument(
                document_id=document_id,
                title=metadata.get("document_title") or document_id,
                version=str(metadata.get("document_version") or ""),
                source_type=str(metadata.get("source_type") or ""),
                priority=int(metadata.get("document_priority") or 0),
                filename=path.name,
                file_hash=_sha256(path),
                file_size=path.stat().st_size,
                chunk_count=len(chunks),
                core_chunk_count=core_chunk_count,
                core_criteria=cast("list[str]", core_criteria),
                agents=cast("list[str]", agents),
                is_core_source=core_chunk_count > 0,
            ),
        )

    return sorted(
        documents,
        key=lambda item: (-item.priority, item.document_id),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
