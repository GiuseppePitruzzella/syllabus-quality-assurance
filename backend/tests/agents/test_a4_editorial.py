"""Tests for the A4 EditorialCareAgent.

Mirrors test_a2_learning_outcomes / test_a3_coherence: focus on field
selection (the A4-specific responsibility) and class metadata. LLM
call paths are covered by tests/agents/test_base_agent.py.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.evaluation.agents.a4_editorial import (
    EditorialCareAgent,
    _postprocess_c9_judgment,
)
from app.evaluation.agents.prompts.a4_prompt import (
    A4_RELEVANT_FIELDS,
    build_a4_prompt,
)
from app.evaluation.agents.schemas import CriterionEvidence, CriterionJudgment


def _full_syllabus() -> SimpleNamespace:
    """Stub syllabus with every A4-relevant field plus several DB internals."""
    return SimpleNamespace(
        # DB internals — must be DROPPED
        id=42,
        cdl_id=3,
        seuid="SEUID-A4",
        # Editorial metadata
        course_code="9999X",
        course_name="Deep Learning",
        course_name_en="Deep Learning",
        module="Modulo 1",
        teacher="Mario Rossi",
        academic_year="2025/2026",
        year_of_study=2,
        url_it="https://example.com/it",   # excluded
        url_en="https://example.com/en",   # excluded
        has_english=True,
        # Italian content
        learning_outcomes_it="RA narrativi.",
        dublin_knowledge_it="Conoscenze.",
        dublin_applying_it="Applicazione.",
        dublin_judgement_it="Giudizio.",
        dublin_communication_it="Comunicazione.",
        dublin_learning_it="Apprendimento.",
        teaching_methods_it="Lezioni frontali.",
        prerequisites_it="Algebra lineare.",
        attendance_it="Frequenza non obbligatoria.",
        course_content_it="Sezione 1 e 2.",
        references_it="Smith J., 'Title', 2020.",
        schedule_it=[{"numero": "1", "argomenti": "Intro"}],
        assessment_methods_it="Prova orale + progetto.",
        sample_questions_it="Domande di esempio.",
        # English content
        learning_outcomes_en="Narrative outcomes.",
        dublin_knowledge_en="Knowledge.",
        dublin_applying_en="Apply.",
        dublin_judgement_en="Judgement.",
        dublin_communication_en="Communication.",
        dublin_learning_en="Learning.",
        teaching_methods_en="Lectures.",
        prerequisites_en="Linear algebra.",
        attendance_en="Attendance optional.",
        course_content_en="Section 1 and 2.",
        references_en="Smith J., 'Title', 2020.",
        schedule_en=[{"numero": "1", "argomenti": "Intro"}],
        assessment_methods_en="Oral exam + project.",
        sample_questions_en="Sample questions.",
    )


# ---------------------------------------------------------------------------
# A4_RELEVANT_FIELDS coverage
# ---------------------------------------------------------------------------


def test_a4_relevant_fields_includes_editorial_metadata():
    expected = {
        "course_code", "course_name", "course_name_en", "module", "teacher",
        "academic_year", "year_of_study", "has_english",
    }
    assert expected.issubset(set(A4_RELEVANT_FIELDS))


def test_a4_relevant_fields_includes_all_italian_content():
    expected = {
        "learning_outcomes_it",
        "dublin_knowledge_it", "dublin_applying_it",
        "dublin_judgement_it", "dublin_communication_it",
        "dublin_learning_it",
        "teaching_methods_it", "prerequisites_it", "attendance_it",
        "course_content_it", "references_it", "schedule_it",
        "assessment_methods_it", "sample_questions_it",
    }
    assert expected.issubset(set(A4_RELEVANT_FIELDS))


def test_a4_relevant_fields_includes_all_english_content():
    expected = {
        "learning_outcomes_en",
        "dublin_knowledge_en", "dublin_applying_en",
        "dublin_judgement_en", "dublin_communication_en",
        "dublin_learning_en",
        "teaching_methods_en", "prerequisites_en", "attendance_en",
        "course_content_en", "references_en", "schedule_en",
        "assessment_methods_en", "sample_questions_en",
    }
    assert expected.issubset(set(A4_RELEVANT_FIELDS))


def test_a4_relevant_fields_excludes_db_internals_and_links():
    excluded = {"id", "cdl_id", "seuid", "url_it", "url_en"}
    assert excluded.isdisjoint(set(A4_RELEVANT_FIELDS))


# ---------------------------------------------------------------------------
# get_relevant_syllabus_fields
# ---------------------------------------------------------------------------


def test_get_relevant_syllabus_fields_drops_db_internals_and_urls():
    agent = EditorialCareAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(_full_syllabus())
    for excluded in ("id", "cdl_id", "seuid", "url_it", "url_en"):
        assert excluded not in out


def test_get_relevant_syllabus_fields_preserves_empty_fields():
    """A4 must see empty fields too — they are still part of editorial layout."""
    agent = EditorialCareAgent(retriever=MagicMock(), llm_client=MagicMock())
    s = _full_syllabus()
    s.references_en = None
    s.attendance_en = ""
    out = agent.get_relevant_syllabus_fields(s)
    assert out["references_en"] is None
    assert out["attendance_en"] == ""


def test_get_relevant_syllabus_fields_returns_full_field_set():
    agent = EditorialCareAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(_full_syllabus())
    assert set(out.keys()) == set(A4_RELEVANT_FIELDS)


def test_get_relevant_syllabus_fields_preserves_schedule_list():
    agent = EditorialCareAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(_full_syllabus())
    assert isinstance(out["schedule_it"], list)
    assert isinstance(out["schedule_en"], list)


def test_get_relevant_syllabus_fields_strips_dublin_leading_dot_artifact():
    """A4 must not see parser-introduced leading dots as editorial defects."""
    agent = EditorialCareAgent(retriever=MagicMock(), llm_client=MagicMock())
    s = _full_syllabus()
    s.dublin_applying_en = "  . Students independently conduct VAPT sessions."
    s.learning_outcomes_en = "  . This non-Dublin field keeps its text."

    out = agent.get_relevant_syllabus_fields(s)

    assert out["dublin_applying_en"] == "Students independently conduct VAPT sessions."
    assert out["learning_outcomes_en"] == "  . This non-Dublin field keeps its text."


def test_get_relevant_syllabus_fields_normalises_quote_artifacts():
    """A4 must not treat mixed quote glyphs as citation defects."""
    agent = EditorialCareAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(
        {
            "schedule_it": '[2] Blocco di slide denominato \u201cDistro Offensive"',
            "references_it": "\u00abMateriale del docente\u00bb",
        }
    )

    assert out["schedule_it"] == '[2] Blocco di slide denominato "Distro Offensive"'
    assert out["references_it"] == '"Materiale del docente"'


def test_get_relevant_syllabus_fields_normalises_literal_line_break_artifacts():
    """A4 must not see literal backslash+n as official page text."""
    agent = EditorialCareAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(
        {"learning_outcomes_en": "Students learn A.\\nThey apply B."}
    )

    assert out["learning_outcomes_en"] == "Students learn A.\nThey apply B."


def test_get_relevant_syllabus_fields_handles_missing_attributes():
    minimal = SimpleNamespace(seuid="x", course_name="X", has_english=False)
    agent = EditorialCareAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(minimal)
    assert out["course_name"] == "X"
    assert out["has_english"] is False
    assert out["references_it"] is None


def test_get_relevant_syllabus_fields_accepts_dict_syllabus():
    agent = EditorialCareAgent(retriever=MagicMock(), llm_client=MagicMock())
    out = agent.get_relevant_syllabus_fields(
        {
            "course_name": "X",
            "has_english": True,
            "references_it": "Smith.",
        }
    )
    assert out["course_name"] == "X"
    assert out["references_it"] == "Smith."
    assert out["learning_outcomes_it"] is None


# ---------------------------------------------------------------------------
# C9 post-processing guard
# ---------------------------------------------------------------------------


def test_postprocess_c9_upgrades_one_typo_plus_mixed_technical_citation():
    judgment = CriterionJudgment(
        criterion_code="C9",
        score=1,
        justification="Refuso localizzato più citazione tecnica mista.",
        confidence="medium",
        evidences=[
            CriterionEvidence(
                text="They also become able to indipendently conduct real VAPT sessions.",
                source_field="learning_outcomes_en",
            ),
            CriterionEvidence(
                text='[1] Chapter 4 "The Drive" e Capitolo 8 "Special Teams"; [2] Online resources',
                source_field="schedule_en",
            ),
        ],
    )

    out = _postprocess_c9_judgment(judgment)

    assert out.score == 2
    assert out.confidence == "medium"
    assert [e.source_field for e in out.evidences] == ["learning_outcomes_en"]
    assert "citazioni tecniche miste" in out.justification


def test_postprocess_c9_keeps_two_real_defects_at_one():
    judgment = CriterionJudgment(
        criterion_code="C9",
        score=1,
        justification="Due difetti editoriali reali in campi distinti.",
        confidence="medium",
        evidences=[
            CriterionEvidence(text="indipendently", source_field="learning_outcomes_en"),
            CriterionEvidence(text="Riferimento bibliografico incompleto: Smith, 2020", source_field="references_it"),
        ],
    )

    out = _postprocess_c9_judgment(judgment)

    assert out.score == 1
    assert len(out.evidences) == 2


# ---------------------------------------------------------------------------
# Class metadata
# ---------------------------------------------------------------------------


def test_editorial_care_agent_advertises_correct_codes():
    agent = EditorialCareAgent(retriever=MagicMock(), llm_client=MagicMock())
    assert agent.agent_code == "A4"
    assert agent.criteria_codes == ["C9"]
    assert agent.prompt_version == "a4_v10"


def test_editorial_care_agent_uses_a4_prompt_builder():
    agent = EditorialCareAgent(retriever=MagicMock(), llm_client=MagicMock())
    assert agent.prompt_builder is build_a4_prompt
