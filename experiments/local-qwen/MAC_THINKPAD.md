# Progetto sul Mac, Ollama sul ThinkPad

Per verificare soltanto collegamento e una breve risposta, usa prima il
[test minimo senza SSH e senza syllabus](SMOKE_TEST.md). La procedura sotto
riguarda invece il benchmark completo tramite tunnel.

Questa configurazione lascia repository, dipendenze, preparazione dei prompt,
confronti e risultati sul Mac. Il ThinkPad esegue soltanto Ollama e il modello
Qwen3.5-4B Q4_K_M. Non occorrono Python, Node, Docker, WSL o una copia del
progetto sul ThinkPad.

| MacBook | ThinkPad Windows 11 |
|---|---|
| Repository e ambiente Python già esistente | Ollama nativo e pesi del modello |
| Preparazione e validazione del benchmark | Generazione delle risposte |
| Salvataggio dei risultati e confronti | RAM e processore usati dal modello |
| Client SSH | Servizio SSH autorizzato e configurato per il port forwarding |

Il collegamento è un tunnel SSH: `Mac 127.0.0.1:11436` inoltra le richieste a
`ThinkPad 127.0.0.1:11434`. Ollama resta in ascolto sul solo ThinkPad; la porta
11434 non deve essere esposta sulla rete. Il benchmark accetta già un indirizzo
loopback con porta personalizzata.

**Ambito attuale:** questi passaggi abilitano il benchmark sperimentale. Non
configurano l'applicazione web per usare Qwen: la sua integrazione con i servizi
Google è ancora separata. Per i test gratuiti usare lo script indicato qui,
non gli script storici di calibrazione con Gemini.

## 1. Verificare il collegamento SSH

Ollama è già consentito sul ThinkPad. Il tunnel richiede anche un servizio
OpenSSH Server disponibile, accessibile dal Mac e autorizzato dall'azienda.
L'installazione standard del server su Windows richiede privilegi di
amministratore; il solo client SSH non basta.

In PowerShell, questo controllo legge lo stato senza cambiare impostazioni:

```powershell
Get-Service sshd -ErrorAction SilentlyContinue | Select-Object Name, Status
```

`Running` indica che il servizio è avviato, ma non dimostra che l'accesso dal
Mac e il port forwarding siano consentiti. Se il servizio manca, è fermo o
l'accesso è bloccato, serve la configurazione approvata dall'IT. Non è necessario
installare dipendenze del progetto per risolvere questo passaggio.

Occorrono l'indirizzo IP del ThinkPad sul collegamento scelto e un utente SSH
abilitato. Non inserire password, chiavi private o indirizzi aziendali nel
repository. I segnaposto nei comandi seguenti vanno sostituiti localmente.

Per vedere gli indirizzi delle interfacce Windows:

```powershell
Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias, IPAddress
```

Puoi usare Wi-Fi o Ethernet se il collegamento tra i dispositivi è consentito.
Un cavo Thunderbolt/USB4 può fornire lo stesso collegamento IP, se entrambe le
porte e il cavo supportano la rete tra computer. Sul Mac si usa Thunderbolt
Bridge; su Windows 11 l'interfaccia USB4/Thunderbolt. Per usare davvero il cavo,
scegli l'IP di quell'interfaccia, non quello Wi-Fi. Il modello esatto del
ThinkPad e il funzionamento di questa rete devono ancora essere verificati.
Non serve attivare la condivisione Internet.

## 2. Avviare Ollama sul ThinkPad

Usare l'installazione nativa di Ollama già autorizzata. Il nostro benchmark
richiede un **server Ollama 0.32.15 o successivo** per rifiutare input troncati.
Se l'aggiornamento è gestito dall'azienda, usare la versione approvata.

Chiudi l'app Ollama dall'icona nell'area di notifica prima di avviare questa
istanza manuale, per evitare due server sulla stessa porta. In una finestra
PowerShell dedicata:

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11434"
$env:OLLAMA_NO_CLOUD = "1"
$env:OLLAMA_NUM_PARALLEL = "1"
$env:OLLAMA_MAX_LOADED_MODELS = "1"
ollama serve
```

Lascia aperta la finestra. Le variabili valgono per questa sessione e i suoi
processi: non modificano le configurazioni Python/Node o le variabili permanenti
di Windows. Nei log del server deve comparire `Ollama cloud disabled: true`.
Si elaborerà una richiesta alla volta; il benchmark imposta un contesto di
16.384 token per richiesta.

In una seconda finestra PowerShell:

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11434"
Invoke-RestMethod http://127.0.0.1:11434/api/version
ollama list
```

Se `qwen3.5:4b` non è presente, scaricalo una volta:

```powershell
ollama pull qwen3.5:4b
```

I pesi restano sul ThinkPad. Il benchmark verifica nome, famiglia e
quantizzazione Q4_K_M, registrando il digest effettivo. Non scarica modelli
automaticamente e non passa al cloud se qualcosa fallisce. Ollama e questo
modello non richiedono abbonamenti o chiamate API a pagamento; dopo il download
la generazione non richiede Internet. Restano l'uso di elettricità, spazio e
risorse del computer.

## 3. Aprire il tunnel dal Mac

Nel Terminale del Mac, sostituire `UTENTE_WINDOWS` e `IP_THINKPAD`:

```sh
ssh -N \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -L 127.0.0.1:11436:127.0.0.1:11434 \
  -l "UTENTE_WINDOWS" "IP_THINKPAD"
```

Usa il metodo di autenticazione autorizzato. Al primo accesso verifica
l'impronta della chiave del server; non disabilitare il controllo della chiave.
Il comando rimane attivo senza aprire una shell Windows: lascia aperta questa
finestra. La porta 11436 sul Mac è distinta dalla 11435 usata nei precedenti
esperimenti sul Mac.

In un altro Terminale del Mac, verifica che risponda il server Windows:

```sh
curl --noproxy '*' --fail --show-error --max-time 10 \
  http://127.0.0.1:11436/api/version
curl --noproxy '*' --fail --show-error --max-time 10 \
  http://127.0.0.1:11436/api/tags
```

Queste richieste leggono versione ed elenco dei modelli, senza generare testo.
`ExitOnForwardFailure` controlla l'apertura del tunnel; solo la verifica API
conferma che Ollama sia raggiungibile. Non occorre avviare Ollama sul Mac.

## 4. Eseguire il benchmark sul Mac

Apri la cartella `backend` del repository sul Mac. I comandi usano direttamente
l'ambiente `.venv` già presente, senza installare o aggiornare pacchetti:

```sh
.venv/bin/python scripts/benchmark_local_qwen.py \
  --base-url http://127.0.0.1:11436 \
  --inference-location ssh-tunnel \
  --prompt-policy current_v1 --evidence-mode source_ids_v2 \
  --agent A1 --seuid 0B53E8E2-4B90-426F-A25C-3AA31FA4B649
```

Questo primo comando prepara il test senza contattare Ollama. Per eseguire
una valutazione A1 sul syllabus Internet of Things:

```sh
.venv/bin/python scripts/benchmark_local_qwen.py --execute \
  --base-url http://127.0.0.1:11436 \
  --inference-location ssh-tunnel \
  --prompt-policy current_v1 --evidence-mode source_ids_v2 \
  --agent A1 --seuid 0B53E8E2-4B90-426F-A25C-3AA31FA4B649 \
  --timeout 1800
```

Il limite di 1.800 secondi lascia tempo al primo caricamento e alla generazione
su CPU: non è una previsione della durata. Non ridurre il contesto o tagliare
il prompt per far apparire il test più veloce.

Dopo aver verificato il primo risultato, per eseguire i quattro agenti sullo
stesso syllabus rimuovi `--agent A1`. Per ripetere ciascun caso tre volte
aggiungi `--runs 3`. L'elaborazione resta sequenziale.

I risultati sono salvati **sul Mac**, in una nuova cartella
`data/local_benchmarks/`, esclusa da Git. Ogni tentativo, anche fallito, conserva
risposta grezza e diagnostica; `summary.md` e `summary.json` contengono il
riepilogo. Nessun risultato precedente viene sovrascritto. Il ThinkPad riceve
il testo del prompt necessario all'inferenza, non una copia del repository.

## 5. Leggere correttamente il confronto

L'opzione `--inference-location ssh-tunnel` annota la configurazione dichiarata;
non crea il tunnel e non rileva automaticamente l'hardware. Il manifest
specifica la provenienza delle misure:

| Dato | Computer o ambito |
|---|---|
| `platform`, `machine`, `swap_before`, `swap_after` | Mac che esegue il benchmark |
| `runtime`, `model_memory_after` | Server Ollama sul ThinkPad |
| `wall_seconds` | Tempo osservato dal Mac, inclusa la comunicazione |
| Durate e token restituiti da Ollama | Elaborazione del modello sul server |

L'allocazione restituita da Ollama non misura la RAM totale o il picco di RAM
del ThinkPad. Lo swap del Mac non descrive la memoria usata dal ThinkPad.
Per osservare quest'ultima puoi usare Gestione attività su Windows; `ollama ps`
mostra anche come Ollama ha ripartito il modello tra CPU e GPU.

Per confrontare Mac e ThinkPad, usare lo stesso commit, gli stessi prompt,
criteri, digest del modello, versione di Ollama, contesto e limiti di output.
Distinguere il primo caricamento dalle esecuzioni con modello già caricato.
La RAM maggiore non garantisce maggiore velocità. Un esito JSON valido non
dimostra che il punteggio sia corretto; rimane necessaria la revisione umana.

## Arresto e problemi comuni

Al termine, nel secondo PowerShell del ThinkPad:

```powershell
ollama stop qwen3.5:4b
```

Poi `Ctrl+C` nella finestra del server Ollama e in quella del tunnel sul Mac.
Il modello resta su disco per il prossimo test; non è necessario disinstallarlo.

| Problema | Controllo |
|---|---|
| SSH non raggiungibile | IP dell'interfaccia corretta, servizio SSH e regole aziendali; il tunnel non abilita da solo il servizio |
| SSH risponde ma il forwarding è rifiutato | Verificare con l'IT che il port forwarding verso `127.0.0.1:11434` sia consentito |
| Porta 11436 sul Mac già occupata | Usare una porta libera sia in `-L` sia in `--base-url`; non terminare processi sconosciuti |
| API non raggiungibile attraverso il tunnel | Provare l'API dal ThinkPad e verificare che `ollama serve` sia ancora attivo |
| Versione o modello rifiutati | Leggere `preflight_error.json`; il runner richiede server >= 0.32.15 e Qwen3.5-4B Q4_K_M |
| Timeout o risposta non valida | Conservare il tentativo fallito e leggerne la diagnostica; nessun fallback a Gemini |

## Riferimenti

- [Ollama su Windows](https://docs.ollama.com/windows)
- [Configurazione Ollama e disattivazione cloud](https://docs.ollama.com/faq)
- [OpenSSH Server su Windows](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse)
- [Opzioni SSH e inoltro locale](https://man.openbsd.org/ssh)
- [USB4NET su Windows](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/usb4-interdomain-connections)
- [Thunderbolt Bridge su macOS](https://support.apple.com/en-kw/guide/mac-help/mchld53dd2f5/mac)
