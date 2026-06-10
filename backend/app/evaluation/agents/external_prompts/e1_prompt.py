"""Prompt builder for the E1 handler (allineamento con SUA-CdS).

Anchors mirror :file:`frontend/src/data/rubric.ts` verbatim — the
rubric file is the single source of truth, the strings here are
quoted faithfully so the LLM sees the same scoring ladder the user
sees in the Settings page.
"""
from __future__ import annotations

from typing import Any

from app.evaluation.agents.external_prompts.common import (
    DUAL_SOURCE_RULE,
    EXTERNAL_BASE_SYSTEM_PROMPT,
    json_block,
    output_schema_block,
)

E1_PROMPT_VERSION = "e1_v1"

E1_SPECIFIC_INSTRUCTIONS = """Sei il gestore del criterio E1 dell'AGENTE DI COERENZA ESTERNA (A5).

E1, "Allineamento con SUA-CdS": verifichi la coerenza sostantiva tra i risultati di apprendimento del syllabus e i quadri A4.b.2 (risultati di apprendimento attesi) e A4.c (autonomia di giudizio, abilità comunicative, capacità di apprendimento) della Scheda Unica Annuale del Corso di Studio (SUA-CdS).

Il documento esterno fornito è la SUA-CdS del CdS a cui appartiene l'insegnamento (tipo `sua_cds`). I frammenti sono già stati filtrati per `tag_E1=True` lato retrieval.

Avvertenze metodologiche:
- Confronta i risultati del syllabus con quelli che la SUA-CdS prescrive a livello di CdS, non con quelli di altri insegnamenti.
- Allineamento non significa identità lessicale: un syllabus può dichiarare risultati formulati diversamente ma sostantivamente coerenti con i descrittori della SUA-CdS.
- Una contraddizione tra syllabus e SUA-CdS (es. il syllabus promette competenze che la SUA-CdS attribuisce a un altro insegnamento) abbassa il punteggio.
- Se i frammenti SUA-CdS forniti non riportano sezioni applicabili all'insegnamento (es. la SUA descrive solo obiettivi generali del CdS senza ricondurli a competenze concrete), il giudizio diventa NA semantico con `na_reason` esplicita.
- Cita evidenze concrete: una frase del syllabus + una frase del frammento SUA-CdS che documenti l'allineamento o il disallineamento.
"""

E1_CRITERION_SPEC: dict[str, Any] = {
    "criterion_code": "E1",
    "name": "Allineamento con SUA-CdS",
    "owned_by": "A5",
    "anchors": {
        "0": "Contraddizioni sostanziali o marcato disallineamento rispetto agli obiettivi e risultati applicabili della SUA-CdS.",
        "1": "Allineamento parziale o prevalentemente implicito, con lacune o tracciabilità debole.",
        "2": "Allineamento sostanziale e chiaramente tracciabile.",
        "NA": "SUA-CdS assente, non abilitata o priva di informazioni applicabili.",
    },
}


def build_e1_prompt(
    *,
    syllabus_data: dict[str, Any],
    external_chunks: list[dict[str, Any]],
    document_id: int,
) -> str:
    """Build the E1 prompt for one (syllabus, SUA-CdS document) pair.

    ``external_chunks`` is the list of retrieved chunks for this
    document, each shaped as
    ``{"chunk_id": str, "text": str, "metadata": dict, "similarity_score": float}``
    so the LLM can quote them by ``source_chunk_id`` and the schema
    validator can match the ``source_document_id`` against
    ``document_id``.
    """
    blocks = [
        EXTERNAL_BASE_SYSTEM_PROMPT.strip(),
        E1_SPECIFIC_INSTRUCTIONS.strip(),
        "SPECIFICA CRITERIO:\n" + json_block(E1_CRITERION_SPEC),
        f"DOCUMENTO ESTERNO — SUA-CdS (document_id = {document_id}):\n"
        + json_block(external_chunks),
        "DATI DEL SYLLABUS DA VALUTARE:\n" + json_block(syllabus_data),
        DUAL_SOURCE_RULE.strip(),
        output_schema_block(
            criterion_code="E1",
            rule_block_name="REGOLA DUAL-SOURCE",
        ).strip(),
        "Rispondi ora esclusivamente con il JSON valido richiesto.",
    ]
    return "\n\n".join(blocks)


__all__ = [
    "E1_PROMPT_VERSION",
    "E1_CRITERION_SPEC",
    "build_e1_prompt",
]
