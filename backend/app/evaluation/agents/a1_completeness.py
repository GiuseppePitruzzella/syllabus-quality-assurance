"""A1 — Agente di completezza documentale (C1, C2, C5).

Validates the structural completeness of a syllabus (C1), the
availability of an English version for the minimum bilingual perimeter
(C2), and the clarity of the prerequisites (C5).

The agent owns nothing about the LLM call itself — that lives in
``BaseAgent``. The only A1-specific responsibility here is selecting
the syllabus fields that go into the prompt: we exclude fields that
are irrelevant to A1 (e.g. ``url_it``) but we keep fields *expected*
by the rubric even when they are empty, because absence of content is
itself information for C1 and C2.
"""
from __future__ import annotations

from typing import Any

from app.evaluation.agents.base import BaseAgent
from app.evaluation.agents.prompts.a1_prompt import build_a1_prompt

# Fields A1 reads from the syllabus. Order is preserved in the prompt
# JSON dump for deterministic inspection during the calibration runs.
#
# The list is the union of:
#   - C1 obligatory sections (RA, PR, CN, MV, ED, TD, MS, MF, PRG)
#     — IT side, always included (empty value = section absent).
#   - C2 minimum bilingual perimeter (course name, RA, CN, MV)
#     — IT and EN side, plus has_english flag.
#   - C5 prerequisites IT and EN.
#
# Fields excluded on purpose: url_it, url_en, scraped_at, ids,
# course_code, and the EN counterparts of fields outside the C2
# bilingual perimeter (sample_questions_en, references_en,
# teaching_methods_en, attendance_en, schedule_en).
A1_RELEVANT_FIELDS: tuple[str, ...] = (
    # course identity (titolo) + bilingual flag
    "course_name",
    "course_name_en",
    "has_english",
    # RA — risultati di apprendimento (C1 IT + C2 IT/EN)
    "learning_outcomes_it",
    "learning_outcomes_en",
    "dublin_knowledge_it",
    "dublin_knowledge_en",
    "dublin_applying_it",
    "dublin_applying_en",
    "dublin_judgement_it",
    "dublin_judgement_en",
    "dublin_communication_it",
    "dublin_communication_en",
    "dublin_learning_it",
    "dublin_learning_en",
    # PR — prerequisiti (C1 IT + C5 IT/EN)
    "prerequisites_it",
    "prerequisites_en",
    # CN — contenuti (C1 IT + C2 IT/EN)
    "course_content_it",
    "course_content_en",
    # MV — modalità di verifica (C1 IT + C2 IT/EN)
    "assessment_methods_it",
    "assessment_methods_en",
    # ED — esempi domande (C1 IT only — outside C2 perimeter)
    "sample_questions_it",
    # TD — testi (C1 IT only)
    "references_it",
    # MS — metodi didattici (C1 IT only)
    "teaching_methods_it",
    # MF — modalità di frequenza (C1 IT only)
    "attendance_it",
    # PRG — programmazione (C1 IT only)
    "schedule_it",
)


class CompletenessAgent(BaseAgent):
    """A1 — Completezza documentale (criteri C1, C2, C5)."""

    agent_code = "A1"
    criteria_codes = ["C1", "C2", "C5"]
    # Version history:
    # - a1_v1: initial prompt + ScientificConfig.llm_max_output_tokens=2048.
    # - a1_v2: ScientificConfig bumped to 4096 (insufficient, see D030).
    # - a1_v3: ScientificConfig bumped to 8192 (D030 final) AND prompt
    #   instructed to leave evidences=[] when no literal text is
    #   available, instead of emitting "evidences": [{"text": "", ...}]
    #   that the schema (CriterionEvidence.text min_length=1) rejects.
    # - a1_v4: methodological softening on C5. The previous wording
    #   ("le LG UniCT richiedono distinzione culturali/formali e
    #   gradazione utili/importanti/indispensabili") was too strong:
    #   the LG UniCT use language like "è opportuno"/"raccomandato".
    #   The anchor C5=1 is no longer triggered by absence of the
    #   gradation alone: prerequisites already specific and useful to
    #   the student can earn score=2 even without the explicit
    #   gradation. Score=1 now means "generic topic areas, of limited
    #   help to the student" — independent of the gradation question.
    # - a1_v5 (Phase 5.4.J): re-tightened C5 to fix a systematic drift
    #   observed in the E2E calibration (5.4.I) — C5 = 1 → 2 on 3/4
    #   non-NA syllabi. Score=2 now explicitly requires both specificity
    #   AND a distinction between conoscenze culturali/generali and
    #   disciplinari/specialistiche (or equivalent clearly separable
    #   organisation). Score=1 means "specific but without that
    #   distinction"; score=0 covers absent / generic / tautological
    #   prerequisites. The advisory paragraph for C5 in
    #   ``A1_SPECIFIC_INSTRUCTIONS`` was updated for internal
    #   consistency with the new anchors. C1 and C2 are unchanged.
    # - a1_v6: targeted C5 recalibration after the LM-18 validation
    #   showed zero variance (30/30 C5=1). Score=2 no longer requires
    #   the explicit culturali/disciplinari distinction; it rewards
    #   prerequisites that are specific and operationally useful for
    #   student self-assessment. The distinction and utili/importanti/
    #   indispensabili gradation remain positive signals, not hard gates.
    prompt_version = "a1_v6"

    # D030.bis: A1 needs more headroom than the global 8192 budget on
    # the longest LM-18 syllabi (e.g. Machine Learning triggered a
    # MAX_TOKENS truncation in 5.4.I). The override is a runtime
    # parameter, NOT a change of ``prompt_version`` on its own — the
    # version bumped to a1_v5 separately because the prompt text was
    # also modified. The override is captured in
    # ``execution_metadata.max_output_tokens`` of every A1 run.
    max_output_tokens_override = 16384

    def __init__(self, retriever: Any, llm_client: Any) -> None:
        super().__init__(
            retriever=retriever,
            llm_client=llm_client,
            prompt_builder=build_a1_prompt,
        )

    def get_relevant_syllabus_fields(self, syllabus: Any) -> dict[str, Any]:
        """Return the A1-relevant subset of the syllabus.

        Empty / null values are preserved for the obligatory sections
        because their absence is the signal A1 needs to score C1 and
        C2. Fields not in :data:`A1_RELEVANT_FIELDS` are dropped.

        Accepts either an SQLAlchemy ``Syllabus`` row or a plain dict
        (used in tests and prompt-compilation utilities).
        """
        out: dict[str, Any] = {}
        for field in A1_RELEVANT_FIELDS:
            if isinstance(syllabus, dict):
                value = syllabus.get(field)
            else:
                value = getattr(syllabus, field, None)
            out[field] = _coerce(value)
        return out


def _coerce(value: Any) -> Any:
    """Coerce a syllabus field to a JSON-serialisable primitive.

    SQLAlchemy returns ``schedule_*`` as ``list | None`` and string
    fields as ``str | None``. We pass primitives and lists through;
    anything else is stringified so the prompt JSON dump never fails.
    """
    if value is None or isinstance(value, (str, bool, int, float, list, dict)):
        return value
    return str(value)
