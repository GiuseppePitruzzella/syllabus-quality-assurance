# Controllo della rubrica separata — 15 settembre 2026

La [revisione delle fonti](RUBRIC_REVIEW.md) è implementata come esperimento
locale selezionabile. **Non autorizza una sostituzione del valutatore in
produzione.** L'obiettivo è rendere esplicita e verificabile la valutazione,
misurando anche i limiti di un modello piccolo.

## Metodo

- MacBook Air M2, 8 GB; Ollama 0.32.15; Qwen3.5-4B Q4_K_M, stesso digest del
  [primo pilot](RESULTS.md).
- Quattro agenti sul solo syllabus Internet of Things, già esaminato durante
  la costruzione della rubrica. Nessun campione indipendente o giudizio esperto.
- Temperatura 0.1, seed 42, contesto 16.384, massimo 2.048 token di risposta,
  thinking disabilitato, nessun taglio dell'input e nessun tentativo di riparazione.
- Syllabus e contesto RAG conservati identici byte per byte. Cambiano istruzioni
  e alcune regole: il confronto con Gemini storico è soltanto descrittivo.
- Due fasi salvate separatamente: schema storico permissivo, poi schema con
  tutti i campi obbligatori. La rubrica e il testo dei nuovi prompt non cambiano
  tra queste due fasi. Il processo Ollama resta attivo tra le fasi.
- Chiamate esclusivamente locali; **costo API $0**. Tempi osservati durante
  lo sviluppo, con cache e carico del Mac variabili: non un benchmark di velocità
  controllato. Nessun nuovo test Gemini o servizio di embedding remoto.

## Prima fase: limite del contratto di risposta

| Agente | Tempo | Esito |
|---|---:|---|
| A1 | 152,474 s | Scartato: omessi i punteggi di C1, C2 e C5 |
| A2 | 84,369 s | Scartato: omessi i punteggi di C3 e C4 |
| A3 | 198,387 s | Scartato: omessi i punteggi di C6, C7 e C8 |
| A4 | 54,630 s | Struttura valida, C9=0; motivazione non conforme alla rubrica |

Gli oggetti Pydantic ammettono valori predefiniti, rendendo opzionali alcuni
campi nello schema JSON di generazione. Il modello ha sfruttato questa libertà
omettendo la decisione di punteggio. Per `separated_v1` lo schema ora richiede
tutti i campi; `archived` conserva il contratto precedente. La verifica
successiva continua a scartare decisioni non valide, senza assegnare punteggi
automatici in base alle sole motivazioni.

Il giudizio A4 della prima fase mostra un limite diverso: sostiene che manchino
i riferimenti mentre cita il campo contenente materiali e repository; pretende
dettagli bibliografici esclusi dalla rubrica; assegna 0 senza descrivere almeno
tre difetti gravi in due campi. Le sue due citazioni sono letterali, ma non
sostengono quel punteggio. **Citazioni verificate e JSON valido non equivalgono
a una valutazione corretta.**

## Seconda fase e confronto

| Agente | Tempo | Risposte complete | Citazioni letterali verificate |
|---|---:|---|---:|
| A1 | 54,093 s | Sì | 1/13 |
| A2 | 69,777 s | Sì | 11/11 |
| A3 | 90,612 s | Sì | 4/6 |
| A4 | 24,999 s | Sì | 2/2 |

**4/4 risposte strutturalmente valide**, 18/32 citazioni verificate (56,25%),
nessun NA e nessuna lista di evidenze vuota. Il precedente pilot sullo **stesso
syllabus IoT** aveva 4/4 risposte valide e 20/31 citazioni verificate (64,52%).
Il totale 22/34 del vecchio report comprendeva anche Deep Learning: non è il
denominatore da usare per questo confronto.

| Criterio | Gemini storico | Qwen, prompt storico | Qwen, `separated_v1` |
|---|---:|---:|---:|
| C1 | 2 | 1 | 2 |
| C2 | 0 | 0 | 0 |
| C3 | 1 | 1 | 2 |
| C4 | 2 | 1 | 2 |
| C5 | 1 | 1 | 1 |
| C6 | 2 | 1 | 2 |
| C7 | 2 | 1 | 2 |
| C8 | 2 | 2 | 1 |
| C9 | 1 | 1 | 2 |

L'accordo con Gemini passa da **5/9 a 6/9**; la differenza assoluta media passa
da 0,444 a 0,333. Le quattro divergenze originarie (C1, C4, C6 e C7) scompaiono,
ma ne emergono tre (C3, C8 e C9). Poiché le regole sono cambiate, queste sono
differenze descrittive, non etichette automatiche di errore o correttezza.

La lettura delle risposte mostra che:

- **C1** riconosce tutte le sezioni, ma le nove presunte citazioni sono nomi di
  campi, non estratti del loro contenuto. In **C2** tre stringhe rappresentanti
  valori vuoti vengono usate come citazioni, invece di lasciare la lista vuota.
- **C3** assegna 2 considerando specifici tutti i risultati: il cambiamento da 1
  richiede un controllo umano, specialmente per distinguere attività descritte e
  risultati realmente formulati come competenze dello studente.
- **C4** distingue le capacità pur riconoscendo attività comuni. Le citazioni A2
  sono tutte verificabili; questo non dimostra da solo la validità del punteggio.
- **C5** mantiene 1 ma richiama ancora la mancanza della graduazione
  utile/importante/indispensabile, benché la rubrica ne escluda l'obbligatorietà.
- **C6** riconosce prove, accesso sequenziale e criteri. Nella motivazione parla
  anche di prove in itinere, mentre il testo citato documenta soprattutto la
  sequenza delle prove finali: resta da evitare questa estensione terminologica.
- **C7** riconosce l'organizzazione senza pretendere ore; i due estratti falliscono
  però il controllo letterale. Non vanno presentati come citazioni fedeli.
- **C8** assegna 1 per un collegamento ritenuto non esplicito, pur citando una
  relazione tra apprendimento ed esercitazioni. La motivazione non identifica
  chiaramente il collegamento concreto mancante e può contraddire le esclusioni
  della rubrica. È un caso prioritario per revisione umana.
- **C9** passa a 2 con una motivazione generale e due frammenti leggibili: ciò non
  equivale a un'ispezione esaustiva dei difetti. Tra le due fasi, a prompt uguale
  e contratto diverso, è passato da 0 a 2: ulteriore motivo per non promuoverlo.

Complessivamente questa sessione comprende **8 tentativi, 5 strutturalmente
validi e 3 scartati**. I tentativi iniziali non sono stati eliminati o corretti
a posteriori. I conteggi delle citazioni riguardano le risposte valide; i fallimenti
restano nel denominatore di affidabilità strutturale.

I circa 4 minuti della seconda fase non dimostrano un'accelerazione dovuta ai
prompt: il modello era già caricato, i prompt erano già stati elaborati nella
prima fase e il riuso della cache non è stato controllato. La macchina era usata
anche per lo sviluppo. Le istantanee di allocazione e swap sono nei dati, non
sono misure di RAM di picco. Modello e server temporaneo sono stati arrestati.

## Decisione e verifica

Si conservano **il catalogo sperimentale, la selezione della politica, il contratto
esplicito e il resoconto riproducibile**. Questi rendono verificabili gli esperimenti
senza perdere anchor o nascondere fallimenti. **Non si promuovono la nuova rubrica
o Qwen a valutatore dell'applicazione:** le evidenze non dimostrano un miglioramento
complessivo della qualità delle valutazioni.

Il [registro riassuntivo](separated-2026-09-15.json) contiene entrambe le fasi,
impronte di input/output, configurazione, punteggi, tempi e conteggi. Prompt e
risposte integrali rimangono nei dati locali ignorati da Git. I manifest fanno
riferimento al commit precedente perché il codice era in sviluppo; le impronte
del codice identificano le implementazioni effettivamente eseguite. La prima
fase precede il vincolo sui campi obbligatori, la seconda lo include.

Verifica del codice: **53 nuovi test superati**; suite backend completa
**1.168 superati, 3 falliti**. I tre fallimenti sono gli stessi già presenti
prima della modifica: l'inventario del corpus conta anche il README come ottavo
documento. Nessun nuovo fallimento; i test preesistenti non sono stati soppressi.
Ruff sui file Python modificati e controllo degli spazi nel diff superati.
Questi controlli non sostituiscono una validazione dei giudizi con valutatori umani.
