<br />
<div align="center">
<a href="https://github.com/GiuseppePitruzzella/syllabus-quality-assurance">
<!-- <img src="assets/img/logo.png" alt="Logo" width="300"> -->
</a>

<h3 align="center">Syllabus Quality Assurance</h3>

<p align="center">
Sistema multi-agente di supporto alla valutazione automatica dei syllabus universitari, ancorato a un corpus normativo tramite RAG.
<br /><br />
<a href="https://github.com/GiuseppePitruzzella/syllabus-quality-assurance/issues">Report Bug</a>
·
<a href="https://github.com/GiuseppePitruzzella/syllabus-quality-assurance/issues">Request Feature</a>
<br /><br />
</p>
</div>

> **Vuoi provarlo senza costi e con un solo comando?**
> Questo branch `main` è la configurazione di riferimento su **Vertex AI** (Google Cloud, a consumo), usata per gli esperimenti della tesi. Se preferisci eseguire il tutto **a costo zero** con le **API gratuite di Google (Gemini Developer API / AI Studio)** e **Docker**, passa al branch [`feature/docker-gemini-dev-api`](https://github.com/GiuseppePitruzzella/syllabus-quality-assurance/tree/feature/docker-gemini-dev-api), che ha un README dedicato:
> ```bash
> git checkout feature/docker-gemini-dev-api
> ```

## 📘 Project Overview

Syllabus Quality Assurance è il mio progetto di tesi magistrale utile alla valutazione dei syllabus dell'Università di Catania. Il sistema legge il testo di un syllabus e lo confronta con una rubrica di criteri, restituendo per ciascuno un punteggio, una motivazione e le evidenze testuali su cui si basa. Le valutazioni sono ancorate a un corpus normativo chiuso tramite RAG (Retrieval-Augmented Generation): gli agenti non giudicano "a memoria", ma recuperano i frammenti normativi pertinenti e vi si appoggiano.

Caso di studio: Corso di Laurea Magistrale **LM-18 Informatica**.

## ✨ Funzionalità

- **Acquisizione (scraping)** dei syllabus da SmartEdu, con salvataggio locale e consultazione via frontend.
- **Valutazione sui criteri core C1–C9** con calcolo del `CoreScore` (media dei criteri valutati, scala 0–2).
- **Criteri estesi E1–E5** (opzionali, esplorativi), ancorati a documenti specifici del Corso di Studio.
- **Architettura multi-agente**: quattro agenti specialistici A1–A4, ognuno responsabile di un sottoinsieme di criteri.
- **Grounding via RAG** su corpus normativo (ChromaDB) con embedding `gemini-embedding-001`.
- **Doppio output** per ogni valutazione: JSON strutturato e report leggibile in italiano.
- **Viste guidata e tecnica** dei risultati, con export DOCX.
- **Bilingue**: gestisce syllabus con versione inglese assente, parziale o strutturata diversamente.

## 🏗️ Architettura

Monorepo con due package indipendenti:

| Componente | Stack | Porta (dev) |
| --- | --- | --- |
| `backend/` | FastAPI + SQLAlchemy + SQLite, pipeline di valutazione LangGraph (agenti A1–A4), RAG su ChromaDB, client Gemini via **Vertex AI** | `8000` |
| `frontend/` | React 19 + Vite (SPA) | `5173` |

Modelli: generazione `gemini-2.5-flash`, embedding `gemini-embedding-001` (3072 dimensioni). Persistenza locale: SQLite in `backend/data/`, vector store ChromaDB in `data/chroma/`, corpus normativo in `data/normative_corpus/`.

Mapping criteri → agenti: A1 → {C1, C2, C5}; A2 → {C3, C4}; A3 → {C6, C7, C8}; A4 → {C9}.

## 🧩 Prerequisiti

- **Python 3.12** e [**uv**](https://docs.astral.sh/uv/) (gestione dipendenze backend).
- **Node.js** (frontend React + Vite).
- Un **progetto Google Cloud** con Vertex AI abilitato e le **Application Default Credentials** configurate:
  ```bash
  gcloud auth application-default login
  ```

## ⚙️ Setup & avvio (nativo, Vertex AI)

**1. Configurazione backend.** In `backend/.env` (vedi `backend/.env.example`) imposta almeno il progetto GCP:
```bash
GCP_PROJECT_ID=<il-tuo-progetto>
# GCP_LOCATION=europe-west1   # default
```

**2. Backend.**
```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload      # http://localhost:8000
```

**3. Corpus normativo e indicizzazione (una tantum).** Il prototipo è agnostico rispetto ai documenti interni: il corpus **non è incluso nel repository**. Inserisci i tuoi documenti normativi in formato Markdown in `data/normative_corpus/` (vedi il README nella cartella), poi costruisci l'indice ChromaDB con embedding Vertex:
```bash
cd backend
uv run python scripts/ingest_corpus.py
```
**Contattami** se vuoi i documenti che ho usato per valutare i criteri core negli esperimenti, così da inserirli in `data/normative_corpus/`.

**4. Frontend.**
```bash
cd frontend
npm install
npm run dev                                # http://localhost:5173
```

Il frontend punta all'API su `http://localhost:8000/api`.

## 📖 USAGE — usare l'applicazione in pratica

Percorso tipico, dall'installazione pulita alla prima valutazione.

### 1. Popolare i dati (scraping)
Al primo avvio il database è vuoto: i syllabus vanno acquisiti da SmartEdu. Lo scraping è a 4 livelli (dipartimenti → corsi di laurea → elenco syllabus → dettaglio) ed è integrato nel flusso dell'app. Dal frontend puoi navigare i dipartimenti, selezionare il Corso di Laurea (es. LM-18 Informatica) e avviare l'acquisizione. Le operazioni batch usano il pattern `job_id` + streaming SSE per seguire l'avanzamento.

In alternativa, via API (LM-18 ha `cdl_id = 3` nel DB locale di riferimento):
```bash
# 1) popola l'elenco dei syllabus del CdL
curl -X POST http://localhost:8000/api/scrape/cdl/3/syllabi
# 2) scarica i dettagli di tutti i syllabus dell'elenco
curl -X POST http://localhost:8000/api/scrape/cdl/3/syllabi/all
```
Lo scraping è volutamente rispettoso dell'infrastruttura UniCT (ritardo tra le richieste, user-agent identificato come ricerca accademica).

### 2. Consultare i syllabus
Apri il frontend, sfoglia i syllabus acquisiti e visualizza il dettaglio di ognuno (risultati di apprendimento, descrittori di Dublino, programma, versione inglese quando presente). Questa fase non richiede chiamate ai modelli.

### 3. Accesso
Registra un account (email + password) e accedi: le funzioni di valutazione sono protette da autenticazione.

### 4. Valutare un syllabus
Dalla pagina di un syllabus avvia una **valutazione**. Compare prima la schermata di **selezione esplicita dei documenti** (per i criteri estesi). Gli agenti A1–A4 vengono eseguiti in sequenza; l'avanzamento è mostrato in tempo reale via SSE. Al termine ottieni, per ogni criterio, punteggio, motivazione ed evidenze, oltre al `CoreScore` complessivo.

### 5. Criteri estesi E1–E5 (documenti locali)
I criteri core **C1–C9** valutano il solo testo del syllabus. I criteri estesi **E1–E5** richiedono documenti specifici del Corso di Studio: SUA-CdS, Regolamento didattico e Matrice di Tuning (E1–E4) e un documento di usi dipartimentali (E5). Caricali dalla sezione documenti, attendi che risultino **indicizzati**, poi **selezionali** nella schermata pre-valutazione. I documenti sono associati al Corso di Laurea, non all'account.

### 6. Risultati ed export
I risultati sono consultabili in due viste: **guidata** (sintetica, per la lettura) e **tecnica** (dettaglio di evidenze, frammenti RAG recuperati, criteri in `NA`). Da qui puoi **esportare** la valutazione in **DOCX**.

## 🔀 Backend dei modelli: Vertex AI (default) e alternativa gratuita

Su `main` il backend dei modelli è **Vertex AI**: richiede un progetto GCP e le credenziali ADC, e fattura a consumo. È la configurazione con cui è stata condotta la campagna di valutazione della tesi.

Se non vuoi (o non puoi) usare Vertex, il branch [`feature/docker-gemini-dev-api`](https://github.com/GiuseppePitruzzella/syllabus-quality-assurance/tree/feature/docker-gemini-dev-api) permette di eseguire l'intera applicazione **in Docker** usando la **Gemini Developer API (AI Studio)** con una **API key gratuita**, senza alcuna configurazione Google Cloud. Il modello resta identico (`gemini-2.5-flash` / `gemini-embedding-001`): cambia solo il canale. Consulta il README di quel branch per i dettagli.

## 🗂️ Struttura del repository

```
.
├── backend/              # FastAPI, scraping, pipeline di valutazione, RAG
│   ├── app/              # codice applicativo (API, agenti, RAG, modelli)
│   ├── scripts/          # utilità CLI (es. ingest_corpus.py)
│   └── data/             # SQLite + documenti caricati (locale)
├── frontend/             # React + Vite (SPA)
└── data/
    ├── normative_corpus/ # i tuoi documenti normativi (non versionati; vedi README)
    └── chroma/           # vector store ChromaDB (generato)
```
