"""Unit tests for the retrieval-query composer."""
from __future__ import annotations

import pytest

from app.evaluation.rag.query_builder import (
    AGENT_ROLES,
    CRITERION_DESCRIPTIONS,
    CRITERION_FIELDS,
    build_retrieval_query,
)


def test_query_includes_criterion_and_agent_blocks():
    q = build_retrieval_query("C3", "A2")
    assert "Criterio C3" in q
    assert "Ruolo A2" in q
    assert CRITERION_DESCRIPTIONS["C3"] in q
    assert AGENT_ROLES["A2"] in q


def test_query_includes_only_relevant_fields_for_c5():
    """C5 cares about prerequisites only — other fields are dropped."""
    syllabus = {
        "prerequisites_it": "Conoscenze di base di analisi.",
        "prerequisites_en": "Basic calculus knowledge.",
        "course_content_it": "Contenuti irrelevanti per C5.",
        "assessment_methods_it": "Modalità di verifica.",
    }
    q = build_retrieval_query("C5", "A1", syllabus)
    assert "Conoscenze di base di analisi" in q
    assert "Basic calculus knowledge" in q
    assert "Contenuti irrelevanti" not in q
    assert "Modalità di verifica" not in q


def test_query_for_c1_includes_all_non_empty_fields():
    """C1 (presence check) uses every non-empty syllabus field."""
    syllabus = {
        "prerequisites_it": "Pre.",
        "course_content_it": "Cont.",
        "assessment_methods_it": "Ver.",
        "empty_field": "",
        "none_field": None,
    }
    q = build_retrieval_query("C1", "A1", syllabus)
    assert "Pre." in q
    assert "Cont." in q
    assert "Ver." in q


def test_query_skips_empty_fields_for_c5():
    """Empty values for relevant fields are simply skipped."""
    syllabus = {"prerequisites_it": "", "prerequisites_en": "EN only."}
    q = build_retrieval_query("C5", "A1", syllabus)
    assert "EN only" in q
    # The empty IT prerequisites field must not produce a "prerequisites_it: " block.
    assert "prerequisites_it: " not in q


def test_query_no_syllabus_fields_still_returns_criterion_agent():
    q = build_retrieval_query("C3", "A2")
    assert "Criterio C3" in q
    assert "Ruolo A2" in q
    # No "Estratti dal syllabus" block when no fields are passed.
    assert "Estratti dal syllabus" not in q


def test_query_truncates_to_max_chars():
    long_field = "x" * 5000
    syllabus = {"prerequisites_it": long_field}
    q = build_retrieval_query("C5", "A1", syllabus, max_chars=500)
    assert len(q) <= 500
    assert q.endswith("...")


def test_query_truncates_individual_field_to_400_chars():
    """A single field longer than the per-field cap is truncated with '...'."""
    very_long = "y" * 3000
    syllabus = {"prerequisites_it": very_long}
    q = build_retrieval_query("C5", "A1", syllabus, max_chars=10_000)
    # The 'prerequisites_it: ...' block must contain at most ~400 chars of yyyy
    # (truncated representation).
    yyy_count = q.count("y")
    assert yyy_count <= 400


def test_query_rejects_unknown_criterion():
    with pytest.raises(ValueError, match="criterion"):
        build_retrieval_query("C99", "A1")


def test_query_rejects_unknown_agent():
    with pytest.raises(ValueError, match="agent"):
        build_retrieval_query("C1", "A99")


@pytest.mark.parametrize("criterion", sorted(CRITERION_DESCRIPTIONS))
def test_every_core_criterion_has_a_field_list(criterion):
    assert criterion in CRITERION_FIELDS


@pytest.mark.parametrize("agent", sorted(AGENT_ROLES))
def test_every_agent_has_a_role(agent):
    role = AGENT_ROLES[agent]
    assert isinstance(role, str) and len(role) > 0
