<br />
<div align="center">
<a href="https://github.com/GiuseppePitruzzella/syllabus-quality-assurance">
<!-- <img src="assets/img/logo.png" alt="Logo" width="300"> -->
</a>

<h3 align="center">Multi-Agentic System for Evaluation of University Syllabi</h3>

<p align="center">
A multi-agent system that supports the evaluation and quality assurance of university syllabi.
<br /><br />
<a href="https://github.com/GiuseppePitruzzella/syllabus-quality-assurance/issues">Report Bug</a>
·
<a href="https://github.com/GiuseppePitruzzella/syllabus-quality-assurance/issues">Request Feature</a>
<br /><br />
</p>
</div>

> This `main` branch is the reference configuration on Vertex AI, used for the thesis experiments. If you prefer to run everything with Google's free API (Gemini Developer API / AI Studio) and Docker, switch to the [`feature/docker-gemini-dev-api`](https://github.com/GiuseppePitruzzella/syllabus-quality-assurance/tree/feature/docker-gemini-dev-api) branch.
> ```bash
> git checkout feature/docker-gemini-dev-api
> ```

## 📘 Project Overview

Syllabus Quality Assurance is my master's thesis project for evaluating the syllabi of the University of Catania. The system reads the text of a syllabus and compares it against a rubric of criteria, returning for each one a score, a justification, and the textual evidence it relies on. Evaluations are grounded in a closed normative corpus via RAG. The case study was my own master's degree programme, LM-18 Computer Science.

## ✨ Features

- Acquisition (i.e. scraping) of syllabi from SmartEdu, with local storage and browsing via the frontend;
- Evaluation on the core criteria C1–C9 with a `CoreScore` (mean of the evaluated criteria, on a 0–2 scale);
- Extended criteria E1–E5 (optional, exploratory), grounded in documents specific to the degree programme.
- Multi-agent architecture based on four specialised agents A1–A4, each responsible for a subset of criteria.
- RAG grounding over a set of institutional documents (ChromaDB) with `gemini-embedding-001` embeddings.
- Per-evaluation output, guided and technical views of the results, and export capability.

## 🏗️ Architecture

Monorepo with two independent packages:

| Component | Stack | Port (dev) |
| --- | --- | --- |
| `backend/` | FastAPI + SQLAlchemy + SQLite, LangGraph evaluation pipeline (agents A1–A4), RAG over ChromaDB, Gemini client via **Vertex AI** | `8000` |
| `frontend/` | React 19 + Vite (SPA) | `5173` |

The models used are `gemini-2.5-flash` for generation and `gemini-embedding-001` for embeddings (3072 dimensions). Local persistence uses SQLite in `backend/data/`, a ChromaDB vector store in `data/chroma/`, and the normative corpus in `data/normative_corpus/`.
Criteria are handled by the agents as follows: A1 → {C1, C2, C5}; A2 → {C3, C4}; A3 → {C6, C7, C8}; A4 → {C9}.

## 🧩 Prerequisites

- **Python 3.12** and [**uv**](https://docs.astral.sh/uv/) (backend dependency management).
- **Node.js** (React + Vite frontend).
- A **Google Cloud project** with Vertex AI enabled and **Application Default Credentials** configured:
  ```bash
  gcloud auth application-default login
  ```

## ⚙️ Setup & run (native, Vertex AI)

**1. Backend configuration.** In `backend/.env` (see `backend/.env.example`) set at least the GCP project:
```bash
GCP_PROJECT_ID=<your-project>
# GCP_LOCATION=europe-west1   # default
```

**2. Backend.**
```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload      # http://localhost:8000
```

**3. Normative corpus and indexing (one-off).** The prototype is agnostic to the internal documents used: the corpus is **not included in the repository**. Place your normative documents *in Markdown format* in `data/normative_corpus/` (see the README in that folder), then build the ChromaDB index with Vertex embeddings:
```bash
cd backend
uv run python scripts/ingest_corpus.py
```
> Contact me if you'd like the documents I used to evaluate the core criteria in the experiments, so you can place them in `data/normative_corpus/`.

**4. Frontend.**
```bash
cd frontend
npm install
npm run dev                                # http://localhost:5173
```

## 📖 Using the application in practice

A typical path, from a clean install to the first evaluation.

### 1. Populate the data (scraping)
On first start the database is empty: syllabi must be acquired from SmartEdu. Scraping works at four levels (departments, degree programmes, syllabus list, detail).

From the frontend you can browse departments, select the degree programme (e.g. LM-18 Computer Science) and start the acquisition. Batch operations use the `job_id` + SSE streaming pattern to follow progress.

Alternatively, via the API (`cdl_id = 3` for LM-18):
```bash
# 1) populate the programme's syllabus list
curl -X POST http://localhost:8000/api/scrape/cdl/3/syllabi
# 2) download the details of every syllabus in the list
curl -X POST http://localhost:8000/api/scrape/cdl/3/syllabi/all
```

### 2. Browse the syllabi
Open the frontend, browse the acquired syllabi and view the detail of each (learning outcomes, Dublin descriptors, programme, English version when present). This stage requires no model calls.

### 3. Sign in
Register an account and sign in to use the evaluation features.

### 4. Evaluate a syllabus
From a syllabus page, start an **evaluation**. The **explicit document selection** screen appears first (for the extended criteria). Agents A1–A4 run in sequence; progress is shown in real time via SSE. At the end you get, for each criterion, a score, a justification and evidence, plus the overall `CoreScore`.

### 5. Extended criteria E1–E5 (local documents)
The core criteria **C1–C9** evaluate the syllabus text only. The extended criteria **E1–E5** require documents specific to the degree programme: SUA-CdS, the academic programme regulations and the Tuning matrix (E1–E4), and a departmental-practices document (E5). Upload them from the documents section, wait until they are **indexed**, then **select** them in the pre-evaluation screen. Documents are associated with the degree programme, not with the account.

### 6. Results and export
Results are available in two views: **guided** (concise, for reading) and **technical** (detail of evidence, retrieved RAG chunks, criteria marked `NA`). From here you can **export** the evaluation to **DOCX**.

## 🔀 Model backend

On `main` the model backend is **Vertex AI**: it requires a GCP project and ADC credentials, and it is billed per use. It is the configuration used to run the thesis evaluation campaign. Otherwise, the [`feature/docker-gemini-dev-api`](https://github.com/GiuseppePitruzzella/syllabus-quality-assurance/tree/feature/docker-gemini-dev-api) branch lets you run the whole application in Docker using the Gemini Developer API (AI Studio) with a free API key, without any Google Cloud setup. The model stays identical (`gemini-2.5-flash` / `gemini-embedding-001`).

## 🗂️ Repository structure

```
.
├── backend/              # FastAPI, scraping, evaluation pipeline, RAG
│   ├── app/              # application code (API, agents, RAG, models)
│   ├── scripts/          # CLI utilities (e.g. ingest_corpus.py)
│   └── data/             # SQLite + uploaded documents (local)
├── frontend/             # React + Vite (SPA)
└── data/
    ├── normative_corpus/ # your normative documents (not versioned; see README)
    └── chroma/           # ChromaDB vector store (generated)
```
