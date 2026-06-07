"""End-to-end smoke for Phase 8.C — async indexing + SSE.

Exercises the async/SSE boundary against REAL Vertex + REAL Chroma:
the synchronous backbone is already covered by 8.B.2 and 8.B.3
smokes, this one covers what fakes can't:

  - the FastAPI -> scheduler -> worker thread -> queue -> SSE
    handoff;
  - exact event order (`extracting` -> `chunking` -> `indexing`
    -> `done`);
  - terminal stream closure (`None` sentinel from job_registry);
  - distinct job_ids per upload / reindex / PATCH;
  - status transitions persisted in the DB as the worker advances;
  - PATCH reindex actually rewrites `tag_E*` in Chroma;
  - DELETE cascades cleanup (DB + file + Chroma);
  - a parallel error-path scenario using a corrupted PDF: no
    embedding traffic, but proves the SSE error event reaches the
    client with a usable `failure_reason`.

How to run
----------

::

    cd backend
    # Requires GCP_PROJECT_ID set in backend/.env
    uv run python scripts/smoke_phase_8_c.py

Cost
----

Three embed calls total: upload (initial index) + reindex
(idempotent) + PATCH (tag rewrite). The error path uses a
corrupted PDF that fails at extraction, no Vertex traffic.

Safety
------

Unique titles per run (``smoke_phase_8_c_<ts>_*``) so the rows can
never collide with real registry data. Cleanup runs in `finally`:
DB rows, files on disk, Chroma chunks for both the happy-path and
the error-path documents are all removed even when the script
aborts mid-flight.
"""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

import chromadb
from fastapi.testclient import TestClient

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parent.parent))

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.local_documents.ingester import (  # noqa: E402
    DEFAULT_COLLECTION_NAME,
)
from app.main import app  # noqa: E402
from app.models.cdl import CorsoDiLaurea  # noqa: E402
from app.models.local_document import LocalDocument  # noqa: E402


# A 2-paragraph synthetic .md that produces a small but non-trivial
# chunk count (we want at least one chunk; the body stays well below
# the soft limit so 1 chunk is what we get).
SMOKE_TEXT_V1 = (
    "# Linee guida brevi LM-18 (v1)\n\n"
    "Sezione prerequisiti. Conoscenze culturali e disciplinari distinte. "
    "I criteri di voto vanno espliciti."
).encode("utf-8")

# A deliberately broken PDF: starts with the magic number so the
# upload's extension check passes, but pdfplumber can't parse it,
# so the worker emits an error event without touching Vertex.
CORRUPTED_PDF = b"%PDF-1.4\n%garbage that is not a valid PDF body"


CDL_ID = 3  # LM-18 Informatica (per CLAUDE.md)
STREAM_TIMEOUT = 60  # seconds; embedding pass is usually <10s


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _step(n: int, label: str) -> None:
    print(f"\n=== [{n}] {label}")


def _consume_stream(client: TestClient, job_id: str) -> list[dict]:
    """Subscribe to the SSE stream and return the parsed events.

    Stops at the terminal `done` or `error`. Asserts the stream is
    cleanly closed by the server (no hang past the terminal event).
    """
    events: list[dict] = []
    with client.stream(
        "GET",
        f"/api/local-documents/stream/{job_id}",
        timeout=STREAM_TIMEOUT,
    ) as resp:
        assert resp.status_code == 200, (
            f"stream status={resp.status_code} body={resp.read()!r}"
        )
        for raw in resp.iter_lines():
            line = raw.decode() if isinstance(raw, bytes) else raw
            line = line.strip()
            if not line:
                continue
            if not line.startswith("data:"):
                continue
            payload_str = line[len("data:"):].strip()
            if not payload_str:
                continue
            event = json.loads(payload_str)
            events.append(event)
            if event.get("type") in ("done", "error"):
                break
    return events


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


def _refresh_row(db, document_id: int) -> LocalDocument | None:
    db.expire_all()
    return (
        db.query(LocalDocument)
        .filter(LocalDocument.id == document_id)
        .first()
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:  # noqa: PLR0915, PLR0912 — smoke is a linear script
    print("Phase 8.C — end-to-end smoke (REAL Vertex + REAL Chroma + SSE)")
    print(f"Vertex project / location: {settings.gcp_project_id} / {settings.gcp_location}")
    print(f"Chroma persist dir       : {settings.chroma_persist_dir}")
    print(f"Local docs dir           : {settings.local_documents_dir}")

    try:
        settings.require_vertex_ai_config()
    except RuntimeError as exc:
        print(f"\nABORT: {exc}")
        return 2

    ts = int(time.time())
    title_ok = f"smoke_phase_8_c_{ts}_ok"
    title_err = f"smoke_phase_8_c_{ts}_err"
    print(f"Smoke titles: {title_ok!r}, {title_err!r}")

    db = SessionLocal()
    chroma = chromadb.PersistentClient(path=str(settings.chroma_persist_dir))
    collection = chroma.get_or_create_collection(name=DEFAULT_COLLECTION_NAME)
    client = TestClient(app)

    document_id_ok: int | None = None
    version_ok: int | None = None
    file_ok: Path | None = None

    document_id_err: int | None = None
    version_err: int | None = None
    file_err: Path | None = None

    job_ids: list[str] = []

    try:
        # ------------------------------------------------------------------
        _step(0, "preconditions")
        cdl = db.query(CorsoDiLaurea).filter(CorsoDiLaurea.id == CDL_ID).first()
        assert cdl is not None, f"CdL id={CDL_ID} not found."
        print(f"   CdL: id={cdl.id} code={cdl.code} name={cdl.name}")

        # ------------------------------------------------------------------
        _step(1, "POST upload -> job_id; SSE produces extracting/chunking/indexing/done")
        response = client.post(
            "/api/local-documents",
            data={
                "cdl_id": str(CDL_ID),
                "document_type": "usi_dipartimentali",
                "academic_year": "2025-2026",
                "title": title_ok,
            },
            files={"file": (f"{title_ok}.md", io.BytesIO(SMOKE_TEXT_V1), "text/markdown")},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        document_id_ok = body["document"]["id"]
        version_ok = body["document"]["version"]
        file_ok = Path(settings.local_documents_dir) / body["document"]["file_path"]
        upload_job = body["job_id"]
        assert isinstance(upload_job, str) and upload_job, "upload job_id missing"
        job_ids.append(upload_job)
        print(f"   id={document_id_ok} version={version_ok} upload_job={upload_job}")
        assert file_ok.exists()

        events = _consume_stream(client, upload_job)
        progress_messages = [
            e.get("message") for e in events if e["type"] == "progress"
        ]
        terminal = events[-1]
        print(
            f"   SSE events: progress={progress_messages} "
            f"terminal_type={terminal['type']}"
        )
        assert progress_messages == ["extracting", "chunking", "indexing"], (
            f"unexpected progress order: {progress_messages}"
        )
        assert terminal["type"] == "done"
        assert terminal.get("scraped", 0) > 0

        row = _refresh_row(db, document_id_ok)
        assert row is not None and row.status == "indexed"
        assert row.chunk_count == terminal["scraped"]
        assert row.failure_reason is None
        print(
            f"   row.status={row.status} chunk_count={row.chunk_count} "
            f"failure_reason={row.failure_reason}"
        )

        v1_ids = _ids_for(collection, document_id_ok, version_ok)
        tags_initial = _tags_for(collection, v1_ids[0])
        print(f"   Chroma chunks: {len(v1_ids)}, tags: {tags_initial}")
        assert tags_initial == {
            "tag_E1": False, "tag_E2": False, "tag_E3": False,
            "tag_E4": False, "tag_E5": True,
        }

        # ------------------------------------------------------------------
        _step(2, "POST /reindex -> distinct job_id, same chunks, idempotent")
        re_resp = client.post(f"/api/local-documents/{document_id_ok}/reindex")
        assert re_resp.status_code == 202, re_resp.text
        reindex_job = re_resp.json()["job_id"]
        assert isinstance(reindex_job, str) and reindex_job
        assert reindex_job != upload_job, "reindex job_id must differ from upload"
        job_ids.append(reindex_job)
        print(f"   reindex_job={reindex_job}")

        events_re = _consume_stream(client, reindex_job)
        progress_re = [e["message"] for e in events_re if e["type"] == "progress"]
        terminal_re = events_re[-1]
        print(
            f"   SSE events: progress={progress_re} "
            f"terminal_type={terminal_re['type']}"
        )
        assert progress_re == ["extracting", "chunking", "indexing"]
        assert terminal_re["type"] == "done"

        v1_ids_after = _ids_for(collection, document_id_ok, version_ok)
        assert v1_ids == v1_ids_after, (
            f"chunk ids changed across reindex: {v1_ids} -> {v1_ids_after}"
        )

        # ------------------------------------------------------------------
        _step(3, "PATCH -> distinct job_id, tag_E* rewritten")
        patch = client.patch(
            f"/api/local-documents/{document_id_ok}",
            json={"enabled_criteria": ["E4", "E5"]},
        )
        assert patch.status_code == 200, patch.text
        patch_body = patch.json()
        patch_job = patch_body["job_id"]
        assert isinstance(patch_job, str) and patch_job, "PATCH job_id missing"
        assert patch_job not in (upload_job, reindex_job), (
            f"PATCH job_id must be distinct: got {patch_job}"
        )
        job_ids.append(patch_job)
        print(f"   patch_job={patch_job}")
        assert patch_body["document"]["enabled_criteria"] == ["E4", "E5"]

        events_patch = _consume_stream(client, patch_job)
        progress_patch = [
            e["message"] for e in events_patch if e["type"] == "progress"
        ]
        terminal_patch = events_patch[-1]
        print(
            f"   SSE events: progress={progress_patch} "
            f"terminal_type={terminal_patch['type']}"
        )
        assert progress_patch == ["extracting", "chunking", "indexing"]
        assert terminal_patch["type"] == "done"

        tags_after = _tags_for(collection, v1_ids[0])
        print(f"   tags after PATCH: {tags_after}")
        assert tags_after == {
            "tag_E1": False, "tag_E2": False, "tag_E3": False,
            "tag_E4": True, "tag_E5": True,
        }

        # ------------------------------------------------------------------
        _step(4, "GET /chunks -> preview rows, sorted, with current tags")
        gc = client.get(
            f"/api/local-documents/{document_id_ok}/chunks?limit=10"
        )
        assert gc.status_code == 200, gc.text
        chunks_view = gc.json()
        assert len(chunks_view) == len(v1_ids)
        assert chunks_view[0]["chunk_order"] == 0
        assert chunks_view[0]["tags"]["tag_E4"] is True
        assert chunks_view[0]["tags"]["tag_E5"] is True
        assert chunks_view[0]["text_preview"]
        print(
            f"   /chunks count={len(chunks_view)} "
            f"first.preview={chunks_view[0]['text_preview'][:60]!r}..."
        )

        # ------------------------------------------------------------------
        _step(5, "Error path: upload corrupted PDF -> SSE error, row.status=failed")
        response_err = client.post(
            "/api/local-documents",
            data={
                "cdl_id": str(CDL_ID),
                "document_type": "regolamento_didattico",
                "academic_year": "2025-2026",
                "title": title_err,
            },
            files={
                "file": (
                    f"{title_err}.pdf",
                    io.BytesIO(CORRUPTED_PDF),
                    "application/pdf",
                ),
            },
        )
        assert response_err.status_code == 201, response_err.text
        body_err = response_err.json()
        document_id_err = body_err["document"]["id"]
        version_err = body_err["document"]["version"]
        file_err = Path(settings.local_documents_dir) / body_err["document"]["file_path"]
        err_job = body_err["job_id"]
        job_ids.append(err_job)
        print(f"   id={document_id_err} version={version_err} err_job={err_job}")

        events_err = _consume_stream(client, err_job)
        progress_err = [e["message"] for e in events_err if e["type"] == "progress"]
        terminal_err = events_err[-1]
        print(
            f"   SSE events: progress={progress_err} "
            f"terminal={terminal_err}"
        )
        # The worker had time to publish at least the `extracting`
        # transition before the extractor blew up.
        assert "extracting" in progress_err
        assert terminal_err["type"] == "error"
        assert terminal_err.get("message"), "error event must carry a message"

        row_err = _refresh_row(db, document_id_err)
        assert row_err is not None and row_err.status == "failed"
        assert row_err.failure_reason and "extraction_failed" in row_err.failure_reason
        print(
            f"   error row.status={row_err.status} "
            f"failure_reason={row_err.failure_reason!r}"
        )

        # ------------------------------------------------------------------
        _step(6, "Distinct job_ids check")
        assert len(set(job_ids)) == len(job_ids), (
            f"job_ids must all be distinct, got {job_ids}"
        )
        print(f"   all distinct: {len(job_ids)} job_ids")

        # ------------------------------------------------------------------
        _step(7, "DELETE happy doc -> DB row, file, Chroma chunks gone")
        delete = client.delete(f"/api/local-documents/{document_id_ok}")
        assert delete.status_code == 204

        gone_db = _refresh_row(db, document_id_ok)
        gone_file = file_ok.exists()
        remaining_chunks = _ids_for(collection, document_id_ok, version_ok)
        print(
            f"   DB row present={gone_db is not None} "
            f"file present={gone_file} "
            f"remaining chunks={len(remaining_chunks)}"
        )
        assert gone_db is None
        assert not gone_file
        assert remaining_chunks == []
        document_id_ok = None  # mark cleaned

        # Same for the error doc.
        delete_err = client.delete(f"/api/local-documents/{document_id_err}")
        assert delete_err.status_code == 204
        assert _refresh_row(db, document_id_err) is None
        assert file_err is not None and not file_err.exists()
        document_id_err = None

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
        for doc_id, version, on_disk in (
            (document_id_ok, version_ok, file_ok),
            (document_id_err, version_err, file_err),
        ):
            if doc_id is None:
                continue
            try:
                collection.delete(
                    where={
                        "$and": [
                            {"document_id": {"$eq": int(doc_id)}},
                            {"version": {"$eq": int(version)}},
                        ]
                    }
                )
            except Exception as exc:
                print(f"   cleanup chroma id={doc_id}: {exc}")
            if on_disk is not None:
                try:
                    if on_disk.exists():
                        on_disk.unlink()
                except OSError as exc:
                    print(f"   cleanup file {on_disk}: {exc}")
            try:
                obj = (
                    db.query(LocalDocument)
                    .filter(LocalDocument.id == doc_id)
                    .first()
                )
                if obj is not None:
                    db.delete(obj)
                    db.commit()
            except Exception as exc:
                print(f"   cleanup db id={doc_id}: {exc}")
        try:
            (Path(settings.local_documents_dir) / str(CDL_ID)).rmdir()
        except OSError:
            pass
        # Confirm Chroma is back to empty for the smoke documents.
        for doc_id, version in (
            (document_id_ok, version_ok),
            (document_id_err, version_err),
        ):
            if doc_id is None or version is None:
                continue
            remaining = _ids_for(collection, doc_id, version)
            print(f"   Chroma remaining for (id={doc_id}, v={version}): {len(remaining)}")
        db.close()
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
