<!-- calibration_mode=phase_9_f_baseline protocol_version=phase_9_f_v1 e5_fixture_version=v1 -->

# Extended judgments — 0B53E8E2-4B90-426F-A25C-3AA31FA4B649

- evaluation_uuid: `82aacfd9-6e21-4789-865f-48f4e5ca6ddb`
- extended status: `completed`
- handler_prompt_versions: `{'E4': 'e4_v1', 'E5': 'e5_v1'}`

## E4

**NA semantico** (source: `handler_na`)

> Il perimetro inglese del syllabus è insufficiente per il confronto cross-lingua: nessuna coppia IT/EN con contenuto valutabile su entrambe le versioni.

- score: `None`  is_na: `True`  is_na_technical: `False`  confidence: `high`

### Justification

Il syllabus non espone alcun campo bilingue con contenuto su entrambe le versioni IT ed EN. Senza almeno una coppia confrontabile, qualsiasi giudizio numerico sarebbe arbitrario, quindi il criterio è dichiarato NA semantico.

## E5

- score: `0`  is_na: `False`  is_na_technical: `False`  confidence: `high`

### Justification

Il syllabus disattende in modo significativo diverse indicazioni esplicite fornite dagli usi dipartimentali. In particolare, la sezione dei prerequisiti non distingue tra conoscenze culturali/generali e disciplinari/specialistiche, presentando una lista omogenea che non soddisfa l'uso dipartimentale. Inoltre, la sezione dei riferimenti bibliografici non include testi nel formato richiesto (autore, anno, titolo, editore/rivista), fornendo solo link a slide e repository. Sebbene la sezione delle modalità di verifica includa una domanda esempio e indicazioni sui voti minimi, manca l'esplicitazione del peso relativo delle diverse componenti d'esame sul voto finale, rendendola solo parzialmente aderente. La combinazione di queste non conformità porta a un giudizio di non aderenza.

### Evidences

1. Syllabus · `prerequisites_it`
   > Altamente consigliabile:
Programmazione a microcontrollori
Programmazione 2
Reti di Calcolatori

2. Documento esterno · `doc:1` · `external_1_v1__chunk_0001`
   > La distinzione può essere realizzata con elenchi separati, con sottosezioni esplicite o con un elenco unico organizzato in modo chiaramente separabile. Una semplice lista omogenea che mischi le due famiglie senza alcuna separazione **non** soddisfa l'uso.

3. Syllabus · `assessment_methods_it`
   > Il voto è attribuito secondo il seguente schema:
Non approvato: lo studente non ha acquisito i concetti di base e non è in grado di rispondere ad almeno il 60% delle domande né di svolgere gli esercizi teorici e pratici.
18-20 : lo studente dimostra una padronanza appena sufficiente dei concetti base, e/o riesce ad impostare gli esercizi teorico/pratici con molta difficoltà e con vari errori.
20 - 25 : lo studente ha superato con successo la prova scritta ed orale, dimostrando una buona padronanza dei contenuti del corso
25 - 29: lo studente ha affrontato la prova progettuale
29 - 30 e lode : lo studente ha affrontato tutte le prove d'esame, riuscendo inoltre a progettare e a sviluppare un progetto IoT senza problemi.

4. Documento esterno · `doc:1` · `external_1_v1__chunk_0002`
   > - esplicitare il **peso relativo** delle componenti dell'esame (scritto, orale, progetto, prova in itinere) sul voto finale, almeno qualitativamente (es. "il progetto pesa per circa metà del voto finale, lo scritto per circa metà");

5. Syllabus · `sample_questions_it`
   > Realizzare una soluzione IoT per monitorare una coltivazione di piante

6. Documento esterno · `doc:1` · `external_1_v1__chunk_0002`
   > - includere **almeno una domanda esempio** rappresentativa, preferibilmente nella sezione apposita (`sample_questions_it`), oppure in fondo alla sezione modalità di verifica.

7. Syllabus · `references_it`
   > Sono disponibili le slides del corso pubblicamente:
https://docs.google.com/presentation/d/1s7WTns6GiE-XUIywNy83hqUFYQeAIBy3K5g6Zrj0bLo/edit?usp=sharing
Inoltre anche la repository pubblica dei progetti:
https://github.com/UniCT-Internet-of-Things

8. Documento esterno · `doc:1` · `external_1_v1__chunk_0002`
   > Uso: ogni riferimento bibliografico riportato nel syllabus deve includere come minimo:

- **autore/autori** (cognome puntato è ammesso);
- **anno** di pubblicazione (anche solo l'edizione di riferimento);
- **titolo** completo dell'opera;
- **editore** (per i libri) o **rivista** (per gli articoli);
- **edizione** quando rilevante per il corso (es. terza edizione di un manuale per cui il syllabus indica capitoli specifici).
