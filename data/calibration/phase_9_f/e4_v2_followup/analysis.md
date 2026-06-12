# Phase 9.F e4_v2 follow-up — analisi post-run

**Calibration mode:** `phase_9_f_e4_v2_followup`  
**Protocol version:** `phase_9_f_v1`  
**Prompt versions:** E4 `e4_v2`, E5 `e5_v1`  
**Data run:** 12 giugno 2026

## Esito sintetico

Il follow-up e' tecnicamente valido e ha superato tutti i guard
metodologici definiti prima della campagna:

- 5/5 evaluation core `completed`;
- 5/5 risultati estesi `completed`;
- zero `handler_errors`;
- zero NA tecnici;
- `handler_prompt_versions["E4"] == "e4_v2"` in tutte le run;
- `handler_prompt_versions["E5"] == "e5_v1"` in tutte le run;
- fixture E5 v1 riutilizzata senza modifica;
- `gcp_project_id` redatto negli artefatti JSON;
- verdetto automatico: **GREEN — every expectation met**.

La campagna e' durata 678.55 secondi.

## Risultati E4

| Caso | Atteso | Osservato | Verdetto |
|---|---:|---:|---|
| Advanced Computer Graphics | 1 | 1 | Fix funzionale confermato |
| Deep Learning | 2 | 2 | Controllo bilingue positivo invariato |
| Internet of Things | NA semantico | NA `handler_na` | Path pre-LLM preservato |
| Machine Learning | 0 | 0 | Caso grave non rilassato |
| Synthetic positive control | 2 | 2 | Controllo pienamente parallelo invariato |

Distribuzione osservata: score 0 x1, score 1 x1, score 2 x2,
NA semantico x1, NA tecnico x0. Il follow-up esercita quindi tutti
gli esiti metodologicamente rilevanti di E4.

## Verifica della correzione strutturale

### Advanced Computer Graphics

Con `e4_v1`, la sezione `course_content_it` veniva esclusa dal payload
perche' `course_content_en` era vuota. Il modello vedeva soltanto le
coppie presenti e assegnava 2.

Con `e4_v2`, il giudizio assegna correttamente **1** e cita
esplicitamente:

- la buona equivalenza delle coppie effettivamente confrontabili;
- `course_content` come sezione presente solo in italiano e quindi
  omissione rilevante;
- i descrittori di Dublino presenti solo in inglese come anomalia
  formale.

Il risultato non e' quindi un semplice drift stocastico: la
justification mostra che il nuovo perimetro informativo e la regola
di soglia hanno corretto esattamente il blind spot identificato in
`targeted_v1`.

### Guard di non regressione

- **Deep Learning = 2:** l'assenza di omissioni sostanziali non produce
  penalizzazioni spurie.
- **Internet of Things = NA semantico:** zero coppie sostanziali
  confrontabili continua a produrre NA prima della chiamata LLM,
  senza trasformarsi in errore tecnico.
- **Machine Learning = 0:** omissioni ampie e differenze semantiche
  gravi restano valutate con il minimo.
- **Synthetic positive = 2:** il controllo con perimetro IT/EN
  parallelo completo conserva il massimo.

## Decisione metodologica

`e4_v2` e' accettato come nuova versione del prompt/handler E4.

La modifica risolve il difetto strutturale di `e4_v1` senza
evidenziare regressioni sui quattro guard. La soglia esplicita agisce
come massimo ammissibile e non sostituisce il giudizio semantico:
contraddizioni e differenze di contenuto possono ancora abbassare il
punteggio.

`A5` resta correttamente versionato come `a5_v1`, poiche' il
coordinator non e' cambiato. La fonte di verita' della modifica e'
`handler_prompt_versions["E4"] == "e4_v2"`.

## Decisione E5

Il follow-up non modifica E5. La fixture e il prompt restano
rispettivamente `v1` ed `e5_v1`.

La baseline, la review manuale di Machine Learning e `targeted_v1`
mostrano che:

- `e5_v1` produce giudizi grounded e dual-source;
- il controllo sintetico raggiunge 2;
- i boundary reali raggiungono 1;
- il caso Machine Learning = 0 rimane un outlier severo isolato.

Non e' quindi giustificato introdurre `e5_v2` in Phase 9.F.

## Limiti residui

- Il follow-up e' diagnostico e contiene soltanto cinque casi.
- Il comportamento con almeno tre omissioni IT-only e con campi
  EN-only e' coperto dai test deterministici, ma non da ulteriori
  syllabus reali dedicati.
- Le evaluation core sono state rieseguite per completare il flusso
  E2E, ma eventuali variazioni dei punteggi C1-C9 non costituiscono
  oggetto di questa campagna.

## Verdetto finale

La calibrazione Phase 9.F puo' essere chiusa con:

- **E4:** promozione da `e4_v1` a `e4_v2`;
- **E5:** mantenimento di `e5_v1`;
- nessun ulteriore tuning necessario prima della PR Phase 9.F.

Gli artefatti `targeted_v1` restano immutati come prova storica del
comportamento `e4_v1`; gli artefatti di questa directory documentano
la correzione e i guard di non regressione di `e4_v2`.
