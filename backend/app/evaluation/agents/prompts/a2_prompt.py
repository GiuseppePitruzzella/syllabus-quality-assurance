"""Prompt builder for A2 PedagogicalAgent.

A2 evaluates two criteria:
- C3, formulazione dei risultati di apprendimento (RA).
- C4, articolazione secondo i Descrittori di Dublino.

A2 reads narrative learning outcomes plus the five Dublin descriptor
fields (knowledge / applying / judgement / communication / learning),
both IT and EN. ``teaching_methods_*`` is included as light context
(it can corroborate whether the RA are coherent with the declared
didactic style) but it must not be cited as the primary evidence
for either criterion.

Methodological note (cf. retrofit on A1/C5): when citing the
Linee Guida UniCT, prefer 'raccomandano' / 'è opportuno' over
'richiedono'. The five Dublin descriptors are an ANVUR / DM 1154
standard that the LG UniCT carry into the syllabus structure, so
their *presence* is a strong expectation, but the *quality* of the
formulation is a graded judgment.
"""
from __future__ import annotations

import json
from typing import Any

from app.evaluation.agents.prompts.base import BASE_SYSTEM_PROMPT
from app.evaluation.agents.schemas import AgentInput

A2_SPECIFIC_INSTRUCTIONS = """Sei l'AGENTE PEDAGOGICO (A2).
Il tuo focus è valutare la formulazione dei risultati di apprendimento attesi e la loro articolazione secondo i Descrittori di Dublino.

Valuti due criteri della rubrica:
- C3, formulazione dei risultati di apprendimento.
- C4, articolazione secondo i cinque Descrittori di Dublino.

Gli anchor di punteggio per ciascun criterio sono nel blocco "SPECIFICHE CRITERI" più avanti. Usali come unico riferimento per assegnare 0, 1 o 2.

Avvertenze specifiche per A2:
- I cinque Descrittori di Dublino sono: conoscenza e capacità di comprensione (campo "dublin_knowledge_*"); capacità di applicare conoscenza e comprensione (campo "dublin_applying_*"); autonomia di giudizio (campo "dublin_judgement_*"); abilità comunicative (campo "dublin_communication_*"); capacità di apprendimento (campo "dublin_learning_*"). I cinque descrittori sono uno standard del sistema italiano di accreditamento (DM 1154/2021, Linee Guida AVA 3 ANVUR) ripreso dalle Linee Guida UniCT per la compilazione del syllabus.
- Per C3, valuta la formulazione dei risultati di apprendimento attesi nel campo narrativo "learning_outcomes_*" e nei contenuti dei cinque descrittori. Formulazioni che descrivono il corso ("il corso copre X", "saranno presentate Y") sono punteggio 0; formulazioni in termini di apprendimento ma generiche ("lo studente acquisirà conoscenze") sono punteggio 1; formulazioni specifiche e verificabili in termini di conoscenze e abilità osservabili sono punteggio 2.
- Per C4, valuta presenza e articolazione dei cinque descrittori. Tutti e cinque praticamente assenti o costituiti da formulazioni minimali prive di contenuto sostanziale è punteggio 0; alcuni descrittori compilati ma con contenuti generici, ripetitivi o duplicati tra di essi è punteggio 1; tutti e cinque articolati con contenuti specifici e differenziati è punteggio 2. Le Linee Guida UniCT raccomandano una formulazione esplicita per ciascuno dei cinque descrittori.
- "teaching_methods_*" è incluso nel payload come CONTESTO LEGGERO. Può aiutarti a giudicare la coerenza tra metodi didattici dichiarati e risultati di apprendimento attesi, ma le evidenze principali per C3 e C4 devono venire dai campi "learning_outcomes_*" e "dublin_*_*". Non citare "teaching_methods_*" come unica evidenza.
- Quando un campo del syllabus è presente nei DATI DEL SYLLABUS ma vuoto, considera quel descrittore o RA come assente. Questo NON è NA: è informazione utile per il punteggio (0 o 1).
"""

A2_CRITERIA_SPECS: list[dict[str, Any]] = [
    {
        "criterion_code": "C3",
        "name": "Formulazione dei risultati di apprendimento",
        "owned_by": "A2",
        "anchors": {
            "0": "Risultati di apprendimento assenti o formulati come descrizione del corso ('il corso copre X', 'saranno presentate Y'). La descrizione dei contenuti non è un risultato di apprendimento.",
            "1": "Risultati di apprendimento espressi in termini di apprendimento ma generici, ripetitivi o poco verificabili (es. 'lo studente acquisirà conoscenze', 'lo studente sarà in grado di comprendere').",
            "2": "Risultati di apprendimento specifici, verificabili e formulati in termini di conoscenze e abilità osservabili. Le Linee Guida UniCT raccomandano l'uso di verbi d'azione concreti e la coerenza con il livello del CdS.",
        },
    },
    {
        "criterion_code": "C4",
        "name": "Articolazione secondo i Descrittori di Dublino",
        "owned_by": "A2",
        "anchors": {
            "0": "I cinque Descrittori di Dublino (knowledge_and_understanding, applying_knowledge, making_judgements, communication_skills, learning_skills) sono praticamente assenti o costituiti da formulazioni minimali prive di contenuto sostanziale.",
            "1": "Alcuni dei cinque Descrittori sono compilati, ma con contenuti generici, duplicati tra loro o non differenziati: il syllabus copre i Descrittori solo formalmente.",
            "2": "Tutti e cinque i Descrittori sono articolati con contenuti specifici e differenziati, coerenti con il livello del CdS e con i risultati di apprendimento dichiarati nel campo narrativo. Le Linee Guida UniCT raccomandano una formulazione esplicita per ciascuno dei cinque descrittori.",
        },
    },
]

# Fields A2 reads from the syllabus.
#
# Union of:
# - C3 (formulazione RA): course_name (titolo per contesto),
#   learning_outcomes_it/en (RA narrativi), the five dublin_*_it/en
#   (RA strutturati per i Descrittori), has_english (per stabilire
#   se considerare anche la versione EN).
# - C4 (Dublin Descriptors): the five dublin_*_it/en (cuore di C4)
#   plus learning_outcomes_it/en (per giudicare coerenza con i RA
#   narrativi), course_name e has_english.
# - light context: teaching_methods_it/en, can corroborate whether
#   the declared learning style fits the stated RA. NOT a primary
#   evidence source.
#
# Empty / null values are kept on purpose: an empty Dublin descriptor
# field is the signal A2 needs to score C4 down.
A2_RELEVANT_FIELDS: tuple[str, ...] = (
    "course_name",
    "has_english",
    # RA narrativi (C3 + C4 coerenza con narrativa)
    "learning_outcomes_it",
    "learning_outcomes_en",
    # I cinque Descrittori di Dublino (C3 strutturato + C4 cuore)
    "dublin_knowledge_it",
    "dublin_knowledge_en",
    "dublin_applying_it",
    "dublin_applying_en",
    "dublin_judgement_it",
    "dublin_judgement_en",
    "dublin_communication_it",
    "dublin_communication_en",
    "dublin_learning_it",
    "dublin_learning_en",
    # Light context (NOT primary evidence)
    "teaching_methods_it",
    "teaching_methods_en",
)


A2_OUTPUT_SCHEMA_INSTRUCTIONS = """SCHEMA OUTPUT JSON (forma, non valori da copiare):
{
  "judgments": [
    {
      "criterion_code": "C3",
      "score": <0 | 1 | 2 | null>,
      "is_na": <true | false>,
      "na_reason": <string | null>,
      "justification": <string in italiano, almeno 2 frasi>,
      "evidences": [
        {"text": <citazione letterale dal syllabus>, "source_field": <nome_campo>}
      ],
      "confidence": <"low" | "medium" | "high">
    },
    { "criterion_code": "C4", ... }
  ]
}

I valori che vedi sono PLACEHOLDER: non vanno copiati, ma sostituiti con la tua valutazione concreta.

Vincoli sull'output:
- Devi restituire esattamente due giudizi, uno per C3 e uno per C4.
- Se is_na è false, score deve essere 0, 1 o 2 e na_reason deve essere null.
- Se is_na è true, score deve essere null e na_reason deve spiegare il problema tecnico.
- Per C4, l'assenza dei Descrittori in inglese non basta a giustificare punteggi alti su C4: C4 valuta l'articolazione dei cinque descrittori indipendentemente dalla lingua. La completezza bilingue è valutata da C2 (non di tua competenza).
- evidences deve contenere solo citazioni letterali dal SYLLABUS (mai dal contesto normativo). Le evidenze principali per C3 e C4 devono venire da "learning_outcomes_*" e dai cinque "dublin_*_*"; "teaching_methods_*" può essere citato solo come supporto secondario.
- Ogni "evidences[i].text" DEVE essere una stringa NON vuota. Se non hai testo letterale da citare (per esempio perché un descrittore è assente o vuoto), descrivi l'assenza nella "justification" e LASCIA "evidences" come lista vuota []. NON inserire MAI evidenze con "text": "".
"""


def build_a2_prompt(agent_input: AgentInput | dict[str, Any]) -> str:
    """Build the complete prompt for A2 from standardized agent input.

    Block order mirrors A1 (criterion -> object -> context -> output contract):
    1. BASE_SYSTEM_PROMPT       — role, rules, perimeter, scale, NA, confidence
    2. A2_SPECIFIC_INSTRUCTIONS — A2 role + Dublin descriptors + warnings
    3. SPECIFICHE CRITERI       — structured anchors (single source of truth)
    4. SYLLABUS DA VALUTARE     — A2-relevant syllabus fields
    5. CONTESTO NORMATIVO       — RAG chunks (used to interpret criteria)
    6. SCHEMA OUTPUT JSON       — output contract with neutral placeholder example
    7. closing                  — one-line directive to emit JSON only
    """
    data = _coerce_agent_input(agent_input)
    criteria_specs = data.criteria_specs or A2_CRITERIA_SPECS
    return "\n\n".join(
        [
            BASE_SYSTEM_PROMPT.strip(),
            A2_SPECIFIC_INSTRUCTIONS.strip(),
            "SPECIFICHE CRITERI:\n" + _json_block(criteria_specs),
            "DATI DEL SYLLABUS DA VALUTARE:\n" + _json_block(data.syllabus_data),
            "CONTESTO NORMATIVO RECUPERATO VIA RAG:\n" + _json_block(data.normative_context),
            A2_OUTPUT_SCHEMA_INSTRUCTIONS.strip(),
            "Rispondi ora esclusivamente con il JSON valido richiesto.",
        ]
    )


def _coerce_agent_input(agent_input: AgentInput | dict[str, Any]) -> AgentInput:
    if isinstance(agent_input, AgentInput):
        return agent_input
    return AgentInput.model_validate(agent_input)


def _json_block(value: Any) -> str:
    return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n```"
