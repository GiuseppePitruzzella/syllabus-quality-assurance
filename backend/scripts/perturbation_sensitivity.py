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
import sys
import time
from pathlib import Path
from typing import Any, Callable

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.evaluation.analysis.perturbation import generate_variants  # noqa: E402

GraphInvoker = Callable[[dict[str, Any]], dict[str, Any]]
_TERMINAL_STATUSES = {"completed", "partial", "failed"}


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
