"""Local-document registry API (Phase 8.A + 8.B.1 hardening).

This module handles the storage side only — file lands on disk, row
is persisted, listing / detail work. Text extraction lives in
`app/local_documents/extractors.py`, the async indexing job that
calls it will land in Phase 8.C.

The POST response shape (`{ document, job_id }`) is forward-
compatible with the async indexing job: today `job_id` is always
`null`, but the contract lets the frontend attach to a stream once
it's there without touching this endpoint.

Deletion is hard-delete in Phase 8 because no `EvaluationResult`
references a document yet. From Phase 9 onwards, delete on a
referenced document will fall back to soft-delete via
`deleted_at` to preserve historical reproducibility — `deleted_at`
is already in the schema.

Phase 8.B.1 adds:
  - Hard cap on upload size (413 before any disk write).
  - Full transactional hardening of the upload path: any failure
    after the bytes have been written rolls back the DB row AND
    removes the on-disk file. Cleanup failures don't shadow the
    original exception (they are logged but the original is
    re-raised).
  - Safe-path resolution on delete so a corrupted `file_path`
    can't be turned into a filesystem-escape primitive.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import chromadb
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.jobs import job_registry
from app.local_documents import (
    ExtractionError,
    IndexingJobScheduler,
    resolve_local_document_path,
)
from app.local_documents.dependencies import (
    get_chroma_client,
    get_external_ingester,
    get_indexing_job_scheduler,
)
from app.local_documents.ingester import (
    DEFAULT_COLLECTION_NAME as EXTERNAL_COLLECTION_NAME,
    ExternalDocumentIngester,
)
from app.models.cdl import CorsoDiLaurea
from app.models.local_document import LocalDocument
from app.schemas.job import JobCreated
from app.schemas.local_document import (
    ALLOWED_CRITERIA_BY_DOCUMENT_TYPE,
    ALLOWED_EXTENSIONS,
    ChunkPreview,
    DEFAULT_ENABLED_CRITERIA,
    DocumentType,
    LocalDocumentEnabledCriteriaUpdate,
    LocalDocumentPatchResponse,
    LocalDocumentResponse,
    LocalDocumentStatus,
    LocalDocumentUploadResponse,
)

logger = logging.getLogger(__name__)

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
    Any explicitly-passed list must be a subset of
    ``ALLOWED_CRITERIA_BY_DOCUMENT_TYPE[document_type]`` — Phase 9.A
    enforces the document-to-criterion contract server-side to
    keep the registry's semantics tight: a ``manifesto`` cannot
    silently be PATCHed into serving E5 just because the previous
    Phase 8 default map permitted it.
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
    _assert_criteria_allowed_for_type(parts, document_type)
    return parts


def _assert_criteria_allowed_for_type(
    criteria: list[str], document_type: str,
) -> None:
    """Reject criteria that the document type cannot serve.

    Used by both POST upload (via :func:`_parse_enabled_criteria`)
    and PATCH (after the Pydantic-level enum check). Returns
    silently when the list is fully allowed; raises 422 with the
    offending codes otherwise. An empty allowed-set for the type
    means the document is registry-only (e.g. ``piano_studi``)
    and rejects any enabled criterion.
    """
    allowed = set(ALLOWED_CRITERIA_BY_DOCUMENT_TYPE.get(document_type, []))
    not_allowed = [c for c in criteria if c not in allowed]
    if not not_allowed:
        return
    if not allowed:
        raise HTTPException(
            status_code=422,
            detail=(
                f"document_type {document_type!r} does not serve any "
                f"extended criterion; got {not_allowed}"
            ),
        )
    raise HTTPException(
        status_code=422,
        detail=(
            f"criteria {not_allowed} are not allowed for document_type "
            f"{document_type!r}; allowed: {sorted(allowed)}"
        ),
    )


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
    scheduler: IndexingJobScheduler = Depends(get_indexing_job_scheduler),
) -> LocalDocumentUploadResponse:
    """Accept a multipart upload, persist file + row, schedule indexing.

    Phase 8.C: indexing is dispatched asynchronously via the
    `IndexingJobScheduler`. The response carries the freshly
    persisted row plus the `job_id` clients can stream progress
    from at `GET /api/local-documents/stream/{job_id}`.
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
    if len(content) > settings.local_documents_max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File exceeds max upload size "
                f"({settings.local_documents_max_upload_bytes} bytes)"
            ),
        )
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
    try:
        db.add(row)
        db.flush()
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to persist document row: {e}",
        ) from e

    rel_path = f"{cdl_id}/{row.id}_v{version}{ext}"
    abs_path = Path(settings.local_documents_dir) / rel_path

    file_written = False
    try:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(content)
        file_written = True
        row.file_path = rel_path
        db.commit()
    except Exception as e:
        # Any failure after disk write — including commit() — rolls
        # back the row AND removes the orphan file. The DB row never
        # had a real file_path committed; the file (if any) is
        # unreachable from the registry once we roll back.
        db.rollback()
        if file_written:
            _best_effort_unlink(abs_path)
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=500, detail=f"Failed to persist document: {e}",
        ) from e
    db.refresh(row)

    # Phase 8.C: auto-trigger async indexing. The scheduler reads
    # the row from a fresh DB session inside the worker, so it's
    # safe to dispatch immediately after the commit above.
    job_id = scheduler.schedule(row.id)

    return LocalDocumentUploadResponse(
        document=LocalDocumentResponse.model_validate(row),
        job_id=job_id,
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


@router.patch("/{document_id}", response_model=LocalDocumentPatchResponse)
def update_enabled_criteria(
    document_id: int,
    payload: LocalDocumentEnabledCriteriaUpdate,
    db: Session = Depends(get_db),
    scheduler: IndexingJobScheduler = Depends(get_indexing_job_scheduler),
) -> LocalDocumentPatchResponse:
    """Replace the ``enabled_criteria`` list for a document.

    Phase 8.C: when the document is ``indexed``, the PATCH
    schedules an async reindex via the same JobScheduler the
    upload path uses, and the response carries a ``job_id`` the
    UI can stream from. For any other state, the new flags are
    persisted and ``job_id`` is ``None`` — the new tags will be
    picked up at the next indexing pass.

    The Chroma chunks carry the criterion flags as boolean
    metadata (``tag_E1`` ... ``tag_E5``); a PATCH without reindex
    would silently drift the retrieval surface, which is why the
    indexed case is auto-triggered.
    """
    row = db.query(LocalDocument).filter(LocalDocument.id == document_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")

    new_enabled = list(payload.enabled_criteria)
    if new_enabled == list(row.enabled_criteria or []):
        return LocalDocumentPatchResponse(
            document=LocalDocumentResponse.model_validate(row),
            job_id=None,
        )

    # Phase 9.A: enforce the document-to-criterion contract on PATCH
    # too — Pydantic validates each item is a valid E* code but
    # cannot know which codes are admissible for this row's type.
    _assert_criteria_allowed_for_type(new_enabled, row.document_type)

    row.enabled_criteria = new_enabled
    db.commit()
    db.refresh(row)

    job_id: str | None = None
    if row.status == "indexed":
        job_id = scheduler.schedule(row.id)

    return LocalDocumentPatchResponse(
        document=LocalDocumentResponse.model_validate(row),
        job_id=job_id,
    )


@router.post(
    "/{document_id}/reindex",
    response_model=JobCreated,
    status_code=202,
)
def reindex_local_document(
    document_id: int,
    db: Session = Depends(get_db),
    scheduler: IndexingJobScheduler = Depends(get_indexing_job_scheduler),
) -> JobCreated:
    """Manually trigger an async reindex.

    Useful when a previous indexing run ended in ``failed`` and
    the operator wants to retry without changing
    ``enabled_criteria``, or when the underlying file has been
    replaced on disk through another path. Returns a 202 plus
    the ``job_id`` to stream progress from.
    """
    row = db.query(LocalDocument).filter(LocalDocument.id == document_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if row.deleted_at is not None:
        raise HTTPException(
            status_code=409,
            detail="Document is soft-deleted and cannot be reindexed",
        )
    job_id = scheduler.schedule(row.id)
    return JobCreated(job_id=job_id)


@router.get("/stream/{job_id}")
async def stream_indexing_job(job_id: str):
    """SSE stream of progress / completion events for an indexing job.

    Emits one ``progress`` event per state transition
    (``extracting``, ``chunking``, ``indexing``), then a terminal
    ``done`` (with ``scraped`` set to chunk count) or ``error``
    (with ``message`` set to the failure reason).

    Mirrors `GET /api/scrape/stream/{job_id}` for the scraping
    jobs — they share the same `job_registry` singleton, so the
    SSE plumbing is identical.
    """
    # Imported lazily to keep test-time import of the router
    # decoupled from sse-starlette's optional dependencies surface.
    from sse_starlette.sse import EventSourceResponse

    state = job_registry.get_job(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        while True:
            event = await state.queue.get()
            if event is None:
                break  # sentinel: job complete
            yield {"data": event.model_dump_json()}

    return EventSourceResponse(event_generator())


@router.get("/{document_id}/chunks", response_model=list[ChunkPreview])
def list_chunks_for_document(
    document_id: int,
    limit: int = 20,
    text_preview_chars: int = 240,
    db: Session = Depends(get_db),
    chroma: chromadb.api.client.Client = Depends(get_chroma_client),
) -> list[ChunkPreview]:
    """Read-only chunk preview for the registry UI.

    Only the chunks belonging to the row's current ``version`` are
    returned (older versions remain in Chroma for historical
    EvaluationResult references but the UI shows what's "live").
    Each entry carries a truncated text preview so the UI doesn't
    need to ship full chunk bodies on a list view.
    """
    if limit <= 0 or limit > 200:
        raise HTTPException(
            status_code=422, detail="limit must be in [1, 200]",
        )
    if text_preview_chars <= 0 or text_preview_chars > 2000:
        raise HTTPException(
            status_code=422,
            detail="text_preview_chars must be in [1, 2000]",
        )

    row = db.query(LocalDocument).filter(LocalDocument.id == document_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")

    collection = chroma.get_or_create_collection(name=EXTERNAL_COLLECTION_NAME)
    where = {
        "$and": [
            {"document_id": {"$eq": int(row.id)}},
            {"version": {"$eq": int(row.version)}},
        ]
    }
    try:
        res = collection.get(
            where=where, include=["metadatas", "documents"], limit=limit,
        )
    except Exception as exc:
        logger.warning(
            "list_chunks: chroma get failed for id=%s v=%s: %s",
            row.id, row.version, exc,
        )
        return []

    ids = list(res.get("ids") or [])
    metadatas = list(res.get("metadatas") or [])
    documents = list(res.get("documents") or [])
    out: list[ChunkPreview] = []
    for chunk_id, md, doc in zip(ids, metadatas, documents):
        if md is None or doc is None:
            continue
        tags = {k: bool(md[k]) for k in md if k.startswith("tag_")}
        out.append(
            ChunkPreview(
                chunk_id=chunk_id,
                chunk_order=int(md.get("chunk_order", 0)),
                char_count=int(md.get("char_count", 0)),
                document_id=int(md.get("document_id", row.id)),
                version=int(md.get("version", row.version)),
                text_preview=str(doc)[:text_preview_chars],
                tags=tags,
            )
        )
    out.sort(key=lambda c: c.chunk_order)
    return out


@router.delete("/{document_id}", status_code=204)
def delete_local_document(
    document_id: int,
    db: Session = Depends(get_db),
    ingester: ExternalDocumentIngester = Depends(get_external_ingester),
) -> None:
    """Hard-delete (Phase 8 only).

    Removes, in this order:

      1. every chunk for ``(document_id, version)`` from the
         ``external_documents`` Chroma collection — must happen
         BEFORE the DB row is gone so we still know which version
         to delete;
      2. the DB row;
      3. the file on disk (best-effort).

    From Phase 9 onwards, this endpoint will check whether the
    document is referenced by any ``EvaluationResult`` and fall
    back to soft-delete (``deleted_at = now()``) when so. For now,
    no EvaluationResult ever references a local document, so hard
    delete is safe.
    """
    row = db.query(LocalDocument).filter(LocalDocument.id == document_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # 1) Resolve the on-disk path before touching the DB / Chroma so
    # any failure here can short-circuit before mutating anything.
    abs_path: Path | None
    try:
        abs_path = resolve_local_document_path(
            row.file_path, settings.local_documents_dir,
        )
    except ExtractionError as e:
        logger.warning(
            "delete_local_document: unsafe file_path on row %s: %s",
            row.id, e,
        )
        abs_path = None

    # 2) Chroma cleanup. delete_for is best-effort internally
    # (logs + returns count). A failure here logs but does not
    # block the DB delete: the DB is the registry's canonical
    # state, and orphan chunks would be recoverable via a future
    # `reindex` or `purge` job.
    document_id_val = row.id
    version_val = row.version
    try:
        ingester.delete_for(document_id_val, version_val)
    except Exception as exc:
        logger.warning(
            "delete_local_document: ingester.delete_for failed "
            "for id=%s v=%s: %s",
            document_id_val, version_val, exc,
        )

    # 3) DB row.
    db.delete(row)
    db.commit()

    # 4) File on disk.
    if abs_path is not None:
        _best_effort_unlink(abs_path)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _best_effort_unlink(path: Path) -> None:
    """Remove a file ignoring missing / locked path.

    Used in two places: cleanup of an orphan after a failed upload
    commit, and the post-delete file removal. Cleanup failures are
    logged but never raised — the canonical state of the registry
    lives in the DB, and an orphan file is recoverable, while a
    masked original exception is not.
    """
    try:
        if path.exists():
            path.unlink()
    except OSError as cleanup_err:
        logger.warning(
            "local_documents cleanup: failed to remove %s: %s",
            path, cleanup_err,
        )


# Re-export so the API module surface stays explicit.
__all__ = ["router", "LocalDocumentStatus"]
