"""Pydantic schemas for the local-document registry (Phase 8.A)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Closed enum, validated server-side. Adding a new value here is the
# only place we change to extend the registry — `DEFAULT_ENABLED_CRITERIA`
# below must be kept in sync.
DocumentType = Literal[
    "regolamento_didattico",
    "sua_cds",
    "piano_studi",
    "manifesto",
    "propedeuticita",
    "metadati_ufficiali",
    "usi_dipartimentali",
    "linee_guida_cdl",
    "template_locale",
    "nota_presidio",
]

# Closed enum mirroring the rubric — only criteria for which the
# registry can ever serve a document.
ExtendedCriterionCode = Literal["E1", "E2", "E3", "E4", "E5"]

# Default `enabled_criteria` assignment per document_type. The mapping
# matches the rubric in `docs/progettazione.md §2.4` and the Phase 7
# constants. The user can override by passing an explicit
# `enabled_criteria` on upload, or by PATCH after the fact.
DEFAULT_ENABLED_CRITERIA: dict[str, list[str]] = {
    "regolamento_didattico": ["E1"],
    "sua_cds": ["E1"],
    "piano_studi": ["E2"],
    "manifesto": ["E2"],
    "propedeuticita": ["E3"],
    "metadati_ufficiali": ["E4"],
    "usi_dipartimentali": ["E5"],
    "linee_guida_cdl": ["E5"],
    "template_locale": ["E5"],
    "nota_presidio": ["E5"],
}

# Closed enum for lifecycle status.
LocalDocumentStatus = Literal[
    "uploaded",
    "extracting",
    "chunking",
    "indexing",
    "indexed",
    "failed",
]

# Accepted file extensions for upload. Anything else 415s.
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".html", ".htm", ".md"}


class LocalDocumentResponse(BaseModel):
    """Response payload mirroring the `LocalDocument` row."""

    id: int
    cdl_id: int
    document_type: str
    academic_year: str
    title: str
    normalized_title: str
    file_path: str
    file_extension: str
    file_hash: str
    file_size: int
    version: int
    enabled_criteria: list[str]
    status: str
    chunk_count: int | None
    failure_reason: str | None
    uploaded_at: datetime
    indexed_at: datetime | None
    deleted_at: datetime | None

    model_config = {"from_attributes": True}


class LocalDocumentUploadResponse(BaseModel):
    """Response of POST /api/local-documents.

    `job_id` is forward-compatible with Phase 8.C: it stays `None`
    while indexing is not wired yet. When the async indexing job is
    introduced, the same endpoint will return the same shape with
    `job_id` populated and clients won't need to change.
    """

    document: LocalDocumentResponse
    job_id: str | None = None


class LocalDocumentEnabledCriteriaUpdate(BaseModel):
    """Body of PATCH /api/local-documents/{id} (Phase 8.A subset)."""

    enabled_criteria: list[ExtendedCriterionCode] = Field(
        ..., description="List of extended criterion codes (E1..E5).",
    )

    @field_validator("enabled_criteria")
    @classmethod
    def _no_duplicates(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("enabled_criteria must not contain duplicates")
        return v


class LocalDocumentPatchResponse(BaseModel):
    """Response of PATCH /api/local-documents/{id} (Phase 8.C).

    Carries the updated document plus an optional ``job_id`` when
    the PATCH triggered an async reindex (status was ``indexed``).
    """

    document: LocalDocumentResponse
    job_id: str | None = None


class ChunkPreview(BaseModel):
    """Read-only chunk preview for the UI (Phase 8.C)."""

    chunk_id: str
    chunk_order: int
    char_count: int
    document_id: int
    version: int
    text_preview: str
    tags: dict[str, bool]
