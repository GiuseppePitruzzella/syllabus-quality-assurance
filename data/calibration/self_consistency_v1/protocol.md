# Protocollo — Esperimento test-retest / self-consistency

- Data esecuzione: 2026-06-22T07:40:35.208674+00:00
- Git commit: `416036149774519287ba8055423b8a71db4bc994` (branch `feature/self-consistency-experiment`, dirty: sì)
- Esperimento: self_consistency_v1
- Ripetizioni per syllabus (N): 5

## Configurazione scientifica (di produzione)

- Modello LLM: gemini-2.5-flash
- Temperatura LLM: 0.1
- Max output tokens: 8192
- Modello embedding: gemini-embedding-001 (dim 3072)
- RAG top_k/final_k/soglia: 5/3/0.6
- Versioni prompt:
  - A1: a1_v6
  - A2: a2_v1
  - A3: a3_v1
  - A4: a4_v10
  - A5: a5_v1

## Campione

- `88B7C1CE-B595-46A5-A37A-C5414AD807B5` — 01_COMPUTER_VISION_LAB
- `0B53E8E2-4B90-426F-A25C-3AA31FA4B649` — 02_INTERNET_OF_THINGS
- `F4AF1512-9D7A-4256-B57D-E103E05B009B` — 03_PEER_TO_PEER_LAB
- `9A90BBCE-99E3-4FB0-BF91-CCAAA5C51791` — 04_MULTIMEDIA_LAB
- `89E21813-A17C-4C85-AF65-C295EE11ED59` — 05_COMPUTER_VISION
- `E2446DF6-59A1-46FD-B8D8-635EB937C1B3` — 06_OTTIMIZZAZIONE
- `3540D939-DA16-4C1D-983C-E6B85C403F2F` — 07_DEEP_LEARNING
- `46D62804-0FCD-4478-A51D-A752B64A7DCB` — 08_VULN_ASSESSMENT_PT

## Fonte di non-determinismo

Le run sono eseguite a parità di input e configurazione. La variabilità run-to-run deriva dalla stocasticità del modello generativo (gemini-2.5-flash) alla temperatura di produzione (0.1) e dal *thinking* abilitato di default in Gemini 2.5 Flash.

## Metriche

Il grafo è eseguito **come in produzione** (inclusa la sintesi del report testuale), ma le metriche di self-consistency usano **solo** campi strutturati: punteggi C1–C9, stato NA, CoreScore, coverage, status e agent_errors. Il **testo** del report/justification non entra in alcuna metrica.

Definizioni (per coppia syllabus×criterio, su N run):

- **accordo modale** = conteggio(moda) / N, con NA come categoria distinta;
- **unanime** = tutte le N run uguali e non-NA;
- **range** e **deviazione standard** (di popolazione) sui soli valori numerici;
- **NA-flip** = criterio NA in alcune run e valutato in altre.

Aggregati per criterio: tasso di unanimità, stdev media intra-item, flip rate = media di (1 − accordo modale), swing massimo, incidenza NA-flip. CoreScore: stdev e range per syllabus, più stdev media e swing massimo aggregati.

