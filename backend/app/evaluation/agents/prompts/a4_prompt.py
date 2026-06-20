"""Prompt builder for A4 EditorialCareAgent.

A4 evaluates a single criterion:
- C9, cura editoriale del syllabus.

C9 is the most interpretive criterion in the rubric (D006). It looks
at observable editorial care: typos, internal inconsistencies between
sections, completeness and formatting of bibliographical references,
overall coherence between IT and EN versions, narrative
proof-reading. The grounding is global: A4 reads the whole syllabus
and judges it as a unit.

Methodological notes (cf. retrofit on A1/C5, the A2 review and the
A3 review):

- Posture is intentionally PRUDENT. Where A4 cannot point at
  evidence in the syllabus, it MUST NOT invent issues. ``confidence``
  defaults to ``"medium"`` rather than ``"high"`` whenever the
  evidence is partial or interpretation is required.
- The RAG context is small for C9 (often only 2 chunks) and the
  prompt acknowledges that explicitly: A4 relies more on the
  syllabus itself than on external normative grounding. The few
  RAG chunks help interpret what "cura" means but do not provide
  exhaustive criteria.
- C9 must NOT double-count problems already handled by other
  criteria. Bilingual coverage gaps belong to C2 (A1). Generic
  learning outcomes belong to C3 (A2). Dublin descriptor coverage
  belongs to C4 (A2). Missing assessment criteria belong to C6 (A3).
  Content organisation belongs to C7 (A3). Didactic alignment
  between RA / content / methods / assessment belongs to C8 (A3).
  Semantic equivalence between IT and EN belongs to extended
  criterion E4. C9 only cares about *observable editorial quality*:
  typos, formal/redactional internal inconsistencies (e.g. a
  cross-reference using a different label, leftover paste, broken
  numbering), reference completeness, formatting noise, macroscopic
  IT/EN parallelism (NOT semantic equivalence). A4 does not penalize
  isolated minor imperfections or field-fragment artifacts: C9=1
  requires either a severe redactional defect or a small cluster of
  concrete defects across distinct fields. Repeated instances of the
  same typo in duplicated/derived fields count as ONE defect. English
  prose that is understandable, even if not idiomatic, is not a C9
  defect by itself.
"""
from __future__ import annotations

import json
from typing import Any

from app.evaluation.agents.prompts.base import BASE_SYSTEM_PROMPT
from app.evaluation.agents.schemas import AgentInput

A4_SPECIFIC_INSTRUCTIONS = """Sei l'AGENTE DI CURA EDITORIALE (A4).
Il tuo focus è verificare la cura editoriale del syllabus considerato come documento unitario: refusi, incongruenze interne fra le sezioni, qualità e completezza dei riferimenti bibliografici, coerenza fra versione italiana e inglese laddove la versione inglese è presente, formattazione complessivamente curata.

Valuti un solo criterio della rubrica:
- C9, cura editoriale del syllabus.

Gli anchor di punteggio per C9 sono nel blocco "SPECIFICHE CRITERI" più avanti. Usali come unico riferimento per assegnare 0, 1 o 2.

Avvertenze specifiche per A4:
- POSTURA PRUDENTE. C9 è il criterio più interpretativo della rubrica (vedi D006 nelle decisioni di progetto). Non inventare problemi che non sei in grado di documentare con un'evidenza testuale concreta. Se non hai prove osservabili di un difetto editoriale, NON penalizzare.
- POSTURA NEUTRALE SUL 1/2. Non partire dal presupposto che ogni syllabus reale debba avere C9=1. Se non trovi difetti editoriali concreti e attribuibili al testo del syllabus, assegna C9=2. Anche in presenza di UNO SOLO difetto minore o localizzato, assegna C9=2 se il documento resta complessivamente curato. Il punteggio 1 richiede almeno DUE difetti editoriali concreti e indipendenti in campi distinti oppure UN difetto redazionale grave e chiaramente attribuibile al testo originale (es. riferimento bibliografico sostanzialmente malformato, incongruenza formale che cambia un nome/codice/strumento, errore grammaticale evidente in una sezione chiave). Riserva il punteggio 0 a casi in cui i difetti editoriali sono gravi, diffusi e sistematici (illeggibilità di parti del documento, riferimenti completamente assenti, frasi sintatticamente rotte sistematiche).
- CONTEGGIO DEI DIFETTI. Conta come UN SOLO difetto le occorrenze ripetute dello stesso refuso o della stessa frase in campi duplicati/derivati (es. learning_outcomes_en e dublin_applying_en riportano la stessa frase con lo stesso refuso). Non trasformare una duplicazione tecnica dei dati in "difetti distribuiti". Una riga bibliografica o di programmazione che mescola titoli inglesi e parole italiane funzionali ("Capitolo", "e", "risorse online") NON è un difetto editoriale e NON va citata come evidenza C9 se resta comprensibile e coerente con il contesto. Se l'unico difetto reale è un refuso localizzato e l'altra possibile evidenza è solo una citazione tecnica mista ma intelligibile, assegna C9=2.
- INGLESE COMPRENSIBILE. Nei campi EN valuta come difetti solo errori chiaramente testuali: refusi evidenti, parole spezzate, frasi sintatticamente rotte o formulazioni che impediscono/alterano la comprensione. NON penalizzare frasi inglesi sufficientemente comprensibili solo perché non perfettamente idiomatiche, non native-like, o stilisticamente migliorabili. Errori lievi di collocazione, articolo, preposizione o stile contano al massimo come limite trascurabile se il senso resta chiaro.
- USO DELLA CONFIDENCE. Per C9 la confidence di DEFAULT è "medium". Usala "high" SOLO quando i difetti (o la cura) sono numerosi, concordanti, distribuiti su più sezioni e chiaramente gravi. Per un punteggio 1 la confidence è di norma "medium". Usa "low" quando la valutazione è particolarmente interpretativa o le evidenze sono ambigue.
- ARTEFATTI DI PARSING. Non penalizzare il syllabus per segnali che possono ragionevolmente derivare dallo scraping/parsing invece che dalla pagina originale: interruzioni di parola dovute ad a capo, punti isolati all'inizio dei descrittori, marker come "-->", spazi anomali, liste appiattite, oppure sequenze letterali come "\\n" / "\\r\\n" dovute alla serializzazione del testo. Puoi citarli solo come limite tecnico con confidence "low", ma NON usarli come ragione principale per abbassare C9. Penalizza invece refusi lessicali reali, frasi grammaticalmente scorrette, riferimenti bibliografici incompleti/malformati e incongruenze editoriali che rimangono tali anche sul testo originale.
- CAMPI DUBLIN. I campi dublin_* possono apparire come frammenti perché sono sotto-campi estratti dal syllabus o porzioni dei risultati di apprendimento. NON penalizzare un dublin_* solo perché inizia con minuscola, non è una frase autonoma, ripete una frase dei risultati di apprendimento o sembra un segmento. Usa un dublin_* come evidenza C9 solo se contiene un difetto editoriale reale e autonomo (refuso, grammatica errata, residuo redazionale), non perché è frammentario.
- RIGORE SULL'ESCLUSIONE C2. NON citare in evidences né in justification l'assenza, parzialità, o incompletezza della versione inglese del syllabus. Anche se vedi che "learning_outcomes_en" è vuoto o "dublin_*_en" sono incompleti, NON è un problema editoriale di tua competenza: ricade su C2 (A1). C9 valuta SOLO la qualità editoriale di quello che è effettivamente scritto, indipendentemente dalla lingua. Puoi valutare i campi EN che sono presenti per refusi, formattazione, residui di traduzione e incoerenze redazionali macroscopiche, ma non puoi penalizzare un campo EN per il fatto di essere vuoto o parziale.
- CONTRADDIZIONI IT/EN. NON usare C9 per valutare se il contenuto italiano e quello inglese dicono la stessa cosa: l'equivalenza semantica IT/EN appartiene a E4. Esempi come prerequisiti_it popolato e prerequisites_en = "None" NON sono di per sé C9: possono indicare problemi di completezza/equivalenza, ma non cura editoriale, salvo che il testo mostri anche un difetto redazionale formale verificabile.
- LIMITE EVIDENCES. Riporta al MASSIMO 5 evidences per il giudizio C9, scegliendo le più rappresentative del difetto (o della cura) che stai motivando. NON fare un inventario esaustivo di tutti i refusi: rischi di troncare l'output e produrre una motivazione meno leggibile.
- RIFERIMENTI E FONTI. Sii tollerante sulla formattazione bibliografica: stili diversi, elenchi non perfettamente uniformi, titoli in inglese dentro testi italiani, riferimenti a slide/siti/materiale docente e numerazioni sintetiche non sono difetti se lo studente riesce comunque a identificare la fonte. Penalizza i riferimenti solo quando sono sostanzialmente incompleti, ambigui o malformati al punto da non essere risolvibili.
- COSA VALUTARE. Refusi e errori ortografici/grammaticali; incongruenze formali o redazionali interne (es. una sezione che fa riferimento a un'altra con titolo o nome diverso, riferimenti numerici incoerenti, residui di copia-incolla chiaramente presenti nel contenuto); qualità dei riferimenti bibliografici quando il riferimento è davvero non risolvibile; link o riferimenti testuali visibilmente malformati nel testo del syllabus; coerenza editoriale macroscopica fra IT e EN dove entrambe sono presenti, intesa solo come parallelismo formale (sezioni disallineate in modo evidente, termini lasciati a metà, residui di traduzione).
- COSA NON VALUTARE (RICADE SU ALTRI AGENTI). NON penalizzare l'assenza della versione inglese: questo è C2 (A1). NON penalizzare la qualità della formulazione dei risultati di apprendimento: questo è C3 (A2). NON penalizzare la copertura dei Descrittori di Dublino: questo è C4 (A2). NON penalizzare l'assenza di prerequisiti: questo è C5 (A1). NON penalizzare l'assenza di criteri di attribuzione del voto: questo è C6 (A3). NON valutare l'organizzazione dei contenuti del corso: questo è C7 (A3). NON valutare il disallineamento didattico fra contenuti, RA, metodi e verifica (es. un esame che valuta competenze non coperte dai contenuti): questo è C8 (A3). NON valutare l'equivalenza semantica fra IT e EN: questo è il criterio esteso E4. C9 valuta esclusivamente la qualità editoriale OSSERVABILE come refusi, incongruenze formali, riferimenti malformati, formattazione e parallelismo editoriale IT/EN.
- RAG LIMITATO. Per C9 il contesto normativo recuperato è tipicamente più piccolo (2-3 chunk). Le Linee Guida UniCT raccomandano una compilazione curata, ma non forniscono una checklist esaustiva di criteri editoriali. Considera il RAG come orientamento sul significato di "cura editoriale" all'interno del sistema AVA, non come elenco normativo prescrittivo.
- Quando un campo del syllabus è presente nei DATI DEL SYLLABUS ma vuoto, NON è di per sé un difetto editoriale: è informazione che spetta ad altri criteri. C9 valuta come è scritto quello che c'è, non quello che manca strutturalmente.
"""

A4_CRITERIA_SPECS: list[dict[str, Any]] = [
    {
        "criterion_code": "C9",
        "name": "Cura editoriale del syllabus",
        "owned_by": "A4",
        "anchors": {
            "0": "Difetti editoriali GRAVI, DIFFUSI e SISTEMATICI, tali da compromettere la leggibilità o l'affidabilità del documento. Esempi: parti del syllabus illeggibili o sintatticamente rotte in modo ricorrente; sezione bibliografica completamente assente o priva di qualunque riferimento risolvibile; riferimenti o frasi sistematicamente corrotti. Punteggio 0 NON va assegnato per refusi sparsi, difetti minori o possibili artefatti di parsing.",
            "1": "Difetti editoriali reali e osservabili ma di entità contenuta: almeno due difetti concreti e indipendenti in campi distinti, oppure un singolo difetto redazionale grave e chiaramente attribuibile al testo originale. Esempi: refusi/errori grammaticali evidenti in più sezioni, riferimenti bibliografici sostanzialmente non risolvibili, link/riferimenti testuali malformati, incongruenze formali minori ma verificabili. Il documento resta leggibile e usabile. Non assegnare 1 per un solo difetto minore o localizzato, per inglese comprensibile ma non perfettamente idiomatico, per variazioni innocue nello stile dei riferimenti, per la ripetizione dello stesso refuso in campi duplicati/derivati, per titoli tecnici/citazioni bibliografiche che mescolano parole italiane e inglesi in modo comprensibile, per campi dublin_* frammentari, per contraddizioni semantiche IT/EN o se le uniche evidenze sono possibili artefatti di scraping/parsing. In particolare: un refuso localizzato più una citazione tecnica mista ma intelligibile non costituiscono due difetti indipendenti.",
            "2": "Documento editorialmente curato o con difetti assenti/trascurabili: refusi non evidenti o non significativi, riferimenti sufficientemente chiari, struttura leggibile e coerente. Un singolo difetto minore/localizzato, anche se ripetuto in campi duplicati o derivati, non basta ad abbassare il punteggio. Inglese comprensibile ma non idiomatico, titoli tecnici, citazioni bibliografiche o righe di programmazione che combinano lessico italiano e inglese restano accettabili se sono intelligibili e coerenti. Possibili artefatti di parsing isolati (es. a capo anomali, punti iniziali, marker '-->', sequenze '\\n') e frammentarietà dei campi dublin_* non bastano ad abbassare il punteggio se non sono difetti verificabili del testo originale. Il giudizio resta editoriale: non valuta l'equivalenza semantica IT/EN, che appartiene a E4.",
        },
    },
]

# Fields A4 reads from the syllabus.
#
# A4 is the only agent that reads the syllabus as a UNIT, so the field
# list is the largest. Excluded: internal DB ids (id, cdl_id, seuid)
# and links (url_it, url_en) — they don't carry editorial signal.
#
# Empty / null values are kept on purpose: the absence itself is not a
# C9 problem (it belongs to other criteria) but the prompt instructs
# A4 to ignore "missing" and focus on "how what's there is written".
A4_RELEVANT_FIELDS: tuple[str, ...] = (
    # Editorial metadata
    "course_code",
    "course_name",
    "course_name_en",
    "module",
    "teacher",
    "academic_year",
    "year_of_study",
    "has_english",
    # Italian content
    "learning_outcomes_it",
    "dublin_knowledge_it",
    "dublin_applying_it",
    "dublin_judgement_it",
    "dublin_communication_it",
    "dublin_learning_it",
    "teaching_methods_it",
    "prerequisites_it",
    "attendance_it",
    "course_content_it",
    "references_it",
    "schedule_it",
    "assessment_methods_it",
    "sample_questions_it",
    # English content
    "learning_outcomes_en",
    "dublin_knowledge_en",
    "dublin_applying_en",
    "dublin_judgement_en",
    "dublin_communication_en",
    "dublin_learning_en",
    "teaching_methods_en",
    "prerequisites_en",
    "attendance_en",
    "course_content_en",
    "references_en",
    "schedule_en",
    "assessment_methods_en",
    "sample_questions_en",
)


A4_OUTPUT_SCHEMA_INSTRUCTIONS = """SCHEMA OUTPUT JSON (forma, non valori da copiare):
{
  "judgments": [
    {
      "criterion_code": "C9",
      "score": <0 | 1 | 2 | null>,
      "is_na": <true | false>,
      "na_reason": <string | null>,
      "justification": <string in italiano, almeno 2 frasi>,
      "evidences": [
        {"text": <citazione letterale dal syllabus>, "source_field": <nome_campo>}
      ],
      "confidence": <"low" | "medium" | "high">
    }
  ]
}

I valori che vedi sono PLACEHOLDER: non vanno copiati, ma sostituiti con la tua valutazione concreta.

Vincoli sull'output:
- Devi restituire esattamente un giudizio, per C9.
- Se is_na è false, score deve essere 0, 1 o 2 e na_reason deve essere null.
- Se is_na è true, score deve essere null e na_reason deve spiegare il problema tecnico.
- Confidence di default per C9 è "medium". Usa "high" solo se hai evidenze concordanti del difetto editoriale (o della cura). Usa "low" quando la valutazione è particolarmente interpretativa.
- evidences deve contenere solo citazioni letterali dal SYLLABUS (mai dal contesto normativo). Per C9 le evidenze sono i passaggi del syllabus dove il difetto editoriale è OSSERVABILE: refusi, riferimenti incompleti/malformati, incongruenze o residui redazionali che restano difetti del testo originale. Non usare come evidenza principale possibili artefatti di scraping/parsing.
- Per assegnare C9=1 servono almeno due evidenze di difetti concreti e indipendenti in campi distinti, oppure una evidenza di difetto redazionale grave. Se trovi solo un difetto minore/localizzato, assegna C9=2 e menzionalo come limite trascurabile nella justification. Occorrenze ripetute dello stesso refuso in campi duplicati/derivati contano come un solo difetto.
- Non usare come difetti C9 titoli tecnici, nomi di moduli, citazioni bibliografiche o righe di programmazione che mescolano italiano e inglese in modo comprensibile e coerente: sono normali in syllabus bilingui/tecnici, salvo errori formali autonomi. NON citarli nelle evidences come se fossero difetti, perché non sono evidenze valide per abbassare C9.
- Non usare come difetti C9 inglese sufficientemente comprensibile ma non perfettamente idiomatico, né sequenze letterali "\\n" / "\\r\\n" visibili solo per serializzazione o scraping. Se il testo è leggibile e il difetto non compare chiaramente nella pagina ufficiale, non usarlo per abbassare il punteggio.
- Per riferimenti bibliografici/testi: non richiedere uno stile bibliografico uniforme. Penalizza solo fonti non identificabili o sostanzialmente malformate.
- I campi dublin_* NON vanno usati come evidenza C9 solo perché frammentari, minuscoli, ripetitivi o non autonomi: usali soltanto se contengono un refuso o errore editoriale reale.
- NON usare come evidenza C9 contraddizioni semantiche IT/EN (es. prerequisiti italiani presenti e inglesi "None"): appartengono a E4/C2/C5, non alla cura editoriale.
- LIMITE: massimo 5 evidences per il giudizio C9. Scegli le più rappresentative del difetto (o della cura) che stai motivando, non un inventario esaustivo.
- Ogni "evidences[i].text" DEVE essere una stringa NON vuota. Se non hai testo letterale da citare, descrivi la qualità editoriale nella "justification" e LASCIA "evidences" come lista vuota []. NON inserire MAI evidenze con "text": "".
- NON valutare aspetti che ricadono su altri criteri: assenza dell'inglese (C2), formulazione RA (C3), copertura Dublin (C4), prerequisiti (C5), criteri di voto (C6), organizzazione dei contenuti (C7), disallineamento didattico fra RA/contenuti/metodi/verifica (C8), equivalenza semantica IT/EN (E4).
- NON citare l'assenza, parzialità o incompletezza della versione inglese in nessuna parte del giudizio. La completezza bilingue è esclusivamente di C2.
"""


def build_a4_prompt(agent_input: AgentInput | dict[str, Any]) -> str:
    """Build the complete prompt for A4 from standardized agent input.

    Block order mirrors A1/A2/A3:
    1. BASE_SYSTEM_PROMPT       — role, rules, perimeter, scale, NA, confidence
    2. A4_SPECIFIC_INSTRUCTIONS — A4 role + prudent posture + scope warnings
    3. SPECIFICHE CRITERI       — structured anchors (single source of truth)
    4. SYLLABUS DA VALUTARE     — A4-relevant syllabus fields (the whole syllabus)
    5. CONTESTO NORMATIVO       — RAG chunks (small for C9 by design)
    6. SCHEMA OUTPUT JSON       — output contract with neutral placeholder example
    7. closing                  — one-line directive to emit JSON only
    """
    data = _coerce_agent_input(agent_input)
    criteria_specs = data.criteria_specs or A4_CRITERIA_SPECS
    return "\n\n".join(
        [
            BASE_SYSTEM_PROMPT.strip(),
            A4_SPECIFIC_INSTRUCTIONS.strip(),
            "SPECIFICHE CRITERI:\n" + _json_block(criteria_specs),
            "DATI DEL SYLLABUS DA VALUTARE:\n" + _syllabus_data_block(data.syllabus_data),
            "CONTESTO NORMATIVO RECUPERATO VIA RAG:\n" + _json_block(data.normative_context),
            A4_OUTPUT_SCHEMA_INSTRUCTIONS.strip(),
            "Rispondi ora esclusivamente con il JSON valido richiesto.",
        ]
    )


def _coerce_agent_input(agent_input: AgentInput | dict[str, Any]) -> AgentInput:
    if isinstance(agent_input, AgentInput):
        return agent_input
    return AgentInput.model_validate(agent_input)


def _json_block(value: Any) -> str:
    return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n```"


def _syllabus_data_block(value: Any) -> str:
    """Render syllabus fields as readable text instead of JSON strings.

    C9 is sensitive to visual/editorial artifacts. JSON serialisation
    exposes line breaks as literal ``\\n`` sequences, which are not text
    authored in the official syllabus page.
    """
    if not isinstance(value, dict):
        return _json_block(value)
    parts: list[str] = []
    for field, content in value.items():
        parts.append(f"### {field}")
        parts.append(_format_syllabus_field(content))
    return "\n\n".join(parts)


def _format_syllabus_field(value: Any) -> str:
    if value is None:
        return "<vuoto>"
    if isinstance(value, str):
        text = value.replace("\\r\\n", "\n").replace("\\n", "\n").strip()
        return text or "<vuoto>"
    rendered = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    return rendered.replace("\\r\\n", "\n").replace("\\n", "\n")
