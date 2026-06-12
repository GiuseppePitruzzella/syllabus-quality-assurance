<!-- calibration_mode=phase_9_f_e4_v2_followup protocol_version=phase_9_f_v1 e5_fixture_version=v1 e4_prompt_version=e4_v2 expected_e4=NA-handler_na observed_e4=NA-handler_na role=real -->

# Extended judgments — 0B53E8E2-4B90-426F-A25C-3AA31FA4B649

- evaluation_uuid: `3f9261ff-d0fc-4af2-b929-997dce6ac49a`
- extended status: `completed`
- handler_prompt_versions: `{'E4': 'e4_v2', 'E5': 'e5_v1'}`

## E4

**NA semantico** (source: `handler_na`)

> Il perimetro inglese del syllabus è insufficiente per il confronto cross-lingua: nessuna coppia IT/EN con contenuto sostanziale valutabile su entrambe le versioni.

- score: `None`  is_na: `True`  is_na_technical: `False`  confidence: `high`

### Justification

Il syllabus non espone alcun campo bilingue con contenuto sostanziale su entrambe le versioni IT ed EN. Senza almeno una coppia confrontabile, qualsiasi giudizio numerico sarebbe arbitrario, quindi il criterio è dichiarato NA semantico.

## E5

- score: `0`  is_na: `False`  is_na_technical: `False`  confidence: `high`

### Justification

Il syllabus disattende in modo significativo le indicazioni dipartimentali esplicite fornite. In particolare, la sezione "Prerequisiti" presenta un elenco omogeneo senza la richiesta distinzione tra conoscenze culturali/generali e disciplinari/specialistiche. Inoltre, la sezione "Riferimenti bibliografici" non include alcun riferimento formattato secondo gli standard minimi richiesti (autore, anno, titolo, editore/rivista, edizione), fornendo solo link a slide e repository. Sebbene la sezione "Modalità di verifica" includa una domanda esempio e indicazioni sui requisiti minimi per le prove, manca l'esplicitazione del peso relativo delle diverse componenti d'esame sul voto finale, come raccomandato dagli usi dipartimentali.

### Evidences

1. Syllabus · `prerequisites_it`
   > Altamente consigliabile:
Programmazione a microcontrollori
Programmazione 2
Reti di Calcolatori

2. Documento esterno · `doc:1` · `external_1_v1__chunk_0001`
   > La distinzione può essere realizzata con elenchi separati, con
sottosezioni esplicite o con un elenco unico organizzato in modo
chiaramente separabile. Una semplice lista omogenea che mischi le
due famiglie senza alcuna separazione **non** soddisfa l'uso.

3. Syllabus · `references_it`
   > Sono disponibili le slides del corso pubblicamente:
https://docs.google.com/presentation/d/1s7WTns6GiE-XUIywNy83hqUFYQeAIBy3K5g6Zrj0bLo/edit?usp=sharing
Inoltre anche la repository pubblica dei progetti:
https://github.com/UniCT-Internet-of-Things

4. Documento esterno · `doc:1` · `external_1_v1__chunk_0002`
   > Ogni riferimento bibliografico riportato nel syllabus
deve includere come minimo:

- **autore/autori** (cognome puntato è ammesso);
- **anno** di pubblicazione (anche solo l'edizione di riferimento);
- **titolo** completo dell'opera;
- **editore** (per i libri) o **rivista** (per gli articoli);
- **edizione** quando rilevante per il corso (es. terza edizione
  di un manuale per cui il syllabus indica capitoli specifici).

5. Syllabus · `assessment_methods_it`
   > La verifica delle competenze acquisite viene effettuata tramite esame scritto e colloquio orale. La valutazione complessiva tiene conto della successiva prova progettuale.

6. Documento esterno · `doc:1` · `external_1_v1__chunk_0002`
   > - esplicitare il **peso relativo** delle componenti dell'esame
  (scritto, orale, progetto, prova in itinere) sul voto finale,
  almeno qualitativamente (es. "il progetto pesa per circa metà
  del voto finale, lo scritto per circa metà");
