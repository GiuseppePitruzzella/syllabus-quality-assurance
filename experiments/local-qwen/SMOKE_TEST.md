# Test minimo Mac → Ollama, senza valutare syllabus

Il test esegue **una sola generazione**: chiede quanto fa 2 + 2 e controlla
una risposta JSON. Non importa l'applicazione, non legge syllabus, non avvia
database, RAG, agenti o servizi Google. Sul ThinkPad servono soltanto Ollama
avviato e `qwen3.5:4b` Q4_K_M già scaricato.

## Dal Mac

Il ThinkPad deve essere raggiungibile sulla rete autorizzata. Con Ollama in
ascolto sull'IP del ThinkPad e sulla porta 11434, esegui dalla cartella
`backend` del repository sul Mac, sostituendo l'IP di esempio:

```sh
.venv/bin/python scripts/smoke_ollama.py --host 192.168.1.50
```

Non serve SSH. Il test usa l'ambiente Python già presente sul Mac; non installa
nulla sul ThinkPad, non cambia il firewall e non scarica modelli.
Accetta solo IPv4 letterali privati, link-local o loopback; ignora i proxy
d'ambiente e rifiuta i redirect. Le restrizioni del benchmark syllabus restano
invariate: questo è un controllo indipendente, non la sua integrazione LAN.

Se Ollama è ancora in ascolto solo su `127.0.0.1`, sul ThinkPad chiudi l'app
dall'area di notifica e avvia in una PowerShell dedicata (IP da sostituire):

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
2. Verifica che siano presenti i pesi locali Qwen3.5-4B Q4_K_M; rifiuta alias cloud.
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
puoi usare `ollama stop qwen3.5:4b` sul ThinkPad, indicando nella stessa finestra
PowerShell `OLLAMA_HOST` uguale all'indirizzo del server. Il test rilascia solo
il modello richiesto; evitare di lanciarlo mentre un altro lavoro usa quel modello.

Un esito positivo verifica collegamento e generazione, **non** qualità dei
giudizi, velocità con prompt lunghi o impatto durante una giornata di lavoro.
Non vengono creati risultati fittizi in caso di errore e il costo API è zero.
Il server resta attivo finché non chiudi la finestra o premi `Ctrl+C`.

Riferimenti: [API chat](https://docs.ollama.com/api/chat),
[rilascio del modello e configurazione server](https://docs.ollama.com/faq),
[modelli caricati](https://docs.ollama.com/api/ps).
