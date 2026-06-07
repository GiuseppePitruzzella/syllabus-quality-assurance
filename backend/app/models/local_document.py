"""SQLAlchemy model for external/local documents (Phase 8.A).

The local document registry is the backbone of the extended-criteria
pipeline (E1-E5). A row describes a single upload of a single
document version. Subsequent uploads of "the same" document (same
cdl + same type + same normalized title) increment ``version``; old
versions are NOT overwritten — they remain on disk and in the DB
for reproducibility of historical evaluation runs.

Phase 8.A persists the record + the file on disk only. Indexing
(text extraction, chunking, ChromaDB ingestion) lands in Phase 8.B;
A5 wiring into the evaluation graph lands in Phase 9.

Soft-delete is intentionally supported via ``deleted_at`` already at
this stage, even though Phase 8 UI only exposes "Elimina" (hard
delete). From Phase 9 onwards, deletion of a document referenced by
any ``EvaluationResult`` must fall back to soft-delete to preserve
historical reproducibility.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LocalDocument(Base):
    __tablename__ = "local_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cdl_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("corsi_di_laurea.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Closed enum, validated server-side via Pydantic. See
    # `schemas/local_document.py::DocumentType`.
    document_type: Mapped[str] = mapped_column(Text, nullable=False)
    academic_year: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # Versioning key: (cdl_id, document_type, normalized_title).
    # Normalization (trim / lowercase / collapse whitespace / strip
    # punctuation) makes the key robust to cosmetic title edits.
    normalized_title: Mapped[str] = mapped_column(Text, nullable=False)

    # Storage layout: backend/data/local_documents/{cdl_id}/{id}_v{version}.{ext}
    # `file_path` is the path relative to the storage root.
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_extension: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)

    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # List of criterion codes the document is enabled for, e.g. ["E5"]
    # or ["E1", "E3"]. Stored as JSON; default mapping is provided by
    # `schemas/local_document.py::DEFAULT_ENABLED_CRITERIA` keyed on
    # document_type.
    enabled_criteria: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Lifecycle states: uploaded -> extracting -> chunking ->
    # indexing -> indexed. Terminal failure goes to `failed`. Phase
    # 8.A only sets `uploaded`; later phases drive the transitions.
    status: Mapped[str] = mapped_column(Text, nullable=False, default="uploaded")
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Reserved for Phase 9+: soft-delete kicks in when the row is
    # referenced by an existing `EvaluationResult`.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    cdl = relationship("CorsoDiLaurea")
