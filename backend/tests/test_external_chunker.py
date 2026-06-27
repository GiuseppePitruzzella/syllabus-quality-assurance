"""Tests for the ExternalDocumentChunker (Phase 8.B.2).

Covers: plain-text input with no headings, deterministic chunk
order and ids, flat metadata, tag_E* boolean encoding, size-based
splitting cascade, empty input, missing required metadata,
isolation between versions (same document id with different
version yields distinct chunk ids).
"""
from __future__ import annotations

import pytest

from app.local_documents.chunker import (
    ExternalDocumentChunker,
    build_chunk_id,
    chunk_id_prefix,
    linearize_tuning_matrix,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _meta(**overrides):
    base = {
        "document_id": 1,
        "version": 1,
        "cdl_id": 3,
        "document_type": "usi_dipartimentali",
        "academic_year": "2025-2026",
        "file_hash": "abc123",
        "enabled_criteria": ["E5"],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_short_plain_text_produces_one_chunk():
    text = "Linee guida LM-18.\nPrerequisiti culturali e disciplinari."
    chunks = ExternalDocumentChunker().chunk_text(text, _meta())
    assert len(chunks) == 1
    c = chunks[0]
    assert c.chunk_id == "external_1_v1__chunk_0000"
    assert c.text == text
    assert c.metadata["document_id"] == 1
    assert c.metadata["cdl_id"] == 3
    assert c.metadata["version"] == 1
    assert c.metadata["chunk_order"] == 0
    assert c.metadata["char_count"] == len(text)
    assert c.metadata["document_type"] == "usi_dipartimentali"
    assert c.metadata["academic_year"] == "2025-2026"
    assert c.metadata["file_hash"] == "abc123"


def test_chunk_id_format_and_prefix_match():
    """build_chunk_id and chunk_id_prefix must agree for delete-by-prefix."""
    cid = build_chunk_id(42, 3, 7)
    assert cid == "external_42_v3__chunk_0007"
    assert cid.startswith(chunk_id_prefix(42, 3))


def test_chunk_order_is_zero_padded_to_four_digits():
    # Force many chunks by feeding paragraphs over hard_max_chars.
    paragraphs = ["paragrafo " + str(i) + " " + ("x" * 50) for i in range(20)]
    text = "\n\n".join(paragraphs)
    chunks = ExternalDocumentChunker(
        max_chars=200, hard_max_chars=300,
    ).chunk_text(text, _meta())
    for i, c in enumerate(chunks):
        assert c.chunk_id == f"external_1_v1__chunk_{i:04d}"
        assert c.metadata["chunk_order"] == i


def test_enabled_criteria_become_boolean_tags():
    chunks = ExternalDocumentChunker().chunk_text(
        "corpo", _meta(enabled_criteria=["E1", "E3"]),
    )
    md = chunks[0].metadata
    assert md["tag_E1"] is True
    assert md["tag_E2"] is False
    assert md["tag_E3"] is True
    assert md["tag_E4"] is False
    assert md["tag_E5"] is False


def test_enabled_criteria_missing_means_all_false_tags():
    chunks = ExternalDocumentChunker().chunk_text(
        "corpo", _meta(enabled_criteria=[]),
    )
    md = chunks[0].metadata
    for code in ("E1", "E2", "E3", "E4", "E5"):
        assert md[f"tag_{code}"] is False


def test_metadata_is_flat_scalar_only():
    chunks = ExternalDocumentChunker().chunk_text(
        "corpo", _meta(enabled_criteria=["E5"]),
    )
    for key, value in chunks[0].metadata.items():
        assert isinstance(value, (str, int, float, bool)), (
            f"metadata key {key!r} is not a flat scalar: {type(value).__name__}"
        )


def test_optional_metadata_keys_are_dropped_when_missing():
    md_in = _meta()
    md_in.pop("academic_year")
    md_in.pop("file_hash")
    chunks = ExternalDocumentChunker().chunk_text("corpo", md_in)
    out = chunks[0].metadata
    assert "academic_year" not in out
    assert "file_hash" not in out
    assert out["document_type"] == "usi_dipartimentali"


def test_tuning_matrix_maps_x_cells_to_explicit_course_names():
    text = """Pagina 1
MATRICE DI TUNING
Corso A | Corso B | Corso C | Corso D | Corso E
Competenze/Descrittori di Dublino/Risultati di apprendimento | | | | | |
Risultato alpha | X | | X | | | |
continuazione del risultato | | | | |
Risultato trasversale | X | X | X | X | X
"""

    linearized = linearize_tuning_matrix(text)

    assert "Corso A | Corso B" not in linearized
    assert "Risultato alpha" in linearized
    assert "Attività formative associate: Corso A; Corso C" in linearized
    assert "continuazione del risultato" in linearized
    assert "Attività formative associate: tutte le attività formative" in linearized


def test_tuning_matrix_without_recognisable_header_is_unchanged():
    text = (
        "Competenze/Descrittori di Dublino | | |\n"
        "Risultato alpha | X | |"
    )
    assert linearize_tuning_matrix(text) == text


def test_tuning_matrix_chunking_uses_linearized_associations():
    text = """MATRICE DI TUNING
Corso A | Corso B | Corso C | Corso D | Corso E
Competenze/Descrittori di Dublino/Risultati di apprendimento | | | | |
Risultato alpha | | X | | X |
"""

    chunks = ExternalDocumentChunker().chunk_text(
        text,
        _meta(document_type="matrice_tuning", enabled_criteria=["E2"]),
    )

    assert len(chunks) == 1
    assert "Attività formative associate: Corso B; Corso D" in chunks[0].text
    assert "Risultato alpha |" not in chunks[0].text


# ---------------------------------------------------------------------------
# Size-based splitting
# ---------------------------------------------------------------------------


def test_long_text_splits_on_paragraph_boundary():
    # Two paragraphs that together exceed the hard limit.
    p1 = "Paragrafo uno. " * 100
    p2 = "Paragrafo due. " * 100
    text = p1.strip() + "\n\n" + p2.strip()
    chunks = ExternalDocumentChunker(
        max_chars=500, hard_max_chars=900,
    ).chunk_text(text, _meta())
    assert len(chunks) >= 2
    # Every chunk respects the hard limit (modulo last-resort hard cut).
    assert all(len(c.text) <= 900 for c in chunks)
    # Order is preserved.
    orders = [c.metadata["chunk_order"] for c in chunks]
    assert orders == sorted(orders)


def test_deterministic_chunking_same_input_same_output():
    text = "Sezione A.\n\nSezione B.\n\nSezione C."
    a = ExternalDocumentChunker().chunk_text(text, _meta())
    b = ExternalDocumentChunker().chunk_text(text, _meta())
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]
    assert [c.text for c in a] == [c.text for c in b]
    assert [c.metadata for c in a] == [c.metadata for c in b]


# ---------------------------------------------------------------------------
# Isolation between versions
# ---------------------------------------------------------------------------


def test_same_document_id_different_versions_yield_distinct_chunk_ids():
    text = "Linee guida."
    v1 = ExternalDocumentChunker().chunk_text(text, _meta(version=1))
    v2 = ExternalDocumentChunker().chunk_text(text, _meta(version=2))
    assert v1[0].chunk_id != v2[0].chunk_id
    assert v1[0].chunk_id.startswith("external_1_v1__")
    assert v2[0].chunk_id.startswith("external_1_v2__")


# ---------------------------------------------------------------------------
# Edge cases / validation
# ---------------------------------------------------------------------------


def test_empty_text_yields_no_chunks():
    assert ExternalDocumentChunker().chunk_text("", _meta()) == []
    assert ExternalDocumentChunker().chunk_text("    \n\n", _meta()) == []


def test_missing_document_id_raises():
    md = _meta()
    md.pop("document_id")
    with pytest.raises(ValueError):
        ExternalDocumentChunker().chunk_text("text", md)


def test_missing_version_raises():
    md = _meta()
    md.pop("version")
    with pytest.raises(ValueError):
        ExternalDocumentChunker().chunk_text("text", md)


def test_missing_cdl_id_raises():
    md = _meta()
    md.pop("cdl_id")
    with pytest.raises(ValueError):
        ExternalDocumentChunker().chunk_text("text", md)


def test_missing_enabled_criteria_raises():
    md = _meta()
    md.pop("enabled_criteria")
    with pytest.raises(ValueError):
        ExternalDocumentChunker().chunk_text("text", md)


def test_non_positive_document_id_raises():
    with pytest.raises(ValueError):
        ExternalDocumentChunker().chunk_text("text", _meta(document_id=0))


def test_hard_max_chars_lower_than_max_chars_raises():
    with pytest.raises(ValueError):
        ExternalDocumentChunker(max_chars=200, hard_max_chars=100)
