"""Vertex AI gemini-embedding-001 wrapper.

Provides a simple batch-friendly interface around the Vertex AI text
embedding API. ``gemini-embedding-001`` accepts only one input per
request, so the public batch surface (:meth:`embed_documents`)
iterates internally.

Asymmetric task types are used so document embeddings (stored in the
vector store) and query embeddings (computed at retrieval time) live
in compatible but optimised subspaces:

- ``RETRIEVAL_DOCUMENT`` for ingestion (stored in ChromaDB).
- ``RETRIEVAL_QUERY`` for retriever queries.

Retry policy: 3 attempts with exponential backoff (1s, 4s, 16s) on
quota / availability errors raised by Vertex AI. Permanent errors
(invalid argument, permission denied) propagate immediately.
"""
from __future__ import annotations

import time

import structlog
import vertexai
from google.api_core.exceptions import (
    DeadlineExceeded,
    ResourceExhausted,
    ServiceUnavailable,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

logger = structlog.get_logger(__name__)

# Errors that warrant retry. Permission and invalid-argument errors
# are NOT retryable: retrying would just hit the same wall.
_RETRYABLE_EXCEPTIONS = (ResourceExhausted, ServiceUnavailable, DeadlineExceeded)


class VertexAIEmbeddings:
    """Vertex AI wrapper for ``gemini-embedding-001``.

    The class is intentionally thin: no caching, no rate limiting.
    Rate limiting lives in a separate ``VertexAILimitedClient`` (added
    in Phase 5.4) so it can be shared with the LLM client.
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
        vertexai.init(project=project_id, location=location)
        self._model = TextEmbeddingModel.from_pretrained(model_name)
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
        embeddings = self._model.get_embeddings(
            [TextEmbeddingInput(text, task_type)],
            output_dimensionality=self._output_dim,
        )
        latency_ms = int((time.time() - started) * 1000)

        if not embeddings:
            raise RuntimeError("Vertex AI returned no embeddings")

        values = list(embeddings[0].values)
        if len(values) != self._output_dim:
            raise RuntimeError(
                f"Vertex AI returned embedding of dimension {len(values)}, "
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
