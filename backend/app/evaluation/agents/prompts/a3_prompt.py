"""Prompt builder for A3 DidacticConsistencyAgent.

A3 evaluates three criteria:
- C6, modalità di verifica dell'apprendimento.
- C7, chiarezza dei contenuti del corso.
- C8, coerenza didattico-valutativa.

A3 is the most transversal of the three agents that own multiple
criteria: C8 in particular requires looking simultaneously at
contenuti, metodi didattici, modalità di verifica e RA per giudicare
l'allineamento. The payload therefore covers all the didactic
sections plus learning outcomes and Dublin descriptors as the RA
side of the consistency check.

Methodological notes (cf. retrofit on A1/C5 and review of A2):
- When citing the Linee Guida UniCT, prefer 'raccomandano' /
  'è opportuno' / 'coerente con' over 'richiedono'. The C6/C7/C8
  rubric is largely about quality and alignment, not about hard
  binary requirements.
- An introductory sentence framing the course (e.g. "lo scopo del
  corso è...") must NOT by itself lower the score: the anchors
  evaluate the actual content and alignment that follow.
"""
from __future__ import annotations

import json
from typing import Any

from app.evaluation.agents.prompts.base import BASE_SYSTEM_PROMPT
from app.evaluation.agents.schemas import AgentInput

A3_SPECIFIC_INSTRUCTIONS = """Sei l'AGENTE DI COERENZA DIDATTICO-VALUTATIVA (A3).
Il tuo focus è valutare la qualità della verifica dell'apprendimento, la chiarezza dei contenuti del corso e la coerenza fra contenuti, metodi didattici, risultati di apprendimento e modalità di verifica.

Valuti tre criteri della rubrica:
- C6, modalità di verifica dell'apprendimento.
- C7, chiarezza dei contenuti del corso.
- C8, coerenza didattico-valutativa.

Gli anchor di punteggio per ciascun criterio sono nel blocco "SPECIFICHE CRITERI" più avanti. Usali come unico riferimento per assegnare 0, 1 o 2.

Avvertenze specifiche per A3:
- Per C6, valuta i campi "assessment_methods_*" e "sample_questions_*". Una formula del tipo "esame finale orale" priva di dettagli su criteri di attribuzione del voto o esempi è punteggio 1; modalità chiare con criteri di attribuzione del voto, esempi di domande o rubriche sono punteggio 2; assenza o solo intestazione vuota è punteggio 0.
- Per C7, valuta i campi "course_content_*" e "schedule_*". Contenuti assenti o ridotti a poche etichette isolate (non sufficienti a capire cosa verrà trattato) è punteggio 0; contenuti presenti ma poco organizzati (elenco lineare di argomenti o parole chiave senza scansione tematica) è punteggio 1; contenuti articolati con organizzazione chiara, sezioni, progressione, schedule o struttura riconoscibile è punteggio 2.
- Per C8, valuta la coerenza fra: i risultati di apprendimento dichiarati (campi "learning_outcomes_*" e "dublin_*_*"), i metodi didattici ("teaching_methods_*"), i contenuti ("course_content_*", "schedule_*") e le modalità di verifica ("assessment_methods_*", "sample_questions_*"). Un forte disallineamento (es. RA che parlano di progettazione ma verifica solo a quiz a scelta multipla, o viceversa) è punteggio 0; allineamento parziale (alcune componenti coerenti, altre no) è punteggio 1; allineamento chiaro tra i quattro piani è punteggio 2.
- IMPORTANTE: una frase introduttiva descrittiva (del tipo "lo scopo del corso è fornire...", "il corso copre X") non deve da sola abbassare il punteggio. Quello che conta è la qualità dei contenuti e dell'allineamento che seguono. Considera l'INSIEME del campo, non solo l'apertura.
- Le Linee Guida UniCT raccomandano (non impongono) di esplicitare criteri di attribuzione del voto, esempi di domande, e una programmazione dettagliata. L'assenza di questi elementi può abbassare il punteggio rispetto al massimo, ma non lo determina da sola: contenuti e modalità di verifica già specifiche e coerenti possono ricevere 2 anche senza tutti gli elementi raccomandati.
- Quando un campo del syllabus è presente nei DATI DEL SYLLABUS ma vuoto, considera la sezione assente. Questo NON è NA: è informazione utile per il punteggio (0 o 1).
"""

A3_CRITERIA_SPECS: list[dict[str, Any]] = [
    {
        "criterion_code": "C6",
        "name": "Modalità di verifica dell'apprendimento",
        "owned_by": "A3",
        "anchors": {
            "0": "Modalità di verifica assenti o ridotte a una sola riga senza alcun dettaglio (es. 'esame finale' senza tipologia né criteri).",
            "1": "Modalità di verifica presenti ma generiche, senza criteri di attribuzione del voto né esempi di domande. La verifica è descritta a livello di tipologia (scritto, orale) ma non a livello di valutazione.",
            "2": "Modalità di verifica articolate: tipologia chiara, criteri di attribuzione del voto espliciti e/o esempi di domande pertinenti agli obiettivi del corso. Le Linee Guida UniCT raccomandano l'esplicitazione di criteri e/o rubriche di valutazione.",
        },
    },
    {
        "criterion_code": "C7",
        "name": "Chiarezza dei contenuti del corso",
        "owned_by": "A3",
        "anchors": {
            "0": "Contenuti assenti o ridotti a poche etichette isolate, non sufficienti a capire cosa verrà trattato nel corso.",
            "1": "Contenuti presenti ma poco organizzati: per esempio elenco lineare di argomenti o parole chiave senza scansione tematica.",
            "2": "Contenuti articolati con organizzazione chiara, sezioni, progressione, schedule o struttura riconoscibile. I contenuti sono coerenti con il livello del CdS e con gli obiettivi formativi dichiarati.",
        },
    },
    {
        "criterion_code": "C8",
        "name": "Coerenza didattico-valutativa",
        "owned_by": "A3",
        "anchors": {
            "0": "Forte disallineamento fra risultati di apprendimento, metodi didattici, contenuti e modalità di verifica: la verifica non misura quello che gli RA dichiarano, oppure i metodi didattici non supportano gli RA, oppure i contenuti sono scollegati dagli obiettivi.",
            "1": "Allineamento parziale: alcune componenti coerenti, altre no (es. contenuti allineati agli RA ma modalità di verifica non centrate, oppure il contrario).",
            "2": "Allineamento chiaro: i contenuti, i metodi didattici e le modalità di verifica concorrono in modo coerente al raggiungimento dei risultati di apprendimento dichiarati. Le Linee Guida UniCT raccomandano l'esplicitazione di questo allineamento; quando l'allineamento è ricostruibile da evidenze testuali concrete del syllabus, anche se non dichiarato in forma esplicita, il punteggio può essere 2.",
        },
    },
]

# Fields A3 reads from the syllabus.
#
# Union of:
# - C6 (verifica): assessment_methods_it/en, sample_questions_it/en.
# - C7 (contenuti): course_content_it/en, schedule_it/en.
# - C8 (coerenza didattico-valutativa): all of the above PLUS the RA
#   side (learning_outcomes_it/en, the five dublin_*_it/en) and
#   teaching_methods_it/en, so the agent can judge the alignment
#   across the four planes (RA / contenuti / metodi / verifica).
#
# Empty / null values are kept on purpose: an empty assessment_methods
# field is exactly the signal A3 needs to score C6 and C8 down.
A3_RELEVANT_FIELDS: tuple[str, ...] = (
    "course_name",
    "has_english",
    # RA side (needed for C8 alignment)
    "learning_outcomes_it",
    "learning_outcomes_en",
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
    # Contenuti (C7 + C8)
    "course_content_it",
    "course_content_en",
    "schedule_it",
    "schedule_en",
    # Metodi didattici (C8)
    "teaching_methods_it",
    "teaching_methods_en",
    # Modalità di verifica (C6 + C8)
    "assessment_methods_it",
    "assessment_methods_en",
    "sample_questions_it",
    "sample_questions_en",
)


A3_OUTPUT_SCHEMA_INSTRUCTIONS = """SCHEMA OUTPUT JSON (forma, non valori da copiare):
{
  "judgments": [
    {
      "criterion_code": "C6",
      "score": <0 | 1 | 2 | null>,
      "is_na": <true | false>,
      "na_reason": <string | null>,
      "justification": <string in italiano, almeno 2 frasi>,
      "evidences": [
        {"text": <citazione letterale dal syllabus>, "source_field": <nome_campo>}
      ],
      "confidence": <"low" | "medium" | "high">
    },
    { "criterion_code": "C7", ... },
    { "criterion_code": "C8", ... }
  ]
}

I valori che vedi sono PLACEHOLDER: non vanno copiati, ma sostituiti con la tua valutazione concreta.

Vincoli sull'output:
- Devi restituire esattamente tre giudizi, uno per C6, uno per C7 e uno per C8.
- Se is_na è false, score deve essere 0, 1 o 2 e na_reason deve essere null.
- Se is_na è true, score deve essere null e na_reason deve spiegare il problema tecnico.
- L'assenza dei contenuti in inglese non basta a determinare i punteggi di C6/C7/C8: la completezza bilingue è valutata da C2 (non di tua competenza).
- evidences deve contenere solo citazioni letterali dal SYLLABUS (mai dal contesto normativo). Per C8 (coerenza), le evidences possono attingere indistintamente a "learning_outcomes_*", "dublin_*_*", "course_content_*", "schedule_*", "teaching_methods_*", "assessment_methods_*", "sample_questions_*" purché il punto sia ancorato al testo del syllabus.
- Ogni "evidences[i].text" DEVE essere una stringa NON vuota. Se non hai testo letterale da citare (per esempio perché un campo è assente o vuoto), descrivi l'assenza nella "justification" e LASCIA "evidences" come lista vuota []. NON inserire MAI evidenze con "text": "".
"""


def build_a3_prompt(agent_input: AgentInput | dict[str, Any]) -> str:
    """Build the complete prompt for A3 from standardized agent input.

    Block order mirrors A1/A2:
    1. BASE_SYSTEM_PROMPT       — role, rules, perimeter, scale, NA, confidence
    2. A3_SPECIFIC_INSTRUCTIONS — A3 role + per-criterion warnings
    3. SPECIFICHE CRITERI       — structured anchors (single source of truth)
    4. SYLLABUS DA VALUTARE     — A3-relevant syllabus fields
    5. CONTESTO NORMATIVO       — RAG chunks (used to interpret criteria)
    6. SCHEMA OUTPUT JSON       — output contract with neutral placeholder example
    7. closing                  — one-line directive to emit JSON only
    """
    data = _coerce_agent_input(agent_input)
    criteria_specs = data.criteria_specs or A3_CRITERIA_SPECS
    return "\n\n".join(
        [
            BASE_SYSTEM_PROMPT.strip(),
            A3_SPECIFIC_INSTRUCTIONS.strip(),
            "SPECIFICHE CRITERI:\n" + _json_block(criteria_specs),
            "DATI DEL SYLLABUS DA VALUTARE:\n" + _json_block(data.syllabus_data),
            "CONTESTO NORMATIVO RECUPERATO VIA RAG:\n" + _json_block(data.normative_context),
            A3_OUTPUT_SCHEMA_INSTRUCTIONS.strip(),
            "Rispondi ora esclusivamente con il JSON valido richiesto.",
        ]
    )


def _coerce_agent_input(agent_input: AgentInput | dict[str, Any]) -> AgentInput:
    if isinstance(agent_input, AgentInput):
        return agent_input
    return AgentInput.model_validate(agent_input)


def _json_block(value: Any) -> str:
    return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n```"
