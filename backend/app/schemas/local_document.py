"""Pydantic schemas for the local-document registry.

Phase 9.A — consolidates the extended-criteria document contract.
The Phase 8 ``DEFAULT_ENABLED_CRITERIA`` map was wrong on three
counts (``regolamento_didattico`` was bound to E1 instead of E3;
``piano_studi`` / ``manifesto`` to E2 whose real source is the
Matrice di Tuning; ``metadati_ufficiali`` to E4 whose source is the
syllabus itself, not the registry) and a fourth tipo ``matrice_tuning``
was missing. This module is now the single source of truth for:

  - the closed enum of registry-accepted document types
    (``DocumentType``);
  - the closed enum of extended criterion codes
    (``ExtendedCriterionCode``);
  - the **default** criteria the upload endpoint auto-assigns
    (``DEFAULT_ENABLED_CRITERIA``);
  - the **allowed** criteria server-side validation accepts on
    upload / PATCH (``ALLOWED_CRITERIA_BY_DOCUMENT_TYPE``).

Default ⊆ Allowed for every document type. Allowed can be richer
than default (today it is not, but the registry is built so the
domain can grow without code changes elsewhere).

E4 is intentionally absent from every map: cross-lingua is
served by the syllabus itself (``learning_outcomes_en`` and the
other ``*_en`` fields), not by a registry document. See Phase 9.B
for the resolver logic.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Closed enum, validated server-side. Adding a new value here is the
# only place we change to extend the registry — `DEFAULT_ENABLED_CRITERIA`
# and `ALLOWED_CRITERIA_BY_DOCUMENT_TYPE` below must be kept in sync.
DocumentType = Literal[
    "regolamento_didattico",
    "sua_cds",
    "matrice_tuning",  # Phase 9.A: new type, sole source of E2.
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
# registry can ever serve a document. E4 (cross-lingua) is served
# by the syllabus itself, never by the registry; it appears here
# only because the rubric defines it, not because the registry
# can be enabled for it.
ExtendedCriterionCode = Literal["E1", "E2", "E3", "E4", "E5"]

# Default ``enabled_criteria`` assignment per document_type. Picked
# up by the upload endpoint when the caller doesn't pass an
# explicit list. A document type whose default is the empty list
# (e.g. ``piano_studi``) is admitted into the registry as
# context-only — it doesn't auto-serve any extended criterion.
#
# Source of truth: ``docs/progettazione.md §2.4`` (rubric) +
# §2.5 (criterion-to-source mapping). Mirrored client-side by
# ``frontend/src/data/sources.ts::DOCUMENT_TYPES``.
DEFAULT_ENABLED_CRITERIA: dict[str, list[str]] = {
    "regolamento_didattico": ["E3"],
    "sua_cds": ["E1"],
    "matrice_tuning": ["E2"],
    "piano_studi": [],
    "manifesto": [],
    "propedeuticita": [],
    "metadati_ufficiali": [],
    "usi_dipartimentali": ["E5"],
    "linee_guida_cdl": ["E5"],
    "template_locale": ["E5"],
    "nota_presidio": ["E5"],
}

# Allowed ``enabled_criteria`` per document type. Server-side
# validation rejects any upload / PATCH whose criteria are not a
# subset of the entry for the document's type. Designed so future
# additions to the extended-criteria set (e.g. an E6) can be
# enabled per-type by editing this map alone, without touching
# the defaults.
#
# Invariant: ``DEFAULT_ENABLED_CRITERIA[t] ⊆ ALLOWED_CRITERIA_BY_DOCUMENT_TYPE[t]``
# for every ``t``. Verified by the test suite.
ALLOWED_CRITERIA_BY_DOCUMENT_TYPE: dict[str, list[str]] = {
    "regolamento_didattico": ["E3"],
    "sua_cds": ["E1"],
    "matrice_tuning": ["E2"],
    "piano_studi": [],
    "manifesto": [],
    "propedeuticita": [],
    "metadati_ufficiali": [],
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
