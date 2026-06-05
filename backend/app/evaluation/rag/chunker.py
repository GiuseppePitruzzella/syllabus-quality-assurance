"""Markdown chunker for the normative corpus.

Splits a Markdown document into per-section chunks using ``##`` and ``###``
as section boundaries. ``#`` (H1) is treated as the document title and
ignored as a delimiter; ``####`` and lower are treated as content.

Section references are extracted from heading text via a sequence of
regex patterns, supporting numeric (``3.1``), dotted-alphanumeric
(``D.CDS.1.4.1``), article (``Art. 1``), quadro (``Quadro A``),
allegato (``Allegato A``), parte (``Parte I``) and a slug fallback for
non-numbered headings.

Long chunks (>1500 characters) are split at paragraph boundaries with
suffixes ``.a``, ``.b``, ``.c`` ... in the section reference.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# Phase 8.B.2: the generic paragraph/line/sentence/hard-cut cascade
# moved into `app.text_splitting` so the new
# `ExternalDocumentChunker` can share it byte-for-byte. The corpus
# Markdown chunker keeps its own H2/H3 boundary detection, section
# refs and sub-suffixes; only the size-based splitting is shared.
from app.text_splitting import (
    DEFAULT_HARD_MAX_CHARS,
    DEFAULT_MAX_CHARS,
    merge_noise_subchunks as _merge_noise_subchunks,
    pack_greedy as _greedy_pack,  # noqa: F401 — re-export for tests/rag/test_chunker.py
    split_long as _split_long,
)

__all__ = [
    "Chunk",
    "MarkdownChunker",
    "DEFAULT_MAX_CHARS",
    "DEFAULT_HARD_MAX_CHARS",
    "extract_section_ref",
]

# A sub-chunk with fewer than this many alphanumeric characters is treated
# as noise (table separators, isolated punctuation, single-word fragments
# like "DECRETA") and merged with the adjacent sub-chunk. Only applies
# *within* a section split: legitimate short sections that fit in a
# single chunk are kept as-is.
_MIN_SUB_CHUNK_ALNUM = 30

# Patterns are tried in order. The first match wins. Each pattern must
# capture (1) the section reference token and (2) the rest of the title.
_SECTION_REF_PATTERNS: list[re.Pattern[str]] = [
    # Dotted alphanumeric (D.CDS.1.4.1) — must come before pure numeric
    re.compile(r"^([A-Z]+(?:\.[A-Z]+)*(?:\.\d+)+)\s*[-–:.]?\s*(.*)$"),
    # Article: Art. 1, Art. 12, Art. 1-bis
    re.compile(r"^(Art\.\s*\d+(?:[-\s][a-z]+)?)\s*[-–:.]?\s*\(?(.*?)\)?$", re.IGNORECASE),
    # Quadro: Quadro A, Quadro B.1
    re.compile(r"^(Quadro\s+[A-Z0-9.]+)\s*[-–:.]?\s*(.*)$"),
    # Allegato: Allegato A, Allegato 1
    re.compile(r"^(Allegato\s+[A-Z0-9]+)\s*[-–:.]?\s*(.*)$", re.IGNORECASE),
    # Parte: Parte I, Parte II
    re.compile(r"^(Parte\s+[IVXLCDM]+)\s*[-–:.]?\s*(.*)$"),
    # Numbered: 1, 1.1, 1.1.1
    re.compile(r"^(\d+(?:\.\d+)*)\s*[-–:.]?\s*(.*)$"),
]


class Chunk(BaseModel):
    """A retrievable normative chunk.

    Attributes:
        chunk_id: Deterministic identifier ``{document_id}__{section_ref}__{sub_index}``.
        text: Raw Markdown text of the chunk (without the heading line itself).
        metadata: Chunk metadata. See Appendix A of the Phase 5 spec for the
            full schema. Tags ``tag_C*`` / ``tag_E*`` / ``tag_A*`` are added
            later by the tagging rules layer; the chunker only fills the
            structural and provenance fields.
    """

    chunk_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    metadata: dict[str, Any]


def extract_section_ref(title: str) -> tuple[str, str]:
    """Extract a stable section reference and the cleaned title.

    Returns:
        ``(section_ref, clean_title)``. If no pattern matches, the section
        reference is a slug derived from the first words of the title and
        the clean title is the original heading text.
    """
    title = title.strip()
    for pattern in _SECTION_REF_PATTERNS:
        match = pattern.match(title)
        if match and match.group(1):
            ref = match.group(1).strip().rstrip(".")
            rest = (match.group(2) or "").strip().strip("-–:.()")
            return ref, rest if rest else title
    # Fallback: slug from first 4 words, lowercase, ASCII-safe.
    # Strip trailing/leading underscores that arise when the heading
    # contains trailing punctuation (e.g. "Indice -") to keep the slug
    # stable under cosmetic title changes.
    words = title.split()[:4]
    slug = "_".join(words).lower()
    slug = re.sub(r"[^a-z0-9_]", "", slug).strip("_")[:50] or "section"
    return slug, title


def _suffix_for(index: int) -> str:
    """Return ``a`` for 0, ``b`` for 1, ..., ``aa`` for 26, etc."""
    if index < 0:
        raise ValueError("index must be non-negative")
    chars: list[str] = []
    while True:
        chars.append(chr(ord("a") + (index % 26)))
        index = index // 26 - 1
        if index < 0:
            break
    return "".join(reversed(chars))


class MarkdownChunker:
    """Parse a Markdown file into per-section ``Chunk`` objects.

    The chunker walks the file line-by-line, tracking the currently open
    H2 (and optionally nested H3). Each H2/H3 starts a new chunk; lines
    until the next H2/H3 form the chunk body. H1 lines are recorded as
    the inferred document title but never produce a chunk (the document
    title can also be supplied via ``document_metadata``).
    """

    def __init__(
        self,
        max_chars: int = DEFAULT_MAX_CHARS,
        hard_max_chars: int = DEFAULT_HARD_MAX_CHARS,
    ) -> None:
        if hard_max_chars < max_chars:
            raise ValueError("hard_max_chars must be >= max_chars")
        self.max_chars = max_chars
        self.hard_max_chars = hard_max_chars

    def chunk_document(
        self, file_path: Path, document_metadata: dict[str, Any]
    ) -> list[Chunk]:
        """Chunk a Markdown file.

        Args:
            file_path: Path to a UTF-8 Markdown file.
            document_metadata: Per-document metadata. Must contain at
                least ``document_id``. Other fields recommended:
                ``document_title``, ``document_version``, ``source_type``,
                ``document_priority``, ``language``. These are merged into
                each chunk's metadata.

        Returns:
            List of ``Chunk`` objects in document order. Empty sections
            (an H2 followed immediately by an H3 with no body in between)
            are skipped.

        Raises:
            ValueError: if ``document_metadata['document_id']`` is missing.
            FileNotFoundError: if ``file_path`` does not exist.
        """
        text = file_path.read_text(encoding="utf-8")
        return self.chunk_text(text, document_metadata)

    def chunk_text(self, text: str, document_metadata: dict[str, Any]) -> list[Chunk]:
        """Chunk a Markdown string. Same contract as :meth:`chunk_document`."""
        if "document_id" not in document_metadata or not document_metadata["document_id"]:
            raise ValueError("document_metadata must include a non-empty 'document_id'")
        document_id = document_metadata["document_id"]
        raw_sections = self._collect_raw_sections(text)
        return self._materialise_chunks(raw_sections, document_id, document_metadata)

    def _collect_raw_sections(self, text: str) -> list[dict[str, Any]]:
        """Walk the document and group lines under H2/H3 headings."""
        raw: list[dict[str, Any]] = []
        current_h2: dict[str, Any] | None = None
        current: dict[str, Any] | None = None

        h1_re = re.compile(r"^# (.+)$")
        h2_re = re.compile(r"^## (.+)$")
        h3_re = re.compile(r"^### (.+)$")

        def flush() -> None:
            nonlocal current
            if current is not None:
                raw.append(current)
                current = None

        for line in text.splitlines():
            if h1_re.match(line):
                # H1 is the document title, skip as boundary.
                continue
            m2 = h2_re.match(line)
            if m2:
                flush()
                title = m2.group(1).strip()
                ref, clean = extract_section_ref(title)
                current_h2 = {
                    "level": 2,
                    "section_title": clean,
                    "section_ref": ref,
                    "parent_section_ref": "",
                    "lines": [],
                }
                current = current_h2
                continue
            m3 = h3_re.match(line)
            if m3:
                flush()
                title = m3.group(1).strip()
                ref, clean = extract_section_ref(title)
                parent_ref = current_h2["section_ref"] if current_h2 else ""
                current = {
                    "level": 3,
                    "section_title": clean,
                    "section_ref": ref,
                    "parent_section_ref": parent_ref,
                    "lines": [],
                }
                continue
            # H4+ and content lines accumulate in the open chunk
            if current is not None:
                current["lines"].append(line)
        flush()
        return raw

    def _materialise_chunks(
        self,
        raw: list[dict[str, Any]],
        document_id: str,
        document_metadata: dict[str, Any],
    ) -> list[Chunk]:
        """Convert raw section dicts into ``Chunk`` instances with split logic.

        ``chunk_id`` is ``{document_id}__{section_ref}__{sub_index}`` where
        ``sub_index`` is a per-section_ref counter that disambiguates
        duplicates. Most sections produce exactly one chunk with
        ``sub_index=0``. Collisions arise when a document has two distinct
        H2/H3 with titles that resolve to the same ``section_ref`` (e.g.
        two ``### D.CDS.3.2`` blocks for different CdS in ava3_unict, or
        slug-fallback collisions when two long titles share their first
        four words).
        """
        chunks: list[Chunk] = []
        chunk_order = 0
        # Track how many chunks have already been emitted for each section_ref
        # so duplicates get monotonically increasing sub_indexes.
        sub_index_counter: dict[str, int] = {}

        for section in raw:
            body = "\n".join(section["lines"]).strip()
            if not body:
                continue

            sub_bodies = _split_long(body, self.max_chars, self.hard_max_chars)
            sub_bodies = _merge_noise_subchunks(
                sub_bodies, _MIN_SUB_CHUNK_ALNUM, self.hard_max_chars
            )
            for j, sub in enumerate(sub_bodies):
                if len(sub_bodies) > 1:
                    section_ref = f"{section['section_ref']}.{_suffix_for(j)}"
                    parent_section_ref = section["section_ref"]
                else:
                    section_ref = section["section_ref"]
                    parent_section_ref = section["parent_section_ref"]

                sub_index = sub_index_counter.get(section_ref, 0)
                sub_index_counter[section_ref] = sub_index + 1

                chunk_id = f"{document_id}__{section_ref}__{sub_index}"
                metadata = {
                    **document_metadata,
                    "section_title": section["section_title"],
                    "section_ref": section_ref,
                    "parent_section_ref": parent_section_ref,
                    "chunk_order": chunk_order,
                    "sub_index": sub_index,
                    "char_count": len(sub),
                    "language": document_metadata.get("language", "it"),
                }
                chunks.append(Chunk(chunk_id=chunk_id, text=sub, metadata=metadata))
                chunk_order += 1
        return chunks
