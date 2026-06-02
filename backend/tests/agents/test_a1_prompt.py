"""Tests for the A1 prompt builder.

Smoke tests focus on prompt structure (block order, single source of
truth for anchors, placeholder safety in the JSON schema example)
rather than the LLM call.
"""
from __future__ import annotations

from app.evaluation.agents.prompts.a1_prompt import (
    A1_CRITERIA_SPECS,
    A1_OUTPUT_SCHEMA_INSTRUCTIONS,
    A1_SPECIFIC_INSTRUCTIONS,
    build_a1_prompt,
)
from app.evaluation.agents.schemas import AgentInput


def _agent_input(syllabus_data: dict | None = None) -> AgentInput:
    return AgentInput(
        syllabus_seuid="SEUID-TEST",
        syllabus_data=syllabus_data
        or {
            "course_name": "Sample course",
            "has_english": False,
            "prerequisites_it": "Nessuno",
        },
        criteria_specs=A1_CRITERIA_SPECS,
        normative_context=[
            {
                "criterion_code": "C1",
                "chunk_id": "lg_unict__2__0",
                "text": "Tutte le sezioni devono essere compilate.",
                "metadata": {"document_id": "lg_unict", "section_ref": "2"},
                "similarity_score": 0.85,
            }
        ],
    )


def test_prompt_block_order():
    """Blocks appear in the order: BASE -> A1_SPEC -> SPECS -> SYLLABUS -> RAG -> SCHEMA -> closing."""
    prompt = build_a1_prompt(_agent_input())

    markers_in_order = [
        "Sei un esperto di Assicurazione della Qualità",   # BASE
        "AGENTE DI COMPLETEZZA DOCUMENTALE (A1)",          # A1_SPEC
        "SPECIFICHE CRITERI:",                             # SPECS (structured)
        "DATI DEL SYLLABUS DA VALUTARE:",                  # SYLLABUS
        "CONTESTO NORMATIVO RECUPERATO VIA RAG:",          # RAG
        "SCHEMA OUTPUT JSON",                              # SCHEMA
        "Rispondi ora esclusivamente con il JSON valido",  # closing
    ]
    positions = [prompt.find(m) for m in markers_in_order]
    missing = [m for m, p in zip(markers_in_order, positions, strict=True) if p < 0]
    assert not missing, f"missing markers: {missing}"
    assert positions == sorted(positions), f"out-of-order blocks: {positions}"


def test_prompt_contains_role_and_payloads():
    """Sanity check: A1 identity + syllabus + closing all present."""
    agent_input = AgentInput(
        syllabus_seuid="abc",
        syllabus_data={
            "course_name": "Deep Learning",
            "has_english": True,
            "learning_outcomes_it": "Risultati di apprendimento attesi.",
            "learning_outcomes_en": "Expected learning outcomes.",
            "prerequisites_it": "Programmazione e algebra lineare.",
        },
        criteria_specs=A1_CRITERIA_SPECS,
        normative_context=[
            {
                "criterion_code": "C2",
                "chunk_id": "lg_unict__3__0",
                "text": "Tutte le sezioni presenti nella scheda insegnamento dovranno essere compilate in italiano e in inglese.",
                "metadata": {"document_id": "lg_unict", "section_ref": "3"},
                "similarity_score": 0.72,
            }
        ],
    )

    prompt = build_a1_prompt(agent_input)

    assert "AGENTE DI COMPLETEZZA DOCUMENTALE" in prompt
    assert "Deep Learning" in prompt
    assert "Programmazione e algebra lineare" in prompt
    assert "Rispondi ora esclusivamente con il JSON valido richiesto." in prompt


def test_a1_specific_does_not_duplicate_anchors():
    """Anchor strings are owned by A1_CRITERIA_SPECS, NOT by the narrative block.

    The narrative used to repeat 'Anchor:\\n- 0: ...' for each criterion;
    we removed that to avoid two sources of truth for the same anchor.
    The structured A1_CRITERIA_SPECS list is the single source.
    """
    spec_text = A1_SPECIFIC_INSTRUCTIONS
    # The narrative must NOT include the legacy "Anchor:\n- 0:..." structure.
    assert "Anchor:" not in spec_text
    # And no "=== C1 ===" / "=== C2 ===" / "=== C5 ===" headers either.
    assert "=== C1" not in spec_text
    assert "=== C2" not in spec_text
    assert "=== C5" not in spec_text
    # The structured specs DO contain the anchors with all three levels.
    for spec in A1_CRITERIA_SPECS:
        assert set(spec["anchors"].keys()) == {"0", "1", "2"}


def test_prompt_includes_three_criteria_specs():
    prompt = build_a1_prompt(_agent_input())
    assert '"criterion_code": "C1"' in prompt
    assert '"criterion_code": "C2"' in prompt
    assert '"criterion_code": "C5"' in prompt


def test_prompt_includes_rag_vs_evidences_rule():
    """The base prompt must clarify that RAG is for interpretation, not evidence."""
    prompt = build_a1_prompt(_agent_input())
    rag_rule_present = (
        "non citare frammenti del contesto normativo" in prompt.lower()
        or "non è una fonte di evidenze" in prompt.lower()
    )
    assert rag_rule_present, "RAG-vs-evidences rule must be in the base prompt"


def test_schema_example_is_neutral():
    """The output schema must NOT bias the LLM toward score=0.

    The original draft used 'score: 0' as the canonical example, which
    risks biasing the LLM. The placeholder form '<0 | 1 | 2 | null>'
    plus an explicit anti-copy directive removes the bias.
    """
    schema = A1_OUTPUT_SCHEMA_INSTRUCTIONS
    assert "<0 | 1 | 2 | null>" in schema
    assert "PLACEHOLDER" in schema or "non vanno copiati" in schema


def test_prompt_emits_evidences_only_from_syllabus_rule():
    """Final reminder to keep evidences syllabus-only must be present in the schema block."""
    prompt = build_a1_prompt(_agent_input())
    assert "evidences deve contenere solo citazioni letterali dal SYLLABUS" in prompt


def test_prompt_forbids_empty_text_evidences():
    """When a field is empty, the prompt must instruct evidences=[] rather than text=''.

    This rule exists because ``CriterionEvidence.text`` has min_length=1
    (an empty quote is not evidence). Without the rule the LLM emits
    `[{"text": "", "source_field": "X_en"}]` to signal an absent field,
    which the validator rejects, the agent retries, and we waste a full
    LLM call with the same outcome.
    """
    from app.evaluation.agents.prompts.a1_prompt import (
        A1_OUTPUT_SCHEMA_INSTRUCTIONS,
    )
    schema = A1_OUTPUT_SCHEMA_INSTRUCTIONS
    assert "NON inserire MAI evidenze" in schema or "evidences\" come lista vuota" in schema


def test_prompt_accepts_dict_input():
    """build_a1_prompt should accept either AgentInput or a dict."""
    payload = {
        "syllabus_seuid": "X",
        "syllabus_data": {"course_name": "Some Course", "has_english": False},
        "criteria_specs": A1_CRITERIA_SPECS,
        "normative_context": [],
    }
    prompt = build_a1_prompt(payload)
    assert "Sei un esperto" in prompt
    assert "Some Course" in prompt


def test_a1_c5_anchors_require_explicit_culturali_disciplinari_distinction_for_score_2():
    """a1_v5: C5 = 2 requires both specificity AND the explicit distinction.

    The 5.4.I E2E calibration found C5 drifting systematically from 1 to 2
    on 3/4 non-NA syllabi because the a1_v4 anchors let "specific but
    without the culturali/disciplinari distinction" earn a 2. a1_v5 moves
    that bar: score=2 now requires both criteria; score=1 explicitly
    covers the specific-but-no-distinction case.
    """
    c5_spec = next(s for s in A1_CRITERIA_SPECS if s["criterion_code"] == "C5")
    anchor_2 = c5_spec["anchors"]["2"].lower()
    anchor_1 = c5_spec["anchors"]["1"].lower()

    # Score=2 requires the distinction, in both dimensions.
    assert "distint" in anchor_2 or "distinzione" in anchor_2
    assert "cultural" in anchor_2 and "disciplinar" in anchor_2

    # Score=1 covers "specific but no distinction".
    assert "specifici" in anchor_1
    assert "senza distinzione" in anchor_1


def test_a1_c5_narrative_is_consistent_with_new_anchors():
    """The narrative paragraph for C5 must match the new a1_v5 anchors.

    a1_v4 said the gradation/distinction "raccomandano (non impongono)";
    a1_v5 tightens the C5=2 bar but keeps the *gradation* (utili /
    importanti / indispensabili) as a non-mandatory recommendation.
    """
    spec_text = A1_SPECIFIC_INSTRUCTIONS

    # The advisory must explicitly say "score 2 requires the distinction".
    assert "Il punteggio 2 richiede" in spec_text
    assert "distinzione esplicita" in spec_text
    assert "cultural" in spec_text and "disciplinar" in spec_text

    # The gradation utili/importanti/indispensabili must still be framed
    # as recommended, not mandatory.
    assert "raccomandata" in spec_text or "raccomanda" in spec_text
    assert "non è di per sé sufficiente né necessaria" in spec_text

    # No lingering a1_v4 softening on the distinction itself.
    assert "non lo determina da sola" not in spec_text
    assert "RACCOMANDANO" not in spec_text  # all-caps emphasis from a1_v4


def test_build_a1_prompt_defaults_to_a1_criteria_specs_when_empty():
    """If criteria_specs is empty in the input, the builder falls back to A1_CRITERIA_SPECS."""
    prompt = build_a1_prompt(
        {
            "syllabus_seuid": "abc",
            "syllabus_data": {"course_name": "Deep Learning"},
            "criteria_specs": [],
            "normative_context": [],
        }
    )
    # All three criterion names from A1_CRITERIA_SPECS must be present.
    assert "Completezza strutturale" in prompt
    assert "Completezza bilingue" in prompt
    assert "Chiarezza dei prerequisiti" in prompt
