# Usi dipartimentali per la redazione dei syllabus — LM-18 Informatica

**Versione fixture:** `v1`
**Anno accademico di riferimento:** `2025-2026`
**Tipo documento:** `usi_dipartimentali`
**Ambito:** redazione dei syllabus degli insegnamenti del Corso di
Laurea Magistrale in Informatica (LM-18), Dipartimento di
Matematica e Informatica, Università degli Studi di Catania.
**Stato:** baseline immutabile di calibrazione Phase 9.F. Nuove
revisioni andranno salvate come `usi_dipartimentali_lm18_v2.md`,
`v3.md`, ecc., conservando le precedenti.

Le indicazioni che seguono sono **usi tipici e raccomandazioni
dipartimentali**: descrivono pratiche redazionali che il presidio
qualità del CdL si aspetta di trovare nei syllabus. Non
sostituiscono le Linee Guida UniCT, il Regolamento didattico né la
SUA-CdS: integrano questi documenti con scelte locali, applicabili
trasversalmente a tutti gli insegnamenti del CdL.

Ogni uso elenca il perimetro di applicazione (a quali sezioni del
syllabus si riferisce) e la formulazione raccomandata. Un syllabus
è considerato **aderente** all'uso quando la sua sezione
corrispondente rispecchia in sostanza, anche con formulazioni
diverse, l'indicazione qui descritta.

## 1. Prerequisiti — distinzione esplicita culturali / disciplinari

**Perimetro:** sezione "Prerequisiti" (`prerequisites_it`).

**Uso:** i prerequisiti del corso vanno organizzati distinguendo
in modo esplicito tra due famiglie di conoscenze attese:

- **Conoscenze culturali / generali**: competenze metodologiche e
  formative trasversali, tipicamente acquisite durante il triennio
  o nei primi insegnamenti dell'LM (esempi: logica matematica di
  base, ragionamento algoritmico, fondamenti di analisi).
- **Conoscenze disciplinari / specialistiche**: contenuti tecnici
  specifici, attesi dagli insegnamenti propedeutici o dal manifesto
  (esempi: strutture dati, programmazione orientata agli oggetti,
  basi di dati, fondamenti di reti).

La distinzione può essere realizzata con elenchi separati, con
sottosezioni esplicite o con un elenco unico organizzato in modo
chiaramente separabile. Una semplice lista omogenea che mischi le
due famiglie senza alcuna separazione **non** soddisfa l'uso.

L'inclusione della gradazione "utili / importanti / indispensabili"
suggerita dalle Linee Guida UniCT è **raccomandata** ma non
sostituisce la distinzione culturali/disciplinari: i due assi sono
ortogonali.

## 2. Modalità di verifica — pesi espliciti e almeno una domanda esempio

**Perimetro:** sezione "Modalità di verifica dell'apprendimento"
(`assessment_methods_it`) e sezione "Esempi di domande"
(`sample_questions_it`).

**Uso:** i criteri di voto vanno descritti in modo da rendere
prevedibile l'esito al candidato:

- esplicitare il **peso relativo** delle componenti dell'esame
  (scritto, orale, progetto, prova in itinere) sul voto finale,
  almeno qualitativamente (es. "il progetto pesa per circa metà
  del voto finale, lo scritto per circa metà");
- indicare se è previsto un **voto minimo** sulle singole
  componenti per accedere alla componente successiva;
- includere **almeno una domanda esempio** rappresentativa,
  preferibilmente nella sezione apposita
  (`sample_questions_it`), oppure in fondo alla sezione modalità
  di verifica.

Un syllabus che limita la descrizione a formule generiche del tipo
"esame orale con valutazione complessiva delle competenze
acquisite" senza pesi né esempi è considerato **parzialmente
aderente** (aderenza 1). L'assenza completa di pesi e di esempi
porta a **non aderente** (0).

## 3. Riferimenti bibliografici — formato minimo

**Perimetro:** sezione "Testi adottati / Riferimenti"
(`references_it`).

**Uso:** ogni riferimento bibliografico riportato nel syllabus
deve includere come minimo:

- **autore/autori** (cognome puntato è ammesso);
- **anno** di pubblicazione (anche solo l'edizione di riferimento);
- **titolo** completo dell'opera;
- **editore** (per i libri) o **rivista** (per gli articoli);
- **edizione** quando rilevante per il corso (es. terza edizione
  di un manuale per cui il syllabus indica capitoli specifici).

I riferimenti possono essere organizzati per **tipo** (manuale
principale, manuale complementare, articoli di approfondimento,
risorse online ufficiali) o in elenco unico, ma il livello minimo
di dettaglio sopra resta non negoziabile. Una sola riga del tipo
"il libro di Tanenbaum" non soddisfa l'uso.

## 4. Modalità di frequenza — esplicitazione del livello richiesto

**Perimetro:** sezione "Modalità di frequenza"
(`attendance_it`).

**Uso:** la sezione deve indicare in modo esplicito:

- se la frequenza è **obbligatoria** o **facoltativa**;
- in caso di obbligatorietà parziale (es. solo per la componente
  di laboratorio), specificare quale componente è soggetta a
  obbligo;
- per gli insegnamenti con componenti pratiche (laboratorio,
  esercitazioni), indicare il livello di frequenza atteso anche
  quando non strettamente obbligatorio (es. "fortemente
  raccomandata per la componente di laboratorio").

Un syllabus che lascia la sezione vuota o si limita a indicazioni
generiche tipo "frequenza consigliata" senza distinguere
componenti pratiche e teoriche è considerato parzialmente
aderente.

## 5. Note operative sull'applicabilità

- **Casi non applicabili.** Per i corsi che non prevedono una data
  sezione (es. nessuna componente pratica → indicazione di
  frequenza meno articolata), l'uso si considera **non
  applicabile** e il giudizio è `NA semantico`, non `0`. La
  decisione spetta all'agente, sulla base del syllabus letto.
- **Combinazione con C1-C9.** Questi usi dipartimentali integrano,
  non sostituiscono, i criteri core. Un syllabus può essere
  contemporaneamente conforme al criterio core C5 (chiarezza dei
  prerequisiti) e non aderente all'uso 1 (distinzione esplicita
  culturali/disciplinari): l'aderenza al primo è un livello
  minimo trasversale UniCT, l'aderenza al secondo è una
  raccomandazione locale del Dipartimento.
- **Versionamento.** Future revisioni di questo documento devono
  essere registrate come nuovi file `_v2`, `_v3`, ecc., e ogni
  campagna di calibrazione deve annotare in summary quale
  versione del documento ha alimentato la run.
