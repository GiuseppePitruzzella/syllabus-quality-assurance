<br />
<div align="center">
<a href="https://github.com/GiuseppePitruzzella/syllabus-quality-assurance">
<!-- <img src="assets/img/logo.png" alt="Logo" width="300"> -->
</a>

<h3 align="center">Syllabus Quality Assurance</h3>

<p align="center">
Sistema multi-agente di supporto alla valutazione automatica dei syllabus universitari, ancorato a un corpus normativo tramite RAG. Deployment Docker con Gemini Developer API (piano gratuito).
<br /><br />
<a href="https://github.com/GiuseppePitruzzella/syllabus-quality-assurance/issues">Report Bug</a>
·
<a href="https://github.com/GiuseppePitruzzella/syllabus-quality-assurance/issues">Request Feature</a>
<br /><br />
</p>
</div>

> `feature/docker-gemini-dev-api` prevede l'esecuzione attraverso **Docker** usando **Gemini Developer API**. La configurazione a pagamento su Vertex AI resta disponibile by default su `main`.

## 📘 Project Overview

Syllabus Quality Assurance è il mio progetto di tesi magistrale utile alla valutazione di syllabus dell'Università di Catania.
Il sistema legge il testo di un syllabus e lo confronta con una rubrica di criteri, restituendo per ciascun criterio un punteggio, una motivazione e le evidenze testuali su cui si basa. Le valutazioni sono ancorate ad un corpus normativo chiuso tramite RAG.

## ✨ Funzionalità

- **Valutazione sui criteri core C1–C9** con calcolo del `CoreScore` (media dei criteri valutati, scala 0–2).
- **Criteri estesi E1–E5** (opzionali, esplorativi), ancorati a documenti specifici del Corso di Studio caricati dall'utente.
- **Architettura multi-agente**: quattro agenti specialistici A1–A4, ognuno responsabile di un sottoinsieme di criteri.
- **Grounding via RAG** su corpus normativo (ChromaDB) con embedding `gemini-embedding-001`.
- **Doppio output** per ogni valutazione: JSON strutturato e report leggibile in italiano.
- **Viste guidata e tecnica** dei risultati, con export DOCX.
- **Bilingue**: gestisce syllabus con versione inglese assente, parziale o strutturata diversamente.

## 🏗️ Architettura

Due container orchestrati da Docker Compose:

| Servizio | Contenuto | Esposizione |
| --- | --- | --- |
| `backend` | FastAPI + SQLAlchemy + SQLite, pipeline di valutazione LangGraph (agenti A1–A4), RAG su ChromaDB, client Gemini AI Studio | interno (`8000`, non pubblicato) |
| `frontend` | React 19 + Vite, servito da **nginx** che fa da reverse proxy verso `/api` | `http://localhost:8080` |

Un terzo servizio `seed` costruisce una tantum l'indice vettoriale del corpus normativo.
I modelli utilizzati sono `gemini-2.5-flash` per la generazione e `gemini-embedding-001` per l'embedding.

- `backend/data/`, database SQLite e documenti caricati;
- `data/normative_corpus/`, corpus normativo (input del seed);
- `data/chroma_aistudio/`, indice vettoriale costruito con embedding AI Studio.

## 🧩 Prerequisiti

- **Docker** e **Docker Compose** installati e con il daemon attivo.
- Una **API key gratuita di Gemini**, ottenibile su [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
- (Consigliato) il **bundle del database SQLite pre-popolato** con i syllabus, per non dover rifare lo scraping.

## ⚙️ Configurazione iniziale

1. Copiare il file di esempio delle variabili d'ambiente e inserire la propria chiave:

   ```bash
   cp .env.example .env
   # modificare .env e impostare GEMINI_API_KEY=<la-tua-chiave>
   ```

   Il file `.env` è git-ignored: la chiave resta solo sulla tua macchina.

2. (Consigliato) copiare il database pre-popolato in `backend/data/`, così l'app parte con i syllabus già caricati:

   ```bash
   cp /percorso/al/bundle/syllabus_ai.db backend/data/syllabus_ai.db
   ```

## 🌱 Seeding dell'indice vettoriale

Prima del primo avvio va costruito l'indice del corpus normativo (ChromaDB con embedding AI Studio).

Il prototipo è agnostico rispetto ai documenti interni: il corpus **non è incluso nel repository**. Inserisci i tuoi documenti normativi in formato Markdown in `data/normative_corpus/` (vedi il README nella cartella), poi esegui **una sola volta**:

```bash
docker compose --profile seed run --rm seed
```

L'operazione richiede alcuni minuti: gli embedding vengono deliberatamente rallentati (throttling) per restare sotto il limite gratuito di 100 richieste/minuto. Al termine vedrai il numero di chunk indicizzati e `Errors: 0` (con il corpus sperimentale sono 315 chunk).

**Contattami** se vuoi i documenti che ho usato per valutare i criteri core negli esperimenti, così da inserirli in `data/normative_corpus/`.

## 🚀 Avvio

```bash
docker compose up --build
```

Poi apri **[http://localhost:8080](http://localhost:8080)**. Per fermare lo stack: `docker compose down`.

## 🖥️ Guida all'uso

1. **Registrazione / login.** Al primo accesso crea un account e accedi.
2. **Consultazione.** Sfoglia i syllabus già presenti e apri il dettaglio di uno di essi.
3. **Valutazione.** Dalla pagina di un syllabus avvia una valutazione. Prima dell'esecuzione compare la schermata di **selezione esplicita dei documenti** (per i criteri estesi). Al termine puoi consultare i risultati nelle viste **guidata** e **tecnica** ed esportarli in DOCX.
4. **Attesa.** Una valutazione nuova esegue gli agenti A1–A4 in sequenza; con il piano gratuito (5 richieste/minuto sull'LLM) può richiedere qualche minuto.

## 📄 Documenti locali e criteri estesi (E1–E5)

I criteri core **C1–C9** valutano il solo testo del syllabus e funzionano **da subito** dopo il seed. I criteri estesi **E1–E5** richiedono invece documenti specifici del Corso di Studio (SUA-CdS, Regolamento didattico, Matrice di Tuning per E1–E4; documento di usi dipartimentali per E5).

> I documenti sono associati al Corso di Laurea, non all'account. Un documento caricato è quindi visibile a tutti gli account sullo stesso CdL: è una scelta di progetto del prototipo (perimetro a valutatore singolo), non un errore.

## 📊 Monitoraggio delle chiamate API

`gemini-2.5-flash` è limitato a circa **5 richieste al minuto**, più un tetto giornaliero. Le valutazioni sono perciò più lente (throttling integrato). `gemini-embedding-001` è limitato a circa **100 richieste al minuto**. Seed e indicizzazione documenti sono rallentati per rispettarlo.

**Lato Google (ufficiale):** l'uso corrente e i limiti sono consultabili su [ai.dev/rate-limit](https://ai.dev/rate-limit) e nella [documentazione dei rate limit](https://ai.google.dev/gemini-api/docs/rate-limits).

**Lato locale (in tempo reale):** il backend registra una riga di log per ogni chiamata di embedding. Per contarle:

```bash
# conteggio istantaneo delle chiamate embedding dall'avvio del container
docker compose logs backend | grep -c embedding_completed

# monitoraggio dal vivo (una riga per ogni embedding)
docker compose logs -f backend | grep --line-buffered embedding_completed
```

## 🔀 Backend: AI Studio vs Vertex AI

Il backend dei modelli è selezionabile via variabile d'ambiente, senza modifiche al codice:

- `GENAI_USE_VERTEX=false` (default in Docker) → Gemini Developer API / AI Studio, con `GEMINI_API_KEY`.
- `GENAI_USE_VERTEX=true` → Vertex AI, con credenziali GCP (`GCP_PROJECT_ID` e Application Default Credentials). È la configurazione usata per riprodurre la campagna di valutazione della tesi.

Il modello resta identico nei due casi: cambia solo il canale di fatturazione. Nota: i due backend usano indici vettoriali separati (`data/chroma_aistudio` per AI Studio, `data/chroma` per Vertex), per non mescolare embedding prodotti da canali diversi.

## 🩺 Risoluzione dei problemi

| Sintomo | Causa / soluzione |
| --- | --- |
| 502 all'apertura di localhost:8080 | nginx risponde prima che il backend abbia finito il boot. Ricarica la pagina dopo qualche secondo. |
| Il seed fallisce con `RESOURCE_EXHAUSTED` (429) | Limite embedding per minuto o tetto giornaliero. Attendi qualche minuto (o il giorno dopo) e rilancia il seed. |
| I criteri E1–E5 restano vuoti | I documenti non sono stati caricati/indicizzati in questo ambiente, oppure non sono stati selezionati nella schermata pre-valutazione. Vedi la sezione *Documenti locali e criteri estesi*. |
| `GEMINI_API_KEY is not set` | Manca la chiave: verifica di aver creato `.env` con `GEMINI_API_KEY` valorizzata. |
| Modifiche al codice non hanno effetto | Ricostruisci l'immagine: `docker compose build <servizio>`. Nota che il servizio `seed` ha un'immagine separata da `backend`. |

## 🗂️ Struttura del repository

```
.
├── backend/              # FastAPI, pipeline di valutazione, RAG, Dockerfile
│   └── data/             # SQLite + documenti caricati (bind-mount)
├── frontend/             # React + Vite, Dockerfile, nginx.conf
├── data/
│   ├── normative_corpus/ # corpus normativo (input del seed)
│   └── chroma_aistudio/  # indice vettoriale AI Studio (generato dal seed)
├── docker-compose.yml    # orchestrazione: backend, frontend, seed
└── .env.example          # template variabili d'ambiente (GEMINI_API_KEY)
```