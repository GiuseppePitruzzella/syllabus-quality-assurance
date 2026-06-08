"""Audit table linking an EvaluationResult to the local-document
versions that fed its extended criteria.

Phase 9.B.1 creates the table; Phase 9.B.2 fills it from the
:class:`ExternalDocumentResolver`; Phase 9.B.3 reads it from the
``DELETE /api/local-documents/{id}`` endpoint to decide between
hard and soft delete (a row referenced by any past run is
soft-deleted, so the run remains reproducible).

FK policy
---------

``local_document_id`` is declared ``ON DELETE RESTRICT``: it is
intentionally impossible to drop a registry row that any
``EvaluationResult`` ever referenced. Phase 9.B.3's API guard
turns RESTRICT-violating DELETE into a soft-delete fallback
client-side, but the constraint itself is the last line of
defense — even a manual SQL ``DELETE`` against the registry
would fail with a foreign-key violation.

``evaluation_result_id`` is declared ``ON DELETE CASCADE`` so that
deleting an ``EvaluationResult`` (rare, application-level
restricted) cleans the matching audit rows. The cascade is on
the join rows, NOT on the documents themselves.

Indices
-------

  - ``UNIQUE(evaluation_result_id, criterion_code, local_document_id)``:
    a run lists each (criterion, document) pair at most once. E5
    can reference multiple documents for the same criterion in the
    same run, which is why the document id is part of the key.
  - ``INDEX(evaluation_result_id, criterion_code)``: lookup path
    used by the future evaluation-page UI when rendering the
    "Criteri estesi" section per E*.
  - ``INDEX(local_document_id)``: lookup path used by Phase 9.B.3's
    DELETE guard ("is this document referenced by any run?").
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EvaluationExternalDocument(Base):
    __tablename__ = "evaluation_external_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    evaluation_result_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("evaluation_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    local_document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("local_documents.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Closed enum at the API layer ("E1" / "E2" / "E3" / "E5").
    # E4 is never present here — it is served by the syllabus itself
    # and never resolves a registry document.
    criterion_code: Mapped[str] = mapped_column(Text, nullable=False)

    # Snapshot fields: copies of the registry-row state at the time
    # the run consumed it. Phase 9.B.3 keeps the registry row alive
    # (soft-delete) so these stay consistent with the document on
    # disk; the snapshots are extra defence so a hard-delete
    # accident or a hand edit wouldn't drift historical context.
    document_version_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    file_hash_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    document_type_snapshot: Mapped[str] = mapped_column(Text, nullable=False)

    # Why this specific version was chosen, per the resolver's
    # precedence ladder. One of:
    #   "explicit_selection"          — caller passed the version id
    #   "academic_year_match"         — academic_year matched the syllabus's
    #   "latest_available_fallback"   — neither, but a row was indexed
    resolution_reason: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Optional convenience back-ref for the future evaluation-page UI.
    # We only declare the local-side relationship to avoid forcing
    # `EvaluationResult` to load this list eagerly on every fetch.
    local_document = relationship(
        "LocalDocument",
        foreign_keys=[local_document_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "evaluation_result_id",
            "criterion_code",
            "local_document_id",
            name="uq_evaluation_external_docs_run_crit_doc",
        ),
        Index(
            "ix_evaluation_external_docs_run_crit",
            "evaluation_result_id",
            "criterion_code",
        ),
        Index(
            "ix_evaluation_external_docs_local_doc",
            "local_document_id",
        ),
    )
