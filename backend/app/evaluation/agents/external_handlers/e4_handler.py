"""E4 handler — Coerenza cross-lingua del syllabus.

E4 is unique among the extended criteria: it consults NO external
documents. Evidence is built strictly from IT/EN paired prefixes
of the syllabus itself.

Phase 9.F.2 (e4_v2) refactor
----------------------------

The targeted_v1 campaign uncovered that pre-filtering the LLM
payload to *only* paired prefixes blinded the model to legitimate
omissions: a section that existed in IT but had no EN counterpart
was simply absent from the prompt, so the model gave Advanced
Computer Graphics E4=2 even though ``course_content_en`` was
empty.

The refactor introduces :class:`E4FieldPartition` from
:mod:`app.evaluation.agents.external_prompts.e4_prompt`, a typed
four-way breakdown built by :func:`_partition_prefixes`. The
prompt receives:

  * paired fields (both sides substantial) — unchanged from v1;
  * asymmetric prefixes split by substantiality of the populated
    side, so the e4_v2 threshold rule can apply.

The pre-LLM semantic NA path is preserved: if no prefix has
substantial content on both sides, the handler returns a semantic
NA *before* calling the LLM, with the same justification as v1.
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
    E4FieldPartition,
    E4PrefixOmission,
    build_e4_prompt,
)
from app.evaluation.agents.external_schemas import (
    ExtendedCriterionCode,
    ExtendedCriterionJudgment,
)

# Fields E4 considers: every prefix that has both an IT and an EN
# variant in the Syllabus model. Membership in this list does NOT
# guarantee the EN side is populated for a given syllabus — the
# pre-LLM check filters down to actually-paired-substantial fields.
E4_PAIRED_PREFIXES: tuple[str, ...] = (
    "course_name",
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


# ---------------------------------------------------------------------------
# Substantiality rule (Phase 9.F.2 e4_v2)
# ---------------------------------------------------------------------------

# Placeholder literals — case-insensitive — that should NOT count
# as substantial content even when their length is short. The set
# is comprehensive but not arbitrary; each entry corresponds to a
# pattern actually observed on the LM-18 corpus or to a generic
# "to-be-filled" marker we want to silently filter out.
_PLACEHOLDER_LITERALS: frozenset[str] = frozenset(
    {
        "n/a", "na", "n.a.", "n.a", "n/d", "n.d.", "n.d",
        "-", "—", "–", "*",
        "nessuno", "nessuna",
        "non applicabile", "non specificato", "non specificata",
        "to be defined", "tbd", "to be announced", "tba",
        "italiano", "inglese", "italian", "english",
        "none", "null", "nil",
        "...", "…",
        "vedi sopra", "vedi sotto", "see above", "see below",
    },
)

# Characters stripped at both ends of a value before the
# placeholder membership test runs.
_BORDER_PUNCT = " \t\n\r-—–:;.,!?()[]{}\"'`*_/\\"

# Substantiality thresholds: a value counts as substantial iff
# either the character count or the word count exceeds the
# threshold (OR — keeps short-but-meaningful Italian sentences
# like "La frequenza non è obbligatoria" in scope).
_SUBSTANTIAL_MIN_CHARS = 30
_SUBSTANTIAL_MIN_WORDS = 5


def _is_substantial(value: Any) -> bool:
    """Decide whether ``value`` counts as substantial bilingual content.

    Phase 9.F.2 alignment rule:

      1. ``None``, non-string, whitespace-only -> not substantial.
      2. Known placeholders (``N/A``, ``-``, ``nessuno``, language
         markers like ``Italiano``, ``-``, ``...``, etc.) -> not
         substantial. Comparison is case-insensitive after stripping
         border punctuation.
      3. Otherwise substantial iff
         ``len(stripped) >= 30`` OR
         ``word_count >= 5``.
         The OR keeps short Italian sentences in scope (e.g.
         "La frequenza non è obbligatoria") without inflating the
         omission count via placeholders.
    """
    if value is None or not isinstance(value, str):
        return False
    stripped = value.strip()
    if not stripped:
        return False
    if _normalize_for_placeholder_check(stripped) in _PLACEHOLDER_LITERALS:
        return False
    word_count = sum(1 for w in stripped.split() if w)
    return (
        len(stripped) >= _SUBSTANTIAL_MIN_CHARS
        or word_count >= _SUBSTANTIAL_MIN_WORDS
    )


def _normalize_for_placeholder_check(value: str) -> str:
    """Lowercase + strip border punctuation for placeholder lookup."""
    return value.strip().strip(_BORDER_PUNCT).lower()


def _has_any_content(value: Any) -> bool:
    """Return True when ``value`` is a non-empty string of any kind."""
    if value is None or not isinstance(value, str):
        return False
    return bool(value.strip())


def _partition_prefixes(
    syllabus: Any, prefixes: tuple[str, ...],
) -> E4FieldPartition:
    """Bucket every E4 prefix into the typed four-way breakdown.

    Each prefix lands in exactly one bucket:

      - paired_fields: both IT and EN sides substantial.
      - it_only_substantial: IT substantial, EN missing OR
        non-substantial (placeholder, < threshold).
      - en_only_substantial: EN substantial, IT missing OR
        non-substantial.
      - it_only_non_substantial: IT has *some* content but it's
        below the substantiality threshold AND EN is empty.
      - en_only_non_substantial: symmetric of the above.

    Prefixes where both sides are empty (or both are present but
    non-substantial) are silently dropped — they don't represent
    omissions, they represent "section not populated at all".
    """
    paired: dict[str, Any] = {}
    it_sub: list[E4PrefixOmission] = []
    en_sub: list[E4PrefixOmission] = []
    it_non_sub: list[str] = []
    en_non_sub: list[str] = []

    for prefix in prefixes:
        it_field = f"{prefix}_it"
        en_field = f"{prefix}_en"
        it_value = _get(syllabus, it_field)
        en_value = _get(syllabus, en_field)

        it_is_sub = _is_substantial(it_value)
        en_is_sub = _is_substantial(en_value)
        it_present = _has_any_content(it_value)
        en_present = _has_any_content(en_value)

        if it_is_sub and en_is_sub:
            paired[it_field] = it_value
            paired[en_field] = en_value
        elif it_is_sub:
            # IT substantial; EN absent or non-substantial. Either way
            # it's an omission on the EN side.
            it_sub.append(
                E4PrefixOmission(
                    prefix=prefix, field=it_field, content=str(it_value).strip(),
                ),
            )
        elif en_is_sub:
            # EN substantial; IT absent or non-substantial.
            en_sub.append(
                E4PrefixOmission(
                    prefix=prefix, field=en_field, content=str(en_value).strip(),
                ),
            )
        elif it_present and not en_present:
            it_non_sub.append(prefix)
        elif en_present and not it_present:
            en_non_sub.append(prefix)
        # else: both empty (no content at all) → silently dropped.

    return E4FieldPartition(
        paired_fields=paired,
        it_only_substantial=tuple(it_sub),
        en_only_substantial=tuple(en_sub),
        it_only_non_substantial=tuple(it_non_sub),
        en_only_non_substantial=tuple(en_non_sub),
    )


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


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
        partition = _partition_prefixes(syllabus, E4_PAIRED_PREFIXES)
        if partition.paired_prefix_count == 0:
            # Pre-LLM check fails: no prefix has substantial content
            # on both sides. SEMANTIC NA — "perimetro EN inadeguato".
            return self._semantic_na_result(started=started)
        prompt = build_e4_prompt(partition=partition)
        judgment = self._call_llm_with_retry(prompt)
        return HandlerResult(
            judgment=judgment,
            retrieved_chunks=[],
            prompt_version=self.prompt_version,
            retry_count=self._last_retry_count,
            execution_metadata=self._execution_metadata_base(started=started)
            | {
                "paired_prefixes_count": partition.paired_prefix_count,
                "it_only_substantial_count": len(partition.it_only_substantial),
                "en_only_substantial_count": len(partition.en_only_substantial),
                "it_only_non_substantial_count": len(
                    partition.it_only_non_substantial,
                ),
                "en_only_non_substantial_count": len(
                    partition.en_only_non_substantial,
                ),
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
                "sostanziale valutabile su entrambe le versioni."
            ),
            justification=(
                "Il syllabus non espone alcun campo bilingue con contenuto "
                "sostanziale su entrambe le versioni IT ed EN. Senza almeno "
                "una coppia confrontabile, qualsiasi giudizio numerico sarebbe "
                "arbitrario, quindi il criterio è dichiarato NA semantico."
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


def _get(syllabus: Any, field: str) -> Any:
    if isinstance(syllabus, dict):
        return syllabus.get(field)
    return getattr(syllabus, field, None)


__all__ = [
    "E4Handler",
    "E4_PAIRED_PREFIXES",
    "_is_substantial",
    "_partition_prefixes",
]
