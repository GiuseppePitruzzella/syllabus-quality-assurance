"""Perturbation / sensitivity experiment runner.

Standalone. Generates 7 single-aspect perturbed variants of one base
syllabus, freezes them to variants/, then invokes the production graph
N times per condition (base + variants) WITHOUT persisting to the app DB
(only a read-only SELECT snapshots the base). Writes per-run dumps,
metrics, a manifest, and thesis-ready .md/.tex artifacts.

Usage:
    cd backend
    uv run python scripts/perturbation_sensitivity.py --dry-run   # no Vertex
    uv run python scripts/perturbation_sensitivity.py             # asks confirmation
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.config import settings  # noqa: E402
from app.evaluation.analysis.perturbation import (  # noqa: E402
    PERTURBATIONS,
    RunRecord,
    compute_perturbation_metrics,
    generate_variants,
)
from app.evaluation.analysis.perturbation_reporting import (  # noqa: E402
    render_perturbation_deltas_tex,
    render_protocol_md,
    render_side_effects_tex,
    render_summary_md,
)
from app.evaluation.service import DEFAULT_PROMPT_VERSIONS  # noqa: E402

GraphInvoker = Callable[[dict[str, Any]], dict[str, Any]]
_TERMINAL_STATUSES = {"completed", "partial", "failed"}
_DEFAULT_BASE_SEUID = "3540D939-DA16-4C1D-983C-E6B85C403F2F"  # 07_DEEP_LEARNING
_AVG_RUN_SECONDS = 90


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def execute_run(
    graph_invoker: GraphInvoker, condition: str, snapshot: dict[str, Any],
    course_name: str, run_index: int,
) -> dict[str, Any]:
    """Invoke the graph once; return structured fields only (no report text)."""
    initial_state = {
        "syllabus_seuid": condition,
        "course_name": course_name,
        "syllabus_snapshot": snapshot,
    }
    started = time.time()
    final = graph_invoker(initial_state)
    duration_ms = int((time.time() - started) * 1000)

    agg = final.get("aggregation")
    if agg is not None:
        criterion_scores = dict(agg.criterion_scores)
        status = agg.status
        core_score = agg.core_score
        coverage = agg.coverage
        na_criteria = [r.model_dump() for r in agg.na_criteria]
    else:
        criterion_scores, status, core_score = {}, final.get("status", "failed"), None
        coverage, na_criteria = 0.0, []

    return {
        "condition": condition, "run_index": run_index, "status": status,
        "criterion_scores": criterion_scores, "core_score": core_score,
        "coverage": coverage, "na_criteria": na_criteria,
        "agent_errors": dict(final.get("agent_errors") or {}),
        "duration_ms": duration_ms,
    }


def build_variants(
    base_snapshot: dict[str, Any], output_dir: Path,
) -> list[tuple[str, dict[str, Any]]]:
    """Freeze base + 7 variants to variants/, return [(condition_id, snapshot)]."""
    variants_dir = output_dir / "variants"
    variants_dir.mkdir(parents=True, exist_ok=True)
    conditions: list[tuple[str, dict[str, Any]]] = [("base", base_snapshot)]
    conditions.extend(generate_variants(base_snapshot).items())
    for cid, snap in conditions:
        _write_json(variants_dir / f"{cid}.json", snap)
    return conditions


def _dump_path(output_dir: Path, condition: str, run_index: int) -> Path:
    return output_dir / "runs" / f"{condition}__run{run_index}__evaluation.json"


def _resumable(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if payload.get("phase") != "perturbation_sensitivity":
        return None
    if payload.get("status") not in _TERMINAL_STATUSES:
        return None
    return payload


def run_campaign(
    *, conditions: list[tuple[str, dict[str, Any]]], runs: int, output_dir: Path,
    graph_invoker: GraphInvoker, course_name: str, resume: bool,
    console: Any | None = None,
) -> list[dict[str, Any]]:
    (output_dir / "runs").mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for condition, snapshot in conditions:
        for i in range(1, runs + 1):
            path = _dump_path(output_dir, condition, i)
            if resume and (resumed := _resumable(path)) is not None:
                records.append({k: v for k, v in resumed.items() if k != "phase"})
                if console:
                    console.print(f"[yellow]SKIP[/yellow] {condition} run {i}")
                continue
            record = execute_run(graph_invoker, condition, snapshot, course_name, i)
            _write_json(path, {"phase": "perturbation_sensitivity", **record})
            records.append(record)
            if console:
                console.print(
                    f"[green]OK[/green] {condition} run {i}: status={record['status']}"
                )
    return records


def _git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=_PROJECT_ROOT,
                            capture_output=True, text=True)
    return result.stdout.strip()


def _git_info() -> dict[str, Any]:
    return {
        "commit": _git(["rev-parse", "HEAD"]),
        "branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "dirty": bool(_git(["status", "--porcelain"])),
    }


def build_manifest(base_seuid: str, runs: int, output_dir: Path) -> dict[str, Any]:
    sci = settings.scientific
    return {
        "experiment": "perturbation_sensitivity_v1",
        "datetime": _now_iso(),
        "git": _git_info(),
        "base_seuid": base_seuid,
        "n_runs": runs,
        "variants": [p.meta() for p in PERTURBATIONS],
        "scientific_config": {
            "llm_model": sci.llm_model,
            "llm_temperature": sci.llm_temperature,
            "llm_max_output_tokens": sci.llm_max_output_tokens,
            "embedding_model": sci.embedding_model,
            "embedding_output_dimensionality": sci.embedding_output_dimensionality,
            "rag_top_k": sci.rag_top_k,
            "rag_final_k": sci.rag_final_k,
            "rag_similarity_threshold": sci.rag_similarity_threshold,
        },
        "prompt_versions": dict(DEFAULT_PROMPT_VERSIONS),
        "output_dir": str(output_dir),
    }


def _records_for(records: list[dict[str, Any]], condition: str) -> list[RunRecord]:
    return [
        RunRecord(
            seuid=r["condition"], run_index=r["run_index"], status=r["status"],
            criterion_scores=r["criterion_scores"], core_score=r["core_score"],
            coverage=r["coverage"], agent_errors=r.get("agent_errors") or {},
        )
        for r in records if r["condition"] == condition
    ]


def write_outputs(
    output_dir: Path, records: list[dict[str, Any]], manifest: dict[str, Any],
) -> None:
    base_records = _records_for(records, "base")
    variant_records = {p.id: _records_for(records, p.id) for p in PERTURBATIONS}
    metrics = compute_perturbation_metrics(
        base_records, variant_records, PERTURBATIONS,
        base_seuid=manifest["base_seuid"], n_runs=manifest["n_runs"],
    )

    _write_json(output_dir / "metrics.json", metrics.model_dump())
    _write_json(output_dir / "manifest.json", manifest)
    (output_dir / "protocol.md").write_text(
        render_protocol_md(manifest, metrics, PERTURBATIONS), encoding="utf-8")
    (output_dir / "summary.md").write_text(
        render_summary_md(metrics), encoding="utf-8")
    tables = output_dir / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    (tables / "tbl_perturbation_deltas.tex").write_text(
        render_perturbation_deltas_tex(metrics), encoding="utf-8")
    (tables / "tbl_side_effects.tex").write_text(
        render_side_effects_tex(metrics), encoding="utf-8")


def format_plan(
    base_seuid: str, course_name: str, runs: int,
    conditions: list[tuple[str, dict[str, Any]]],
) -> str:
    total = len(conditions) * runs
    est_min = round(total * _AVG_RUN_SECONDS / 60, 1)
    by_id = {p.id: p for p in PERTURBATIONS}
    lines = [
        "Piano esecuzione perturbation/sensitivity:",
        f"  base       : {base_seuid}  ({course_name})",
        f"  condizioni : {len(conditions)} (1 base + {len(conditions) - 1} varianti)",
        f"  run/cond.  : {runs}   run totali: {total}",
        f"  stima      : ~{est_min} min (a ~{_AVG_RUN_SECONDS}s/run, Vertex reale)",
        "  attese per variante:",
    ]
    for cid, _ in conditions:
        if cid == "base":
            continue
        p = by_id[cid]
        lines.append(
            f"    - {cid}: bersaglio {','.join(p.target_criteria)} ↓ "
            f"(coupling: {','.join(p.plausible_coupling) or '—'})"
        )
    return "\n".join(lines)


def _load_base_snapshot(seuid: str) -> tuple[dict[str, Any], str]:
    from app.database import SessionLocal
    from app.evaluation.state import snapshot_syllabus
    from app.models.syllabus import Syllabus

    with SessionLocal() as session:
        row = session.query(Syllabus).filter(Syllabus.seuid == seuid).first()
        if row is None:
            raise ValueError(f"base seuid not found in DB: {seuid!r}")
        return snapshot_syllabus(row), row.course_name


def _build_production_graph_invoker() -> GraphInvoker:
    import chromadb

    from app.evaluation.agents.llm_client import VertexAILLMClient
    from app.evaluation.orchestrator import build_graph
    from app.evaluation.rag.embeddings import VertexAIEmbeddings
    from app.evaluation.rag.retriever import NormativeRetriever

    project_id, location = settings.require_vertex_ai_config()
    sci = settings.scientific
    chroma = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    embeddings = VertexAIEmbeddings(
        project_id=project_id, location=location, model_name=sci.embedding_model,
        output_dimensionality=sci.embedding_output_dimensionality,
    )
    retriever = NormativeRetriever(chroma, embeddings, sci)
    llm_client = VertexAILLMClient(project_id=project_id, location=location, scientific=sci)
    graph = build_graph(retriever=retriever, llm_client=llm_client)
    return lambda initial_state: graph.invoke(initial_state)


def main() -> None:
    import typer
    from rich.console import Console
    from rich.prompt import Confirm

    console = Console()

    def _command(
        base_seuid: str = typer.Option(_DEFAULT_BASE_SEUID, "--base-seuid"),
        runs: int = typer.Option(3, "--runs"),
        output_dir: Path = typer.Option(
            _PROJECT_ROOT / "data" / "calibration" / "perturbation_sensitivity_v1",
            "--output-dir",
        ),
        resume: bool = typer.Option(True, "--resume/--no-resume"),
        dry_run: bool = typer.Option(False, "--dry-run"),
        yes: bool = typer.Option(False, "--yes"),
    ) -> None:
        base_snapshot, course_name = _load_base_snapshot(base_seuid)
        conditions = build_variants(base_snapshot, output_dir)
        console.print(format_plan(base_seuid, course_name, runs, conditions))

        if dry_run:
            raise typer.Exit(0)
        if not yes and not Confirm.ask("Procedo con le chiamate Vertex reali?"):
            console.print("[yellow]Annullato.[/yellow]")
            raise typer.Exit(1)

        invoker = _build_production_graph_invoker()
        records = run_campaign(
            conditions=conditions, runs=runs, output_dir=output_dir,
            graph_invoker=invoker, course_name=course_name, resume=resume,
            console=console,
        )
        manifest = build_manifest(base_seuid, runs, output_dir)
        write_outputs(output_dir, records, manifest)
        console.print(f"\n[green]Artifacts written to[/green] {output_dir}")

    typer.run(_command)


if __name__ == "__main__":
    main()
