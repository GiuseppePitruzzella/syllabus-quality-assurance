"""Backend-neutral LLM contract, without SDK imports or application settings."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


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
        metadata: Backend-specific data suitable for ``execution_metadata``
            of ``AgentOutput``. Cloud identifiers are only present for
            cloud backends; local results record their runtime and digest.
    """

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


# === protocol ===============================================================


class LLMClient(Protocol):
    """Minimum surface that ``BaseAgent`` needs.

    Any callable returning an object with a ``.text`` attribute satisfies
    this. Cloud and local implementations share these types without
    importing each other's SDKs or configuration.
    """

    def __call__(
        self,
        prompt: str,
        *,
        seed: int | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResult: ...
