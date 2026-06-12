<!-- calibration_mode=phase_9_f_e4_v2_followup protocol_version=phase_9_f_v1 e5_fixture_version=v1 e4_prompt_version=e4_v2 expected_e4=score:1 observed_e4=score:1 role=real -->

# Extended judgments — 3ED4B3BB-D25C-4EA3-BC50-14A310BEF4FF

- evaluation_uuid: `624e70bb-ef87-4189-b99c-66de17a66c7e`
- extended status: `completed`
- handler_prompt_versions: `{'E4': 'e4_v2', 'E5': 'e5_v1'}`

## E4

- score: `1`  is_na: `False`  is_na_technical: `False`  confidence: `high`

### Justification

La versione inglese del syllabus presenta una buona equivalenza semantica per i campi presenti in entrambe le lingue, come i risultati di apprendimento, i prerequisiti e le modalità di valutazione. Tuttavia, la sezione relativa al contenuto del corso (`course_content`) è presente solo in italiano, costituendo un'omissione rilevante nella versione inglese. Inoltre, sono presenti campi relativi ai descrittori di Dublino (`dublin_knowledge`, `dublin_applying`, `dublin_communication`, `dublin_learning`) solo nella versione inglese, che rappresentano un'anomalia formale. Queste lacune impediscono di assegnare il punteggio massimo, portando a un allineamento parziale.

### Evidences

1. Syllabus · `learning_outcomes_it`
   > Conoscenza
e capacità di comprensione (knowledge and understanding):
a) data
visualization: lo studente apprenderà i principi della corretta
visualizzazione dati seguento l’approccio strutturato della
‘Grammar of Graphics’.
b) visual programming: lo studente
apprenderà i prinicipi generali dello stile di programmazione
mediante reti di nodi con particolare riferimento al loro uso nel
sistema Blender.

2. Syllabus · `learning_outcomes_en`
   > Knowledge and Understanding:
a) Data Visualization: The student will learn the principles of proper data visualization using the structured approach of the 'Grammar of Graphics'.
b) Visual Programming: The student will learn the general principles of the node-based programming style, with particular reference to their use in the Blender system.

3. Syllabus · `course_content_it`
   > Modulo
Data Visualization
(3cfu)
In questo primo modulo del
corso si affronta il tema della rappresentazione grafica di
informazioni numeriche e/o qualitative a partire da una collezione
strutturata di dati.
Si fornisce una breve panoramica storica
presentando esempi di data visualizaztion precursori dei metodi
moderni.
Si
affrontano successivamente alcune problematiche rilevanti relative
alla percezione visuale passando in rassegna le leggi della Gestalt e
alla valutazione dello stile grafico secondo le regole di E.Tufte.
Dopo
aver presentato una rapida tassonomia dei grafici più comuni nella
reportistica tecnica attuale si introduce l’approccio strutturale
della ‘Grammar of Graphics’ di L.Wilkinson dapprima nel sup
aspetto teorico e successivamente con attività di laboratorio in
Python.
Le
attività di laboratorio includono lo sviluppo di ‘notebook’ che
utilizzino le librerie pandas, matplotlib, seaborn e plotnine.
Modulo
Visual programming (3cfu)
In
questo modulo dopo avere presentato una breve storia dell’approccio
visuale alla programmazione e illustarto alcuni degli esempi pù noti
si presentano gli ambienti di sviluppo ‘a nodi’ presenti dentro
il software 3d Blender con particolare riferimento al sistema detto
dei ‘geometry nodes’..
Giustificata
con esempi rilevanti la opportunità e il valore dlelo sviluppo di
asset parametrici vs asset fissi si svolgono attività di laboratorio
che presentano via via i ‘nodi’ base e i ‘nodi’ avanzati per
completare lo sviluppo di asset complessi sia statici che animati.

4. Syllabus · `dublin_knowledge_en`
   > a) Data Visualization: The student will learn the principles of proper data visualization using the structured approach of the 'Grammar of Graphics'.
b) Visual Programming: The student will learn the general principles of the node-based programming style, with particular reference to their use in the Blender system.

## E5

- score: `0`  is_na: `False`  is_na_technical: `False`  confidence: `high`

### Justification

Il syllabus presenta diverse e significative non conformità rispetto agli usi dipartimentali esplicitati nel documento esterno. In particolare, la sezione dei prerequisiti non distingue tra conoscenze culturali/generali e disciplinari/specialistiche, contravvenendo all'indicazione che una lista omogenea non soddisfa l'uso. Inoltre, i riferimenti bibliografici non includono l'anno di pubblicazione per le opere citate, un requisito minimo e non negoziabile secondo le linee guida. Anche la sezione relativa alle modalità di frequenza è generica, rimandando alle regole del Corso di Studio anziché esplicitare lo status per l'insegnamento specifico, e la sezione delle domande d'esempio non fornisce una domanda concreta, ma solo una descrizione generica delle tipologie di prove.

### Evidences

1. Syllabus · `prerequisites_it`
   > Conoscenza della programmazione strutturata ed ad oggetti con particolare riferimento al linguaggio Python.
Conoscenza delle nozioni di base di statistica descrittiva e testing di ipotesi.
Conoscenza delle nozioni base di Interazione Uomo/Macchina.
Esperienza nell’utilizzo di un sistema di un ambiente di sviluppo di asset grafici 3d con particolare riferimento a Blender.
Nozioni sui grafi.

2. Documento esterno · `doc:1` · `external_1_v1__chunk_0001`
   > Una semplice lista omogenea che mischi le due famiglie senza alcuna separazione **non** soddisfa l'uso.

3. Syllabus · `references_it`
   > ‘The Grammar of Graphics’ L.Wilkinsonet alii, Springer 2nd ed.
-
‘Non designer’s design book’, R.Williams, Pearson ed.

4. Documento esterno · `doc:1` · `external_1_v1__chunk_0002`
   > ogni riferimento bibliografico riportato nel syllabus deve includere come minimo:

- **autore/autori** (cognome puntato è ammesso);
- **anno** di pubblicazione (anche solo l'edizione di riferimento);
- **titolo** completo dell'opera;
- **editore** (per i libri) o **rivista** (per gli articoli);
- **edizione** quando rilevante per il corso (es. terza edizione
  di un manuale per cui il syllabus indica capitoli specifici).

5. Documento esterno · `doc:1` · `external_1_v1__chunk_0003`
   > il livello minimo di dettaglio sopra resta non negoziabile.

6. Syllabus · `attendance_it`
   > Seconod le regole del corso di Studio

7. Documento esterno · `doc:1` · `external_1_v1__chunk_0003`
   > la sezione deve indicare in modo esplicito:

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

8. Syllabus · `sample_questions_it`
   > Le prove di Laboratorio richiedono lo sviluppo di alcune tipologie di grafico (barplot, pieplot, scatterplot multimodali, denisty plot, denisty matrix etc) a partire da basi di dati tabellari con max 300 records a 10 campi (numerici e/o categoriali).

9. Documento esterno · `doc:1` · `external_1_v1__chunk_0002`
   > - includere **almeno una domanda esempio** rappresentativa,
  preferibilmente nella sezione apposita
  (`sample_questions_it`), oppure in fondo alla sezione modalità
  di verifica.
