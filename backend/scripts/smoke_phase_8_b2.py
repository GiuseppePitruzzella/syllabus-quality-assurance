"""End-to-end smoke for Phase 8.B.2 — REAL Vertex + REAL ChromaDB.

What this script verifies
-------------------------

1. Upload (simulated: row + file on disk like the real endpoint would).
2. ``LocalDocumentIndexingService.index_document(id)`` against the
   live Vertex AI embeddings client and the live persistent Chroma
   collection ``external_documents``:
   - row.status flips to ``indexed`` and chunk_count > 0;
   - the persisted chunks carry the deterministic id format
     ``external_{id}_v{ver}__chunk_{order:04d}``;
   - embeddings are present and have the expected dimension;
   - metadata is scalar-only and the five ``tag_E*`` flags reflect
     the row's ``enabled_criteria``.
3. Reindex of the same row is idempotent (no duplicates, count
   stable).
4. Uploading and indexing a second version (v2) does not touch v1
   chunks (per-version isolation against the real Chroma
   ``where=`` filter).
5. Cleanup: DB rows removed, files removed from disk, all chunks
   for the smoke document removed from Chroma.

How to run
----------

::

    cd backend
    # Requires GCP_PROJECT_ID set in backend/.env
    uv run python scripts/smoke_phase_8_b2.py

Cost
----

3 small text chunks per upload, 2 uploads, plus 1 reindex of the
first upload (idempotent re-embedding). Roughly 9 embedding calls
total. Negligible.

Safety
------

A unique title is generated per-run (``smoke_phase_8_b2_<ts>``) so
the script never collides with real registry rows. The cleanup
block runs in a ``finally`` so even a mid-script failure leaves no
orphan rows / files / chunks.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import chromadb

# Local imports: allow running as `python scripts/smoke_phase_8_b2.py`.
_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parent.parent))  # backend/

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.evaluation.rag.embeddings import VertexAIEmbeddings  # noqa: E402
from app.local_documents.chunker import chunk_id_prefix  # noqa: E402
from app.local_documents.ingester import (  # noqa: E402
    DEFAULT_COLLECTION_NAME,
    ExternalDocumentIngester,
)
from app.local_documents.service import LocalDocumentIndexingService  # noqa: E402
from app.models.cdl import CorsoDiLaurea  # noqa: E402
from app.models.local_document import LocalDocument  # noqa: E402


# ---------------------------------------------------------------------------
# Test material — synthetic Markdown ~3500 chars split into 3 paragraphs.
# ---------------------------------------------------------------------------


SMOKE_TEXT_V1 = (
    "# Linee guida compilazione syllabus LM-18\n\n"
    + ("Sezione prerequisiti. " * 80).strip()
    + "\n\n"
    + ("Sezione contenuti del corso. " * 80).strip()
    + "\n\n"
    + ("Sezione modalita di verifica e criteri di voto. " * 80).strip()
).encode("utf-8")

SMOKE_TEXT_V2 = (
    "# Linee guida compilazione syllabus LM-18 (v2)\n\n"
    + ("Sezione prerequisiti aggiornata. " * 80).strip()
    + "\n\n"
    + ("Sezione contenuti del corso aggiornata. " * 80).strip()
).encode("utf-8")


CDL_ID = 3  # LM-18 Informatica (per CLAUDE.md)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _step(n: int, label: str) -> None:
    print(f"\n=== [{n}] {label}")


def _persist_row(db, *, cdl_id: int, version: int, title: str, content: bytes) -> LocalDocument:
    """Mirror the upload-endpoint flow without going through HTTP."""
    normalized = title.lower()
    row = LocalDocument(
        cdl_id=cdl_id,
        document_type="usi_dipartimentali",
        academic_year="2025-2026",
        title=title,
        normalized_title=normalized,
        file_path="",
        file_extension=".md",
        file_hash="0" * 64,  # we don't care for the smoke, but the column is non-null
        file_size=len(content),
        version=version,
        enabled_criteria=["E5"],
        status="uploaded",
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()

    rel = f"{cdl_id}/{row.id}_v{version}.md"
    abs_path = Path(settings.local_documents_dir) / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(content)

    row.file_path = rel
    db.commit()
    db.refresh(row)
    return row


def _inspect_row(row: LocalDocument) -> None:
    print(
        f"   row.id={row.id} version={row.version} status={row.status} "
        f"chunk_count={row.chunk_count} enabled_criteria={row.enabled_criteria} "
        f"failure_reason={row.failure_reason}"
    )


def _ids_for(collection, document_id: int, version: int) -> list[str]:
    where = {
        "$and": [
            {"document_id": {"$eq": int(document_id)}},
            {"version": {"$eq": int(version)}},
        ]
    }
    res = collection.get(where=where, include=["metadatas"])
    ids = list(res.get("ids") or [])
    return sorted(ids)


def _summarise_chunk(collection, chunk_id: str, expected_dim: int) -> None:
    got = collection.get(ids=[chunk_id], include=["metadatas", "embeddings", "documents"])
    metadatas = got.get("metadatas")
    embeddings = got.get("embeddings")
    documents = got.get("documents")
    md = metadatas[0] if metadatas is not None and len(metadatas) else None
    emb = embeddings[0] if embeddings is not None and len(embeddings) else None
    doc = documents[0] if documents is not None and len(documents) else None
    assert md is not None, f"no metadata for {chunk_id}"
    assert emb is not None, f"no embedding for {chunk_id}"
    assert doc is not None, f"no document for {chunk_id}"
    print(f"   chunk_id={chunk_id}")
    print(f"     metadata keys: {sorted(md.keys())}")
    print(
        "     tag flags: "
        + ", ".join(f"{k}={md[k]}" for k in sorted(md) if k.startswith("tag_"))
    )
    print(f"     scalar-only metadata: {all(isinstance(v, (str, int, float, bool)) for v in md.values())}")
    print(f"     document length: {len(doc)} chars")
    print(f"     embedding dim: {len(emb)} (expected {expected_dim})")
    assert len(emb) == expected_dim, "unexpected embedding dimension"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print("Phase 8.B.2 — end-to-end smoke (REAL Vertex + REAL Chroma)")
    print(f"Vertex project / location: {settings.gcp_project_id} / {settings.gcp_location}")
    print(f"Chroma persist dir       : {settings.chroma_persist_dir}")
    print(f"Local docs dir           : {settings.local_documents_dir}")

    # Sanity: bail early with a friendly hint if Vertex isn't configured.
    try:
        project, location = settings.require_vertex_ai_config()
    except RuntimeError as exc:
        print(f"\nABORT: {exc}")
        return 2

    title = f"smoke_phase_8_b2_{int(time.time())}"
    print(f"Smoke title: {title!r}")

    db = SessionLocal()
    embeddings = VertexAIEmbeddings(project_id=project, location=location)
    chroma = chromadb.PersistentClient(path=str(settings.chroma_persist_dir))
    ingester = ExternalDocumentIngester(chroma, embeddings)
    collection = chroma.get_or_create_collection(name=DEFAULT_COLLECTION_NAME)
    service = LocalDocumentIndexingService(db, ingester)

    row_v1: LocalDocument | None = None
    row_v2: LocalDocument | None = None
    files_written: list[Path] = []

    try:
        # ------------------------------------------------------------------
        _step(0, "preconditions")
        cdl = db.query(CorsoDiLaurea).filter(CorsoDiLaurea.id == CDL_ID).first()
        assert cdl is not None, (
            f"CdL id={CDL_ID} not found. Run the scraper first or adjust CDL_ID."
        )
        print(f"   CdL: id={cdl.id} code={cdl.code} name={cdl.name}")

        # ------------------------------------------------------------------
        _step(1, "upload v1 -> row.status == 'uploaded'")
        row_v1 = _persist_row(
            db, cdl_id=CDL_ID, version=1, title=title, content=SMOKE_TEXT_V1,
        )
        files_written.append(Path(settings.local_documents_dir) / row_v1.file_path)
        _inspect_row(row_v1)
        assert row_v1.status == "uploaded"

        # ------------------------------------------------------------------
        _step(2, "service.index_document(v1) -> row.status == 'indexed'")
        result1 = service.index_document(row_v1.id)
        db.refresh(row_v1)
        _inspect_row(row_v1)
        print(
            f"   ingester result: chunks_written={result1.chunks_written} "
            f"chunks_deleted={result1.chunks_deleted} errors={result1.errors}"
        )
        assert row_v1.status == "indexed"
        assert row_v1.chunk_count == result1.chunks_written > 0
        assert row_v1.indexed_at is not None

        # ------------------------------------------------------------------
        _step(3, "Chroma inspection — IDs, metadata scalar, embedding dims")
        v1_ids = _ids_for(collection, row_v1.id, 1)
        print(f"   Chroma ids for v1: {len(v1_ids)}")
        for cid in v1_ids:
            assert cid.startswith(chunk_id_prefix(row_v1.id, 1)), (
                f"unexpected chunk id format: {cid}"
            )
        expected_dim = settings.scientific.embedding_output_dimensionality
        _summarise_chunk(collection, v1_ids[0], expected_dim)

        # ------------------------------------------------------------------
        _step(4, "reindex v1 -> no duplicates, count stable")
        result_re = service.index_document(row_v1.id)
        db.refresh(row_v1)
        v1_ids_after = _ids_for(collection, row_v1.id, 1)
        print(
            f"   reindex result: chunks_written={result_re.chunks_written} "
            f"chunks_deleted={result_re.chunks_deleted}"
        )
        print(f"   Chroma ids for v1 after reindex: {len(v1_ids_after)}")
        assert v1_ids == v1_ids_after, "chunk ids changed on idempotent reindex"
        assert row_v1.chunk_count == result_re.chunks_written

        # ------------------------------------------------------------------
        _step(5, "upload + index v2 -> v1 chunks survive")
        row_v2 = _persist_row(
            db, cdl_id=CDL_ID, version=2, title=title, content=SMOKE_TEXT_V2,
        )
        files_written.append(Path(settings.local_documents_dir) / row_v2.file_path)
        result2 = service.index_document(row_v2.id)
        db.refresh(row_v2)
        _inspect_row(row_v2)
        v1_ids_after_v2 = _ids_for(collection, row_v1.id, 1)
        v2_ids = _ids_for(collection, row_v2.id, 2)
        print(f"   Chroma ids: v1={len(v1_ids_after_v2)} v2={len(v2_ids)}")
        assert v1_ids == v1_ids_after_v2, (
            "v1 chunks must be unaffected by v2 indexing"
        )
        assert row_v2.chunk_count == result2.chunks_written

        # ------------------------------------------------------------------
        print("\nSMOKE OK")
        return 0

    except AssertionError as exc:
        print(f"\nSMOKE FAILED: assertion: {exc}")
        return 1
    except Exception as exc:
        print(f"\nSMOKE FAILED: {type(exc).__name__}: {exc}")
        return 1
    finally:
        # ------------------------------------------------------------------
        _step(99, "cleanup")
        # Chroma: delete-by-where for both versions.
        for r in (row_v1, row_v2):
            if r is None:
                continue
            for v in (r.version,):
                try:
                    collection.delete(
                        where={
                            "$and": [
                                {"document_id": {"$eq": int(r.id)}},
                                {"version": {"$eq": int(v)}},
                            ]
                        }
                    )
                except Exception as exc:
                    print(f"   cleanup chroma id={r.id} v={v}: {exc}")
        # Filesystem.
        for f in files_written:
            try:
                if f.exists():
                    f.unlink()
            except OSError as exc:
                print(f"   cleanup file {f}: {exc}")
        # Empty CdL dir if possible.
        try:
            (Path(settings.local_documents_dir) / str(CDL_ID)).rmdir()
        except OSError:
            pass
        # DB rows.
        for r in (row_v1, row_v2):
            if r is None:
                continue
            try:
                obj = db.query(LocalDocument).filter(LocalDocument.id == r.id).first()
                if obj is not None:
                    db.delete(obj)
                    db.commit()
            except Exception as exc:
                print(f"   cleanup db id={r.id}: {exc}")
        # Confirm Chroma is empty for the smoke document.
        for r in (row_v1, row_v2):
            if r is None:
                continue
            remaining = _ids_for(collection, r.id, r.version)
            print(f"   Chroma remaining for id={r.id} v={r.version}: {len(remaining)}")
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
