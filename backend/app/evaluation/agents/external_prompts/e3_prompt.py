"""Prompt builder for the E3 handler (coerenza con Regolamento didattico)."""
from __future__ import annotations

from typing import Any

from app.evaluation.agents.external_prompts.common import (
    DUAL_SOURCE_RULE,
    EXTERNAL_BASE_SYSTEM_PROMPT,
    json_block,
    output_schema_block,
)

E3_PROMPT_VERSION = "e3_v1"

E3_SPECIFIC_INSTRUCTIONS = """Sei il gestore del criterio E3 dell'AGENTE DI COERENZA ESTERNA (A5).

E3, "Coerenza con Regolamento didattico": verifichi che programma, CFU, prerequisiti e modalità di verifica del syllabus siano coerenti con il Regolamento didattico del Corso di Studio.

Il documento esterno fornito è il Regolamento didattico del CdS (tipo `regolamento_didattico`). I frammenti sono filtrati per `tag_E3=True`. Quando un'indicazione del regolamento è applicabile all'insegnamento (es. CFU previsti, propedeuticità, modalità di verifica raccomandate, vincoli di programma), il syllabus deve rispettarla.

Avvertenze metodologiche:
- Un Regolamento didattico non esaurisce mai i contenuti di un insegnamento: aspetti non normati dal regolamento NON penalizzano il syllabus.
- Una contraddizione esplicita (CFU dichiarati nel syllabus diversi da quelli previsti dal regolamento; modalità di verifica che violano un vincolo esplicito; prerequisiti che ignorano una propedeuticità prevista) abbassa il punteggio.
- Coerenza non significa che il syllabus debba citare il regolamento: la coerenza è sostanziale, non testuale.
- Se i frammenti forniti non contengono indicazioni applicabili all'insegnamento (es. il regolamento parla solo di organizzazione generale del CdS), il giudizio diventa NA semantico con `na_reason` esplicita.
- Cita evidenze: una frase del syllabus + una frase del frammento Regolamento didattico che documenti la coerenza o l'incoerenza.
"""

E3_CRITERION_SPEC: dict[str, Any] = {
    "criterion_code": "E3",
    "name": "Coerenza con Regolamento didattico",
    "owned_by": "A5",
    "anchors": {
        "0": "Contraddice vincoli o indicazioni esplicite applicabili.",
        "1": "Generalmente compatibile, ma presenta ambiguità, incompletezze o divergenze parziali.",
        "2": "Coerente con tutte le indicazioni esplicite applicabili.",
        "NA": "Regolamento assente, non abilitato o senza indicazioni pertinenti.",
    },
}


def build_e3_prompt(
    *,
    syllabus_data: dict[str, Any],
    external_chunks: list[dict[str, Any]],
    document_id: int,
) -> str:
    blocks = [
        EXTERNAL_BASE_SYSTEM_PROMPT.strip(),
        E3_SPECIFIC_INSTRUCTIONS.strip(),
        "SPECIFICA CRITERIO:\n" + json_block(E3_CRITERION_SPEC),
        f"DOCUMENTO ESTERNO — Regolamento didattico (document_id = {document_id}):\n"
        + json_block(external_chunks),
        "DATI DEL SYLLABUS DA VALUTARE:\n" + json_block(syllabus_data),
        DUAL_SOURCE_RULE.strip(),
        output_schema_block(
            criterion_code="E3",
            rule_block_name="REGOLA DUAL-SOURCE",
        ).strip(),
        "Rispondi ora esclusivamente con il JSON valido richiesto.",
    ]
    return "\n\n".join(blocks)


__all__ = [
    "E3_PROMPT_VERSION",
    "E3_CRITERION_SPEC",
    "build_e3_prompt",
]
