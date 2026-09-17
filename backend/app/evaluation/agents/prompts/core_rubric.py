"""Canonical existing core anchors. This migration does not rewrite scoring rules.

Prompt builders validate supplied specs and fill missing anchors from here.
Versions identify the restored-anchor prompts, not a newly validated rubric.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

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

CORE_CRITERIA_SPECS = {
    "A1": A1_CRITERIA_SPECS, "A2": A2_CRITERIA_SPECS,
    "A3": A3_CRITERIA_SPECS, "A4": A4_CRITERIA_SPECS,
}
CORE_PROMPT_VERSIONS = {"A1": "a1_v8", "A2": "a2_v2", "A3": "a3_v2", "A4": "a4_v11"}


def resolve_criteria_specs(supplied: list[dict[str, Any]], agent: str) -> list[dict[str, Any]]:
    """Never allow description-only input to suppress score anchors.

    Partial metadata input is supported, but cannot remove an owned criterion.
    Explicit custom anchors must be complete. Unknown/duplicate codes and wrong
    owners fail before inference. Return copies so callers cannot mutate defaults.
    """
    defaults = CORE_CRITERIA_SPECS[agent]
    expected = {spec["criterion_code"] for spec in defaults}
    overrides = {}
    for spec in supplied:
        code = spec.get("criterion_code")
        if code not in expected or code in overrides:
            raise ValueError("Unknown or duplicate criterion specification")
        if spec.get("owned_by", agent) != agent:
            raise ValueError("Criterion specification has the wrong owner")
        overrides[code] = spec
    resolved = []
    for default in defaults:
        spec = deepcopy(default | overrides.get(default["criterion_code"], {}))
        anchors = spec.get("anchors")
        if (not isinstance(anchors, dict) or set(anchors) != {"0", "1", "2"}
                or not all(isinstance(v, str) and v.strip() for v in anchors.values())):
            raise ValueError("Every criterion requires complete nonempty 0/1/2 anchors")
        resolved.append(spec)
    return resolved
