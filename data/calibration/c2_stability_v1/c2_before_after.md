# C2 stability — before/after (mini-fase `a1_v7`, pre-check deterministico)

Confronto sui **4 syllabi C2-instabili** della campagna self-consistency.
- **Before**: baseline `self_consistency_v1` (A1 = `a1_v6`).
- **After**: `c2_stability_v1`, 4 syllabi × 5 run (A1 = `a1_v7`, `english_coverage` + `suggested_c2`).
- Run after: 20/20 `completed` (0 partial, 0 failed, 0 agent_errors).

## C2 per syllabus

| Syllabus | C2 before (5 run) | unanim. | flip | stdev | C2 after (5 run) | unanim. | flip | stdev |
| --- | --- | :-: | :-: | :-: | --- | :-: | :-: | :-: |
| 01_COMPUTER_VISION_LAB | `[0,1,1,1,1]` | N | 0.20 | 0.40 | `[2,2,2,2,2]` | **Y** | 0.00 | 0.00 |
| 03_PEER_TO_PEER_LAB | `[1,0,0,1,1]` | N | 0.40 | 0.49 | `[1,1,1,1,1]` | **Y** | 0.00 | 0.00 |
| 05_COMPUTER_VISION | `[0,0,NA,0,1]` | N | 0.40 | 0.43 | `[1,1,1,1,1]` | **Y** | 0.00 | 0.00 |
| 08_VULN_ASSESSMENT_PT | `[1,1,0,1,1]` | N | 0.20 | 0.40 | `[2,2,2,2,2]` | **Y** | 0.00 | 0.00 |

## Aggregati C2 (sui 4)

| metrica | before | after |
| --- | :-: | :-: |
| unanimità | 0/4 (0.00) | **4/4 (1.00)** |
| flip-rate medio | 0.30 | **0.00** |
| stdev media | 0.43 | **0.00** |
| oscillazioni 0↔1 | 4 | **0** |
| oscillazioni 1↔2 | 0 | 0 |
| run NA / partial su C2 | 1 NA | **0** |

Tutte le 20 run hanno adottato lo score **suggerito** dal pre-check deterministico (01→2, 03→1, 05→1, 08→2): l'ibrido ha confermato il suggerimento in 20/20 casi, senza deviazioni.

## Impatto sul CoreScore

| Syllabus | CoreScore before (media / stdev) | CoreScore after (media / stdev) |
| --- | :-: | :-: |
| 01_COMPUTER_VISION_LAB | 1.60 / 0.089 | 1.71 / 0.089 |
| 03_PEER_TO_PEER_LAB | 1.59 / 0.126 | 1.58 / 0.083 |
| 05_COMPUTER_VISION | 1.38 / 0.114 | 1.38 / 0.054 |
| 08_VULN_ASSESSMENT_PT | 1.85 / 0.089 | 1.93 / 0.089 |

stdev media CoreScore: 0.105 → 0.077 (ridotta o invariata; mai aumentata).

## Lettura metodologica (obbligatoria)

Il fix migliora **sia la stabilità sia il livello** di C2, perché corregge una
**sottovalutazione sistematica** dovuta al payload/regola precedente — il titolo
inglese non veniva passato ad A1 e la rubrica libera era troppo severa — **non**
perché il sistema sia diventato più indulgente:

- `01_COMPUTER_VISION_LAB` e `08_VULN_ASSESSMENT_PT` hanno **copertura EN piena**
  (risultati di apprendimento, contenuti, modalità di verifica tutti presenti):
  il valore corretto è C2=2, non 0/1. Lo shift `→2` è la correzione del bug.
- `03_PEER_TO_PEER_LAB` e `05_COMPUTER_VISION` hanno una **sezione informativa EN
  mancante** (modalità di verifica): il valore corretto e stabile è C2=1.
- Nessun syllabus a copertura parziale è stato spinto a 2: il livello riflette la
  copertura reale, ora misurata in modo deterministico.

In sintesi: C2 passa da criterio più fragile a criterio **quasi deterministico con
supervisione LLM**; unanimità 0/4 → 4/4, flip-rate 0.30 → 0.00, senza sacrificare
la correttezza del livello.
