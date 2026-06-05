"""Synchronous indexing service for local documents (Phase 8.B.2).

Drives a row through the state machine

  uploaded -> extracting -> chunking -> indexing -> indexed
                                                 -> failed

This module is intentionally synchronous: Phase 8.C will wrap it in
an async job (the JobRegistry pattern already used for scraping)
and add SSE progress, but the state transitions and the failure
semantics live here. Phase 9 will NOT touch this module — A5 will
query the Chroma collection directly via a retriever.
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.config import settings
from app.local_documents.chunker import (
    ExternalChunk,
    ExternalDocumentChunker,
)
from app.local_documents.extractors import (
    ExtractionError,
    extract_text,
    resolve_local_document_path,
)
from app.local_documents.ingester import (
    ExternalDocumentIngester,
    IngestionResult,
)
from app.models.local_document import LocalDocument

logger = structlog.get_logger(__name__)


class IndexingError(Exception):
    """Raised internally to short-circuit the state machine.

    Always converted into a ``status="failed"`` row update before
    propagating, so callers see both the exception and the
    persisted failure_reason.
    """


class LocalDocumentIndexingService:
    """Glue between the extractor, the chunker and the ingester.

    Failures are swallowed into a ``failed`` row state with a
    ``failure_reason`` string. The exception is re-raised after the
    DB update so the async wrapper (Phase 8.C) can also emit an
    SSE error event and the test suite can assert on the cause.
    """

    def __init__(
        self,
        db: Session,
        ingester: ExternalDocumentIngester,
        chunker: ExternalDocumentChunker | None = None,
        storage_root: str | None = None,
    ) -> None:
        self._db = db
        self._ingester = ingester
        self._chunker = chunker or ExternalDocumentChunker()
        self._storage_root = storage_root or settings.local_documents_dir

    # ------------------------------------------------------------------

    def index_document(self, document_id: int) -> IngestionResult:
        """Run extraction + chunking + indexing on a single document.

        Idempotent thanks to the ingester: re-running on an already-
        indexed row replaces its Chroma chunks with the freshly
        produced set.

        Returns the :class:`IngestionResult` from the ingester so
        the caller can introspect chunks_written / chunks_deleted /
        errors. On failure the row ends up in ``status="failed"``
        and the original exception is re-raised.
        """
        row = (
            self._db.query(LocalDocument)
            .filter(LocalDocument.id == document_id)
            .first()
        )
        if row is None:
            raise IndexingError(f"local document {document_id} not found")
        if row.deleted_at is not None:
            raise IndexingError(
                f"local document {document_id} is soft-deleted",
            )

        try:
            text = self._extract(row)
            chunks = self._chunk(row, text)
            result = self._index(row, chunks)
        except Exception as exc:
            self._mark_failed(row, exc)
            raise

        # All three phases succeeded. Persist the terminal state.
        row.status = "indexed"
        row.chunk_count = result.chunks_written
        row.failure_reason = None
        row.indexed_at = datetime.now(timezone.utc)
        self._db.commit()
        self._db.refresh(row)
        return result

    # ------------------------------------------------------------------
    # Phases
    # ------------------------------------------------------------------

    def _extract(self, row: LocalDocument) -> str:
        self._transition(row, "extracting")
        try:
            abs_path = resolve_local_document_path(
                row.file_path, self._storage_root,
            )
            return extract_text(abs_path, row.file_extension)
        except ExtractionError as exc:
            raise IndexingError(f"extraction_failed: {exc}") from exc
        except Exception as exc:
            raise IndexingError(f"extraction_failed: {exc}") from exc

    def _chunk(self, row: LocalDocument, text: str) -> list[ExternalChunk]:
        self._transition(row, "chunking")
        document_metadata = {
            "document_id": row.id,
            "version": row.version,
            "cdl_id": row.cdl_id,
            "document_type": row.document_type,
            "academic_year": row.academic_year,
            "file_hash": row.file_hash,
            "enabled_criteria": list(row.enabled_criteria or []),
        }
        try:
            return self._chunker.chunk_text(text, document_metadata)
        except Exception as exc:
            raise IndexingError(f"chunking_failed: {exc}") from exc

    def _index(
        self, row: LocalDocument, chunks: list[ExternalChunk],
    ) -> IngestionResult:
        self._transition(row, "indexing")
        result = self._ingester.index_chunks(
            chunks, document_id=row.id, version=row.version,
        )
        if result.errors:
            raise IndexingError(
                "indexing_failed: " + "; ".join(result.errors),
            )
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _transition(self, row: LocalDocument, target: str) -> None:
        row.status = target
        row.failure_reason = None
        self._db.commit()
        self._db.refresh(row)

    def _mark_failed(self, row: LocalDocument, exc: Exception) -> None:
        reason = str(exc)
        # Keep cleanup fully resilient: we don't want a secondary
        # failure here to mask the original cause.
        try:
            row.status = "failed"
            row.failure_reason = reason
            self._db.commit()
        except Exception as inner:
            logger.warning(
                "local_document_failure_persist_failed",
                document_id=row.id,
                cause=str(exc),
                persist_error=str(inner),
            )


__all__ = ["LocalDocumentIndexingService", "IndexingError"]
