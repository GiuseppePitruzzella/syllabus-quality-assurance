"""Base for the per-criterion handlers of the A5 ExternalConsistencyAgent.

Handlers share a common retry / parse / LLM-call pipeline but each
concrete handler owns its own retrieval shape (single doc, no doc,
multi-doc) and prompt builder. The base class intentionally does
NOT mandate a retriever — E4 doesn't use one — and does not
mandate ``document_ids`` to be a single element either, since E5
takes a list.

Handlers RAISE :class:`ExternalHandlerError` for unrecoverable
errors (retry exhaustion, retrieval failure, pre-LLM validation
failure). The A5 coordinator catches the exception, records the
message in ``ExtendedAgentOutput.handler_errors`` and emits a
technical-NA :class:`ExtendedCriterionJudgment` for the criterion.
Centralising the technical-NA construction in the coordinator
keeps handlers single-responsibility (produce a *good* judgment
or signal failure) and makes the dual-source / paired-prefix
rules unambiguous in the handler path.
"""
from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import ValidationError

from app.evaluation.agents.external_schemas import (
    ExtendedCriterionCode,
    ExtendedCriterionJudgment,
    ExtendedRetrievedChunkRef,
)


@dataclass(frozen=True)
class HandlerResult:
    """What a successful handler returns to the coordinator.

    The coordinator decides whether to drop the chunks into
    :attr:`ExtendedAgentOutput.retrieved_chunks` and the prompt
    version into :attr:`ExtendedAgentOutput.handler_prompt_versions`.
    """

    judgment: ExtendedCriterionJudgment
    retrieved_chunks: list[ExtendedRetrievedChunkRef]
    prompt_version: str
    retry_count: int = 0
    execution_metadata: dict[str, Any] = field(default_factory=dict)


class ExternalHandlerError(Exception):
    """Raised by a handler when it cannot produce a valid judgment.

    The coordinator catches this, records the message and produces
    a technical-NA judgment on behalf of the criterion. The
    original exception (if any) is preserved on ``original``.
    """

    def __init__(
        self,
        criterion_code: ExtendedCriterionCode,
        message: str,
        *,
        original: Exception | None = None,
        retry_count: int = 0,
    ) -> None:
        super().__init__(message)
        self.criterion_code = criterion_code
        self.original = original
        self.retry_count = retry_count


class ExternalHandler(ABC):
    """Base class for E1..E5 handlers.

    Concrete handlers must declare their ``criterion_code`` and
    ``prompt_version`` as class attributes and implement
    :meth:`evaluate`. The base provides the retry / parse / LLM
    plumbing as instance methods (``_call_llm_with_retry``,
    ``_parse_judgment``, ``_invoke_llm``) which handlers call from
    their ``evaluate``.
    """

    criterion_code: ClassVar[ExtendedCriterionCode]
    prompt_version: ClassVar[str]
    max_retries: ClassVar[int] = 2  # 3 attempts total

    def __init__(self, llm_client: Any) -> None:
        self.llm_client = llm_client
        self._last_retry_count = 0
        self._last_llm_metadata: dict[str, Any] = {}

    # ---- public API ----

    @abstractmethod
    def evaluate(
        self,
        *,
        syllabus: Any,
        cdl_id: int,
        document_ids: list[int],
    ) -> HandlerResult:
        """Run retrieval, prompt, LLM call and return the judgment.

        Args:
            syllabus: The syllabus ORM object (or a duck-typed proxy
                exposing the same attribute names).
            cdl_id: The Corso di Studio id; for E1/E2/E3/E5 it
                drives the retrieval filter; E4 ignores it.
            document_ids: Resolved local-document ids for this
                criterion. E1/E2/E3 always pass a single id; E5
                passes one or more; E4 ignores it (handler reads
                the syllabus itself).
        """

    # ---- shared retry / parse pipeline ----

    def _call_llm_with_retry(self, prompt: str) -> ExtendedCriterionJudgment:
        """Invoke the LLM, validate the parsed judgment, retry on failure.

        Raises :class:`ExternalHandlerError` after exhausting all
        attempts. Mirrors the core :class:`BaseAgent` behaviour so
        retry messages remain consistent across the system.
        """
        last_error: Exception | None = None
        self._last_retry_count = 0
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            try:
                raw = self._invoke_llm(
                    prompt if attempt == 0 else self._retry_prompt(prompt, last_error),
                )
                judgment = self._parse_judgment(raw)
                self._last_retry_count = attempt
                return judgment
            except (ValueError, ValidationError, json.JSONDecodeError) as exc:
                last_error = exc
        raise ExternalHandlerError(
            self.criterion_code,
            f"LLM output did not match schema after {attempts} attempts: {last_error}",
            original=last_error,
            retry_count=attempts,
        )

    def _parse_judgment(self, raw: str) -> ExtendedCriterionJudgment:
        """Parse the LLM response into a validated judgment.

        Accepts both ``{"judgment": {...}}`` and the bare ``{...}``
        shape, since the LLM tends to omit the outer key under
        time pressure. Empty evidences are dropped pre-validation
        (same drift the core agents see — see ``base.py`` comment).
        """
        text = _strip_json_fence(raw)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM output is not valid JSON: {exc}") from exc
        if isinstance(payload, dict) and "judgment" in payload:
            judgment_payload = payload["judgment"]
        elif isinstance(payload, dict):
            judgment_payload = payload
        else:
            raise ValueError("LLM output must be a JSON object")
        if not isinstance(judgment_payload, dict):
            raise ValueError("LLM output 'judgment' must be a JSON object")
        judgment_payload = _drop_empty_evidences(judgment_payload)
        judgment = ExtendedCriterionJudgment.model_validate(judgment_payload)
        if judgment.criterion_code != self.criterion_code:
            raise ValueError(
                f"judgment criterion_code mismatch: expected "
                f"{self.criterion_code}, got {judgment.criterion_code}",
            )
        return judgment

    def _invoke_llm(self, prompt: str) -> str:
        """Duck-typed LLM invocation, identical contract to BaseAgent."""
        client = self.llm_client
        if callable(client):
            result = client(prompt)
        elif hasattr(client, "generate"):
            result = client.generate(prompt)
        elif hasattr(client, "invoke"):
            result = client.invoke(prompt)
        else:
            raise TypeError(
                "llm_client must be callable or expose generate()/invoke()",
            )
        metadata = getattr(result, "metadata", None)
        self._last_llm_metadata = dict(metadata) if isinstance(metadata, dict) else {}
        if isinstance(result, str):
            return result
        if hasattr(result, "text"):
            return str(result.text)
        if hasattr(result, "content"):
            return str(result.content)
        return str(result)

    def _retry_prompt(self, prompt: str, error: Exception | None) -> str:
        return (
            f"{prompt}\n\nATTENZIONE: la risposta precedente non rispettava "
            "lo schema JSON richiesto. Rispondi di nuovo esclusivamente con "
            f"JSON valido. Errore di validazione: {error}"
        )

    # ---- shared helpers for concrete handlers ----

    def _execution_metadata_base(self, *, started: float) -> dict[str, Any]:
        return {
            "latency_ms": int((time.time() - started) * 1000),
            "retry_count": self._last_retry_count,
            "prompt_version": self.prompt_version,
            "criterion_code": self.criterion_code,
            "llm_metadata": dict(self._last_llm_metadata),
        }


# ---------------------------------------------------------------------------
# Shared parsing helpers (kept module-local; not part of the public API)
# ---------------------------------------------------------------------------


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _drop_empty_evidences(judgment: dict) -> dict:
    """Drop ``evidences[i]`` entries whose ``text`` is empty/whitespace."""
    if not isinstance(judgment, dict):
        return judgment
    evidences = judgment.get("evidences")
    if not isinstance(evidences, list):
        return judgment
    cleaned = [
        ev
        for ev in evidences
        if isinstance(ev, dict)
        and isinstance(ev.get("text"), str)
        and ev["text"].strip() != ""
    ]
    if len(cleaned) == len(evidences):
        return judgment
    return {**judgment, "evidences": cleaned}


__all__ = [
    "ExternalHandler",
    "ExternalHandlerError",
    "HandlerResult",
]
