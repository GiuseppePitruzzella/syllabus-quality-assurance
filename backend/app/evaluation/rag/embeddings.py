"""Gen AI SDK embeddings wrapper for ``gemini-embedding-001``.

Migrated to ``google-genai`` (Vertex AI backend) from the deprecated
``vertexai.language_models.TextEmbeddingModel``, which is removed on
2026-06-24. The public surface of :class:`VertexAIEmbeddings` is
unchanged by design — the migration is infrastructural, not a
functional change.

Documented invariants preserved across the migration:

- Asymmetric task types: ``RETRIEVAL_DOCUMENT`` for documents stored
  in the vector store, ``RETRIEVAL_QUERY`` for the retriever queries.
- One API call per text (``gemini-embedding-001`` batch size is 1).
- Output dimensionality 3072 by default, enforced on every response.
- Retry policy: 3 attempts with exponential backoff (1s, 4s, 16s) on
  quota / availability errors raised by the underlying Vertex backend.
  Both the legacy ``google.api_core.exceptions`` family (still raised
  by the backend in many cases) and the new
  ``google.genai.errors.ServerError`` family are retryable. Permanent
  errors (``ClientError`` 4xx, ``ValueError``) propagate immediately.
"""
from __future__ import annotations

import time

import structlog
from google import genai
from google.api_core.exceptions import (
    DeadlineExceeded,
    ResourceExhausted,
    ServiceUnavailable,
)
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger(__name__)


def _is_retryable_error(exc: BaseException) -> bool:
    """Decide which exceptions deserve a back-off retry.

    - ``ServerError`` (5xx from the Gen AI SDK) -> retry.
    - ``ClientError`` (4xx) -> retry ONLY when the HTTP code is
      429 (rate limit). The new SDK surfaces quota / rate-limit
      errors as ``ClientError(code=429)``, so without this check
      a real 429 would NOT be retried (regression vs. the legacy
      ``ResourceExhausted`` path).
    - Legacy ``google.api_core`` quota / availability exceptions
      are still propagated by the underlying Vertex backend in
      many cases, so they remain in the retryable set as a
      defensive fallback.
    """
    if isinstance(exc, (ResourceExhausted, ServiceUnavailable, DeadlineExceeded)):
        return True
    if isinstance(exc, genai_errors.ServerError):
        return True
    if isinstance(exc, genai_errors.ClientError):
        return getattr(exc, "code", None) == 429
    return False


class VertexAIEmbeddings:
    """Vertex AI wrapper for ``gemini-embedding-001`` via the Gen AI SDK.

    The class is intentionally thin: no caching, no rate limiting.
    Rate limiting lives in a separate ``VertexAILimitedClient`` (added
    in Phase 5.4) so it can be shared with the LLM client.

    Public surface (constructor signature, ``embed_documents``,
    ``embed_query``, ``model_name``, ``output_dimensionality``)
    matches the pre-migration class exactly. Callers do not need to
    change.
    """

    DOCUMENT_TASK_TYPE = "RETRIEVAL_DOCUMENT"
    QUERY_TASK_TYPE = "RETRIEVAL_QUERY"

    def __init__(
        self,
        project_id: str,
        location: str,
        model_name: str = "gemini-embedding-001",
        output_dimensionality: int = 3072,
    ) -> None:
        if not project_id:
            raise ValueError("project_id is required (set GCP_PROJECT_ID in .env)")
        # Pin the stable API surface (``v1``). Without this, the
        # client may target beta endpoints, which can shift
        # response shape between runs and hurts the
        # reproducibility guarantees of the EvaluationResult.
        self._client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
            http_options=genai_types.HttpOptions(api_version="v1"),
        )
        self._model_name = model_name
        self._location = location
        self._output_dim = output_dimensionality

    @property
    def output_dimensionality(self) -> int:
        return self._output_dim

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts as ``RETRIEVAL_DOCUMENT``.

        Each text is sent in its own API call (gemini-embedding-001
        batch size is 1). An empty list returns ``[]`` without any API
        traffic. Empty / whitespace-only strings raise ``ValueError``.
        """
        if not texts:
            return []
        return [self._embed_one(t, self.DOCUMENT_TASK_TYPE) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string as ``RETRIEVAL_QUERY``."""
        return self._embed_one(text, self.QUERY_TASK_TYPE)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        retry=retry_if_exception(_is_retryable_error),
        reraise=True,
    )
    def _embed_one(self, text: str, task_type: str) -> list[float]:
        if not text or not text.strip():
            raise ValueError("text must be a non-empty string")

        started = time.time()
        response = self._client.models.embed_content(
            model=self._model_name,
            contents=text,
            config=genai_types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self._output_dim,
            ),
        )
        latency_ms = int((time.time() - started) * 1000)

        embeddings = getattr(response, "embeddings", None)
        if not embeddings:
            raise RuntimeError("Gen AI SDK returned no embeddings")
        values = list(embeddings[0].values)
        if len(values) != self._output_dim:
            raise RuntimeError(
                f"Gen AI SDK returned embedding of dimension {len(values)}, "
                f"expected {self._output_dim}"
            )

        logger.info(
            "embedding_completed",
            model=self._model_name,
            task_type=task_type,
            text_chars=len(text),
            output_dim=self._output_dim,
            latency_ms=latency_ms,
        )
        return values


class GeminiApiEmbeddings(VertexAIEmbeddings):
    """Embeddings on the Gemini Developer API (AI Studio) free tier (D080).

    Reuses all VertexAIEmbeddings behaviour (asymmetric task types, per-text
    call, 3072-dim enforcement, retry policy). Only the client construction
    differs: API key instead of ADC project/location. The spike (2026-07-06)
    confirmed ``output_dimensionality=3072`` is honoured on this backend.
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-embedding-001",
        output_dimensionality: int = 3072,
        rpm_limit: int = 0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required (set GEMINI_API_KEY in .env)")
        # Local import avoids a module-level dependency of the rag package on the
        # agents package; the gate itself is dependency-free.
        from app.evaluation.agents.rate_limit import MinIntervalGate

        self._client = genai.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(api_version="v1"),
        )
        self._model_name = model_name
        self._location = ""
        self._output_dim = output_dimensionality
        # Free-tier embedding quota is 100 req/min; gate each call to stay under
        # it during corpus ingestion (315 chunks in one pass).
        self._gate = MinIntervalGate(rpm_limit)

    def _embed_one(self, text: str, task_type: str) -> list[float]:
        self._gate.wait()
        return super()._embed_one(text, task_type)
