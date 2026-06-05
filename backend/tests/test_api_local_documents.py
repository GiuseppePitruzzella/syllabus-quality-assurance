"""Tests for the local-document registry API (Phase 8.A).

Covers: upload, version bump on re-upload, list with filters, detail,
patch enabled_criteria, hard delete, validation errors (unknown
document_type, unsupported extension, empty file, unknown cdl).

Storage is redirected to a tmp_path per-test so the real
`backend/data/local_documents/` is never touched.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.cdl import CorsoDiLaurea
from app.models.department import Department
from app.models.local_document import LocalDocument


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_db():
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
def client(test_db, tmp_path, monkeypatch):
    # Redirect uploads under tmp_path so the test never touches the
    # real backend/data/local_documents/ tree.
    monkeypatch.setattr(settings, "local_documents_dir", str(tmp_path))

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cdl(db) -> CorsoDiLaurea:
    dept = Department(
        name="DMI",
        area="Scienze",
        website_url="https://web.dmi.unict.it",
        email="dmi@unict.it",
        phone="095123",
        director="Direttore",
        scraped_at=datetime.now(timezone.utc),
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)

    cdl = CorsoDiLaurea(
        department_id=dept.id,
        name="Informatica",
        code="lm-18",
        type="Magistrale",
        academic_year=None,
        url="https://web.dmi.unict.it/corsi/lm-18",
        scraped_at=datetime.now(timezone.utc),
    )
    db.add(cdl)
    db.commit()
    db.refresh(cdl)
    return cdl


def _upload(client, cdl_id: int, **overrides):
    """Issue a POST /api/local-documents with sensible defaults."""
    data = {
        "cdl_id": str(cdl_id),
        "document_type": "usi_dipartimentali",
        "academic_year": "2025-2026",
        "title": "Linee guida LM-18",
    }
    data.update({k: str(v) for k, v in overrides.items() if k != "file"})
    file_tuple = overrides.get(
        "file", ("guida.md", io.BytesIO(b"# linee guida"), "text/markdown"),
    )
    return client.post(
        "/api/local-documents",
        data=data,
        files={"file": file_tuple},
    )


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


def test_upload_persists_row_and_file(client, test_db, tmp_path):
    cdl = _make_cdl(test_db)
    response = _upload(client, cdl.id)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["job_id"] is None  # forward-compatible, populated in Phase 8.C
    doc = body["document"]
    assert doc["cdl_id"] == cdl.id
    assert doc["document_type"] == "usi_dipartimentali"
    assert doc["title"] == "Linee guida LM-18"
    assert doc["normalized_title"] == "linee guida lm 18"
    assert doc["version"] == 1
    assert doc["status"] == "uploaded"
    assert doc["enabled_criteria"] == ["E5"]  # default for usi_dipartimentali
    assert doc["file_extension"] == ".md"
    assert doc["file_size"] == len(b"# linee guida")
    assert doc["chunk_count"] is None
    assert doc["indexed_at"] is None
    assert doc["deleted_at"] is None

    on_disk = tmp_path / doc["file_path"]
    assert on_disk.exists()
    assert on_disk.read_bytes() == b"# linee guida"


def test_upload_increments_version_on_same_normalized_title(client, test_db):
    cdl = _make_cdl(test_db)
    r1 = _upload(client, cdl.id, title="Linee guida LM-18")
    r2 = _upload(client, cdl.id, title="  linee guida lm-18  ")
    r3 = _upload(client, cdl.id, title="Linee-Guida LM-18!")
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r3.status_code == 201
    versions = [r.json()["document"]["version"] for r in (r1, r2, r3)]
    assert versions == [1, 2, 3]


def test_upload_explicit_enabled_criteria_overrides_default(client, test_db):
    cdl = _make_cdl(test_db)
    response = _upload(
        client,
        cdl.id,
        document_type="sua_cds",
        enabled_criteria="E1,E2",
    )
    assert response.status_code == 201
    assert response.json()["document"]["enabled_criteria"] == ["E1", "E2"]


def test_upload_rejects_unknown_document_type(client, test_db):
    cdl = _make_cdl(test_db)
    response = _upload(client, cdl.id, document_type="not_a_type")
    assert response.status_code == 422


def test_upload_rejects_unsupported_extension(client, test_db):
    cdl = _make_cdl(test_db)
    response = _upload(
        client,
        cdl.id,
        file=("bad.exe", io.BytesIO(b"binary"), "application/octet-stream"),
    )
    assert response.status_code == 415


def test_upload_rejects_empty_file(client, test_db):
    cdl = _make_cdl(test_db)
    response = _upload(
        client,
        cdl.id,
        file=("empty.md", io.BytesIO(b""), "text/markdown"),
    )
    assert response.status_code == 422


def test_upload_404_when_cdl_missing(client, test_db):
    response = _upload(client, cdl_id=9999)
    assert response.status_code == 404


def test_upload_rejects_invalid_enabled_criteria(client, test_db):
    cdl = _make_cdl(test_db)
    response = _upload(client, cdl.id, enabled_criteria="E5,E9")
    assert response.status_code == 422


def test_upload_rejects_duplicate_enabled_criteria(client, test_db):
    cdl = _make_cdl(test_db)
    response = _upload(client, cdl.id, enabled_criteria="E5,E5")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# List / detail
# ---------------------------------------------------------------------------


def test_list_filters_by_cdl_and_document_type(client, test_db):
    cdl = _make_cdl(test_db)
    _upload(client, cdl.id, title="Doc A", document_type="usi_dipartimentali")
    _upload(client, cdl.id, title="Doc B", document_type="sua_cds")

    r_all = client.get("/api/local-documents", params={"cdl_id": cdl.id})
    assert r_all.status_code == 200
    assert len(r_all.json()) == 2

    r_filtered = client.get(
        "/api/local-documents",
        params={"cdl_id": cdl.id, "document_type": "sua_cds"},
    )
    assert r_filtered.status_code == 200
    docs = r_filtered.json()
    assert len(docs) == 1
    assert docs[0]["document_type"] == "sua_cds"


def test_list_hides_soft_deleted_by_default(client, test_db):
    cdl = _make_cdl(test_db)
    response = _upload(client, cdl.id)
    document_id = response.json()["document"]["id"]

    # Simulate the Phase 9 soft-delete path directly on the row.
    row = (
        test_db.query(LocalDocument)
        .filter(LocalDocument.id == document_id)
        .first()
    )
    row.deleted_at = datetime.now(timezone.utc)
    test_db.commit()

    visible = client.get("/api/local-documents").json()
    assert visible == []

    full = client.get(
        "/api/local-documents", params={"include_deleted": "true"},
    ).json()
    assert len(full) == 1


def test_detail_404_when_missing(client):
    response = client.get("/api/local-documents/9999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Patch enabled_criteria
# ---------------------------------------------------------------------------


def test_patch_updates_enabled_criteria(client, test_db):
    cdl = _make_cdl(test_db)
    response = _upload(client, cdl.id, document_type="sua_cds")
    document_id = response.json()["document"]["id"]

    patch = client.patch(
        f"/api/local-documents/{document_id}",
        json={"enabled_criteria": ["E1", "E2"]},
    )
    assert patch.status_code == 200
    assert patch.json()["enabled_criteria"] == ["E1", "E2"]


def test_patch_rejects_duplicates(client, test_db):
    cdl = _make_cdl(test_db)
    response = _upload(client, cdl.id)
    document_id = response.json()["document"]["id"]
    patch = client.patch(
        f"/api/local-documents/{document_id}",
        json={"enabled_criteria": ["E5", "E5"]},
    )
    assert patch.status_code == 422


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_removes_row_and_file(client, test_db, tmp_path):
    cdl = _make_cdl(test_db)
    response = _upload(client, cdl.id)
    document_id = response.json()["document"]["id"]
    file_rel = response.json()["document"]["file_path"]
    on_disk = tmp_path / file_rel
    assert on_disk.exists()

    delete = client.delete(f"/api/local-documents/{document_id}")
    assert delete.status_code == 204
    assert not on_disk.exists()
    assert client.get(f"/api/local-documents/{document_id}").status_code == 404


def test_delete_404_when_missing(client):
    response = client.delete("/api/local-documents/9999")
    assert response.status_code == 404


def test_delete_swallows_unsafe_file_path(client, test_db, tmp_path):
    """A corrupted `file_path` doesn't let DELETE unlink outside the store."""
    cdl = _make_cdl(test_db)
    response = _upload(client, cdl.id)
    document_id = response.json()["document"]["id"]

    # Forge an escape attempt by mutating the row directly. The API
    # never produces such a path itself, but the delete endpoint
    # must not turn the corrupted value into a filesystem-escape
    # primitive — the unsafe path is swallowed and the row is still
    # removed from the DB.
    outside_target = tmp_path.parent / "must_not_be_unlinked.md"
    outside_target.write_text("untouched", encoding="utf-8")

    row = (
        test_db.query(LocalDocument)
        .filter(LocalDocument.id == document_id)
        .first()
    )
    row.file_path = "../" + outside_target.name
    test_db.commit()

    res = client.delete(f"/api/local-documents/{document_id}")
    assert res.status_code == 204
    assert outside_target.exists()  # the unsafe path was ignored
    assert (
        test_db.query(LocalDocument)
        .filter(LocalDocument.id == document_id)
        .first()
        is None
    )


# ---------------------------------------------------------------------------
# Phase 8.B.1 — max upload size + transaction hardening
# ---------------------------------------------------------------------------


def test_upload_rejects_files_above_max_size(client, test_db, monkeypatch):
    cdl = _make_cdl(test_db)
    # Cap at 16 bytes so we can stay tiny in tests; the real default
    # is 50 MB. Override via monkeypatch keeps the test hermetic.
    monkeypatch.setattr(settings, "local_documents_max_upload_bytes", 16)
    payload = b"x" * 32
    response = _upload(
        client,
        cdl.id,
        file=("big.md", io.BytesIO(payload), "text/markdown"),
    )
    assert response.status_code == 413
    # No row should have been created.
    assert test_db.query(LocalDocument).count() == 0


def test_upload_rolls_back_and_cleans_file_on_commit_failure(
    client, test_db, tmp_path, monkeypatch,
):
    """A commit() failure AFTER the file is on disk leaves no orphans."""
    cdl = _make_cdl(test_db)

    # Patch Session.commit to raise on the first invocation only — so
    # the upload path fails at commit time, but later test teardown
    # / setup that may need commit() still works.
    import sqlalchemy.orm

    original_commit = sqlalchemy.orm.Session.commit
    calls = {"n": 0}

    def flaky_commit(self):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("forced commit failure")
        return original_commit(self)

    monkeypatch.setattr(sqlalchemy.orm.Session, "commit", flaky_commit)

    response = _upload(client, cdl.id)
    assert response.status_code == 500

    # No row left behind, no file left behind.
    assert test_db.query(LocalDocument).count() == 0
    leftovers = list(tmp_path.rglob("*"))
    leftover_files = [p for p in leftovers if p.is_file()]
    assert leftover_files == [], (
        f"orphan file(s) after commit failure: {leftover_files}"
    )
