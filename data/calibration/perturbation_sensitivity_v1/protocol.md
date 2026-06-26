# Protocollo — Perturbation / Sensitivity Test

- Data esecuzione: 2026-06-26T21:17:10.678965+00:00
- Git commit: `46ef8f1078c88961fd4b704c7406f3df5fab73b7` (branch `feature/perturbation-sensitivity-test`, dirty: sì)
- Esperimento: perturbation_sensitivity_v1
- Syllabus base (seuid): `3540D939-DA16-4C1D-983C-E6B85C403F2F`
- Run per condizione (N): 3 (1 base + 7 varianti = 24 run totali)

## Scopo

Questo test dimostra la **validità di costrutto / sensibilità direzionale** del sistema: a fronte di una perturbazione controllata che degrada un singolo aspetto, il criterio bersaglio deve peggiorare. **Non** misura accordo umano e **non** sostituisce Phase 5.8; complementa la self-consistency (di cui riusa il rumore run-to-run come noise floor).

## Configurazione scientifica (di produzione)

- Modello LLM: gemini-2.5-flash (temperatura 0.1)
- Embedding: gemini-embedding-001 (dim 3072)
- RAG top_k/final_k/soglia: 5/3/0.6
- Versioni prompt: {'A1': 'a1_v7', 'A2': 'a2_v1', 'A3': 'a3_v1', 'A4': 'a4_v10', 'A5': 'a5_v1'}

## Perturbazioni

- **C1_remove_sections** → bersaglio C1; coupling plausibile: C7, C8, C9; Svuota 3 sezioni obbligatorie (metodi didattici, frequenza, riferimenti).
- **C2_strip_english** → bersaglio C2; coupling plausibile: C1; Svuota i campi EN rilevanti (titolo, risultati, descrittori, contenuti, verifica).
- **C3C4_generic_outcomes** → bersaglio C3, C4; coupling plausibile: C8; Rende i risultati di apprendimento generici, corso-centrici e ripetitivi.
- **C5_blank_prerequisites** → bersaglio C5; coupling plausibile: C1; Sostituisce i prerequisiti con 'Prerequisiti non indicati'.
- **C6_strip_assessment** → bersaglio C6; coupling plausibile: C1, C8; Rimuove griglia/fasce/criteri/pesi/esempi dalla verifica.
- **C7_remove_schedule** → bersaglio C7; coupling plausibile: C1, C8; Rimuove la programmazione del corso (schedule); appiattisce eventuali contenuti strutturati.
- **C9_editorial_noise** → bersaglio C9; coupling plausibile: —; Inietta refusi, marker tecnici e formattazione sporca nei campi IT.

## Definizione del verdetto

Per il criterio bersaglio: `delta = media(variante) − media(base)`; `noise_floor = range delle 3 run base`. **PASS** = direzione corretta, `|delta| ≥ 0.5` e `|delta| > noise_floor`; **WEAK** = direzione corretta e `|delta| ≥ 0.5` ma entro il rumore della base; **FAIL** = direzione sbagliata o `|delta| < 0.5`. NA non è 0: `TARGET_BECAME_NA` e `insufficient_base_data` sono esiti distinti.

## Note metodologiche (refinement)

- **C1**: rimuovere sezioni obbligatorie non è mai isolato → coupling plausibile dichiarato con C7/C8/C9.
- **C2**: oggi guidato dal pre-check deterministico `english_coverage`; atteso comportamento molto stabile (un calo netto conferma la correzione C2).
- **C5**: perturbazione chiaramente negativa ('Prerequisiti non indicati'), non 'Nessun prerequisito' (interpretabile come informazione legittima).

## Caveat

- N piccolo (3/condizione); perturbazioni sintetiche; singola base (LM-18 Deep Learning) → generalizzabilità limitata.
- Headroom limitata per C9 (baseline 1, delta minimo osservabile -1).
