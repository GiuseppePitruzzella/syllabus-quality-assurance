# Proposta di miglioramento della rubrica e della valutazione locale

16 settembre 2026 — **Bozza da validare. Nessuna modifica alla rubrica attiva.**

## Obiettivo e punto di partenza

Valutare quanto il syllabus documenta informazioni utili, comprensibili e
coerenti per lo studente. Il risultato non misura direttamente la qualità
dell'insegnamento svolto e non certifica integralmente la conformità normativa.

Conservare i nove criteri e la scala 0–2, rendendo però osservabile il percorso
che conduce al punteggio: condizioni, passaggi del syllabus, regola applicata,
eventuale informazione mancante e intervento suggerito.

Il [pilot con la rubrica separata](SEPARATED_RESULTS.md) non dimostra ancora un
miglioramento complessivo: sul solo syllabus IoT l'accordo con Gemini storico
è passato da 5/9 a 6/9, mentre le citazioni verificate sono scese da 20/31 a
18/32. Le regole erano cambiate e il caso era già stato usato nello sviluppo.
La priorità è quindi rendere il giudizio controllabile, poi verificarne la validità.

## Tre livelli espliciti

| Livello | Contenuto | Effetto sul risultato |
|---|---|---|
| Fonte e applicabilità | Documento, versione, sezione, anno accademico e condizioni pertinenti | Determina quali riferimenti usare; non inventa una soglia numerica |
| Rubrica del progetto | Definizione del criterio, condizioni 0/1/2, esclusioni, esempi | Determina il punteggio; è una scelta metodologica da validare |
| Suggerimenti | Miglioramenti facoltativi utili allo studente | Non diventano automaticamente penalizzazioni |

La [guida UniCT 26.04](https://www.unict.it/sites/default/files/files/linee_guida_syllabus.pdf)
richiede la compilazione bilingue delle sezioni; distingue i due descrittori
disciplinari da quelli trasversali eventualmente aggiunti; richiede di
esplicitare il contributo delle modalità didattiche ai risultati. Per i
prerequisiti distingue conoscenze e propedeuticità formali, se previste dal
regolamento. Questi riferimenti orientano il profilo pertinente, senza
trasformare le novità in obblighi retroattivi. La revisione delle altre fonti
e delle differenze rispetto al corpus storico è in [RUBRIC_REVIEW.md](RUBRIC_REVIEW.md).

Se non è possibile stabilire quale versione si applichi, il rapporto dichiara
il profilo scelto e limita le conclusioni di conformità. Le regole 0/1/2 qui
proposte sono nostre convenzioni operative, non punteggi ufficiali UniCT.

## Regole proposte per i nove criteri

Le condizioni seguenti sono candidate per il prossimo esperimento. Un dato
tecnicamente indisponibile segue le regole di non valutabilità descritte più avanti.

| Criterio e domanda | 0 | 1 | 2 |
|---|---|---|---|
| **C1 — Copertura informativa.** Quali sezioni informano sul proprio oggetto? | Almeno tre delle nove sezioni non informative | Una o due sezioni non informative | Tutte le nove sezioni informative |
| **C2 — Copertura inglese minima.** Sono disponibili i tre gruppi centrali? | Nessun gruppo informativo | Uno o due gruppi informativi | Risultati, contenuti e valutazione informativi in inglese |
| **C3 — Formulazione dei risultati.** Che cosa saprà conoscere o fare lo studente? | Nessun risultato riconoscibile; solo argomenti o attività del docente | Risultati riconoscibili, ma almeno uno sostanziale resta generico o non verificabile | Ogni risultato sostanziale specifica una conoscenza o capacità verificabile e il suo oggetto |
| **C4 — Domini di apprendimento.** Conoscere e applicare sono distinguibili? | Nessun dominio riconoscibile | Conoscenza e applicazione incomplete/indistinte, oppure un dominio trasversale dichiarato è privo di contenuto distinto o attività di sviluppo | Conoscenza e applicazione distinte; domini trasversali dichiarati distinguibili e collegati ad attività |
| **C5 — Prerequisiti comprensibili.** Lo studente può capire come prepararsi? | Informazione assente o tautologica | Indicazioni generiche, soli nomi di corsi o condizioni di accesso ambigue | Conoscenze/abilità sufficientemente specifiche per autovalutarsi, oppure esplicita assenza di prerequisiti; condizioni formali chiare se dichiarate |
| **C6 — Trasparenza degli esami.** Lo studente sa come sarà valutato? | Non è identificabile la natura delle prove | Prove identificabili, ma svolgimento, criteri di giudizio o condizioni applicabili incompleti | Prove, svolgimento, criteri e condizioni applicabili comprensibili |
| **C7 — Organizzazione del programma.** Si ricostruiscono argomenti e struttura? | Non si ricostruiscono i contenuti | Ambito riconoscibile, ma argomenti troppo generici o organizzazione non ricostruibile | Argomenti specifici organizzati in nuclei, moduli o progressione comprensibile |
| **C8 — Coerenza interna.** Le attività e le prove sostengono i risultati dichiarati? | Contraddizione documentata che impedisce di sviluppare o verificare almeno un risultato sostanziale | Componenti disponibili, ma almeno una relazione resta indeterminata o mostra una discrepanza circoscritta | Le relazioni risultati–contenuti, risultati–didattica e risultati–prove sono sostenute dal testo |
| **C9 — Comprensibilità editoriale.** I difetti di scrittura ostacolano la lettura? | Un difetto editoriale rende irrecuperabile il significato di un'informazione essenziale | Il significato resta ricostruibile, ma occorre correggere un difetto per eliminare ambiguità o ostacoli concreti alla lettura | Lettura chiara; eventuali difetti minori non alterano il significato e non ostacolano la consultazione |

### Precisazioni necessarie per applicare la tabella

- **C1:** mantenere inizialmente i confini quantitativi della rubrica attiva,
  evitando di introdurre insieme anche le nuove soglie 4/8/9 di `separated_v1`.
  Non sono soglie validate: il dato principale è l'elenco delle nove sezioni
  con stato ed evidenza. Informativo non significa lungo o pedagogicamente
  eccellente: «frequenza non obbligatoria» è informazione; un'intestazione vuota
  non lo è. RA narrativi e descrittori sono rappresentazioni dello stesso gruppo.
  Brevità e mancata traduzione non producono automaticamente assenza in C1.
- **C2:** rinominare l'indicatore per chiarirne il limite. Affiancare una matrice
  di tutte le nove sezioni IT/EN e il titolo come diagnostica, senza confonderla
  con lo score sui tre gruppi. L'equivalenza semantica delle traduzioni resta
  nel controllo E4. Lunghezza minima e nome del campo non provano lingua e
  pertinenza: i controlli automatici producono candidati, da verificare nei casi
  ambigui. Accettare anche risultati distribuiti nei descrittori, senza contarli
  più volte.
- **C3:** estrarre prima i risultati sostanziali e distinguere frasi introduttive
  e attività didattiche. «Il docente presenterà…» non è di per sé un risultato
  dello studente. Non basta cercare un elenco di verbi: azione e oggetto devono
  consentire di capire quale prestazione o conoscenza verificare.
- **C4:** non richiedere automaticamente cinque domini. Se documenti applicabili
  del CdS impongono risultati ulteriori, verificarli nel livello di allineamento
  esterno, con quei documenti disponibili. Lo stesso laboratorio può sostenere
  capacità diverse; identità dell'attività non significa identità dei risultati.
- **C5:** chiarire il livello con esempi, ad esempio «risolvere sistemi lineari»
  rispetto a «matematica». Le etichette utile/importante/indispensabile sono
  suggerimenti, non condizioni universali per 2. Non inferire l'assenza di
  propedeuticità regolamentari da un syllabus che non ne parla: occorre il
  regolamento per verificarla. Questo criterio valuta la chiarezza documentata.
- **C6:** controllare separatamente prove, svolgimento, criteri di giudizio e
  condizioni. Pesi, soglie di accesso, ordine delle prove e contributo di prove
  in itinere si controllano quando pertinenti. Non imporre una particolare
  tabella di fasce di voto né scambiare due prove finali per prove in itinere.
- **C7:** ammettere una struttura narrativa chiara. Ore per argomento, calendario
  e formato tabellare non sono requisiti universali per 2. Verificare questo
  confine con lo stesso contenuto presentato in forme equivalenti.
- **C8:** produrre una matrice delle tre relazioni, con i passaggi di entrambe
  le componenti. Distinguere collegamento esplicito, ricostruibile e indeterminato.
  La richiesta documentale di esplicitazione del profilo 26.04 va riportata come
  controllo dedicato, distinto dal giudizio di compatibilità pedagogica. La sola
  etichetta «orale» o «scritto» non dimostra incompatibilità con un risultato.
- **C9:** sostituire i conteggi arbitrari di refusi con l'effetto sulla
  comprensione. Verificare il difetto sul documento originale quando si sospetta
  un errore di estrazione. Bibliografia o inglese assenti appartengono alla
  copertura; informazioni sostanzialmente contraddittorie richiedono il criterio
  pertinente. L'impatto editoriale va calibrato con esempi condivisi: questa
  proposta restringe il criterio e non è equivalente allo score storico.

## Evidenze e casi non valutabili

Ogni condizione deve avere uno stato: **soddisfatta**, **non soddisfatta**,
**incerta** o **non applicabile**. L'ultima voce riguarda una condizione
realmente subordinata, per esempio il peso delle prove in itinere quando
non sono previste. Non è un modo per escludere un criterio sfavorevole.

Distinguere nel risultato:

| Situazione | Trattamento |
|---|---|
| Campo vuoto verificato nell'originale | Assenza osservata, valutabile secondo il criterio |
| Campo escluso dal payload o estrazione dubbia | Dato indisponibile; verifica tecnica, senza attribuire l'omissione al docente |
| Intera componente necessaria a C8 assente, senza una contraddizione già dimostrabile | Coerenza non valutabile per dati insufficienti; riportare separatamente l'assenza in C1 |
| Componenti presenti ma generiche | C8 può essere 1 per relazione indeterminata; non chiamarla contraddizione |
| Modello fallito o evidenza non valida | Valutazione da completare o revisionare; nessun punteggio sostitutivo inventato |

Un difetto non abbassa automaticamente più criteri. Lo stesso testo può
sostenerne diversi, ma ogni giudizio richiede una ragione nel proprio perimetro.
Un esame descritto chiaramente può quindi ricevere C6=2 e C8=0 se contraddice
un risultato documentato. Una contraddizione già dimostrata non viene nascosta
dalla mancanza di un'altra componente: resta segnalata e sostiene C8=0, con
l'indicazione separata dei dati mancanti.

Per le citazioni, assegnare identificativi ai passaggi originali. Qwen sceglie
gli identificativi pertinenti; il programma riproduce il testo esatto. Le
assenze sono registrate con il campo controllato, non con citazioni vuote.
Un identificativo valido garantisce la provenienza, **non la pertinenza**:
il collegamento fra evidenza, condizione e punteggio resta da verificare.

Dove la corrispondenza è definita, il programma calcola il punteggio dalle
condizioni accertate. Non deve trasformare automaticamente condizioni incerte
in giudizi positivi. La selezione semantica di risultati, domini e relazioni
resta affidata al modello e, nei casi dubbi, alla revisione umana.

## Contesto fisso e uso di Qwen sul Mac

Preparare per ciascun agente un pacchetto versionato di passaggi pertinenti
e regole, con riferimenti alle sezioni delle fonti. Includere una sola volta
i brani condivisi e conservare le condizioni di applicabilità. Per il nucleo
stabile della rubrica, questo consente di evitare ricerca ed embedding a ogni
valutazione. I documenti specifici di un CdS richiedono invece una selezione
dedicata quando cambia il contesto dell'insegnamento.

La [pipeline](../../backend/app/evaluation/agents/base.py), prima della correzione
del 16 settembre, passava ai builder specifiche prive degli anchor: i dati non
vuoti sostituivano il catalogo completo. Il primo intervento ora implementato
garantisce che definizioni e soglie arrivino realmente nel prompt, con una
versione riconoscibile e una verifica del prompt finale. Questo corregge la
consegna delle istruzioni; non dimostra ancora un aumento dell'accuratezza.

Mantenere Qwen3.5-4B quantizzato, un'unica richiesta alla volta e risposte brevi
strutturate. Prima di cambiare modello o runtime, ridurre duplicazioni e lavoro
di conteggio affidato al modello. Il guadagno di velocità resta da misurare:
i benchmark locali attuali riusano già il contesto archiviato e non eseguono RAG.

Tutte le prove previste usano strumenti locali gratuiti, senza chiamate Gemini,
Vertex o embedding remoti, né ripieghi automatici su servizi a pagamento.
Il vincolo è zero costi API o abbonamenti; restano le risorse del computer.

## Rapporto finale più utile

Mostrare prima il profilo dei nove criteri, raggruppati in copertura documentale
(C1–C2), aspetti didattici documentati (C3–C8) e comprensibilità editoriale (C9).
Per ogni criticità: passaggio, condizione non soddisfatta e correzione suggerita.
C3 e C4 restano distinti ma vicini nella presentazione; non introdurre pesi nuovi.

Tenere il CoreScore come sintesi secondaria, sempre con numero di criteri
valutati e motivi di non valutabilità. Otto punteggi 2 e un C8=0 producono 1,78/2:
la media va accompagnata dalla segnalazione della contraddizione. Se C8 è
indeterminabile, non presentare l'eventuale media alta come valutazione completa.
Non confrontare direttamente medie con rubriche o coperture diverse.

## Ordine di lavoro e condizioni per adottare i cambiamenti

| Passo | Risultato concreto | Verifica prima dell'adozione |
|---|---|---|
| **1. Regole consegnate e citazioni fedeli** | Catalogo unico, anchor completi nel prompt, identificativi delle evidenze e registrazione delle assenze | Tutti i prompt contengono gli anchor previsti; ogni citazione pubblicata è ricostruibile; errori e revisioni restano visibili |
| **2. Contesto fisso** | Passaggi selezionati, deduplicati e versionati per agente | Revisione della copertura dei riferimenti; nessuna chiamata remota; confronto di qualità e tempi a regole invariate |
| **3. Rubrica candidata** | Condizioni della tabella, esempi di confine, matrice C8, diagnostica bilingue estesa e nuova C9 | Valutatori indipendenti applicano la stessa versione; analisi separata di disaccordi, errori gravi e non valutabilità |
| **4. Rapporto e integrazione** | Profilo, evidenze, priorità e accesso alla valutazione locale nell'app | Miglioramenti confermati su casi nuovi; limiti dichiarati; scelta della versione registrata e reversibile |

Separare le modifiche nelle prove: prima la consegna degli anchor, poi il
meccanismo delle evidenze, poi il contesto e infine le nuove regole. Conservare
ogni configurazione e confrontare coppie che differiscono per un intervento
identificabile. Non attribuire al prompt un beneficio ottenuto cambiando anche
schema, rubrica o campione.

Per la validazione iniziale propongo un piccolo campione di **12–20 syllabus
indipendenti**, diversificati per disciplina, forma d'esame, lingua e completezza,
valutati da **due persone separatamente** prima del confronto con il modello.
È una dimensione pratica per un pilot, non una garanzia statistica. Richiede
disponibilità di valutatori senza incarichi a pagamento; con un solo valutatore
il risultato resta diagnostico e non misura l'accordo fra persone.

Preparare gli esempi sintetici di confine sul campione di sviluppo; congelare
rubrica e protocollo prima dei casi nuovi. Usare riformattazioni equivalenti
per C7, descrizioni chiare ma incoerenti per C6/C8 e assenze note per C1/C2.
I casi sintetici verificano regole specifiche, non sostituiscono i syllabus reali.

Misurare accordo esatto e ponderato con i giudizi umani, errori di due punti,
pertinenza delle evidenze, fallimenti, non valutabilità e stabilità su ripetizioni.
Riportare tempi totali, caricamento e condizioni di cache; non trattare
l'allocazione del modello come misura della RAM di picco. Nessun fallimento
deve sparire dal denominatore perché manca un punteggio.

Adottare un intervento solo quando risolve il problema dichiarato e il confronto
non mostra regressioni materiali negli altri aspetti. Le tolleranze di confronto
vanno fissate prima del pilot. Se il campione non permette di concludere, lasciare
la variante sperimentale. L'accordo con Gemini è un confronto storico secondario.

Questa proposta non abilita nuove soglie nell'applicazione. Dal 16 settembre
sono implementati la consegna completa degli anchor attivi e, nel percorso
sperimentale locale, la selezione delle evidenze e i riferimenti fissi A2/A4.
La validazione umana delle soglie candidate e la loro eventuale adozione
rimangono passaggi distinti; la pubblicazione di questo documento non le
presenta come miglioramenti già dimostrati.
