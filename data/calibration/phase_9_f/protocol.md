# Phase 9.F — Protocollo di calibrazione A5 (E4 + E5)

**Versione protocollo:** `phase_9_f_v1`
**Branch di lavoro:** `feature/phase-9-f-a5-calibration`
**Prerequisiti:** Phase 9.A (contratto documento↔criterio), 9.B (resolver +
audit), 9.C (A5 ExternalConsistencyAgent), 9.D (API+UI dei risultati
estesi). Phase 9.E (selezione esplicita pre-run) NON è prerequisito:
la calibrazione usa il flusso resolver automatico.

Questo documento fissa il perimetro, il campione, i documenti, il
formato di output e le regole operative della prima calibrazione di
A5. Il codice della pipeline di calibrazione (9.F.2) verrà scritto
solo dopo che questo protocollo è stato concordato e congelato.

## 1. Perimetro iniziale

La prima campagna calibra **soltanto E4 ed E5**. Le ragioni sono di
disponibilità documentale, non metodologiche:

| Criterio | Sorgente prevista | Stato attuale | Inclusione in 9.F |
|:---|:---|:---|:---|
| `E1` | SUA-CdS LM-18 | non caricata nel registry | escluso (resolver-NA atteso) |
| `E2` | Matrice di Tuning LM-18 | non compilata per LM-18 | escluso (resolver-NA atteso) |
| `E3` | Regolamento didattico LM-18 | non caricato nel registry | escluso (resolver-NA atteso) |
| **`E4`** | Versione EN del syllabus stesso | sempre disponibile per i 5 syllabus storici | **incluso** |
| **`E5`** | Documento `usi_dipartimentali` LM-18 | preparato come fixture (sezione 3) | **incluso** |

E1-E3 resteranno `resolver-NA` per costruzione e non entrano nei
report di distribuzione. La struttura dello script di calibrazione
deve però rendere triviale la loro inclusione futura una volta che i
documenti SUA-CdS / Matrice / Regolamento saranno caricati e
indicizzati.

## 2. Campione

### 2.1 Shortlist storica (5 syllabus)

Sono gli stessi 5 SEUID usati nelle calibrazioni precedenti
(`a1_v4_before_a1_v5`, `e2e_v1`, `e2e_v2`, fixtures A3/A4 v2). La
loro riusabilità è il principio: confrontabilità di CoreScore e
coverage core fra prima/dopo la Phase 9.

| # | SEUID | Note |
|:---|:---|:---|
| 1 | `3540D939-DA16-4C1D-983C-E6B85C403F2F` | shortlist |
| 2 | `E2446DF6-59A1-46FD-B8D8-635EB937C1B3` | shortlist |
| 3 | `F4AF1512-9D7A-4256-B57D-E103E05B009B` | shortlist |
| 4 | `FE97232C-4F07-41F8-A82F-FF73592265EC` | shortlist |
| 5 | `0B53E8E2-4B90-426F-A25C-3AA31FA4B649` | shortlist |

### 2.2 Casi mirati opzionali (≤3)

Da aggiungere **solo se** la shortlist non copre uno dei seguenti
profili. La selezione finale è da confermare in fase 9.F.2 sulla
base di un'ispezione manuale dei 30 syllabus LM-18:

1. **Syllabus con `has_english=False`** — deve produrre `E4 = NA
   semantico` dal resolver, senza chiamata LLM. Utile per validare
   che il path semantico stia funzionando in produzione.
2. **Syllabus con EN parziale (1-2 campi paired su 10)** — deve
   esercitare il pre-LLM paired-prefix check (semantic NA della
   sezione "perimetro EN inadeguato" se le coppie non hanno
   contenuto) e/o produrre un giudizio E4 score=1 di equivalenza
   parziale.
3. **Syllabus con EN integrale e ben curato** — atteso E4 score=2,
   utile come reference positiva.

I casi mirati vengono presi **dai 30 syllabus LM-18 di calibrazione
esistente**, non da nuovi syllabus, per restare nel dataset
scientifico.

### 2.3 Numerosità totale

- baseline iniziale: **5** (shortlist) → 10 giudizi A5 (E4+E5 per
  syllabus);
- con casi mirati: fino a **8** → 16 giudizi.

L'analisi statistica resta indicativa a questi numeri — la
calibrazione 9.F è in primo luogo *diagnostica*, non per produrre
stime di accordo inter-umano. La fase di validazione vera è
Phase 5.8.

## 3. Documento E5 — fixture metodologica

### 3.1 Identità

- **Tipo:** `usi_dipartimentali`
- **CdL:** `cdl_id` di LM-18 (auto-risolto da `_resolver` sui 5 syllabus
  della shortlist, tutti LM-18)
- **Titolo:** `Usi dipartimentali LM-18 — Phase 9.F baseline`
- **Anno accademico:** `2025-2026`
- **Versione registry:** prima ingestion → `version=1`
- **Versione fixture:** **`v1`** (sezione 3.2 fissa la baseline)
- **File:** [fixtures/usi_dipartimentali_lm18_v1.md](fixtures/usi_dipartimentali_lm18_v1.md)
- **`enabled_criteria`:** `["E5"]`

### 3.2 Politica di versioning

Il documento è **immutabile durante la baseline**. Se una revisione
post-analisi richiede modifiche al contenuto (per esempio rendere
più espliciti certi usi che si rivelano ambigui al modello), la
nuova versione del file ha suffisso `_v2`, `_v3`, ... e il sommario
di calibrazione annota esplicitamente quale versione del documento
ha alimentato ogni run.

Questa stessa cartella conserva tutte le versioni così che ogni
`EvaluationResult` storico resta riproducibile: anche se il
registry produce nuove versioni a runtime (`document.version`),
la fixture sorgente resta sotto controllo.

### 3.3 Contenuto

Il documento descrive un piccolo numero di usi tipici facilmente
verificabili dal modello sui 5 syllabus della shortlist:

- struttura raccomandata dei **prerequisiti** (separazione
  esplicita conoscenze culturali/generali vs disciplinari/specialistiche);
- linea sui **criteri di voto** (peso esplicito delle componenti +
  almeno un esempio di domanda);
- formato dei **riferimenti bibliografici** (autore, anno, edizione);
- linea sulla **modalità di frequenza** (esplicitare se obbligatoria
  o consigliata; eventuali percentuali minime).

Ogni uso è formulato per essere **applicabile** ai 5 syllabus
storici, in modo che la pipeline possa effettivamente assegnare un
giudizio (0/1/2) e non solo un NA semantico per inapplicabilità.

## 4. Output

Per ogni run la pipeline scrive in `data/calibration/phase_9_f/<run>/`:

### 4.1 Per syllabus

- `<seuid>__evaluation.json` — dump della `EvaluationDetail` API
  completa (struttura tipizzata 9.D.1: `extended_criteria_result`
  compact, `external_documents_used`);
- `<seuid>__report.md` — `final_report` core deterministico
  (Phase 5.4.G) riportato per ispezione visiva;
- `<seuid>__extended_judgments.md` — riassunto leggibile dei
  giudizi E4 + E5 (codice, score, justification, evidenze
  Syllabus/Documento) e dei NA con provenienza esplicita.

### 4.2 A livello di run

- `summary.json` — tabella per syllabus + aggregati:
  - distribuzione E4 / E5 (conteggio per score 0/1/2/NA semantico/NA
    tecnico);
  - elenco `handler_errors` con il messaggio dell'handler;
  - tempi (`latency_ms` per handler);
  - per ogni run: `extended_criteria_result.status`,
    `handler_prompt_versions`, `document_id` + `version` + `hash`
    del documento E5 utilizzato;
- `summary.md` — versione human-readable di `summary.json`, con la
  stessa tabella distribuzioni e una lista esplicita dei casi
  patologici (NA tecnici, drift evidenze, justification troppo corte
  o non in italiano, evidenze paired non corrette per E4).

### 4.3 Tracciabilità

Ogni file di output riporta in testa:

- `protocol_version` (`phase_9_f_v1`);
- `e5_fixture_version` (`v1`);
- `e4_prompt_version` / `e5_prompt_version` effettivamente usati
  (letti dalla `EvaluationDetail.prompt_versions` lato core +
  `extended_criteria_result.handler_prompt_versions` lato A5);
- `evaluation_uuid`.

## 5. Baseline e regole operative

### 5.1 Prompt versions

La baseline gira con **`e4_v1` e `e5_v1`** verbatim. Nessuna
modifica ai prompt durante la baseline, anche se l'analisi
preliminare rivela drift. Le modifiche di prompt (eventuale
`e4_v2` / `e5_v2`) sono in carico a una fase successiva (9.F.3)
con il suo set di output separato.

### 5.2 Configurazione scientifica

I parametri (`ScientificConfig` di runtime) sono quelli di default
in `app/config.py`:

- `llm_model = gemini-2.5-flash`
- `llm_temperature = 0.1`
- `llm_max_output_tokens = 8192`
- `rag_top_k = 5`, `rag_final_k = 3`, `rag_similarity_threshold = 0.6`
- override A1 `max_output_tokens = 16384` (per il core, non per A5)

Nessun override per gli handler A5 nella baseline. La calibrazione
documenta in summary la configurazione effettiva di ogni run.

### 5.3 Resolver e documento

- la run gira con `selected_document_ids=None`, quindi il resolver
  applica la precedence ladder standard. Per la fixture E5
  (`document_type=usi_dipartimentali`, `academic_year=2025-2026`) e
  syllabus della shortlist (tutti LM-18 con
  `academic_year=2025/2026`) il match atteso è
  `academic_year_match`;
- la calibrazione carica la fixture **una sola volta all'inizio**
  della campagna e la mantiene attiva per tutta la durata. Il
  cleanup è scelta esplicita post-analisi (analogo a
  `--preserve-history` di 9.D);
- E1/E2/E3 restano `resolver-NA` su tutte le run (nessun documento
  applicabile è caricato nel registry).

### 5.4 Vertex / costi

Stima per la baseline: 5 syllabus × (A1+A2+A3+A4 + 2 handler A5
invocati) = 30 LLM call core + 10 LLM call A5 ≈ 40 chiamate +
indicizzazione embedding del documento E5 (1-3 chunk).

L'utente è il responsabile dell'esecuzione: lo script di
calibrazione 9.F.2 stamperà la stima prima di partire e richiederà
conferma esplicita.

## 6. Analisi

Dopo la baseline, l'analisi mira a rispondere a queste domande in
ordine di priorità:

1. **Distribuzione E4 vs aspettativa**: i punteggi rispecchiano il
   profilo bilingue effettivo dei syllabus? Quanti dei 5 producono
   E4=2, E4=1, E4=0, NA semantico?
2. **E5 grounding**: tutti i giudizi E5 numerici rispettano il
   dual-source (citazione syllabus + citazione documento)? Le
   evidenze documentali puntano davvero al chunk corretto?
3. **NA semantici vs tecnici**: quanti casi di NA tecnico per
   syllabus? Sono concentrati su un criterio specifico? La loro
   causa è retry exhaustion o errore di retrieval?
4. **Justification e lingua**: le justification sono in italiano,
   articolate (≥2 frasi), e citano esplicitamente la fonte? Ci
   sono pattern di justification generica/templatic?
5. **Tempi**: latency per handler accettabile (target < 30s per
   handler)?

L'analisi è prodotta come parte del `summary.md` + una breve nota
in `data/calibration/phase_9_f/baseline/analysis.md` (da scrivere
manualmente post-run, non auto-generata).

## 7. Tuning (9.F.3 — futuro)

Solo se l'analisi della baseline identifica drift consistenti, si
procederà con un giro di tuning:

- modifiche del prompt **incrementali e versionate**: ogni revisione
  bumpa la prompt_version (`e4_v2`, `e5_v2`, ...);
- ogni revisione gira sullo stesso campione + i casi mirati
  eventualmente confermati;
- output sotto `data/calibration/phase_9_f/<eN_vM>/`;
- non si modifica E5 fixture per "aggirare" un problema del prompt:
  la fixture e il prompt sono variabili indipendenti.

## 8. Sequenza operativa

| Step | Owner | Quando |
|:---|:---|:---|
| 9.F.1 protocollo + fixture | Claude | adesso (questo branch) |
| 9.F.2 script calibrazione | Claude | dopo conferma del protocollo |
| Indicizzazione fixture E5 + run baseline | Utente (Vertex) | dopo merge 9.F.2 |
| Analisi baseline + nota | Utente + Claude | dopo run |
| 9.F.3 tuning (opzionale) | Claude | solo se baseline lo richiede |

## 9. Vincoli metodologici da preservare

- **E1-E5 non concorrono al CoreScore**: invariante già garantita
  da 9.C, riaffermata qui per chiarezza. Nessuna analisi di 9.F
  può "fondere" estesi e core.
- **NA semantico ≠ NA tecnico**: le distribuzioni li tengono
  separati. I NA tecnici sono debito di pipeline (da risolvere), i
  NA semantici sono esiti legittimi del criterio.
- **Run smoke vs calibrazione**: lo script di 9.F.2 distingue
  esplicitamente. Una run di calibrazione viene segnata con
  `calibration_mode: "phase_9_f_baseline"` in modo da poterla
  filtrare nella history dell'`EvaluationResult` rispetto allo
  smoke e alle run sperimentali quotidiane (la marcatura concreta
  è da decidere in 9.F.2, ma il principio è qui fissato).
- **Riproducibilità**: ogni file di output deve consentire di
  ricostruire la configurazione completa della run senza dover
  guardare il codice. Le versioni di protocollo, fixture e prompt
  sono in testa a ogni file.
