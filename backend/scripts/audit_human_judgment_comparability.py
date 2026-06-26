"""Write the Phase 5.8 criterion-comparability audit."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import typer

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.evaluation.analysis.human_comparability import (  # noqa: E402
    audit_payload,
    render_audit_markdown,
)


app = typer.Typer(help=__doc__, no_args_is_help=False)


@app.command()
def main(
    output_dir: Path = typer.Option(
        _BACKEND_DIR.parent / "data" / "human_judgment" / "analysis",
        file_okay=False,
    ),
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = audit_payload()
    (output_dir / "comparability_audit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "comparability_audit.md").write_text(
        render_audit_markdown(),
        encoding="utf-8",
    )
    typer.echo(
        "Comparability audit written: "
        f"primary={payload['primary_criteria']}, "
        f"secondary={payload['secondary_criteria']}, "
        f"excluded={payload['excluded_criteria']}"
    )


if __name__ == "__main__":
    app()
