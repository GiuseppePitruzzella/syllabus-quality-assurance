"""Tests for the A1 CompletenessAgent.

Focus on field selection: the agent's only A1-specific responsibility.
LLM call paths are covered by tests/agents/test_base_agent.py with a
fake llm_client.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.evaluation.agents.a1_completeness import (
    A1_RELEVANT_FIELDS,
    CompletenessAgent,
)


def _full_syllabus() -> SimpleNamespace:
    """A syllabus stub with every A1-relevant field plus several irrelevant ones."""
    return SimpleNamespace(
        seuid="SEUID-1",
        course_name="ALGORITMI E COMPLESSITA'",
        has_english=True,
        # Obligatory sections (RA, PR, CN, MV, ED, TD, MS, MF, PRG)
        learning_outcomes_it="Conoscenze e capacità di comprensione...",
        learning_outcomes_en="Knowledge and understanding...",
        dublin_knowledge_it="Strutture dati avanzate.",
        dublin_knowledge_en="Advanced data structures.",
        dublin_applying_it="Applicazione algoritmi.",
        dublin_applying_en="Algorithm application.",
        dublin_judgement_it="",
        dublin_judgement_en=None,
        dublin_communication_it="Comunicazione tecnica.",
        dublin_communication_en="Technical communication.",
        dublin_learning_it="Apprendimento autonomo.",
        dublin_learning_en="Self-learning.",
        prerequisites_it="Programmazione e algebra.",
        prerequisites_en="Programming and algebra.",
        course_content_it="Algoritmi greedy, programmazione dinamica.",
        course_content_en="Greedy algorithms, dynamic programming.",
        assessment_methods_it="Esame scritto + orale.",
        assessment_methods_en="Written + oral exam.",
        sample_questions_it="Esempi di domande.",
        references_it="CLRS, Capitoli 1-26.",
        teaching_methods_it="Lezioni frontali + laboratorio.",
        attendance_it="Frequenza non obbligatoria.",
        schedule_it=[
            {"numero": "1", "argomenti": "Intro", "riferimenti_testi": "Cap. 1"}
        ],
        # Irrelevant for A1 — must be DROPPED
        url_it="https://example.com/it",
        url_en="https://example.com/en",
        sample_questions_en="Sample questions in English.",  # outside C2 perimeter
        references_en="English references.",                 # outside C2 perimeter
        teaching_methods_en="Lectures.",                     # outside C2 perimeter
        attendance_en="Attendance not required.",            # outside C2 perimeter
        schedule_en=[],                                      # outside C2 perimeter
    )


def test_relevant_fields_contains_all_obligatory_it_sections():
    """C1's nine obligatory sections must all be in the field list (IT side)."""
    obligatory_it = {
        "learning_outcomes_it",
        "prerequisites_it",
        "course_content_it",
        "assessment_methods_it",
        "sample_questions_it",
        "references_it",
        "teaching_methods_it",
        "attendance_it",
        "schedule_it",
    }
    assert obligatory_it.issubset(set(A1_RELEVANT_FIELDS))


def test_relevant_fields_contains_c2_perimeter_en_side():
    """C2's bilingual perimeter EN side must be in the field list."""
    c2_en = {
        "course_name",  # title
        "has_english",
        "learning_outcomes_en",
        "course_content_en",
        "assessment_methods_en",
    }
    assert c2_en.issubset(set(A1_RELEVANT_FIELDS))


def test_relevant_fields_excludes_en_outside_c2_perimeter():
    """EN fields outside the C2 bilingual perimeter must NOT be in the field list."""
    excluded = {
        "sample_questions_en",
        "references_en",
        "teaching_methods_en",
        "attendance_en",
        "schedule_en",
        "url_it",
        "url_en",
    }
    assert excluded.isdisjoint(set(A1_RELEVANT_FIELDS))


def test_get_relevant_syllabus_fields_drops_irrelevant():
    """Irrelevant fields on the syllabus instance are dropped from the output."""
    agent = CompletenessAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(_full_syllabus())
    assert "url_it" not in out
    assert "url_en" not in out
    assert "sample_questions_en" not in out
    assert "schedule_en" not in out


def test_get_relevant_syllabus_fields_preserves_empty_obligatory_sections():
    """Empty obligatory sections must be preserved as '' or None.

    Absence of content is information for C1; the LLM must see it.
    """
    agent = CompletenessAgent(retriever=MagicMock(), llm_client=MagicMock())
    s = _full_syllabus()
    s.dublin_judgement_it = ""        # empty string
    s.dublin_judgement_en = None      # null
    out = agent.get_relevant_syllabus_fields(s)
    assert "dublin_judgement_it" in out
    assert out["dublin_judgement_it"] == ""
    assert "dublin_judgement_en" in out
    assert out["dublin_judgement_en"] is None


def test_get_relevant_syllabus_fields_includes_obligatory_section_value():
    agent = CompletenessAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(_full_syllabus())
    assert out["course_name"] == "ALGORITMI E COMPLESSITA'"
    assert out["prerequisites_it"] == "Programmazione e algebra."
    assert out["prerequisites_en"] == "Programming and algebra."
    assert out["assessment_methods_en"] == "Written + oral exam."


def test_get_relevant_syllabus_fields_returns_full_field_set():
    """The output dict has exactly len(A1_RELEVANT_FIELDS) keys."""
    agent = CompletenessAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(_full_syllabus())
    assert set(out.keys()) == set(A1_RELEVANT_FIELDS)


def test_get_relevant_syllabus_fields_handles_missing_attributes():
    """Missing attributes on the syllabus default to None (still kept)."""
    minimal = SimpleNamespace(
        seuid="x",
        course_name="X",
        has_english=False,
    )
    agent = CompletenessAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(minimal)
    assert out["course_name"] == "X"
    assert out["has_english"] is False
    # Missing fields preserved as None — A1 can score them as 0.
    assert out["prerequisites_it"] is None
    assert out["learning_outcomes_en"] is None


def test_get_relevant_syllabus_fields_accepts_dict():
    """The agent must accept a plain dict syllabus too (used in tests)."""
    agent = CompletenessAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(
        {"course_name": "X", "has_english": True, "prerequisites_it": "Pre."}
    )
    assert out["course_name"] == "X"
    assert out["prerequisites_it"] == "Pre."
    assert out["learning_outcomes_it"] is None


def test_completeness_agent_advertises_correct_codes():
    agent = CompletenessAgent(retriever=MagicMock(), llm_client=MagicMock())
    assert agent.agent_code == "A1"
    assert agent.criteria_codes == ["C1", "C2", "C5"]
    assert agent.prompt_version == "a1_v4"


def test_completeness_agent_uses_a1_prompt_builder():
    """The agent wires build_a1_prompt as its prompt_builder."""
    from app.evaluation.agents.prompts.a1_prompt import build_a1_prompt

    agent = CompletenessAgent(retriever=MagicMock(), llm_client=MagicMock())
    assert agent.prompt_builder is build_a1_prompt
