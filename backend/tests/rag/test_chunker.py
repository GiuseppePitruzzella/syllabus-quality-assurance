"""Unit tests for the Markdown chunker."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.evaluation.rag.chunker import (
    Chunk,
    MarkdownChunker,
    _greedy_pack,
    _merge_noise_subchunks,
    _split_long,
    _suffix_for,
    extract_section_ref,
)


# ---------------------------------------------------------------------------
# extract_section_ref
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title, expected_ref, expected_clean",
    [
        ("3.1 - Risultati di apprendimento", "3.1", "Risultati di apprendimento"),
        ("3.4 Valutazione", "3.4", "Valutazione"),
        ("1.1.1 Sotto-sotto", "1.1.1", "Sotto-sotto"),
        ("D.CDS.1.4.1 - Programmazione", "D.CDS.1.4.1", "Programmazione"),
        ("D.CDS.2.4 Aspetti", "D.CDS.2.4", "Aspetti"),
        ("Art. 1 (Ambito di applicazione)", "Art. 1", "Ambito di applicazione"),
        ("Art. 12 - Decorrenza", "Art. 12", "Decorrenza"),
        ("Quadro A - Analisi", "Quadro A", "Analisi"),
        ("Quadro B.1 - Sub", "Quadro B.1", "Sub"),
        ("Allegato A", "Allegato A", "Allegato A"),
        ("Allegato 2 - Esempi", "Allegato 2", "Esempi"),
        ("Parte I - Introduzione", "Parte I", "Introduzione"),
        ("Parte II", "Parte II", "Parte II"),
    ],
)
def test_extract_section_ref_recognised_patterns(title, expected_ref, expected_clean):
    ref, clean = extract_section_ref(title)
    assert ref == expected_ref
    assert clean == expected_clean


def test_extract_section_ref_fallback_slug():
    """Untyped headings produce a slug from the first words, not an empty ref."""
    ref, clean = extract_section_ref("Premesse e Riferimenti Normativi")
    assert ref == "premesse_e_riferimenti_normativi"
    assert clean == "Premesse e Riferimenti Normativi"


def test_extract_section_ref_fallback_strips_punctuation():
    ref, _ = extract_section_ref("Sommario")
    assert ref == "sommario"


# Stability tests: section_ref must be deterministic across calls and stable
# under cosmetic title changes, because tagging_rules.yaml will key on it.


def test_extract_section_ref_slug_is_deterministic():
    """Same title produces the same slug across repeated calls."""
    title = "Premesse e Riferimenti Normativi"
    refs = {extract_section_ref(title)[0] for _ in range(5)}
    assert refs == {"premesse_e_riferimenti_normativi"}


def test_extract_section_ref_slug_stable_under_case_changes():
    """Lowercased and uppercased forms of the same title yield the same slug."""
    ref_lower, _ = extract_section_ref("premesse e riferimenti normativi")
    ref_title, _ = extract_section_ref("Premesse e Riferimenti Normativi")
    ref_upper, _ = extract_section_ref("PREMESSE E RIFERIMENTI NORMATIVI")
    assert ref_lower == ref_title == ref_upper


def test_extract_section_ref_slug_stable_under_trailing_punctuation():
    """Trailing colon/dash on a heading does not change the slug."""
    assert extract_section_ref("Sommario")[0] == extract_section_ref("Sommario:")[0]
    assert extract_section_ref("Indice")[0] == extract_section_ref("Indice -")[0]


def test_extract_section_ref_slug_stable_under_extra_whitespace():
    """Extra internal whitespace is collapsed and does not affect the slug."""
    ref1, _ = extract_section_ref("Premesse e Riferimenti")
    ref2, _ = extract_section_ref("  Premesse  e   Riferimenti  ")
    assert ref1 == ref2

    # Section refs from numbered patterns must also be stable.
    assert extract_section_ref("3.1 - Risultati")[0] == "3.1"
    assert extract_section_ref("  3.1  -  Risultati  ")[0] == "3.1"


# ---------------------------------------------------------------------------
# _suffix_for
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "index, expected",
    [(0, "a"), (1, "b"), (25, "z"), (26, "aa"), (27, "ab"), (51, "az"), (52, "ba")],
)
def test_suffix_for(index, expected):
    assert _suffix_for(index) == expected


def test_suffix_for_negative_raises():
    with pytest.raises(ValueError):
        _suffix_for(-1)


# ---------------------------------------------------------------------------
# _greedy_pack
# ---------------------------------------------------------------------------


def test_greedy_pack_packs_under_max():
    items = ["aaa", "bbb", "ccc"]
    packed = _greedy_pack(items, max_chars=10, separator="|")
    # 'aaa|bbb' = 7, adding '|ccc' -> 11 > 10, so split
    assert packed == ["aaa|bbb", "ccc"]


def test_greedy_pack_emits_oversize_alone():
    """An item already longer than max_chars is emitted as its own packet."""
    items = ["short", "x" * 100, "tail"]
    packed = _greedy_pack(items, max_chars=10, separator=" ")
    assert packed[0] == "short"
    assert packed[1] == "x" * 100  # emitted alone, oversize
    assert packed[2] == "tail"


def test_greedy_pack_skips_empty():
    packed = _greedy_pack(["a", "", "  ", "b"], max_chars=100, separator=" ")
    assert packed == ["a b"]


# ---------------------------------------------------------------------------
# _split_long
# ---------------------------------------------------------------------------


def test_split_long_returns_short_body_unchanged():
    body = "x" * 100
    assert _split_long(body, max_chars=200, hard_max_chars=400) == [body]


def test_split_long_paragraph_split():
    body = ("Paragrafo uno.\n\n" + "x" * 600 + "\n\n" + "Paragrafo tre.")
    parts = _split_long(body, max_chars=400, hard_max_chars=600)
    assert len(parts) >= 2


def test_split_long_keeps_oversize_paragraph_under_hard_limit():
    """A single paragraph between max_chars and hard_max_chars is kept whole.

    Semantic coherence beats hitting the soft target: a paragraph that
    expresses one idea should not be split mid-thought just to drop a
    few hundred characters. Construct a body large enough to force a
    top-level split, then verify the 1800-char paragraph survives.
    """
    big_paragraph = "y" * 1800
    body = (
        "Premesse introduttive del paragrafo iniziale.\n\n"
        + big_paragraph
        + "\n\n"
        + "Coda esplicativa: " + ("z" * 600)
    )
    parts = _split_long(body, max_chars=1500, hard_max_chars=2200)
    # The 1800-char paragraph stays in its own sub-chunk (under hard limit),
    # not split into ~1500 + ~300 by line/sentence/hard-cut.
    assert any(big_paragraph in p and len(p) <= 2200 for p in parts)
    # And nothing was hard-cut into 1500 + 300 fragments of the big paragraph.
    assert not any(len(p) >= 1499 and len(p) <= 1501 and "y" in p for p in parts)


def test_split_long_recurses_when_paragraph_exceeds_hard_limit():
    """A paragraph past the hard limit is split at finer granularity."""
    rows = [f"row{i}" + "x" * 1000 for i in range(8)]
    body = "\n".join(rows)  # ~8 lines × 1004 = ~8032 chars, no blank lines
    parts = _split_long(body, max_chars=1500, hard_max_chars=2200)
    assert len(parts) > 1
    assert all(len(p) <= 2200 for p in parts)


def test_split_long_falls_through_to_hard_cut():
    """A body with no separators at all is hard-cut at hard_max_chars."""
    body = "x" * 1000
    parts = _split_long(body, max_chars=300, hard_max_chars=300)
    assert len(parts) == 4  # ceil(1000/300)
    assert parts[0] == "x" * 300
    assert parts[-1] == "x" * 100


# ---------------------------------------------------------------------------
# _merge_noise_subchunks
# ---------------------------------------------------------------------------


def test_merge_noise_into_previous():
    real = "a" * 100  # high alnum
    noise = "|||"  # low alnum
    merged = _merge_noise_subchunks([real, noise], min_alnum=30, max_chars=1000)
    assert len(merged) == 1
    assert merged[0].startswith(real)
    assert merged[0].endswith(noise)


def test_merge_skips_when_overflow_would_occur():
    real = "a" * 990  # high alnum, near limit
    noise = "|" * 50  # low alnum
    merged = _merge_noise_subchunks([real, noise], min_alnum=30, max_chars=1000)
    # Merging would yield 990 + 1 + 50 = 1041 > 1000, so noise stays alone.
    assert merged == [real, noise]


def test_merge_singleton_passes_through():
    merged = _merge_noise_subchunks(["|"], min_alnum=30, max_chars=1000)
    assert merged == ["|"]


def test_merge_leading_noise_attaches_to_next_real():
    noise = "|||"
    real = "x" * 100
    merged = _merge_noise_subchunks([noise, real], min_alnum=30, max_chars=1000)
    assert len(merged) == 1
    assert noise in merged[0]
    assert real in merged[0]


# ---------------------------------------------------------------------------
# MarkdownChunker.chunk_text — end-to-end behaviour
# ---------------------------------------------------------------------------


def test_chunker_basic_h2_h3_hierarchy():
    md = """
# Doc title

## 1. Premessa

Testo introduttivo della premessa.

## 2. Indicazioni operative

### 2.1 Sotto-tema A

Contenuto del sotto-tema A.

### 2.2 Sotto-tema B

Contenuto del sotto-tema B.
""".strip()

    ck = MarkdownChunker()
    chunks = ck.chunk_text(md, {"document_id": "test", "language": "it"})

    refs = [c.metadata["section_ref"] for c in chunks]
    assert refs == ["1", "2.1", "2.2"]
    # H2 "2." has no body of its own (immediately followed by H3) → no chunk.
    assert all(c.text.strip() for c in chunks)


def test_chunker_parent_section_ref_for_h3():
    md = """
## 3. Guida alla compilazione

### 3.1 Risultati di apprendimento

Contenuto 3.1.

### 3.2 Prerequisiti

Contenuto 3.2.
""".strip()

    ck = MarkdownChunker()
    chunks = ck.chunk_text(md, {"document_id": "lg_unict"})
    by_ref = {c.metadata["section_ref"]: c for c in chunks}
    assert by_ref["3.1"].metadata["parent_section_ref"] == "3"
    assert by_ref["3.2"].metadata["parent_section_ref"] == "3"


def test_chunker_chunk_id_format():
    md = "## 2. Indicazioni\n\nContenuto."
    ck = MarkdownChunker()
    chunks = ck.chunk_text(md, {"document_id": "lg_unict"})
    assert chunks[0].chunk_id == "lg_unict__2__0"


def test_chunker_chunk_ids_are_unique():
    md = """
## 1. A

Testo A.

## 2. B

Testo B.

### 2.1 Sub

Testo Sub.
""".strip()
    ck = MarkdownChunker()
    chunks = ck.chunk_text(md, {"document_id": "doc"})
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))


def test_chunker_disambiguates_repeated_section_ref_via_sub_index():
    """Two distinct H2/H3 with the same section_ref get unique chunk_ids."""
    md = """
## D.CDS.3.2 Dotazione di personale

Primo blocco.

## D.CDS.3.2 Dotazione di personale (LM-41)

Secondo blocco.
""".strip()
    ck = MarkdownChunker()
    chunks = ck.chunk_text(md, {"document_id": "ava3_unict"})
    assert len(chunks) == 2
    # section_ref is the same for both (the duplicate is a real feature of
    # the source document), but chunk_id and sub_index differ.
    assert chunks[0].metadata["section_ref"] == chunks[1].metadata["section_ref"]
    assert chunks[0].metadata["sub_index"] == 0
    assert chunks[1].metadata["sub_index"] == 1
    assert chunks[0].chunk_id != chunks[1].chunk_id
    assert chunks[0].chunk_id.endswith("__0")
    assert chunks[1].chunk_id.endswith("__1")


def test_chunker_split_long_section_uses_letter_suffix():
    """A long section produces sub-chunks with .a/.b suffixes."""
    body = ("Paragrafo " + "x" * 800 + "\n\n") * 3
    md = f"## 5. Lunga\n\n{body}"
    ck = MarkdownChunker(max_chars=1000)
    chunks = ck.chunk_text(md, {"document_id": "doc"})
    refs = [c.metadata["section_ref"] for c in chunks]
    assert len(refs) > 1
    assert refs[0].endswith(".a")
    assert refs[1].endswith(".b")
    # parent_section_ref should be the un-suffixed ref
    assert chunks[0].metadata["parent_section_ref"] == "5"


def test_chunker_empty_section_skipped():
    md = """
## 1. Vuota

## 2. Piena

Contenuto.
""".strip()
    ck = MarkdownChunker()
    chunks = ck.chunk_text(md, {"document_id": "doc"})
    # H2 "1." has only whitespace body and is skipped.
    refs = [c.metadata["section_ref"] for c in chunks]
    assert refs == ["2"]


def test_chunker_h1_ignored_as_boundary():
    md = """
# Document Title

## 1. Sezione

Body."""
    ck = MarkdownChunker()
    chunks = ck.chunk_text(md, {"document_id": "doc"})
    # H1 does not produce a chunk; the H2 is the only boundary.
    assert len(chunks) == 1
    assert chunks[0].metadata["section_ref"] == "1"


def test_chunker_h4_kept_as_content():
    md = """
## 1. Sezione

#### Sotto-titolo H4

Contenuto sotto H4.
"""
    ck = MarkdownChunker()
    chunks = ck.chunk_text(md, {"document_id": "doc"})
    # The H4 line is part of the content, not a boundary, so it stays in body.
    assert len(chunks) == 1
    assert "#### Sotto-titolo H4" in chunks[0].text


def test_chunker_metadata_includes_provenance():
    """document_metadata fields propagate into every chunk's metadata."""
    md = "## 1. Sez\n\nBody."
    ck = MarkdownChunker()
    chunks = ck.chunk_text(
        md,
        {
            "document_id": "lg_unict",
            "document_title": "Linee Guida UniCT",
            "document_version": "2.0",
            "source_type": "linea_guida_ateneo",
            "document_priority": 2,
            "language": "it",
        },
    )
    md_meta = chunks[0].metadata
    assert md_meta["document_id"] == "lg_unict"
    assert md_meta["document_title"] == "Linee Guida UniCT"
    assert md_meta["document_version"] == "2.0"
    assert md_meta["source_type"] == "linea_guida_ateneo"
    assert md_meta["document_priority"] == 2
    assert md_meta["language"] == "it"
    assert md_meta["section_ref"] == "1"
    assert md_meta["chunk_order"] == 0
    assert md_meta["char_count"] == len(chunks[0].text)


def test_chunker_chunk_order_increments():
    md = """
## 1. A

Testo A.

## 2. B

Testo B.

## 3. C

Testo C.
""".strip()
    ck = MarkdownChunker()
    chunks = ck.chunk_text(md, {"document_id": "doc"})
    orders = [c.metadata["chunk_order"] for c in chunks]
    assert orders == [0, 1, 2]


def test_chunker_requires_document_id():
    ck = MarkdownChunker()
    with pytest.raises(ValueError, match="document_id"):
        ck.chunk_text("## 1. X\n\nBody.", {})


def test_chunker_rejects_hard_limit_below_soft_limit():
    with pytest.raises(ValueError, match="hard_max_chars"):
        MarkdownChunker(max_chars=2000, hard_max_chars=1000)


def test_chunk_model_validates_required_fields():
    with pytest.raises(Exception):  # noqa: B017 — pydantic raises ValidationError
        Chunk(chunk_id="", text="text", metadata={})  # empty chunk_id
    with pytest.raises(Exception):  # noqa: B017
        Chunk(chunk_id="id", text="", metadata={})  # empty text


def test_chunker_chunk_document_reads_file(tmp_path: Path):
    f = tmp_path / "doc.md"
    f.write_text("# Title\n\n## 1. Sez\n\nBody content.\n", encoding="utf-8")
    ck = MarkdownChunker()
    chunks = ck.chunk_document(f, {"document_id": "test"})
    assert len(chunks) == 1
    assert chunks[0].text.strip() == "Body content."


def test_chunker_chunk_document_missing_file_raises(tmp_path: Path):
    ck = MarkdownChunker()
    with pytest.raises(FileNotFoundError):
        ck.chunk_document(tmp_path / "missing.md", {"document_id": "test"})
