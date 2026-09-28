# Test minimo Mac → Ollama, senza valutare syllabus

Il test prepara **una sola generazione**: chiede quanto fa 2 + 2 e controlla
una risposta JSON. Per impostazione predefinita mostra soltanto un'anteprima
offline: non invia richieste. Non importa l'applicazione, non legge syllabus,
non avvia database, RAG, agenti o servizi Google. Sul ThinkPad è installato
`qwen3.5:9b`: gli esempi selezionano esplicitamente questo modello. Rimane
disponibile anche `--model qwen3.5:4b` (default storico), senza sostituzioni
automatiche o download. Il controllo dei pesi richiede Q4_K_M per entrambi.

## Supervisione del ThinkPad

Ogni operazione sul computer aziendale e ogni invio di dati verso di esso
richiedono la supervisione e l'approvazione esplicita dell'utente per il
passaggio proposto. Vale anche per leggere versione, elenco modelli e stato
della memoria; conoscere l'IP non autorizza a contattarlo. Le modifiche alla
configurazione Windows e l'esecuzione del test non sono automatiche.

È possibile preparare codice e anteprima sul Mac senza accedere al ThinkPad.
L'utente esamina destinazione, modello, prompt e richieste previste, quindi
esegue personalmente il test o autorizza esplicitamente quell'esecuzione.
La verifica automatica dello script usa risposte simulate, non il ThinkPad.

## Dal Mac

Dalla cartella `backend` del repository sul Mac, prepara l'anteprima,
sostituendo l'IP di esempio. Questo comando **non apre collegamenti**:

```sh
.venv/bin/python scripts/smoke_ollama.py --host 192.168.1.50 --model qwen3.5:9b
```

L'anteprima mostra le cinque richieste in ordine, incluso il testo completo
inviato al modello. Dopo averle esaminate e approvate, l'utente può avviare
quel singolo test aggiungendo `--execute` allo stesso comando. Da quel momento
Ollama deve essere raggiungibile sull'IP indicato e avere il modello scaricato.
**Senza `--execute` non viene verificata neppure la raggiungibilità del server.**

Non serve SSH. Il test usa l'ambiente Python già presente sul Mac; non installa
nulla sul ThinkPad, non cambia il firewall e non scarica modelli.
Accetta solo IPv4 letterali privati, link-local o loopback; ignora i proxy
d'ambiente e rifiuta i redirect. Le restrizioni del benchmark syllabus restano
invariate: questo è un controllo indipendente, non la sua integrazione LAN.

La seguente configurazione è un passaggio separato da esaminare con l'utente;
non va applicata automaticamente. Se Ollama è ancora in ascolto solo su
`127.0.0.1`, l'utente può chiudere l'app dall'area di notifica e avviarla in
una PowerShell dedicata (IP da sostituire):

```powershell
$env:OLLAMA_HOST = "192.168.1.50:11434"
$env:OLLAMA_NO_CLOUD = "1"
$env:OLLAMA_NUM_PARALLEL = "1"
ollama serve
```

Queste impostazioni valgono solo per la sessione. Per accedere dal Mac, il
firewall deve consentire la porta TCP 11434 dal suo indirizzo secondo le regole
aziendali. L'API HTTP non è cifrata e non richiede autenticazione: usare il
collegamento privato autorizzato. Per questa domanda sintetica non viene inviato
alcun documento. Se il server non è raggiungibile, il test termina con errore.

## Cosa fa e come leggere l'esito

1. Legge versione e modelli disponibili senza caricarli in RAM.
2. Verifica che siano presenti i pesi locali Q4_K_M del modello selezionato;
   rifiuta alias cloud e non usa un altro modello se quello scelto manca.
3. Invia una domanda, con contesto 2.048 token, output massimo 32 token,
   thinking disabilitato e due thread CPU richiesti. Non è un limite percentuale
   all'utilizzo della CPU e il modello deve comunque essere caricato in memoria.
4. Richiede il rilascio del modello con `keep_alive: 0` e legge `/api/ps` una volta.

`passed: true` indica una risposta completa e corretta (`{"risposta": 4}`).
`wall_seconds` comprende comunicazione, caricamento e generazione;
`load_seconds` riporta il caricamento comunicato da Ollama.
`model_still_loaded: false` conferma che il modello non compare nella lettura
successiva; `true` significa che risulta ancora caricato in quel momento;
`null` indica che non è stato possibile verificarlo. Non è una misura del picco RAM.

Il timeout predefinito è 120 secondi, modificabile con `--timeout 300`. Non ci
sono retry o fallback. Dopo un'interruzione o se il modello resta caricato,
puoi usare `ollama stop qwen3.5:9b` sul ThinkPad (o il nome del modello scelto),
indicando nella stessa finestra
PowerShell `OLLAMA_HOST` uguale all'indirizzo del server. Il test rilascia solo
il modello richiesto; evitare di lanciarlo mentre un altro lavoro usa quel modello.

Un esito positivo verifica collegamento e generazione, **non** qualità dei
giudizi, velocità con prompt lunghi o impatto durante una giornata di lavoro.
Non vengono creati risultati fittizi in caso di errore e il costo API è zero.
Il server resta attivo finché non chiudi la finestra o premi `Ctrl+C`.

Riferimenti: [API chat](https://docs.ollama.com/api/chat),
[rilascio del modello e configurazione server](https://docs.ollama.com/faq),
[modelli caricati](https://docs.ollama.com/api/ps),
[Qwen3.5:9b nel catalogo Ollama](https://ollama.com/library/qwen3.5:9b).
