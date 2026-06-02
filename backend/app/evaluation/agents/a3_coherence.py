"""A3 — Agente di coerenza didattico-valutativa (C6, C7, C8).

Evaluates the assessment methods (C6), the clarity of the course
content (C7) and the alignment between course content, teaching
methods, learning outcomes and assessment (C8).

Of the four agents, A3 owns the most transversal criterion: C8
requires looking simultaneously at the four planes
(RA / contenuti / metodi / verifica). The relevant-fields list is
therefore the largest, mirroring the breadth of the consistency
check.

As with A1 and A2, only the agent-specific responsibility (syllabus
field selection) lives here: the LLM call, the retry loop and the
JSON parsing are inherited from BaseAgent.
"""
from __future__ import annotations

from typing import Any

from app.evaluation.agents.base import BaseAgent
from app.evaluation.agents.prompts.a3_prompt import (
    A3_RELEVANT_FIELDS,
    build_a3_prompt,
)


class DidacticConsistencyAgent(BaseAgent):
    """A3 — Coerenza didattico-valutativa (C6, C7, C8)."""

    agent_code = "A3"
    criteria_codes = ["C6", "C7", "C8"]
    # a3_v1: first version of the A3 prompt, calibrated against the
    # ScientificConfig.llm_max_output_tokens=8192 set in D030. Anchors
    # use soft normative wording ("le LG UniCT raccomandano") in line
    # with the methodological correction made on A1/C5 (a1_v4) and A2.
    # C7 is intentionally soft on score=0 (a keyword list is C7=1, not
    # C7=0) and C8 score=2 is anchored to "evidenze testuali concrete"
    # to avoid rewarding inferred coherence.
    prompt_version = "a3_v1"

    def __init__(self, retriever: Any, llm_client: Any) -> None:
        super().__init__(
            retriever=retriever,
            llm_client=llm_client,
            prompt_builder=build_a3_prompt,
        )

    def get_relevant_syllabus_fields(self, syllabus: Any) -> dict[str, Any]:
        """Return the A3-relevant subset of the syllabus.

        The list is wide because C8 needs to compare four planes:
        learning outcomes, content, teaching methods, assessment.
        Empty / null values are preserved on purpose — an absent
        assessment_methods field is exactly the signal A3 needs to
        score C6 and C8 down.

        Accepts either an SQLAlchemy ``Syllabus`` row or a plain dict.
        """
        out: dict[str, Any] = {}
        for field in A3_RELEVANT_FIELDS:
            if isinstance(syllabus, dict):
                value = syllabus.get(field)
            else:
                value = getattr(syllabus, field, None)
            out[field] = _coerce(value)
        return out


def _coerce(value: Any) -> Any:
    """Coerce a syllabus field to a JSON-serialisable primitive."""
    if value is None or isinstance(value, (str, bool, int, float, list, dict)):
        return value
    return str(value)
