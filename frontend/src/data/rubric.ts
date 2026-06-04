/**
 * Phase 7 — read-only snapshot of the evaluation rubric.
 *
 * SOURCE OF TRUTH: docs/progettazione.md §2.3-2.6.
 * Anchors are condensed paraphrases of the prompt-level rubric in
 * `backend/app/evaluation/agents/prompts/a{1..4}_prompt.py`. Both
 * are kept in sync MANUALLY — there is no runtime fetch. When the
 * rubric in `progettazione.md` changes, update this file by hand
 * and bump the profile in `profile.ts`.
 *
 * The split between CORE_CRITERIA (C1-C9) and EXTENDED_CRITERIA
 * (E1-E4) is the methodological backbone of the project:
 *
 *   - core      enters the `CoreScore` aggregation, all on a 0/1/2
 *               ordinal scale with `NA` reserved for technical
 *               non-evaluability.
 *   - extended  is OPTIONAL and EXPERIMENTAL. It requires external
 *               documents (SUA-CdS, Matrice di Tuning, Regolamento
 *               didattico, cross-lingua check) and is therefore not
 *               uniformly available. EXTENDED criteria DO NOT enter
 *               the `CoreScore` — they are reported separately.
 *
 * UI consumers must render the two sets in clearly distinct blocks
 * and surface the "Non concorrono al CoreScore" note next to the
 * extended one.
 */

export type Score = 0 | 1 | 2 | "NA";

export interface Anchor {
  score: Score;
  description: string;
}

export interface CoreCriterion {
  code: string; // "C1" .. "C9"
  name: string;
  area: string;
  agent: "A1" | "A2" | "A3" | "A4";
  weight: number;
  prompt_version: string; // mirrors profile.ts; redundant but local for the row
  description: string;
  anchors: Anchor[];
  notes?: string;
}

export interface ExtendedCriterion {
  code: string; // "E1" .. "E4"
  name: string;
  area: string;
  agent: "A2" | "A3" | "A4";
  description: string;
  requires: string; // document(s) that must be available
  status: "futuro" | "sperimentale";
}

// ---------------------------------------------------------------------------
// Core — C1..C9 (concorre al CoreScore)
// ---------------------------------------------------------------------------

export const CORE_CRITERIA: CoreCriterion[] = [
  {
    code: "C1",
    name: "Completezza strutturale",
    area: "Completezza",
    agent: "A1",
    weight: 1.0,
    prompt_version: "a1_v5",
    description:
      "Verifica la presenza e compilazione sostanziale di tutte le sezioni previste dalle Linee Guida UniCT: risultati di apprendimento, prerequisiti, contenuti, modalità di valutazione, esempi di domande, testi adottati, modalità di svolgimento, modalità di frequenza, programmazione del corso.",
    anchors: [
      { score: 0, description: "Più di una sezione obbligatoria mancante o sostanzialmente vuota." },
      { score: 1, description: "Una sezione obbligatoria mancante o compilata in modo frammentario." },
      { score: 2, description: "Tutte le sezioni obbligatorie compilate in modo sostantivo." },
      { score: "NA", description: "Contenuto non recuperabile per errore tecnico persistente." },
    ],
  },
  {
    code: "C2",
    name: "Completezza bilingue",
    area: "Bilinguismo",
    agent: "A1",
    weight: 1.0,
    prompt_version: "a1_v5",
    description:
      "Verifica la disponibilità della versione inglese sul perimetro minimo: titolo, risultati di apprendimento, contenuti, modalità di verifica. L'assenza reale della versione inglese non rende NA il criterio: incide sul punteggio.",
    anchors: [
      { score: 0, description: "Versione inglese assente o perimetro minimo non coperto." },
      { score: 1, description: "Versione inglese presente ma con copertura parziale del perimetro minimo." },
      { score: 2, description: "Versione inglese completa sul perimetro minimo (titolo, RA, contenuti, MV)." },
      { score: "NA", description: "Riservato a casi tecnici eccezionali, non al solo dato mancante." },
    ],
    notes:
      "C2 è strettamente di A1: A4 e altri agenti non devono penalizzare l'assenza della versione inglese — ricade qui.",
  },
  {
    code: "C3",
    name: "Qualità dei risultati di apprendimento",
    area: "Outcome",
    agent: "A2",
    weight: 1.0,
    prompt_version: "a2_v1",
    description:
      "Valuta la formulazione degli outcome come apprendimenti osservabili, non come argomenti o contenuti del corso.",
    anchors: [
      { score: 0, description: "RA formulati come elenco di argomenti, senza verbi osservabili." },
      { score: 1, description: "RA in parte osservabili, in parte ancora orientati agli argomenti." },
      { score: 2, description: "RA chiaramente osservabili e verificabili." },
      { score: "NA", description: "RA non recuperabili per ragioni tecniche." },
    ],
  },
  {
    code: "C4",
    name: "Articolazione dei Descrittori di Dublino",
    area: "Outcome",
    agent: "A2",
    weight: 1.0,
    prompt_version: "a2_v1",
    description:
      "Valuta presenza e qualità dell'articolazione dei cinque Descrittori di Dublino: conoscenza/comprensione, capacità di applicare, autonomia di giudizio, abilità comunicative, capacità di apprendimento. Indipendente dalla bilinguità (C2).",
    anchors: [
      { score: 0, description: "Descrittori assenti o generici/sovrapposti su più descrittori." },
      { score: 1, description: "Descrittori presenti ma con articolazione frammentaria." },
      { score: 2, description: "Cinque descrittori articolati con specificità sull'insegnamento." },
      { score: "NA", description: "Descrittori non recuperabili per ragioni tecniche." },
    ],
  },
  {
    code: "C5",
    name: "Chiarezza dei prerequisiti",
    area: "Completezza",
    agent: "A1",
    weight: 1.0,
    prompt_version: "a1_v5",
    description:
      "Valuta se i prerequisiti sono formulati in modo utile allo studente. Per il punteggio massimo serve specificità + distinzione esplicita tra conoscenze culturali/generali e disciplinari/specialistiche (o organizzazione equivalente).",
    anchors: [
      { score: 0, description: "Prerequisiti assenti o formulati in modo generico." },
      { score: 1, description: "Prerequisiti specifici ma senza distinzione fra culturali e disciplinari." },
      { score: 2, description: "Prerequisiti specifici con distinzione esplicita culturali/disciplinari." },
      { score: "NA", description: "Sezione non recuperabile per ragioni tecniche." },
    ],
    notes:
      "Ricalibrato in a1_v5 (Phase 5.4.J) per ristabilire un bordo netto tra punteggio 1 e 2.",
  },
  {
    code: "C6",
    name: "Trasparenza della valutazione",
    area: "Coerenza",
    agent: "A3",
    weight: 1.0,
    prompt_version: "a3_v1",
    description:
      "Valuta la chiarezza delle modalità di verifica dell'apprendimento. Criteri di voto, rubriche o esempi di domande sono raccomandati ma non singolarmente obbligatori se la modalità è già chiara.",
    anchors: [
      { score: 0, description: "Modalità di verifica non chiara o non descritta." },
      { score: 1, description: "Modalità descritta ma con elementi di ambiguità sui criteri." },
      { score: 2, description: "Modalità chiara, con criteri di attribuzione del voto o equivalenti." },
      { score: "NA", description: "Sezione non recuperabile per ragioni tecniche." },
    ],
  },
  {
    code: "C7",
    name: "Chiarezza dei contenuti del corso",
    area: "Coerenza",
    agent: "A3",
    weight: 1.0,
    prompt_version: "a3_v1",
    description:
      "Valuta se contenuti e programmazione permettono allo studente di capire cosa verrà trattato e con quale organizzazione. Focus sulla qualità informativa della sezione contenuti.",
    anchors: [
      { score: 0, description: "Contenuti elencati in modo confuso o assente." },
      { score: 1, description: "Contenuti presenti ma con organizzazione poco chiara." },
      { score: 2, description: "Contenuti chiari, organizzati, con riferimento a programmazione." },
      { score: "NA", description: "Sezione non recuperabile per ragioni tecniche." },
    ],
  },
  {
    code: "C8",
    name: "Coerenza didattico-valutativa",
    area: "Coerenza",
    agent: "A3",
    weight: 1.0,
    prompt_version: "a3_v1",
    description:
      "Valuta il principio di constructive alignment: risultati di apprendimento, contenuti, metodi didattici e modalità di verifica devono tenersi insieme. Richiede inferenza relazionale fra più sezioni.",
    anchors: [
      { score: 0, description: "Disallineamento esplicito tra RA, contenuti e verifica." },
      { score: 1, description: "Allineamento parziale: alcune sezioni in coerenza, altre non chiaramente." },
      { score: 2, description: "Allineamento sistemico tra RA, contenuti, metodi e verifica." },
      { score: "NA", description: "Materiale necessario non recuperabile." },
    ],
    notes:
      "Per C8 ci si aspetta un accordo inter-umano potenzialmente più basso, perché il giudizio richiede inferenza fra sezioni.",
  },
  {
    code: "C9",
    name: "Cura editoriale",
    area: "Editoriale",
    agent: "A4",
    weight: 1.0,
    prompt_version: "a4_v2",
    description:
      "Valuta la coerenza interna del documento come artefatto scritto: refusi, residui redazionali, formattazione, qualità dei riferimenti, incongruenze formali evidenti. Non penalizza artefatti del parser non presenti nell'originale, né la sola assenza della versione inglese (ricade su C2).",
    anchors: [
      { score: 0, description: "Refusi sistematici, incongruenze formali macroscopiche, riferimenti malformati." },
      { score: 1, description: "Refusi puntuali o riferimenti migliorabili, ma documento leggibile." },
      { score: 2, description: "Documento curato, riferimenti coerenti, formattazione uniforme." },
      { score: "NA", description: "Riservato a casi tecnici eccezionali." },
    ],
  },
];

// ---------------------------------------------------------------------------
// Extended — E1..E4 (NON entrano nel CoreScore)
// ---------------------------------------------------------------------------

export const EXTENDED_CRITERIA: ExtendedCriterion[] = [
  {
    code: "E1",
    name: "Allineamento con SUA-CdS",
    area: "Allineamento documentale",
    agent: "A2",
    description:
      "Verifica la coerenza sostantiva tra i risultati del syllabus e i quadri A4.b.2 e A4.c della SUA-CdS.",
    requires: "SUA-CdS del CdS di appartenenza",
    status: "sperimentale",
  },
  {
    code: "E2",
    name: "Allineamento con Matrice di Tuning",
    area: "Allineamento documentale",
    agent: "A2",
    description:
      "Verifica la coerenza tra risultati attesi del syllabus e ruolo dell'insegnamento nella matrice delle corrispondenze.",
    requires:
      "Matrice di Tuning del CdS — non disponibile per LM-18 al momento.",
    status: "futuro",
  },
  {
    code: "E3",
    name: "Coerenza con Regolamento didattico",
    area: "Allineamento documentale",
    agent: "A3",
    description:
      "Controlla la coerenza tra programma, CFU, prerequisiti e modalità di verifica rispetto al Regolamento didattico del CdS.",
    requires: "Regolamento didattico del CdS",
    status: "sperimentale",
  },
  {
    code: "E4",
    name: "Coerenza cross-lingua",
    area: "Bilinguismo avanzato",
    agent: "A4",
    description:
      "Verifica l'equivalenza semantica tra versione italiana e inglese, non solo la presenza formale di entrambe (che è C2).",
    requires: "Versione inglese del syllabus presente sul perimetro completo",
    status: "sperimentale",
  },
];
