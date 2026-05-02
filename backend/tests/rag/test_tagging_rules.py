"""Unit tests for tagging_rules: loader, validation, prefix matching."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.evaluation.rag.chunker import Chunk
from app.evaluation.rag.tagging_rules import (
    ALL_AGENTS,
    ALL_CRITERIA,
    TaggingRules,
    TaggingRulesError,
    _matches_prefix,
)


def _make_chunk(document_id: str, section_ref: str, text: str = "body") -> Chunk:
    return Chunk(
        chunk_id=f"{document_id}__{section_ref}__0",
        text=text,
        metadata={
            "document_id": document_id,
            "section_ref": section_ref,
        },
    )


# ---------------------------------------------------------------------------
# _matches_prefix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ref, key, expected",
    [
        ("3.1", "3.1", True),
        ("3.1.a", "3.1", True),
        ("3.1.5", "3.1", True),
        ("3.10", "3.1", False),  # critical: 3.10 must NOT match key 3.1
        ("3", "3.1", False),
        ("D.CDS.1.4.1", "D.CDS.1.4", True),
        ("D.CDS.1.4", "D.CDS.1", True),
        ("D.CDS.1.40", "D.CDS.1.4", False),
        ("Allegato 1.a", "Allegato 1", True),
        ("Allegato 10", "Allegato 1", False),
    ],
)
def test_matches_prefix(ref, key, expected):
    assert _matches_prefix(ref, key) is expected


# ---------------------------------------------------------------------------
# TaggingRules construction and validation
# ---------------------------------------------------------------------------


def test_rules_rejects_missing_documents_key():
    with pytest.raises(TaggingRulesError, match="documents"):
        TaggingRules({"foo": {}})


def test_rules_rejects_unknown_criterion(tmp_path: Path):
    bad = tmp_path / "rules.yaml"
    bad.write_text(
        "documents:\n"
        "  doc1:\n"
        "    section_tags:\n"
        "      '1':\n"
        "        criterion_tags: [C99]\n"
        "        agent_tags: []\n",
        encoding="utf-8",
    )
    with pytest.raises(TaggingRulesError, match="unknown criterion"):
        TaggingRules.from_yaml(bad)


def test_rules_rejects_unknown_agent(tmp_path: Path):
    bad = tmp_path / "rules.yaml"
    bad.write_text(
        "documents:\n"
        "  doc1:\n"
        "    section_tags:\n"
        "      '1':\n"
        "        criterion_tags: []\n"
        "        agent_tags: [A99]\n",
        encoding="utf-8",
    )
    with pytest.raises(TaggingRulesError, match="unknown agent"):
        TaggingRules.from_yaml(bad)


def test_rules_from_yaml_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        TaggingRules.from_yaml(tmp_path / "nope.yaml")


def test_rules_section_tags_must_be_mapping(tmp_path: Path):
    bad = tmp_path / "rules.yaml"
    bad.write_text(
        "documents:\n  doc1:\n    section_tags: 'not a mapping'\n",
        encoding="utf-8",
    )
    with pytest.raises(TaggingRulesError, match="section_tags"):
        TaggingRules.from_yaml(bad)


# ---------------------------------------------------------------------------
# apply() — tag propagation
# ---------------------------------------------------------------------------


def _rules() -> TaggingRules:
    """Build a small in-memory rule set for tests."""
    return TaggingRules(
        {
            "documents": {
                "lg_unict": {
                    "document_title": "LG UniCT",
                    "document_version": "2.0",
                    "source_type": "linea_guida_ateneo",
                    "document_priority": 2,
                    "excluded_sections": [],
                    "section_tags": {
                        "1": {"criterion_tags": [], "agent_tags": []},
                        "3.1": {
                            "criterion_tags": ["C3", "C4"],
                            "agent_tags": ["A2"],
                        },
                        "3.4": {
                            "criterion_tags": ["C6", "C8"],
                            "agent_tags": ["A3"],
                        },
                        "Allegato 1": {
                            "criterion_tags": ["C4"],
                            "agent_tags": ["A2"],
                        },
                    },
                },
                "ava3": {
                    "source_type": "linea_guida_anvur",
                    "document_priority": 2,
                    "excluded_sections": ["1", "5"],
                    "section_tags": {
                        "3.2": {"criterion_tags": ["C1"], "agent_tags": ["A1"]},
                    },
                },
            }
        }
    )


def test_apply_sets_all_tag_fields_to_bool():
    rules = _rules()
    tagged = rules.apply(_make_chunk("lg_unict", "3.1"))
    for code in ALL_CRITERIA:
        assert tagged.metadata[f"tag_{code}"] in (True, False)
    for code in ALL_AGENTS:
        assert tagged.metadata[f"tag_{code}"] in (True, False)


def test_apply_exact_match_sets_correct_tags():
    rules = _rules()
    tagged = rules.apply(_make_chunk("lg_unict", "3.1"))
    assert tagged.metadata["tag_C3"] is True
    assert tagged.metadata["tag_C4"] is True
    assert tagged.metadata["tag_A2"] is True
    # All others must be False
    assert tagged.metadata["tag_C1"] is False
    assert tagged.metadata["tag_A1"] is False


def test_apply_prefix_match_for_split_subchunks():
    """Split sub-chunks (3.4.a, 3.4.b) inherit the parent rule (3.4)."""
    rules = _rules()
    for ref in ["3.4", "3.4.a", "3.4.b", "3.4.c"]:
        tagged = rules.apply(_make_chunk("lg_unict", ref))
        assert tagged.metadata["tag_C6"] is True
        assert tagged.metadata["tag_C8"] is True
        assert tagged.metadata["tag_A3"] is True


def test_apply_prefix_match_for_allegato_with_space():
    rules = _rules()
    tagged = rules.apply(_make_chunk("lg_unict", "Allegato 1.a"))
    assert tagged.metadata["tag_C4"] is True
    assert tagged.metadata["tag_A2"] is True


def test_apply_no_match_returns_all_false():
    rules = _rules()
    tagged = rules.apply(_make_chunk("lg_unict", "3.99"))
    for code in ALL_CRITERIA:
        assert tagged.metadata[f"tag_{code}"] is False
    for code in ALL_AGENTS:
        assert tagged.metadata[f"tag_{code}"] is False


def test_apply_unknown_document_returns_all_false():
    rules = _rules()
    tagged = rules.apply(_make_chunk("unknown_doc", "1"))
    for code in ALL_CRITERIA:
        assert tagged.metadata[f"tag_{code}"] is False


def test_apply_excluded_section_strips_tags():
    """An excluded section produces no tags even if a section_tags rule matches."""
    rules = _rules()
    # ava3 has '1' excluded. A child '1.2' is also excluded by prefix.
    tagged = rules.apply(_make_chunk("ava3", "1.2"))
    for code in ALL_CRITERIA:
        assert tagged.metadata[f"tag_{code}"] is False


def test_apply_most_specific_rule_wins():
    """When a chunk matches multiple keys, the longest key prevails."""
    rules = TaggingRules(
        {
            "documents": {
                "doc": {
                    "section_tags": {
                        "1": {"criterion_tags": ["C1"], "agent_tags": []},
                        "1.4": {"criterion_tags": ["C7"], "agent_tags": ["A3"]},
                    }
                }
            }
        }
    )
    tagged = rules.apply(_make_chunk("doc", "1.4.1"))
    assert tagged.metadata["tag_C7"] is True
    assert tagged.metadata["tag_A3"] is True
    # The shorter rule "1" must NOT also apply (most-specific wins).
    assert tagged.metadata["tag_C1"] is False


def test_document_metadata_returns_provenance():
    rules = _rules()
    md = rules.document_metadata("lg_unict")
    assert md["document_id"] == "lg_unict"
    assert md["document_title"] == "LG UniCT"
    assert md["document_version"] == "2.0"
    assert md["source_type"] == "linea_guida_ateneo"
    assert md["document_priority"] == 2


def test_document_metadata_unknown_doc_returns_safe_defaults():
    rules = _rules()
    md = rules.document_metadata("unknown_doc")
    assert md["document_id"] == "unknown_doc"
    assert md["source_type"] == ""
    assert md["document_priority"] == 0


# ---------------------------------------------------------------------------
# Integration: load the actual data/tagging_rules.yaml
# ---------------------------------------------------------------------------


def test_real_rules_yaml_loads_and_covers_8_documents():
    """The committed tagging_rules.yaml is well-formed and covers all docs."""
    project_root = Path(__file__).resolve().parents[3]
    rules_path = project_root / "data" / "tagging_rules.yaml"
    if not rules_path.exists():
        pytest.skip(f"{rules_path} not present in this checkout")

    rules = TaggingRules.from_yaml(rules_path)
    expected_docs = {
        "lg_unict",
        "ava3",
        "ava3_unict",
        "dm1154",
        "lgsua_cds",
        "matrice_tuning",
        "lg_cpds_unict",
        "cpds_unict",
    }
    assert set(rules.documents()) == expected_docs
