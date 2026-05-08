"""Tests for the A3 DidacticConsistencyAgent.

Mirrors test_a2_learning_outcomes: focus on field selection (the
agent-specific responsibility) and class metadata. LLM call paths are
covered by tests/agents/test_base_agent.py.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.evaluation.agents.a3_coherence import DidacticConsistencyAgent
from app.evaluation.agents.prompts.a3_prompt import (
    A3_RELEVANT_FIELDS,
    build_a3_prompt,
)


def _full_syllabus() -> SimpleNamespace:
    """Syllabus stub with every A3-relevant field plus several A3-irrelevant ones."""
    return SimpleNamespace(
        seuid="SEUID-A3",
        course_name="Deep Learning",
        has_english=True,
        # RA side (needed for C8)
        learning_outcomes_it="Risultati narrativi.",
        learning_outcomes_en="Narrative outcomes.",
        dublin_knowledge_it="Conoscenze.",
        dublin_knowledge_en="Knowledge.",
        dublin_applying_it="Applicazione.",
        dublin_applying_en="Apply.",
        dublin_judgement_it="Giudizio.",
        dublin_judgement_en="Judgement.",
        dublin_communication_it="Comunicazione.",
        dublin_communication_en="Communication.",
        dublin_learning_it="Apprendimento autonomo.",
        dublin_learning_en="Self-learning.",
        # Contenuti / programma
        course_content_it="Sezione 1: introduzione. Sezione 2: reti.",
        course_content_en="Section 1: intro. Section 2: nets.",
        schedule_it=[{"numero": "1", "argomenti": "Intro"}],
        schedule_en=[{"numero": "1", "argomenti": "Intro"}],
        # Metodi didattici
        teaching_methods_it="Lezioni frontali + lab.",
        teaching_methods_en="Lectures + lab.",
        # Modalità di verifica
        assessment_methods_it="Esame orale + progetto.",
        assessment_methods_en="Oral exam + project.",
        sample_questions_it="Domande di esempio.",
        sample_questions_en="Sample questions.",
        # A3-IRRELEVANT — must be DROPPED
        prerequisites_it="Algebra lineare.",
        prerequisites_en="Linear algebra.",
        attendance_it="Frequenza non obbligatoria.",
        attendance_en="Attendance optional.",
        references_it="CLRS.",
        references_en="CLRS.",
        url_it="https://example.com/it",
        url_en="https://example.com/en",
    )


# ---------------------------------------------------------------------------
# A3_RELEVANT_FIELDS coverage
# ---------------------------------------------------------------------------


def test_a3_relevant_fields_covers_assessment_content_schedule():
    expected = {
        "assessment_methods_it", "assessment_methods_en",
        "sample_questions_it", "sample_questions_en",
        "course_content_it", "course_content_en",
        "schedule_it", "schedule_en",
    }
    assert expected.issubset(set(A3_RELEVANT_FIELDS))


def test_a3_relevant_fields_covers_ra_side_for_c8():
    """C8 needs all the RA evidence: learning_outcomes + dublin_*_it/en."""
    expected = {
        "learning_outcomes_it", "learning_outcomes_en",
        "dublin_knowledge_it", "dublin_knowledge_en",
        "dublin_applying_it", "dublin_applying_en",
        "dublin_judgement_it", "dublin_judgement_en",
        "dublin_communication_it", "dublin_communication_en",
        "dublin_learning_it", "dublin_learning_en",
        "teaching_methods_it", "teaching_methods_en",
    }
    assert expected.issubset(set(A3_RELEVANT_FIELDS))


def test_a3_relevant_fields_excludes_a1_owned_sections():
    excluded = {
        "prerequisites_it", "prerequisites_en",
        "attendance_it", "attendance_en",
        "references_it", "references_en",
        "url_it", "url_en",
    }
    assert excluded.isdisjoint(set(A3_RELEVANT_FIELDS))


# ---------------------------------------------------------------------------
# get_relevant_syllabus_fields
# ---------------------------------------------------------------------------


def test_get_relevant_syllabus_fields_drops_irrelevant():
    agent = DidacticConsistencyAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(_full_syllabus())
    assert "prerequisites_it" not in out
    assert "attendance_it" not in out
    assert "references_en" not in out
    assert "url_it" not in out


def test_get_relevant_syllabus_fields_preserves_empty_assessment():
    """An absent assessment_methods is exactly what C6/C8 need to see."""
    agent = DidacticConsistencyAgent(retriever=MagicMock(), llm_client=MagicMock())
    s = _full_syllabus()
    s.assessment_methods_it = ""
    s.assessment_methods_en = None
    out = agent.get_relevant_syllabus_fields(s)
    assert "assessment_methods_it" in out
    assert out["assessment_methods_it"] == ""
    assert out["assessment_methods_en"] is None


def test_get_relevant_syllabus_fields_returns_full_field_set():
    agent = DidacticConsistencyAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(_full_syllabus())
    assert set(out.keys()) == set(A3_RELEVANT_FIELDS)


def test_get_relevant_syllabus_fields_preserves_schedule_list():
    """schedule_* is a JSON list — must survive coercion intact."""
    agent = DidacticConsistencyAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(_full_syllabus())
    assert isinstance(out["schedule_it"], list)
    assert out["schedule_it"][0]["numero"] == "1"


def test_get_relevant_syllabus_fields_handles_missing_attributes():
    minimal = SimpleNamespace(seuid="x", course_name="X", has_english=False)
    agent = DidacticConsistencyAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(minimal)
    assert out["course_name"] == "X"
    assert out["has_english"] is False
    assert out["assessment_methods_it"] is None
    assert out["course_content_en"] is None


def test_get_relevant_syllabus_fields_accepts_dict_syllabus():
    agent = DidacticConsistencyAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(
        {
            "course_name": "X",
            "has_english": True,
            "assessment_methods_it": "Esame.",
        }
    )
    assert out["course_name"] == "X"
    assert out["assessment_methods_it"] == "Esame."
    assert out["course_content_it"] is None


# ---------------------------------------------------------------------------
# Class metadata
# ---------------------------------------------------------------------------


def test_didactic_consistency_agent_advertises_correct_codes():
    agent = DidacticConsistencyAgent(retriever=MagicMock(), llm_client=MagicMock())
    assert agent.agent_code == "A3"
    assert agent.criteria_codes == ["C6", "C7", "C8"]
    assert agent.prompt_version == "a3_v1"


def test_didactic_consistency_agent_uses_a3_prompt_builder():
    agent = DidacticConsistencyAgent(retriever=MagicMock(), llm_client=MagicMock())
    assert agent.prompt_builder is build_a3_prompt
