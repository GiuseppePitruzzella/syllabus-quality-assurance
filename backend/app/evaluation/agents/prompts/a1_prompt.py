"""Prompt builder for A1 CompletenessAgent."""
from __future__ import annotations

import json
from typing import Any

from app.evaluation.agents.english_coverage import english_coverage, suggest_c2
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
- Per C2 (completezza bilingue) usa il blocco "PRE-CHECK DETERMINISTICO COPERTURA INGLESE": la matrice "english_coverage" indica, con calcolo deterministico, quali campi inglesi sono presenti, e "suggested_c2" è lo score suggerito. Adotta "suggested_c2" come punteggio C2, salvo evidenza testuale chiara nel syllabus che la matrice è errata; se ti discosti, indica nella justification quale campo e perché. Regola: C2=2 se le tre sezioni informative inglesi (risultati di apprendimento, contenuti, modalità di verifica) sono presenti; C2=1 se ne sono presenti 1 o 2; C2=0 se nessuna è presente o c'è solo il titolo. Il titolo inglese ("course_name_en") è diagnostico ma NON bloccante: la sua sola assenza non abbassa C2. NON penalizzare C2 per stile, refusi, formulazioni migliorabili o qualità dell'inglese: quegli aspetti appartengono a C9 (o a E4 per l'equivalenza semantica IT/EN). C2 valuta solo la presenza del perimetro minimo bilingue.
- Per C5: l'assenza dei prerequisiti è punteggio 0, NON NA. Un elenco nudo di codici o nomi di insegnamenti, senza indicare le conoscenze richieste, resta 0. Il punteggio 1 copre prerequisiti presenti ma ancora poco operativi per lo studente: aree molto generiche, nomi di insegnamenti con scarso dettaglio, oppure conoscenze specifiche ma senza livello atteso / priorità / contesto d'uso. Il punteggio 2 richiede prerequisiti specifici, formulati come conoscenze o abilità effettivamente utili allo studente per autovalutarsi. La distinzione tra prerequisiti culturali/generali e disciplinari/specialistici, o la gradazione utili/importanti/indispensabili, sono segnali positivi ma NON sono condizioni obbligatorie per il punteggio massimo se la formulazione è già specifica e operativa.
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
            "0": "Nessuna delle 3 sezioni informative inglesi (risultati di apprendimento, contenuti, modalità di verifica) presente: versione inglese assente o limitata al solo titolo.",
            "1": "1 o 2 delle 3 sezioni informative inglesi presenti (copertura parziale).",
            "2": "Tutte e 3 le sezioni informative inglesi presenti. Il titolo inglese è diagnostico, non bloccante.",
        },
    },
    {
        "criterion_code": "C5",
        "name": "Chiarezza dei prerequisiti",
        "owned_by": "A1",
        "anchors": {
            "0": "Prerequisiti assenti, tautologici, o formulati solo come codici/nomi di insegnamenti senza indicare le conoscenze richieste.",
            "1": "Prerequisiti presenti ma parzialmente operativi: aree molto generiche, nomi di insegnamenti con scarso dettaglio, oppure conoscenze specifiche senza livello atteso / priorità / contesto d'uso.",
            "2": "Prerequisiti specifici e utili all'autovalutazione dello studente: indicano conoscenze o abilità richieste con sufficiente granularità; la distinzione culturali/disciplinari o la gradazione utili/importanti/indispensabili rafforzano il giudizio ma non sono obbligatorie.",
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
- Ogni "evidences[i].text" DEVE essere una stringa NON vuota. Se non hai testo letterale da citare (per esempio perché un campo del syllabus è assente o vuoto), descrivi l'assenza nella "justification" e LASCIA "evidences" come lista vuota []. NON inserire MAI evidenze con "text": "".
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
    coverage = english_coverage(data.syllabus_data)
    precheck = {"english_coverage": coverage, "suggested_c2": suggest_c2(coverage)}
    return "\n\n".join(
        [
            BASE_SYSTEM_PROMPT.strip(),
            A1_SPECIFIC_INSTRUCTIONS.strip(),
            "SPECIFICHE CRITERI:\n" + _json_block(criteria_specs),
            "DATI DEL SYLLABUS DA VALUTARE:\n" + _json_block(data.syllabus_data),
            "PRE-CHECK DETERMINISTICO COPERTURA INGLESE (per C2):\n" + _json_block(precheck),
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
