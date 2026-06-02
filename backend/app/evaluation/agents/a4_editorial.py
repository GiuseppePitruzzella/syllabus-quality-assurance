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
    prompt_version = "a4_v2"

    def __init__(self, retriever: Any, llm_client: Any) -> None:
        super().__init__(
            retriever=retriever,
            llm_client=llm_client,
            prompt_builder=build_a4_prompt,
        )

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
            out[field] = _coerce(value)
        return out


def _coerce(value: Any) -> Any:
    """Coerce a syllabus field to a JSON-serialisable primitive."""
    if value is None or isinstance(value, (str, bool, int, float, list, dict)):
        return value
    return str(value)
