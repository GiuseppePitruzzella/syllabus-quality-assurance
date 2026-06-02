# syllabus-quality-assurance

Syllabus Quality Assurance: a Retrieval-Augmented Multi-Agent Framework for Automated Evaluation of UniCT syllabi.

Il prototipo acquisisce syllabus da SmartEdu, li salva localmente, li rende consultabili tramite frontend React/FastAPI e costruisce una pipeline di valutazione con:

- corpus normativo chiuso di 8 documenti Markdown;
- chunking per sezione logica, tagging per criterio/agente e retrieval ChromaDB;
- embedding `gemini-embedding-001` e generazione `gemini-2.5-flash` via Vertex AI;
- agenti specialistici A1-A4 sui criteri core C1-C9;
- output JSON validato con Pydantic, evidenze testuali dal syllabus e report leggibile.

Stato Phase 5: A1 e A2 implementati e calibrati su 5 syllabus LM-18; prompt A3 compilato e revisionato; A3/A4, orchestrazione, persistenza dei risultati e UI di valutazione sono i prossimi blocchi.
