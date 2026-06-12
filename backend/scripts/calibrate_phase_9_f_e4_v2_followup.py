"""Phase 9.F.3 follow-up runner — verifies the e4_v2 fix end-to-end.

The campaign phase_9_f_e4_v2_followup verifies that the
substantiality + partition + threshold changes introduced in
e4_v2 actually correct the Advanced Computer Graphics E4=2 outlier
*without* relaxing any well-calibrated case from the baseline or
the targeted_v1 campaign.

Sample (5 evaluations)
----------------------

Each case carries an *acceptance set* of E4 outcomes. The runner
fails fast if any observed outcome falls outside it — the
campaign is a structural verification, not a rubric exploration.

  | Role  | SEUID       | Course                                | Expected E4 | Acceptance set            | Fail-on |
  |-------|-------------|---------------------------------------|-------------|---------------------------|---------|
  | real  | 3ED4B3BB…   | Advanced Computer Graphics            | 1           | {score:0, score:1}        | score:2 |
  | real  | 3540D939…   | Deep Learning                         | 2           | {score:2}                 | <2      |
  | real  | 0B53E8E2…   | Internet of Things                    | NA semantic | {NA-resolver, NA-handler} | NA tec  |
  | real  | FE97232C…   | Machine Learning (regression guard)   | 0           | {score:0}                 | ≠0      |
  | synth | SYNTHETIC…  | Sistemi distribuiti avanzati (ctrl)   | 2           | {score:2}                 | <2      |

What "fail-on" enforces:
  - ACG must drop below 2: the structural bias of e4_v1 cannot
    persist;
  - Deep Learning and the synthetic positive control must stay at
    2: e4_v2 must not regress well-bilingual cases;
  - IoT must remain NA semantic (resolver OR handler_na), never
    NA-handler_error: e4_v2's stricter substantial check must
    not turn semantic-NA cases into technical failures;
  - Machine Learning must stay at 0: e4_v2 must not over-correct
    by rescuing genuinely bad cases.

Reuses
------
  - the E5 fixture v1 (unchanged) and its idempotent ingestion;
  - the targeted_v1 synthetic syllabus row (already in DB);
  - the partition / drift / artifact-writer plumbing from the
    baseline runner — only the sample, the expectation table and
    the summary semantics differ.

How to run::

    cd backend
    uv run python scripts/calibrate_phase_9_f_e4_v2_followup.py [--yes]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Syllabus  # noqa: E402

# Same shared core as the baseline + targeted runners.
from scripts.calibrate_phase_9_f import (  # noqa: E402
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
    _write_evaluation_json,
    _write_extended_judgments_md,
    _write_report_md,
)


CALIBRATION_MODE = "phase_9_f_e4_v2_followup"
EXPECTED_E4_PROMPT_VERSION = "e4_v2"


# ---------------------------------------------------------------------------
# Sample + expectations
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Expectation:
    """Per-SEUID acceptance criteria.

    ``expected_e4`` is the canonical anchor for the case
    (informational, used to populate the summary). ``accepted_e4``
    is the closed set of outcomes that count as PASS. Anything
    outside it fails the campaign.

    Outcome tokens used here:

      - ``score:0`` / ``score:1`` / ``score:2`` — numeric judgment
      - ``NA-resolver`` — resolver short-circuited the criterion
      - ``NA-handler_na`` — handler returned a semantic NA
        (e.g. e4 pre-LLM check)
      - ``NA-handler_error`` — technical failure (always rejected
        by this campaign)
    """

    seuid: str
    course_label: str
    role: Literal["real", "synthetic_positive_control"]
    expected_e4: str
    accepted_e4: frozenset[str]
    note: str


FOLLOWUP_SAMPLE: tuple[Expectation, ...] = (
    Expectation(
        seuid="3ED4B3BB-D25C-4EA3-BC50-14A310BEF4FF",
        course_label="Advanced Computer Graphics",
        role="real",
        expected_e4="score:1",
        # The fix must drop ACG below 2. Score 0 is a stronger
        # version of the same correction, also acceptable.
        accepted_e4=frozenset({"score:0", "score:1"}),
        note=(
            "course_content_en is empty; e4_v2 must surface the "
            "omission via it_only_substantial and refuse score 2."
        ),
    ),
    Expectation(
        seuid="3540D939-DA16-4C1D-983C-E6B85C403F2F",
        course_label="Deep Learning",
        role="real",
        expected_e4="score:2",
        accepted_e4=frozenset({"score:2"}),
        note=(
            "Fully bilingual baseline case: e4_v2 must not penalise "
            "a syllabus with no omission via the new threshold rule."
        ),
    ),
    Expectation(
        seuid="0B53E8E2-4B90-426F-A25C-3AA31FA4B649",
        course_label="Internet of Things",
        role="real",
        expected_e4="NA-handler_na",
        # The stricter substantial check could push the verdict
        # toward resolver-NA if the handler is never reached, but
        # technical NA remains rejected.
        accepted_e4=frozenset({"NA-resolver", "NA-handler_na"}),
        note=(
            "has_english=True but no paired prefix has substantial "
            "content on both sides. Must remain semantic NA (resolver "
            "or handler), never technical NA."
        ),
    ),
    Expectation(
        seuid="FE97232C-4F07-41F8-A82F-FF73592265EC",
        course_label="Machine Learning",
        role="real",
        expected_e4="score:0",
        # Regression guard: e4_v2 must not rescue a genuinely
        # severe case. score 1 or score 2 are explicit failures.
        accepted_e4=frozenset({"score:0"}),
        note=(
            "Baseline had E4=0 with explicit contradictions on the "
            "EN side; e4_v2 must not relax this verdict."
        ),
    ),
    Expectation(
        seuid="SYNTHETIC-9F-POSITIVE-E5-V1",
        course_label="Sistemi distribuiti avanzati (ctrl)",
        role="synthetic_positive_control",
        expected_e4="score:2",
        accepted_e4=frozenset({"score:2"}),
        note=(
            "Positive control with IT/EN paired on every prefix; "
            "must reach the maximum."
        ),
    ),
)


# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------


def _preflight_e4_v2_in_handler() -> str:
    """Confirm the on-disk handler imports ``e4_v2``.

    This guards against running the follow-up on a branch that
    accidentally still ships e4_v1.
    """
    from app.evaluation.agents.external_prompts.e4_prompt import (
        E4_PROMPT_VERSION,
    )
    if E4_PROMPT_VERSION != EXPECTED_E4_PROMPT_VERSION:
        raise _PreflightError(
            f"E4_PROMPT_VERSION on disk is {E4_PROMPT_VERSION!r}; "
            f"the followup campaign requires {EXPECTED_E4_PROMPT_VERSION!r}. "
            "Make sure the e4_v2 commit is merged into the current branch."
        )
    return E4_PROMPT_VERSION


def _preflight_sample() -> int:
    """Verify every SEUID in the sample exists in the DB and that
    real cases have ``has_english`` set correctly."""
    cdl_ids: set[int] = set()
    with SessionLocal() as session:
        for exp in FOLLOWUP_SAMPLE:
            syl = (
                session.execute(select(Syllabus).where(Syllabus.seuid == exp.seuid))
                .scalar_one_or_none()
            )
            if syl is None:
                raise _PreflightError(
                    f"sample SEUID {exp.seuid!r} ({exp.course_label}) not in DB"
                )
            if exp.role == "real":
                cdl_ids.add(int(syl.cdl_id))
            # Real cases require has_english=True. The synthetic
            # control is exempt (we set it ourselves).
            if exp.role == "real" and not syl.has_english:
                raise _PreflightError(
                    f"real sample SEUID {exp.seuid!r} has has_english=False; "
                    "the followup expects EN-bearing syllabi."
                )
    if len(cdl_ids) != 1:
        raise _PreflightError(
            f"real SEUIDs span multiple CdL ids ({sorted(cdl_ids)})"
        )
    return next(iter(cdl_ids))


def _preflight_output_dir(out: Path) -> None:
    if out.exists() and any(out.iterdir()):
        raise _PreflightError(
            f"output directory {out} is not empty. Pass --output-dir to a "
            "fresh path so previous followup artifacts are not overwritten."
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 9.F e4_v2 follow-up runner")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "data" / "calibration" / "phase_9_f" / "e4_v2_followup",
    )
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--terminal-timeout", type=int, default=900)
    args = parser.parse_args()

    print(f"=== Phase 9.F follow-up ({CALIBRATION_MODE}) — protocol {PROTOCOL_VERSION} ===")

    try:
        fixture_hash = _preflight_check_files()
        e4_prompt_version = _preflight_e4_v2_in_handler()
        cdl_id = _preflight_sample()
        _preflight_output_dir(args.output_dir)
    except _PreflightError as exc:
        print(f"[FAIL] preflight: {exc}")
        return 2

    print(f"\nE4 prompt version on disk: {e4_prompt_version}")
    print(
        f"Sample: {len(FOLLOWUP_SAMPLE)} evaluations "
        f"(4 real + 1 synthetic). Estimate: ≤1 fixture embed round + "
        f"{len(FOLLOWUP_SAMPLE)} real Vertex evaluations."
    )
    if not args.yes and not _confirm():
        print("aborted.")
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc)

    with TestClient(app) as client:
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

        run_summaries: list[dict[str, Any]] = []
        for expectation in FOLLOWUP_SAMPLE:
            print(f"\n--- {expectation.seuid} ({expectation.course_label}) ---")
            try:
                summary = _run_one(
                    client,
                    expectation=expectation,
                    e5_doc=e5_doc,
                    output_dir=args.output_dir,
                    timeout_s=args.terminal_timeout,
                )
            except _RunError as exc:
                print(f"  [FAIL] {exc}")
                return 1
            run_summaries.append(summary)
            print(
                f"  expected={summary['expected_e4']}  "
                f"observed={summary['observed_e4']}  "
                f"verdict={summary['verdict']}"
            )

    # Post-flight: fixture hash unchanged.
    final_fixture_hash = _compute_hash(E5_FIXTURE_PATH)
    if final_fixture_hash != fixture_hash:
        print(
            f"\n[FAIL] fixture hash drifted "
            f"({fixture_hash[:7]} -> {final_fixture_hash[:7]}). "
            "Summary NOT written."
        )
        return 1

    finished_at = datetime.now(timezone.utc)
    manifest = _build_manifest(
        started_at=started_at,
        finished_at=finished_at,
        fixture_hash=fixture_hash,
        e4_prompt_version=e4_prompt_version,
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

    any_fail = any(not r["passed"] for r in run_summaries)
    if any_fail:
        print(
            f"\n=== FOLLOW-UP RED ===\n  → {args.output_dir}\n  "
            f"  Some expectations were violated; see summary.md."
        )
        return 1
    print(f"\n=== ALL FIVE FOLLOWUP RUNS GREEN ===\n  → {args.output_dir}")
    return 0


# ---------------------------------------------------------------------------
# Per-SEUID run + verdict
# ---------------------------------------------------------------------------


def _run_one(
    client: TestClient,
    *,
    expectation: Expectation,
    e5_doc: dict[str, Any],
    output_dir: Path,
    timeout_s: int,
) -> dict[str, Any]:
    started = time.time()
    response = client.post(f"/api/evaluate/{expectation.seuid}")
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

    # Drift check: e4_v2 must be the prompt actually used.
    if hpv.get("E4") and hpv.get("E4") != EXPECTED_E4_PROMPT_VERSION:
        raise _RunError(
            f"E4 prompt drift: got {hpv.get('E4')!r}, "
            f"expected {EXPECTED_E4_PROMPT_VERSION!r}"
        )
    # The other handlers' prompt versions remain pinned.
    if hpv.get("E5") and hpv.get("E5") != E5_PROMPT_VERSION:
        raise _RunError(
            f"E5 prompt drift: got {hpv.get('E5')!r}, "
            f"expected {E5_PROMPT_VERSION!r}"
        )

    e4_judgment = _judgment_for(ext, "E4")
    observed_e4 = _classify_e4_outcome(ext, e4_judgment)
    passed = observed_e4 in expectation.accepted_e4
    verdict = _verdict_text(expectation, observed_e4)

    calibration_header = {
        "calibration_mode": CALIBRATION_MODE,
        "protocol_version": PROTOCOL_VERSION,
        "e5_fixture_version": E5_FIXTURE_VERSION,
        "e4_prompt_version": EXPECTED_E4_PROMPT_VERSION,
        "expected_e4": expectation.expected_e4,
        "observed_e4": observed_e4,
        "role": expectation.role,
    }
    _write_evaluation_json(
        body, e5_doc, output_dir, expectation.seuid,
        calibration_header=calibration_header,
    )
    _write_report_md(body, output_dir, expectation.seuid,
                     calibration_header=calibration_header)
    _write_extended_judgments_md(
        body, output_dir, expectation.seuid,
        calibration_header=calibration_header,
    )

    return {
        "seuid": expectation.seuid,
        "course_label": expectation.course_label,
        "role": expectation.role,
        "evaluation_uuid": evaluation_uuid,
        "core_status": body["status"],
        "core_score": body.get("core_score"),
        "coverage": body.get("coverage"),
        "duration_seconds": elapsed,
        "extended_status": ext["status"],
        "handler_errors": dict(ext.get("handler_errors") or {}),
        "handler_prompt_versions": dict(hpv),
        "expected_e4": expectation.expected_e4,
        "observed_e4": observed_e4,
        "accepted_e4": sorted(expectation.accepted_e4),
        "passed": passed,
        "verdict": verdict,
        "note": expectation.note,
        "e4": _outcome_dict(e4_judgment, ext, "E4"),
        "e5": _outcome_dict(_judgment_for(ext, "E5"), ext, "E5"),
    }


def _judgment_for(ext: dict[str, Any], code: str) -> dict[str, Any] | None:
    for j in ext.get("judgments") or []:
        if j["criterion_code"] == code:
            return j
    return None


def _classify_e4_outcome(
    ext: dict[str, Any], e4_judgment: dict[str, Any] | None,
) -> str:
    """Return the canonical outcome token for E4.

    Tokens (closed set):
      - ``score:0`` / ``score:1`` / ``score:2``
      - ``NA-resolver``
      - ``NA-handler_na``
      - ``NA-handler_error``
    """
    na = next(
        (n for n in (ext.get("na_criteria") or []) if n["criterion_code"] == "E4"),
        None,
    )
    if na is not None:
        return f"NA-{na['source']}"
    if e4_judgment is None:
        return "ABSENT"
    if e4_judgment.get("is_na"):
        # Defensive: na flagged on the judgment but not on na_criteria.
        if e4_judgment.get("is_na_technical"):
            return "NA-handler_error"
        return "NA-handler_na"
    score = e4_judgment.get("score")
    if score in (0, 1, 2):
        return f"score:{score}"
    return "ABSENT"


def _verdict_text(expectation: Expectation, observed: str) -> str:
    if observed in expectation.accepted_e4:
        return f"OK — {observed} ∈ accepted {sorted(expectation.accepted_e4)}"
    return (
        f"FAIL — {observed} ∉ accepted {sorted(expectation.accepted_e4)} "
        f"(expected {expectation.expected_e4})"
    )


# ---------------------------------------------------------------------------
# Manifest + summary
# ---------------------------------------------------------------------------


def _build_manifest(
    *,
    started_at: datetime,
    finished_at: datetime,
    fixture_hash: str,
    e4_prompt_version: str,
    e5_doc: dict[str, Any],
    run_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "calibration_mode": CALIBRATION_MODE,
        "protocol_version": PROTOCOL_VERSION,
        "e5_fixture_version": E5_FIXTURE_VERSION,
        "e4_prompt_version": e4_prompt_version,
        "e5_prompt_version": E5_PROMPT_VERSION,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
        "e5_document": e5_doc,
        "e5_fixture_sha256": fixture_hash,
        "sample": [
            {
                "seuid": e.seuid,
                "course_label": e.course_label,
                "role": e.role,
                "expected_e4": e.expected_e4,
                "accepted_e4": sorted(e.accepted_e4),
            }
            for e in FOLLOWUP_SAMPLE
        ],
        "evaluation_uuids": [s["evaluation_uuid"] for s in run_summaries],
    }


def _build_summary(
    manifest: dict[str, Any],
    run_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    failed = [r for r in run_summaries if not r["passed"]]
    return {
        "calibration_mode": CALIBRATION_MODE,
        "protocol_version": PROTOCOL_VERSION,
        "manifest": manifest,
        "runs": run_summaries,
        "fail_count": len(failed),
        "pass_count": len(run_summaries) - len(failed),
        "overall_verdict": (
            "GREEN — every expectation met"
            if not failed
            else f"RED — {len(failed)} expectation(s) violated"
        ),
        "extended_status_counts": dict(
            Counter(r["extended_status"] for r in run_summaries)
        ),
        "observed_e4_distribution": dict(
            Counter(r["observed_e4"] for r in run_summaries)
        ),
    }


def _render_summary_md(summary: dict[str, Any]) -> str:
    manifest = summary["manifest"]
    lines: list[str] = []
    lines.append(f"# Phase 9.F follow-up — {CALIBRATION_MODE}")
    lines.append("")
    lines.append(f"- Protocol: `{PROTOCOL_VERSION}`")
    lines.append(f"- E4 prompt version: `{manifest['e4_prompt_version']}`")
    lines.append(f"- E5 prompt version: `{manifest['e5_prompt_version']}`")
    lines.append(
        f"- E5 fixture: `{manifest['e5_fixture_version']}` "
        f"(sha {manifest['e5_fixture_sha256'][:7]})"
    )
    lines.append(
        f"- E5 document id: `{manifest['e5_document']['id']}` v{manifest['e5_document']['version']} "
        f"(hash {manifest['e5_document']['file_hash'][:7]}, "
        f"{'reused' if manifest['e5_document']['reused'] else 'uploaded'})"
    )
    lines.append(f"- Started: {manifest['started_at']}")
    lines.append(f"- Finished: {manifest['finished_at']}")
    lines.append(f"- Duration: {manifest['duration_seconds']}s")
    lines.append("")
    lines.append(f"## Overall verdict: {summary['overall_verdict']}")
    lines.append("")
    lines.append("| Role | SEUID | Course | Expected E4 | Observed E4 | Verdict |")
    lines.append("|---|---|---|---|---|---|")
    for r in summary["runs"]:
        role = "synth" if r["role"] == "synthetic_positive_control" else "real"
        marker = "OK" if r["passed"] else "FAIL"
        lines.append(
            f"| {role} | `{r['seuid'][:8]}…` | {r['course_label']} | "
            f"`{r['expected_e4']}` | `{r['observed_e4']}` | **{marker}** |"
        )
    lines.append("")
    lines.append("## Per-run notes")
    lines.append("")
    for r in summary["runs"]:
        lines.append(f"- `{r['seuid']}` — {r['course_label']}")
        lines.append(f"  - {r['note']}")
        lines.append(f"  - accepted set: {r['accepted_e4']}")
        lines.append(f"  - verdict: {r['verdict']}")
    lines.append("")
    lines.append("## Distributions")
    lines.append("")
    lines.append(f"- Observed E4: {summary['observed_e4_distribution']}")
    lines.append(f"- Extended status: {summary['extended_status_counts']}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
