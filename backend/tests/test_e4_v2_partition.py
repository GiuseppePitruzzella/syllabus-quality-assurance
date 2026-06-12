"""Phase 9.F.2 (e4_v2) — focused tests for the substantiality rule,
the partition function, the threshold rendering in the prompt and
the handler→prompt integration.

These tests do not call the LLM. They cover the structural
contract of the new partition path: which prefix lands in which
bucket, what the prompt renders, and whether the handler's
``execution_metadata`` exposes the right counts.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.evaluation.agents.external_handlers.e4_handler import (
    E4Handler,
    E4_PAIRED_PREFIXES,
    _is_substantial,
    _partition_prefixes,
)
from app.evaluation.agents.external_prompts.e4_prompt import (
    E4_PROMPT_VERSION,
    E4FieldPartition,
    E4PrefixOmission,
    build_e4_prompt,
)


# ---------------------------------------------------------------------------
# _is_substantial
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        None, "", "   ", "\n\t",
        "N/A", "n/a", "N.A.", "n.d.",
        "-", "—", "–", "...", "…",
        "nessuno", "Nessuna", "non applicabile",
        "to be defined", "TBD",
        "italiano", "Inglese", "english",
        "*", "*  ",
        "vedi sopra", "see below",
        "ciao mondo",  # 11 chars, 2 words → not substantial
        "ab cd",  # 5 chars, 2 words → not substantial
    ],
)
def test_is_substantial_rejects_placeholders_and_short_strings(value):
    assert _is_substantial(value) is False


@pytest.mark.parametrize(
    "value",
    [
        # ≥ 30 chars
        "Conoscenza dei modelli di consistenza distribuita.",
        "La frequenza al laboratorio è obbligatoria.",
        # ≥ 5 words, < 30 chars (the OR threshold)
        "uno due tre quattro cinque sei",
        # Borderline cases that should still pass
        "La frequenza non è obbligatoria",  # 31 chars
        "uno due tre quattro cinque",  # 25 chars, 5 words → substantial
    ],
)
def test_is_substantial_accepts_meaningful_content(value):
    assert _is_substantial(value) is True


def test_is_substantial_returns_false_for_non_string():
    for value in (123, 12.5, True, [], {}, object()):
        assert _is_substantial(value) is False


# ---------------------------------------------------------------------------
# _partition_prefixes
# ---------------------------------------------------------------------------


def _syllabus(**fields):
    """Make a syllabus stub with every E4 prefix's _it/_en field
    set to '' by default (so undeclared fields don't trip the
    partition into "substantial" buckets accidentally)."""
    defaults: dict[str, str] = {}
    for prefix in E4_PAIRED_PREFIXES:
        defaults[f"{prefix}_it"] = ""
        defaults[f"{prefix}_en"] = ""
    defaults.update(fields)
    return SimpleNamespace(**defaults)


def test_partition_all_paired_substantial():
    long_it = "Conoscenza dei modelli di consistenza distribuita."
    long_en = "Knowledge of distributed consistency models for systems."
    syllabus = _syllabus(
        learning_outcomes_it=long_it,
        learning_outcomes_en=long_en,
        course_content_it="Modelli, consenso, replicazione e tolleranza.",
        course_content_en="Models, consensus, replication and tolerance.",
    )
    partition = _partition_prefixes(syllabus, E4_PAIRED_PREFIXES)
    assert partition.paired_prefix_count == 2
    assert partition.it_only_substantial == ()
    assert partition.en_only_substantial == ()
    assert "learning_outcomes_it" in partition.paired_fields
    assert "learning_outcomes_en" in partition.paired_fields


def test_partition_one_it_only_substantial_when_en_empty():
    long_it = "I prerequisiti del corso comprendono basi di analisi matematica."
    syllabus = _syllabus(
        learning_outcomes_it="Risultati di apprendimento sostanziali e pertinenti.",
        learning_outcomes_en="Substantial learning outcomes for the course.",
        course_content_it=long_it,
        course_content_en="",  # missing EN → omission
    )
    partition = _partition_prefixes(syllabus, E4_PAIRED_PREFIXES)
    assert partition.paired_prefix_count == 1
    assert len(partition.it_only_substantial) == 1
    omission = partition.it_only_substantial[0]
    assert omission.prefix == "course_content"
    assert omission.field == "course_content_it"
    assert omission.content == long_it


def test_partition_en_only_substantial_when_it_empty():
    syllabus = _syllabus(
        learning_outcomes_it="Risultati di apprendimento sostanziali del corso.",
        learning_outcomes_en="Substantial learning outcomes for this course.",
        course_content_it="",
        course_content_en="Substantial content section in English only.",
    )
    partition = _partition_prefixes(syllabus, E4_PAIRED_PREFIXES)
    assert partition.paired_prefix_count == 1
    assert len(partition.en_only_substantial) == 1
    omission = partition.en_only_substantial[0]
    assert omission.prefix == "course_content"
    assert omission.field == "course_content_en"


def test_partition_it_only_non_substantial_when_placeholder():
    """A placeholder on the IT side with no EN content is audit-only
    — it does NOT inflate the omission threshold."""
    syllabus = _syllabus(
        learning_outcomes_it="Risultati di apprendimento sostanziali del corso.",
        learning_outcomes_en="Substantial learning outcomes for this course.",
        prerequisites_it="N/A",  # placeholder → non-substantial
        prerequisites_en="",
    )
    partition = _partition_prefixes(syllabus, E4_PAIRED_PREFIXES)
    assert partition.paired_prefix_count == 1
    assert "prerequisites" in partition.it_only_non_substantial
    # NOT in it_only_substantial: the placeholder must not count.
    assert all(
        o.prefix != "prerequisites" for o in partition.it_only_substantial
    )


def test_partition_drops_prefixes_with_both_sides_empty():
    """Symmetric absence of content is not an omission — it's just
    a section the syllabus chose not to populate. Such prefixes are
    silently dropped from every bucket."""
    syllabus = _syllabus(
        learning_outcomes_it="Risultati di apprendimento sostanziali del corso.",
        learning_outcomes_en="Substantial learning outcomes for this course.",
        # all other prefixes left at "" / "" default
    )
    partition = _partition_prefixes(syllabus, E4_PAIRED_PREFIXES)
    assert partition.paired_prefix_count == 1
    # Nothing else lands anywhere.
    assert partition.it_only_substantial == ()
    assert partition.en_only_substantial == ()
    assert partition.it_only_non_substantial == ()
    assert partition.en_only_non_substantial == ()


def test_partition_treats_it_substantial_en_placeholder_as_omission():
    """IT substantial + EN placeholder counts as an EN-side omission
    (the EN value is not substantial, so it can't satisfy the
    pairing requirement). The prefix lands in ``it_only_substantial``,
    not in ``it_only_non_substantial``."""
    syllabus = _syllabus(
        learning_outcomes_it="Risultati di apprendimento sostanziali del corso.",
        learning_outcomes_en="Substantial learning outcomes for this course.",
        course_content_it="Contenuti corso strutturati e dettagliati.",
        course_content_en="N/A",  # placeholder
    )
    partition = _partition_prefixes(syllabus, E4_PAIRED_PREFIXES)
    omissions = {o.prefix for o in partition.it_only_substantial}
    assert "course_content" in omissions


# ---------------------------------------------------------------------------
# build_e4_prompt — threshold + substantial language
# ---------------------------------------------------------------------------


def _full_partition():
    """An E4 partition where every kind of bucket is non-empty."""
    return E4FieldPartition(
        paired_fields={
            "learning_outcomes_it": "Risultati di apprendimento substanziali del corso.",
            "learning_outcomes_en": "Substantial learning outcomes for the course.",
        },
        it_only_substantial=(
            E4PrefixOmission(
                prefix="course_content",
                field="course_content_it",
                content="Contenuti corso strutturati e dettagliati.",
            ),
        ),
        en_only_substantial=(
            E4PrefixOmission(
                prefix="prerequisites",
                field="prerequisites_en",
                content="Substantial English prerequisites text.",
            ),
        ),
        it_only_non_substantial=("dublin_knowledge",),
        en_only_non_substantial=("dublin_applying",),
    )


def test_e4_prompt_version_bumped_to_v2():
    assert E4_PROMPT_VERSION == "e4_v2"


def test_e4_prompt_renders_threshold_rule_with_specific_numbers():
    prompt = build_e4_prompt(partition=_full_partition())
    # The 0 / 1-2 / ≥3 threshold language must be in the prompt
    # so the model has explicit thresholds.
    assert "Nessun prefisso in `it_only_substantial`" in prompt
    assert "score massimo ammissibile 2" in prompt
    assert "1 o 2 prefissi in `it_only_substantial`" in prompt
    assert "score massimo ammissibile 1" in prompt
    assert "3 o più prefissi in `it_only_substantial`" in prompt
    assert "score massimo ammissibile 0" in prompt
    assert "`en_only_substantial`" in prompt


def test_e4_prompt_renders_substantial_definition():
    prompt = build_e4_prompt(partition=_full_partition())
    assert "DEFINIZIONE DI SOSTANZIALE" in prompt
    # placeholder examples are explicit (so the model can replicate
    # the filter mentally if needed)
    assert "N/A" in prompt
    assert "30 caratteri" in prompt


def test_e4_prompt_exposes_perimeter_view_with_all_buckets():
    prompt = build_e4_prompt(partition=_full_partition())
    # Each bucket name must appear in the JSON-rendered perimeter view
    # so the model can read it directly.
    assert "it_only_substantial" in prompt
    assert "en_only_substantial" in prompt
    assert "it_only_non_substantial" in prompt
    assert "en_only_non_substantial" in prompt
    # The omitted IT content must be in the prompt so the model can
    # verify the substantiality call.
    assert "Contenuti corso strutturati e dettagliati." in prompt


def test_e4_prompt_still_carries_paired_prefix_rule():
    """The validator rule on the response schema is unchanged. The
    prompt must continue to instruct the model that numeric scores
    require at least one paired evidence."""
    prompt = build_e4_prompt(partition=_full_partition())
    assert "REGOLA PAIRED-PREFIX" in prompt


# ---------------------------------------------------------------------------
# Handler → prompt integration (no LLM call here)
# ---------------------------------------------------------------------------


def test_handler_returns_semantic_na_when_no_substantial_pair():
    """A syllabus whose only "EN" content is a placeholder still
    triggers semantic NA: the substantial-pair count is zero."""
    syllabus = _syllabus(
        learning_outcomes_it="Risultati di apprendimento sostanziali.",
        learning_outcomes_en="N/A",  # placeholder → not substantial
    )
    llm = MagicMock()
    handler = E4Handler(llm_client=llm)
    result = handler.evaluate(syllabus=syllabus, cdl_id=3, document_ids=[])
    assert result.judgment.is_na is True
    assert result.judgment.is_na_technical is False
    assert llm.call_count == 0
    assert result.execution_metadata["paired_prefixes_count"] == 0


def test_handler_metadata_exposes_partition_counts():
    """When the LLM is called, the handler's execution_metadata
    must surface the four partition counts for downstream audit
    (calibration scripts, frontend hover, ...)."""
    long_it = "Risultati di apprendimento sostanziali e ben articolati."
    long_en = "Substantial learning outcomes well articulated for the course."
    syllabus = _syllabus(
        learning_outcomes_it=long_it,
        learning_outcomes_en=long_en,
        course_content_it="Contenuti dettagliati su modelli e protocolli.",
        course_content_en="",  # missing EN → it_only_substantial
        prerequisites_it="N/A",  # placeholder → it_only_non_substantial
    )

    # Minimal valid E4 response with paired evidence.
    response = """{
        "judgment": {
            "criterion_code": "E4",
            "score": 1,
            "is_na": false,
            "is_na_technical": false,
            "na_reason": null,
            "justification": "Una sezione manca lato EN; equivalenza parziale rispetto a quanto presente.",
            "evidences": [
                {"text": "%s", "source_field": "learning_outcomes_it"},
                {"text": "%s", "source_field": "learning_outcomes_en"}
            ],
            "confidence": "medium"
        }
    }""" % (long_it, long_en)

    llm = MagicMock(return_value=response)
    handler = E4Handler(llm_client=llm)
    result = handler.evaluate(syllabus=syllabus, cdl_id=3, document_ids=[])
    md = result.execution_metadata
    assert md["paired_prefixes_count"] == 1
    assert md["it_only_substantial_count"] == 1
    assert md["en_only_substantial_count"] == 0
    assert md["it_only_non_substantial_count"] == 1
    assert md["en_only_non_substantial_count"] == 0
    assert llm.call_count == 1


def test_handler_threshold_data_flows_into_prompt_argument():
    """End-to-end sanity: the prompt passed to the LLM mentions the
    omitted prefix name, the partition counts and the threshold
    rule. This guards against a refactor that silently stops
    passing the partition through."""
    syllabus = _syllabus(
        learning_outcomes_it="Risultati di apprendimento sostanziali e ben articolati.",
        learning_outcomes_en="Substantial learning outcomes well articulated.",
        course_content_it="Contenuti dettagliati su modelli e protocolli.",
        course_content_en="",
    )

    captured: dict[str, str] = {}

    def _fake_llm(prompt: str) -> str:
        captured["prompt"] = prompt
        return """{
            "judgment": {
                "criterion_code": "E4",
                "score": 1,
                "is_na": false,
                "is_na_technical": false,
                "na_reason": null,
                "justification": "Una sezione mancante in EN giustifica omissione rilevante.",
                "evidences": [
                    {"text": "Risultati di apprendimento sostanziali e ben articolati.", "source_field": "learning_outcomes_it"},
                    {"text": "Substantial learning outcomes well articulated.", "source_field": "learning_outcomes_en"}
                ],
                "confidence": "medium"
            }
        }"""

    handler = E4Handler(llm_client=_fake_llm)
    handler.evaluate(syllabus=syllabus, cdl_id=3, document_ids=[])
    prompt = captured["prompt"]
    assert "course_content" in prompt
    assert "Contenuti dettagliati" in prompt
    assert "score massimo ammissibile 1" in prompt
