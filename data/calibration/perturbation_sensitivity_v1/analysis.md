# Analisi — Perturbation / Sensitivity Test

## Risultato complessivo

Il sistema mostra sensibilità direzionale robusta su **6/8 giudizi bersaglio** (**5/7 varianti**). Il risultato sostiene la validità di costrutto per C1, C2, C3, C4, C5 e C6, entro i limiti di un singolo syllabus base e di tre repliche per condizione.

## Lettura dei due FAIL

- **C7_remove_schedule — FAIL informativo, non errore automatico.** La rimozione delle 16 righe della programmazione non abbassa C7 perché il campo dei contenuti conserva una narrazione articolata e una progressione riconoscibile. L'esito è coerente con l'anchor corrente, che ammette una struttura narrativa in alternativa alla schedule. Il test mostra quindi che la sola programmazione non è condizione necessaria per C7=2; non dimostra insensibilità alla qualità dei contenuti in generale.
- **C9_editorial_noise — limite di sensibilità.** Nonostante refusi ripetuti, marker `[TODO]`, caratteri sostitutivi e formattazione sporca in più campi, C9 resta a 1. Il criterio distingue il documento curato dal documento migliorabile, ma in questa prova non discrimina il confine 1→0. Il risultato va riportato come limite dell'operazionalizzazione di C9, non corretto retroattivamente modificando la perturbazione.

## Effetti collaterali

- Le variazioni C3/C4→C8, C6→C1/C8 e C7→C1 sono coupling attesi: risultati di apprendimento, verifica e programmazione partecipano anche a completezza e coerenza interna.
- L'aumento di C9 dopo la perturbazione C6 è spurio e conferma che C9 resta il criterio più interpretativo. Non altera il verdetto sul bersaglio C6.
- C3 varia tra 0 e 1 nella condizione perturbata, ma il calo medio rispetto alla base stabile resta ampio e supera la noise floor.

## Integrità della campagna

- Tutti i bersagli hanno prodotto score numerici sufficienti; nessun esito è stato classificato come NA o dato insufficiente.
- Le metriche derivano esclusivamente dai campi strutturati C1-C9; nessun report testuale è stato usato per calcolare i verdetti.
- I risultati descrivono sensibilità direzionale sul caso Deep Learning e non sono automaticamente generalizzabili a tutti i syllabus LM-18.
