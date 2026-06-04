from pathlib import Path

from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root contains both `backend/` and the shared `data/` directory
# (corpus + vector store live at project root; the SQLite DB stays under backend/data/).
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class ScientificConfig(BaseModel):
    """Parametri scientifici versionati in git.

    Frozen: non sovrascrivibili a runtime nemmeno via env. Modificarli richiede
    un commit e una nuova ``prompt_version`` registrata in ``EvaluationResult``.
    """

    model_config = ConfigDict(frozen=True)

    llm_model: str = "gemini-2.5-flash"
    embedding_model: str = "gemini-embedding-001"
    embedding_output_dimensionality: int = 3072
    llm_temperature: float = 0.1
    # Sized for gemini-2.5-flash with default thinking enabled.
    # Empirical evidence (D030):
    # - 2048: every A1 calibration run truncated (5/5).
    # - 4096: only 1/5 succeeded (OTTIMIZZAZIONE, prompt 39811c). Larger
    #   prompts (40-47k chars) consumed >2500 thoughts_tokens and the
    #   JSON output was truncated.
    # - 8192: gives ~5-6k token of headroom over the observed thoughts
    #   budget, enough for the JSON output of any 3-criterion agent
    #   (A1, A3) on prompts up to the largest LM-18 syllabus seen so
    #   far (Deep Learning, ~12k input tokens).
    # Cost is bounded by tokens actually generated, not by this limit.
    llm_max_output_tokens: int = 8192
    rag_top_k: int = 5
    rag_final_k: int = 3
    rag_similarity_threshold: float = 0.6


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # === Persistence (existing) ===
    database_url: str = f"sqlite:///{BACKEND_DATA_DIR / 'syllabus_ai.db'}"

    # === Scraping (existing) ===
    scrape_delay: float = 1.5
    scrape_timeout: int = 15
    scrape_user_agent: str = "SyllabusAI/1.0 (UniCT research thesis)"

    # === GCP / Vertex AI ===
    gcp_project_id: str = ""
    gcp_location: str = "europe-west1"

    # === Vector store and corpus paths (project root) ===
    chroma_persist_dir: str = str(PROJECT_ROOT / "data" / "chroma")
    normative_corpus_dir: str = str(PROJECT_ROOT / "data" / "normative_corpus")
    tagging_rules_file: str = str(PROJECT_ROOT / "data" / "tagging_rules.yaml")

    # === Local-document registry (Phase 8) ===
    # Filesystem root for uploads. Per-CdL subdirectory is created on
    # first upload. Versioning is on disk too: each version of a
    # document gets its own file, old versions are kept for the
    # lifetime of any EvaluationResult that referenced them.
    local_documents_dir: str = str(BACKEND_DATA_DIR / "local_documents")

    # === Rate limiting (Vertex AI) ===
    vertex_ai_rpm_limit: int = 30

    # === Evaluation pipeline (Phase 5.4.H) ===
    # Hard timeout for a single graph run. The AsyncEvaluationService
    # cancels the worker thread (and emits an ``error`` SSE event) if
    # the graph takes longer than this. Default 10 min covers the
    # observed end-to-end runs (~3-5 min) with comfortable headroom.
    evaluation_timeout_seconds: int = 600

    # === Development frontend ===
    # Explicit origins keep browser CORS behaviour predictable during the
    # Vite/FastAPI split-dev setup used for Phase 5.5 UI smoke tests.
    cors_allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # === Logging ===
    log_level: str = "INFO"

    @property
    def scientific(self) -> ScientificConfig:
        return ScientificConfig()

    def require_vertex_ai_config(self) -> tuple[str, str]:
        """Validate Vertex AI config and return ``(project_id, location)``.

        No fallback to ``gcloud config get-value project``: the project used
        for any experimental run must be explicit in the configuration so
        every ``EvaluationResult`` is reproducible.

        Raises:
            RuntimeError: if ``gcp_project_id`` is empty.
        """
        if not self.gcp_project_id:
            raise RuntimeError(
                "GCP_PROJECT_ID is not set. Vertex AI calls (embeddings and "
                "LLM) require an explicit project ID. Set it in backend/.env "
                "(see backend/.env.example). No automatic fallback to "
                "`gcloud config` is performed: the project is part of the "
                "experimental configuration and must be tracked explicitly."
            )
        return self.gcp_project_id, self.gcp_location


settings = Settings()
