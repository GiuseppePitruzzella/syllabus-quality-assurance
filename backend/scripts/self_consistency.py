"""Self-consistency (test-retest) experiment runner.

Standalone. Invokes the production evaluation graph N times per syllabus
WITHOUT persisting to the application DB (the only DB access is a
read-only SELECT to snapshot the syllabus). Writes raw per-run dumps,
consolidated metrics, a manifest, and thesis-ready .md/.tex artifacts.

Usage (official campaign — 8 human-validation syllabi, N=5):

    cd backend
    uv run python scripts/self_consistency.py            # asks confirmation
    uv run python scripts/self_consistency.py --dry-run  # plan only, no Vertex
    uv run python scripts/self_consistency.py --seuid <SEUID> --runs 3
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# Allow running this script directly from anywhere.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.config import settings  # noqa: E402
from app.evaluation.service import DEFAULT_PROMPT_VERSIONS  # noqa: E402

GraphInvoker = Callable[[dict[str, Any]], dict[str, Any]]

_TERMINAL_STATUSES = {"completed", "partial", "failed"}


def _safe_name(seuid: str) -> str:
    return seuid.replace("/", "_").replace("\\", "_")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def execute_run(
    graph_invoker: GraphInvoker,
    seuid: str,
    snapshot: dict[str, Any],
    course_name: str,
    run_index: int,
) -> dict[str, Any]:
    """Invoke the graph once and extract the structured run record.

    Only structured fields are returned; the report text is intentionally
    dropped (metrics never use it).
    """
    initial_state = {
        "syllabus_seuid": seuid,
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
    else:  # defensive: aggregate node always runs, but never crash here
        criterion_scores = {}
        status = final.get("status", "failed")
        core_score = None
        coverage = 0.0
        na_criteria = []

    return {
        "seuid": seuid,
        "run_index": run_index,
        "status": status,
        "criterion_scores": criterion_scores,
        "core_score": core_score,
        "coverage": coverage,
        "na_criteria": na_criteria,
        "agent_errors": dict(final.get("agent_errors") or {}),
        "duration_ms": duration_ms,
    }


def _dump_path(output_dir: Path, seuid: str, run_index: int) -> Path:
    return output_dir / f"{_safe_name(seuid)}__run{run_index}__evaluation.json"


def _resumable_record(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if payload.get("phase") != "self_consistency":
        return None
    if payload.get("status") not in _TERMINAL_STATUSES:
        return None
    return payload


def run_campaign(
    *,
    seuids_with_slug: list[tuple[str, str]],
    runs: int,
    output_dir: Path,
    graph_invoker: GraphInvoker,
    syllabus_rows: dict[str, tuple[dict[str, Any], str]],
    resume: bool,
    console: Any | None = None,
) -> list[dict[str, Any]]:
    """Run N evaluations per syllabus, writing one dump per run."""
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for seuid, slug in seuids_with_slug:
        snapshot, course_name = syllabus_rows[seuid]
        for i in range(1, runs + 1):
            path = _dump_path(output_dir, seuid, i)
            if resume:
                resumed = _resumable_record(path)
                if resumed is not None:
                    records.append({k: v for k, v in resumed.items()
                                    if k not in {"phase", "slug", "captured_at"}})
                    if console:
                        console.print(f"[yellow]SKIP[/yellow] {slug} run {i}")
                    continue
            record = execute_run(graph_invoker, seuid, snapshot, course_name, i)
            _write_json(path, {"phase": "self_consistency", "slug": slug, **record})
            records.append(record)
            if console:
                console.print(
                    f"[green]OK[/green] {slug} run {i}: status={record['status']} "
                    f"core={record['core_score']}"
                )
    return records


def _git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args], cwd=_PROJECT_ROOT, capture_output=True, text=True
    )
    return result.stdout.strip()


def _git_info() -> dict[str, Any]:
    return {
        "commit": _git(["rev-parse", "HEAD"]),
        "branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "dirty": bool(_git(["status", "--porcelain"])),
    }


def build_manifest(
    seuids_with_slug: list[tuple[str, str]], runs: int, output_dir: Path
) -> dict[str, Any]:
    sci = settings.scientific
    return {
        "experiment": "self_consistency_v1",
        "datetime": _now_iso(),
        "git": _git_info(),
        "n_runs_per_seuid": runs,
        "sample": [{"seuid": s, "slug": sl} for s, sl in seuids_with_slug],
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


from app.evaluation.analysis.human_sample import OFFICIAL_HUMAN_SAMPLE  # noqa: E402
from app.evaluation.analysis.reporting import (  # noqa: E402
    render_corescore_stability_tex,
    render_criterion_stability_tex,
    render_protocol_md,
    render_run_status_tex,
    render_summary_md,
)
from app.evaluation.analysis.self_consistency import (  # noqa: E402
    CRITERIA_ORDER,
    RunRecord,
    compute_self_consistency,
)

_AVG_RUN_SECONDS = 90  # for the dry-run wall-clock estimate only


def resolve_sample(seuids: list[str] | None) -> list[tuple[str, str]]:
    """Return [(seuid, slug)]; default = the official 8-syllabus sample.

    Manual --seuid overrides the default. Known seuids keep their slug;
    unknown ones get the "CUSTOM" label.
    """
    if not seuids:
        return list(OFFICIAL_HUMAN_SAMPLE)
    known = dict(OFFICIAL_HUMAN_SAMPLE)
    return [(s, known.get(s, "CUSTOM")) for s in seuids]


def _build_runs_matrix(
    records: list[dict[str, Any]], seuids_with_slug: list[tuple[str, str]]
) -> dict[str, Any]:
    matrix: dict[str, Any] = {"_slugs": dict(seuids_with_slug)}
    for seuid, _ in seuids_with_slug:
        runs = sorted(
            (r for r in records if r["seuid"] == seuid), key=lambda r: r["run_index"]
        )
        matrix[seuid] = {
            crit: [r["criterion_scores"].get(crit) for r in runs]
            for crit in CRITERIA_ORDER
        }
    return matrix


def write_outputs(
    output_dir: Path,
    records: list[dict[str, Any]],
    seuids_with_slug: list[tuple[str, str]],
    manifest: dict[str, Any],
) -> None:
    """Compute metrics and write every artifact to ``output_dir``."""
    slug_map = dict(seuids_with_slug)
    metrics = compute_self_consistency([
        RunRecord(
            seuid=r["seuid"], run_index=r["run_index"], status=r["status"],
            criterion_scores=r["criterion_scores"], core_score=r["core_score"],
            coverage=r["coverage"], agent_errors=r.get("agent_errors") or {},
        )
        for r in records
    ])

    _write_json(output_dir / "metrics.json", metrics.model_dump())
    _write_json(output_dir / "runs_matrix.json",
                _build_runs_matrix(records, seuids_with_slug))
    _write_json(output_dir / "manifest.json", manifest)
    (output_dir / "protocol.md").write_text(
        render_protocol_md(manifest, metrics, slug_map), encoding="utf-8"
    )
    (output_dir / "summary.md").write_text(
        render_summary_md(metrics, slug_map), encoding="utf-8"
    )
    tables = output_dir / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    (tables / "tbl_criterion_stability.tex").write_text(
        render_criterion_stability_tex(metrics), encoding="utf-8"
    )
    (tables / "tbl_corescore_stability.tex").write_text(
        render_corescore_stability_tex(metrics, slug_map), encoding="utf-8"
    )
    (tables / "tbl_run_status.tex").write_text(
        render_run_status_tex(metrics), encoding="utf-8"
    )


def _load_syllabus_rows(
    seuids: list[str],
) -> dict[str, tuple[dict[str, Any], str]]:
    """Read-only snapshot of each syllabus. Raises if any seuid is absent."""
    from app.database import SessionLocal
    from app.evaluation.state import snapshot_syllabus
    from app.models.syllabus import Syllabus

    out: dict[str, tuple[dict[str, Any], str]] = {}
    with SessionLocal() as session:
        for seuid in seuids:
            row = session.query(Syllabus).filter(Syllabus.seuid == seuid).first()
            if row is None:
                raise ValueError(f"seuid not found in DB: {seuid!r}")
            out[seuid] = (snapshot_syllabus(row), row.course_name)
    return out


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
    llm_client = VertexAILLMClient(
        project_id=project_id, location=location, scientific=sci
    )
    graph = build_graph(retriever=retriever, llm_client=llm_client)  # A5 off

    def _invoke(initial_state: dict[str, Any]) -> dict[str, Any]:
        return graph.invoke(initial_state)

    return _invoke


def _format_plan(
    sample: list[tuple[str, str]],
    runs: int,
    output_dir: Path,
    rows: dict[str, tuple[dict[str, Any], str]],
) -> str:
    total = len(sample) * runs
    est_min = round(total * _AVG_RUN_SECONDS / 60, 1)
    lines = [
        "Piano esecuzione self-consistency:",
        f"  output dir : {output_dir}",
        f"  syllabi    : {len(sample)}   run/syllabus: {runs}   "
        f"run totali: {total}",
        f"  stima      : ~{est_min} min (a ~{_AVG_RUN_SECONDS}s/run, Vertex reale)",
        "  campione   :",
    ]
    for seuid, slug in sample:
        _, course_name = rows[seuid]
        lines.append(f"    - {slug}  [{seuid[:8]}]  {course_name}")
    return "\n".join(lines)


def main() -> None:
    import typer
    from rich.console import Console
    from rich.prompt import Confirm

    console = Console()

    def _command(
        seuid: list[str] = typer.Option(
            None, "--seuid",
            help="Override manuale del campione (ripetibile). "
                 "Default = campione umano ufficiale (8 syllabi).",
        ),
        runs: int = typer.Option(5, "--runs", help="Ripetizioni per syllabus."),
        output_dir: Path = typer.Option(
            _PROJECT_ROOT / "data" / "calibration" / "self_consistency_v1",
            "--output-dir",
        ),
        resume: bool = typer.Option(True, "--resume/--no-resume"),
        dry_run: bool = typer.Option(
            False, "--dry-run", help="Stampa il piano ed esce (nessuna chiamata Vertex)."
        ),
        yes: bool = typer.Option(False, "--yes", help="Salta la conferma interattiva."),
    ) -> None:
        sample = resolve_sample(seuid)
        rows = _load_syllabus_rows([s for s, _ in sample])  # read-only preflight
        console.print(_format_plan(sample, runs, output_dir, rows))

        if dry_run:
            raise typer.Exit(0)
        if not yes and not Confirm.ask("Procedo con le chiamate Vertex reali?"):
            console.print("[yellow]Annullato.[/yellow]")
            raise typer.Exit(1)

        invoker = _build_production_graph_invoker()
        records = run_campaign(
            seuids_with_slug=sample, runs=runs, output_dir=output_dir,
            graph_invoker=invoker, syllabus_rows=rows, resume=resume, console=console,
        )
        manifest = build_manifest(sample, runs, output_dir)
        write_outputs(output_dir, records, sample, manifest)
        console.print(f"\n[green]Artifacts written to[/green] {output_dir}")

    typer.run(_command)


if __name__ == "__main__":
    main()
