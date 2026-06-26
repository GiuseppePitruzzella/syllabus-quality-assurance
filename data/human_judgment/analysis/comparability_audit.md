# Audit di comparabilità — Phase 5.8

Il confronto usa il questionario blind ricevuto dal valutatore e le valutazioni storiche `validation_lm18`, generate con A1 `a1_v5`, A2 `a2_v1`, A3 `a3_v1` e A4 `a4_v2`.

| Criterio | Stato | Livello analisi | Motivazione |
| --- | --- | --- | --- |
| C1 | Comparabile | primary | Perimetro e soglie sono sostanzialmente equivalenti. |
| C2 | Parzialmente comparabile | secondary | Il questionario aggiunge un requisito di coerenza IT/EN che A1 a1_v5 non valutava; le soglie sulla copertura sono inoltre formulate in modo leggermente diverso. |
| C3 | Comparabile | primary | Le formulazioni differiscono, ma operazionalizzano lo stesso costrutto di qualità formulativa degli outcome. |
| C4 | Comparabile | primary | Costrutto e anchor sono sostanzialmente equivalenti. |
| C5 | Comparabile | primary | Il confronto storico è valido perché validation_lm18 usava a1_v5. La rubrica corrente a1_v7 è stata successivamente ridefinita e non va usata retroattivamente. |
| C6 | Non comparabile | excluded | I due lati misurano costrutti differenti. Un accordo numerico sarebbe accidentale e non interpretabile. |
| C7 | Parzialmente comparabile | secondary | Entrambi valutano la comprensibilità dei contenuti, ma il questionario premia esplicitamente macro-blocchi e può confliggere con le istruzioni locali favorevoli alla forma discorsiva. |
| C8 | Parzialmente comparabile | secondary | Il giudizio umano copre un sottoinsieme del costrutto usato dal sistema; l'accordo resta informativo ma non pienamente equivalente. |
| C9 | Parzialmente comparabile | secondary | Il costrutto è lo stesso, ma le fonti osservate non sono equivalenti: parser e portale possono introdurre marker o interruzioni non visibili al valutatore. |

## Perimetro delle metriche

- **Primario:** C1, C3, C4, C5.
- **Secondario/esplorativo:** C2, C7, C8, C9.
- **Escluso dalle metriche di accordo:** C6.

C6 è escluso perché il questionario umano misura il mapping RA-contenuti, mentre il sistema misura la trasparenza della valutazione. C5 resta comparabile nel confronto storico perché sia il questionario sia A1 `a1_v5` usavano la tassonomia culturali/disciplinari; la successiva ridefinizione `a1_v7` sarà trattata soltanto come analisi controfattuale.
