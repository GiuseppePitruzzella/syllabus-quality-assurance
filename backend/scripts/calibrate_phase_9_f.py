"""Baseline calibration runner for Phase 9.F (E4 + E5).

Executes the calibration described in
``data/calibration/phase_9_f/protocol.md`` on the five canonical
LM-18 SEUIDs. The runner:

  1. **pre-flight**: reads the protocol + E5 fixture, computes the
     fixture hash, looks up the five SEUIDs in the DB and checks
     that each one has ``has_english=True`` (otherwise E4 would
     skip into a resolver-NA, which we want as a *targeted*
     sub-campaign, not in the baseline);
  2. **idempotent fixture ingest**: looks the
     ``usi_dipartimentali`` document up in the registry; reuses
     an existing ``indexed`` row with matching hash; uploads if
     missing; **aborts** if a row with the same identity exists
     with a different hash;
  3. **per-SEUID evaluation**: hits the production HTTP API
     (``POST /api/evaluate/{seuid}`` + polling) so the artifacts
     are byte-for-byte what the UI would see;
  4. **per-evaluation drift check**: refuses the run if any
     observed ``handler_prompt_versions`` deviates from
     ``e4_v1`` / ``e5_v1``, or the run did not consume the
     expected fixture;
  5. **output**: writes per-SEUID artifacts (full
     ``EvaluationDetail`` JSON dump + final report + extended
     judgments rendered in human-readable Markdown) and a
     run-level ``manifest.json`` / ``summary.json`` /
     ``summary.md``. Every JSON artifact carries the
     ``calibration_mode = phase_9_f_baseline`` and the
     ``protocol_version = phase_9_f_v1`` markers at top level;
  6. **post-flight**: re-checks the fixture hash on disk; refuses
     to write the summary if the file changed during the run.

The fixture is **never** removed at the end — per protocol §3.2
and §5.3 the fixture, the audit rows and the EvaluationResults
must remain in place so the runs stay reproducible.

How to run::

    cd backend
    uv run python scripts/calibrate_phase_9_f.py [--yes]

Cost
----

Five real evaluations against Vertex + at most one embedding round
for the fixture ingestion. The runner prints a confirmation prompt
with the estimate; ``--yes`` skips the prompt.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Syllabus  # noqa: E402
from app.models.local_document import LocalDocument  # noqa: E402


# --- constants from protocol.md (single source of truth) ---------------------
PROTOCOL_VERSION = "phase_9_f_v1"
CALIBRATION_MODE = "phase_9_f_baseline"
E4_PROMPT_VERSION = "e4_v1"
E5_PROMPT_VERSION = "e5_v1"
E5_FIXTURE_VERSION = "v1"
E5_DOCUMENT_TYPE = "usi_dipartimentali"
E5_DOCUMENT_TITLE = "Usi dipartimentali LM-18 — Phase 9.F baseline"
E5_ACADEMIC_YEAR = "2025-2026"
REDACTED = "<REDACTED>"

REPO_ROOT = _THIS.parent.parent.parent
PROTOCOL_PATH = REPO_ROOT / "data" / "calibration" / "phase_9_f" / "protocol.md"
E5_FIXTURE_PATH = (
    REPO_ROOT
    / "data"
    / "calibration"
    / "phase_9_f"
    / "fixtures"
    / f"usi_dipartimentali_lm18_{E5_FIXTURE_VERSION}.md"
)

# Same shortlist as a1_v4_before_a1_v5 / e2e_v1 / e2e_v2.
BASELINE_SEUIDS: tuple[str, ...] = (
    "3540D939-DA16-4C1D-983C-E6B85C403F2F",
    "E2446DF6-59A1-46FD-B8D8-635EB937C1B3",
    "F4AF1512-9D7A-4256-B57D-E103E05B009B",
    "FE97232C-4F07-41F8-A82F-FF73592265EC",
    "0B53E8E2-4B90-426F-A25C-3AA31FA4B649",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 9.F baseline runner")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "data" / "calibration" / "phase_9_f" / "baseline",
        help=(
            "Directory where the per-syllabus artifacts and the run "
            "summary will be written. Refuses to run if the directory "
            "already contains files — pass a different dir for re-runs."
        ),
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the cost-confirmation prompt.",
    )
    parser.add_argument(
        "--terminal-timeout",
        type=int,
        default=900,
        help="Per-evaluation timeout while waiting for a terminal status.",
    )
    args = parser.parse_args()

    print(f"=== Phase 9.F baseline — protocol {PROTOCOL_VERSION} ===\n")

    # ---- Pre-flight ----------------------------------------------------------
    try:
        fixture_hash = _preflight_check_files()
        cdl_id = _preflight_check_syllabi()
        _preflight_check_output_dir(args.output_dir)
    except _PreflightError as exc:
        print(f"[FAIL] preflight: {exc}")
        return 2

    estimate = (
        f"Estimate: 1 fixture embedding round (if not already indexed) + "
        f"{len(BASELINE_SEUIDS)} real evaluations against Vertex "
        f"(~6 LLM calls each: A1+A2+A3+A4 core + E4 + E5)."
    )
    print(estimate)
    if not args.yes and not _confirm():
        print("aborted.")
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc)

    with TestClient(app) as client:
        # ---- Ingest fixture (idempotent) -------------------------------------
        try:
            e5_doc = _ensure_fixture_indexed(
                client,
                cdl_id=cdl_id,
                fixture_path=E5_FIXTURE_PATH,
                fixture_hash=fixture_hash,
            )
        except _FixtureError as exc:
            print(f"[FAIL] fixture ingest: {exc}")
            return 2

        # ---- Per-SEUID baseline ---------------------------------------------
        run_summaries: list[dict[str, Any]] = []
        for seuid in BASELINE_SEUIDS:
            print(f"\n--- {seuid} ---")
            try:
                summary = _run_one(
                    client,
                    seuid=seuid,
                    e5_doc=e5_doc,
                    output_dir=args.output_dir,
                    timeout_s=args.terminal_timeout,
                )
            except _RunError as exc:
                print(f"  [FAIL] {exc}")
                return 1
            run_summaries.append(summary)
            print(
                f"  [OK] status={summary['core_status']} "
                f"core_score={summary['core_score']} "
                f"E4={summary['e4']['outcome']} E5={summary['e5']['outcome']}"
            )

    # ---- Post-flight: fixture hash unchanged --------------------------------
    final_hash = _compute_hash(E5_FIXTURE_PATH)
    if final_hash != fixture_hash:
        print(
            f"\n[FAIL] fixture hash drifted during the run "
            f"(was {fixture_hash[:7]}, now {final_hash[:7]}). "
            f"Summary NOT written; per-syllabus artifacts retained for forensics."
        )
        return 1

    # ---- Write manifest + summary ------------------------------------------
    finished_at = datetime.now(timezone.utc)
    manifest = _build_manifest(
        started_at=started_at,
        finished_at=finished_at,
        fixture_hash=fixture_hash,
        e5_doc=e5_doc,
        run_summaries=run_summaries,
    )
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    summary = _build_summary(manifest, run_summaries)
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    (args.output_dir / "summary.md").write_text(
        _render_summary_md(summary), encoding="utf-8",
    )

    print(f"\n=== ALL FIVE BASELINE RUNS GREEN ===\n  → {args.output_dir}")
    return 0


# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------


class _PreflightError(Exception):
    pass


class _FixtureError(Exception):
    pass


class _RunError(Exception):
    pass


def _preflight_check_files() -> str:
    if not PROTOCOL_PATH.exists():
        raise _PreflightError(f"missing protocol at {PROTOCOL_PATH}")
    if not E5_FIXTURE_PATH.exists():
        raise _PreflightError(f"missing E5 fixture at {E5_FIXTURE_PATH}")
    fixture_hash = _compute_hash(E5_FIXTURE_PATH)
    print(
        f"protocol:      {PROTOCOL_PATH.relative_to(REPO_ROOT)} (sha {_compute_hash(PROTOCOL_PATH)[:7]})\n"
        f"E5 fixture:    {E5_FIXTURE_PATH.relative_to(REPO_ROOT)} (sha {fixture_hash[:7]})"
    )
    return fixture_hash


def _preflight_check_syllabi() -> int:
    """Verify each of the five SEUIDs is in the DB and has ``has_english=True``.

    Returns the common ``cdl_id`` (LM-18) used by all five.
    """
    cdl_ids: set[int] = set()
    with SessionLocal() as session:
        for seuid in BASELINE_SEUIDS:
            row = (
                session.execute(select(Syllabus).where(Syllabus.seuid == seuid))
                .scalar_one_or_none()
            )
            if row is None:
                raise _PreflightError(f"syllabus seuid={seuid!r} not found")
            if not row.has_english:
                raise _PreflightError(
                    f"syllabus seuid={seuid!r} has has_english=False; the "
                    "baseline expects EN-bearing syllabi (targeted cases go "
                    "into phase_9_f_targeted_v1)."
                )
            cdl_ids.add(int(row.cdl_id))
    if len(cdl_ids) != 1:
        raise _PreflightError(
            f"baseline SEUIDs span multiple CdL ids ({sorted(cdl_ids)}); "
            "the protocol assumes a single LM-18 CdL."
        )
    cdl_id = next(iter(cdl_ids))
    print(f"baseline SEUIDs: {len(BASELINE_SEUIDS)} all on cdl_id={cdl_id}")
    return cdl_id


def _preflight_check_output_dir(out: Path) -> None:
    if out.exists() and any(out.iterdir()):
        raise _PreflightError(
            f"output directory {out} is not empty. Pass --output-dir to a "
            "fresh path so previous baseline artifacts are not overwritten."
        )


def _confirm() -> bool:
    try:
        ans = input("Proceed? [y/N] ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


# ---------------------------------------------------------------------------
# Fixture ingest
# ---------------------------------------------------------------------------


def _ensure_fixture_indexed(
    client: TestClient,
    *,
    cdl_id: int,
    fixture_path: Path,
    fixture_hash: str,
) -> dict[str, Any]:
    """Reuse / upload / refuse — the three branches the user agreed.

    Returns a dict with ``id``, ``version``, ``file_hash`` and a flag
    ``reused`` so the manifest can record whether this run paid the
    embedding round.
    """
    print("\n--- E5 fixture ingest ---")
    with SessionLocal() as session:
        existing = (
            session.query(LocalDocument)
            .filter(
                LocalDocument.cdl_id == cdl_id,
                LocalDocument.document_type == E5_DOCUMENT_TYPE,
                LocalDocument.title == E5_DOCUMENT_TITLE,
                LocalDocument.deleted_at.is_(None),
            )
            .order_by(LocalDocument.version.desc())
            .first()
        )
        if existing is not None:
            if existing.file_hash != fixture_hash:
                raise _FixtureError(
                    f"a registry document with the baseline title and CdL "
                    f"already exists (id={existing.id}, version={existing.version}) "
                    f"but its file_hash {existing.file_hash[:7]} differs from "
                    f"the on-disk fixture {fixture_hash[:7]}. Refusing to "
                    "shadow it. Reconcile manually before retrying."
                )
            if existing.status != "indexed":
                raise _FixtureError(
                    f"matching registry row (id={existing.id}) is in status "
                    f"{existing.status!r}; baseline requires 'indexed'."
                )
            if existing.enabled_criteria != ["E5"]:
                raise _FixtureError(
                    f"matching registry row (id={existing.id}) has "
                    f"enabled_criteria={existing.enabled_criteria}; baseline "
                    "requires exactly ['E5']."
                )
            print(
                f"  [OK] reusing existing id={existing.id} version={existing.version} "
                f"hash={existing.file_hash[:7]}"
            )
            return {
                "id": int(existing.id),
                "version": int(existing.version),
                "file_hash": str(existing.file_hash),
                "reused": True,
            }

    content = fixture_path.read_bytes()
    files = {
        "file": (
            f"usi_dipartimentali_lm18_{E5_FIXTURE_VERSION}.md",
            io.BytesIO(content),
            "text/markdown",
        ),
    }
    form = {
        "cdl_id": str(cdl_id),
        "document_type": E5_DOCUMENT_TYPE,
        "title": E5_DOCUMENT_TITLE,
        "academic_year": E5_ACADEMIC_YEAR,
        "enabled_criteria": "E5",
    }
    resp = client.post("/api/local-documents", files=files, data=form)
    if resp.status_code not in (200, 201):
        raise _FixtureError(
            f"upload failed: {resp.status_code} {resp.text[:300]}"
        )
    doc_id = int(resp.json()["document"]["id"])

    deadline = time.time() + 120
    while time.time() < deadline:
        with SessionLocal() as session:
            doc = session.query(LocalDocument).filter_by(id=doc_id).one()
            if doc.status == "indexed":
                if doc.enabled_criteria != ["E5"]:
                    raise _FixtureError(
                        f"newly-indexed doc id={doc.id} has "
                        f"enabled_criteria={doc.enabled_criteria}, "
                        "expected ['E5']."
                    )
                if doc.file_hash != fixture_hash:
                    raise _FixtureError(
                        f"newly-indexed doc id={doc.id} has hash "
                        f"{doc.file_hash[:7]} but fixture is {fixture_hash[:7]}."
                    )
                print(
                    f"  [OK] uploaded + indexed id={doc.id} version={doc.version} "
                    f"chunks={doc.chunk_count}"
                )
                return {
                    "id": int(doc.id),
                    "version": int(doc.version),
                    "file_hash": str(doc.file_hash),
                    "reused": False,
                }
            if doc.status == "failed":
                raise _FixtureError(
                    f"fixture indexing failed: {doc.failure_reason!r}"
                )
        time.sleep(1.5)
    raise _FixtureError("fixture indexing timed out (120s)")


# ---------------------------------------------------------------------------
# Per-SEUID baseline run
# ---------------------------------------------------------------------------


def _run_one(
    client: TestClient,
    *,
    seuid: str,
    e5_doc: dict[str, Any],
    output_dir: Path,
    timeout_s: int,
) -> dict[str, Any]:
    started = time.time()
    response = client.post(f"/api/evaluate/{seuid}")
    response.raise_for_status()
    evaluation_uuid = response.json()["evaluation_uuid"]
    print(f"  evaluation_uuid={evaluation_uuid}")

    deadline = time.time() + timeout_s
    body: dict[str, Any] | None = None
    while time.time() < deadline:
        body = client.get(f"/api/evaluations/{evaluation_uuid}").json()
        status = body.get("status")
        if status in ("completed", "partial", "failed"):
            break
        time.sleep(3.0)
    if body is None or body.get("status") not in (
        "completed", "partial", "failed",
    ):
        raise _RunError(f"evaluation did not reach a terminal status in {timeout_s}s")

    elapsed = round(time.time() - started, 2)

    # ---- Drift checks ----
    prompt_versions = body.get("prompt_versions") or {}
    if prompt_versions.get("A1") is None:
        raise _RunError("missing A1 prompt_version in record")
    ext = body.get("extended_criteria_result")
    if ext is None:
        raise _RunError(
            "extended_criteria_result is None for a 9.C+ run — this is "
            "unexpected on the baseline shortlist."
        )
    hpv = ext.get("handler_prompt_versions") or {}
    if hpv.get("E4") != E4_PROMPT_VERSION:
        raise _RunError(
            f"E4 prompt_version drift: got {hpv.get('E4')!r}, "
            f"expected {E4_PROMPT_VERSION!r}. Baseline aborted."
        )
    if hpv.get("E5") != E5_PROMPT_VERSION:
        raise _RunError(
            f"E5 prompt_version drift: got {hpv.get('E5')!r}, "
            f"expected {E5_PROMPT_VERSION!r}. Baseline aborted."
        )

    docs_used = body.get("external_documents_used") or []
    e5_audit = [d for d in docs_used if d["criterion_code"] == "E5"]
    if len(e5_audit) != 1:
        raise _RunError(
            f"E5 audit rows count = {len(e5_audit)}, expected exactly 1."
        )
    if e5_audit[0]["local_document_id"] != e5_doc["id"]:
        raise _RunError(
            f"E5 audit row points to doc_id={e5_audit[0]['local_document_id']} "
            f"instead of the seeded fixture id={e5_doc['id']}."
        )
    if e5_audit[0]["file_hash"] != e5_doc["file_hash"]:
        raise _RunError(
            "E5 audit row file_hash drift relative to the seeded fixture."
        )

    # ---- Write per-SEUID artifacts ----
    _write_evaluation_json(body, e5_doc, output_dir, seuid)
    _write_report_md(body, output_dir, seuid)
    _write_extended_judgments_md(body, output_dir, seuid)

    e4_judgment = _judgment_for(ext, "E4")
    e5_judgment = _judgment_for(ext, "E5")

    return {
        "seuid": seuid,
        "evaluation_uuid": evaluation_uuid,
        "core_status": body["status"],
        "core_score": body.get("core_score"),
        "coverage": body.get("coverage"),
        "duration_seconds": elapsed,
        "extended_status": ext["status"],
        "handler_errors": dict(ext.get("handler_errors") or {}),
        "handler_prompt_versions": dict(hpv),
        "e4": _outcome_dict(e4_judgment, ext, "E4"),
        "e5": _outcome_dict(e5_judgment, ext, "E5"),
        "e5_document_used": dict(e5_audit[0]),
    }


def _outcome_dict(
    judgment: dict[str, Any] | None,
    ext: dict[str, Any],
    code: str,
) -> dict[str, Any]:
    na = next(
        (n for n in (ext.get("na_criteria") or []) if n["criterion_code"] == code),
        None,
    )
    if na is not None:
        return {
            "outcome": f"NA-{na['source']}",
            "score": None,
            "na_source": na["source"],
            "na_reason": na["reason"],
            "confidence": judgment.get("confidence") if judgment else None,
            "evidences_count": len(judgment.get("evidences") or []) if judgment else 0,
        }
    if judgment is None:
        return {"outcome": "absent", "score": None}
    return {
        "outcome": "score",
        "score": judgment.get("score"),
        "is_na_technical": judgment.get("is_na_technical", False),
        "confidence": judgment.get("confidence"),
        "evidences_count": len(judgment.get("evidences") or []),
    }


def _judgment_for(ext: dict[str, Any], code: str) -> dict[str, Any] | None:
    for j in ext.get("judgments") or []:
        if j["criterion_code"] == code:
            return j
    return None


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------


def _calibration_header() -> dict[str, Any]:
    return {
        "calibration_mode": CALIBRATION_MODE,
        "protocol_version": PROTOCOL_VERSION,
        "e5_fixture_version": E5_FIXTURE_VERSION,
    }


def _write_evaluation_json(
    body: dict[str, Any],
    e5_doc: dict[str, Any],
    output_dir: Path,
    seuid: str,
) -> None:
    redacted_body = copy.deepcopy(body)
    _redact_gcp_project_id(redacted_body)
    payload = {
        **_calibration_header(),
        "e5_document": e5_doc,
        "evaluation_detail": redacted_body,
    }
    (output_dir / f"{seuid}__evaluation.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _redact_gcp_project_id(obj: Any) -> None:
    """Redact project identifiers recursively before persisting artifacts."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "gcp_project_id":
                obj[key] = REDACTED
            else:
                _redact_gcp_project_id(value)
    elif isinstance(obj, list):
        for item in obj:
            _redact_gcp_project_id(item)


def _write_report_md(body: dict[str, Any], output_dir: Path, seuid: str) -> None:
    header = (
        f"<!-- calibration_mode={CALIBRATION_MODE} "
        f"protocol_version={PROTOCOL_VERSION} "
        f"e5_fixture_version={E5_FIXTURE_VERSION} -->\n\n"
    )
    body_text = body.get("final_report") or "_no final report available_"
    (output_dir / f"{seuid}__report.md").write_text(
        header + body_text, encoding="utf-8",
    )


def _write_extended_judgments_md(
    body: dict[str, Any], output_dir: Path, seuid: str,
) -> None:
    ext = body["extended_criteria_result"] or {}
    lines: list[str] = []
    lines.append(
        f"<!-- calibration_mode={CALIBRATION_MODE} "
        f"protocol_version={PROTOCOL_VERSION} "
        f"e5_fixture_version={E5_FIXTURE_VERSION} -->"
    )
    lines.append("")
    lines.append(f"# Extended judgments — {seuid}")
    lines.append("")
    lines.append(f"- evaluation_uuid: `{body['evaluation_uuid']}`")
    lines.append(f"- extended status: `{ext.get('status')}`")
    lines.append(f"- handler_prompt_versions: `{ext.get('handler_prompt_versions')}`")
    lines.append("")
    for code in ("E4", "E5"):
        lines.append(f"## {code}")
        lines.append("")
        na = next(
            (
                n
                for n in (ext.get("na_criteria") or [])
                if n["criterion_code"] == code
            ),
            None,
        )
        j = _judgment_for(ext, code)
        if na is not None:
            tag = "tecnico" if na["source"] == "handler_error" else "semantico"
            lines.append(f"**NA {tag}** (source: `{na['source']}`)")
            lines.append("")
            lines.append(f"> {na['reason']}")
            lines.append("")
        if j is None:
            lines.append("_(no judgment payload)_")
            lines.append("")
            continue
        lines.append(
            f"- score: `{j.get('score')}`  is_na: `{j.get('is_na')}`  "
            f"is_na_technical: `{j.get('is_na_technical', False)}`  "
            f"confidence: `{j.get('confidence')}`"
        )
        lines.append("")
        lines.append("### Justification")
        lines.append("")
        lines.append(j.get("justification") or "_(empty)_")
        lines.append("")
        evidences = j.get("evidences") or []
        if evidences:
            lines.append("### Evidences")
            lines.append("")
            for i, ev in enumerate(evidences, 1):
                src = (
                    f"Syllabus · `{ev['source_field']}`"
                    if ev.get("source_field")
                    else (
                        f"Documento esterno · `doc:{ev['source_document_id']}`"
                        f"{(' · `' + ev['source_chunk_id'] + '`') if ev.get('source_chunk_id') else ''}"
                    )
                )
                lines.append(f"{i}. {src}")
                lines.append(f"   > {ev.get('text','')}")
                lines.append("")
    (output_dir / f"{seuid}__extended_judgments.md").write_text(
        "\n".join(lines), encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Run-level summary
# ---------------------------------------------------------------------------


def _build_manifest(
    *,
    started_at: datetime,
    finished_at: datetime,
    fixture_hash: str,
    e5_doc: dict[str, Any],
    run_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        **_calibration_header(),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round(
            (finished_at - started_at).total_seconds(), 2,
        ),
        "e4_prompt_version": E4_PROMPT_VERSION,
        "e5_prompt_version": E5_PROMPT_VERSION,
        "e5_document": e5_doc,
        "e5_fixture_sha256": fixture_hash,
        "seuids": list(BASELINE_SEUIDS),
        "evaluation_uuids": [s["evaluation_uuid"] for s in run_summaries],
    }


def _build_summary(
    manifest: dict[str, Any],
    run_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    e4_outcomes = Counter(r["e4"]["outcome"] for r in run_summaries)
    e5_outcomes = Counter(r["e5"]["outcome"] for r in run_summaries)

    core_scores = [
        r["core_score"] for r in run_summaries if r["core_score"] is not None
    ]
    coverage_values = [
        r["coverage"] for r in run_summaries if r["coverage"] is not None
    ]
    durations = [
        r["duration_seconds"]
        for r in run_summaries
        if r["duration_seconds"] is not None
    ]

    return {
        **_calibration_header(),
        "manifest": manifest,
        "runs": run_summaries,
        "core": {
            "status_counts": dict(
                Counter(r["core_status"] for r in run_summaries)
            ),
            "core_score": _scalar_stats(core_scores),
            "coverage": _scalar_stats(coverage_values),
        },
        "extended": {
            "status_counts": dict(
                Counter(r["extended_status"] for r in run_summaries)
            ),
            "E4": {
                "outcomes": dict(e4_outcomes),
                "scores": _score_distribution(run_summaries, "e4"),
            },
            "E5": {
                "outcomes": dict(e5_outcomes),
                "scores": _score_distribution(run_summaries, "e5"),
            },
            "technical_na_count": sum(
                1 for r in run_summaries
                if r["e4"]["outcome"] == "NA-handler_error"
                or r["e5"]["outcome"] == "NA-handler_error"
            ),
            "any_handler_errors": sum(
                len(r["handler_errors"]) for r in run_summaries
            ),
        },
        "durations_seconds": _scalar_stats(durations),
    }


def _scalar_stats(xs: list[float]) -> dict[str, float | None]:
    if not xs:
        return {"n": 0, "mean": None, "median": None, "min": None, "max": None}
    return {
        "n": len(xs),
        "mean": round(statistics.fmean(xs), 4),
        "median": round(statistics.median(xs), 4),
        "min": round(min(xs), 4),
        "max": round(max(xs), 4),
    }


def _score_distribution(
    rows: list[dict[str, Any]], key: str,
) -> dict[str, int]:
    out: dict[str, int] = {"0": 0, "1": 0, "2": 0, "NA": 0}
    for r in rows:
        outcome = r[key]
        score = outcome.get("score")
        if score in (0, 1, 2):
            out[str(score)] += 1
        else:
            out["NA"] += 1
    return out


def _render_summary_md(summary: dict[str, Any]) -> str:
    manifest = summary["manifest"]
    lines: list[str] = []
    lines.append(f"# Phase 9.F baseline — {CALIBRATION_MODE}")
    lines.append("")
    lines.append(f"- Protocol: `{PROTOCOL_VERSION}`")
    lines.append(f"- E5 fixture: `{E5_FIXTURE_VERSION}` (sha {manifest['e5_fixture_sha256'][:7]})")
    lines.append(
        f"- E5 document id: `{manifest['e5_document']['id']}` "
        f"version {manifest['e5_document']['version']} "
        f"hash {manifest['e5_document']['file_hash'][:7]} "
        f"({'reused' if manifest['e5_document']['reused'] else 'uploaded'})"
    )
    lines.append(f"- Prompts: E4=`{manifest['e4_prompt_version']}`, E5=`{manifest['e5_prompt_version']}`")
    lines.append(f"- Started: {manifest['started_at']}")
    lines.append(f"- Finished: {manifest['finished_at']}")
    lines.append(f"- Duration: {manifest['duration_seconds']}s")
    lines.append("")
    lines.append("## Per-syllabus")
    lines.append("")
    lines.append("| SEUID | core | core_score | coverage | E4 | E5 |")
    lines.append("|---|---|---:|---:|---|---|")
    for r in summary["runs"]:
        lines.append(
            f"| `{r['seuid'][:8]}…` | {r['core_status']} | "
            f"{r['core_score']} | {r['coverage']} | "
            f"{r['e4']['outcome']} ({r['e4'].get('score')}) | "
            f"{r['e5']['outcome']} ({r['e5'].get('score')}) |"
        )
    lines.append("")
    lines.append("## Distributions")
    lines.append("")
    lines.append(f"- Core status: {summary['core']['status_counts']}")
    lines.append(f"- Core score: {summary['core']['core_score']}")
    lines.append(f"- Coverage: {summary['core']['coverage']}")
    lines.append(f"- Extended status: {summary['extended']['status_counts']}")
    lines.append(f"- E4 outcomes: {summary['extended']['E4']['outcomes']}")
    lines.append(f"- E5 outcomes: {summary['extended']['E5']['outcomes']}")
    lines.append(
        f"- Technical NA count: {summary['extended']['technical_na_count']} "
        f"(any_handler_errors={summary['extended']['any_handler_errors']})"
    )
    lines.append(f"- Durations (s): {summary['durations_seconds']}")
    lines.append("")
    lines.append(
        "Artifacts: `manifest.json`, per-syllabus `*.evaluation.json` / "
        "`*.report.md` / `*.extended_judgments.md`."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    sys.exit(main())
