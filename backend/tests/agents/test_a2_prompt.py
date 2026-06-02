"""Tests for the A2 prompt builder.

Mirrors test_a1_prompt structure: block order, single-source-of-truth
anchors, neutral output schema, dict input. Plus A2-specific checks:
- C3/C4 are the owned criteria (NOT C1/C2/C5);
- the prompt warns that teaching_methods is light context, not
  primary evidence;
- the wording on the LG UniCT is methodologically soft (no
  'richiedono' for what is actually a recommendation).
"""
from __future__ import annotations

from app.evaluation.agents.prompts.a2_prompt import (
    A2_CRITERIA_SPECS,
    A2_OUTPUT_SCHEMA_INSTRUCTIONS,
    A2_RELEVANT_FIELDS,
    A2_SPECIFIC_INSTRUCTIONS,
    build_a2_prompt,
)
from app.evaluation.agents.schemas import AgentInput


def _agent_input(syllabus_data: dict | None = None) -> AgentInput:
    return AgentInput(
        syllabus_seuid="SEUID-A2-TEST",
        syllabus_data=syllabus_data
        or {
            "course_name": "Sample course",
            "has_english": True,
            "learning_outcomes_it": "Lo studente acquisirà conoscenze.",
            "dublin_knowledge_it": "Conoscenze su X.",
        },
        criteria_specs=A2_CRITERIA_SPECS,
        normative_context=[
            {
                "criterion_code": "C3",
                "chunk_id": "lg_unict__3.1__0",
                "text": "Formulazione dei risultati di apprendimento attesi.",
                "metadata": {"document_id": "lg_unict", "section_ref": "3.1"},
                "similarity_score": 0.80,
            }
        ],
    )


def test_a2_prompt_block_order():
    prompt = build_a2_prompt(_agent_input())
    markers = [
        "Sei un esperto di Assicurazione della Qualità",   # BASE
        "AGENTE PEDAGOGICO (A2)",                          # A2_SPEC
        "SPECIFICHE CRITERI:",                             # SPECS
        "DATI DEL SYLLABUS DA VALUTARE:",                  # SYLLABUS
        "CONTESTO NORMATIVO RECUPERATO VIA RAG:",          # RAG
        "SCHEMA OUTPUT JSON",                              # SCHEMA
        "Rispondi ora esclusivamente con il JSON valido",  # closing
    ]
    positions = [prompt.find(m) for m in markers]
    missing = [m for m, p in zip(markers, positions, strict=True) if p < 0]
    assert not missing, f"missing markers: {missing}"
    assert positions == sorted(positions), f"out-of-order blocks: {positions}"


def test_a2_specifies_only_c3_and_c4():
    """A2 owns C3 and C4 — NOT C1, C2 or C5 (those belong to A1)."""
    spec = A2_SPECIFIC_INSTRUCTIONS
    assert "C3" in spec
    assert "C4" in spec
    # Must NOT mix in A1 criteria
    assert "C1," not in spec and "C1 " not in spec.split("Avvertenze")[0]
    assert "C5" not in spec.split("Avvertenze specifiche")[0]


def test_a2_criteria_specs_have_three_levels():
    assert len(A2_CRITERIA_SPECS) == 2
    codes = {s["criterion_code"] for s in A2_CRITERIA_SPECS}
    assert codes == {"C3", "C4"}
    for spec in A2_CRITERIA_SPECS:
        assert set(spec["anchors"].keys()) == {"0", "1", "2"}
        assert spec["owned_by"] == "A2"


def test_a2_anchors_describe_dublin_articulation():
    """C4 must reference 'Descrittori di Dublino' / dublin_* explicitly."""
    c4 = next(s for s in A2_CRITERIA_SPECS if s["criterion_code"] == "C4")
    assert "Descrittori di Dublino" in c4["name"] or "Dublino" in c4["anchors"]["0"]
    assert "specifici" in c4["anchors"]["2"].lower() or "differenziati" in c4["anchors"]["2"].lower()


def test_a2_relevant_fields_contains_dublin_descriptors():
    expected = {
        "dublin_knowledge_it", "dublin_knowledge_en",
        "dublin_applying_it", "dublin_applying_en",
        "dublin_judgement_it", "dublin_judgement_en",
        "dublin_communication_it", "dublin_communication_en",
        "dublin_learning_it", "dublin_learning_en",
    }
    assert expected.issubset(set(A2_RELEVANT_FIELDS))


def test_a2_relevant_fields_contains_learning_outcomes():
    assert "learning_outcomes_it" in A2_RELEVANT_FIELDS
    assert "learning_outcomes_en" in A2_RELEVANT_FIELDS


def test_a2_relevant_fields_includes_teaching_methods_as_light_context():
    """teaching_methods_* is included BUT must be flagged in the prompt
    as light context, not primary evidence."""
    assert "teaching_methods_it" in A2_RELEVANT_FIELDS
    assert "teaching_methods_en" in A2_RELEVANT_FIELDS
    spec = A2_SPECIFIC_INSTRUCTIONS
    assert "teaching_methods" in spec.lower()
    assert "contesto leggero" in spec.lower() or "non citare \"teaching_methods" in spec.lower() or "non.*primaria" in spec.lower()


def test_a2_relevant_fields_excludes_unrelated_sections():
    """A2 does not need prerequisites, references, schedule, attendance, etc."""
    excluded = {
        "prerequisites_it", "prerequisites_en",
        "course_content_it", "course_content_en",
        "assessment_methods_it", "assessment_methods_en",
        "sample_questions_it", "sample_questions_en",
        "references_it", "references_en",
        "attendance_it", "attendance_en",
        "schedule_it", "schedule_en",
    }
    assert excluded.isdisjoint(set(A2_RELEVANT_FIELDS))


def test_a2_normative_wording_is_soft():
    """LG UniCT recommendations must NOT be phrased as obligations.

    Methodological correction applied uniformly across A1 and A2:
    the LG UniCT use 'opportuno' / 'raccomandato'. The narrative must
    reflect that for any criterion that depends on a recommendation
    rather than a binding rule.
    """
    spec = A2_SPECIFIC_INSTRUCTIONS
    # 'richiedono' should NOT appear as the verb the LG UniCT use.
    # (It can appear in other contexts, but never directly attached
    # to "Linee Guida UniCT".)
    assert "Linee Guida UniCT richiedono" not in spec
    assert "LG UniCT richiedono" not in spec
    # Soft wording must be present for the C4 anchor 2.
    c4 = next(s for s in A2_CRITERIA_SPECS if s["criterion_code"] == "C4")
    assert "raccoman" in c4["anchors"]["2"].lower()


def test_a2_output_schema_is_neutral():
    schema = A2_OUTPUT_SCHEMA_INSTRUCTIONS
    assert "<0 | 1 | 2 | null>" in schema
    assert "PLACEHOLDER" in schema or "non vanno copiati" in schema
    assert "esattamente due giudizi" in schema


def test_a2_output_schema_forbids_empty_text_evidences():
    """Same defensive instruction as A1: NEVER emit `text=""`."""
    schema = A2_OUTPUT_SCHEMA_INSTRUCTIONS
    assert "NON inserire MAI evidenze" in schema or "evidences\" come lista vuota" in schema


def test_a2_output_schema_disambiguates_c4_from_c2():
    """C4 (Dublin articulation) must NOT be confused with C2 (bilingual coverage).

    The prompt must explicitly say that the bilingual presence of the
    Dublin descriptors does NOT influence C4: that is C2's job and C2
    is owned by A1.
    """
    schema = A2_OUTPUT_SCHEMA_INSTRUCTIONS
    assert "C2" in schema
    assert "indipendentemente dalla lingua" in schema or "non di tua competenza" in schema


def test_a2_prompt_accepts_dict_input():
    payload = {
        "syllabus_seuid": "X",
        "syllabus_data": {"course_name": "Some Course", "has_english": False},
        "criteria_specs": A2_CRITERIA_SPECS,
        "normative_context": [],
    }
    prompt = build_a2_prompt(payload)
    assert "Sei un esperto" in prompt
    assert "Some Course" in prompt
    assert "AGENTE PEDAGOGICO" in prompt
