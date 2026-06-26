# Risultati — Perturbation / Sensitivity Test

Base `3540D939-DA16-4C1D-983C-E6B85C403F2F`, N=3 run/condizione. Varianti che superano (PASS robusto sul bersaglio primario): 5/7.

| Variante | Bersaglio | Base | Perturbato | Delta | Atteso | Verdict | Side effects |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| C1_remove_sections | C1 | 2.0 | 1.0 | -1.00 | decrease | PASS | C8(-1.0,expe) |
| C2_strip_english | C2 | 2.0 | 0.0 | -2.00 | decrease | PASS | — |
| C3C4_generic_outcomes | C3 | 2.0 | 0.6667 | -1.33 | decrease | PASS | C8(-1.0,expe) |
| C3C4_generic_outcomes | C4 | 2.0 | 0.0 | -2.00 | decrease | PASS | C8(-1.0,expe) |
| C5_blank_prerequisites | C5 | 2.0 | 0.0 | -2.00 | decrease | PASS | C1(-0.7,expe) |
| C6_strip_assessment | C6 | 2.0 | 0.0 | -2.00 | decrease | PASS | C1(-1.0,expe), C8(-1.0,expe), C9(+0.7,spur) |
| C7_remove_schedule | C7 | 2.0 | 2.0 | +0.00 | decrease | FAIL | C1(-1.0,expe) |
| C9_editorial_noise | C9 | 1.0 | 1.0 | +0.00 | decrease | FAIL | — |

Legenda verdict: PASS = sensibilità robusta (oltre il rumore della base); WEAK = direzione corretta ma entro il rumore; FAIL = nessun calo significativo.

## Esiti per classe

- **PASS robusti:** C1_remove_sections/C1, C2_strip_english/C2, C3C4_generic_outcomes/C3, C3C4_generic_outcomes/C4, C5_blank_prerequisites/C5, C6_strip_assessment/C6.
- **WEAK:** nessuno.
- **FAIL:** C7_remove_schedule/C7, C9_editorial_noise/C9.
- **Bersagli diventati NA:** nessuno.
- **Dati base insufficienti:** nessuno.
