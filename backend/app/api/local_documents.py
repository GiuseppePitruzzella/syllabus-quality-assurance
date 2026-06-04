"""Local-document registry API (Phase 8.A).

This module handles the storage side only — file lands on disk, row
is persisted, listing / detail work. No text extraction, no
chunking, no ChromaDB ingestion: those come in Phase 8.B and the
async job that wraps them in Phase 8.C.

The POST response shape (`{ document, job_id }`) is forward-
compatible with the async indexing job that will land in Phase 8.C:
today `job_id` is always `null`, but the contract lets the frontend
attach to a stream once it's there without touching this endpoint.

Deletion is hard-delete in Phase 8 because no `EvaluationResult`
references a document yet. From Phase 9 onwards, delete on a
referenced document will fall back to soft-delete via
`deleted_at` to preserve historical reproducibility — `deleted_at`
is already in the schema.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.cdl import CorsoDiLaurea
from app.models.local_document import LocalDocument
from app.schemas.local_document import (
    ALLOWED_EXTENSIONS,
    DEFAULT_ENABLED_CRITERIA,
    DocumentType,
    LocalDocumentEnabledCriteriaUpdate,
    LocalDocumentResponse,
    LocalDocumentStatus,
    LocalDocumentUploadResponse,
)

router = APIRouter(prefix="/api/local-documents", tags=["local-documents"])

_VALID_DOCUMENT_TYPES = set(DEFAULT_ENABLED_CRITERIA.keys())
_VALID_STATUSES = {
    "uploaded", "extracting", "chunking", "indexing", "indexed", "failed",
}
_VALID_EXTENDED_CRITERIA = {"E1", "E2", "E3", "E4", "E5"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_title(title: str) -> str:
    """Versioning-stable key for a user-defined title.

    Trim, lowercase, treat hyphens as separators, strip punctuation,
    collapse internal whitespace. Robust to cosmetic edits
    (`Linee Guida CdL` ↔ `linee guida cdl ` ↔ `Linee-Guida CdL!`) so
    a re-upload of "the same" document doesn't accidentally fork
    into two version chains.
    """
    s = title.strip().lower()
    s = s.replace("-", " ")
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extension_of(filename: str | None) -> str:
    """Return the lowercase suffix (e.g. `.pdf`) of an upload filename.

    Raises 415 if the extension is missing or not whitelisted.
    """
    if not filename:
        raise HTTPException(status_code=415, detail="Missing upload filename")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file extension: {ext!r}. "
                f"Allowed: {sorted(ALLOWED_EXTENSIONS)}"
            ),
        )
    # Normalise .htm to .html so the rest of the pipeline only sees one.
    return ".html" if ext == ".htm" else ext


def _next_version(
    db: Session, cdl_id: int, document_type: str, normalized_title: str,
) -> int:
    """Compute the next version for the (cdl, type, normalized title) key."""
    latest = (
        db.query(LocalDocument)
        .filter(
            LocalDocument.cdl_id == cdl_id,
            LocalDocument.document_type == document_type,
            LocalDocument.normalized_title == normalized_title,
        )
        .order_by(LocalDocument.version.desc())
        .first()
    )
    return (latest.version + 1) if latest else 1


def _parse_enabled_criteria(
    raw: str | None, document_type: str,
) -> list[str]:
    """Parse the comma-separated form field; fall back to defaults.

    The field is optional. If absent or empty, the default mapping
    for `document_type` is used (see `DEFAULT_ENABLED_CRITERIA`).
    """
    if raw is None or raw.strip() == "":
        return list(DEFAULT_ENABLED_CRITERIA[document_type])
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    invalid = [p for p in parts if p not in _VALID_EXTENDED_CRITERIA]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid extended criterion codes: {invalid}",
        )
    if len(set(parts)) != len(parts):
        raise HTTPException(
            status_code=422,
            detail="enabled_criteria must not contain duplicates",
        )
    return parts


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=LocalDocumentUploadResponse,
    status_code=201,
)
async def upload_local_document(
    cdl_id: int = Form(...),
    document_type: DocumentType = Form(...),
    academic_year: str = Form(...),
    title: str = Form(...),
    enabled_criteria: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> LocalDocumentUploadResponse:
    """Accept a multipart upload, persist file + row.

    Indexing (text extraction → chunking → ChromaDB) is NOT triggered
    yet. The response shape is forward-compatible: `job_id` is always
    `None` here; Phase 8.C will populate it with the indexing job's
    id when the async pipeline is wired in.
    """
    if document_type not in _VALID_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown document_type: {document_type!r}",
        )

    cdl = db.query(CorsoDiLaurea).filter(CorsoDiLaurea.id == cdl_id).first()
    if cdl is None:
        raise HTTPException(status_code=404, detail="CdL not found")

    title_stripped = title.strip()
    if not title_stripped:
        raise HTTPException(status_code=422, detail="title must be non-empty")
    academic_year_stripped = academic_year.strip()
    if not academic_year_stripped:
        raise HTTPException(
            status_code=422, detail="academic_year must be non-empty",
        )

    ext = _extension_of(file.filename)
    normalized = _normalize_title(title_stripped)
    enabled = _parse_enabled_criteria(enabled_criteria, document_type)
    version = _next_version(db, cdl_id, document_type, normalized)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    file_hash = hashlib.sha256(content).hexdigest()
    file_size = len(content)

    # Insert with a placeholder file_path so the row has an id we can
    # bake into the filename. flush() assigns the PK without
    # committing the transaction.
    row = LocalDocument(
        cdl_id=cdl_id,
        document_type=document_type,
        academic_year=academic_year_stripped,
        title=title_stripped,
        normalized_title=normalized,
        file_path="",  # backfilled below
        file_extension=ext,
        file_hash=file_hash,
        file_size=file_size,
        version=version,
        enabled_criteria=enabled,
        status="uploaded",
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()

    rel_path = f"{cdl_id}/{row.id}_v{version}{ext}"
    abs_path = Path(settings.local_documents_dir) / rel_path

    try:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(content)
    except OSError as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to persist file on disk: {e}",
        ) from e

    row.file_path = rel_path
    db.commit()
    db.refresh(row)

    return LocalDocumentUploadResponse(
        document=LocalDocumentResponse.model_validate(row),
        job_id=None,
    )


@router.get("", response_model=list[LocalDocumentResponse])
def list_local_documents(
    cdl_id: int | None = None,
    document_type: str | None = None,
    status: str | None = None,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
) -> list[LocalDocument]:
    """List documents, ordered by uploaded_at desc.

    Filters are optional. By default, soft-deleted rows are hidden
    (`deleted_at is None`); pass `include_deleted=true` to inspect
    the full history once Phase 9 enables soft-delete in practice.
    """
    query = db.query(LocalDocument)
    if cdl_id is not None:
        query = query.filter(LocalDocument.cdl_id == cdl_id)
    if document_type is not None:
        if document_type not in _VALID_DOCUMENT_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown document_type: {document_type!r}",
            )
        query = query.filter(LocalDocument.document_type == document_type)
    if status is not None:
        if status not in _VALID_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown status: {status!r}",
            )
        query = query.filter(LocalDocument.status == status)
    if not include_deleted:
        query = query.filter(LocalDocument.deleted_at.is_(None))
    return query.order_by(LocalDocument.uploaded_at.desc()).all()


@router.get("/{document_id}", response_model=LocalDocumentResponse)
def get_local_document(
    document_id: int, db: Session = Depends(get_db),
) -> LocalDocument:
    row = db.query(LocalDocument).filter(LocalDocument.id == document_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return row


@router.patch("/{document_id}", response_model=LocalDocumentResponse)
def update_enabled_criteria(
    document_id: int,
    payload: LocalDocumentEnabledCriteriaUpdate,
    db: Session = Depends(get_db),
) -> LocalDocument:
    """Replace the `enabled_criteria` list for a document."""
    row = db.query(LocalDocument).filter(LocalDocument.id == document_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    row.enabled_criteria = list(payload.enabled_criteria)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{document_id}", status_code=204)
def delete_local_document(
    document_id: int, db: Session = Depends(get_db),
) -> None:
    """Hard-delete (Phase 8 only).

    From Phase 9 onwards, this endpoint will check whether the
    document is referenced by any `EvaluationResult` and fall back
    to soft-delete (`deleted_at = now()`) when so. For now, no
    EvaluationResult ever references a local document, so hard
    delete is safe.
    """
    row = db.query(LocalDocument).filter(LocalDocument.id == document_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")

    abs_path = Path(settings.local_documents_dir) / row.file_path
    db.delete(row)
    db.commit()
    # Best-effort filesystem cleanup. The DB row is already gone; if
    # the file is missing or unwritable we log via the response but
    # don't error out (the canonical state lives in the DB).
    try:
        if abs_path.exists():
            abs_path.unlink()
    except OSError:
        pass


# Re-export so the API module surface stays explicit.
__all__ = ["router", "LocalDocumentStatus"]
