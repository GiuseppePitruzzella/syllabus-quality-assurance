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
            "course_name_en": "Sample course",
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


def test_a4_anchor_2_tolerates_parser_artifacts_when_not_real_defects():
    spec = A4_CRITERIA_SPECS[0]
    score_2 = spec["anchors"]["2"].lower()
    assert "artefatti di parsing" in score_2
    assert "non bastano ad abbassare il punteggio" in score_2
    assert "-->" in score_2


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
        "course_code", "course_name", "course_name_en", "module", "teacher",
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


def test_a4_anchor_1_requires_real_observable_defects_not_parser_artifacts():
    """C9=1 requires actual editorial defects after the a4_v10 recalibration."""
    c9 = next(s for s in A4_CRITERIA_SPECS if s["criterion_code"] == "C9")
    score_1 = c9["anchors"]["1"].lower()
    assert "reali e osservabili" in score_1
    assert "almeno due difetti concreti" in score_1
    assert "indipendenti" in score_1
    assert "campi distinti" in score_1
    assert "non assegnare 1" in score_1
    assert "artefatti di scraping/parsing" in score_1
    assert "dublin_* frammentari" in score_1
    assert "inglese comprensibile" in score_1
    assert "stile dei riferimenti" in score_1


def test_a4_anchor_1_does_not_count_duplicated_typos_as_independent_defects():
    """A repeated typo in duplicated/derived fields is still one defect.

    Regression for VAPT: the same "indipendently" typo appeared in
    learning_outcomes_en and dublin_applying_en and was incorrectly
    treated as part of a multi-field defect cluster.
    """
    c9 = next(s for s in A4_CRITERIA_SPECS if s["criterion_code"] == "C9")
    score_1 = c9["anchors"]["1"].lower()
    score_2 = c9["anchors"]["2"].lower()
    spec = A4_SPECIFIC_INSTRUCTIONS.lower()
    schema = A4_OUTPUT_SCHEMA_INSTRUCTIONS.lower()

    assert "ripetizione dello stesso refuso" in score_1
    assert "campi duplicati/derivati" in score_1
    assert "un solo difetto minore o localizzato" in score_1
    assert "un refuso localizzato più una citazione tecnica mista" in score_1
    assert "non costituiscono due difetti indipendenti" in score_1
    assert "anche se ripetuto in campi duplicati o derivati" in score_2
    assert "conta come un solo difetto" in spec
    assert "assegna c9=2" in spec
    assert "occorrenze ripetute dello stesso refuso" in schema


def test_a4_prompt_tolerates_intelligible_mixed_language_technical_citations():
    """Mixed IT/EN technical citations are not automatically editorial defects.

    Regression for VAPT: lines such as "Chapter 4 ... e Capitolo 8"
    and technical titles such as "Distro Offensive" are understandable
    syllabus content, not standalone C9 defects.
    """
    c9 = next(s for s in A4_CRITERIA_SPECS if s["criterion_code"] == "C9")
    score_1 = c9["anchors"]["1"].lower()
    score_2 = c9["anchors"]["2"].lower()
    spec = A4_SPECIFIC_INSTRUCTIONS.lower()
    schema = A4_OUTPUT_SCHEMA_INSTRUCTIONS.lower()

    assert "titoli tecnici/citazioni bibliografiche" in score_1
    assert "mescolano parole italiane e inglesi" in score_1
    assert "titoli tecnici" in score_2
    assert "citazioni bibliografiche" in score_2
    assert "riga bibliografica o di programmazione" in spec
    assert "normali in syllabus bilingui/tecnici" in schema
    assert "non citarli nelle evidences" in schema
    assert "non sono evidenze valide per abbassare c9" in schema
    assert "non usare come difetti c9 titoli tecnici" in schema


def test_a4_default_confidence_is_explicitly_medium():
    """Confidence guidance must default to medium; high requires evidence
    that is numerous, concordant, distributed and clearly grave."""
    spec = A4_SPECIFIC_INSTRUCTIONS.lower()
    assert "default" in spec
    assert "medium" in spec
    # The 'high' bar must be explicit in the spec.
    assert "numerosi" in spec or "concordanti" in spec or "distribuiti" in spec


def test_a4_prompt_does_not_default_toward_c9_1():
    """a4_v10 must be neutral on the 1/2 boundary.

    The LM-18 validation showed C9 collapsing to 1 in almost every latest
    run. The prompt now explicitly allows score=2 when no concrete,
    text-attributable editorial defects are found.
    """
    spec = A4_SPECIFIC_INSTRUCTIONS.lower()
    assert "postura neutrale sul 1/2" in spec
    assert "non partire dal presupposto" in spec
    assert "assegna c9=2" in spec
    assert "uno solo difetto minore" in spec
    assert "almeno due difetti editoriali concreti" in spec


def test_a4_prompt_treats_scraping_parsing_artifacts_as_technical_limits():
    """Markers such as '-->' or isolated leading dots are not primary C9 defects."""
    spec = A4_SPECIFIC_INSTRUCTIONS.lower()
    schema = A4_OUTPUT_SCHEMA_INSTRUCTIONS.lower()
    assert "artefatti di parsing" in spec
    assert "scraping/parsing" in spec
    assert "-->" in spec
    assert "punti isolati" in spec
    assert "\\n" in spec
    assert "non usarli come ragione principale" in spec
    assert "non usare come evidenza principale possibili artefatti" in schema
    assert "\\n" in schema


def test_a4_prompt_renders_syllabus_text_without_json_escaped_newlines():
    """The A4 syllabus block must not expose line breaks as literal \\n."""
    prompt = build_a4_prompt(_agent_input({"course_content_it": "Topic A.\nTopic B."}))
    syllabus_block = prompt.split("DATI DEL SYLLABUS DA VALUTARE:\n", 1)[1].split(
        "CONTESTO NORMATIVO RECUPERATO VIA RAG:", 1
    )[0]

    assert "### course_content_it" in syllabus_block
    assert "Topic A.\nTopic B." in syllabus_block
    assert "\\n" not in syllabus_block


def test_a4_prompt_is_tolerant_on_english_and_references():
    spec = A4_SPECIFIC_INSTRUCTIONS.lower()
    schema = A4_OUTPUT_SCHEMA_INSTRUCTIONS.lower()
    score_2 = next(
        s for s in A4_CRITERIA_SPECS if s["criterion_code"] == "C9"
    )["anchors"]["2"].lower()

    assert "inglese comprensibile" in spec
    assert "sufficientemente comprensibile" in schema
    assert "non perfettamente idiomatic" in spec
    assert "riferimenti e fonti" in spec
    assert "non richiedere uno stile bibliografico uniforme" in schema
    assert "riferimenti sufficientemente chiari" in score_2


def test_a4_prompt_excludes_dublin_field_fragmentation_from_c9():
    """Dublin sub-field fragments are not editorial defects by themselves."""
    spec = A4_SPECIFIC_INSTRUCTIONS.lower()
    schema = A4_OUTPUT_SCHEMA_INSTRUCTIONS.lower()
    score_2 = next(s for s in A4_CRITERIA_SPECS if s["criterion_code"] == "C9")["anchors"]["2"].lower()

    assert "campi dublin" in spec
    assert "non penalizzare un dublin_* solo perché" in spec
    assert "frammentarietà dei campi dublin_*" in score_2
    assert "i campi dublin_* non vanno usati" in schema


def test_a4_prompt_excludes_semantic_it_en_contradictions_from_c9():
    """Semantic IT/EN mismatch belongs to E4/C2/C5, not editorial care."""
    spec = A4_SPECIFIC_INSTRUCTIONS.lower()
    schema = A4_OUTPUT_SCHEMA_INSTRUCTIONS.lower()
    score_1 = next(s for s in A4_CRITERIA_SPECS if s["criterion_code"] == "C9")["anchors"]["1"].lower()

    assert "contraddizioni it/en" in spec
    assert "l'equivalenza semantica it/en appartiene a e4" in spec
    assert 'prerequisites_en = "none"' in spec
    assert "contraddizioni semantiche it/en" in score_1
    assert "contraddizioni semantiche it/en" in schema


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
    A4 caps evidences at 5 representative items."""
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
