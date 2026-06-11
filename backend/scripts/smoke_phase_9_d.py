"""End-to-end smoke for Phase 9.D — extended detail + audit table UI surface.

Where Phase 9.C smoke exercised the *backend* extended-criteria
pipeline, this 9.D smoke exercises the *HTTP* surface the
frontend consumes:

  * ``GET /api/evaluations/{uuid}`` returns the compact,
    typed ``extended_criteria_result`` (no opaque ``agent_output``
    envelope leaked through);
  * ``external_documents_used`` carries the audit-table view
    joined with the live ``LocalDocument`` row (title +
    ``deleted_at`` flag);
  * a documented row that gets soft-deleted *after* the run still
    renders correctly in the historical detail: title present,
    ``deleted_at`` non-null, snapshot fields stable.

To make the run idempotent and to give the user a UI handle, the
script:

  1. seeds a fresh ``usi_dipartimentali`` document for the chosen
     syllabus's CdL and waits for indexing to complete (Vertex
     embed + Chroma persist);
  2. runs a real evaluation with the document available — A5
     fully invoked, E5 evaluated;
  3. polls the API and validates the response shape — first while
     the document is still live (title present, ``deleted_at``
     null), then again after DELETE-ing the document via the
     local-documents endpoint (title still present, ``deleted_at``
     non-null because the FK RESTRICT triggered the soft-delete
     fallback);
  4. holds before final cleanup, so the user can manually open
     the URL in the dev frontend and visually verify the panel
     (``--hold`` flag controls how long the hold lasts;
     0 by default for CI-style runs);
  5. hard-cleans up the audit row, the document on disk, and the
     Chroma chunks. The historical ``EvaluationResult`` row is
     preserved per the same policy as 9.C: it stays in history
     identifiable by its ``smoke_phase_9_d_<ts>`` document title.

How to run
----------

::

    cd backend
    uv run python scripts/smoke_phase_9_d.py --seuid <SEUID> --hold 120
"""
from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parent.parent))

import chromadb  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.local_documents.ingester import (  # noqa: E402
    DEFAULT_COLLECTION_NAME as EXTERNAL_COLLECTION,
)
from app.main import app  # noqa: E402
from app.models import EvaluationResult, Syllabus  # noqa: E402
from app.models.evaluation_external_document import (  # noqa: E402
    EvaluationExternalDocument,
)
from app.models.local_document import LocalDocument  # noqa: E402


SMOKE_E5_CONTENT = (
    "# Linee guida locali per la redazione dei syllabus (smoke 9.D)\n"
    "\n"
    "Sezione prerequisiti. Distinguere conoscenze culturali e generali "
    "da conoscenze disciplinari e specialistiche. Esplicitare le sezioni "
    "in elenchi brevi e leggibili.\n"
    "\n"
    "Sezione criteri di voto. Esplicitare i pesi tra scritto, orale e "
    "progetto e indicare almeno un esempio di domanda significativa.\n"
).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 9.D smoke")
    parser.add_argument(
        "--seuid",
        required=True,
        help="SEUID of a syllabus already in the DB (mandatory).",
    )
    parser.add_argument(
        "--hold",
        type=int,
        default=0,
        help=(
            "Seconds to keep the seeded document alive after smoke "
            "checks complete, so the user can manually open the dev "
            "frontend and inspect the UI panel. The script will then "
            "soft-delete the document, re-check, and cleanup."
        ),
    )
    parser.add_argument(
        "--preserve-history",
        action="store_true",
        help=(
            "Skip the final cleanup so the smoke leaves an inspectable "
            "demo run in the DB: the soft-deleted document, its audit row, "
            "the file on disk, the Chroma chunks AND the EvaluationResult "
            "all remain. Useful when you want to re-open the frontend "
            "later and re-verify the historical view of a soft-deleted "
            "document. Default (flag absent) is a full cleanup: the "
            "EvaluationResult is hard-deleted, which cascades to the "
            "audit row, the LocalDocument is then unreferenced and is "
            "hard-deleted with its file + Chroma chunks — so the smoke "
            "leaves zero trace in evaluation history."
        ),
    )
    args = parser.parse_args()

    print(f"=== Phase 9.D smoke — seuid={args.seuid} ===\n")

    with SessionLocal() as session:
        syllabus = (
            session.execute(select(Syllabus).where(Syllabus.seuid == args.seuid))
            .scalar_one_or_none()
        )
        if syllabus is None:
            print(f"[FAIL] syllabus seuid={args.seuid} not found")
            return 2
        if not syllabus.has_english:
            print(
                "[FAIL] selected syllabus has has_english=False; choose one "
                "with an English version so A5 can run E4 (the smoke wants a "
                "fully-active A5 surface)"
            )
            return 2
        cdl_id = int(syllabus.cdl_id)
        smoke_title = f"smoke_phase_9_d_{int(time.time())}__usi"
        incompatible = _active_e5_documents(cdl_id)
        if incompatible:
            print(
                "[FAIL] selected CdL already has E5 documents enabled; "
                "remove them so this smoke gets an isolated audit row:"
            )
            for d in incompatible:
                print(f"  - id={d.id} title={d.title!r}")
            return 2

    # Use TestClient as a context manager so the FastAPI lifespan
    # hooks fire (startup + shutdown) and the threaded scheduler
    # drains cleanly. Without the ``with`` block the script exits
    # while a background indexing task is still pending and prints
    # a noisy warning at teardown.
    failures: list[str] = []
    e5_doc_id: int | None = None
    evaluation_uuid: str | None = None
    with TestClient(app) as client:
        try:
            # 1. seed E5 document
            e5_doc_id = _seed_e5_document(
                client, cdl_id=cdl_id, smoke_title=smoke_title,
            )

            # 2. run a real evaluation through the HTTP API
            evaluation_uuid = _trigger_evaluation_and_wait(client, args.seuid)
            if evaluation_uuid is None:
                failures.append("evaluation did not complete in time")
                return _conclude(failures)

            # 3a. fetch the detail and validate the active shape
            failures.extend(
                _check_detail_active(
                    client, evaluation_uuid, e5_doc_id, smoke_title,
                )
            )

            # 4. optional human-in-the-loop pause
            if args.hold > 0 and not failures:
                print(
                    f"\n>>> Hold {args.hold}s — open the dev frontend at "
                    f"http://localhost:5173/evaluation/{evaluation_uuid} "
                    "and verify the panel. Press Ctrl+C to abort early."
                )
                try:
                    time.sleep(args.hold)
                except KeyboardInterrupt:
                    print("  hold interrupted; proceeding to soft-delete check")

            # 3b. soft-delete the document and validate the historical view
            if not failures:
                failures.extend(
                    _check_detail_soft_deleted(
                        client, evaluation_uuid, e5_doc_id,
                    )
                )
        finally:
            if args.preserve_history:
                _print_preserved_summary(
                    evaluation_uuid=evaluation_uuid,
                    e5_doc_id=e5_doc_id,
                )
            elif e5_doc_id is not None:
                _force_cleanup(
                    e5_doc_id=e5_doc_id,
                    evaluation_uuid=evaluation_uuid,
                )

    return _conclude(failures)


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


def _active_e5_documents(cdl_id: int) -> list[LocalDocument]:
    with SessionLocal() as session:
        return (
            session.query(LocalDocument)
            .filter(
                LocalDocument.cdl_id == cdl_id,
                LocalDocument.status == "indexed",
                LocalDocument.deleted_at.is_(None),
            )
            .all()
        ) or []


def _seed_e5_document(
    client: TestClient, *, cdl_id: int, smoke_title: str,
) -> int:
    files = {
        "file": (
            f"{smoke_title}.md",
            io.BytesIO(SMOKE_E5_CONTENT),
            "text/markdown",
        ),
    }
    form = {
        "cdl_id": str(cdl_id),
        "document_type": "usi_dipartimentali",
        "title": smoke_title,
        "academic_year": "2025-2026",
        "enabled_criteria": "E5",
    }
    response = client.post("/api/local-documents", files=files, data=form)
    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"E5 seed failed: {response.status_code} {response.text[:300]}"
        )
    doc_id = int(response.json()["document"]["id"])
    deadline = time.time() + 60
    while time.time() < deadline:
        with SessionLocal() as session:
            row = session.query(LocalDocument).filter_by(id=doc_id).one()
            if row.status == "indexed":
                print(
                    f"  [OK] seeded E5 doc id={doc_id} title={smoke_title!r} "
                    f"chunks={row.chunk_count}"
                )
                return doc_id
            if row.status == "failed":
                raise RuntimeError(
                    f"E5 seed failed: {row.failure_reason}"
                )
        time.sleep(1.0)
    raise RuntimeError("E5 seed timeout before indexed")


def _trigger_evaluation_and_wait(
    client: TestClient, seuid: str, *, timeout_s: int = 600,
) -> str | None:
    response = client.post(f"/api/evaluate/{seuid}")
    response.raise_for_status()
    evaluation_uuid = response.json()["evaluation_uuid"]
    print(f"  evaluation kicked off: {evaluation_uuid}")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        body = client.get(f"/api/evaluations/{evaluation_uuid}").json()
        status = body.get("status")
        if status in ("completed", "partial", "failed"):
            print(f"  [OK] evaluation reached terminal status={status}")
            return evaluation_uuid
        time.sleep(2.5)
    return None


def _check_detail_active(
    client: TestClient, evaluation_uuid: str, e5_doc_id: int, smoke_title: str,
) -> list[str]:
    """Validate the detail payload while the document is still active."""
    print("\n--- 9.D check 1: active document ---")
    body = client.get(f"/api/evaluations/{evaluation_uuid}").json()
    fails: list[str] = []

    ext = body.get("extended_criteria_result")
    if ext is None:
        fails.append("extended_criteria_result is None on a 9.C+ run")
        return fails

    # Compact normalization: agent_output must NOT appear at the top.
    if "agent_output" in ext:
        fails.append(
            "extended_criteria_result still carries the opaque agent_output "
            "envelope (compact normalization 9.D.1 should have lifted "
            "judgments and handler_prompt_versions)"
        )
    if not isinstance(ext.get("judgments"), list):
        fails.append("extended_criteria_result.judgments is not a list")
    if ext.get("handler_prompt_versions", {}).get("E5") != "e5_v1":
        fails.append(
            f"E5 prompt version not 'e5_v1': "
            f"{ext.get('handler_prompt_versions', {}).get('E5')!r}"
        )

    docs = body.get("external_documents_used") or []
    if len(docs) != 1:
        fails.append(
            f"external_documents_used should have 1 row; got {len(docs)}"
        )
        return fails
    row = docs[0]

    if row["criterion_code"] != "E5":
        fails.append(f"audit row criterion_code = {row['criterion_code']!r}, expected E5")
    if row["local_document_id"] != e5_doc_id:
        fails.append(
            f"audit row local_document_id = {row['local_document_id']} "
            f"vs expected {e5_doc_id}"
        )
    if row["document_type"] != "usi_dipartimentali":
        fails.append(f"document_type = {row['document_type']!r}")
    if row["title"] != smoke_title:
        fails.append(f"title = {row['title']!r} vs expected {smoke_title!r}")
    if row["deleted_at"] is not None:
        fails.append(
            f"deleted_at should be None while document is active; got {row['deleted_at']!r}"
        )
    if not row["file_hash"]:
        fails.append("file_hash empty")
    if row["document_version"] != 1:
        fails.append(f"document_version = {row['document_version']}")
    if row["resolution_reason"] not in (
        "explicit_selection", "academic_year_match", "latest_available_fallback",
    ):
        fails.append(f"resolution_reason = {row['resolution_reason']!r}")

    # Verify the E5 judgment honours the dual-source rule when numeric.
    e5_judgment = next(
        (j for j in ext["judgments"] if j["criterion_code"] == "E5"), None,
    )
    if e5_judgment is None:
        fails.append("E5 judgment missing")
    elif not e5_judgment["is_na"]:
        evs = e5_judgment["evidences"]
        has_syllabus = any(e.get("source_field") for e in evs)
        has_external = any(e.get("source_document_id") is not None for e in evs)
        if not (has_syllabus and has_external):
            fails.append(
                "E5 numeric judgment violates dual-source rule "
                "(missing syllabus or external evidence)"
            )

    if not fails:
        print(
            f"  [OK] active doc: title={row['title']!r} "
            f"hash={row['file_hash'][:7]} reason={row['resolution_reason']}"
        )
    return fails


def _check_detail_soft_deleted(
    client: TestClient, evaluation_uuid: str, e5_doc_id: int,
) -> list[str]:
    """DELETE the document, then check that the run still reads it."""
    print("\n--- 9.D check 2: soft-delete fallback ---")
    fails: list[str] = []

    response = client.delete(f"/api/local-documents/{e5_doc_id}")
    if response.status_code not in (200, 204):
        fails.append(
            f"DELETE returned {response.status_code}: {response.text[:200]}"
        )
        return fails

    with SessionLocal() as session:
        doc = session.query(LocalDocument).filter_by(id=e5_doc_id).one_or_none()
    if doc is None:
        fails.append(
            "document was hard-deleted despite being referenced "
            "(FK RESTRICT should have prevented this)"
        )
        return fails
    if doc.deleted_at is None:
        fails.append("deleted_at is None after DELETE (soft-delete did not fire)")
        return fails

    body = client.get(f"/api/evaluations/{evaluation_uuid}").json()
    docs = body.get("external_documents_used") or []
    if len(docs) != 1:
        fails.append(f"external_documents_used count = {len(docs)}")
        return fails
    row = docs[0]
    if row["title"] is None:
        fails.append("title disappeared after soft-delete (should still be readable)")
    if row["deleted_at"] is None:
        fails.append("deleted_at is None in the API payload after soft-delete")
    if not fails:
        print(
            f"  [OK] soft-delete preserved title={row['title']!r} "
            f"deleted_at={row['deleted_at']}"
        )
    return fails


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


def _force_cleanup(
    *, e5_doc_id: int, evaluation_uuid: str | None,
) -> None:
    """Hard-cleanup the full smoke trail.

    Order matters: deleting the ``EvaluationResult`` first lets the
    audit row CASCADE-delete automatically (FK
    ``evaluation_result_id ON DELETE CASCADE``); the
    ``LocalDocument`` is then unreferenced and can be hard-deleted
    despite the audit-side ``RESTRICT`` FK; finally we drop the file
    on disk and the Chroma chunks.

    The smoke is supposed to leave zero trace in evaluation history
    when this branch runs. The ``--preserve-history`` flag selects
    the opposite policy.
    """
    print(f"\n  Cleanup: hard-removing smoke trail (doc id={e5_doc_id})")
    file_rel_path: str | None = None
    with SessionLocal() as session:
        # Force FK constraints on so the CASCADE actually fires
        # on SQLite (engine-level setting is off by default).
        session.execute(_pragma_fk_on())

        # Delete the EvaluationResult so the audit row cascades.
        if evaluation_uuid is not None:
            evaluation = (
                session.query(EvaluationResult)
                .filter_by(evaluation_uuid=evaluation_uuid)
                .one_or_none()
            )
            if evaluation is not None:
                session.delete(evaluation)
                session.flush()

        # Defensive: if the cascade didn't fire (older SQLite,
        # non-FK driver, ...), drop any audit row that still points
        # at the temp doc.
        session.query(EvaluationExternalDocument).filter_by(
            local_document_id=e5_doc_id,
        ).delete(synchronize_session=False)

        # Hard-delete the LocalDocument (file path captured first).
        doc = (
            session.query(LocalDocument).filter_by(id=e5_doc_id).one_or_none()
        )
        if doc is not None:
            file_rel_path = doc.file_path
            session.delete(doc)
        session.commit()

    if file_rel_path:
        full = Path(settings.local_documents_dir).resolve() / file_rel_path
        if full.exists():
            try:
                full.unlink()
            except OSError as exc:
                print(f"  [WARN] could not remove file {full}: {exc}")
    try:
        chroma = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        collection = chroma.get_collection(EXTERNAL_COLLECTION)
        collection.delete(where={"document_id": {"$eq": int(e5_doc_id)}})
    except Exception as exc:  # noqa: BLE001 — cleanup best-effort
        print(f"  [WARN] Chroma cleanup skipped: {exc}")


def _print_preserved_summary(
    *, evaluation_uuid: str | None, e5_doc_id: int | None,
) -> None:
    print("\n  Cleanup skipped (--preserve-history).")
    print(
        "  The smoke trail is left in place so the soft-deleted view "
        "remains inspectable:"
    )
    if evaluation_uuid is not None:
        print(f"   - EvaluationResult: {evaluation_uuid}")
    if e5_doc_id is not None:
        print(
            f"   - LocalDocument: id={e5_doc_id} (deleted_at set, file on disk and "
            "Chroma chunks preserved)"
        )
    print(
        "  Re-run with the cleanup default (no flag) when you no longer "
        "need the demo data."
    )


def _pragma_fk_on():
    """Return a SQLAlchemy ``text()`` enabling SQLite FK constraints."""
    from sqlalchemy import text  # imported lazily to keep top imports small
    return text("PRAGMA foreign_keys=ON")


def _conclude(failures: list[str]) -> int:
    if failures:
        print("\n=== SMOKE FAILED ===")
        for f in failures:
            print(f"  [FAIL] {f}")
        return 1
    print("\n=== 9.D SMOKE GREEN ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
