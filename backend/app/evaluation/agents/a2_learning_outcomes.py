"""A2 — Agente dei risultati di apprendimento e descrittori (C3, C4).

Evaluates the formulation of the learning outcomes (C3) and their
articulation across the five Dublin descriptors (C4). Mirrors the
shape of CompletenessAgent: only the agent-specific responsibility
(syllabus field selection) lives here; the LLM call, retry loop and
JSON parsing live in BaseAgent.

The field selection is the union of:
- C3: course_name, has_english, learning_outcomes_it/en (RA narrative)
  plus the five dublin_*_it/en (RA structured by descriptor).
- C4: the five dublin_*_it/en (core), learning_outcomes_it/en (for
  coherence with the narrative).
- light context: teaching_methods_it/en, included so the agent can
  cross-check whether the declared didactic style fits the stated RA;
  the prompt is explicit that this is NOT a primary evidence source.

Empty / null values are preserved on purpose: an absent dublin_*
field is the signal A2 needs to score C4 down (per anchor 0/1).
"""
from __future__ import annotations

from typing import Any

from app.evaluation.agents.base import BaseAgent
from app.evaluation.agents.prompts.a2_prompt import (
    A2_RELEVANT_FIELDS,
    build_a2_prompt,
)


class PedagogicalAgent(BaseAgent):
    """A2 — Risultati di apprendimento e Descrittori di Dublino (C3, C4)."""

    agent_code = "A2"
    criteria_codes = ["C3", "C4"]
    # a2_v1: first version of the A2 prompt, calibrated against the
    # ScientificConfig.llm_max_output_tokens=8192 set in D030. Anchors
    # use soft normative wording ("le LG UniCT raccomandano") in line
    # with the methodological correction made on A1/C5 (a1_v4).
    prompt_version = "a2_v1"

    def __init__(self, retriever: Any, llm_client: Any) -> None:
        super().__init__(
            retriever=retriever,
            llm_client=llm_client,
            prompt_builder=build_a2_prompt,
        )

    def get_relevant_syllabus_fields(self, syllabus: Any) -> dict[str, Any]:
        """Return the A2-relevant subset of the syllabus.

        Empty / null values are preserved: an empty Dublin descriptor
        is exactly the signal A2 needs to score C4 down. Fields not
        in :data:`A2_RELEVANT_FIELDS` are dropped.

        Accepts either an SQLAlchemy ``Syllabus`` row or a plain dict.
        """
        out: dict[str, Any] = {}
        for field in A2_RELEVANT_FIELDS:
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
