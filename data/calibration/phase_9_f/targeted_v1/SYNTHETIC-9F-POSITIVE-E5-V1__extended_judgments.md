<!-- calibration_mode=phase_9_f_targeted_v1 protocol_version=phase_9_f_v1 e5_fixture_version=v1 synthetic_fixture_version=v1 -->

# Extended judgments — SYNTHETIC-9F-POSITIVE-E5-V1

- evaluation_uuid: `911bd62a-f7b8-41fb-878a-5fb2b8d3f242`
- extended status: `completed`
- handler_prompt_versions: `{'E4': 'e4_v1', 'E5': 'e5_v1'}`

## E4

- score: `2`  is_na: `False`  is_na_technical: `False`  confidence: `high`

### Justification

La versione inglese del syllabus presenta una sostanziale equivalenza semantica con la versione italiana per tutti i campi esaminati. La terminologia è coerente e non si riscontrano omissioni significative o cambiamenti di significato che possano compromettere la comprensione o l'aderenza ai contenuti didattici. Le traduzioni sono accurate e professionali.

### Evidences

1. Syllabus · `learning_outcomes_it`
   > Al termine del corso lo studente sarà in grado di: progettare protocolli di consenso distribuito tolleranti ai guasti; analizzare le proprietà di safety e liveness di algoritmi di replica; valutare il trade-off tra coerenza, disponibilità e tolleranza alle partizioni in sistemi reali; implementare un servizio replicato che usi un protocollo di consenso a sua scelta e ne dimostri le proprietà sperimentalmente.

2. Syllabus · `learning_outcomes_en`
   > At the end of the course the student will be able to: design fault-tolerant distributed consensus protocols; analyse safety and liveness properties of replication algorithms; evaluate the trade-off between consistency, availability and partition tolerance in real-world systems; implement a replicated service using a consensus protocol of choice and demonstrate its properties experimentally.

3. Syllabus · `assessment_methods_it`
   > L'esame si compone di tre componenti:

- **progetto**: peso 40% sul voto finale. Consiste nell'implementazione di un servizio replicato che usi un protocollo di consenso a scelta dello studente. Il progetto include una relazione tecnica con analisi delle proprietà di safety / liveness e una valutazione sperimentale.
- **prova scritta**: peso 40% sul voto finale. Tre domande aperte sui contenuti teorici del corso (FLP, CAP, scelta del protocollo, analisi di scenari di fallimento).
- **prova orale**: peso 20% sul voto finale. Discussione del progetto e approfondimento di un argomento a scelta del docente.

Voto minimo per accedere alla prova orale: 18/30 sia sulla prova scritta sia sulla relazione del progetto. La sufficienza sul voto finale richiede inoltre almeno 18/30 sulla prova orale. Per esempi rappresentativi delle domande della prova scritta e della discussione orale si veda la sezione 'Esempi di domande'.

4. Syllabus · `assessment_methods_en`
   > The exam comprises three components:

- **project**: weight 40% of the final mark. Consists of the implementation of a replicated service using a consensus protocol of the student's choice. The project includes a technical report with safety / liveness analysis and an experimental evaluation.
- **written test**: weight 40% of the final mark. Three open questions on the theoretical content of the course (FLP, CAP, protocol selection, failure scenarios).
- **oral test**: weight 20% of the final mark. Discussion of the project and in-depth treatment of a topic chosen by the lecturer.

Minimum mark to access the oral test: 18/30 on both the written test and the project report. A pass on the final mark additionally requires at least 18/30 on the oral test. Sample questions for the written and oral parts are listed in the 'Sample questions' section.

## E5

- score: `2`  is_na: `False`  is_na_technical: `False`  confidence: `high`

### Justification

Il syllabus dimostra un'aderenza sostanziale alle istruzioni operative locali fornite nel documento 'Usi dipartimentali'. In particolare, la sezione dei prerequisiti distingue chiaramente tra 'Conoscenze culturali / generali' e 'Conoscenze disciplinari / specialistiche', come richiesto. Le modalità di verifica dell'apprendimento esplicitano i pesi percentuali di ciascuna componente d'esame (progetto, prova scritta, prova orale) e indicano i voti minimi necessari per accedere alle fasi successive, oltre a includere esempi di domande. Infine, la sezione relativa alla frequenza specifica in modo dettagliato se è obbligatoria o facoltativa per le diverse componenti (lezioni teoriche e laboratorio) e le relative soglie, e i riferimenti bibliografici sono completi di autore, anno, titolo, editore ed edizione, rispettando il formato minimo richiesto.

### Evidences

1. Syllabus · `prerequisites_it`
   > **Conoscenze culturali / generali**: capacità di formalizzare un protocollo con notazione precisa; familiarità con il ragionamento per casi e per induzione; capacità di leggere e analizzare testi tecnici in inglese; nozioni di base di logica matematica (predicati, quantificatori).

**Conoscenze disciplinari / specialistiche**: strutture dati e algoritmi (alberi bilanciati, grafi, complessità asintotica); sistemi operativi (processi, scheduling, sincronizzazione e mutua esclusione); reti di calcolatori (modello a strati ISO/OSI, TCP/UDP, RPC); programmazione concorrente di base (thread, lock, monitor); fondamenti di basi di dati (transazioni ACID, livelli di isolamento).

2. Documento esterno · `doc:1` · `external_1_v1__chunk_0001`
   > La distinzione può essere realizzata con elenchi separati, con sottosezioni esplicite o con un elenco unico organizzato in modo chiaramente separabile. Una semplice lista omogenea che mischi le due famiglie senza alcuna separazione **non** soddisfa l'uso.

3. Syllabus · `assessment_methods_it`
   > L'esame si compone di tre componenti:

- **progetto**: peso 40% sul voto finale. Consiste nell'implementazione di un servizio replicato che usi un protocollo di consenso a scelta dello studente. Il progetto include una relazione tecnica con analisi delle proprietà di safety / liveness e una valutazione sperimentale.
- **prova scritta**: peso 40% sul voto finale. Tre domande aperte sui contenuti teorici del corso (FLP, CAP, scelta del protocollo, analisi di scenari di fallimento).
- **prova orale**: peso 20% sul voto finale. Discussione del progetto e approfondimento di un argomento a scelta del docente.

Voto minimo per accedere alla prova orale: 18/30 sia sulla prova scritta sia sulla relazione del progetto. La sufficienza sul voto finale richiede inoltre almeno 18/30 sulla prova orale. Per esempi rappresentativi delle domande della prova scritta e della discussione orale si veda la sezione 'Esempi di domande'.

4. Syllabus · `sample_questions_it`
   > - Si enunci e si discuta il risultato di impossibilità FLP. In quali condizioni resta valido? Quali ipotesi vengono rilassate dai protocolli pratici come Paxos e Raft?
- Si confrontino la linearizzabilità e la coerenza sequenziale, fornendo un esempio di esecuzione che le distingue.
- Si analizzi il comportamento di Raft in presenza di una partizione di rete simmetrica che isola il leader: chi può eleggere un nuovo leader e con quali garanzie di safety?
- Si discuta la motivazione dietro l'uso dei lease nel leader management e le condizioni per la loro correttezza.

5. Documento esterno · `doc:1` · `external_1_v1__chunk_0002`
   > - esplicitare il **peso relativo** delle componenti dell'esame
  (scritto, orale, progetto, prova in itinere) sul voto finale,
  almeno qualitativamente (es. "il progetto pesa per circa metà
  del voto finale, lo scritto per circa metà");
- indicare se è previsto un **voto minimo** sulle singole
  componenti per accedere alla componente successiva;
- includere **almeno una domanda esempio** rappresentativa,
  preferibilmente nella sezione apposita
  (`sample_questions_it`), oppure in fondo alla sezione modalità
  di verifica.

6. Syllabus · `references_it`
   > - M. van Steen, A. S. Tanenbaum, *Distributed Systems*, 4ª edizione, distributed-systems.net, 2023.
- N. A. Lynch, *Distributed Algorithms*, 1ª edizione, Morgan Kaufmann, 1996.
- C. Cachin, R. Guerraoui, L. Rodrigues, *Introduction to Reliable and Secure Distributed Programming*, 2ª edizione, Springer, 2011.
- M. Kleppmann, *Designing Data-Intensive Applications*, 1ª edizione, O'Reilly, 2017.

7. Documento esterno · `doc:1` · `external_1_v1__chunk_0002`
   > ogni riferimento bibliografico riportato nel syllabus
deve includere come minimo:

- **autore/autori** (cognome puntato è ammesso);
- **anno** di pubblicazione (anche solo l'edizione di riferimento);
- **titolo** completo dell'opera;
- **editore** (per i libri) o **rivista** (per gli articoli);
- **edizione** quando rilevante per il corso (es. terza edizione
  di un manuale per cui il syllabus indica capitoli specifici).

8. Syllabus · `attendance_it`
   > La frequenza alle lezioni teoriche è facoltativa ma fortemente consigliata. La frequenza al laboratorio è obbligatoria al 75% delle ore: gli studenti che non raggiungono questa soglia dovranno concordare con il docente un percorso integrativo di recupero pratico prima di sostenere l'esame.

9. Documento esterno · `doc:1` · `external_1_v1__chunk_0003`
   > la sezione deve indicare in modo esplicito:

- se la frequenza è **obbligatoria** o **facoltativa**;
- in caso di obbligatorietà parziale (es. solo per la componente
  di laboratorio), specificare quale componente è soggetta a
  obbligo;
- per gli insegnamenti con componenti pratiche (laboratorio,
  esercitazioni), indicare il livello di frequenza atteso anche
  quando non strettamente obbligatorio (es. "fortemente
  raccomandata per la componente di laboratorio").
