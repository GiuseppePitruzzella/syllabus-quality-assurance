"""Targeted calibration runner for Phase 9.F — campaign phase_9_f_targeted_v1.

This is the *targeted* counterpart of ``calibrate_phase_9_f.py``
(the baseline). The campaign exercises three score bands that the
baseline did not produce: E4=1, and the high band E5=2 via a
synthetic positive control. The fixture
``usi_dipartimentali_lm18_v1.md`` is reused verbatim — per protocol
§3.2 changing the fixture between baseline and targeted would
mix two variables. The E4 / E5 prompt versions are also
unchanged: e4_v1 / e5_v1, same drift guards as the baseline.

Sample (4 evaluations)
----------------------

Three real LM-18 syllabi, chosen by inspecting the 30 historical
records:

  - ``3ED4B3BB-D25C-4EA3-BC50-14A310BEF4FF`` (Advanced Computer
    Graphics): expected **E4 = 1**. The EN side covers most fields
    well but ``course_content_en`` is missing — a partial bilingual
    equivalence, not a full one, exactly the mid-band E4 anchor.
  - ``B99A46CC-D23B-4987-91AF-A2ECCFBAC778`` (Computer Vision e
    Laboratorio): boundary case for E5. Human expectation: 1 (2
    uses adhered, 1 partial, 1 violated). Cross-validates the ML
    review verdict — if Computer Vision also receives E5=0, the
    one-strike-out severity is systemic.
  - ``DADC30FD-2222-4C43-BAB8-A57D08667196`` (Crittografia):
    second E5 boundary, again expected 1.

Plus one **synthetic positive control** for E5:

  - ``SYNTHETIC-9F-POSITIVE-E5-V1``: a syllabus row inserted into
    the DB from
    ``data/calibration/phase_9_f/fixtures/synthetic_syllabus_positive_e5_v1.json``.
    All four fixture uses (prerequisites cultural/disciplinary
    split; assessment with weights + voto minimo + sample
    question; references with full bibliographic format;
    attendance with explicit obligatory/facultative level) are
    explicitly satisfied. The IT/EN side is built to be
    semantically equivalent so E4 also can reach the top band as
    a positive sanity check.

The synthetic syllabus is persisted (not torn down) so the run
is reproducible and inspectable from the frontend.

The two questions this campaign answers
---------------------------------------

  1. Is e5_v1 *capable* of granting E5=2 on a fully-conforming
     syllabus? The synthetic answers this directly: if it gets
     less than 2, the prompt is structurally severe.

  2. Is the boundary E5=0 verdict on the ML baseline systemic?
     The two boundary real cases (Computer Vision, Crittografia)
     answer this: if both also collapse to 0 despite having two
     uses adhered, the *aggregation rule* is the issue, not the
     anchor wording.

Decision tree at the end of the campaign:

  * synthetic = 2, boundaries = 1 → e5_v1 is well-calibrated;
    Machine Learning was a defensible outlier on the shortlist.
  * synthetic = 2, boundaries = 0 → aggregation rule is the
    issue; e5_v2 should refine the per-use vs criterion-level
    language and forbid one-strike-out.
  * synthetic < 2 → e5_v1 is structurally severe; e5_v2 needed
    regardless of boundary behaviour.

How to run::

    cd backend
    uv run python scripts/calibrate_phase_9_f_targeted.py [--yes]
"""
from __future__ import annotations

import argparse
import json
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

# Reuse baseline runner's helpers + constants — single source of
# truth for protocol version, fixture path, prompt versions,
# ingest/idempotency, artifact writers and the drift guards. The
# baseline file is unchanged.
from scripts.calibrate_phase_9_f import (  # noqa: E402
    E4_PROMPT_VERSION,
    E5_FIXTURE_PATH,
    E5_FIXTURE_VERSION,
    E5_PROMPT_VERSION,
    PROTOCOL_VERSION,
    REPO_ROOT,
    _compute_hash,
    _confirm,
    _ensure_fixture_indexed,
    _FixtureError,
    _outcome_dict,
    _preflight_check_files,
    _PreflightError,
    _RunError,
    _scalar_stats,
    _score_distribution,
    _write_evaluation_json,
    _write_extended_judgments_md,
    _write_report_md,
)


CALIBRATION_MODE = "phase_9_f_targeted_v1"

SYNTHETIC_FIXTURE_PATH = (
    REPO_ROOT
    / "data"
    / "calibration"
    / "phase_9_f"
    / "fixtures"
    / "synthetic_syllabus_positive_e5_v1.json"
)
SYNTHETIC_FIXTURE_VERSION = "v1"
SYNTHETIC_SEUID = "SYNTHETIC-9F-POSITIVE-E5-V1"

# Three real LM-18 syllabi, chosen by inspecting the 30 historical
# records — see the module docstring for the rationale per case.
TARGETED_REAL_SEUIDS: tuple[str, ...] = (
    "3ED4B3BB-D25C-4EA3-BC50-14A310BEF4FF",  # Advanced Computer Graphics → E4=1
    "B99A46CC-D23B-4987-91AF-A2ECCFBAC778",  # Computer Vision → boundary E5
    "DADC30FD-2222-4C43-BAB8-A57D08667196",  # Crittografia → boundary E5
)

# Fields the runner deeply compares between the synthetic JSON and
# the in-DB Syllabus row to enforce drift detection on re-runs.
# Order matters only for the hash digest we surface in the manifest.
_SYNTHETIC_CONTENT_FIELDS: tuple[str, ...] = (
    "seuid",
    "course_code",
    "course_name",
    "teacher",
    "academic_year",
    "year_of_study",
    "url_it",
    "url_en",
    "has_english",
    "learning_outcomes_it",
    "learning_outcomes_en",
    "dublin_knowledge_it",
    "dublin_knowledge_en",
    "dublin_applying_it",
    "dublin_applying_en",
    "dublin_judgement_it",
    "dublin_judgement_en",
    "dublin_communication_it",
    "dublin_communication_en",
    "dublin_learning_it",
    "dublin_learning_en",
    "prerequisites_it",
    "prerequisites_en",
    "course_content_it",
    "course_content_en",
    "assessment_methods_it",
    "assessment_methods_en",
    "sample_questions_it",
    "references_it",
    "teaching_methods_it",
    "attendance_it",
    "schedule_it",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 9.F targeted runner")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "data" / "calibration" / "phase_9_f" / "targeted_v1",
        help=(
            "Output dir for per-syllabus and run-level artifacts. "
            "Refuses to run if non-empty."
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
        help="Per-evaluation timeout (seconds).",
    )
    args = parser.parse_args()

    print(
        f"=== Phase 9.F targeted ({CALIBRATION_MODE}) — protocol {PROTOCOL_VERSION} ==="
    )

    try:
        fixture_hash = _preflight_check_files()
        synthetic_payload, synthetic_hash = _preflight_synthetic_fixture()
        cdl_id, real_syllabi = _preflight_check_real_syllabi()
        _preflight_check_output_dir(args.output_dir)
    except _PreflightError as exc:
        print(f"[FAIL] preflight: {exc}")
        return 2

    print(
        f"\nEstimate: 1 fixture embedding round (if not already indexed) + "
        f"{len(TARGETED_REAL_SEUIDS) + 1} real evaluations against Vertex "
        f"(3 real + 1 synthetic positive control)."
    )
    if not args.yes and not _confirm():
        print("aborted.")
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc)

    with TestClient(app) as client:
        # ---- Idempotent E5 fixture ingest (same path as the baseline) ----
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

        # ---- Idempotent synthetic syllabus seed ----
        try:
            _ensure_synthetic_syllabus(synthetic_payload, cdl_id=cdl_id)
        except _SyntheticError as exc:
            print(f"[FAIL] synthetic seed: {exc}")
            return 2

        # ---- Per-SEUID baseline ----
        all_seuids = list(TARGETED_REAL_SEUIDS) + [SYNTHETIC_SEUID]
        run_summaries: list[dict[str, Any]] = []
        for seuid in all_seuids:
            is_synth = seuid == SYNTHETIC_SEUID
            label = "synthetic positive control" if is_synth else "real"
            print(f"\n--- {seuid} ({label}) ---")
            try:
                summary = _run_one(
                    client,
                    seuid=seuid,
                    e5_doc=e5_doc,
                    output_dir=args.output_dir,
                    timeout_s=args.terminal_timeout,
                    is_synthetic=is_synth,
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

    # ---- Post-flight: fixture and synthetic JSON unchanged ----
    final_fixture_hash = _compute_hash(E5_FIXTURE_PATH)
    if final_fixture_hash != fixture_hash:
        print(
            f"\n[FAIL] E5 fixture hash drifted during the run "
            f"({fixture_hash[:7]} -> {final_fixture_hash[:7]}). "
            "Summary NOT written."
        )
        return 1
    final_synthetic_hash = _compute_hash(SYNTHETIC_FIXTURE_PATH)
    if final_synthetic_hash != synthetic_hash:
        print(
            f"\n[FAIL] synthetic fixture hash drifted during the run "
            f"({synthetic_hash[:7]} -> {final_synthetic_hash[:7]}). "
            "Summary NOT written."
        )
        return 1

    finished_at = datetime.now(timezone.utc)
    manifest = _build_manifest(
        started_at=started_at,
        finished_at=finished_at,
        fixture_hash=fixture_hash,
        synthetic_hash=synthetic_hash,
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

    print(f"\n=== ALL FOUR TARGETED RUNS GREEN ===\n  → {args.output_dir}")
    return 0


# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------


class _SyntheticError(Exception):
    pass


def _preflight_synthetic_fixture() -> tuple[dict[str, Any], str]:
    """Read the synthetic syllabus JSON, validate the expected SEUID and
    return the parsed payload + the on-disk SHA-256 (for drift guard).
    """
    if not SYNTHETIC_FIXTURE_PATH.exists():
        raise _PreflightError(
            f"missing synthetic syllabus fixture at {SYNTHETIC_FIXTURE_PATH}"
        )
    try:
        payload = json.loads(SYNTHETIC_FIXTURE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise _PreflightError(f"synthetic fixture is not valid JSON: {exc}") from exc
    if payload.get("seuid") != SYNTHETIC_SEUID:
        raise _PreflightError(
            f"synthetic fixture SEUID mismatch: file says "
            f"{payload.get('seuid')!r}, code expects {SYNTHETIC_SEUID!r}."
        )
    digest = _compute_hash(SYNTHETIC_FIXTURE_PATH)
    print(
        f"synthetic syllabus fixture: "
        f"{SYNTHETIC_FIXTURE_PATH.relative_to(REPO_ROOT)} (sha {digest[:7]})"
    )
    return payload, digest


def _preflight_check_real_syllabi() -> tuple[int, list[dict[str, Any]]]:
    """Verify the three real targeted SEUIDs exist with has_english=True
    and that they share a single cdl_id (LM-18)."""
    cdl_ids: set[int] = set()
    rows: list[dict[str, Any]] = []
    with SessionLocal() as session:
        for seuid in TARGETED_REAL_SEUIDS:
            syl = (
                session.execute(select(Syllabus).where(Syllabus.seuid == seuid))
                .scalar_one_or_none()
            )
            if syl is None:
                raise _PreflightError(f"real targeted SEUID {seuid!r} not in DB")
            if not syl.has_english:
                raise _PreflightError(
                    f"real targeted SEUID {seuid!r} has has_english=False; "
                    "the targeted campaign requires EN-bearing syllabi."
                )
            cdl_ids.add(int(syl.cdl_id))
            rows.append(
                {
                    "seuid": syl.seuid,
                    "course_name": syl.course_name,
                    "cdl_id": int(syl.cdl_id),
                }
            )
    if len(cdl_ids) != 1:
        raise _PreflightError(
            f"real targeted SEUIDs span multiple CdL ids ({sorted(cdl_ids)})"
        )
    cdl_id = next(iter(cdl_ids))
    for r in rows:
        print(f"real targeted: {r['seuid']} — {r['course_name']!r}")
    return cdl_id, rows


def _preflight_check_output_dir(out: Path) -> None:
    if out.exists() and any(out.iterdir()):
        raise _PreflightError(
            f"output directory {out} is not empty. Pass --output-dir to a "
            "fresh path so previous targeted artifacts are not overwritten."
        )


# ---------------------------------------------------------------------------
# Synthetic syllabus seeding (idempotent, drift-aware)
# ---------------------------------------------------------------------------


def _ensure_synthetic_syllabus(
    payload: dict[str, Any], *, cdl_id: int,
) -> None:
    """Insert the synthetic syllabus on first run, reuse on subsequent
    runs only if every content field still matches the on-disk
    fixture (drift -> abort)."""
    print("\n--- Synthetic syllabus seed ---")
    expected = _expected_syllabus_fields(payload)
    with SessionLocal() as session:
        existing = (
            session.execute(select(Syllabus).where(Syllabus.seuid == SYNTHETIC_SEUID))
            .scalar_one_or_none()
        )
        if existing is None:
            now = datetime.now(timezone.utc)
            syl = Syllabus(
                cdl_id=cdl_id,
                seuid=expected["seuid"],
                course_code=expected["course_code"],
                course_name=expected["course_name"],
                teacher=expected["teacher"],
                academic_year=expected["academic_year"],
                year_of_study=expected["year_of_study"],
                url_it=expected["url_it"],
                url_en=expected["url_en"],
                has_english=bool(expected["has_english"]),
                scraped_at=now,
                learning_outcomes_it=expected["learning_outcomes_it"],
                learning_outcomes_en=expected["learning_outcomes_en"],
                dublin_knowledge_it=expected["dublin_knowledge_it"],
                dublin_knowledge_en=expected["dublin_knowledge_en"],
                dublin_applying_it=expected["dublin_applying_it"],
                dublin_applying_en=expected["dublin_applying_en"],
                dublin_judgement_it=expected["dublin_judgement_it"],
                dublin_judgement_en=expected["dublin_judgement_en"],
                dublin_communication_it=expected["dublin_communication_it"],
                dublin_communication_en=expected["dublin_communication_en"],
                dublin_learning_it=expected["dublin_learning_it"],
                dublin_learning_en=expected["dublin_learning_en"],
                teaching_methods_it=expected["teaching_methods_it"],
                prerequisites_it=expected["prerequisites_it"],
                prerequisites_en=expected["prerequisites_en"],
                course_content_it=expected["course_content_it"],
                course_content_en=expected["course_content_en"],
                assessment_methods_it=expected["assessment_methods_it"],
                assessment_methods_en=expected["assessment_methods_en"],
                sample_questions_it=expected["sample_questions_it"],
                references_it=expected["references_it"],
                attendance_it=expected["attendance_it"],
                schedule_it=expected["schedule_it"],
            )
            session.add(syl)
            session.commit()
            print(f"  [OK] inserted synthetic syllabus id={syl.id} seuid={SYNTHETIC_SEUID}")
            return

        # Drift detection
        drift: list[str] = []
        for field in _SYNTHETIC_CONTENT_FIELDS:
            db_value = getattr(existing, field, None)
            fx_value = expected.get(field)
            if db_value != fx_value:
                drift.append(field)
        if drift:
            raise _SyntheticError(
                f"existing synthetic syllabus id={existing.id} drifted from the "
                f"on-disk fixture {SYNTHETIC_FIXTURE_PATH.name} on fields "
                f"{drift}. Reconcile manually before retrying."
            )
        print(
            f"  [OK] reusing existing synthetic syllabus id={existing.id} "
            "(content matches fixture)"
        )


def _expected_syllabus_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract the strictly-syllabus fields from the JSON, ignoring
    methodological metadata (``_meta``)."""
    return {f: payload.get(f) for f in _SYNTHETIC_CONTENT_FIELDS}


# ---------------------------------------------------------------------------
# Per-SEUID baseline run (mirror of calibrate_phase_9_f._run_one, with
# the synthetic flag carried into the artifacts)
# ---------------------------------------------------------------------------


def _run_one(
    client: TestClient,
    *,
    seuid: str,
    e5_doc: dict[str, Any],
    output_dir: Path,
    timeout_s: int,
    is_synthetic: bool,
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
        if body.get("status") in ("completed", "partial", "failed"):
            break
        time.sleep(3.0)
    if body is None or body.get("status") not in (
        "completed", "partial", "failed",
    ):
        raise _RunError(f"evaluation did not reach a terminal status in {timeout_s}s")

    elapsed = round(time.time() - started, 2)

    ext = body.get("extended_criteria_result")
    if ext is None:
        raise _RunError("extended_criteria_result is None on a 9.C+ run")
    hpv = ext.get("handler_prompt_versions") or {}
    if hpv.get("E4") != E4_PROMPT_VERSION:
        raise _RunError(
            f"E4 prompt drift: got {hpv.get('E4')!r}, expected {E4_PROMPT_VERSION!r}"
        )
    if hpv.get("E5") != E5_PROMPT_VERSION:
        raise _RunError(
            f"E5 prompt drift: got {hpv.get('E5')!r}, expected {E5_PROMPT_VERSION!r}"
        )

    docs_used = body.get("external_documents_used") or []
    e5_audit = [d for d in docs_used if d["criterion_code"] == "E5"]
    if len(e5_audit) != 1:
        raise _RunError(f"E5 audit rows count = {len(e5_audit)}, expected 1")
    if e5_audit[0]["local_document_id"] != e5_doc["id"]:
        raise _RunError(
            f"E5 audit row points to doc_id={e5_audit[0]['local_document_id']} "
            f"instead of fixture id={e5_doc['id']}"
        )
    if e5_audit[0]["file_hash"] != e5_doc["file_hash"]:
        raise _RunError("E5 audit row file_hash drift relative to seeded fixture")

    _write_evaluation_json(
        body, e5_doc, output_dir, seuid,
        calibration_header=_targeted_header(extra={"role": "synthetic_positive_control" if is_synthetic else "real"}),
    )
    _write_report_md(body, output_dir, seuid, calibration_header=_targeted_header())
    _write_extended_judgments_md(
        body, output_dir, seuid, calibration_header=_targeted_header(),
    )

    return {
        "seuid": seuid,
        "evaluation_uuid": evaluation_uuid,
        "role": "synthetic_positive_control" if is_synthetic else "real",
        "core_status": body["status"],
        "core_score": body.get("core_score"),
        "coverage": body.get("coverage"),
        "duration_seconds": elapsed,
        "extended_status": ext["status"],
        "handler_errors": dict(ext.get("handler_errors") or {}),
        "handler_prompt_versions": dict(hpv),
        "e4": _outcome_dict(_judgment_for(ext, "E4"), ext, "E4"),
        "e5": _outcome_dict(_judgment_for(ext, "E5"), ext, "E5"),
        "e5_document_used": dict(e5_audit[0]),
    }


def _judgment_for(ext: dict[str, Any], code: str) -> dict[str, Any] | None:
    for j in ext.get("judgments") or []:
        if j["criterion_code"] == code:
            return j
    return None


# ---------------------------------------------------------------------------
# Calibration header for targeted artifacts
# ---------------------------------------------------------------------------


def _targeted_header(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "calibration_mode": CALIBRATION_MODE,
        "protocol_version": PROTOCOL_VERSION,
        "e5_fixture_version": E5_FIXTURE_VERSION,
        "synthetic_fixture_version": SYNTHETIC_FIXTURE_VERSION,
    }
    if extra:
        base.update(extra)
    return base


# ---------------------------------------------------------------------------
# Manifest + summary
# ---------------------------------------------------------------------------


def _build_manifest(
    *,
    started_at: datetime,
    finished_at: datetime,
    fixture_hash: str,
    synthetic_hash: str,
    e5_doc: dict[str, Any],
    run_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        **_targeted_header(),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round(
            (finished_at - started_at).total_seconds(), 2,
        ),
        "e4_prompt_version": E4_PROMPT_VERSION,
        "e5_prompt_version": E5_PROMPT_VERSION,
        "e5_document": e5_doc,
        "e5_fixture_sha256": fixture_hash,
        "synthetic_fixture_sha256": synthetic_hash,
        "synthetic_seuid": SYNTHETIC_SEUID,
        "real_seuids": list(TARGETED_REAL_SEUIDS),
        "evaluation_uuids": [s["evaluation_uuid"] for s in run_summaries],
    }


def _build_summary(
    manifest: dict[str, Any],
    run_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    real_rows = [r for r in run_summaries if r["role"] == "real"]
    synthetic_rows = [r for r in run_summaries if r["role"] == "synthetic_positive_control"]
    synthetic_row = synthetic_rows[0] if synthetic_rows else None

    e4_outcomes = Counter(r["e4"]["outcome"] for r in run_summaries)
    e5_outcomes = Counter(r["e5"]["outcome"] for r in run_summaries)

    durations = [
        r["duration_seconds"] for r in run_summaries
        if r["duration_seconds"] is not None
    ]
    core_scores = [
        r["core_score"] for r in run_summaries if r["core_score"] is not None
    ]
    coverage_values = [
        r["coverage"] for r in run_summaries if r["coverage"] is not None
    ]

    decision_tree = _interpret(synthetic_row, real_rows)

    return {
        **_targeted_header(),
        "manifest": manifest,
        "runs": run_summaries,
        "real_runs": real_rows,
        "synthetic_run": synthetic_row,
        "decision_tree": decision_tree,
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


def _interpret(
    synthetic_row: dict[str, Any] | None,
    real_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply the decision tree documented in the module docstring."""
    synth_score = synthetic_row["e5"]["score"] if synthetic_row else None
    real_scores = [r["e5"]["score"] for r in real_rows]
    real_boundary_zero = sum(1 for s in real_scores if s == 0)
    real_boundary_one = sum(1 for s in real_scores if s == 1)

    if synth_score is None:
        verdict = (
            "synthetic positive control returned NA / no score — review the "
            "extended_judgments artifact for the synthetic run; e5_v1 cannot "
            "be graded on its top band yet."
        )
    elif synth_score < 2:
        verdict = (
            f"synthetic positive control reached E5={synth_score} (< 2); "
            "e5_v1 is structurally severe on the maximum band. e5_v2 is "
            "warranted regardless of boundary behaviour."
        )
    elif real_boundary_zero >= 1 and real_boundary_one == 0:
        verdict = (
            "synthetic reached E5=2 but every real boundary case collapsed "
            "to E5=0. The one-strike-out aggregation is the dominant issue. "
            "e5_v2 should refine per-use vs criterion-level language and "
            "forbid single-violation downgrades."
        )
    elif real_boundary_zero >= 1 and real_boundary_one >= 1:
        verdict = (
            "synthetic reached E5=2; real boundary cases split between 1 and "
            "0. e5_v1 discriminates but the aggregation rule is still partly "
            "severe; e5_v2 could refine wording but is not urgent."
        )
    else:
        verdict = (
            "synthetic reached E5=2 and the real boundary cases scored at "
            "least 1: e5_v1 is well-calibrated; the Machine Learning baseline "
            "outcome looks like a defensible outlier."
        )

    return {
        "synthetic_e5_score": synth_score,
        "real_e5_scores": real_scores,
        "verdict": verdict,
    }


def _render_summary_md(summary: dict[str, Any]) -> str:
    manifest = summary["manifest"]
    lines: list[str] = []
    lines.append(f"# Phase 9.F targeted_v1 — {CALIBRATION_MODE}")
    lines.append("")
    lines.append(f"- Protocol: `{PROTOCOL_VERSION}`")
    lines.append(
        f"- E5 fixture (document): `{E5_FIXTURE_VERSION}` "
        f"(sha {manifest['e5_fixture_sha256'][:7]})"
    )
    lines.append(
        f"- Synthetic syllabus fixture: `{SYNTHETIC_FIXTURE_VERSION}` "
        f"(sha {manifest['synthetic_fixture_sha256'][:7]})"
    )
    lines.append(
        f"- E5 document id: `{manifest['e5_document']['id']}` "
        f"version {manifest['e5_document']['version']} "
        f"hash {manifest['e5_document']['file_hash'][:7]} "
        f"({'reused' if manifest['e5_document']['reused'] else 'uploaded'})"
    )
    lines.append(
        f"- Prompts: E4=`{manifest['e4_prompt_version']}`, E5=`{manifest['e5_prompt_version']}`"
    )
    lines.append(f"- Synthetic SEUID: `{manifest['synthetic_seuid']}`")
    lines.append(f"- Started: {manifest['started_at']}")
    lines.append(f"- Finished: {manifest['finished_at']}")
    lines.append(f"- Duration: {manifest['duration_seconds']}s")
    lines.append("")
    lines.append("## Per-syllabus")
    lines.append("")
    lines.append("| Ruolo | SEUID | core | core_score | E4 | E5 |")
    lines.append("|---|---|---|---:|---|---|")
    for r in summary["runs"]:
        role = "synth" if r["role"] == "synthetic_positive_control" else "real"
        lines.append(
            f"| {role} | `{r['seuid'][:8]}…` | {r['core_status']} | "
            f"{r['core_score']} | {r['e4']['outcome']} ({r['e4'].get('score')}) | "
            f"{r['e5']['outcome']} ({r['e5'].get('score')}) |"
        )
    lines.append("")
    lines.append("## Verdetto automatico")
    lines.append("")
    dt = summary["decision_tree"]
    lines.append(f"- synthetic E5: **{dt['synthetic_e5_score']}**")
    lines.append(f"- real E5 (boundary): {dt['real_e5_scores']}")
    lines.append("")
    lines.append(f"> {dt['verdict']}")
    lines.append("")
    lines.append("## Distributions")
    lines.append("")
    lines.append(f"- E4 outcomes: {summary['extended']['E4']['outcomes']}")
    lines.append(f"- E5 outcomes: {summary['extended']['E5']['outcomes']}")
    lines.append(
        f"- Technical NA: {summary['extended']['technical_na_count']} "
        f"(handler_errors={summary['extended']['any_handler_errors']})"
    )
    lines.append(f"- Durations (s): {summary['durations_seconds']}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
