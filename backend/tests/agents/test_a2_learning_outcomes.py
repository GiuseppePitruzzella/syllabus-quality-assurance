"""Tests for the A2 PedagogicalAgent.

Focus on field selection: A2's only A2-specific responsibility. LLM call
paths are exercised by tests/agents/test_base_agent.py with a fake
llm_client; here we verify that A2_RELEVANT_FIELDS is correctly applied
to the syllabus and that the agent advertises the expected metadata.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.evaluation.agents.a2_learning_outcomes import PedagogicalAgent
from app.evaluation.agents.prompts.a2_prompt import (
    A2_RELEVANT_FIELDS,
    build_a2_prompt,
)


def _full_syllabus() -> SimpleNamespace:
    """A syllabus stub with every A2-relevant field plus several A2-irrelevant ones."""
    return SimpleNamespace(
        seuid="SEUID-A2",
        course_name="Deep Learning",
        has_english=True,
        learning_outcomes_it="Risultati di apprendimento attesi narrativi.",
        learning_outcomes_en="Expected learning outcomes (narrative).",
        dublin_knowledge_it="Conoscenze su modelli avanzati di Deep Learning.",
        dublin_knowledge_en="Knowledge of advanced Deep Learning models.",
        dublin_applying_it="Applicazione di reti neurali profonde a problemi reali.",
        dublin_applying_en="Application of deep networks to real problems.",
        dublin_judgement_it="",
        dublin_judgement_en=None,
        dublin_communication_it="Capacità di presentare risultati in forma scritta.",
        dublin_communication_en="Ability to present results in written form.",
        dublin_learning_it="Apprendimento autonomo della letteratura recente.",
        dublin_learning_en="Self-learning of recent literature.",
        teaching_methods_it="Lezioni frontali + laboratorio.",
        teaching_methods_en="Lectures + lab.",
        # A2-IRRELEVANT — must be DROPPED
        prerequisites_it="Algebra lineare e programmazione.",
        prerequisites_en="Linear algebra and programming.",
        course_content_it="Reti neurali, transformer, ottimizzazione.",
        course_content_en="Neural networks, transformers, optimization.",
        assessment_methods_it="Esame orale + progetto.",
        assessment_methods_en="Oral exam + project.",
        sample_questions_it="Domande di esempio.",
        references_it="CLRS + slides.",
        attendance_it="Frequenza non obbligatoria.",
        schedule_it=[{"numero": "1", "argomenti": "Intro"}],
        url_it="https://example.com/it",
        url_en="https://example.com/en",
    )


# ---------------------------------------------------------------------------
# A2_RELEVANT_FIELDS coverage
# ---------------------------------------------------------------------------


def test_a2_relevant_fields_includes_all_dublin_descriptors_both_languages():
    expected = {
        "dublin_knowledge_it", "dublin_knowledge_en",
        "dublin_applying_it", "dublin_applying_en",
        "dublin_judgement_it", "dublin_judgement_en",
        "dublin_communication_it", "dublin_communication_en",
        "dublin_learning_it", "dublin_learning_en",
    }
    assert expected.issubset(set(A2_RELEVANT_FIELDS))


def test_a2_relevant_fields_includes_learning_outcomes_both_languages():
    assert "learning_outcomes_it" in A2_RELEVANT_FIELDS
    assert "learning_outcomes_en" in A2_RELEVANT_FIELDS


def test_a2_relevant_fields_includes_course_name_and_has_english():
    assert "course_name" in A2_RELEVANT_FIELDS
    assert "has_english" in A2_RELEVANT_FIELDS


def test_a2_relevant_fields_includes_teaching_methods_as_light_context():
    assert "teaching_methods_it" in A2_RELEVANT_FIELDS
    assert "teaching_methods_en" in A2_RELEVANT_FIELDS


def test_a2_relevant_fields_excludes_other_sections():
    """A2 has nothing to do with prerequisites, content, assessment, etc."""
    excluded = {
        "prerequisites_it", "prerequisites_en",
        "course_content_it", "course_content_en",
        "assessment_methods_it", "assessment_methods_en",
        "sample_questions_it", "sample_questions_en",
        "references_it", "references_en",
        "attendance_it", "attendance_en",
        "schedule_it", "schedule_en",
        "url_it", "url_en",
    }
    assert excluded.isdisjoint(set(A2_RELEVANT_FIELDS))


# ---------------------------------------------------------------------------
# get_relevant_syllabus_fields
# ---------------------------------------------------------------------------


def test_get_relevant_syllabus_fields_drops_irrelevant():
    agent = PedagogicalAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(_full_syllabus())
    assert "prerequisites_it" not in out
    assert "course_content_en" not in out
    assert "schedule_it" not in out
    assert "url_it" not in out


def test_get_relevant_syllabus_fields_preserves_empty_dublin_descriptor():
    """An absent Dublin descriptor field must remain in the dict.

    Score=0/1 on C4 hinges on which descriptors are missing or shallow,
    so the LLM needs to see the empty/null value, not have it dropped.
    """
    agent = PedagogicalAgent(retriever=MagicMock(), llm_client=MagicMock())
    s = _full_syllabus()
    s.dublin_judgement_it = ""
    s.dublin_judgement_en = None
    out = agent.get_relevant_syllabus_fields(s)
    assert "dublin_judgement_it" in out
    assert out["dublin_judgement_it"] == ""
    assert "dublin_judgement_en" in out
    assert out["dublin_judgement_en"] is None


def test_get_relevant_syllabus_fields_preserves_full_field_set():
    agent = PedagogicalAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(_full_syllabus())
    assert set(out.keys()) == set(A2_RELEVANT_FIELDS)


def test_get_relevant_syllabus_fields_handles_missing_attributes():
    minimal = SimpleNamespace(seuid="x", course_name="X", has_english=False)
    agent = PedagogicalAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(minimal)
    assert out["course_name"] == "X"
    assert out["has_english"] is False
    # Missing fields default to None, not dropped.
    assert out["learning_outcomes_it"] is None
    assert out["dublin_knowledge_en"] is None


def test_get_relevant_syllabus_fields_accepts_dict_syllabus():
    agent = PedagogicalAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(
        {
            "course_name": "X",
            "has_english": True,
            "dublin_knowledge_it": "Conoscenze.",
        }
    )
    assert out["course_name"] == "X"
    assert out["dublin_knowledge_it"] == "Conoscenze."
    assert out["learning_outcomes_it"] is None


# ---------------------------------------------------------------------------
# Class metadata
# ---------------------------------------------------------------------------


def test_pedagogical_agent_advertises_correct_codes():
    agent = PedagogicalAgent(retriever=MagicMock(), llm_client=MagicMock())
    assert agent.agent_code == "A2"
    assert agent.criteria_codes == ["C3", "C4"]
    assert agent.prompt_version == "a2_v1"


def test_pedagogical_agent_uses_a2_prompt_builder():
    agent = PedagogicalAgent(retriever=MagicMock(), llm_client=MagicMock())
    assert agent.prompt_builder is build_a2_prompt
