"""Tests for the A3 prompt builder.

Mirrors test_a1_prompt / test_a2_prompt: block order, single-source-of-
truth anchors, neutral output schema, dict input. Plus A3-specific
checks: ownership of C6/C7/C8, soft normative wording, the methodological
warning that an introductory descriptive sentence must not by itself
lower the score (carried over from the A2 review).
"""
from __future__ import annotations

from app.evaluation.agents.prompts.a3_prompt import (
    A3_CRITERIA_SPECS,
    A3_OUTPUT_SCHEMA_INSTRUCTIONS,
    A3_RELEVANT_FIELDS,
    A3_SPECIFIC_INSTRUCTIONS,
    build_a3_prompt,
)
from app.evaluation.agents.schemas import AgentInput


def _agent_input(syllabus_data: dict | None = None) -> AgentInput:
    return AgentInput(
        syllabus_seuid="SEUID-A3-TEST",
        syllabus_data=syllabus_data
        or {
            "course_name": "Sample course",
            "has_english": True,
            "course_content_it": "Topic A, Topic B.",
            "assessment_methods_it": "Esame orale.",
        },
        criteria_specs=A3_CRITERIA_SPECS,
        normative_context=[
            {
                "criterion_code": "C6",
                "chunk_id": "lg_unict__3.4.b__0",
                "text": "Modalità di valutazione.",
                "metadata": {"document_id": "lg_unict", "section_ref": "3.4.b"},
                "similarity_score": 0.78,
            }
        ],
    )


def test_a3_prompt_block_order():
    prompt = build_a3_prompt(_agent_input())
    markers = [
        "Sei un esperto di Assicurazione della Qualità",       # BASE
        "AGENTE DI COERENZA DIDATTICO-VALUTATIVA (A3)",        # A3_SPEC
        "SPECIFICHE CRITERI:",                                  # SPECS
        "DATI DEL SYLLABUS DA VALUTARE:",                       # SYLLABUS
        "CONTESTO NORMATIVO RECUPERATO VIA RAG:",               # RAG
        "SCHEMA OUTPUT JSON",                                   # SCHEMA
        "Rispondi ora esclusivamente con il JSON valido",       # closing
    ]
    positions = [prompt.find(m) for m in markers]
    missing = [m for m, p in zip(markers, positions, strict=True) if p < 0]
    assert not missing, f"missing markers: {missing}"
    assert positions == sorted(positions), f"out-of-order blocks: {positions}"


def test_a3_specifies_only_c6_c7_c8():
    """A3 owns C6, C7, C8 — NOT C1/C2/C5 (A1) and NOT C3/C4 (A2)."""
    spec = A3_SPECIFIC_INSTRUCTIONS
    assert "C6" in spec
    assert "C7" in spec
    assert "C8" in spec
    head = spec.split("Avvertenze")[0]
    # Head should mention C6/C7/C8 explicitly but not the criteria of A1 or A2.
    assert "C1" not in head
    assert "C2" not in head
    assert "C3" not in head
    assert "C4" not in head
    assert "C5" not in head


def test_a3_criteria_specs_have_three_levels():
    assert len(A3_CRITERIA_SPECS) == 3
    codes = {s["criterion_code"] for s in A3_CRITERIA_SPECS}
    assert codes == {"C6", "C7", "C8"}
    for spec in A3_CRITERIA_SPECS:
        assert set(spec["anchors"].keys()) == {"0", "1", "2"}
        assert spec["owned_by"] == "A3"


def test_a3_relevant_fields_includes_assessment_and_content_and_schedule():
    """C6/C7 read assessment + content + schedule + sample_questions."""
    expected = {
        "assessment_methods_it", "assessment_methods_en",
        "course_content_it", "course_content_en",
        "schedule_it", "schedule_en",
        "sample_questions_it", "sample_questions_en",
    }
    assert expected.issubset(set(A3_RELEVANT_FIELDS))


def test_a3_relevant_fields_includes_ra_side_for_c8_alignment():
    """C8 needs the RA side: learning_outcomes + dublin_* + teaching_methods."""
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


def test_a3_relevant_fields_excludes_a1_specific_sections():
    """A3 has nothing to do with prerequisites, attendance, references, urls."""
    excluded = {
        "prerequisites_it", "prerequisites_en",
        "attendance_it", "attendance_en",
        "references_it", "references_en",
        "url_it", "url_en",
    }
    assert excluded.isdisjoint(set(A3_RELEVANT_FIELDS))


def test_a3_c7_score0_is_not_about_keyword_lists():
    """C7=0 must NOT punish "elenco di parole chiave" by itself.

    Methodological correction from the review: a keyword list IS still
    content; the right call is C7=1 (poorly organised). Score 0 is for
    cases where content is missing or reduced to a few isolated labels
    insufficient to convey what the course covers.
    """
    c7 = next(s for s in A3_CRITERIA_SPECS if s["criterion_code"] == "C7")
    score_0 = c7["anchors"]["0"].lower()
    score_1 = c7["anchors"]["1"].lower()
    # Score 0 must talk about absent / minimal labels insufficient to convey topics.
    assert "etichette isolate" in score_0 or "non sufficienti" in score_0
    # Score 1 is where the keyword/list pattern lives.
    assert "elenco lineare" in score_1 or "parole chiave" in score_1


def test_a3_c8_score2_anchored_to_textual_evidence():
    """C8=2 must require alignment that is reconstructible from textual evidence.

    'Leggibile' was too permissive — the LLM could reward inferred
    coherence. The corrected wording requires concrete syllabus
    evidence even when alignment is not declared explicitly.
    """
    c8 = next(s for s in A3_CRITERIA_SPECS if s["criterion_code"] == "C8")
    score_2 = c8["anchors"]["2"].lower()
    assert "ricostruibile" in score_2
    assert "evidenze testuali" in score_2


def test_a3_normative_wording_is_soft():
    """LG UniCT recommendations must NOT be phrased as obligations."""
    spec = A3_SPECIFIC_INSTRUCTIONS
    assert "Linee Guida UniCT richiedono" not in spec
    assert "LG UniCT richiedono" not in spec
    # Soft wording must be present in at least one of the C6/C7/C8 anchors at level 2.
    score_2_anchors = [s["anchors"]["2"] for s in A3_CRITERIA_SPECS]
    assert any("raccoman" in a.lower() for a in score_2_anchors), (
        "at least one score-2 anchor must use raccomandano/raccomandato wording"
    )


def test_a3_warns_against_intro_sentence_penalty():
    """Methodological note from the A2 review carried over into A3.

    An introductory descriptive sentence ("lo scopo del corso è...")
    must NOT by itself lower the score: anchors evaluate the actual
    content and alignment that follow.
    """
    spec = A3_SPECIFIC_INSTRUCTIONS
    assert "frase introduttiva" in spec.lower()
    assert "non deve" in spec.lower()


def test_a3_output_schema_is_neutral():
    schema = A3_OUTPUT_SCHEMA_INSTRUCTIONS
    assert "<0 | 1 | 2 | null>" in schema
    assert "PLACEHOLDER" in schema or "non vanno copiati" in schema
    assert "esattamente tre giudizi" in schema


def test_a3_output_schema_forbids_empty_text_evidences():
    """Same defensive instruction as A1/A2: NEVER emit `text=""`."""
    schema = A3_OUTPUT_SCHEMA_INSTRUCTIONS
    assert "NON inserire MAI evidenze" in schema or "evidences\" come lista vuota" in schema


def test_a3_output_schema_disambiguates_from_c2_bilingual():
    """C6/C7/C8 must NOT penalise based on EN absence — that's C2's job."""
    schema = A3_OUTPUT_SCHEMA_INSTRUCTIONS
    assert "C2" in schema
    assert "completezza bilingue" in schema.lower() or "non di tua competenza" in schema.lower()


def test_a3_prompt_includes_three_criteria_specs():
    prompt = build_a3_prompt(_agent_input())
    assert '"criterion_code": "C6"' in prompt
    assert '"criterion_code": "C7"' in prompt
    assert '"criterion_code": "C8"' in prompt


def test_a3_prompt_accepts_dict_input():
    payload = {
        "syllabus_seuid": "X",
        "syllabus_data": {"course_name": "Some Course", "has_english": False},
        "criteria_specs": A3_CRITERIA_SPECS,
        "normative_context": [],
    }
    prompt = build_a3_prompt(payload)
    assert "Sei un esperto" in prompt
    assert "Some Course" in prompt
    assert "AGENTE DI COERENZA DIDATTICO-VALUTATIVA" in prompt
