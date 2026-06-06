"""End-to-end smoke for Phase 8.B.3 — REAL Vertex + REAL Chroma + real DB.

Validates the two API paths that 8.B.3 introduces or extends:

  - PATCH /api/local-documents/{id} with a CHANGED enabled_criteria
    on a row that is already `indexed` -> sync reindex, the
    chunks in Chroma now carry the new `tag_E*` booleans.
  - DELETE /api/local-documents/{id} on an indexed row -> chunks
    for (document_id, version) are removed from the
    `external_documents` collection alongside the DB row and the
    on-disk file.

A 1-chunk synthetic .md (< soft limit) keeps Vertex traffic to one
embed call per indexing pass. The script attaches FastAPI's
``TestClient`` to the real app object with NO dependency overrides,
so the dependency providers wire the live ``PersistentClient`` and
``VertexAIEmbeddings`` exactly as production would.

How to run
----------

::

    cd backend
    # Requires GCP_PROJECT_ID set in backend/.env
    uv run python scripts/smoke_phase_8_b3.py

Cost
----

Two embed calls total: one initial index, one reindex after PATCH.
Negligible.

Safety
------

Uses a fresh title per run (``smoke_phase_8_b3_<ts>``) so the row
can never collide with real registry data. Cleanup runs in a
``finally`` block: DB row, file, Chroma chunks are all removed
even when the script aborts mid-flight.
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import chromadb
from fastapi.testclient import TestClient

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parent.parent))

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.evaluation.rag.embeddings import VertexAIEmbeddings  # noqa: E402
from app.local_documents.ingester import (  # noqa: E402
    DEFAULT_COLLECTION_NAME,
    ExternalDocumentIngester,
)
from app.local_documents.service import LocalDocumentIndexingService  # noqa: E402
from app.main import app  # noqa: E402
from app.models.cdl import CorsoDiLaurea  # noqa: E402
from app.models.local_document import LocalDocument  # noqa: E402


# Small enough to produce exactly one chunk (under DEFAULT_MAX_CHARS=1500).
SMOKE_TEXT = (
    "# Linee guida brevi LM-18\n\n"
    "I prerequisiti devono distinguere conoscenze culturali e disciplinari. "
    "I criteri di voto vanno espliciti. La modalita di verifica si appoggia "
    "sui descrittori di Dublino."
).encode("utf-8")

CDL_ID = 3  # LM-18 Informatica (per CLAUDE.md)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _step(n: int, label: str) -> None:
    print(f"\n=== [{n}] {label}")


def _ids_for(collection, document_id: int, version: int) -> list[str]:
    where = {
        "$and": [
            {"document_id": {"$eq": int(document_id)}},
            {"version": {"$eq": int(version)}},
        ]
    }
    res = collection.get(where=where, include=["metadatas"])
    return sorted(list(res.get("ids") or []))


def _tags_for(collection, chunk_id: str) -> dict[str, bool]:
    got = collection.get(ids=[chunk_id], include=["metadatas"])
    metadatas = got.get("metadatas") or []
    if not metadatas:
        return {}
    md = metadatas[0]
    return {k: md[k] for k in sorted(md) if k.startswith("tag_")}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print("Phase 8.B.3 — end-to-end smoke (REAL Vertex + REAL Chroma + real DB)")
    print(f"Vertex project / location: {settings.gcp_project_id} / {settings.gcp_location}")
    print(f"Chroma persist dir       : {settings.chroma_persist_dir}")
    print(f"Local docs dir           : {settings.local_documents_dir}")

    try:
        project, location = settings.require_vertex_ai_config()
    except RuntimeError as exc:
        print(f"\nABORT: {exc}")
        return 2

    title = f"smoke_phase_8_b3_{int(time.time())}"
    print(f"Smoke title: {title!r}")

    db = SessionLocal()
    embeddings = VertexAIEmbeddings(project_id=project, location=location)
    chroma = chromadb.PersistentClient(path=str(settings.chroma_persist_dir))
    collection = chroma.get_or_create_collection(name=DEFAULT_COLLECTION_NAME)

    # The TestClient is bound to the real app — NO dependency
    # overrides. PATCH and DELETE will hit the real lazy providers
    # that wire Chroma + Vertex exactly as production.
    client = TestClient(app)

    document_id: int | None = None
    version: int | None = None
    file_on_disk: Path | None = None

    try:
        # ------------------------------------------------------------------
        _step(0, "preconditions")
        cdl = db.query(CorsoDiLaurea).filter(CorsoDiLaurea.id == CDL_ID).first()
        assert cdl is not None, (
            f"CdL id={CDL_ID} not found. Run the scraper first or adjust CDL_ID."
        )
        print(f"   CdL: id={cdl.id} code={cdl.code} name={cdl.name}")

        # ------------------------------------------------------------------
        _step(1, "POST upload -> row.status == 'uploaded'")
        response = client.post(
            "/api/local-documents",
            data={
                "cdl_id": str(CDL_ID),
                "document_type": "usi_dipartimentali",
                "academic_year": "2025-2026",
                "title": title,
            },
            files={"file": (f"{title}.md", io.BytesIO(SMOKE_TEXT), "text/markdown")},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        document_id = body["document"]["id"]
        version = body["document"]["version"]
        file_on_disk = Path(settings.local_documents_dir) / body["document"]["file_path"]
        print(
            f"   id={document_id} version={version} "
            f"status={body['document']['status']} "
            f"enabled_criteria={body['document']['enabled_criteria']}"
        )
        assert body["document"]["status"] == "uploaded"
        assert body["document"]["enabled_criteria"] == ["E5"]
        assert file_on_disk.exists()

        # ------------------------------------------------------------------
        _step(2, "index v1 via service -> row.status == 'indexed'")
        # 8.C will trigger this automatically; 8.B.3 still needs us to
        # call the service directly to get the row to `indexed` so the
        # PATCH path exercises the auto-reindex branch.
        ingester = ExternalDocumentIngester(chroma, embeddings)
        service = LocalDocumentIndexingService(db, ingester)
        result1 = service.index_document(document_id)
        row = db.query(LocalDocument).filter(LocalDocument.id == document_id).first()
        db.refresh(row)
        print(
            f"   row.status={row.status} chunk_count={row.chunk_count} "
            f"chunks_written={result1.chunks_written}"
        )
        assert row.status == "indexed"
        assert row.chunk_count == result1.chunks_written
        v1_ids = _ids_for(collection, document_id, version)
        assert len(v1_ids) == result1.chunks_written
        tags_before = _tags_for(collection, v1_ids[0])
        print(f"   tags before PATCH: {tags_before}")
        assert tags_before == {
            "tag_E1": False,
            "tag_E2": False,
            "tag_E3": False,
            "tag_E4": False,
            "tag_E5": True,
        }

        # ------------------------------------------------------------------
        _step(3, "PATCH enabled_criteria=['E4','E5'] -> auto-reindex, tags updated")
        patch = client.patch(
            f"/api/local-documents/{document_id}",
            json={"enabled_criteria": ["E4", "E5"]},
        )
        assert patch.status_code == 200, patch.text
        patched = patch.json()
        print(
            f"   status={patched['status']} "
            f"enabled_criteria={patched['enabled_criteria']} "
            f"chunk_count={patched['chunk_count']}"
        )
        assert patched["enabled_criteria"] == ["E4", "E5"]
        assert patched["status"] == "indexed"

        v1_ids_after = _ids_for(collection, document_id, version)
        # Same number of chunks, same ids (deterministic), no duplicates.
        assert v1_ids == v1_ids_after, (
            f"chunk ids changed across reindex: {v1_ids} -> {v1_ids_after}"
        )
        tags_after = _tags_for(collection, v1_ids_after[0])
        print(f"   tags after PATCH: {tags_after}")
        assert tags_after == {
            "tag_E1": False,
            "tag_E2": False,
            "tag_E3": False,
            "tag_E4": True,
            "tag_E5": True,
        }

        # ------------------------------------------------------------------
        _step(4, "DELETE -> DB row, file, Chroma chunks all gone")
        delete = client.delete(f"/api/local-documents/{document_id}")
        assert delete.status_code == 204, delete.text

        # DB row.
        gone = (
            db.query(LocalDocument)
            .filter(LocalDocument.id == document_id)
            .first()
        )
        print(f"   DB row present: {gone is not None}")
        assert gone is None

        # File on disk.
        print(f"   File on disk present: {file_on_disk.exists()}")
        assert not file_on_disk.exists()

        # Chroma chunks for this (document, version).
        remaining = _ids_for(collection, document_id, version)
        print(f"   Chroma chunks for (id={document_id}, v={version}): {len(remaining)}")
        assert remaining == []

        document_id = None  # mark as already-cleaned so cleanup skips it

        print("\nSMOKE OK")
        return 0

    except AssertionError as exc:
        print(f"\nSMOKE FAILED: assertion: {exc}")
        return 1
    except Exception as exc:
        print(f"\nSMOKE FAILED: {type(exc).__name__}: {exc}")
        return 1
    finally:
        _step(99, "cleanup")
        if document_id is not None and version is not None:
            try:
                collection.delete(
                    where={
                        "$and": [
                            {"document_id": {"$eq": int(document_id)}},
                            {"version": {"$eq": int(version)}},
                        ]
                    }
                )
            except Exception as exc:
                print(f"   cleanup chroma id={document_id} v={version}: {exc}")
            if file_on_disk is not None:
                try:
                    if file_on_disk.exists():
                        file_on_disk.unlink()
                except OSError as exc:
                    print(f"   cleanup file {file_on_disk}: {exc}")
            try:
                obj = (
                    db.query(LocalDocument)
                    .filter(LocalDocument.id == document_id)
                    .first()
                )
                if obj is not None:
                    db.delete(obj)
                    db.commit()
            except Exception as exc:
                print(f"   cleanup db id={document_id}: {exc}")
        try:
            (Path(settings.local_documents_dir) / str(CDL_ID)).rmdir()
        except OSError:
            pass
        # Final confirmation.
        if document_id is not None and version is not None:
            remaining = _ids_for(collection, document_id, version)
            print(f"   Chroma remaining for (id={document_id}, v={version}): {len(remaining)}")
        db.close()
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
