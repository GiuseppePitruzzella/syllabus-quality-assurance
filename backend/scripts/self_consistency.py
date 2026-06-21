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
