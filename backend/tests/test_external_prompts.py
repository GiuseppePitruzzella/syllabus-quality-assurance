"""Tests for the A5 extended-criteria prompt builders (Phase 9.C.3.A).

The goal of these tests is not to assert exact prompt text — that
would make every minor copy edit a test-breaking churn — but to
guarantee structural invariants the LLM relies on:

  * every prompt embeds the four rubric anchors of its criterion
    verbatim (so the model sees what the user sees on the Settings
    page);
  * every prompt carries an explicit ``prompt_version`` string via
    the ``PROMPT_VERSIONS`` map so each run is reproducible;
  * the per-criterion JSON output schema block is present and
    matches the criterion code (no E2 prompt accidentally asking
    for a judgment on E3, e.g.);
  * the dual-source rule is enforced for E1/E2/E3/E5, the
    paired-prefix rule for E4 and NEVER the other way round
    (E4 must not mention external documents in its rule).
"""
from __future__ import annotations

import pytest

from app.evaluation.agents.external_prompts import (
    E1_PROMPT_VERSION,
    E2_PROMPT_VERSION,
    E3_PROMPT_VERSION,
    E4_PROMPT_VERSION,
    E5_PROMPT_VERSION,
    PROMPT_VERSIONS,
    build_e1_prompt,
    build_e2_prompt,
    build_e3_prompt,
    build_e4_prompt,
    build_e5_prompt,
)
from app.evaluation.agents.external_prompts.e1_prompt import E1_CRITERION_SPEC
from app.evaluation.agents.external_prompts.e2_prompt import E2_CRITERION_SPEC
from app.evaluation.agents.external_prompts.e3_prompt import E3_CRITERION_SPEC
from app.evaluation.agents.external_prompts.e4_prompt import E4_CRITERION_SPEC
from app.evaluation.agents.external_prompts.e5_prompt import E5_CRITERION_SPEC


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _syllabus_fields() -> dict:
    """A minimal syllabus payload sufficient for the prompts.

    The handler will pass criterion-relevant fields; the prompt
    builder itself doesn't care about which fields — it just
    serialises whatever it receives.
    """
    return {
        "seuid": "test-seuid",
        "course_title_it": "Sistemi distribuiti",
        "course_title_en": "Distributed Systems",
        "learning_outcomes_it": "Conoscenza dei modelli di consistenza...",
        "learning_outcomes_en": "Understanding of consistency models...",
        "prerequisites_it": "Programmazione concorrente di base",
        "course_content_it": "Modelli, consenso, replicazione",
        "course_content_en": "Models, consensus, replication",
    }


def _chunks(*, document_id: int = 42, n: int = 2) -> list[dict]:
    return [
        {
            "chunk_id": f"external_{document_id}__chunk_{i:04d}",
            "text": f"Frammento di esempio numero {i}",
            "metadata": {"document_id": document_id, "section": f"§{i}"},
            "similarity_score": 0.8 - 0.05 * i,
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# PROMPT_VERSIONS registry
# ---------------------------------------------------------------------------


def test_prompt_versions_map_covers_e1_through_e5_and_matches_constants():
    assert set(PROMPT_VERSIONS.keys()) == {"E1", "E2", "E3", "E4", "E5"}
    assert PROMPT_VERSIONS["E1"] == E1_PROMPT_VERSION == "e1_v1"
    assert PROMPT_VERSIONS["E2"] == E2_PROMPT_VERSION == "e2_v1"
    assert PROMPT_VERSIONS["E3"] == E3_PROMPT_VERSION == "e3_v1"
    assert PROMPT_VERSIONS["E4"] == E4_PROMPT_VERSION == "e4_v1"
    assert PROMPT_VERSIONS["E5"] == E5_PROMPT_VERSION == "e5_v1"


# ---------------------------------------------------------------------------
# Anchor verbatim
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spec, builder, builder_kwargs",
    [
        (
            E1_CRITERION_SPEC,
            build_e1_prompt,
            {
                "syllabus_data": _syllabus_fields(),
                "external_chunks": _chunks(document_id=42),
                "document_id": 42,
            },
        ),
        (
            E2_CRITERION_SPEC,
            build_e2_prompt,
            {
                "syllabus_data": _syllabus_fields(),
                "external_chunks": _chunks(document_id=51),
                "document_id": 51,
            },
        ),
        (
            E3_CRITERION_SPEC,
            build_e3_prompt,
            {
                "syllabus_data": _syllabus_fields(),
                "external_chunks": _chunks(document_id=77),
                "document_id": 77,
            },
        ),
        (
            E4_CRITERION_SPEC,
            build_e4_prompt,
            {"syllabus_data": _syllabus_fields()},
        ),
        (
            E5_CRITERION_SPEC,
            build_e5_prompt,
            {
                "syllabus_data": _syllabus_fields(),
                "external_chunks_by_document": [
                    {
                        "document_id": 11,
                        "document_type": "usi_dipartimentali",
                        "chunks": _chunks(document_id=11, n=1),
                    },
                    {
                        "document_id": 12,
                        "document_type": "linee_guida_cdl",
                        "chunks": _chunks(document_id=12, n=1),
                    },
                ],
            },
        ),
    ],
    ids=["E1", "E2", "E3", "E4", "E5"],
)
def test_each_prompt_embeds_its_four_anchors_verbatim(
    spec, builder, builder_kwargs,
):
    """The 0/1/2/NA strings from the criterion spec must appear
    verbatim in the rendered prompt. This guards against future
    paraphrasing drift between the rubric on the Settings page and
    what the LLM actually reads."""
    prompt = builder(**builder_kwargs)
    for key in ("0", "1", "2", "NA"):
        assert spec["anchors"][key] in prompt, (
            f"Anchor {spec['criterion_code']} score={key} missing in prompt"
        )


# ---------------------------------------------------------------------------
# Output schema block
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "criterion, builder, builder_kwargs",
    [
        (
            "E1",
            build_e1_prompt,
            {
                "syllabus_data": _syllabus_fields(),
                "external_chunks": _chunks(),
                "document_id": 42,
            },
        ),
        (
            "E2",
            build_e2_prompt,
            {
                "syllabus_data": _syllabus_fields(),
                "external_chunks": _chunks(),
                "document_id": 42,
            },
        ),
        (
            "E3",
            build_e3_prompt,
            {
                "syllabus_data": _syllabus_fields(),
                "external_chunks": _chunks(),
                "document_id": 42,
            },
        ),
        (
            "E4",
            build_e4_prompt,
            {"syllabus_data": _syllabus_fields()},
        ),
        (
            "E5",
            build_e5_prompt,
            {
                "syllabus_data": _syllabus_fields(),
                "external_chunks_by_document": [
                    {
                        "document_id": 11,
                        "document_type": "usi_dipartimentali",
                        "chunks": _chunks(document_id=11, n=1),
                    },
                ],
            },
        ),
    ],
)
def test_prompt_carries_schema_block_for_correct_criterion(
    criterion, builder, builder_kwargs,
):
    prompt = builder(**builder_kwargs)
    # The schema block names the criterion and exposes the JSON shape.
    assert "SCHEMA OUTPUT JSON" in prompt
    assert f'"criterion_code": "{criterion}"' in prompt
    # And one criterion's prompt should NOT carry another's code as
    # the schema target (no cross-pollination).
    others = {"E1", "E2", "E3", "E4", "E5"} - {criterion}
    for o in others:
        assert f'"criterion_code": "{o}"' not in prompt, (
            f"{criterion} prompt accidentally targets {o}"
        )


# ---------------------------------------------------------------------------
# Rule block: dual-source vs paired-prefix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "criterion, builder, builder_kwargs",
    [
        (
            "E1",
            build_e1_prompt,
            {
                "syllabus_data": _syllabus_fields(),
                "external_chunks": _chunks(),
                "document_id": 42,
            },
        ),
        (
            "E2",
            build_e2_prompt,
            {
                "syllabus_data": _syllabus_fields(),
                "external_chunks": _chunks(),
                "document_id": 42,
            },
        ),
        (
            "E3",
            build_e3_prompt,
            {
                "syllabus_data": _syllabus_fields(),
                "external_chunks": _chunks(),
                "document_id": 42,
            },
        ),
        (
            "E5",
            build_e5_prompt,
            {
                "syllabus_data": _syllabus_fields(),
                "external_chunks_by_document": [
                    {
                        "document_id": 11,
                        "document_type": "usi_dipartimentali",
                        "chunks": _chunks(document_id=11, n=1),
                    },
                ],
            },
        ),
    ],
    ids=["E1", "E2", "E3", "E5"],
)
def test_dual_source_criteria_carry_dual_source_rule(
    criterion, builder, builder_kwargs,
):
    prompt = builder(**builder_kwargs)
    assert "REGOLA DUAL-SOURCE" in prompt
    # And not the paired-prefix rule.
    assert "REGOLA PAIRED-PREFIX" not in prompt


def test_e4_carries_paired_prefix_rule_and_no_dual_source():
    prompt = build_e4_prompt(syllabus_data=_syllabus_fields())
    assert "REGOLA PAIRED-PREFIX" in prompt
    assert "REGOLA DUAL-SOURCE" not in prompt


def test_e4_explicitly_forbids_external_document_id():
    prompt = build_e4_prompt(syllabus_data=_syllabus_fields())
    # E4 must not encourage citing external documents.
    assert "NON usare \"source_document_id\"" in prompt


# ---------------------------------------------------------------------------
# Per-criterion methodological warnings
# ---------------------------------------------------------------------------


def test_e1_prompt_mentions_sua_cds_specific_quadri():
    prompt = build_e1_prompt(
        syllabus_data=_syllabus_fields(),
        external_chunks=_chunks(),
        document_id=42,
    )
    # The methodological block names the SUA-CdS quadri that E1 cares about.
    assert "A4.b.2" in prompt
    assert "A4.c" in prompt


def test_e3_prompt_mentions_cfu_and_propedeuticita():
    prompt = build_e3_prompt(
        syllabus_data=_syllabus_fields(),
        external_chunks=_chunks(),
        document_id=42,
    )
    # E3 specifically calls out CFU and prerequisite chains.
    assert "CFU" in prompt
    assert "propedeuticit" in prompt.lower()


def test_e5_prompt_distinguishes_e5_from_core_criteria():
    prompt = build_e5_prompt(
        syllabus_data=_syllabus_fields(),
        external_chunks_by_document=[
            {
                "document_id": 11,
                "document_type": "usi_dipartimentali",
                "chunks": _chunks(document_id=11, n=1),
            },
        ],
    )
    # E5 must explicitly disclaim duplicating C1-C9.
    assert "non duplica C1" in prompt or "non duplica C1–C9" in prompt


# ---------------------------------------------------------------------------
# Document id propagation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "builder",
    [build_e1_prompt, build_e2_prompt, build_e3_prompt],
)
def test_dual_source_handlers_expose_document_id_in_external_block(builder):
    prompt = builder(
        syllabus_data=_syllabus_fields(),
        external_chunks=_chunks(document_id=42),
        document_id=42,
    )
    assert "document_id = 42" in prompt


def test_e5_exposes_every_local_document_id_in_payload():
    prompt = build_e5_prompt(
        syllabus_data=_syllabus_fields(),
        external_chunks_by_document=[
            {
                "document_id": 11,
                "document_type": "usi_dipartimentali",
                "chunks": _chunks(document_id=11, n=1),
            },
            {
                "document_id": 12,
                "document_type": "linee_guida_cdl",
                "chunks": _chunks(document_id=12, n=1),
            },
        ],
    )
    # Both document_id values must be visible to the model.
    assert "\"document_id\": 11" in prompt
    assert "\"document_id\": 12" in prompt
