"""Prompt builder for A1 CompletenessAgent."""
from __future__ import annotations

import json
from typing import Any

from app.evaluation.agents.prompts.base import BASE_SYSTEM_PROMPT
from app.evaluation.agents.schemas import AgentInput

A1_SPECIFIC_INSTRUCTIONS = """Sei l'AGENTE DI COMPLETEZZA DOCUMENTALE (A1).
Il tuo focus è verificare la presenza e completezza delle informazioni nel syllabus.

Valuti tre criteri della rubrica:
- C1, completezza strutturale e documentale.
- C2, completezza bilingue.
- C5, chiarezza dei prerequisiti.

Gli anchor di punteggio per ciascun criterio sono nel blocco "SPECIFICHE CRITERI" più avanti. Usali come unico riferimento per assegnare 0, 1 o 2.

Avvertenze specifiche per A1:
- Le 9 sezioni obbligatorie da verificare per C1 sono: RA (risultati di apprendimento), PR (prerequisiti), CN (contenuti del corso), MV (modalità di verifica), ED (esempi domande), TD (testi/riferimenti), MS (modalità di svolgimento e metodi didattici), MF (modalità di frequenza), PRG (programmazione).
- Per C2 il perimetro minimo bilingue è: titolo del corso, risultati di apprendimento, contenuti, modalità di verifica. Il flag "has_english" non basta: verifica i campi "_en" effettivi nel syllabus.
- Per C5: l'assenza dei prerequisiti è punteggio 0, NON NA. Un elenco nudo di codici di esami è 0; aree tematiche generiche senza gradazione sono 1; conoscenze e abilità specifiche con distinzione culturali/formali e gradazione utili/importanti/indispensabili sono 2.
- Quando un campo del syllabus è presente nei DATI DEL SYLLABUS ma vuoto (stringa vuota o null), considera la sezione assente. Questo NON è NA: è informazione utile per il punteggio (0 o 1).
"""

A1_CRITERIA_SPECS: list[dict[str, Any]] = [
    {
        "criterion_code": "C1",
        "name": "Completezza strutturale e documentale",
        "owned_by": "A1",
        "anchors": {
            "0": "Mancano 3 o più sezioni, o più sezioni sono presenti solo come intestazione vuota.",
            "1": "Manca 1 o 2 sezioni, o alcune sezioni sono compilate in modo puramente nominale.",
            "2": "Tutte le sezioni sono presenti e compilate con contenuto sostanziale.",
        },
    },
    {
        "criterion_code": "C2",
        "name": "Completezza bilingue",
        "owned_by": "A1",
        "anchors": {
            "0": "Versione inglese assente o limitata al solo titolo.",
            "1": "Versione inglese parziale: copre alcune ma non tutte le sezioni minime.",
            "2": "Versione inglese presente per titolo, risultati di apprendimento, contenuti e modalità di verifica.",
        },
    },
    {
        "criterion_code": "C5",
        "name": "Chiarezza dei prerequisiti",
        "owned_by": "A1",
        "anchors": {
            "0": "Prerequisiti assenti, o espressi solo come elenco di codici di esami.",
            "1": "Prerequisiti generici, senza gradazione né distinzione culturali/formali.",
            "2": "Prerequisiti specifici e utili allo studente, con distinzione/gradazione quando rilevante.",
        },
    },
]

A1_OUTPUT_SCHEMA_INSTRUCTIONS = """SCHEMA OUTPUT JSON (forma, non valori da copiare):
{
  "judgments": [
    {
      "criterion_code": "C1",
      "score": <0 | 1 | 2 | null>,
      "is_na": <true | false>,
      "na_reason": <string | null>,
      "justification": <string in italiano, almeno 2 frasi>,
      "evidences": [
        {"text": <citazione letterale dal syllabus>, "source_field": <nome_campo>}
      ],
      "confidence": <"low" | "medium" | "high">
    },
    { "criterion_code": "C2", ... },
    { "criterion_code": "C5", ... }
  ]
}

I valori che vedi sono PLACEHOLDER: non vanno copiati, ma sostituiti con la tua valutazione concreta.

Vincoli sull'output:
- Devi restituire esattamente tre giudizi, uno per C1, uno per C2 e uno per C5.
- Se is_na è false, score deve essere 0, 1 o 2 e na_reason deve essere null.
- Se is_na è true, score deve essere null e na_reason deve spiegare il problema tecnico.
- Per C2, l'assenza della versione inglese non è NA: è score 0.
- evidences deve contenere solo citazioni letterali dal SYLLABUS (mai dal contesto normativo).
"""


def build_a1_prompt(agent_input: AgentInput | dict[str, Any]) -> str:
    """Build the complete prompt for A1 from standardized agent input.

    Block order (criterion -> object -> context -> output contract):
    1. BASE_SYSTEM_PROMPT       — role, rules, perimeter, scale, NA, confidence
    2. A1_SPECIFIC_INSTRUCTIONS — A1 role + per-criterion warnings (no anchors)
    3. SPECIFICHE CRITERI       — structured anchors (single source of truth)
    4. SYLLABUS DA VALUTARE     — A1-relevant syllabus fields
    5. CONTESTO NORMATIVO       — RAG chunks (used to interpret criteria)
    6. SCHEMA OUTPUT JSON       — output contract with neutral placeholder example
    7. closing                  — one-line directive to emit JSON only
    """
    data = _coerce_agent_input(agent_input)
    criteria_specs = data.criteria_specs or A1_CRITERIA_SPECS
    return "\n\n".join(
        [
            BASE_SYSTEM_PROMPT.strip(),
            A1_SPECIFIC_INSTRUCTIONS.strip(),
            "SPECIFICHE CRITERI:\n" + _json_block(criteria_specs),
            "DATI DEL SYLLABUS DA VALUTARE:\n" + _json_block(data.syllabus_data),
            "CONTESTO NORMATIVO RECUPERATO VIA RAG:\n" + _json_block(data.normative_context),
            A1_OUTPUT_SCHEMA_INSTRUCTIONS.strip(),
            "Rispondi ora esclusivamente con il JSON valido richiesto.",
        ]
    )


def _coerce_agent_input(agent_input: AgentInput | dict[str, Any]) -> AgentInput:
    if isinstance(agent_input, AgentInput):
        return agent_input
    return AgentInput.model_validate(agent_input)


def _json_block(value: Any) -> str:
    return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n```"
