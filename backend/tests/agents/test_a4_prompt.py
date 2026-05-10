"""Tests for the A4 prompt builder.

Mirrors test_a1/a2/a3_prompt: block order, single-source-of-truth
anchor, neutral output schema, dict input. Plus A4-specific checks:
- exactly one criterion (C9) is owned;
- the prompt enforces prudent posture and confidence='medium' default;
- the prompt forbids re-evaluating concerns owned by other criteria
  (C2 bilingual, C3 RA formulation, C5 prerequisites, C6 assessment);
- the field list is the largest of the four agents (whole syllabus).
"""
from __future__ import annotations

from app.evaluation.agents.prompts.a4_prompt import (
    A4_CRITERIA_SPECS,
    A4_OUTPUT_SCHEMA_INSTRUCTIONS,
    A4_RELEVANT_FIELDS,
    A4_SPECIFIC_INSTRUCTIONS,
    build_a4_prompt,
)
from app.evaluation.agents.schemas import AgentInput


def _agent_input(syllabus_data: dict | None = None) -> AgentInput:
    return AgentInput(
        syllabus_seuid="SEUID-A4-TEST",
        syllabus_data=syllabus_data
        or {
            "course_name": "Sample course",
            "has_english": True,
            "course_content_it": "Topic A.\nTopic B.",
            "references_it": "Smith J., 'Title', 2020.",
        },
        criteria_specs=A4_CRITERIA_SPECS,
        normative_context=[
            {
                "criterion_code": "C9",
                "chunk_id": "lg_unict__3.6__0",
                "text": "Cura del campo 'testi' del syllabus.",
                "metadata": {"document_id": "lg_unict", "section_ref": "3.6"},
                "similarity_score": 0.71,
            }
        ],
    )


def test_a4_prompt_block_order():
    prompt = build_a4_prompt(_agent_input())
    markers = [
        "Sei un esperto di Assicurazione della Qualità",   # BASE
        "AGENTE DI CURA EDITORIALE (A4)",                  # A4_SPEC
        "SPECIFICHE CRITERI:",                              # SPECS
        "DATI DEL SYLLABUS DA VALUTARE:",                   # SYLLABUS
        "CONTESTO NORMATIVO RECUPERATO VIA RAG:",           # RAG
        "SCHEMA OUTPUT JSON",                               # SCHEMA
        "Rispondi ora esclusivamente con il JSON valido",   # closing
    ]
    positions = [prompt.find(m) for m in markers]
    missing = [m for m, p in zip(markers, positions, strict=True) if p < 0]
    assert not missing, f"missing markers: {missing}"
    assert positions == sorted(positions), f"out-of-order blocks: {positions}"


def test_a4_specifies_only_c9():
    """A4 owns C9 — and ONLY C9."""
    spec = A4_SPECIFIC_INSTRUCTIONS
    assert "C9" in spec
    head = spec.split("Avvertenze")[0]
    for code in ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"):
        assert f"{code}," not in head and f"{code} " not in head, f"{code} should not be in A4 head"


def test_a4_criteria_specs_exactly_one():
    assert len(A4_CRITERIA_SPECS) == 1
    spec = A4_CRITERIA_SPECS[0]
    assert spec["criterion_code"] == "C9"
    assert spec["owned_by"] == "A4"
    assert set(spec["anchors"].keys()) == {"0", "1", "2"}


def test_a4_anchor_2_uses_soft_normative_wording():
    spec = A4_CRITERIA_SPECS[0]
    score_2 = spec["anchors"]["2"].lower()
    assert "raccoman" in score_2, "C9 score-2 anchor must use raccomandano/raccomandato"


def test_a4_specifies_prudent_posture_and_default_medium_confidence():
    """A4 must instruct the model to default to confidence='medium'.

    C9 is the most interpretive criterion (D006); the prompt's posture
    is intentionally cautious to avoid hallucinated editorial issues.
    """
    spec = A4_SPECIFIC_INSTRUCTIONS
    schema = A4_OUTPUT_SCHEMA_INSTRUCTIONS
    assert "POSTURA PRUDENTE" in spec or "prudente" in spec.lower()
    # Default confidence guidance must be present.
    assert "medium" in spec.lower()
    assert "medium" in schema.lower()
    # Explicit "do not invent issues" instruction.
    assert "non inventare problemi" in spec.lower() or "non penalizzare" in spec.lower()


def test_a4_forbids_double_counting_with_other_criteria():
    """A4 must not penalise issues owned by other agents.

    The exclusion list now covers every other criterion that could
    overlap with editorial care: C2 (bilingual), C3 (RA formulation),
    C4 (Dublin), C5 (prerequisites), C6 (assessment criteria),
    C7 (content organisation), C8 (didactic alignment), and the
    extended E4 (IT/EN semantic equivalence).
    """
    spec = A4_SPECIFIC_INSTRUCTIONS
    schema = A4_OUTPUT_SCHEMA_INSTRUCTIONS
    for code in ("C2", "C3", "C4", "C5", "C6", "C7", "C8", "E4"):
        assert code in spec, f"{code} must appear in A4_SPECIFIC exclusion list"
        assert code in schema, f"{code} must appear in A4 output schema exclusion list"
    assert "NON penalizzare" in spec or "NON valutare" in spec


def test_a4_does_not_use_assessment_strumento_example():
    """The 'assessment cita uno strumento mai introdotto' example was a C8
    case, not C9. Make sure it isn't reintroduced."""
    spec = A4_SPECIFIC_INSTRUCTIONS
    assert "strumento mai introdotto" not in spec.lower()
    assert "strumento mai introdotto nei contenuti" not in spec.lower()


def test_a4_it_en_parallelism_is_macroscopic_only():
    """C9 IT/EN check is restricted to macroscopic editorial parallelism,
    not semantic equivalence (which is E4)."""
    spec = A4_SPECIFIC_INSTRUCTIONS
    assert "macroscopic" in spec.lower() or "parallelismo" in spec.lower()
    # And the spec must explicitly say it is NOT semantic equivalence.
    score_2 = next(s for s in A4_CRITERIA_SPECS if s["criterion_code"] == "C9")["anchors"]["2"]
    assert "non equivalenza semantica" in score_2.lower() or "non equivalenza" in score_2.lower() or "e4" in score_2.lower()


def test_a4_link_wording_avoids_unverifiable_broken_link_claim():
    """The earlier 'link rotti' wording could push the LLM to invent
    broken links it cannot verify. Replace with 'link/riferimenti
    visibilmente malformati nel testo del syllabus'.
    """
    spec = A4_SPECIFIC_INSTRUCTIONS.lower()
    # No raw 'link rotti' claim.
    assert "link rotti" not in spec
    # Some softer wording about malformed links/references in the syllabus text.
    assert "malformati" in spec


def test_a4_relevant_fields_covers_whole_syllabus():
    """A4 reads the syllabus as a unit: most fields are present."""
    must_include = {
        "course_code", "course_name", "module", "teacher",
        "academic_year", "year_of_study", "has_english",
        "learning_outcomes_it", "learning_outcomes_en",
        "dublin_knowledge_it", "dublin_knowledge_en",
        "dublin_applying_it", "dublin_applying_en",
        "dublin_judgement_it", "dublin_judgement_en",
        "dublin_communication_it", "dublin_communication_en",
        "dublin_learning_it", "dublin_learning_en",
        "teaching_methods_it", "teaching_methods_en",
        "prerequisites_it", "prerequisites_en",
        "attendance_it", "attendance_en",
        "course_content_it", "course_content_en",
        "references_it", "references_en",
        "schedule_it", "schedule_en",
        "assessment_methods_it", "assessment_methods_en",
        "sample_questions_it", "sample_questions_en",
    }
    assert must_include.issubset(set(A4_RELEVANT_FIELDS))


def test_a4_relevant_fields_excludes_db_internals_and_links():
    excluded = {"id", "cdl_id", "seuid", "url_it", "url_en"}
    assert excluded.isdisjoint(set(A4_RELEVANT_FIELDS))


def test_a4_output_schema_is_neutral():
    schema = A4_OUTPUT_SCHEMA_INSTRUCTIONS
    assert "<0 | 1 | 2 | null>" in schema
    assert "PLACEHOLDER" in schema or "non vanno copiati" in schema
    assert "esattamente un giudizio" in schema


def test_a4_output_schema_forbids_empty_text_evidences():
    """Same defensive instruction as the other agents: never emit text=''."""
    schema = A4_OUTPUT_SCHEMA_INSTRUCTIONS
    assert "NON inserire MAI evidenze" in schema or "evidences\" come lista vuota" in schema


def test_a4_output_schema_repeats_cross_criterion_disambiguation():
    """The schema block must restate the don't-double-count rule."""
    schema = A4_OUTPUT_SCHEMA_INSTRUCTIONS
    assert "C2" in schema
    assert "C3" in schema
    assert "C6" in schema


def test_a4_includes_examples_of_observable_editorial_issues():
    """The prompt should list concrete examples of what 'cura editoriale' looks like."""
    spec = A4_SPECIFIC_INSTRUCTIONS
    must_mention_some = [
        "refusi",
        "incongruenze",
        "riferimenti bibliografici",
        "formattazione",
    ]
    assert all(t in spec.lower() for t in must_mention_some), (
        "A4 spec must mention typos, internal inconsistencies, references and formatting"
    )


def test_a4_prompt_includes_one_criterion_spec():
    prompt = build_a4_prompt(_agent_input())
    assert '"criterion_code": "C9"' in prompt
    # And no spurious C1..C8 keys in the SPECS block.
    for code in ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"):
        assert f'"criterion_code": "{code}"' not in prompt


def test_a4_anchor_0_is_for_grave_diffuse_systematic_defects():
    """C9=0 must be reserved for grave, diffuse and systematic defects.

    The diagnostic A4 v1 run scored 4/4 syllabi as C9=0 because the
    anchor was too permissive: any cluster of typos plus formatting
    residues triggered score 0. The new wording requires the defects
    to be GRAVE, DIFFUSI and SISTEMATICI before falling to 0.
    """
    c9 = next(s for s in A4_CRITERIA_SPECS if s["criterion_code"] == "C9")
    score_0 = c9["anchors"]["0"].lower()
    assert "gravi" in score_0
    assert "diffusi" in score_0
    assert "sistematici" in score_0
    # And explicit exclusion of "refusi sparsi alone -> score 0".
    assert "non va assegnato" in score_0 or "non va a 0" in score_0


def test_a4_anchor_1_is_default_for_isolated_residues():
    """C9=1 is the default for typical real syllabi: scattered typos and
    localised formatting residues."""
    c9 = next(s for s in A4_CRITERIA_SPECS if s["criterion_code"] == "C9")
    score_1 = c9["anchors"]["1"].lower()
    assert "default" in score_1 or "maggior parte" in score_1


def test_a4_default_confidence_is_explicitly_medium():
    """Confidence guidance must default to medium; high requires evidence
    that is numerous, concordant, distributed and clearly grave."""
    spec = A4_SPECIFIC_INSTRUCTIONS.lower()
    assert "default" in spec
    assert "medium" in spec
    # The 'high' bar must be explicit in the spec.
    assert "numerosi" in spec or "concordanti" in spec or "distribuiti" in spec


def test_a4_anti_english_exclusion_is_severe():
    """A4 must NOT cite English absence/partiality anywhere in the judgment.

    Diagnostic A4 v1 caught: "la versione inglese è gravemente incompleta
    in sezioni chiave" — that is C2 (A1), not C9. The new spec enforces
    a hard ban with explicit "RIGORE SULL'ESCLUSIONE C2" wording.
    """
    spec = A4_SPECIFIC_INSTRUCTIONS
    schema = A4_OUTPUT_SCHEMA_INSTRUCTIONS
    # The severe wording must appear in the spec block.
    assert "RIGORE SULL'ESCLUSIONE C2" in spec or "rigore" in spec.lower()
    # Both blocks must explicitly forbid citing English absence.
    forbid_phrases = [
        "non citare in evidences né in justification",
        "non citare l'assenza",
        "non penalizzare un campo en per il fatto di essere vuoto",
    ]
    assert any(p in spec.lower() for p in forbid_phrases)
    assert "completezza bilingue è esclusivamente di c2" in schema.lower() or \
        "non citare l'assenza" in schema.lower()


def test_a4_caps_evidences_at_five():
    """Evidence inflation triggered MAX_TOKENS in the diagnostic run.
    a4_v2 caps evidences at 5 representative items."""
    spec = A4_SPECIFIC_INSTRUCTIONS.lower()
    schema = A4_OUTPUT_SCHEMA_INSTRUCTIONS.lower()
    assert "massimo 5 evidences" in spec or "max 5" in spec or "limite evidences" in spec
    assert "massimo 5 evidences" in schema or "max 5" in schema or "5 evidences" in schema


def test_a4_prompt_accepts_dict_input():
    payload = {
        "syllabus_seuid": "X",
        "syllabus_data": {"course_name": "Some Course", "has_english": False},
        "criteria_specs": A4_CRITERIA_SPECS,
        "normative_context": [],
    }
    prompt = build_a4_prompt(payload)
    assert "Sei un esperto" in prompt
    assert "Some Course" in prompt
    assert "AGENTE DI CURA EDITORIALE" in prompt
