from app.evaluation.agents.prompts.a1_prompt import build_a1_prompt
from app.evaluation.agents.schemas import AgentInput


def _agent_input(syllabus_data):
    return AgentInput(
        syllabus_data=syllabus_data,
        criteria_specs=[{"criterion_code": "C2", "description": "Completezza bilingue"}],
        normative_context=[],
        syllabus_seuid="TEST-SEUID",
    )


def test_prompt_contains_precheck_block_and_suggestion_full_coverage():
    syllabus = {
        "course_name": "Visione",
        "course_name_en": "Computer Vision",
        "learning_outcomes_en": "The student will design CV pipelines and evaluate models.",
        "course_content_en": "Convolutional networks, detection, segmentation, transformers.",
        "assessment_methods_en": "Written exam plus a graded project with oral discussion.",
    }
    prompt = build_a1_prompt(_agent_input(syllabus))
    assert "PRE-CHECK DETERMINISTICO COPERTURA INGLESE" in prompt
    assert "english_coverage" in prompt
    assert "suggested_c2" in prompt
    assert '"suggested_c2": 2' in prompt


def test_prompt_suggestion_title_only_is_zero():
    syllabus = {"course_name": "IoT", "course_name_en": "Internet of Things"}
    prompt = build_a1_prompt(_agent_input(syllabus))
    assert '"suggested_c2": 0' in prompt


def test_prompt_c2_guidance_separates_presence_from_quality():
    prompt = build_a1_prompt(_agent_input({"course_name": "X"}))
    # the always-injected A1 instructions must carry the deviation + no-quality rule
    assert "suggested_c2" in prompt.lower() or "suggerito" in prompt.lower()
    assert "non bloccante" in prompt.lower()
