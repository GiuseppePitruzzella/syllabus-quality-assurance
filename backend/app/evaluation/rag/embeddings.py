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
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger(__name__)

# Both the legacy google.api_core family (still propagated by the
# underlying Vertex backend in many cases) and the new SDK
# ``ServerError`` (5xx) qualify as retryable. ``ClientError`` 4xx is
# intentionally NOT retried — it usually means invalid argument or
# permission denied and retrying would just hit the same wall.
_RETRYABLE_EXCEPTIONS = (
    ResourceExhausted,
    ServiceUnavailable,
    DeadlineExceeded,
    genai_errors.ServerError,
)


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
        self._client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
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
        retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
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
