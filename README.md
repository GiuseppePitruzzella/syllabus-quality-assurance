# syllabus-quality-assurance

Syllabus Quality Assurance: a Retrieval-Augmented Multi-Agent Framework for Automated Evaluation of UniCT syllabi.

Il prototipo acquisisce syllabus da SmartEdu, li salva localmente, li rende consultabili tramite frontend React/FastAPI e costruisce una pipeline di valutazione con:

- corpus normativo chiuso di 8 documenti Markdown;
- chunking per sezione logica, tagging per criterio/agente e retrieval ChromaDB;
- embedding `gemini-embedding-001` e generazione `gemini-2.5-flash` via Vertex AI;
- agenti specialistici A1-A4 sui criteri core C1-C9;
- output JSON validato con Pydantic, evidenze testuali dal syllabus e report leggibile.

Stato Phase 5: A1 e A2 implementati e calibrati su 5 syllabus LM-18; prompt A3 compilato e revisionato; A3/A4, orchestrazione, persistenza dei risultati e UI di valutazione sono i prossimi blocchi.

## Eseguire con Docker (Gemini Developer API)

Questa modalità permette di avviare l'intero prototipo (backend + frontend) con un comando, usando la Gemini Developer API di Google AI Studio come backend LLM/embedding. È il percorso pensato per chi deve solo consultare i syllabus già caricati e provare qualche valutazione, senza configurare un progetto Google Cloud.

### Prerequisiti

- Docker e Docker Compose installati.
- Una API key gratuita di Gemini, ottenibile su [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

### Setup

Copiare il file di esempio delle variabili d'ambiente e inserire la propria chiave:

```bash
cp .env.example .env
# poi modificare .env e impostare GEMINI_API_KEY=<la-tua-chiave>
```

Se si dispone del bundle del database SQLite pre-popolato (`syllabus_ai.db`), copiarlo in `backend/data/` prima di avviare i container, in modo che l'applicazione parta con i syllabus già caricati e non sia necessario rifare lo scraping:

```bash
cp /percorso/al/bundle/syllabus_ai.db backend/data/syllabus_ai.db
```

### Seeding una tantum (indice vettoriale)

Prima del primo avvio è necessario costruire l'indice vettoriale del corpus normativo su AI Studio (ChromaDB con embedding Gemini). Questo passaggio va eseguito una sola volta:

```bash
docker compose --profile seed run --rm seed
```

### Avvio

```bash
docker compose up --build
```

L'applicazione è raggiungibile su [http://localhost:8080](http://localhost:8080).

### Note

- Il backend predefinito in questa configurazione è la Gemini Developer API gratuita (AI Studio): il `docker-compose.yml` imposta `GENAI_USE_VERTEX=false`.
- Limiti del piano gratuito: `gemini-2.5-flash` è limitato a circa 5 richieste al minuto, più un tetto giornaliero di richieste. Consultare i syllabus e i dati già caricati non richiede chiamate API; la chiave serve solo per lanciare NUOVE valutazioni, che di conseguenza risulteranno più lente a causa del throttling.
- Trasparenza: con il piano gratuito di AI Studio, Google può utilizzare i dati delle richieste per migliorare i propri prodotti. I syllabus trattati sono documenti pubblici.
- Vertex AI resta disponibile come backend alternativo impostando `GENAI_USE_VERTEX=true` e fornendo le credenziali GCP (`GCP_PROJECT_ID` e Application Default Credentials); è la configurazione usata per riprodurre la campagna di valutazione della tesi.
