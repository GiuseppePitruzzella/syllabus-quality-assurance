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
