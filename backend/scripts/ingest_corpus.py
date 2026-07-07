"""CLI entry point for ingesting the normative corpus into ChromaDB.

Usage:

    # Preview only — no ChromaDB writes, no Vertex AI calls.
    uv run python scripts/ingest_corpus.py --preview

    # Real ingestion (idempotent: skips chunks already present).
    uv run python scripts/ingest_corpus.py

    # Force re-ingestion (re-embeds and upserts every chunk).
    uv run python scripts/ingest_corpus.py --force

The preview mode generates ``data/chunks_preview.json`` containing every
chunk with full metadata, so the tagging can be inspected manually
before paying for embedding API calls.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running this script directly: `uv run python scripts/ingest_corpus.py`.
# We add the backend root to sys.path so `app.*` imports resolve.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import structlog  # noqa: E402
import typer  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from app.backends import build_embeddings_client  # noqa: E402
from app.config import settings  # noqa: E402
from app.evaluation.rag.ingester import CorpusIngester, IngestionReport  # noqa: E402
from app.evaluation.rag.tagging_rules import TaggingRules  # noqa: E402

logger = structlog.get_logger(__name__)
console = Console()
app = typer.Typer(help=__doc__, no_args_is_help=False)


@app.command()
def main(
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Write chunks_preview.json without ingesting or calling Vertex AI.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-embed and upsert every chunk, ignoring existing entries.",
    ),
    preview_path: Path = typer.Option(
        Path(settings.normative_corpus_dir).parent / "chunks_preview.json",
        "--preview-path",
        help="Output path for the preview JSON.",
    ),
) -> None:
    rules = TaggingRules.from_yaml(Path(settings.tagging_rules_file))

    if preview:
        _run_preview(rules, preview_path)
        return

    # Real ingestion: requires Vertex AI or Gemini Developer API configuration,
    # depending on settings.genai_use_vertex.
    embeddings = build_embeddings_client(settings)
    ingester = CorpusIngester(
        corpus_dir=Path(settings.normative_corpus_dir),
        chroma_persist_dir=Path(settings.chroma_persist_dir),
        rules=rules,
        embeddings=embeddings,
    )

    console.print(
        f"[bold]Ingesting[/bold] from [cyan]{settings.normative_corpus_dir}[/cyan] "
        f"into [cyan]{settings.chroma_persist_dir}[/cyan] "
        f"(force_reingest={force})"
    )
    report = ingester.ingest_all(force_reingest=force)
    _print_report(report)
    if report.errors:
        raise typer.Exit(code=1)


def _run_preview(rules: TaggingRules, preview_path: Path) -> None:
    """Generate chunks_preview.json without embedding or storing."""

    # Construct a dummy ingester whose ``embeddings`` is never invoked
    # because we only call ``produce_chunks``.
    class _NoEmbeddings:
        def embed_documents(self, _texts):  # pragma: no cover — unreachable in preview
            raise AssertionError("embed_documents must not be called in preview mode")

        def embed_query(self, _text):  # pragma: no cover — unreachable in preview
            raise AssertionError("embed_query must not be called in preview mode")

    ingester = CorpusIngester(
        corpus_dir=Path(settings.normative_corpus_dir),
        chroma_persist_dir=Path(settings.chroma_persist_dir),
        rules=rules,
        embeddings=_NoEmbeddings(),  # type: ignore[arg-type]
    )
    chunks = ingester.produce_chunks()

    payload = {
        "total_chunks": len(chunks),
        "chunks": [
            {
                "chunk_id": c.chunk_id,
                "text": c.text,
                "metadata": c.metadata,
            }
            for c in chunks
        ],
    }
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    console.print(
        f"[bold green]Wrote {len(chunks)} chunks[/bold green] to [cyan]{preview_path}[/cyan]"
    )
    _print_preview_summary(chunks)


def _print_preview_summary(chunks):
    """Render distribution tables for the preview run."""
    from app.evaluation.rag.tagging_rules import ALL_AGENTS, ALL_CRITERIA

    table = Table(title="Chunks per document", show_header=True)
    table.add_column("Document")
    table.add_column("N chunks", justify="right")
    table.add_column("Min chars", justify="right")
    table.add_column("Max chars", justify="right")
    by_doc: dict[str, list[int]] = {}
    for c in chunks:
        by_doc.setdefault(c.metadata["document_id"], []).append(c.metadata["char_count"])
    for doc, lens in sorted(by_doc.items()):
        table.add_row(doc, str(len(lens)), str(min(lens)), str(max(lens)))
    console.print(table)

    crit_table = Table(title="Chunks per criterion / agent", show_header=True)
    crit_table.add_column("Code")
    crit_table.add_column("N chunks", justify="right")
    for code in sorted(ALL_CRITERIA) + sorted(ALL_AGENTS):
        n = sum(1 for c in chunks if c.metadata.get(f"tag_{code}"))
        crit_table.add_row(code, str(n))
    console.print(crit_table)


def _print_report(report: IngestionReport) -> None:
    table = Table(title="Ingestion summary", show_header=False)
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Total chunks", str(report.total_chunks))
    table.add_row("Ingested", str(report.ingested_chunks))
    table.add_row("Skipped (already present)", str(report.skipped_chunks))
    table.add_row("Untagged", str(report.untagged_chunks))
    table.add_row("Errors", str(len(report.errors)))
    console.print(table)

    if report.errors:
        console.print("[bold red]Errors:[/bold red]")
        for err in report.errors:
            console.print(f"  - {err}")


if __name__ == "__main__":
    app()
