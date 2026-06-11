"""End-to-end smoke for Phase 9.C — A5 ExternalConsistencyAgent.

Exercises the real production wiring (Vertex + Chroma + SQLite +
LangGraph) along the five scenarios agreed with the user before
opening the Phase 9.C PR:

  1. ``no_docs_no_en``  — syllabus with ``has_english=False`` and an
     empty registry: every E1..E5 must be resolver hard-NA, A5
     handlers must NOT be invoked, ``extended_result.status`` must
     still be ``completed`` (per the C.1.fix all-resolver-NA rule).

  2. ``en_only``        — syllabus with ``has_english=True`` and an
     empty registry: only E4 reaches its handler (paired-prefix
     check), E1/E2/E3/E5 stay resolver-NA, NO audit row is
     persisted.

  3. ``e5_doc``         — a temporary ``usi_dipartimentali``
     document seeded into the registry, indexed in Chroma:
     E5 is evaluated for real, the audit table carries one row,
     ``extended_criteria_result`` is persisted with the right
     handler_prompt_versions and a non-trivial judgment.

  4. ``core_isolation`` — deterministic recalculation: for every
     run produced above, verify that
       * ``criterion_scores`` contains exactly C1..C9,
       * ``core_score`` equals the arithmetic mean of the non-NA
         C1..C9 entries,
       * ``coverage`` equals ``(non-NA C1..C9 count) / 9``,
       * no E* score is folded into the core,
       * ``extended_criteria_result`` is structurally separate.
     This proves the invariant *without* comparing CoreScores
     across LLM runs (which would be confounded by stochasticity).

  5. ``soft_delete``    — DELETE the temp document seeded in (3)
     after the run completed: the registry endpoint must perform a
     soft-delete (``deleted_at`` set) rather than a hard-delete,
     because the audit row references it. The file on disk and
     the Chroma chunks must survive.

Cost
----

Three real evaluations against Vertex (one per evaluating
scenario). Each run executes A1..A4 plus the A5 handlers that
the resolver flagged applicable for that scenario. A bounded
embedding round-trip happens for the E5 document indexing in
scenario 3.

Cleanup
-------

After the smoke completes (success OR failure), the script:

  * restores the syllabus's ``has_english`` flag;
  * hard-deletes the temporary E5 document — including its audit
    row, the file on disk, and the Chroma chunks. The historical
    ``EvaluationResult`` rows are intentionally preserved per the
    user's instruction ("Le evaluation create possono restare
    nello storico, purché chiaramente identificabili come smoke").

The temp document is created with a unique title
``smoke_phase_9_c_<timestamp>__e5_local_usage`` so it can never
collide with a real registry row.

How to run
----------

::

    cd backend
    # Requires GCP_PROJECT_ID set in backend/.env, plus a syllabus
    # already in the DB. We default to the non-LM-18 syllabus the
    # team used during the SDK migration; override with --seuid.
    uv run python scripts/smoke_phase_9_c.py --seuid <SEUID>
"""
from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path
from typing import Any

# Path bootstrap so the script can import the app package.
_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parent.parent))

import chromadb  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.evaluation.agents.llm_client import VertexAILLMClient  # noqa: E402
from app.evaluation.orchestrator import build_graph  # noqa: E402
from app.evaluation.rag.embeddings import VertexAIEmbeddings  # noqa: E402
from app.evaluation.rag.external_retriever import (  # noqa: E402
    ExternalDocumentRetriever,
)
from app.evaluation.rag.retriever import NormativeRetriever  # noqa: E402
from app.evaluation.service import EvaluationService  # noqa: E402
from app.local_documents.ingester import (  # noqa: E402
    DEFAULT_COLLECTION_NAME as EXTERNAL_COLLECTION,
)
from app.main import app  # noqa: E402
from app.models import EvaluationResult, Syllabus  # noqa: E402
from app.models.evaluation_external_document import (  # noqa: E402
    EvaluationExternalDocument,
)
from app.models.local_document import LocalDocument  # noqa: E402


# No safe default: the user MUST pass --seuid pointing to a syllabus
# already present in the local DB. The script will temporarily flip
# the ``has_english`` flag on that row during scenario 1 and restore
# it in the ``finally`` block. Pick a syllabus OUTSIDE the LM-18
# scientific dataset whenever possible so smoke runs don't pollute
# the calibration history.

# A short Italian text used as the temporary E5 local-usage
# document. Small enough to produce a single chunk; non-trivial
# enough that the retriever can pull above the similarity threshold.
SMOKE_E5_CONTENT = (
    "# Linee guida locali per la redazione dei syllabus (smoke 9.C)\n"
    "\n"
    "Sezione prerequisiti. È buona prassi distinguere conoscenze "
    "culturali / generali da conoscenze disciplinari / specialistiche, "
    "e renderle esplicite all'inizio della sezione.\n"
    "\n"
    "Sezione criteri di voto. Esplicitare i pesi delle componenti "
    "(scritto, orale, progetto) e l'eventuale modalità di recupero. "
    "Indicare almeno un esempio di domanda.\n"
).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 9.C smoke")
    parser.add_argument(
        "--seuid",
        required=True,
        help=(
            "SEUID of a syllabus already in the DB (mandatory). The "
            "script will temporarily flip has_english=False on it for "
            "scenario 1 and restore the original value at the end."
        ),
    )
    parser.add_argument(
        "--cdl-id",
        type=int,
        default=None,
        help=(
            "Override the CdL id used to seed the temp E5 document. "
            "Defaults to the syllabus's own cdl_id."
        ),
    )
    args = parser.parse_args()

    print(f"=== Phase 9.C smoke — seuid={args.seuid} ===\n")

    with SessionLocal() as session:
        syllabus = (
            session.execute(select(Syllabus).where(Syllabus.seuid == args.seuid))
            .scalar_one_or_none()
        )
        if syllabus is None:
            print(f"[FAIL] syllabus seuid={args.seuid} not found in DB")
            return 2
        cdl_id = int(args.cdl_id or syllabus.cdl_id)
        original_has_english = bool(syllabus.has_english)
        smoke_title = f"smoke_phase_9_c_{int(time.time())}__e5_local_usage"

    if cdl_id != int(syllabus.cdl_id):
        print(
            f"[FAIL] --cdl-id={cdl_id} differs from the syllabus cdl_id="
            f"{syllabus.cdl_id}; the resolver would not see the seeded E5 document"
        )
        return 2
    if not original_has_english:
        print(
            "[FAIL] selected syllabus has has_english=False; choose one with an "
            "English version so scenario 'en_only' can exercise E4"
        )
        return 2
    incompatible_docs = _active_applicable_documents(cdl_id)
    if incompatible_docs:
        print(
            "[FAIL] selected CdL already has indexed documents enabled for "
            "extended criteria; the no-doc scenarios would not be isolated:"
        )
        for doc in incompatible_docs:
            print(
                f"  - id={doc.id} type={doc.document_type} "
                f"title={doc.title!r} enabled_criteria={doc.enabled_criteria}"
            )
        print("No rows were changed. Choose a syllabus from a CdL with an empty registry.")
        return 2

    service = _build_service()
    client = TestClient(app)

    failures: list[str] = []
    runs_to_audit: list[str] = []  # evaluation_uuids for scenario 4

    e5_doc_id: int | None = None
    try:
        # ---------- Scenario 1: no_docs_no_en ----------
        _set_has_english(args.seuid, False)
        try:
            evaluation_uuid_1, scenario_1_fails = _scenario_no_docs_no_en(
                service, args.seuid,
            )
            failures.extend(scenario_1_fails)
            runs_to_audit.append(evaluation_uuid_1)
            if scenario_1_fails:
                print("  [ABORT] stopping after scenario 1 to avoid invalid/costly follow-ups")
                return 1
        finally:
            _set_has_english(args.seuid, original_has_english)

        # ---------- Scenario 2: en_only ----------
        evaluation_uuid_2, scenario_2_fails = _scenario_en_only(
            service, args.seuid,
        )
        failures.extend(scenario_2_fails)
        runs_to_audit.append(evaluation_uuid_2)
        if scenario_2_fails:
            print("  [ABORT] stopping after scenario 2 to avoid invalid/costly follow-ups")
            return 1

        # ---------- Scenario 3: e5_doc ----------
        e5_doc_id = _seed_e5_document(
            client, cdl_id=cdl_id, smoke_title=smoke_title,
        )
        evaluation_uuid_3, scenario_3_fails = _scenario_e5_doc(
            service, args.seuid, e5_doc_id,
        )
        failures.extend(scenario_3_fails)
        runs_to_audit.append(evaluation_uuid_3)
        if scenario_3_fails:
            print("  [ABORT] stopping after scenario 3; cleanup will still run")
            return 1

        # ---------- Scenario 4: core_isolation ----------
        failures.extend(_scenario_core_isolation(runs_to_audit))

        # ---------- Scenario 5: soft_delete ----------
        failures.extend(_scenario_soft_delete(client, e5_doc_id))

    finally:
        # Always restore has_english to its original value.
        _set_has_english(args.seuid, original_has_english)
        # Hard-cleanup of the temp E5 document (audit rows + DB + file + chunks).
        if e5_doc_id is not None:
            _force_cleanup_e5_document(e5_doc_id)

    if failures:
        print("\n=== SMOKE FAILED ===")
        for f in failures:
            print(f"  [FAIL] {f}")
        return 1
    print("\n=== ALL FIVE SCENARIOS GREEN ===")
    return 0


# ---------------------------------------------------------------------------
# Production wiring
# ---------------------------------------------------------------------------


def _build_service() -> EvaluationService:
    project_id, location = settings.require_vertex_ai_config()
    sci = settings.scientific
    chroma = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    embeddings = VertexAIEmbeddings(
        project_id=project_id,
        location=location,
        model_name=sci.embedding_model,
        output_dimensionality=sci.embedding_output_dimensionality,
    )
    retriever = NormativeRetriever(chroma, embeddings, sci)
    external_retriever = ExternalDocumentRetriever(chroma, embeddings, sci)
    llm_client = VertexAILLMClient(
        project_id=project_id, location=location, scientific=sci,
    )

    def _graph_invoker(
        initial_state: dict[str, Any],
        *,
        progress_publisher: Any | None = None,
    ) -> dict[str, Any]:
        graph = build_graph(
            retriever=retriever,
            llm_client=llm_client,
            external_retriever=external_retriever,
            progress_publisher=progress_publisher,
        )
        return graph.invoke(initial_state)

    return EvaluationService(
        session_factory=SessionLocal,
        graph_invoker=_graph_invoker,
        settings=settings,
    )


def _set_has_english(seuid: str, value: bool) -> None:
    with SessionLocal() as session:
        syl = session.query(Syllabus).filter_by(seuid=seuid).one()
        syl.has_english = bool(value)
        session.commit()


def _active_applicable_documents(cdl_id: int) -> list[LocalDocument]:
    """Return registry rows that would invalidate the no-document scenarios.

    This is deliberately read-only. The smoke must never disable, delete, or
    re-tag real registry documents merely to manufacture an isolated fixture.
    """
    with SessionLocal() as session:
        rows = (
            session.query(LocalDocument)
            .filter_by(cdl_id=cdl_id, status="indexed")
            .filter(LocalDocument.deleted_at.is_(None))
            .all()
        )
        applicable = [row for row in rows if row.enabled_criteria]
        for row in applicable:
            session.expunge(row)
        return applicable


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def _scenario_no_docs_no_en(
    service: EvaluationService, seuid: str,
) -> tuple[str, list[str]]:
    print("--- Scenario 1: no_docs_no_en ---")
    record = service.evaluate(seuid)
    fails = _core_health_failures(record, "scenario_1")
    ext = record.extended_criteria_result
    if ext is None:
        fails.append("scenario_1: extended_criteria_result is None")
        return record.evaluation_uuid, fails

    if set(ext["criterion_scores"].keys()) != {"E1", "E2", "E3", "E4", "E5"}:
        fails.append(
            f"scenario_1: criterion_scores keys = "
            f"{sorted(ext['criterion_scores'].keys())}, expected E1..E5"
        )
    if any(v is not None for v in ext["criterion_scores"].values()):
        fails.append(
            f"scenario_1: expected all None, got {ext['criterion_scores']}"
        )
    sources = {n["source"] for n in ext["na_criteria"]}
    if sources != {"resolver"}:
        fails.append(
            f"scenario_1: na_criteria sources = {sorted(sources)}, "
            f"expected only 'resolver'"
        )
    if ext["status"] != "completed":
        fails.append(
            f"scenario_1: extended.status = {ext['status']!r}, expected 'completed'"
        )
    # No handler should have been invoked: handler_prompt_versions must be empty.
    versions = (ext.get("agent_output") or {}).get("handler_prompt_versions") or {}
    if versions:
        fails.append(
            f"scenario_1: handler_prompt_versions non-empty: {versions}"
        )
    # And no audit row for this run.
    with SessionLocal() as session:
        audit_count = (
            session.query(EvaluationExternalDocument)
            .filter_by(evaluation_result_id=record.id)
            .count()
        )
    if audit_count != 0:
        fails.append(
            f"scenario_1: {audit_count} audit rows persisted (expected 0)"
        )

    _print_scenario_summary(record, fails, "no_docs_no_en")
    return record.evaluation_uuid, fails


def _scenario_en_only(
    service: EvaluationService, seuid: str,
) -> tuple[str, list[str]]:
    print("\n--- Scenario 2: en_only ---")
    record = service.evaluate(seuid)
    fails = _core_health_failures(record, "scenario_2")
    ext = record.extended_criteria_result
    if ext is None:
        fails.append("scenario_2: extended_criteria_result is None")
        return record.evaluation_uuid, fails

    # Only E4 should be in handler_prompt_versions (the others were
    # resolver-NA because there are no documents in the registry).
    versions = (ext.get("agent_output") or {}).get("handler_prompt_versions") or {}
    if set(versions.keys()) != {"E4"}:
        fails.append(
            f"scenario_2: handler_prompt_versions keys = {sorted(versions.keys())}, "
            f"expected just E4"
        )
    if ext["status"] != "completed":
        fails.append(
            f"scenario_2: extended.status = {ext['status']!r}, expected 'completed'"
        )
    # The four registry-served criteria must be resolver-NA.
    for code in ("E1", "E2", "E3", "E5"):
        score = ext["criterion_scores"].get(code)
        if score is not None:
            fails.append(
                f"scenario_2: {code} score = {score} (expected None / resolver-NA)"
            )
    # E4 outcome can be 0/1/2 OR NA semantic — either is acceptable.
    e4_score = ext["criterion_scores"].get("E4")
    e4_na = next(
        (n for n in ext["na_criteria"] if n["criterion_code"] == "E4"), None,
    )
    if e4_score is None and e4_na is None:
        fails.append(
            "scenario_2: E4 has no score AND no na_criteria entry"
        )

    # No audit row anywhere.
    with SessionLocal() as session:
        audit_count = (
            session.query(EvaluationExternalDocument)
            .filter_by(evaluation_result_id=record.id)
            .count()
        )
    if audit_count != 0:
        fails.append(
            f"scenario_2: {audit_count} audit rows persisted (expected 0)"
        )

    _print_scenario_summary(record, fails, "en_only")
    return record.evaluation_uuid, fails


def _scenario_e5_doc(
    service: EvaluationService, seuid: str, e5_doc_id: int,
) -> tuple[str, list[str]]:
    print("\n--- Scenario 3: e5_doc ---")
    record = service.evaluate(seuid)
    fails = _core_health_failures(record, "scenario_3")
    ext = record.extended_criteria_result
    if ext is None:
        fails.append("scenario_3: extended_criteria_result is None")
        return record.evaluation_uuid, fails

    # E5 must appear in handler_prompt_versions.
    versions = (ext.get("agent_output") or {}).get("handler_prompt_versions") or {}
    if "E5" not in versions:
        fails.append(
            f"scenario_3: E5 missing from handler_prompt_versions: {sorted(versions.keys())}"
        )
    if ext["status"] != "completed":
        fails.append(
            f"scenario_3: extended.status = {ext['status']!r}, expected 'completed'"
        )

    # An audit row must exist for E5 with the right document id.
    with SessionLocal() as session:
        rows = (
            session.query(EvaluationExternalDocument)
            .filter_by(evaluation_result_id=record.id, criterion_code="E5")
            .all()
        )
    if len(rows) != 1:
        fails.append(
            f"scenario_3: {len(rows)} audit rows for E5 (expected 1)"
        )
    elif rows[0].local_document_id != e5_doc_id:
        fails.append(
            f"scenario_3: audit row local_document_id = "
            f"{rows[0].local_document_id} (expected {e5_doc_id})"
        )

    # Dual-source check on the E5 judgment if it's numeric. If the
    # handler returned NA, the rule is exempt.
    e5_judgment = _judgment_for(ext["agent_output"], "E5")
    if e5_judgment is None:
        fails.append("scenario_3: E5 judgment missing from agent_output")
    elif not e5_judgment.get("is_na", True):
        evs = e5_judgment.get("evidences") or []
        has_syllabus = any(e.get("source_field") for e in evs)
        has_external = any(e.get("source_document_id") is not None for e in evs)
        if not (has_syllabus and has_external):
            fails.append(
                "scenario_3: E5 numeric judgment violates dual-source "
                "(missing syllabus or external evidence)"
            )

    _print_scenario_summary(record, fails, "e5_doc")
    return record.evaluation_uuid, fails


def _scenario_core_isolation(evaluation_uuids: list[str]) -> list[str]:
    print("\n--- Scenario 4: core_isolation ---")
    fails: list[str] = []
    expected_core_codes = {"C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"}
    with SessionLocal() as session:
        for uuid in evaluation_uuids:
            record = (
                session.query(EvaluationResult)
                .filter_by(evaluation_uuid=uuid)
                .one()
            )
            cs = record.criterion_scores or {}
            keys = set(cs.keys())
            if keys != expected_core_codes:
                fails.append(
                    f"core_isolation[{uuid}]: criterion_scores keys = "
                    f"{sorted(keys)}, expected exactly C1..C9"
                )
                continue
            non_na = [v for v in cs.values() if v is not None]
            expected_coverage = round(len(non_na) / 9.0, 6)
            actual_coverage = round(record.coverage, 6) if record.coverage is not None else None
            if actual_coverage != expected_coverage:
                fails.append(
                    f"core_isolation[{uuid}]: coverage = {actual_coverage} "
                    f"vs expected {expected_coverage} (={len(non_na)}/9)"
                )
            if non_na:
                # The production aggregator intentionally persists
                # CoreScore rounded to two decimals.
                expected_core = round(sum(non_na) / len(non_na), 2)
                actual_core = (
                    round(record.core_score, 2)
                    if record.core_score is not None
                    else None
                )
                if actual_core != expected_core:
                    fails.append(
                        f"core_isolation[{uuid}]: core_score = {actual_core} "
                        f"vs expected {expected_core} (mean of {non_na})"
                    )
            # extended_criteria_result must be JSON-separated.
            if record.extended_criteria_result is None:
                fails.append(
                    f"core_isolation[{uuid}]: extended_criteria_result is None"
                )
            else:
                ext_keys = set(record.extended_criteria_result.get(
                    "criterion_scores", {}
                ).keys())
                if ext_keys & expected_core_codes:
                    fails.append(
                        f"core_isolation[{uuid}]: extended_criteria_result "
                        f"contains core codes: {ext_keys & expected_core_codes}"
                    )
    if not fails:
        print("  [OK] CoreScore + coverage + isolation invariants hold")
    return fails


def _scenario_soft_delete(client: TestClient, e5_doc_id: int) -> list[str]:
    print("\n--- Scenario 5: soft_delete ---")
    fails: list[str] = []

    # The DELETE endpoint must succeed and the row must be soft-deleted.
    response = client.delete(f"/api/local-documents/{e5_doc_id}")
    if response.status_code not in (200, 204):
        fails.append(
            f"scenario_5: DELETE returned {response.status_code}: {response.text[:200]}"
        )
        return fails

    with SessionLocal() as session:
        doc = (
            session.query(LocalDocument)
            .filter_by(id=e5_doc_id)
            .one_or_none()
        )
    if doc is None:
        fails.append(
            "scenario_5: document was hard-deleted despite being referenced "
            "by an audit row (FK RESTRICT should have prevented this)"
        )
        return fails
    if doc.deleted_at is None:
        fails.append(
            "scenario_5: document row still present but deleted_at is None "
            "(soft-delete fallback did not fire)"
        )
    # File on disk must survive the soft-delete.
    file_path = _absolute_storage_path(doc.file_path)
    if not file_path.exists():
        fails.append(
            f"scenario_5: file {file_path} removed despite soft-delete"
        )
    # Chroma chunks must survive too.
    if _chroma_chunk_count_for_document(e5_doc_id) == 0:
        fails.append(
            "scenario_5: Chroma chunks for the document were purged "
            "despite the soft-delete"
        )

    if not fails:
        print("  [OK] soft-delete applied; file and chunks preserved")
    return fails


# ---------------------------------------------------------------------------
# E5 document seeding / cleanup
# ---------------------------------------------------------------------------


def _seed_e5_document(
    client: TestClient, *, cdl_id: int, smoke_title: str,
) -> int:
    """Upload a synthetic ``usi_dipartimentali`` document via the API.

    The endpoint runs the async pipeline (extract -> chunk -> index)
    and returns the row right away with status ``uploaded``. We
    then poll the DB until ``status=='indexed'`` so the retriever
    will find chunks for the run.
    """
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
        # The upload endpoint accepts a comma-separated multipart form
        # field, not a JSON-encoded list.
        "enabled_criteria": "E5",
    }
    response = client.post(
        "/api/local-documents", files=files, data=form,
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"E5 seed failed: {response.status_code} {response.text[:300]}"
        )
    body = response.json()
    doc_id = int(body.get("document", body).get("id"))

    deadline = time.time() + 60
    while time.time() < deadline:
        with SessionLocal() as session:
            doc = session.query(LocalDocument).filter_by(id=doc_id).one()
            if doc.status == "indexed":
                print(
                    f"  [OK] seeded E5 doc id={doc_id} title={smoke_title!r} "
                    f"(version={doc.version}, chunks={doc.chunk_count})"
                )
                return doc_id
            if doc.status == "failed":
                raise RuntimeError(
                    f"E5 seed failed during indexing: {doc.failure_reason}"
                )
        time.sleep(1.0)
    raise RuntimeError("E5 seed timed out before reaching status=indexed")


def _force_cleanup_e5_document(e5_doc_id: int) -> None:
    """Hard-delete the temp E5 document and everything that points to it.

    Steps:
      1. drop the audit rows referencing the document so the FK
         RESTRICT releases the LocalDocument row;
      2. fetch the document, remember the file path;
      3. delete the document row;
      4. unlink the file on disk;
      5. drop the matching Chroma chunks from the external_documents
         collection (any chunk_id beginning with ``external_{id}_``).

    The EvaluationResult rows that triggered the soft-delete remain
    in place — per the user's instruction, smoke runs are allowed to
    persist in history as long as they are clearly identifiable.
    """
    print(f"  Cleanup: hard-removing temp E5 document id={e5_doc_id} ...")
    with SessionLocal() as session:
        session.query(EvaluationExternalDocument).filter_by(
            local_document_id=e5_doc_id,
        ).delete(synchronize_session=False)
        doc = session.query(LocalDocument).filter_by(id=e5_doc_id).one_or_none()
        file_rel_path = doc.file_path if doc else None
        if doc is not None:
            session.delete(doc)
        session.commit()
    if file_rel_path:
        full = _absolute_storage_path(file_rel_path)
        if full.exists():
            try:
                full.unlink()
            except OSError as exc:
                print(f"  [WARN] could not remove file {full}: {exc}")
    try:
        chroma = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        collection = chroma.get_collection(EXTERNAL_COLLECTION)
        # The ingester names chunks ``external_<doc_id>_v<version>__chunk_<n>``.
        # Use the where filter on document_id metadata for robustness.
        collection.delete(where={"document_id": {"$eq": int(e5_doc_id)}})
    except Exception as exc:  # noqa: BLE001 — cleanup best-effort
        print(f"  [WARN] Chroma cleanup skipped: {exc}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _core_health_failures(
    record: EvaluationResult, scenario: str,
) -> list[str]:
    """Require a healthy C1-C9 run before accepting any A5 assertion.

    The evaluation graph deliberately degrades to a persisted result
    when core agents fail. That behaviour is useful in production, but
    a real E2E smoke must not call such a degraded run green.
    """
    failures: list[str] = []
    if record.status != "completed":
        failures.append(
            f"{scenario}: core status = {record.status!r}, expected 'completed'"
        )
    if record.agent_errors:
        failures.append(
            f"{scenario}: core agent_errors is not empty: {record.agent_errors}"
        )
    if record.core_score is None:
        failures.append(f"{scenario}: core_score is None")
    if record.coverage is None:
        failures.append(f"{scenario}: coverage is None")
    return failures


def _judgment_for(agent_output: dict | None, code: str) -> dict | None:
    if not agent_output:
        return None
    for j in agent_output.get("judgments") or []:
        if j.get("criterion_code") == code:
            return j
    return None


def _absolute_storage_path(rel_path: str) -> Path:
    """Map a registry ``file_path`` (relative) to a real filesystem path."""
    storage_root = Path(settings.local_documents_dir).resolve()
    return storage_root / rel_path


def _chroma_chunk_count_for_document(doc_id: int) -> int:
    try:
        chroma = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        collection = chroma.get_collection(EXTERNAL_COLLECTION)
        result = collection.get(where={"document_id": {"$eq": int(doc_id)}})
        return len(result.get("ids") or [])
    except Exception:
        return 0


def _print_scenario_summary(
    record: EvaluationResult, fails: list[str], label: str,
) -> None:
    if fails:
        for f in fails:
            print(f"  [FAIL] {f}")
        return
    ext = record.extended_criteria_result or {}
    print(
        f"  [OK] {label}: status={record.status}, "
        f"core_score={record.core_score}, "
        f"extended.status={ext.get('status')}, "
        f"extended.scores={ext.get('criterion_scores')}"
    )


if __name__ == "__main__":
    sys.exit(main())
