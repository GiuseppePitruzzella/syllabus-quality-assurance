"""Plain-text chunker for the local-document registry (Phase 8.B.2).

The corpus ``MarkdownChunker`` is specialised on the normative
corpus: it slices on Markdown ``##`` / ``###`` boundaries, treats
text before the first ``##`` as document title, and would produce
zero chunks on a flat PDF or DOCX extracted as plain text.

``ExternalDocumentChunker`` is the plain-text counterpart. It uses
the same paragraph -> line -> sentence -> hard-cut cascade — shared
from :mod:`app.text_splitting` — but does NOT look for headings:
the whole document is one "section" that is then split by size.

Chunk identifiers and metadata are deliberately distinct from the
corpus chunker so the two paths can coexist in different ChromaDB
collections without colliding:

  - id format:   ``external_{document_id}_v{version}__chunk_{order:04d}``
  - metadata:    flat scalars only (str / int / bool); booleans
                 ``tag_E1`` ... ``tag_E5`` are derived from
                 ``enabled_criteria`` so the registry's enabled-
                 list is queryable from Chroma without having to
                 store a list-typed metadata field (Chroma rejects
                 list / dict / None on add, and the existing
                 corpus pipeline already has a cleaner that drops
                 non-scalars).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.text_splitting import (
    DEFAULT_HARD_MAX_CHARS,
    DEFAULT_MAX_CHARS,
    merge_noise_subchunks,
    split_long,
)

_MIN_SUB_CHUNK_ALNUM = 30
_KNOWN_EXTENDED_CRITERIA = ("E1", "E2", "E3", "E4", "E5")


class ExternalChunk(BaseModel):
    """A chunk produced by :class:`ExternalDocumentChunker`.

    Mirrors the shape of :class:`app.evaluation.rag.chunker.Chunk`
    so the ingester loop can stay symmetric, but uses a distinct
    Pydantic class so the two paths are type-checked independently
    in static analysis.
    """

    chunk_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    metadata: dict[str, Any]


class ExternalDocumentChunker:
    """Chunk a plain-text local document by size only.

    The default size limits match the corpus chunker so the two
    pipelines feed Chroma chunks with comparable density. Override
    via constructor args if a particular registry use case needs
    finer or coarser granularity.
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

    def chunk_text(
        self, text: str, document_metadata: dict[str, Any],
    ) -> list[ExternalChunk]:
        """Split ``text`` into chunks and decorate with metadata.

        Required metadata keys:
            - ``document_id`` (int): the local-document row id.
            - ``version``     (int): the row's version.
            - ``cdl_id``      (int): the CdL the document belongs to.
            - ``enabled_criteria`` (list[str]): list of E codes.

        Recommended but optional:
            - ``document_type``, ``academic_year``, ``file_hash``.

        Returns the list of chunks in document order, with
        deterministic identifiers
        ``external_{document_id}_v{version}__chunk_{order:04d}``.
        Empty / whitespace-only input yields an empty list.

        Raises:
            ValueError: when a required metadata key is missing or
                ``document_id`` / ``version`` are not positive ints.
        """
        document_id = document_metadata.get("document_id")
        version = document_metadata.get("version")
        if not isinstance(document_id, int) or document_id <= 0:
            raise ValueError(
                "document_metadata['document_id'] must be a positive int",
            )
        if not isinstance(version, int) or version <= 0:
            raise ValueError(
                "document_metadata['version'] must be a positive int",
            )
        if "cdl_id" not in document_metadata:
            raise ValueError("document_metadata must include 'cdl_id'")
        if "enabled_criteria" not in document_metadata:
            raise ValueError("document_metadata must include 'enabled_criteria'")

        body = text.strip()
        if not body:
            return []
        if document_metadata.get("document_type") == "matrice_tuning":
            body = linearize_tuning_matrix(body)

        sub_bodies = split_long(body, self.max_chars, self.hard_max_chars)
        sub_bodies = merge_noise_subchunks(
            sub_bodies, _MIN_SUB_CHUNK_ALNUM, self.hard_max_chars,
        )

        chunks: list[ExternalChunk] = []
        for order, sub in enumerate(sub_bodies):
            chunk_id = build_chunk_id(document_id, version, order)
            metadata = _build_metadata(document_metadata, sub, order)
            chunks.append(
                ExternalChunk(chunk_id=chunk_id, text=sub, metadata=metadata)
            )
        return chunks


def build_chunk_id(document_id: int, version: int, chunk_order: int) -> str:
    """Deterministic chunk identifier for the external collection.

    Shape: ``external_{document_id}_v{version}__chunk_{order:04d}``.
    Used by both the chunker (to mint ids) and the ingester (to
    delete previous versions before re-ingesting an idempotent
    re-index).
    """
    return f"external_{document_id}_v{version}__chunk_{chunk_order:04d}"


def chunk_id_prefix(document_id: int, version: int) -> str:
    """Prefix that matches every chunk for a (document, version) pair.

    Used by the ingester to enumerate-and-delete the previous
    chunks of a document before re-ingesting an idempotent
    re-index. Re-extracting the same document might produce a
    different number of chunks; deletion-by-prefix is the only way
    to guarantee no orphans survive a shrink.
    """
    return f"external_{document_id}_v{version}__"


def linearize_tuning_matrix(text: str) -> str:
    """Replace positional ``X`` cells with explicit course associations.

    Scanned tuning matrices are commonly one very wide table. OCR can
    preserve cell separators accurately while leaving the header in a
    different chunk from the rows containing the ``X`` marks. Those
    chunks are readable but semantically incomplete.

    When a course-header row can be identified immediately before the
    ``Competenze/Descrittori`` row, each marked row is rewritten as::

        <learning outcome>
        Attività formative associate: <course A>; <course B>

    Missing or extra trailing empty cells are normalised safely. If the
    header cannot be identified, the original text is returned unchanged
    rather than guessing column semantics.
    """
    lines = text.splitlines()
    descriptor_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "|" in line
            and (
                "competenze/descrittori" in line.casefold()
                or "descrittori di dublino" in line.casefold()
            )
        ),
        None,
    )
    if descriptor_index is None:
        return text

    header_index = next(
        (
            index
            for index in range(descriptor_index - 1, -1, -1)
            if _looks_like_course_header(lines[index])
        ),
        None,
    )
    if header_index is None:
        return text

    headers = [cell.strip() for cell in lines[header_index].split("|")]
    while headers and not headers[-1]:
        headers.pop()
    if headers and not headers[0]:
        headers.pop(0)
    if len(headers) < 5 or any(not header for header in headers):
        return text

    output = [line for line in lines[:header_index] if line.strip()]
    output.append(
        "Matrice linearizzata: le associazioni sono espresse per nome "
        "dell'attività formativa."
    )

    expected_cells = len(headers) + 1
    for raw_line in lines[descriptor_index:]:
        if "|" not in raw_line:
            if raw_line.strip():
                output.append(raw_line.strip())
            continue

        cells = [cell.strip() for cell in raw_line.split("|")]
        while len(cells) > expected_cells and not cells[-1]:
            cells.pop()
        while len(cells) < expected_cells:
            cells.append("")

        # A non-empty overflow would shift one or more associations.
        # Preserve that row verbatim instead of manufacturing a mapping.
        if len(cells) != expected_cells:
            output.append(raw_line.strip())
            continue

        description = cells[0]
        marked_indexes = [
            index
            for index, cell in enumerate(cells[1:])
            if cell.casefold() == "x"
        ]
        if description:
            output.append(description)
        if marked_indexes:
            if len(marked_indexes) == len(headers):
                associations = "tutte le attività formative"
            else:
                associations = "; ".join(
                    headers[index] for index in marked_indexes
                )
            output.append(f"Attività formative associate: {associations}")

    return "\n".join(output).strip()


def _looks_like_course_header(line: str) -> bool:
    cells = [cell.strip() for cell in line.split("|")]
    non_empty = [cell for cell in cells if cell]
    return (
        len(non_empty) >= 5
        and len(non_empty) == len(cells)
        and not any(cell.casefold() == "x" for cell in non_empty)
    )


def _build_metadata(
    document_metadata: dict[str, Any], text: str, chunk_order: int,
) -> dict[str, Any]:
    """Compose the ChromaDB metadata payload for a single chunk.

    Layout (all scalar):
        document_id, cdl_id, document_type, version, academic_year,
        file_hash, chunk_order, char_count,
        tag_E1, tag_E2, tag_E3, tag_E4, tag_E5

    ``enabled_criteria`` is NOT stored as a list (Chroma rejects
    list-typed metadata). The same information is encoded as five
    boolean ``tag_E*`` flags, which is also the shape the retriever
    will filter on in Phase 9.
    """
    enabled = set(document_metadata.get("enabled_criteria") or [])
    md: dict[str, Any] = {
        "document_id": int(document_metadata["document_id"]),
        "cdl_id": int(document_metadata["cdl_id"]),
        "version": int(document_metadata["version"]),
        "chunk_order": chunk_order,
        "char_count": len(text),
    }
    # Optional fields — keep them as strings when present, never None.
    for key in ("document_type", "academic_year", "file_hash"):
        value = document_metadata.get(key)
        if value is not None:
            md[key] = str(value)
    for code in _KNOWN_EXTENDED_CRITERIA:
        md[f"tag_{code}"] = code in enabled
    return md
