"""A4 — Agente di cura editoriale (C9).

Evaluates the editorial quality of the syllabus considered as a whole:
typos, formal/redactional internal inconsistencies, completeness and
formatting of bibliographic references, formatting noise, macroscopic
IT/EN parallelism. C9 is the most interpretive criterion in the
rubric (D006); the prompt enforces a prudent posture and a default
``confidence="medium"`` to discourage hallucinated editorial
problems.

A4 is the only agent that reads the syllabus as a unit, so the
relevant-fields list is the largest. The class itself is a thin
subclass of BaseAgent: only field selection is A4-specific.
"""
from __future__ import annotations

from typing import Any

from app.evaluation.agents.base import BaseAgent
from app.evaluation.agents.prompts.a4_prompt import (
    A4_RELEVANT_FIELDS,
    build_a4_prompt,
)
from app.evaluation.agents.schemas import AgentOutput, CriterionEvidence, CriterionJudgment


class EditorialCareAgent(BaseAgent):
    """A4 — Cura editoriale del syllabus (C9)."""

    agent_code = "A4"
    criteria_codes = ["C9"]
    # Version history:
    # - a4_v1: first prompt + ScientificConfig.llm_max_output_tokens=8192
    #   (D030). Diagnostic run on 5 LM-18 syllabi: A4 found real
    #   editorial issues (parser '-->' residues, typos like 'utlizzando',
    #   leftover 'ENGLISH VERSION' template markers) but mis-calibrated
    #   the 0/1 boundary (4/4 valid runs scored C9=0 with confidence=high)
    #   and double-counted C2 (penalised English absence as editorial
    #   defect). 1 truncated run on MACHINE LEARNING due to
    #   evidence-list inflation. Treated as DIAGNOSTIC, not committed
    #   as official fixtures.
    # - a4_v2: four corrections in response to the diagnostic run:
    #   (1) tighter anchors — score=1 is the default for "refusi sparsi
    #       + residui localizzati", score=0 reserved for "gravi, diffusi,
    #       sistematici";
    #   (2) confidence='medium' enforced as the real default;
    #   (3) RIGORE SULL'ESCLUSIONE C2: explicit ban on citing English
    #       absence/partiality in justification or evidences;
    #   (4) cap of 5 evidences per judgment to prevent MAX_TOKENS.
    # - a4_v3: targeted C9 recalibration after LM-18 validation showed
    #   near-zero variance (29/30 C9=1, 1/30 C9=0). The prompt now uses
    #   a neutral 1/2 posture and explicitly forbids penalising likely
    #   scraping/parsing artifacts (isolated leading dots, line-break
    #   splits, "-->" markers) as editorial defects of the syllabus.
    # - a4_v4: second targeted C9 recalibration after c5_c9_targeted_v1
    #   still returned 6/6 C9=1. The prompt now requires at least two
    #   concrete editorial defects in distinct fields (or one severe
    #   redactional defect) before lowering to 1, and explicitly excludes
    #   dublin_* field fragments plus semantic IT/EN contradictions from
    #   C9 evidence.
    # - a4_v5: VAPT review showed a remaining false-positive C9=1:
    #   one localized typo repeated in duplicated/derived EN fields plus
    #   understandable mixed IT/EN technical citations were counted as a
    #   defect cluster. The prompt now counts repeated instances of the
    #   same typo as one defect and tolerates intelligible technical
    #   titles/citations mixing Italian and English.
    # - a4_v6: VAPT rerun still counted an intelligible mixed-language
    #   schedule citation ("Chapter ... e Capitolo ...") as a second C9
    #   defect. The prompt now explicitly forbids citing intelligible
    #   mixed IT/EN technical citations as defect evidence and states that
    #   one localized typo plus such a citation remains C9=2.
    # - a4_v7: VAPT rerun still used leading-dot Dublin fragments as C9
    #   evidence despite prompt exclusions. A4 now strips isolated leading
    #   dots from dublin_* fields before prompting so parser artifacts are
    #   not visible to the LLM as editorial defects.
    # - a4_v8: VAPT rerun still counted a mixed typographic/straight quote
    #   in an intelligible schedule citation as a missing closing quote.
    #   A4 now normalises typographic quotes before prompting so citation
    #   typography is not misread as editorial care.
    # - a4_v9: VAPT rerun still treated intelligible mixed IT/EN technical
    #   schedule citations as a second independent C9 defect. A4 now applies
    #   a deterministic post-validation guard: those citations are excluded
    #   from the C9 defect count, and one remaining localized minor defect is
    #   insufficient to lower an otherwise curated syllabus below C9=2.
    # - a4_v10: C9 no longer sees syllabus text through JSON-escaped
    #   strings (literal "\n" prompt artifacts), includes the scraped
    #   English title, and narrows EN/reference penalties to clear textual
    #   defects rather than intelligible non-native phrasing or harmless
    #   citation-style variation.
    prompt_version = "a4_v10"

    def __init__(self, retriever: Any, llm_client: Any) -> None:
        super().__init__(
            retriever=retriever,
            llm_client=llm_client,
            prompt_builder=build_a4_prompt,
        )

    def evaluate(self, syllabus: Any) -> AgentOutput:
        """Evaluate A4 and apply deterministic C9 false-positive guards."""
        output = super().evaluate(syllabus)
        processed: list[CriterionJudgment] = []
        changed = False
        for judgment in output.judgments:
            next_judgment = _postprocess_c9_judgment(judgment)
            changed = changed or next_judgment != judgment
            processed.append(next_judgment)
        if not changed:
            return output
        metadata = dict(output.execution_metadata)
        metadata["postprocessing"] = {
            "C9": "excluded_intelligible_mixed_technical_citations_from_defect_count"
        }
        return output.model_copy(update={"judgments": processed, "execution_metadata": metadata})

    def get_relevant_syllabus_fields(self, syllabus: Any) -> dict[str, Any]:
        """Return the A4-relevant subset of the syllabus.

        A4 reads the syllabus as a unit, so the field list covers all
        the editorial metadata and every IT/EN content field. DB
        internals (id/cdl_id/seuid) and links (url_*) are excluded:
        they don't carry editorial signal that A4 can verify on the
        text alone.

        Empty / null values are preserved on purpose: the prompt
        instructs A4 to evaluate ``how what is there is written``,
        not what is structurally missing.

        Accepts either an SQLAlchemy ``Syllabus`` row or a plain dict.
        """
        out: dict[str, Any] = {}
        for field in A4_RELEVANT_FIELDS:
            if isinstance(syllabus, dict):
                value = syllabus.get(field)
            else:
                value = getattr(syllabus, field, None)
            out[field] = _clean_a4_field(field, _coerce(value))
        return out


def _coerce(value: Any) -> Any:
    """Coerce a syllabus field to a JSON-serialisable primitive."""
    if value is None or isinstance(value, (str, bool, int, float, list, dict)):
        return value
    return str(value)


def _clean_a4_field(field: str, value: Any) -> Any:
    """Remove parser artifacts that A4 must not evaluate as editorial care.

    The UniCT scraper can surface Dublin descriptor sub-fields with an
    isolated leading dot, e.g. ``". Students will ..."``. That dot is a
    section-splitting artifact, not text authored in the syllabus page.
    Keeping it in A4's payload repeatedly caused false C9 penalties.
    """
    if not isinstance(value, str):
        return value
    cleaned = _normalise_quote_artifacts(value)
    cleaned = _normalise_line_break_artifacts(cleaned)
    if field.startswith("dublin_"):
        cleaned = cleaned.lstrip().removeprefix(".").lstrip()
    return cleaned


_QUOTE_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u00ab": '"',
        "\u00bb": '"',
    }
)


def _normalise_quote_artifacts(value: str) -> str:
    """Normalise quote glyphs that can vary during extraction.

    C9 should not penalise an otherwise intelligible technical citation
    only because the extracted text mixes typographic quotes with straight
    quotes, e.g. ``"Distro Offensive"`` represented with one curly quote
    and one straight quote.
    """
    return value.translate(_QUOTE_TRANSLATION)


def _normalise_line_break_artifacts(value: str) -> str:
    """Treat literal ``\\n`` sequences as extraction/prompt artifacts."""
    return value.replace("\\r\\n", "\n").replace("\\n", "\n")


def _postprocess_c9_judgment(judgment: CriterionJudgment) -> CriterionJudgment:
    """Correct known C9 false positives after schema validation.

    The LLM repeatedly treats intelligible mixed-language technical
    citations in ``schedule_*`` / ``references_*`` as editorial defects
    despite the prompt forbidding that interpretation. C9=1 is only
    justified by at least two independent concrete defects or one severe
    defect; therefore one localized typo plus one such citation remains
    C9=2.
    """
    if judgment.criterion_code != "C9" or judgment.is_na or judgment.score != 1:
        return judgment

    valid_evidences = [
        evidence
        for evidence in judgment.evidences
        if not _is_intelligible_mixed_technical_citation(evidence)
    ]
    if len(valid_evidences) == len(judgment.evidences):
        return judgment
    independent_defects = _dedupe_c9_defect_evidences(valid_evidences)
    if len(independent_defects) > 1:
        return judgment.model_copy(update={"evidences": valid_evidences})
    return judgment.model_copy(
        update={
            "score": 2,
            "confidence": "medium",
            "evidences": valid_evidences,
            "justification": (
                "Il syllabus è complessivamente curato. La revisione deterministica "
                "di C9 ha escluso dal conteggio le citazioni tecniche miste ma "
                "intelligibili nei campi di programmazione o riferimenti; resta al "
                "più un difetto minore e localizzato, insufficiente per abbassare il "
                "punteggio secondo la rubrica."
            ),
        }
    )


def _dedupe_c9_defect_evidences(
    evidences: list[CriterionEvidence],
) -> list[CriterionEvidence]:
    seen: set[str] = set()
    out: list[CriterionEvidence] = []
    for evidence in evidences:
        key = " ".join(evidence.text.casefold().split())
        if key in seen:
            continue
        seen.add(key)
        out.append(evidence)
    return out


def _is_intelligible_mixed_technical_citation(evidence: CriterionEvidence) -> bool:
    field = evidence.source_field
    if field not in {"schedule_it", "schedule_en", "references_it", "references_en"}:
        return False
    text = " ".join(evidence.text.casefold().split())
    has_reference_marker = "[" in text and "]" in text
    has_course_material_hint = any(
        hint in text
        for hint in (
            "chapter",
            "capitolo",
            "online resources",
            "slide",
            "blocco",
            "denominato",
        )
    )
    has_mixed_connector = any(
        connector in text
        for connector in (
            " e capitolo ",
            " e chapter ",
            " e ",
            "denominato",
        )
    )
    return has_reference_marker and has_course_material_hint and has_mixed_connector
