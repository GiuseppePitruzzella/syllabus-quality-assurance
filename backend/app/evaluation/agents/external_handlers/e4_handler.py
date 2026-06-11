"""E4 handler — Coerenza cross-lingua del syllabus.

E4 is unique among the extended criteria: it consults NO external
documents. Evidence is built strictly from IT/EN paired prefixes
of the syllabus itself, so the handler:

  * skips the retriever entirely;
  * performs a pre-LLM check that at least one paired prefix has
    non-empty content on both sides — if none exists, returns a
    SEMANTIC NA judgment directly (no LLM call) because "the EN
    perimeter is inadequate for comparison" is a meaningful
    finding, not a technical failure;
  * otherwise calls the LLM with the IT/EN payload restricted to
    the paired fields that actually have content.

The pre-LLM check is what distinguishes E4 from the dual-source
handlers: by the time we reach the LLM, the call is guaranteed to
have at least one comparable pair, which lets the paired-prefix
validator be a hard constraint on the response.
"""
from __future__ import annotations

import time
from typing import Any, ClassVar

from app.evaluation.agents.external_handlers.base import (
    ExternalHandler,
    HandlerResult,
)
from app.evaluation.agents.external_prompts.e4_prompt import (
    E4_PROMPT_VERSION,
    build_e4_prompt,
)
from app.evaluation.agents.external_schemas import (
    ExtendedCriterionCode,
    ExtendedCriterionJudgment,
)

# Fields E4 considers: every prefix that has both an IT and an EN
# variant in the Syllabus model. Membership in this list does NOT
# guarantee the EN side is populated for a given syllabus — the
# pre-LLM check filters down to actually-paired fields.
E4_PAIRED_PREFIXES: tuple[str, ...] = (
    "course_name",  # course_name has its own IT/EN representation via course_title_*
    "course_title",
    "learning_outcomes",
    "dublin_knowledge",
    "dublin_applying",
    "dublin_judgement",
    "dublin_communication",
    "dublin_learning",
    "prerequisites",
    "course_content",
    "assessment_methods",
)


class E4Handler(ExternalHandler):
    """Cross-lingua handler — syllabus-only, no retriever."""

    criterion_code: ClassVar[ExtendedCriterionCode] = "E4"
    prompt_version: ClassVar[str] = E4_PROMPT_VERSION

    def __init__(self, llm_client: Any) -> None:
        super().__init__(llm_client)

    def evaluate(
        self,
        *,
        syllabus: Any,
        cdl_id: int,
        document_ids: list[int],
    ) -> HandlerResult:
        started = time.time()
        paired_fields = _collect_paired_fields(syllabus, E4_PAIRED_PREFIXES)
        if not paired_fields:
            # Pre-LLM check fails: no paired prefix has content on
            # both sides. This is a SEMANTIC NA — the EN perimeter
            # is inadequate for cross-lingua comparison.
            return self._semantic_na_result(started=started)
        prompt = build_e4_prompt(syllabus_data=paired_fields)
        judgment = self._call_llm_with_retry(prompt)
        return HandlerResult(
            judgment=judgment,
            retrieved_chunks=[],
            prompt_version=self.prompt_version,
            retry_count=self._last_retry_count,
            execution_metadata=self._execution_metadata_base(started=started)
            | {
                "paired_prefixes_count": _count_prefixes(paired_fields),
                "retrieved_chunks_count": 0,
            },
        )

    def _semantic_na_result(self, *, started: float) -> HandlerResult:
        judgment = ExtendedCriterionJudgment(
            criterion_code="E4",
            score=None,
            is_na=True,
            is_na_technical=False,
            na_reason=(
                "Il perimetro inglese del syllabus è insufficiente per il "
                "confronto cross-lingua: nessuna coppia IT/EN con contenuto "
                "valutabile su entrambe le versioni."
            ),
            justification=(
                "Il syllabus non espone alcun campo bilingue con contenuto su "
                "entrambe le versioni IT ed EN. Senza almeno una coppia "
                "confrontabile, qualsiasi giudizio numerico sarebbe arbitrario, "
                "quindi il criterio è dichiarato NA semantico."
            ),
            evidences=[],
            confidence="high",
        )
        return HandlerResult(
            judgment=judgment,
            retrieved_chunks=[],
            prompt_version=self.prompt_version,
            retry_count=0,
            execution_metadata=self._execution_metadata_base(started=started)
            | {
                "paired_prefixes_count": 0,
                "retrieved_chunks_count": 0,
                "pre_llm_na": True,
            },
        )


def _collect_paired_fields(
    syllabus: Any, prefixes: tuple[str, ...],
) -> dict[str, Any]:
    """Return a dict containing both ``*_it`` and ``*_en`` for every
    prefix that has non-empty content on both sides. The result is
    safe to pass directly to :func:`build_e4_prompt`.
    """
    out: dict[str, Any] = {}
    for prefix in prefixes:
        it_field = f"{prefix}_it"
        en_field = f"{prefix}_en"
        it_value = _get(syllabus, it_field)
        en_value = _get(syllabus, en_field)
        if _has_content(it_value) and _has_content(en_value):
            out[it_field] = it_value
            out[en_field] = en_value
    # course_name is a virtual field; on the SQLAlchemy model it
    # often maps to course_title_*. If the model exposes either
    # representation, the above loop has picked it up.
    return out


def _count_prefixes(paired_fields: dict[str, Any]) -> int:
    return sum(1 for k in paired_fields if k.endswith("_it"))


def _get(syllabus: Any, field: str) -> Any:
    if isinstance(syllabus, dict):
        return syllabus.get(field)
    return getattr(syllabus, field, None)


def _has_content(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


__all__ = ["E4Handler", "E4_PAIRED_PREFIXES"]
