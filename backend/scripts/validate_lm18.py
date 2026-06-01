"""Phase 5.7 — Final validation on the 30 LM-18 syllabi.

This script runs the full DB-backed evaluation pipeline introduced in
Phase 5.4.H through EvaluationService.evaluate(seuid) for each of the
30 syllabi selected for the thesis validation. The selection
rationale is in ``docs/validation_lm18_selection.md`` (anno 1 + anno 2
obbligatori, inclusi moduli/laboratori come syllabi autonomi quando
presenti, esclusi i corsi a scelta non comparabili sui criteri C1-C9).

For each syllabus the script writes:

  - ``{seuid}__evaluation.json``  full EvaluationResult dump, with
    ``gcp_project_id`` redacted (D027)
  - ``{seuid}__report.md``        deterministic synthesizer report

After the 30 runs:

  - ``summary.json``  matrix 30x9 + per-criterion statistics + status
                       counts + CoreScore distribution + outlier list
  - ``summary.md``    a thesis-ready Markdown rendering of the same

The script is diagnostic only: it does not change prompts, anchors or
agent code. Any correction surfaced here should land in a separate
phase, keeping this run methodologically clean.

Default behaviour is RESUME: if a per-syllabus dump already exists with
``status in {completed, partial}`` the run is skipped. Pass
``--no-resume`` to force re-run all 30 from scratch.
"""
from __future__ import annotations

import json
import math
import statistics
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


# The 30 LM-18 syllabi selected for the thesis validation
# (docs/validation_lm18_selection.md). Order is preserved for the
# summary table.
DEFAULT_SEUIDS: list[str] = [
    "C4EC1456-0EAA-4027-8124-DE01362473AB",  # ALGORITMI E COMPLESSITA'
    "3ED4B3BB-D25C-4EA3-BC50-14A310BEF4FF",  # Advanced Computer Graphics
    "F8F95848-EC28-4612-BFAC-04AA3C2BE963",  # BLOCKCHAIN E CRYPTOCURRENCIES
    "AC75068C-71BE-4278-9CFE-02EBC624B287",  # BLOCKCHAIN E CRYPTOCURRENCIES (II)
    "FA050289-238A-4FF5-9DB4-7588D977E793",  # COMPUTER SECURITY E LABORATORIO / COMPUTER SECURITY
    "5CCCDB2A-58B8-45A9-8AE9-EA9CE73AA8A3",  # COMPUTER SECURITY E LABORATORIO / LABORATORIO
    "89E21813-A17C-4C85-AF65-C295EE11ED59",  # COMPUTER VISION
    "DADC30FD-2222-4C43-BAB8-A57D08667196",  # CRITTOGRAFIA
    "F8FEDEFE-56FC-4031-9E0E-8726B202B9C1",  # Computer Security
    "3540D939-DA16-4C1D-983C-E6B85C403F2F",  # Deep Learning / Advanced Models and Methods
    "414654A5-811B-4AAB-9031-836CC788F119",  # Deep Learning / Core Models and Methods
    "1408B85C-60A2-4799-8D51-24AEBC1023D2",  # Deep Learning / Core Models and Methods (II)
    "CE3B947A-B024-46B9-B8ED-A8C59DC0C4F7",  # INGEGNERIA DEI SISTEMI DISTRIBUITI / SISTEMI
    "9A85B8E4-05CD-4707-897F-51023B5BB46A",  # INGEGNERIA DEI SISTEMI DISTRIBUITI / LABORATORIO
    "FE97232C-4F07-41F8-A82F-FF73592265EC",  # MACHINE LEARNING
    "9A90BBCE-99E3-4FB0-BF91-CCAAA5C51791",  # MULTIMEDIA E LABORATORIO / MULTIMEDIA
    "A9E33FF0-2CFD-4A51-BE84-E11130C98BFB",  # MULTIMEDIA E LABORATORIO / MULTIMEDIA (II)
    "D5CD7C87-9BF4-4E65-9101-A58FB1522C97",  # MULTIMEDIA E LABORATORIO / LABORATORIO
    "E2446DF6-59A1-46FD-B8D8-635EB937C1B3",  # OTTIMIZZAZIONE
    "27066AED-24A0-4A9C-8AC4-E5C8006ACCF3",  # Sistemi Cloud
    "B99A46CC-D23B-4987-91AF-A2ECCFBAC778",  # COMPUTER VISION E LABORATORIO / VISION
    "88B7C1CE-B595-46A5-A37A-C5414AD807B5",  # COMPUTER VISION E LABORATORIO / LABORATORIO
    "AE4C5A2B-9189-423F-83A0-280C8B1BCEB6",  # CRYPTOGRAPHIC ENGINEERING
    "E6CA35FC-6E63-4B25-BCB8-B73F6461DD31",  # DEEP LEARNING
    "0B53E8E2-4B90-426F-A25C-3AA31FA4B649",  # INTERNET OF THINGS
    "C6F1C332-B4AC-407B-B9BC-0066EBA4E790",  # PEER TO PEER AND WIRELESS NETWORKS / P2P
    "F4AF1512-9D7A-4256-B57D-E103E05B009B",  # PEER TO PEER AND WIRELESS NETWORKS / LABORATORIO
    "71D7A8F2-8C72-4689-8522-A1B79F21A9C8",  # QUANTUM COMPUTER PROGRAMMING
    "EEA0EC5A-8D82-4B7B-A85C-94DEC5070EEB",  # SISTEMI CLOUD E LABORATORIO / SISTEMI CLOUD
    "46D62804-0FCD-4478-A51D-A752B64A7DCB",  # VAPT
]

CRITERIA_ORDER: tuple[str, ...] = (
    "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9",
)

REDACTED = "<REDACTED>"


@app.command()
def main(
    output_dir: Path = typer.Option(
        _PROJECT_ROOT / "data" / "calibration" / "validation_lm18",
        "--output-dir",
        help="Directory where validation artifacts are written.",
    ),
    seuids: list[str] | None = typer.Option(
        None,
        "--seuid",
        help="Override the default 30-syllabus validation set.",
    ),
    redact_project_id: bool = typer.Option(
        True,
        "--redact-project-id/--keep-project-id",
        help="Redact gcp_project_id in saved artifacts (default: True, D027).",
    ),
    resume: bool = typer.Option(
        True,
        "--resume/--no-resume",
        help=(
            "Skip syllabi whose dump already exists with status in "
            "{completed, partial}. Default ON; pass --no-resume to force "
            "re-run all 30 from scratch."
        ),
    ),
    fail_fast: bool = typer.Option(
        False,
        "--fail-fast/--keep-going",
        help="Stop after the first run-level exception.",
    ),
) -> None:
    """Run DB-backed validation on the 30 LM-18 syllabi and aggregate stats."""

    started_at = datetime.now(timezone.utc)
    output_dir.mkdir(parents=True, exist_ok=True)
    _ensure_local_schema()

    seuids_to_run = list(seuids) if seuids else DEFAULT_SEUIDS
    console.rule(f"[bold]Phase 5.7 validation[/bold]  N={len(seuids_to_run)}")
    console.print(f"output_dir = {output_dir}")
    console.print(f"resume = {resume}  redact_project_id = {redact_project_id}")

    service = _build_service()
    runs: list[dict[str, Any]] = []

    for idx, seuid in enumerate(seuids_to_run, 1):
        console.rule(f"[bold]{idx}/{len(seuids_to_run)}[/bold]  {seuid}")
        resumed = _maybe_resume(output_dir, seuid) if resume else None
        if resumed is not None:
            console.print(
                f"[yellow]SKIP[/yellow] {seuid} (already {resumed.get('status')!r})"
            )
            runs.append(resumed)
            continue
        try:
            summary = _run_one(
                service=service,
                seuid=seuid,
                output_dir=output_dir,
                redact_project_id=redact_project_id,
            )
        except Exception as exc:  # noqa: BLE001 — diagnostic script
            summary = _run_exception_summary(seuid, exc)
            _write_json(
                output_dir / f"{_safe_name(seuid)}__evaluation.json", summary
            )
            console.print(
                f"[red]ERROR[/red] {seuid}: {type(exc).__name__}: {exc}"
            )
            if fail_fast:
                raise typer.Exit(code=1) from exc

        runs.append(summary)
        _print_run_result(summary)

    aggregate = _build_aggregate(started_at, output_dir, runs)
    if redact_project_id:
        _redact_gcp_project_id(aggregate)

    _write_json(output_dir / "summary.json", aggregate)
    (output_dir / "summary.md").write_text(
        _render_summary_markdown(aggregate), encoding="utf-8"
    )
    _print_summary_table(aggregate["runs"])
    console.print(f"\n[green]Artifacts written to[/green] {output_dir}")


# === service / single-run plumbing ==========================================


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
    llm_client = VertexAILLMClient(
        project_id=project_id, location=location, scientific=sci
    )

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
    redact_project_id: bool,
) -> dict[str, Any]:
    progress_events: list[dict[str, Any]] = []

    def _capture_event(event: dict[str, Any]) -> None:
        progress_events.append({"captured_at": _now_iso(), **event})

    started = time.time()
    record = service.evaluate(seuid, progress_publisher=_capture_event)
    elapsed_seconds = round(time.time() - started, 2)

    evaluation = _evaluation_record_to_dict(record)
    payload = {
        "phase": "5.7",
        "mode": "validation_lm18",
        "seuid": seuid,
        "elapsed_seconds": elapsed_seconds,
        "evaluation": evaluation,
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
        "id", "evaluation_uuid", "syllabus_id", "syllabus_seuid_snapshot",
        "course_name_snapshot", "status", "started_at", "finished_at",
        "duration_ms", "error_message",
        "llm_model", "embedding_model", "embedding_dim",
        "llm_temperature", "llm_max_output_tokens",
        "rag_top_k", "rag_final_k", "rag_similarity_threshold",
        "gcp_project_id", "gcp_location", "prompt_versions",
        "core_score", "coverage", "criterion_scores", "na_criteria",
        "agent_outputs", "agent_errors", "retrieved_chunks", "final_report",
    ]
    return {field: _jsonable(getattr(record, field)) for field in fields}


def _compact_run_summary(payload: dict[str, Any]) -> dict[str, Any]:
    e = payload["evaluation"]
    return {
        "seuid": payload["seuid"],
        "evaluation_uuid": e.get("evaluation_uuid"),
        "course_name": e.get("course_name_snapshot"),
        "status": e.get("status"),
        "core_score": e.get("core_score"),
        "coverage": e.get("coverage"),
        "duration_ms": e.get("duration_ms"),
        "criterion_scores": e.get("criterion_scores"),
        "agent_errors": e.get("agent_errors"),
        "n_na": len(e.get("na_criteria") or []),
        "artifact_files": {
            "evaluation_json": f"{payload['seuid']}__evaluation.json",
            "report_md": f"{payload['seuid']}__report.md",
        },
    }


def _maybe_resume(output_dir: Path, seuid: str) -> dict[str, Any] | None:
    """Return a compact run summary if a prior dump exists in a final status."""
    path = output_dir / f"{_safe_name(seuid)}__evaluation.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if payload.get("phase") != "5.7":
        return None
    status = (payload.get("evaluation") or {}).get("status")
    if status not in {"completed", "partial"}:
        return None
    return _compact_run_summary(payload)


def _run_exception_summary(seuid: str, exc: BaseException) -> dict[str, Any]:
    return {
        "seuid": seuid,
        "status": "script_error",
        "error": {"type": type(exc).__name__, "message": str(exc)},
    }


# === aggregation ============================================================


def _build_aggregate(
    started_at: datetime,
    output_dir: Path,
    runs: list[dict[str, Any]],
) -> dict[str, Any]:
    completed = [r for r in runs if r.get("status") == "completed"]
    partial = [r for r in runs if r.get("status") == "partial"]
    failed = [
        r for r in runs if r.get("status") in {"failed", "script_error"}
    ]
    valid = completed + partial  # runs with a CoreScore

    # Per-criterion statistics
    per_criterion: dict[str, dict[str, Any]] = {}
    for crit in CRITERIA_ORDER:
        scores: list[int] = []
        na_count = 0
        counts = {0: 0, 1: 0, 2: 0}
        for r in valid:
            cs = (r.get("criterion_scores") or {}).get(crit)
            if cs is None:
                na_count += 1
            elif isinstance(cs, int):
                scores.append(cs)
                if cs in counts:
                    counts[cs] += 1
        n_eval = len(scores)
        per_criterion[crit] = {
            "n_evaluated": n_eval,
            "n_na": na_count,
            "na_rate": round(na_count / len(valid), 3) if valid else None,
            "count_score_0": counts[0],
            "count_score_1": counts[1],
            "count_score_2": counts[2],
            "mean": round(statistics.mean(scores), 3) if scores else None,
            "stdev": (
                round(statistics.stdev(scores), 3) if len(scores) >= 2 else None
            ),
        }

    # CoreScore + coverage distributions
    core_scores = [
        r["core_score"] for r in valid if isinstance(r.get("core_score"), int | float)
    ]
    coverages = [
        r["coverage"] for r in valid if isinstance(r.get("coverage"), int | float)
    ]
    durations = [
        r["duration_ms"] for r in runs if isinstance(r.get("duration_ms"), int)
    ]

    core_summary = {
        "n": len(core_scores),
        "mean": round(statistics.mean(core_scores), 3) if core_scores else None,
        "median": (
            round(statistics.median(core_scores), 3) if core_scores else None
        ),
        "stdev": (
            round(statistics.stdev(core_scores), 3)
            if len(core_scores) >= 2
            else None
        ),
        "min": min(core_scores) if core_scores else None,
        "max": max(core_scores) if core_scores else None,
        "distribution": _bucket_core_score(core_scores),
    }
    coverage_summary = {
        "n": len(coverages),
        "mean": round(statistics.mean(coverages), 3) if coverages else None,
        "fully_covered": sum(1 for c in coverages if math.isclose(c, 1.0)),
        "below_full": sum(1 for c in coverages if c < 1.0),
    }

    # Outliers
    outliers = {
        "low_core_score": sorted(
            [
                {
                    "seuid": r["seuid"],
                    "course_name": r.get("course_name"),
                    "core_score": r.get("core_score"),
                }
                for r in valid
                if isinstance(r.get("core_score"), int | float)
                and r["core_score"] < 1.0
            ],
            key=lambda x: x["core_score"] or 0,
        ),
        "incomplete_coverage": [
            {
                "seuid": r["seuid"],
                "course_name": r.get("course_name"),
                "coverage": r.get("coverage"),
                "n_na": r.get("n_na"),
            }
            for r in valid
            if isinstance(r.get("coverage"), int | float) and r["coverage"] < 1.0
        ],
        "non_completed": [
            {
                "seuid": r["seuid"],
                "course_name": r.get("course_name"),
                "status": r.get("status"),
                "agent_errors": r.get("agent_errors"),
            }
            for r in runs
            if r.get("status") != "completed"
        ],
    }

    return {
        "phase": "5.7",
        "mode": "validation_lm18",
        "generated_at": _now_iso(),
        "started_at": started_at.isoformat(),
        "output_dir": str(output_dir),
        "totals": {
            "n_runs": len(runs),
            "n_completed": len(completed),
            "n_partial": len(partial),
            "n_failed": len(failed),
        },
        "duration": {
            "mean_ms": round(statistics.mean(durations), 1) if durations else None,
            "median_ms": (
                round(statistics.median(durations), 1) if durations else None
            ),
            "total_seconds": round(sum(durations) / 1000.0, 1) if durations else None,
        },
        "core_score": core_summary,
        "coverage": coverage_summary,
        "per_criterion": per_criterion,
        "outliers": outliers,
        "runs": runs,
    }


def _bucket_core_score(scores: list[float]) -> dict[str, int]:
    buckets = {
        "0.0_0.5": 0,
        "0.5_1.0": 0,
        "1.0_1.5": 0,
        "1.5_2.0": 0,
        "2.0": 0,
    }
    for s in scores:
        if math.isclose(s, 2.0):
            buckets["2.0"] += 1
        elif s >= 1.5:
            buckets["1.5_2.0"] += 1
        elif s >= 1.0:
            buckets["1.0_1.5"] += 1
        elif s >= 0.5:
            buckets["0.5_1.0"] += 1
        else:
            buckets["0.0_0.5"] += 1
    return buckets


# === rendering ==============================================================


def _render_summary_markdown(summary: dict[str, Any]) -> str:
    t = summary["totals"]
    cs = summary["core_score"]
    cv = summary["coverage"]
    d = summary["duration"]

    lines = [
        "# Phase 5.7 — Validation Summary (LM-18, 30 syllabi)",
        "",
        f"- Mode: `{summary['mode']}`",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Output dir: `{summary['output_dir']}`",
        "",
        "## Status",
        "",
        f"- Runs: **{t['n_runs']}** "
        f"(completed **{t['n_completed']}**, partial **{t['n_partial']}**, "
        f"failed **{t['n_failed']}**)",
        f"- Mean duration per run: **{_fmt_ms(d['mean_ms'])}** "
        f"(median {_fmt_ms(d['median_ms'])}, "
        f"total {_fmt_seconds(d['total_seconds'])})",
        "",
        "## CoreScore distribution",
        "",
        f"- N (valid runs) = **{cs['n']}**",
        f"- Mean = **{_fmt_num(cs['mean'])}**  median = "
        f"**{_fmt_num(cs['median'])}**  stdev = **{_fmt_num(cs['stdev'])}**",
        f"- Range = [{_fmt_num(cs['min'])}, {_fmt_num(cs['max'])}]",
        "",
        "| Bucket | Count |",
        "| --- | ---: |",
    ]
    for bucket, count in cs["distribution"].items():
        label = bucket.replace("_", " - ")
        lines.append(f"| {label} | {count} |")
    lines += [
        "",
        "## Coverage",
        "",
        f"- N = **{cv['n']}**  mean = **{_fmt_percent(cv['mean'])}**",
        f"- Fully covered (100%): **{cv['fully_covered']}**  "
        f"below full: **{cv['below_full']}**",
        "",
        "## Per-criterion statistics",
        "",
        "| Crit | N eval | N NA | NA rate | 0 | 1 | 2 | mean | stdev |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for crit in CRITERIA_ORDER:
        s = summary["per_criterion"][crit]
        lines.append(
            f"| {crit} | {s['n_evaluated']} | {s['n_na']} | "
            f"{_fmt_percent(s['na_rate'])} | "
            f"{s['count_score_0']} | {s['count_score_1']} | "
            f"{s['count_score_2']} | "
            f"{_fmt_num(s['mean'])} | {_fmt_num(s['stdev'])} |"
        )

    lines += [
        "",
        "## Matrix — per-syllabus criterion scores",
        "",
        "| # | Syllabus | Status | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | C9 | CoreScore | Coverage |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for i, run in enumerate(summary["runs"], 1):
        course = (run.get("course_name") or run.get("seuid") or "?").replace(
            "|", "\\|"
        )[:50]
        cs_row = run.get("criterion_scores") or {}
        cell_scores = " | ".join(_fmt_score(cs_row.get(c)) for c in CRITERIA_ORDER)
        lines.append(
            f"| {i} | {course} | {run.get('status')} | {cell_scores} | "
            f"{_fmt_num(run.get('core_score'))} | "
            f"{_fmt_percent(run.get('coverage'))} |"
        )

    out = summary["outliers"]
    lines += [
        "",
        "## Outliers",
        "",
        f"### CoreScore < 1.0 ({len(out['low_core_score'])})",
        "",
    ]
    for o in out["low_core_score"]:
        lines.append(
            f"- `{o['seuid'][:8]}`  {o['course_name']}  CoreScore = "
            f"**{_fmt_num(o['core_score'])}**"
        )
    lines += [
        "",
        f"### Coverage < 100% ({len(out['incomplete_coverage'])})",
        "",
    ]
    for o in out["incomplete_coverage"]:
        lines.append(
            f"- `{o['seuid'][:8]}`  {o['course_name']}  "
            f"coverage = **{_fmt_percent(o['coverage'])}**  "
            f"(NA: {o.get('n_na')})"
        )
    lines += [
        "",
        f"### Status != completed ({len(out['non_completed'])})",
        "",
    ]
    for o in out["non_completed"]:
        lines.append(
            f"- `{o['seuid'][:8]}`  {o['course_name']}  status = "
            f"**{o['status']}**  agent_errors = `{o.get('agent_errors')}`"
        )

    return "\n".join(lines).rstrip() + "\n"


def _print_run_result(run: dict[str, Any]) -> None:
    style = "green" if run.get("status") == "completed" else "yellow"
    if run.get("status") in {"failed", "script_error"}:
        style = "red"
    console.print(
        f"[{style}]{run.get('status')}[/{style}] "
        f"{run.get('course_name') or run.get('seuid')} "
        f"CoreScore={_fmt_num(run.get('core_score'))} "
        f"coverage={_fmt_percent(run.get('coverage'))} "
        f"NA={run.get('n_na')}"
    )


def _print_summary_table(runs: list[dict[str, Any]]) -> None:
    table = Table(title="Phase 5.7 LM-18 validation summary", show_header=True)
    table.add_column("#")
    table.add_column("course")
    table.add_column("status")
    table.add_column("core")
    table.add_column("coverage")
    table.add_column("duration")
    for i, run in enumerate(runs, 1):
        table.add_row(
            str(i),
            str(run.get("course_name") or run.get("seuid"))[:40],
            str(run.get("status")),
            _fmt_num(run.get("core_score")),
            _fmt_percent(run.get("coverage")),
            _fmt_ms(run.get("duration_ms")),
        )
    console.print(table)


# === helpers ================================================================


def _ensure_local_schema() -> None:
    if engine.dialect.name == "sqlite":
        inspector = inspect(engine)
        if "evaluation_results" in inspector.get_table_names():
            columns = {
                c["name"] for c in inspector.get_columns("evaluation_results")
            }
            if "evaluation_uuid" not in columns:
                with engine.begin() as conn:
                    conn.execute(text("DROP TABLE evaluation_results"))
    Base.metadata.create_all(engine)


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
    return "".join(
        ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fmt_num(value: Any) -> str:
    return f"{value:.2f}" if isinstance(value, int | float) else "—"


def _fmt_percent(value: Any) -> str:
    return f"{value:.0%}" if isinstance(value, int | float) else "—"


def _fmt_ms(value: Any) -> str:
    return f"{value / 1000:.1f}s" if isinstance(value, int | float) else "—"


def _fmt_seconds(value: Any) -> str:
    if not isinstance(value, int | float):
        return "—"
    if value < 60:
        return f"{value:.0f}s"
    if value < 3600:
        return f"{value / 60:.1f}m"
    return f"{value / 3600:.2f}h"


def _fmt_score(value: Any) -> str:
    if value is None:
        return "NA"
    if isinstance(value, int | float):
        return str(int(value))
    return str(value)


if __name__ == "__main__":
    app()
