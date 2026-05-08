"""Calibrate the A3 DidacticConsistencyAgent on the same set of LM-18 syllabi.

Mirrors scripts/calibrate_a1.py and scripts/calibrate_a2.py end to end —
same five seuids, same ChromaDB collection, same Vertex AI configuration,
same audit format. The only differences: it instantiates
``DidacticConsistencyAgent`` (C6, C7, C8) and writes per-syllabus fixtures
named ``a3_calibration_<seuid>.json``.

For each ``seuid`` the script:

1. Loads the Syllabus from the local SQLite DB.
2. Runs ``DidacticConsistencyAgent.evaluate(syllabus)`` end-to-end against
   real Vertex AI (gemini-2.5-flash) and the ingested normative corpus.
3. Saves an audit fixture under ``tests/fixtures/llm_responses/``
   containing the prompt, the raw LLM response, its metadata, and the
   parsed AgentOutput (or a structured error block on failure).

When A4 lands we will fold the four calibration scripts into a single
parametric ``calibrate_agent.py``; for now the duplication is
intentional and keeps each Phase 5.x committed separately.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

# Allow running this script directly from anywhere.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import chromadb  # noqa: E402
import structlog  # noqa: E402
import typer  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.evaluation.agents.a3_coherence import DidacticConsistencyAgent  # noqa: E402
from app.evaluation.agents.llm_client import (  # noqa: E402
    LLMResult,
    VertexAILLMClient,
)
from app.evaluation.rag.embeddings import VertexAIEmbeddings  # noqa: E402
from app.evaluation.rag.retriever import NormativeRetriever  # noqa: E402
from app.models import Syllabus  # noqa: E402

logger = structlog.get_logger(__name__)
console = Console()
app = typer.Typer(help=__doc__, no_args_is_help=False)


# Calibration set agreed with Giuseppe — five LM-18 syllabi covering
# the qualitative spectrum: well-compiled / mediocre / poor / fully
# bilingual / mostly Italian-only.
DEFAULT_SEUIDS: list[str] = [
    "3540D939-DA16-4C1D-983C-E6B85C403F2F",
    "E2446DF6-59A1-46FD-B8D8-635EB937C1B3",
    "F4AF1512-9D7A-4256-B57D-E103E05B009B",
    "FE97232C-4F07-41F8-A82F-FF73592265EC",
    "0B53E8E2-4B90-426F-A25C-3AA31FA4B649",
]


class CapturingLLMClient:
    """Wraps a VertexAILLMClient to capture every call for audit.

    BaseAgent's retry loop calls the client up to 3 times when the JSON
    output fails to validate, so we keep ALL prompt/result pairs across
    retries.

    Each call is appended to ``self.calls`` BEFORE invoking the inner
    client, so the prompt is always recorded. The ``result`` field is
    filled on success; on failure the caught exception is recorded as
    ``error`` and re-raised. Without this, an exception inside the inner
    client (typed errors like LLMResponseTruncatedError, transient
    failures, etc.) leaves the calibration fixture with zero call
    records and we lose the prompt that triggered the failure.
    """

    def __init__(self, inner: VertexAILLMClient) -> None:
        self._inner = inner
        self.calls: list[dict[str, Any]] = []

    def __call__(self, prompt: str, *, seed: int | None = None) -> LLMResult:
        record: dict[str, Any] = {"prompt": prompt, "result": None, "error": None}
        self.calls.append(record)
        try:
            result = self._inner(prompt, seed=seed)
            record["result"] = result
            return result
        except Exception as exc:
            record["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
            raise


_REDACTED_PROJECT_ID = "<redacted-gcp-project-id>"


def _redact_gcp_project_id(obj: Any, project_id: str) -> None:
    """In-place redaction of ``gcp_project_id`` everywhere in ``obj``.

    The fixtures end up committed to git as calibration artifacts; a
    real GCP project ID is not a credential but is private metadata
    we don't want in the public repository. The actual project ID
    used for the run still lives in backend/.env, in structlog
    output, and in the EvaluationResult records — i.e. wherever
    full reproducibility is needed.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "gcp_project_id" and v == project_id:
                obj[k] = _REDACTED_PROJECT_ID
            else:
                _redact_gcp_project_id(v, project_id)
    elif isinstance(obj, list):
        for item in obj:
            _redact_gcp_project_id(item, project_id)


@app.command()
def main(
    output_dir: Path = typer.Option(
        _BACKEND_DIR / "tests" / "fixtures" / "llm_responses",
        "--output-dir",
        help="Where to write the per-syllabus calibration fixtures.",
    ),
    seuids: list[str] = typer.Option(
        None,
        "--seuid",
        help="Override the default 5-syllabus calibration set.",
    ),
    redact_project_id: bool = typer.Option(
        True,
        "--redact-project-id/--keep-project-id",
        help="Redact gcp_project_id in saved fixtures (default: True).",
    ),
) -> None:
    seuids_to_run = seuids or DEFAULT_SEUIDS
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

    output_dir.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()

    summary_rows: list[tuple[str, str, str, str, str]] = []
    for seuid in seuids_to_run:
        syllabus = db.query(Syllabus).filter_by(seuid=seuid).one_or_none()
        if syllabus is None:
            console.print(f"[yellow]SKIP[/yellow] {seuid}: not found in DB")
            summary_rows.append((seuid, "?", "MISSING", "-", "-"))
            continue

        console.print(
            f"[bold]Evaluating[/bold] {syllabus.course_name[:50]!r}  ({seuid})"
        )
        # Each syllabus gets a fresh capturing client so retries don't bleed.
        inner = VertexAILLMClient(
            project_id=project_id, location=location, scientific=sci
        )
        capturing = CapturingLLMClient(inner)
        agent = DidacticConsistencyAgent(retriever=retriever, llm_client=capturing)

        started = time.time()
        try:
            agent_output = agent.evaluate(syllabus)
            error_block: dict[str, Any] | None = None
            scores = ", ".join(
                f"{j.criterion_code}={j.score if j.score is not None else 'NA'}"
                for j in agent_output.judgments
            )
            status = "ok"
        except Exception as exc:  # noqa: BLE001 — we want every failure mode
            agent_output = None
            error_block = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
            scores = "—"
            status = f"error ({type(exc).__name__})"
            console.print(f"[red]error[/red]: {exc}")
        elapsed = time.time() - started

        payload = {
            "seuid": seuid,
            "course_name": syllabus.course_name,
            "has_english": syllabus.has_english,
            "agent_code": "A3",
            "criteria_codes": ["C6", "C7", "C8"],
            "elapsed_seconds": round(elapsed, 2),
            "llm_calls": [
                {
                    "prompt": call["prompt"],
                    "raw_response_text": call["result"].text if call["result"] else None,
                    "metadata": call["result"].metadata if call["result"] else None,
                    "error": call["error"],
                }
                for call in capturing.calls
            ],
            "agent_output": agent_output.model_dump() if agent_output else None,
            "error": error_block,
        }

        if redact_project_id:
            _redact_gcp_project_id(payload, project_id)

        out_path = output_dir / f"a3_calibration_{seuid}.json"
        out_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        console.print(f"  saved -> {out_path}  ({elapsed:.1f}s, scores: {scores})")
        summary_rows.append(
            (seuid[:8] + "…", syllabus.course_name[:32], status, scores, f"{elapsed:.1f}s")
        )

    _print_summary(summary_rows)


def _print_summary(rows: list[tuple[str, str, str, str, str]]) -> None:
    table = Table(title="A3 calibration summary", show_header=True)
    table.add_column("seuid (head)")
    table.add_column("course")
    table.add_column("status")
    table.add_column("scores")
    table.add_column("elapsed")
    for row in rows:
        table.add_row(*row)
    console.print(table)


if __name__ == "__main__":
    app()
