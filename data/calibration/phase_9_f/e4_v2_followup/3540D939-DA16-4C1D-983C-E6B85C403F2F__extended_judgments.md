<!-- calibration_mode=phase_9_f_e4_v2_followup protocol_version=phase_9_f_v1 e5_fixture_version=v1 e4_prompt_version=e4_v2 expected_e4=score:2 observed_e4=score:2 role=real -->

# Extended judgments — 3540D939-DA16-4C1D-983C-E6B85C403F2F

- evaluation_uuid: `71efc174-4aab-4ab6-9835-d474409d0b63`
- extended status: `completed`
- handler_prompt_versions: `{'E4': 'e4_v2', 'E5': 'e5_v1'}`

## E4

- score: `2`  is_na: `False`  is_na_technical: `False`  confidence: `high`

### Justification

La versione inglese del syllabus mostra un'equivalenza semantica sostanziale con la versione italiana. Non sono state riscontrate omissioni rilevanti di contenuto in nessuna delle due lingue, né contraddizioni o cambi di significato. La terminologia utilizzata è coerente e le informazioni veicolate sono le medesime in entrambe le versioni, sebbene in alcuni punti la versione italiana dei descrittori di Dublino appaia frammentata rispetto alla versione inglese che fornisce il contesto completo della frase.

### Evidences

1. Syllabus · `prerequisites_it`
   > Solide basi di Deep Learning (reti neurali convoluzionali e ricorrenti, backpropagation, regolarizzazione) e familiarità con la programmazione scientifica in Python.

2. Syllabus · `prerequisites_en`
   > Solid foundation of Deep Learning (convolutional and recurrent neural networks, backpropagation, regularization) and familiarity with scientific programming in Python.

3. Syllabus · `course_content_it`
   > Il corso "Deep Learning: Advanced Models and Methods" esplora le attuali frontiere del Deep Learning. Si inizia con tecniche avanzate per migliorare la generalizzazione e l'efficienza dei modelli: Metric Learning (apprendimento di spazi di rappresentazione semantica) e Domain Adaptation (adattamento a dati provenienti da distribuzioni diverse). Verrà introdotta la Knowledge Distillation per trasferire conoscenze da modelli complessi a modelli più efficienti. Seguirà il modulo Unsupervised e Self-Supervised Representation Learning, cruciale per sfruttare grandi quantità di dati non etichettati per apprendere rappresentazioni significative. Ampio spazio sarà dedicato al Multimodal Learning, includendo metodi capaci di gestire dati che includono diverse modalità, quali immagini, video, audio, e testo. Verranno dunque trattati metodi avanzati di modellamento di dati sequenziali, quali gli state space models. Infine, si concluderà con un'introduzione ai principi e agli algoritmi fondamentali del Reinforcement Learning, con esempi di applicazione in contesti decisionali.

4. Syllabus · `course_content_en`
   > The course "Deep Learning: Advanced Models and Methods" explores the current frontiers of Deep Learning. It starts with advanced techniques to improve the generalization and efficiency of models: Metric Learning (learning semantic representation spaces) and Domain Adaptation (adaptation to data from different distributions). Knowledge Distillation will be introduced to transfer knowledge from complex models to more efficient models. This will be followed by the Unsupervised and Self-Supervised Representation Learning module, which is crucial for exploiting large amounts of unlabeled data to learn meaningful representations. Ample space will be dedicated to Multimodal Learning, including methods capable of managing data that include different modalities, such as images, video, audio, and text. Advanced methods of modeling sequential data, such as state space models, will therefore be discussed. Finally, it will conclude with an introduction to the fundamental principles and algorithms of Reinforcement Learning, with examples of application in decision-making contexts.

## E5

- score: `1`  is_na: `False`  is_na_technical: `False`  confidence: `medium`

### Justification

Il syllabus presenta un'aderenza parziale agli usi dipartimentali. In particolare, la sezione dei prerequisiti non distingue tra conoscenze culturali/generali e disciplinari/specialistiche, come esplicitamente richiesto dalle linee guida, che considerano una lista omogenea non aderente. Inoltre, la sezione sulla frequenza, pur indicando che non è obbligatoria, non specifica il livello di frequenza atteso per le attività di laboratorio menzionate nelle metodologie didattiche, rientrando nella casistica di aderenza parziale. Anche la sezione dei riferimenti bibliografici mostra una parziale aderenza, in quanto il primo riferimento, pur essendo materiale didattico, non segue il formato minimo richiesto per i riferimenti bibliografici. La sezione delle modalità di verifica, invece, è maggiormente aderente, specificando i pesi relativi delle componenti d'esame e fornendo domande esempio, sebbene non indichi esplicitamente eventuali voti minimi per l'accesso alle componenti successive.

### Evidences

1. Syllabus · `prerequisites_it`
   > Solide basi di Deep Learning (reti neurali convoluzionali e ricorrenti, backpropagation, regolarizzazione) e familiarità con la programmazione scientifica in Python.

2. Documento esterno · `doc:1` · `external_1_v1__chunk_0001`
   > Una semplice lista omogenea che mischi le due famiglie senza alcuna separazione **non** soddisfa l'uso.

3. Syllabus · `attendance_it`
   > La regolare partecipazione alle lezioni non è obbligatoria ma vivamente raccomandata per una comprensione approfondita degli argomenti e delle metodologie.

4. Documento esterno · `doc:1` · `external_1_v1__chunk_0003`
   > Un syllabus che lascia la sezione vuota o si limita a indicazioni generiche tipo "frequenza consigliata" senza distinguere componenti pratiche e teoriche è considerato parzialmente aderente.

5. Syllabus · `references_it`
   > Materiale fornito dal docente e distribuito tramite il sito del docente (
http://antoninofurnari.github.io/
) e il team con codice “cq90ptp”.

6. Documento esterno · `doc:1` · `external_1_v1__chunk_0002`
   > ogni riferimento bibliografico riportato nel syllabus
deve includere come minimo:

- **autore/autori** (cognome puntato è ammesso);
- **anno** di pubblicazione (anche solo l'edizione di riferimento);
- **titolo** completo dell'opera;
- **editore** (per i libri) o **rivista** (per gli articoli);
- **edizione** quando rilevante per il corso (es. terza edizione
  di un manuale per cui il syllabus indica capitoli specifici).

7. Syllabus · `assessment_methods_it`
   > A ciascuna delle due prove è assegnato un punteggio in trentesimi e il voto finale assegnato al modulo è ottenuto mediante la media aritmetica dei due voti.

8. Syllabus · `sample_questions_it`
   > ·
Illustrare il concetto di Metric Learning e il suo uso per migliorare sistemi di localizzazione basati su immagini.
·
Spiegare la differenza tra Domain Adaptation e Transfer Learning tradizionale, descrivendo un algoritmo di Domain Adaptation basato su reti avversarie.
·
Descrivere il concetto di Knowledge Distillation e come può essere utilizzata per migliorare l'efficienza di un modello.
·
Spiegare i principi del Deep Unsupervised e Self-Supervised Representation Learning, evidenziandone le differenze e i benefici per i dati non etichettati.
·
Spiegare l'importanza dell'allineamento tra modalità nei modelli multimodali.
·
Illustrare i principali vantaggi dei modelli sequenziali ricorrenti basati su state space models.
·
Illustrare i principi di base del Reinforcement Learning.
Si precisa che tali domande hanno carattere puramente indicativo: le domande proposte all'esame potranno divergere, anche in modo significativo.

9. Documento esterno · `doc:1` · `external_1_v1__chunk_0002`
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
