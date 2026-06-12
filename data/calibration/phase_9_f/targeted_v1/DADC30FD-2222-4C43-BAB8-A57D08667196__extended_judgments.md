<!-- calibration_mode=phase_9_f_targeted_v1 protocol_version=phase_9_f_v1 e5_fixture_version=v1 synthetic_fixture_version=v1 -->

# Extended judgments — DADC30FD-2222-4C43-BAB8-A57D08667196

- evaluation_uuid: `335d553a-d7a7-4436-b776-da88b1e1b103`
- extended status: `completed`
- handler_prompt_versions: `{'E4': 'e4_v1', 'E5': 'e5_v1'}`

## E4

- score: `2`  is_na: `False`  is_na_technical: `False`  confidence: `high`

### Justification

La versione inglese del syllabus mostra una sostanziale equivalenza semantica con la versione italiana per tutti i campi confrontati. La terminologia è coerente e non si riscontrano omissioni significative o cambi di significato che possano compromettere la comprensione dei contenuti o degli impegni didattici. Sebbene nel campo 'prerequisites_en' sia presente l'indicazione "ChatGPT ha detto:", tale annotazione non altera la coerenza semantica del contenuto dei prerequisiti stessi, che rimane fedele alla versione italiana.

### Evidences

1. Syllabus · `learning_outcomes_it`
   > Obiettivi formativi generali dell'insegnamento in termini di risultati di apprendimento attesi.
Conoscenza e capacità di comprensione (knowledge and understanding):
l'obiettivo del corso è quello di far acquisire conoscenze che consentano allo studente di comprendere le idee ed i principi che stanno alla base della crittografia moderna; in particolare lo studente acquisirà le conoscenze dei principali strumenti crittografici utilizzati in pratica.
Capacità di applicare conoscenza e comprensione (applying knowledge and understanding):
lo studente acquisirà le competenze necessarie per utilizzare in modo sicuro strumenti crittografici quali schemi di cifratura, di autentica e funzioni hash crittografiche.
Autonomia di giudizio (making judgements):
Attraverso esempi concreti di errori derivanti dall'utilizzo di soluzioni solo all'apparenza sicure lo studente sarà in grado di utilizzare autonomamente soluzioni crittografiche in grado di garantire elevati livelli di sicurezza.
Abilità comunicative (communication skills):
lo studente acquisirà le necessarie abilità comunicative e di appropriatezza espressiva nell'impiego del linguaggio tecnico nell'ambito generale della crittografia moderna.
Capacità di apprendimento (learning skills):
il corso si propone, come obiettivo, di fornire allo studente le necessarie metodologie teoriche e pratiche per poter affrontare e risolvere autonomamente nuove problematiche che dovessero richiedere l'utilizzo di strumenti crittografici quali cifrari, schemi di firme digitali e funzioni hash.

2. Syllabus · `learning_outcomes_en`
   > The goals of this course, in terms of expected results, are
Knowledge and understanding
. Students will learn the fundamental ideas and the basic principles of modern cryptography. More specifically, students will be able to understand some of the most important cryptographic schemes and primitives used in practice.
Applying knowledge and understanding.
Students will be able to use, in a secure way, cryptographic schemes such as encryption schemes, authentication schemes and cryptographic hash functions
Making judgements
. By studying concrete examples of seemingly secure (but wrong) solutions students will learn how to use cryptographic schemes providing high security guarantees.
Communication Skills
. Students will learn how to properly communicate using the technical language of modern cryptography
Learning Skills
. A goal of this course is to provide a good theoretical and practical background of modern cryptography. It is expected that students will learn how to autonomously address problems that require the usage of cryptographic primitives such as digital signatures, encryption schemes and cryptographic hash functions.

3. Syllabus · `prerequisites_it`
   > Per una adeguata comprensione dei contenuti del corso sono necessari i seguenti prerequisiti.
Basi di matematica discreta.
Nozioni basilari di algoritmi

4. Syllabus · `prerequisites_en`
   > ChatGPT ha detto:
For an adequate understanding of the course content, the following prerequisites are required:
Basics of discrete mathematics.
Basic knowledge of algorithms.

## E5

- score: `1`  is_na: `False`  is_na_technical: `False`  confidence: `high`

### Justification

Il syllabus dell'insegnamento di CRITTOGRAFIA mostra un'aderenza parziale agli usi dipartimentali. In particolare, la sezione dei prerequisiti presenta un elenco omogeneo che non distingue tra conoscenze culturali/generali e disciplinari/specialistiche, contrariamente a quanto esplicitamente richiesto dalle linee guida dipartimentali. Inoltre, nella sezione delle modalità di verifica, pur essendo presenti esempi di domande e un voto minimo per la prova scritta, manca l'esplicitazione del peso relativo delle componenti d'esame (scritto e orale) sul voto finale, un dettaglio richiesto per una piena aderenza. Anche la sezione dei riferimenti bibliografici è carente, poiché tutti i riferimenti citati non includono l'anno di pubblicazione, che è un elemento minimo obbligatorio. Tuttavia, la sezione relativa alla frequenza è ben allineata, indicando chiaramente che la frequenza non è obbligatoria ma fortemente consigliata, e non essendoci componenti pratiche specifiche, non sono necessarie ulteriori distinzioni.

### Evidences

1. Syllabus · `prerequisites_it`
   > Per una adeguata comprensione dei contenuti del corso sono necessari i seguenti prerequisiti.
Basi di matematica discreta.
Nozioni basilari di algoritmi

2. Documento esterno · `doc:1` · `external_1_v1__chunk_0001`
   > La distinzione può essere realizzata con elenchi separati, con sottosezioni esplicite o con un elenco unico organizzato in modo chiaramente separabile. Una semplice lista omogenea che mischi le due famiglie senza alcuna separazione **non** soddisfa l'uso.

3. Syllabus · `assessment_methods_it`
   > L'esame consiste di una prova scritta ed un colloquio orale. La prova scritta consiste, tipicamente, di 5 domande a risposta aperta.
Per superare la prova scritta è necessario ottenere una valutazione di almeno 18. La prova scritta può essere visionata prima di sostenere la prova orale.

4. Documento esterno · `doc:1` · `external_1_v1__chunk_0002`
   > esplicitare il **peso relativo** delle componenti dell'esame (scritto, orale, progetto, prova in itinere) sul voto finale, almeno qualitativamente (es. "il progetto pesa per circa metà del voto finale, lo scritto per circa metà");

5. Syllabus · `sample_questions_it`
   > Definizioni di sicurezza (cifrari simmetrici, asimmetrici, firme digitali, ecc)
Esercizi sulle primitive crittografiche studiate (ad esempio: dimostrare che un dato cifrario è insicuro)
Algoritmi (ad es. fornire e spiegare lo pseudocodice di algoritmi studiati a lezione)

6. Documento esterno · `doc:1` · `external_1_v1__chunk_0002`
   > includere **almeno una domanda esempio** rappresentativa, preferibilmente nella sezione apposita
  (`sample_questions_it`), oppure in fondo alla sezione modalità
  di verifica.

7. Syllabus · `references_it`
   > [1] M. Bellare, P. Rogaway “Introduction to Modern Cryptography”
Scaricabile da
http://www.cs.ucsd.edu/~mihir/cse107/classnotes.html
[2] V. Shoup A Computational Introduction to Number Theory and Algebra
Scaricabile da
http://shoup.net/ntb/
[3] J. Katz, Y. Lindell “Introduction to Modern Cryptography” CRC press

8. Documento esterno · `doc:1` · `external_1_v1__chunk_0002`
   > ogni riferimento bibliografico riportato nel syllabus
deve includere come minimo:

- **autore/autori** (cognome puntato è ammesso);
- **anno** di pubblicazione (anche solo l'edizione di riferimento);
- **titolo** completo dell'opera;
- **editore** (per i libri) o **rivista** (per gli articoli);
- **edizione** quando rilevante per il corso (es. terza edizione
  di un manuale per cui il syllabus indica capitoli specifici).

9. Syllabus · `attendance_it`
   > La frequenza delle lezioni non è obbligatoria ma fortemente consigliata.

10. Documento esterno · `doc:1` · `external_1_v1__chunk_0003`
   > la sezione deve indicare in modo esplicito:

- se la frequenza è **obbligatoria** o **facoltativa**;
