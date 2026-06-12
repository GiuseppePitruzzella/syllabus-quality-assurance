# Phase 9.F baseline — analisi post-run

**Calibration mode:** `phase_9_f_baseline`  
**Protocol version:** `phase_9_f_v1`  
**E5 fixture version:** `v1`  
**Prompt versions:** E4 `e4_v1`, E5 `e5_v1`  
**Data run:** 12 giugno 2026

## Esito sintetico

La baseline e' tecnicamente valida e riproducibile:

- 5/5 evaluation core `completed`;
- coverage core 100% su tutti i syllabus;
- 5/5 risultati estesi `completed`;
- zero `handler_errors`;
- zero NA tecnici;
- prompt E4/E5 invariati (`e4_v1`, `e5_v1`);
- fixture E5 immutata, indicizzata come documento `id=1`, versione 1,
  hash `ab953d43381c170b07c6eab6e569dbceff6919c0f6d9f5d61b4d2deeedb60418`;
- 5 audit row E5 persistite, una per evaluation.

La campagna e' durata 699.42 secondi. La durata media per evaluation
e' stata 139.23 secondi, con mediana 129.56 secondi.

## Distribuzioni

| Criterio | Score 0 | Score 1 | Score 2 | NA semantico | NA tecnico |
|---|---:|---:|---:|---:|---:|
| E4 — Coerenza cross-lingua | 3 | 0 | 1 | 1 | 0 |
| E5 — Aderenza agli usi locali | 3 | 2 | 0 | 0 | 0 |

Il CoreScore medio dei cinque syllabus e' 1.534, con coverage media
pari a 1.0. I risultati estesi restano separati dal CoreScore.

## Lettura E4

E4 mostra una capacita' discriminante netta e produce giudizi
qualitativamente coerenti con le evidenze:

- **Deep Learning: 2** — le principali coppie IT/EN risultano
  semanticamente equivalenti e terminologicamente coerenti.
- **OTTIMIZZAZIONE: 0** — il giudizio identifica omissioni e derive
  rilevanti, inclusa la sovrapposizione impropria di descrittori di
  Dublino nella versione inglese.
- **Peer to Peer e laboratorio: 0** — viene rilevata la contraddizione
  sostanziale `NS3` in italiano contro `NS2` in inglese, oltre a
  omissioni di sezioni.
- **Machine Learning: 0** — viene rilevata la contraddizione fra
  prerequisiti italiani espliciti e `None` nella versione inglese,
  insieme a omissioni nelle altre sezioni.
- **Internet of Things: NA semantico** — `has_english=True` non e'
  sufficiente: non esiste alcuna coppia IT/EN materialmente
  confrontabile. Il comportamento conferma la distinzione fra presenza
  formale dell'inglese e comparabilita' semantica.

La baseline non contiene alcun caso E4=1. Prima di considerare
calibrata l'intera scala e' consigliabile aggiungere un caso mirato con
versione inglese parziale ma confrontabile.

## Lettura E5

Tutti i cinque giudizi E5 sono numerici e rispettano la regola
dual-source: ogni giudizio cita sia campi del syllabus sia chunk del
documento locale.

- **Deep Learning: 1** e **OTTIMIZZAZIONE: 1** — aderenza parziale
  motivata da un mix di sezioni conformi e lacune esplicite.
- **Peer to Peer e laboratorio: 0**, **Machine Learning: 0** e
  **Internet of Things: 0** — non aderenza motivata con riferimenti
  puntuali agli usi su prerequisiti, criteri di voto, bibliografia e
  frequenza.

Le justification sono in italiano, articolate e grounded. Non emergono
allucinazioni documentali evidenti.

La distribuzione E5 e' tuttavia concentrata nella parte bassa della
scala: nessun syllabus ottiene 2. Questo puo' riflettere correttamente
la severita' della fixture e il campione storico, ma lascia non
esercitato l'anchor positivo. Il caso **Machine Learning** merita una
revisione manuale specifica: il giudizio 0 e' trainato soprattutto
dalla mancata distinzione dei prerequisiti, nonostante altre sezioni
siano aderenti o parzialmente aderenti. Va chiarito metodologicamente
se una singola disattenzione esplicita e rilevante debba essere
sufficiente per assegnare 0 al criterio complessivo, oppure se E5 debba
avere una lettura maggiormente olistica.

## Discrepanza sul resolver

Il protocollo prevedeva per la fixture E5 una risoluzione
`academic_year_match`. Le cinque audit row riportano invece
`latest_available_fallback`.

La causa e' deterministica: i cinque syllabus nel database hanno
`academic_year=''`, mentre la fixture E5 ha `academic_year=2025-2026`.
Il resolver non puo' quindi effettuare il match per anno.

La discrepanza non invalida questa baseline:

- e' stato selezionato lo stesso documento E5 in tutte le run;
- documento, versione e hash sono registrati nelle audit row;
- il fallback e' esplicito e riproducibile.

Per campagne future e' pero' opportuno scegliere una delle seguenti
strategie:

1. popolare correttamente `syllabus.academic_year` durante lo scraping;
2. usare una selezione esplicita del documento per la campagna;
3. dichiarare nel protocollo che, sui dati LM-18 correnti, il fallback
   e' il comportamento atteso.

## Limiti osservati

- Il campione di cinque syllabus e' diagnostico, non statisticamente
  rappresentativo.
- La scala E4 non esercita lo score 1.
- La scala E5 non esercita lo score 2.
- Il summary espone la durata totale per evaluation, ma il payload API
  compatto non espone la latenza separata dei singoli handler E4/E5;
  il target per-handler inferiore a 30 secondi non e' quindi
  verificabile dagli artefatti correnti.

## Decisione consigliata

La baseline `e4_v1` / `e5_v1` puo' essere accettata come baseline
funzionale: il grounding, la gestione degli NA e la separazione dal
CoreScore sono corretti e non richiedono un fix urgente.

Prima di un eventuale tuning 9.F.3, conviene effettuare due controlli
mirati:

1. aggiungere un syllabus atteso E4=1 e un caso senza inglese per
   esercitare i path mancanti;
2. sottoporre a revisione umana almeno Machine Learning per decidere
   se la severita' E5=0 rappresenta l'intento della rubrica.

Solo se la revisione umana considera sistematicamente troppo severi i
giudizi E5=0, sara' giustificato introdurre `e5_v2`. Non e' consigliato
modificare subito il prompt sulla sola base dell'assenza di score 2 nel
piccolo campione.

## Review manuale — Machine Learning (E5=0)

**SEUID:** `FE97232C-4F07-41F8-A82F-FF73592265EC`
**Esito modello:** score 0, confidence high.
**Data review:** 12 giugno 2026.

### Procedura

Letti i quattro usi della fixture `v1` e confrontati uno per uno con i
campi del syllabus Machine Learning (`prerequisites_it`,
`assessment_methods_it`, `sample_questions_it`, `references_it`,
`attendance_it`). Le evidenze del giudizio sono state confrontate con
il contenuto effettivo del syllabus letto direttamente dal DB.

### Mappa uso-per-uso

| Uso fixture | Stato syllabus | Lettura review |
|:---|:---|:---|
| 1 — Prerequisiti culturali/disciplinari | Lista omogenea "analisi matematica, matematica discreta, fondamenti di informatica, programmazione, ..." senza distinzione | **Violato.** La fixture e' esplicita: "Una semplice lista omogenea ... non soddisfa l'uso". |
| 2 — Modalita' di verifica con pesi + esempi | Pesi espliciti ("media dei voti" → 50/50 prova scritta/progetto), tre domande esempio presenti, **voto minimo** per componente non specificato | **Aderenza parziale.** Manca solo l'elemento "voto minimo" del checklist. |
| 3 — Riferimenti bibliografici | Tre libri completi (autori, titolo, editore, anno): Duda-Hart-Stork 2000, Bishop 2006, Alpaydin, + "Materiale fornito dal docente" | **Aderente.** Soddisfa il formato minimo richiesto. |
| 4 — Modalita' di frequenza | "La frequenza non e' obbligatorio ma e' fortemente consigliata per garantire un adeguato grado di comprensione degli argomenti proposti" | **Aderente.** Indica esplicitamente facoltativita' + livello atteso. |

Bilancio: **2 usi aderenti, 1 uso parzialmente aderente, 1 uso
violato**.

### Lettura del giudizio del modello

Il modello ha citato evidenze per tre dei quattro usi (1, 2, 3). L'uso
4 (modalita' di frequenza) **non risulta tra le evidenze del
giudizio**, nonostante il syllabus contenga una formulazione esplicita
e conforme. La justification non menziona la frequenza, ne' come
aderente ne' come non valutata. Questa omissione e' un gap
metodologico del giudizio E5=0: il modello ha scansionato una parte
del corpus ma non ha verificato l'aderenza all'uso 4.

Il punteggio 0 e' stato motivato citando verbatim il passaggio
strict-per-uso della fixture: "Una semplice lista omogenea ... non
soddisfa l'uso". Sulla base di quella singola riga il modello ha
concluso "non aderenza complessiva", trasferendo il giudizio severo
del per-uso al criterio globale.

### Confronto con gli anchor di E5

Gli anchor della rubrica E5 sono:

- 0 — "Documento locale disponibile, ma il syllabus disattende
  indicazioni rilevanti e applicabili";
- 1 — "Il syllabus aderisce solo parzialmente o in modo non uniforme
  alle indicazioni locali";
- 2 — "Il syllabus aderisce in modo sostanziale alle indicazioni
  locali applicabili".

Lo score 0 usa il plurale "indicazioni" e qualifica le violazioni come
"rilevanti e applicabili". L'evidenza supporta **una sola** indicazione
violata (uso 1), accanto a due indicazioni rispettate e una
parzialmente rispettata. La mappa uso-per-uso descrive esattamente la
formulazione dello score 1: "parzialmente o **in modo non uniforme**".

### Verdetto

**E5=0 e' eccessivamente severo rispetto al giudizio umano atteso.**

Il punteggio appropriato sul caso Machine Learning, applicando gli
anchor di E5 con lettura olistica del documento, e' **1**. Il giudizio
del modello e' grounded e onesto ma:

1. **Anchora un solo passaggio strict-per-uso** della fixture (uso 1)
   per giustificare il punteggio piu' basso del criterio complessivo,
   senza pesare quanto sostantivamente le altre indicazioni sono
   soddisfatte.
2. **Omette interamente la valutazione dell'uso 4** (frequenza), anche
   se il syllabus contiene una formulazione esplicita e aderente.
3. **Confonde la lingua per-uso** della fixture ("non soddisfa l'uso")
   con il linguaggio globale di anchor (`indicazioni`, plurale): la
   coerenza tra le due richiede un giudizio aggregato, non una
   propagazione one-strike-out.

### Implicazioni

La review **conferma una severita' osservabile** del prompt `e5_v1` su
un caso concreto. Non e' pero' sufficiente a giustificare da sola un
`e5_v2`, per due motivi:

1. e' un singolo caso su una baseline di cinque syllabus;
2. la scala E5 non ha esercitato alcuno score 2 in baseline, quindi
   non sappiamo ancora se il prompt e' incapace di concedere il
   massimo o se semplicemente i cinque storici non lo meritavano. La
   distinzione non e' decidibile senza il path positivo.

Il prossimo passo coerente con il protocollo §7 e' quindi
**`phase_9_f_targeted_v1`**: aggiungere un caso EN parziale per
toccare E4=1 e almeno un caso atteso E5=2. Se la campagna mirata
produce uno score E5=2 su un syllabus genuinamente conforme alle
indicazioni, allora la severita' osservata su Machine Learning sara'
un outlier accettabile sul campione storico e `e5_v1` puo' essere
considerato sufficiente. Se invece anche un caso ben costruito non
raggiunge 2, la severita' e' sistemica e `e5_v2` diventa necessario.

### Annotazioni metodologiche di supporto al prompt

A prescindere dal tuning, due osservazioni della review meritano di
essere registrate per le revisioni future del prompt o della fixture:

- la fixture mescola lingua **per-uso** ("non soddisfa l'uso") e lingua
  **per-anchor** del criterio ("disattende indicazioni rilevanti"). E'
  un'ambiguita' che il prompt non risolve esplicitamente. Una
  revisione futura della fixture o del prompt dovrebbe rendere
  esplicito il criterio di aggregazione fra uso e criterio;
- il prompt non vincola il modello a **scandire tutti gli usi prima di
  emettere il giudizio**. L'omissione dell'uso 4 in Machine Learning
  e' sintomatica: una checklist esplicita nelle istruzioni potrebbe
  ridurre il rischio di valutazioni parziali.
