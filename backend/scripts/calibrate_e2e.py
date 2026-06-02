"""Run Phase 5.4.I end-to-end calibration through EvaluationService.

This script intentionally validates the DB-backed path introduced in
Phase 5.4.H:

    DB -> pending EvaluationResult -> graph -> agents -> aggregate
       -> synthesize -> persist EvaluationResult

It uses the same five LM-18 syllabi used for the isolated A1/A2/A3/A4
calibrations and writes diagnostic artifacts under ``data/calibration/e2e_v1``.

The script is diagnostic only: it does not change prompts, anchors or
agent code. Any regression found here should be fixed in a later phase
(for example ``phase-5.4.J``), keeping this run methodologically clean.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow running this script directly from anywhere.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import chromadb  # noqa: E402
import typer  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.evaluation.agents.llm_client import VertexAILLMClient  # noqa: E402
from app.evaluation.orchestrator import build_graph  # noqa: E402
from app.evaluation.rag.embeddings import VertexAIEmbeddings  # noqa: E402
from app.evaluation.rag.retriever import NormativeRetriever  # noqa: E402
from app.evaluation.service import EvaluationService  # noqa: E402

console = Console()
app = typer.Typer(help=__doc__, no_args_is_help=False)


# Same calibration set used by A3/A4 v2 fixtures.
DEFAULT_SEUIDS: list[str] = [
    "3540D939-DA16-4C1D-983C-E6B85C403F2F",
    "E2446DF6-59A1-46FD-B8D8-635EB937C1B3",
    "F4AF1512-9D7A-4256-B57D-E103E05B009B",
    "FE97232C-4F07-41F8-A82F-FF73592265EC",
    "0B53E8E2-4B90-426F-A25C-3AA31FA4B649",
]

CRITERIA_ORDER: tuple[str, ...] = (
    "C1",
    "C2",
    "C3",
    "C4",
    "C5",
    "C6",
    "C7",
    "C8",
    "C9",
)

AGENT_CODES: tuple[str, ...] = ("a1", "a2", "a3", "a4")
REDACTED = "<REDACTED>"


@app.command()
def main(
    output_dir: Path = typer.Option(
        _PROJECT_ROOT / "data" / "calibration" / "e2e_v1",
        "--output-dir",
        help="Directory where E2E calibration artifacts are written.",
    ),
    baseline_dir: Path = typer.Option(
        _BACKEND_DIR / "tests" / "fixtures" / "llm_responses",
        "--baseline-dir",
        help="Directory containing isolated A1/A2/A3/A4 calibration fixtures.",
    ),
    seuids: list[str] | None = typer.Option(
        None,
        "--seuid",
        help="Override the default 5-syllabus calibration set.",
    ),
    redact_project_id: bool = typer.Option(
        True,
        "--redact-project-id/--keep-project-id",
        help="Redact gcp_project_id in saved artifacts (default: True).",
    ),
    fail_fast: bool = typer.Option(
        False,
        "--fail-fast/--keep-going",
        help="Stop after the first run-level exception.",
    ),
) -> None:
    """Run DB-backed E2E calibration and write JSON/Markdown artifacts."""

    started_at = datetime.now(timezone.utc)
    output_dir.mkdir(parents=True, exist_ok=True)
    _ensure_local_schema()

    service = _build_service()
    seuids_to_run = seuids or DEFAULT_SEUIDS

    runs: list[dict[str, Any]] = []
    for seuid in seuids_to_run:
        console.rule(f"[bold]E2E[/bold] {seuid}")
        try:
            run_summary = _run_one(
                service=service,
                seuid=seuid,
                output_dir=output_dir,
                baseline_dir=baseline_dir,
                redact_project_id=redact_project_id,
            )
        except Exception as exc:  # noqa: BLE001 - diagnostic script
            run_summary = _run_exception_summary(seuid, exc)
            _write_json(output_dir / f"{_safe_name(seuid)}__evaluation.json", run_summary)
            console.print(f"[red]ERROR[/red] {seuid}: {type(exc).__name__}: {exc}")
            if fail_fast:
                raise typer.Exit(code=1) from exc

        runs.append(run_summary)
        _print_run_result(run_summary)

    summary = _build_summary(started_at, output_dir, baseline_dir, runs)
    if redact_project_id:
        _redact_gcp_project_id(summary)

    _write_json(output_dir / "summary.json", summary)
    (output_dir / "summary.md").write_text(
        _render_summary_markdown(summary), encoding="utf-8"
    )
    _print_summary_table(summary["runs"])
    console.print(f"\n[green]Artifacts written to[/green] {output_dir}")


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
    llm_client = VertexAILLMClient(project_id=project_id, location=location, scientific=sci)

    def _graph_invoker(
        initial_state: dict[str, Any],
        *,
        progress_publisher: Any | None = None,
    ) -> dict[str, Any]:
        graph = build_graph(
            retriever=retriever,
            llm_client=llm_client,
            progress_publisher=progress_publisher,
        )
        return graph.invoke(initial_state)

    return EvaluationService(
        session_factory=SessionLocal,
        graph_invoker=_graph_invoker,
        settings=settings,
    )


def _run_one(
    *,
    service: EvaluationService,
    seuid: str,
    output_dir: Path,
    baseline_dir: Path,
    redact_project_id: bool,
) -> dict[str, Any]:
    progress_events: list[dict[str, Any]] = []

    def _capture_event(event: dict[str, Any]) -> None:
        progress_events.append({"captured_at": _now_iso(), **event})

    started = time.time()
    record = service.evaluate(seuid, progress_publisher=_capture_event)
    elapsed_seconds = round(time.time() - started, 2)

    evaluation = _evaluation_record_to_dict(record)
    baseline = _load_baseline(seuid, baseline_dir)
    comparison = _compare_scores(
        expected=baseline["criterion_scores"],
        actual=evaluation.get("criterion_scores") or {},
    )
    success = _success_diagnostics(evaluation, comparison)

    payload = {
        "phase": "5.4.I",
        "mode": "db_backed_evaluation_service",
        "seuid": seuid,
        "elapsed_seconds": elapsed_seconds,
        "evaluation": evaluation,
        "baseline": baseline,
        "comparison": comparison,
        "success": success,
        "progress_events": progress_events,
    }
    if redact_project_id:
        _redact_gcp_project_id(payload)

    safe = _safe_name(seuid)
    _write_json(output_dir / f"{safe}__evaluation.json", payload)
    (output_dir / f"{safe}__report.md").write_text(
        evaluation.get("final_report") or "_Nessun report generato._\n",
        encoding="utf-8",
    )
    return _compact_run_summary(payload)


def _evaluation_record_to_dict(record: Any) -> dict[str, Any]:
    fields = [
        "id",
        "evaluation_uuid",
        "syllabus_id",
        "syllabus_seuid_snapshot",
        "course_name_snapshot",
        "status",
        "started_at",
        "finished_at",
        "duration_ms",
        "error_message",
        "llm_model",
        "embedding_model",
        "embedding_dim",
        "llm_temperature",
        "llm_max_output_tokens",
        "rag_top_k",
        "rag_final_k",
        "rag_similarity_threshold",
        "gcp_project_id",
        "gcp_location",
        "prompt_versions",
        "core_score",
        "coverage",
        "criterion_scores",
        "na_criteria",
        "agent_outputs",
        "agent_errors",
        "retrieved_chunks",
        "final_report",
    ]
    return {field: _jsonable(getattr(record, field)) for field in fields}


def _load_baseline(seuid: str, baseline_dir: Path) -> dict[str, Any]:
    scores: dict[str, int | None] = {}
    missing_files: list[str] = []
    source_files: list[str] = []

    for agent in AGENT_CODES:
        path = baseline_dir / f"{agent}_calibration_{seuid}.json"
        if not path.exists():
            missing_files.append(str(path))
            continue

        source_files.append(str(path))
        payload = json.loads(path.read_text(encoding="utf-8"))
        agent_output = payload.get("agent_output") or {}
        for judgment in agent_output.get("judgments") or []:
            criterion = judgment.get("criterion_code")
            if criterion:
                scores[criterion] = None if judgment.get("is_na") else judgment.get("score")

    return {
        "criterion_scores": _ordered_scores(scores),
        "missing_files": missing_files,
        "source_files": source_files,
    }


def _compare_scores(
    *,
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> dict[str, Any]:
    flags: list[dict[str, Any]] = []
    deltas: dict[str, int | None] = {}

    for criterion in CRITERIA_ORDER:
        exp = expected.get(criterion)
        act = actual.get(criterion)
        delta = act - exp if isinstance(exp, int) and isinstance(act, int) else None
        deltas[criterion] = delta

        if exp == act:
            continue

        severity = "drift"
        if delta is None or abs(delta) > 1:
            severity = "regression"
        flags.append(
            {
                "criterion": criterion,
                "expected": exp,
                "actual": act,
                "delta": delta,
                "severity": severity,
            }
        )

    regression_count = sum(1 for flag in flags if flag["severity"] == "regression")
    return {
        "expected_scores": _ordered_scores(expected),
        "actual_scores": _ordered_scores(actual),
        "deltas": deltas,
        "regression_flags": flags,
        "regression_count": regression_count,
        "global_regression": regression_count > 2,
    }


def _success_diagnostics(
    evaluation: dict[str, Any],
    comparison: dict[str, Any],
) -> dict[str, Any]:
    status = evaluation.get("status")
    agent_errors = evaluation.get("agent_errors") or {}
    coverage = evaluation.get("coverage")
    duration_ms = evaluation.get("duration_ms")

    if status == "completed":
        failure_classification = "none"
    elif status == "partial" and not agent_errors:
        failure_classification = "expected_partial_due_to_missing_syllabus_fields"
    else:
        failure_classification = "unexpected_failure"

    return {
        "status_ok": status == "completed"
        or failure_classification == "expected_partial_due_to_missing_syllabus_fields",
        "failure_classification": failure_classification,
        "agent_errors_ok": not bool(agent_errors),
        "coverage_ok": isinstance(coverage, int | float) and coverage >= 0.78,
        "duration_ok": isinstance(duration_ms, int) and duration_ms <= 60_000 * 4,
        "global_regression_ok": not comparison["global_regression"],
    }


def _compact_run_summary(payload: dict[str, Any]) -> dict[str, Any]:
    evaluation = payload["evaluation"]
    comparison = payload["comparison"]
    return {
        "seuid": payload["seuid"],
        "evaluation_uuid": evaluation.get("evaluation_uuid"),
        "course_name": evaluation.get("course_name_snapshot"),
        "status": evaluation.get("status"),
        "core_score": evaluation.get("core_score"),
        "coverage": evaluation.get("coverage"),
        "duration_ms": evaluation.get("duration_ms"),
        "criterion_scores": evaluation.get("criterion_scores"),
        "agent_errors": evaluation.get("agent_errors"),
        "regression_flags": comparison["regression_flags"],
        "success": payload["success"],
        "artifact_files": {
            "evaluation_json": f"{payload['seuid']}__evaluation.json",
            "report_md": f"{payload['seuid']}__report.md",
        },
    }


def _run_exception_summary(seuid: str, exc: BaseException) -> dict[str, Any]:
    return {
        "seuid": seuid,
        "status": "script_error",
        "error": {
            "type": type(exc).__name__,
            "message": str(exc),
        },
        "success": {
            "status_ok": False,
            "failure_classification": "unexpected_failure",
            "agent_errors_ok": False,
            "coverage_ok": False,
            "duration_ok": False,
            "global_regression_ok": False,
        },
    }


def _build_summary(
    started_at: datetime,
    output_dir: Path,
    baseline_dir: Path,
    runs: list[dict[str, Any]],
) -> dict[str, Any]:
    completed = sum(1 for run in runs if run.get("status") == "completed")
    partial = sum(1 for run in runs if run.get("status") == "partial")
    failed = sum(1 for run in runs if run.get("status") in {"failed", "script_error"})
    unexpected = sum(
        1
        for run in runs
        if run.get("success", {}).get("failure_classification") == "unexpected_failure"
    )
    regressions = sum(
        1
        for run in runs
        if not run.get("success", {}).get("global_regression_ok", False)
    )
    coverage_values = [
        run["coverage"] for run in runs if isinstance(run.get("coverage"), int | float)
    ]
    durations = [
        run["duration_ms"] for run in runs if isinstance(run.get("duration_ms"), int)
    ]

    return {
        "phase": "5.4.I",
        "mode": "db_backed_evaluation_service",
        "generated_at": _now_iso(),
        "started_at": started_at.isoformat(),
        "output_dir": str(output_dir),
        "baseline_dir": str(baseline_dir),
        "success_thresholds": {
            "coverage_min": 0.78,
            "duration_max_ms": 60_000 * 4,
            "accepted_score_drift_abs": 1,
            "global_regression_if_regression_flags_gt": 2,
        },
        "aggregate": {
            "total": len(runs),
            "completed": completed,
            "partial": partial,
            "failed_or_script_error": failed,
            "unexpected_failures": unexpected,
            "runs_with_global_regression": regressions,
            "mean_coverage": round(sum(coverage_values) / len(coverage_values), 3)
            if coverage_values
            else None,
            "mean_duration_ms": round(sum(durations) / len(durations), 1)
            if durations
            else None,
        },
        "runs": runs,
    }


def _render_summary_markdown(summary: dict[str, Any]) -> str:
    agg = summary["aggregate"]
    lines = [
        "# Phase 5.4.I — E2E Calibration Summary",
        "",
        f"- Mode: `{summary['mode']}`",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Output dir: `{summary['output_dir']}`",
        f"- Total runs: **{agg['total']}**",
        f"- Completed: **{agg['completed']}**",
        f"- Partial: **{agg['partial']}**",
        f"- Failed/script error: **{agg['failed_or_script_error']}**",
        f"- Unexpected failures: **{agg['unexpected_failures']}**",
        f"- Runs with global regression: **{agg['runs_with_global_regression']}**",
        "",
        "| Syllabus | Status | CoreScore | Coverage | Duration | Flags |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for run in summary["runs"]:
        flags = len(run.get("regression_flags") or [])
        duration = _format_duration(run.get("duration_ms"))
        core = _format_number(run.get("core_score"))
        coverage = _format_percent(run.get("coverage"))
        course = (run.get("course_name") or run.get("seuid") or "?").replace("|", "\\|")
        lines.append(
            f"| {course} | {run.get('status')} | {core} | {coverage} | {duration} | {flags} |"
        )
    lines.append("")
    lines.append("## Regression Flags")
    lines.append("")
    for run in summary["runs"]:
        flags = run.get("regression_flags") or []
        if not flags:
            continue
        lines.append(f"### {run.get('course_name') or run.get('seuid')}")
        lines.append("")
        for flag in flags:
            lines.append(
                "- "
                f"{flag['criterion']}: expected `{flag['expected']}`, "
                f"actual `{flag['actual']}`, delta `{flag['delta']}`, "
                f"severity `{flag['severity']}`"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _ensure_local_schema() -> None:
    """Mirror the lightweight startup schema guard used by FastAPI."""
    if engine.dialect.name == "sqlite":
        inspector = inspect(engine)
        if "evaluation_results" in inspector.get_table_names():
            columns = {c["name"] for c in inspector.get_columns("evaluation_results")}
            if "evaluation_uuid" not in columns:
                with engine.begin() as conn:
                    conn.execute(text("DROP TABLE evaluation_results"))

    Base.metadata.create_all(engine)


def _ordered_scores(scores: dict[str, Any]) -> dict[str, Any]:
    return {criterion: scores.get(criterion) for criterion in CRITERIA_ORDER}


def _redact_gcp_project_id(obj: Any) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "gcp_project_id":
                obj[key] = REDACTED
            else:
                _redact_gcp_project_id(value)
    elif isinstance(obj, list):
        for item in obj:
            _redact_gcp_project_id(item)


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_number(value: Any) -> str:
    return f"{value:.2f}" if isinstance(value, int | float) else "—"


def _format_percent(value: Any) -> str:
    return f"{value:.0%}" if isinstance(value, int | float) else "—"


def _format_duration(value: Any) -> str:
    return f"{value / 1000:.1f}s" if isinstance(value, int) else "—"


def _print_run_result(run: dict[str, Any]) -> None:
    success = run.get("success", {})
    style = "green" if all(success.values()) else "yellow"
    if success.get("failure_classification") == "unexpected_failure":
        style = "red"
    console.print(
        f"[{style}]{run.get('status')}[/{style}] "
        f"{run.get('course_name') or run.get('seuid')} "
        f"CoreScore={_format_number(run.get('core_score'))} "
        f"coverage={_format_percent(run.get('coverage'))} "
        f"flags={len(run.get('regression_flags') or [])}"
    )


def _print_summary_table(runs: list[dict[str, Any]]) -> None:
    table = Table(title="Phase 5.4.I E2E summary", show_header=True)
    table.add_column("course")
    table.add_column("status")
    table.add_column("core")
    table.add_column("coverage")
    table.add_column("duration")
    table.add_column("flags")
    for run in runs:
        table.add_row(
            str(run.get("course_name") or run.get("seuid")),
            str(run.get("status")),
            _format_number(run.get("core_score")),
            _format_percent(run.get("coverage")),
            _format_duration(run.get("duration_ms")),
            str(len(run.get("regression_flags") or [])),
        )
    console.print(table)


if __name__ == "__main__":
    app()
