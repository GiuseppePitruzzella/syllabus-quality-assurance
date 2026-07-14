<br />
<div align="center">
<a href="https://github.com/GiuseppePitruzzella/syllabus-quality-assurance">
<!-- <img src="assets/img/logo.png" alt="Logo" width="300"> -->
</a>

<h3 align="center">Syllabus Quality Assurance</h3>

<p align="center">
A multi-agent system supporting the automated evaluation of university syllabi, grounded in a normative corpus via RAG. Docker deployment with the Gemini Developer API (free tier).
<br /><br />
<a href="https://github.com/GiuseppePitruzzella/syllabus-quality-assurance/issues">Report Bug</a>
·
<a href="https://github.com/GiuseppePitruzzella/syllabus-quality-assurance/issues">Request Feature</a>
<br /><br />
</p>
</div>

> The `feature/docker-gemini-dev-api` branch runs the application in **Docker** using the **Gemini Developer API**. The paid Vertex AI configuration remains available by default on `main`.

## 📘 Project Overview

Syllabus Quality Assurance is my master's thesis project for evaluating the syllabi of the University of Catania.
The system reads the text of a syllabus and compares it against a rubric of criteria, returning for each criterion a score, a justification, and the textual evidence it relies on. Evaluations are grounded in a closed normative corpus via RAG.

## ✨ Features

- **Evaluation on the core criteria C1–C9** with a `CoreScore` (mean of the evaluated criteria, 0–2 scale).
- **Extended criteria E1–E5** (optional, exploratory), grounded in programme-specific documents uploaded by the user.
- **Multi-agent architecture**: four specialised agents A1–A4, each responsible for a subset of criteria.
- **RAG grounding** over the normative corpus (ChromaDB) with `gemini-embedding-001` embeddings.
- **Dual output** for each evaluation: structured JSON and a human-readable report in Italian.
- **Guided and technical views** of the results, with DOCX export.
- **Bilingual**: handles syllabi whose English version is absent, partial, or structured differently.

## 🏗️ Architecture

Two containers orchestrated by Docker Compose:

| Service | Contents | Exposure |
| --- | --- | --- |
| `backend` | FastAPI + SQLAlchemy + SQLite, LangGraph evaluation pipeline (agents A1–A4), RAG over ChromaDB, Gemini AI Studio client | internal (`8000`, not published) |
| `frontend` | React 19 + Vite, served by **nginx** acting as a reverse proxy to `/api` | `http://localhost:8080` |

A third `seed` service builds the normative corpus's vector index once.
The models used are `gemini-2.5-flash` for generation and `gemini-embedding-001` for embeddings.

- `backend/data/` — SQLite database and uploaded documents;
- `data/normative_corpus/` — normative corpus (seed input);
- `data/chroma_aistudio/` — vector index built with AI Studio embeddings.

## 🧩 Prerequisites

- **Docker** and **Docker Compose** installed, with the daemon running.
- A **free Gemini API key**, obtainable at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

## ⚡ Quick start

All the steps, in order, from clone to first run:

```bash
# 1. Free API key (https://aistudio.google.com/apikey)
cp .env.example .env
#    then open .env and set GEMINI_API_KEY=<your-key>

# 2. CORE-CRITERIA documents (required): place the normative corpus
#    .md files in data/normative_corpus/ (contact me for the experimental ones)

# 3. Build the vector index (one-off, a few minutes)
docker compose --profile seed run --rm seed

# 4. Start the application
docker compose up --build          # then open http://localhost:8080

# To stop everything
docker compose down
```

Documents for the **extended criteria (E1–E5)** are **optional** and are uploaded from the app (see *Local documents and extended criteria*). Each step is detailed in the sections below.

## ⚙️ Initial configuration

1. Copy the example environment file and insert your key:

   ```bash
   cp .env.example .env
   # edit .env and set GEMINI_API_KEY=<your-key>
   ```

   The `.env` file is git-ignored: the key stays only on your machine.

## 🌱 Core-criteria documents and seeding

The core criteria **C1–C9** are grounded in a **normative corpus**: providing these documents and building the index is **required** for the core evaluation to work.

The prototype is agnostic to the internal documents used: the corpus is **not included in the repository**. Place your normative documents in Markdown (`.md`) in `data/normative_corpus/` (see the README in that folder), then build the index (ChromaDB with AI Studio embeddings) **once**:

```bash
docker compose --profile seed run --rm seed
```

This takes a few minutes: embeddings are deliberately throttled to stay under the free-tier limit of 100 requests/minute. At the end you'll see the number of indexed chunks and `Errors: 0` (315 chunks with the experimental corpus).

**Contact me** if you'd like the documents I used to evaluate the core criteria in the experiments, so you can place them in `data/normative_corpus/`.

## 🚀 Run

```bash
docker compose up --build
```

Then open **[http://localhost:8080](http://localhost:8080)**. To stop the stack: `docker compose down`.

## 🖥️ How to use

1. **Register / sign in.** On first access, create an account and sign in.
2. **Browse.** Browse the syllabi already present and open the detail of one.
3. **Evaluate.** From a syllabus page, start an evaluation. Before it runs, the **explicit document selection** screen appears (for the extended criteria). When done, you can view the results in the **guided** and **technical** views and export them to DOCX.
4. **Wait.** A new evaluation runs agents A1–A4 in sequence; on the free tier (5 requests/minute on the LLM) it may take a few minutes.

## 📄 Local documents and extended criteria (E1–E5) — optional

The core criteria **C1–C9** evaluate the syllabus text only and work right after the seed. The extended criteria **E1–E5** are **optional** and require programme-specific documents (SUA-CdS, academic regulations, and the Tuning matrix for E1–E4; a departmental-practices document for E5).

To enable them, **upload them from the app** (documents section) and wait until they are *indexed*: on upload they are indexed with AI Studio embeddings into the `data/chroma_aistudio` index. Then **select** them in the pre-evaluation screen.

> After the seed, the AI Studio index contains only the corpus. Re-uploading the full set to use the extended criteria for LM-18 costs about **129 embedding calls**.

> Documents are associated with the degree programme, not with the account. An uploaded document is therefore visible to all accounts on the same programme: this is a design choice of the prototype (single-evaluator scope), not a bug.

## 📊 API call limits and monitoring

The free tier has both **per-minute** and **per-day** limits:

- `gemini-2.5-flash` (LLM): about **5 requests/minute** and a **daily cap** on requests. Evaluations are therefore slower (built-in throttling).
- `gemini-embedding-001` (embeddings): about **100 requests/minute** (a quota separate from the LLM). Seeding and document indexing are throttled to respect it.

> **Daily limit.** If calls fail with `RESOURCE_EXHAUSTED` and the quota cited contains *PerDay*, you've exhausted the **daily cap**: waiting a minute isn't enough. Free-tier quotas reset at **midnight Pacific Time**, i.e. **~09:00 Italian time**. If you don't want to wait, use a **second API key** (from another Google project, with its own quota) or switch to **Vertex AI** (`GENAI_USE_VERTEX=true`).

**Google side (official):** current usage and limits are available at [ai.dev/rate-limit](https://ai.dev/rate-limit) and in the [rate-limits documentation](https://ai.google.dev/gemini-api/docs/rate-limits).

**Local side (real time):** the backend logs one line per embedding call. To count them:

```bash
# instant count of embedding calls since the container started
docker compose logs backend | grep -c embedding_completed

# live monitoring (one line per embedding)
docker compose logs -f backend | grep --line-buffered embedding_completed
```

## 🔀 Model backend: AI Studio vs Vertex AI

The model backend is selectable via an environment variable, with no code changes:

- `GENAI_USE_VERTEX=false` (default in Docker) → Gemini Developer API / AI Studio, with `GEMINI_API_KEY`.
- `GENAI_USE_VERTEX=true` → Vertex AI, with GCP credentials (`GCP_PROJECT_ID` and Application Default Credentials). This is the configuration used to reproduce the thesis evaluation campaign.

The model stays identical in both cases: only the billing channel changes. Note: the two backends use separate vector indexes (`data/chroma_aistudio` for AI Studio, `data/chroma` for Vertex) so as not to mix embeddings produced by different channels.

## 🗂️ Repository structure

```
.
├── backend/              # FastAPI, evaluation pipeline, RAG, Dockerfile
│   └── data/             # SQLite + uploaded documents (bind-mount)
├── frontend/             # React + Vite, Dockerfile, nginx.conf
├── data/
│   ├── normative_corpus/ # normative corpus (seed input)
│   └── chroma_aistudio/  # AI Studio vector index (generated by the seed)
├── docker-compose.yml    # orchestration: backend, frontend, seed
└── .env.example          # environment variables template (GEMINI_API_KEY)
```
