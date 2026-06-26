# Phase 5.8 — Human-judgment aggregate report

- Generated at: `2026-06-26T09:30:52.747202+00:00`
- Evaluators: **1**
- Primary metrics exclude `NA` and missing cells; those observations are reported separately as process counts.
- The strict system-vs-expert comparison also follows the comparability audit: C1/C3/C4/C5/C6 primary; C2/C7/C8/C9 secondary; none excluded.
- No automatic majority/consensus score is computed.

> Single-rater diagnostic validation: this report supports a system-vs-expert comparison, not inter-rater reliability.

## System vs evaluator `expert_01`

- N syllabi: **8**
- Strict-primary criteria: **C1, C3, C4, C5, C6**
- Strict-primary numeric pairs: **40**
- Strict-primary kappa = **0.368**
- Strict-primary accuracy = **0.725**
- Strict-primary MAE = **0.275**

- Mean-score MAE on strict-primary criteria: **0.225**
- Legacy all-C1-C9 CoreScore MAE (descriptive only): **0.239**

### Comparability tiers

| Tier | Criteria | numeric pairs | κ weighted | acc | MAE |
| --- | --- | ---: | ---: | ---: | ---: |
| Primary | C1, C3, C4, C5, C6 | 40 | 0.368 | 0.725 | 0.275 |
| Secondary | C2, C7, C8, C9 | 32 | 0.22 | 0.562 | 0.5 |
| Excluded | none | 0 | — | — | — |

### Per-criterion (system vs this evaluator)

| Crit | obs | primary | NA excl. | missing excl. | κ weighted | acc | MAE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C1 | 8 | 8 | 0 | 0 | 0.0 | 0.75 | 0.25 |
| C2 | 8 | 8 | 0 | 0 | 0.333 | 0.5 | 0.625 |
| C3 | 8 | 8 | 0 | 0 | 0.0 | 0.625 | 0.375 |
| C4 | 8 | 8 | 0 | 0 | 0.0 | 0.75 | 0.25 |
| C5 | 8 | 8 | 0 | 0 | 0.0 | 0.5 | 0.5 |
| C6 | 8 | 8 | 0 | 0 | 1.0 | 1.0 | 0.0 |
| C7 | 8 | 8 | 0 | 0 | 0.091 | 0.375 | 0.625 |
| C8 | 8 | 8 | 0 | 0 | 0.0 | 0.875 | 0.125 |
| C9 | 8 | 8 | 0 | 0 | 0.0 | 0.5 | 0.625 |

### CoreScore per syllabus (system vs human)

| Syllabus | system | human | delta |
| --- | ---: | ---: | ---: |
| `88B7C1CE` COMPUTER VISION E LABORATORIO | 1.44 | 1.56 | 0.12 |
| `0B53E8E2` INTERNET OF THINGS | 1.56 | 1.22 | 0.34 |
| `F4AF1512` PEER TO PEER AND WIRELESS NETWORKS E LABORATORIO | 1.44 | 1.78 | 0.34 |
| `9A90BBCE` MULTIMEDIA E LABORATORIO | 1.44 | 1.78 | 0.34 |
| `89E21813` COMPUTER VISION | 1.44 | 1.22 | 0.22 |
| `E2446DF6` OTTIMIZZAZIONE | 1.67 | 1.89 | 0.22 |
| `3540D939` Deep Learning | 1.78 | 1.78 | 0.0 |
| `46D62804` VULNERABILITY ASSESSMENT E PENETRATION TESTING (VAPT) | 1.67 | 2 | 0.33 |

### Top disagreements (system vs this evaluator)

- **C2** on `88B7C1CE` (COMPUTER VISION E LABORATORIO) — system=0 vs human=2  (delta 2)
  - system: Nonostante il flag `has_english` sia impostato su true, la versione inglese del titolo del corso non è presente nel syllabus fornito. Il perimetro minimo bilingue richiede la disponibilità del titolo del corso anche in inglese, che in quest
  - human:  
- **C9** on `F4AF1512` (PEER TO PEER AND WIRELESS NETWORKS E LABORATORIO) — system=0 vs human=2  (delta 2)
  - system: Il syllabus presenta numerosi difetti editoriali che ne compromettono la chiarezza e la professionalità. Si riscontrano errori grammaticali e di punteggiatura, come la frase incompleta in `dublin_communication_it`. La formattazione è gravem
  - human:  buona
- **C1** on `88B7C1CE` (COMPUTER VISION E LABORATORIO) — system=2 vs human=1  (delta 1)
  - system: Tutte le nove sezioni obbligatorie previste dalle Linee Guida UniCT (RA, PR, CN, MV, ED, TD, MS, MF, PRG) sono presenti nel syllabus e compilate in modo sostanziale. Ogni sezione contiene informazioni specifiche e dettagliate, dimostrando u
  - human:  Prerequisiti ha un contenuto minimo
- **C1** on `0B53E8E2` (INTERNET OF THINGS) — system=2 vs human=1  (delta 1)
  - system: Il syllabus presenta tutte le nove sezioni obbligatorie richieste dalle Linee Guida UniCT (RA, PR, CN, MV, ED, TD, MS, MF, PRG) e ciascuna di esse risulta compilata in modo sostanziale. Tutte le informazioni richieste sono presenti e dettag
  - human:  Tutte le sezioni sono presenti ma alcune sono stringate
- **C2** on `9A90BBCE` (MULTIMEDIA E LABORATORIO) — system=1 vs human=2  (delta 1)
  - system: Il syllabus dichiara la disponibilità della versione inglese (`has_english: true`) e presenta traduzioni per i risultati di apprendimento, i contenuti e le modalità di verifica. Tuttavia, il titolo del corso non è tradotto in inglese e alcu
  - human:  
- **C2** on `89E21813` (COMPUTER VISION) — system=1 vs human=0  (delta 1)
  - system: La versione inglese del syllabus è parzialmente presente per il perimetro minimo richiesto. Sebbene il titolo, i risultati di apprendimento e i contenuti siano forniti in inglese, la sezione relativa alle modalità di verifica (`assessment_m
  - human:  La version in inglese non è altrettanto articolata quanto quella italiana.
- **C2** on `E2446DF6` (OTTIMIZZAZIONE) — system=1 vs human=2  (delta 1)
  - system: Sebbene il syllabus indichi la disponibilità di una versione inglese (`has_english: true`) e la maggior parte delle sezioni richieste siano tradotte, il titolo del corso non è presente in inglese. Inoltre, uno dei descrittori di Dublino (Au
  - human:  
- **C3** on `88B7C1CE` (COMPUTER VISION E LABORATORIO) — system=1 vs human=2  (delta 1)
  - system: La formulazione dei risultati di apprendimento attesi presenta un livello di specificità variabile. Alcuni descrittori, come 'Capacità di applicare conoscenza e comprensione' e 'Autonomia di giudizio', sono formulati in modo specifico e ver
  - human:  
- **C3** on `9A90BBCE` (MULTIMEDIA E LABORATORIO) — system=1 vs human=2  (delta 1)
  - system: I risultati di apprendimento attesi presentano una formulazione mista. Alcuni sono specifici e verificabili, come la capacità di applicare conoscenze per 'acquisire, editare, comprimere e salvare immagini segnali video'. Tuttavia, altri son
  - human:  
- **C3** on `89E21813` (COMPUTER VISION) — system=1 vs human=2  (delta 1)
  - system: I risultati di apprendimento attesi sono formulati in termini di ciò che lo studente acquisirà o sarà in grado di fare, il che è coerente con le linee guida. Tuttavia, la specificità e la verificabilità variano tra i diversi descrittori. Me
  - human:
