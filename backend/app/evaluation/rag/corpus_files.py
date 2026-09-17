"""Shared source inventory: repository instructions are not normative texts."""
from pathlib import Path


def corpus_markdown_files(directory: Path) -> list[Path]:
    return [p for p in sorted(directory.glob("*.md"))
            if p.is_file() and p.name.lower() != "readme.md"]
