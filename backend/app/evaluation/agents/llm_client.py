"""Gen AI SDK LLM client for the evaluation agents.

Migrated to ``google-genai`` (Vertex AI backend) from the deprecated
``vertexai.generative_models.GenerativeModel``, which is removed on
2026-06-24. The public surface of :class:`VertexAILLMClient` is
unchanged by design — the migration is infrastructural, not a
functional change. ``BaseAgent`` consumes the result via
``hasattr(result, "text")`` and the typed ``LLMResult.metadata``
dict, both untouched.

Preserved invariants:

- Typed errors mapped from the response ``FinishReason`` (safety
  block -> NA technical; truncated output -> retry once with a
  hint; transient failure -> retried with exponential backoff).
- Rich metadata for ``execution_metadata`` of ``AgentOutput`` (model
  name, project id, location, temperature, max_output_tokens,
  finish reason, prompt/response sizes, latency).
- No fallback on ``gcloud config`` for the GCP project id (D027).
- Retry policy: 3 attempts, exponential backoff (1s, 4s, 16s) on
  ``ResourceExhausted`` / ``ServiceUnavailable`` /
  ``DeadlineExceeded`` (legacy backend exceptions) and on the new
  SDK's ``google.genai.errors.ServerError`` family.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

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

from app.config import ScientificConfig

logger = structlog.get_logger(__name__)


def _is_retryable_error(exc: BaseException) -> bool:
    """Decide which exceptions deserve a back-off retry.

    Mirrors the embeddings client policy (see
    ``app/evaluation/rag/embeddings.py::_is_retryable_error``):

    - ``ServerError`` (5xx from the Gen AI SDK) -> retry.
    - ``ClientError`` -> retry ONLY when the HTTP code is 429
      (rate limit). The new SDK surfaces quota / rate-limit as
      ``ClientError(code=429)``, so without this check a real 429
      would NOT be retried.
    - Legacy ``google.api_core`` quota / availability exceptions
      are still propagated by the Vertex backend in many cases,
      so they remain retryable as a defensive fallback.
    """
    if isinstance(exc, (ResourceExhausted, ServiceUnavailable, DeadlineExceeded)):
        return True
    if isinstance(exc, genai_errors.ServerError):
        return True
    if isinstance(exc, genai_errors.ClientError):
        return getattr(exc, "code", None) == 429
    return False

# Finish-reason buckets. ``STOP`` is the only success state.
# ``MAX_TOKENS`` means the JSON likely got truncated; the agent layer
# handles it as a parsing failure (see BaseAgent retry loop). All
# other reasons either block on safety or signal a model malfunction.
_FINISH_OK = {"STOP"}
_FINISH_TRUNCATED = {"MAX_TOKENS"}
_FINISH_SAFETY = {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "RECITATION"}


# === typed errors ===========================================================


class LLMError(RuntimeError):
    """Base class for LLM client errors."""


class LLMSafetyBlockedError(LLMError):
    """Raised when the response or prompt is blocked by Vertex safety filters.

    Per the Phase 5 spec, the agent layer must record the affected
    criteria as NA with reason ``"blocked by safety filter"`` and NOT
    retry. The truth-value of this error is the block reason name
    (e.g. ``"SAFETY"``, ``"PROHIBITED_CONTENT"``).
    """

    def __init__(self, reason: str, *, prompt_blocked: bool = False) -> None:
        super().__init__(
            ("prompt blocked by safety filter: " if prompt_blocked else "response blocked by safety filter: ")
            + reason
        )
        self.reason = reason
        self.prompt_blocked = prompt_blocked


class LLMResponseTruncatedError(LLMError):
    """Raised when the model hit ``max_output_tokens`` before finishing.

    The agent layer can retry once with a smaller payload or with a more
    aggressive 'be concise' instruction. Not retried inside the client.
    """


class LLMEmptyResponseError(LLMError):
    """Raised when the model returns no usable text (no candidates,
    OTHER finish reason, model armor, malformed function call)."""


# === result type ============================================================


@dataclass(frozen=True)
class LLMResult:
    """One generation result with its metadata.

    Attributes:
        text: Plain text returned by the model. The agent passes this
            into :meth:`BaseAgent._parse_response`.
        metadata: Dict suitable for ``execution_metadata`` of
            ``AgentOutput``. Always contains: ``model``, ``gcp_project_id``,
            ``gcp_location``, ``temperature``, ``max_output_tokens``,
            ``finish_reason``, ``prompt_chars``, ``response_chars``,
            ``latency_ms``. May contain ``seed``.
    """

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


# === protocol ===============================================================


class LLMClient(Protocol):
    """Minimum surface that ``BaseAgent`` needs.

    Any callable returning an object with a ``.text`` attribute satisfies
    this. ``VertexAILLMClient`` is the production implementation; tests
    use a ``MagicMock`` that returns ``LLMResult``.
    """

    def __call__(
        self,
        prompt: str,
        *,
        seed: int | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResult: ...


# === Vertex AI implementation ===============================================


class VertexAILLMClient:
    """Generate text with the Gen AI SDK (Vertex AI backend).

    Public surface (constructor signature, ``__call__``, ``model_name``,
    ``project_id``) matches the pre-migration class exactly. Callers
    do not need to change.
    """

    def __init__(
        self,
        project_id: str,
        location: str,
        scientific: ScientificConfig,
    ) -> None:
        if not project_id:
            raise ValueError(
                "project_id is required (set GCP_PROJECT_ID in backend/.env "
                "and call Settings.require_vertex_ai_config()). No fallback "
                "to `gcloud config` per D027."
            )
        # Pin the stable API surface (``v1``). Without this, the
        # client may target beta endpoints, which can shift the
        # generation contract (finish-reason set, prompt_feedback
        # shape) between runs and hurt the reproducibility
        # guarantees of the EvaluationResult.
        self._client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
            http_options=genai_types.HttpOptions(api_version="v1"),
        )
        self._project_id = project_id
        self._location = location
        self._scientific = scientific
        self._model_name = scientific.llm_model

    # ---- public API ----

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def project_id(self) -> str:
        return self._project_id

    def _backend_metadata(self) -> dict[str, Any]:
        """Backend-specific metadata merged into every LLMResult.

        Overridden by GeminiApiLLMClient (Developer API) which has no
        GCP project/location.
        """
        return {
            "backend": "vertex",
            "gcp_project_id": self._project_id,
            "gcp_location": self._location,
        }

    def __call__(
        self,
        prompt: str,
        *,
        seed: int | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResult:
        """Generate a response.

        ``max_output_tokens`` overrides ``ScientificConfig.llm_max_output_tokens``
        for this single call (D030.bis: per-agent runtime override; e.g. A1
        needs 16384 on long syllabi to avoid MAX_TOKENS truncation). When
        ``None`` the scientific default is used and behaviour is unchanged.
        """
        return self._call(prompt, seed, max_output_tokens)

    # ---- internals ----

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        retry=retry_if_exception(_is_retryable_error),
        reraise=True,
    )
    def _call(
        self,
        prompt: str,
        seed: int | None,
        max_output_tokens: int | None = None,
    ) -> LLMResult:
        if not prompt or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")

        effective_max_output_tokens = (
            max_output_tokens
            if max_output_tokens is not None
            else self._scientific.llm_max_output_tokens
        )
        config = genai_types.GenerateContentConfig(
            temperature=self._scientific.llm_temperature,
            max_output_tokens=effective_max_output_tokens,
            seed=seed,
        )

        started = time.time()
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=config,
        )
        latency_ms = int((time.time() - started) * 1000)

        finish_reason_name = _finish_reason_name(response)
        _raise_for_finish(response, finish_reason_name)

        text = _safe_extract_text(response)

        metadata: dict[str, Any] = {
            "model": self._model_name,
            **self._backend_metadata(),
            "temperature": self._scientific.llm_temperature,
            "max_output_tokens": effective_max_output_tokens,
            "finish_reason": finish_reason_name,
            "prompt_chars": len(prompt),
            "response_chars": len(text),
            "latency_ms": latency_ms,
        }
        if seed is not None:
            metadata["seed"] = seed

        logger.info(
            "llm_completed",
            model=self._model_name,
            finish_reason=finish_reason_name,
            prompt_chars=len(prompt),
            response_chars=len(text),
            latency_ms=latency_ms,
        )
        return LLMResult(text=text, metadata=metadata)


# === helpers (module-level so they're testable in isolation) ================


def _finish_reason_name(response: Any) -> str:
    """Return the ``FinishReason`` name of the first candidate, or 'NO_CANDIDATES'."""
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return "NO_CANDIDATES"
    candidate = candidates[0]
    finish_reason = getattr(candidate, "finish_reason", None)
    if finish_reason is None:
        return "UNKNOWN"
    return getattr(finish_reason, "name", str(finish_reason))


def _raise_for_finish(response: Any, finish_reason_name: str) -> None:
    """Translate non-OK finish reasons into typed errors."""
    if finish_reason_name in _FINISH_OK:
        return

    if finish_reason_name == "NO_CANDIDATES":
        # Prompt was blocked before any candidate was produced.
        block_reason = _prompt_block_reason(response)
        if block_reason:
            raise LLMSafetyBlockedError(block_reason, prompt_blocked=True)
        raise LLMEmptyResponseError("no candidates returned")

    if finish_reason_name in _FINISH_SAFETY:
        raise LLMSafetyBlockedError(finish_reason_name)

    if finish_reason_name in _FINISH_TRUNCATED:
        raise LLMResponseTruncatedError(
            f"response truncated at max_output_tokens (finish_reason={finish_reason_name})"
        )

    raise LLMEmptyResponseError(f"unusable finish_reason={finish_reason_name}")


def _prompt_block_reason(response: Any) -> str | None:
    """Read the prompt-level block reason name, if any."""
    feedback = getattr(response, "prompt_feedback", None)
    if feedback is None:
        return None
    block_reason = getattr(feedback, "block_reason", None)
    if block_reason is None:
        return None
    return getattr(block_reason, "name", str(block_reason))


def _safe_extract_text(response: Any) -> str:
    """Read ``response.text`` defensively.

    The Gen AI SDK's accessor raises if the response has no candidates
    or if the candidate has no usable text part. We've already
    validated ``finish_reason`` upstream, so most failures here are
    surfaced as ``LLMEmptyResponseError``.
    """
    try:
        text = response.text
    except Exception as exc:  # noqa: BLE001 — SDK raises various exception types
        raise LLMEmptyResponseError(f"could not extract text: {exc}") from exc
    if not isinstance(text, str):
        raise LLMEmptyResponseError(f"text is not a string: {type(text).__name__}")
    return text


# === Gemini Developer API (AI Studio) implementation ========================


class GeminiApiLLMClient(VertexAILLMClient):
    """LLM client on the Gemini Developer API (AI Studio) free tier (D080).

    Reuses every VertexAILLMClient behaviour (retry policy, finish-reason
    handling, text extraction, per-call ``max_output_tokens`` override).
    Only two things differ: the client is built with an API key instead of
    ADC project/location, and the metadata records ``backend="ai_studio"``.

    ``api_version="v1"`` is pinned as on Vertex; the spike (2026-07-06)
    confirmed it honours ``seed`` at temp=0.1 and ``output_dimensionality``.
    """

    def __init__(self, api_key: str, scientific: ScientificConfig) -> None:
        if not api_key:
            raise ValueError(
                "api_key is required (set GEMINI_API_KEY in backend/.env)"
            )
        self._client = genai.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(api_version="v1"),
        )
        # No GCP project/location on the Developer API backend.
        self._project_id = ""
        self._location = ""
        self._scientific = scientific
        self._model_name = scientific.llm_model

    def _backend_metadata(self) -> dict[str, Any]:
        return {"backend": "ai_studio"}
