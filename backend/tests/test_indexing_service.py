"""Tests for the LocalDocumentIndexingService (Phase 8.B.2).

End-to-end coverage of the synchronous state machine:
  uploaded -> extracting -> chunking -> indexing -> indexed | failed

The Chroma layer is replaced by an in-memory EphemeralClient. The
embeddings are a deterministic stub. Files are synthesised on the
fly under tmp_path so the real `backend/data/local_documents/` is
never touched.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

import chromadb
import pytest
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.local_documents.ingester import ExternalDocumentIngester
from app.local_documents.service import (
    IndexingError,
    LocalDocumentIndexingService,
)
from app.models.cdl import CorsoDiLaurea
from app.models.department import Department
from app.models.local_document import LocalDocument


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _ConstantEmbeddings:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class _FailingEmbeddings:
    def embed_documents(self, texts):
        raise RuntimeError("vertex down")


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def chroma_client():
    """Ephemeral Chroma isolated per-test.

    `chromadb.EphemeralClient()` shares its in-memory backend across
    instances inside the same process, so without an explicit reset
    a collection populated by a previous test leaks into the next.
    Drop the collection on the way in AND on the way out.
    """
    client = chromadb.EphemeralClient()
    try:
        client.delete_collection("external_documents")
    except Exception:
        pass
    yield client
    try:
        client.delete_collection("external_documents")
    except Exception:
        pass


@pytest.fixture
def ingester(chroma_client):
    return ExternalDocumentIngester(chroma_client, _ConstantEmbeddings())


def _make_cdl(db):
    dept = Department(
        name="DMI", area="Scienze", website_url="https://x", email="x@y",
        phone="1", director="d", scraped_at=datetime.now(timezone.utc),
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    cdl = CorsoDiLaurea(
        department_id=dept.id, name="Informatica", code="lm-18",
        type="Magistrale", academic_year=None, url="https://x/c",
        scraped_at=datetime.now(timezone.utc),
    )
    db.add(cdl)
    db.commit()
    db.refresh(cdl)
    return cdl


def _make_doc_row(
    db, cdl_id: int, storage_root, *,
    extension: str = ".md",
    content: bytes = b"Linee guida LM-18.\n\nPrerequisiti chiari.",
    version: int = 1,
    enabled_criteria: list[str] | None = None,
):
    rel = f"{cdl_id}/N_v{version}{extension}"
    abs_path = storage_root / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(content)
    row = LocalDocument(
        cdl_id=cdl_id,
        document_type="usi_dipartimentali",
        academic_year="2025-2026",
        title="Linee guida",
        normalized_title="linee guida",
        file_path=rel,
        file_extension=extension,
        file_hash="abc",
        file_size=len(content),
        version=version,
        enabled_criteria=enabled_criteria or ["E5"],
        status="uploaded",
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    # Fix the placeholder filename so it matches row.id once assigned.
    new_rel = f"{cdl_id}/{row.id}_v{version}{extension}"
    new_abs = storage_root / new_rel
    new_abs.parent.mkdir(parents=True, exist_ok=True)
    abs_path.rename(new_abs)
    row.file_path = new_rel
    db.commit()
    db.refresh(row)
    return row


def _blank_pdf_bytes() -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_index_document_drives_status_to_indexed(
    db_session, ingester, tmp_path, chroma_client,
):
    cdl = _make_cdl(db_session)
    row = _make_doc_row(db_session, cdl.id, tmp_path)
    service = LocalDocumentIndexingService(
        db_session, ingester, storage_root=str(tmp_path),
    )

    result = service.index_document(row.id)

    db_session.refresh(row)
    assert row.status == "indexed"
    assert row.chunk_count == result.chunks_written
    assert row.chunk_count > 0
    assert row.indexed_at is not None
    assert row.failure_reason is None

    coll = chroma_client.get_or_create_collection("external_documents")
    assert coll.count() == result.chunks_written


def test_reindex_is_idempotent_on_db_state(
    db_session, ingester, tmp_path,
):
    cdl = _make_cdl(db_session)
    row = _make_doc_row(db_session, cdl.id, tmp_path)
    service = LocalDocumentIndexingService(
        db_session, ingester, storage_root=str(tmp_path),
    )

    first = service.index_document(row.id)
    db_session.refresh(row)
    first_chunk_count = row.chunk_count

    second = service.index_document(row.id)
    db_session.refresh(row)

    assert first.chunks_written == second.chunks_written
    assert row.chunk_count == first_chunk_count
    assert row.status == "indexed"


def test_scanned_pdf_is_indexed_through_ocr_fallback(
    db_session, ingester, tmp_path,
):
    cdl = _make_cdl(db_session)
    row = _make_doc_row(
        db_session,
        cdl.id,
        tmp_path,
        extension=".pdf",
        content=_blank_pdf_bytes(),
        enabled_criteria=["E2"],
    )
    service = LocalDocumentIndexingService(
        db_session,
        ingester,
        storage_root=str(tmp_path),
        pdf_ocr=lambda _path: (
            "Risultato di apprendimento | Attività formative\n"
            "R1 | Analisi matematica"
        ),
    )

    result = service.index_document(row.id)

    db_session.refresh(row)
    assert row.status == "indexed"
    assert result.chunks_written > 0


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


def test_extraction_failure_marks_failed_and_reraises(
    db_session, ingester, tmp_path,
):
    cdl = _make_cdl(db_session)
    row = _make_doc_row(
        db_session, cdl.id, tmp_path,
        # Empty content -> extractor raises (empty md after normalisation).
        content=b"",
    )
    service = LocalDocumentIndexingService(
        db_session, ingester, storage_root=str(tmp_path),
    )

    with pytest.raises(IndexingError):
        service.index_document(row.id)

    db_session.refresh(row)
    assert row.status == "failed"
    assert row.failure_reason and "extraction_failed" in row.failure_reason
    assert row.chunk_count is None
    assert row.indexed_at is None


def test_embedding_failure_marks_failed(db_session, chroma_client, tmp_path):
    cdl = _make_cdl(db_session)
    row = _make_doc_row(db_session, cdl.id, tmp_path)
    failing_ingester = ExternalDocumentIngester(
        chroma_client, _FailingEmbeddings(),
    )
    service = LocalDocumentIndexingService(
        db_session, failing_ingester, storage_root=str(tmp_path),
    )

    with pytest.raises(IndexingError):
        service.index_document(row.id)

    db_session.refresh(row)
    assert row.status == "failed"
    assert "indexing_failed" in row.failure_reason


def test_index_missing_document_raises_without_db_mutation(
    db_session, ingester,
):
    service = LocalDocumentIndexingService(db_session, ingester)
    with pytest.raises(IndexingError):
        service.index_document(9999)


def test_soft_deleted_document_is_not_indexed(
    db_session, ingester, tmp_path,
):
    cdl = _make_cdl(db_session)
    row = _make_doc_row(db_session, cdl.id, tmp_path)
    row.deleted_at = datetime.now(timezone.utc)
    db_session.commit()

    service = LocalDocumentIndexingService(
        db_session, ingester, storage_root=str(tmp_path),
    )
    with pytest.raises(IndexingError):
        service.index_document(row.id)
