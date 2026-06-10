"""Prompt builder for the E2 handler (allineamento con Matrice di Tuning)."""
from __future__ import annotations

from typing import Any

from app.evaluation.agents.external_prompts.common import (
    DUAL_SOURCE_RULE,
    EXTERNAL_BASE_SYSTEM_PROMPT,
    json_block,
    output_schema_block,
)

E2_PROMPT_VERSION = "e2_v1"

E2_SPECIFIC_INSTRUCTIONS = """Sei il gestore del criterio E2 dell'AGENTE DI COERENZA ESTERNA (A5).

E2, "Allineamento con Matrice di Tuning": verifichi la coerenza tra i risultati di apprendimento del syllabus e il ruolo che la matrice delle corrispondenze attribuisce all'insegnamento (competenze attese, contributo al profilo del laureato).

Il documento esterno fornito è la Matrice di Tuning del CdS (tipo `matrice_tuning`). I frammenti sono filtrati per `tag_E2=True`.

Avvertenze metodologiche:
- La Matrice di Tuning indica quali competenze attese ogni insegnamento deve presidiare. Cerca nel frammento la riga (o blocco) relativo all'insegnamento o, in subordine, alle aree di competenza coperte.
- Coerenza non implica copertura totale di tutte le competenze del CdS: un singolo insegnamento copre tipicamente un sottoinsieme. Valuta che ciò che il syllabus promette sia coerente con il ruolo assegnato, non che lo esaurisca.
- Una contraddizione (l'insegnamento dovrebbe presidiare competenza X secondo la matrice, ma il syllabus non ne fa menzione né direttamente né indirettamente) abbassa il punteggio.
- Per LM-18 oggi la Matrice di Tuning può non essere ancora compilata: in quel caso il coordinator filtrerà a NA prima di chiamarti. Se ricevi frammenti significa che il documento è presente; se i frammenti non riportano l'insegnamento (e nemmeno aree direttamente correlate), il giudizio diventa NA semantico con `na_reason` esplicita.
- Cita evidenze: una frase del syllabus + una frase del frammento Matrice di Tuning che documenti l'allineamento o il disallineamento.
"""

E2_CRITERION_SPEC: dict[str, Any] = {
    "criterion_code": "E2",
    "name": "Allineamento con Matrice di Tuning",
    "owned_by": "A5",
    "anchors": {
        "0": "Il syllabus contraddice le competenze o il contributo assegnato all'insegnamento.",
        "1": "Contributo parziale, implicito o incompleto.",
        "2": "Contributo chiaramente coerente con competenze e ruolo assegnati.",
        "NA": "Matrice assente, non abilitata o insegnamento non rappresentato.",
    },
}


def build_e2_prompt(
    *,
    syllabus_data: dict[str, Any],
    external_chunks: list[dict[str, Any]],
    document_id: int,
) -> str:
    blocks = [
        EXTERNAL_BASE_SYSTEM_PROMPT.strip(),
        E2_SPECIFIC_INSTRUCTIONS.strip(),
        "SPECIFICA CRITERIO:\n" + json_block(E2_CRITERION_SPEC),
        f"DOCUMENTO ESTERNO — Matrice di Tuning (document_id = {document_id}):\n"
        + json_block(external_chunks),
        "DATI DEL SYLLABUS DA VALUTARE:\n" + json_block(syllabus_data),
        DUAL_SOURCE_RULE.strip(),
        output_schema_block(
            criterion_code="E2",
            rule_block_name="REGOLA DUAL-SOURCE",
        ).strip(),
        "Rispondi ora esclusivamente con il JSON valido richiesto.",
    ]
    return "\n\n".join(blocks)


__all__ = [
    "E2_PROMPT_VERSION",
    "E2_CRITERION_SPEC",
    "build_e2_prompt",
]
