"""Abstract base class for rubric evaluation agents."""
from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from app.evaluation.agents.schemas import (
    AgentInput,
    AgentOutput,
    CriterionJudgment,
    RetrievedChunkRef,
)
from app.evaluation.rag.query_builder import CRITERION_DESCRIPTIONS, build_retrieval_query

PromptBuilder = Callable[[AgentInput], str]


class BaseAgent(ABC):
    """Base pipeline shared by A1-A4 agents.

    Concrete agents define their code, owned criteria, syllabus-field selection,
    and prompt builder. The LLM client is intentionally duck-typed so Phase 5.3
    can test prompt/parsing behavior before locking a Vertex AI wrapper.
    """

    agent_code: str
    criteria_codes: list[str]
    prompt_version = "v1"

    def __init__(
        self,
        retriever: Any,
        llm_client: Any,
        prompt_builder: PromptBuilder,
    ) -> None:
        self.retriever = retriever
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder
        self._last_retry_count = 0

    @abstractmethod
    def get_relevant_syllabus_fields(self, syllabus: Any) -> dict[str, Any]:
        """Extract syllabus fields relevant to this agent."""

    def evaluate(self, syllabus: Any) -> AgentOutput:
        """Run extraction, retrieval, prompt construction, LLM call and parsing."""
        started = time.time()
        syllabus_fields = self.get_relevant_syllabus_fields(syllabus)
        syllabus_seuid = str(getattr(syllabus, "seuid", syllabus_fields.get("seuid", "unknown")))
        normative_context = self._retrieve_normative_context(syllabus_fields)
        agent_input = AgentInput(
            syllabus_data=syllabus_fields,
            criteria_specs=self._criteria_specs(),
            normative_context=normative_context,
            syllabus_seuid=syllabus_seuid,
        )
        prompt = self.prompt_builder(agent_input)
        raw = self._call_llm_with_retry(prompt)
        judgments = self._parse_response(raw)
        return AgentOutput(
            agent_code=self.agent_code,
            judgments=judgments,
            execution_metadata={
                "latency_ms": int((time.time() - started) * 1000),
                "retry_count": self._last_retry_count,
                "prompt_version": self.prompt_version,
                "criteria_codes": self.criteria_codes,
                "retrieved_chunks_count": len(normative_context),
            },
            retrieved_chunks=[
                _compact_chunk_ref(item) for item in normative_context
            ],
        )

    def _retrieve_normative_context(self, syllabus_fields: dict[str, Any]) -> list[dict[str, Any]]:
        contexts: list[dict[str, Any]] = []
        for criterion in self.criteria_codes:
            query = build_retrieval_query(
                criterion=criterion,
                agent=self.agent_code,
                syllabus_fields=syllabus_fields,
            )
            chunks = self.retriever.retrieve(
                query=query,
                criterion=criterion,
                agent=self.agent_code,
            )
            contexts.extend(self._chunk_to_context(criterion, chunk) for chunk in chunks)
        return contexts

    def _criteria_specs(self) -> list[dict[str, str]]:
        return [
            {
                "criterion_code": criterion,
                "description": CRITERION_DESCRIPTIONS[criterion],
            }
            for criterion in self.criteria_codes
        ]

    def _call_llm_with_retry(self, prompt: str, max_retries: int = 2) -> str:
        """Call the LLM and retry when the JSON output does not validate."""
        last_error: Exception | None = None
        self._last_retry_count = 0
        for attempt in range(max_retries + 1):
            raw = self._invoke_llm(prompt if attempt == 0 else self._retry_prompt(prompt, last_error))
            try:
                self._parse_response(raw)
                self._last_retry_count = attempt
                return raw
            except (ValueError, ValidationError, json.JSONDecodeError) as exc:
                last_error = exc
        raise ValueError(f"LLM output did not match schema after {max_retries + 1} attempts") from last_error

    def _parse_response(self, raw: str) -> list[CriterionJudgment]:
        """Parse LLM JSON output into CriterionJudgment objects.

        Pre-processes the JSON before Pydantic validation to drop
        ``evidences`` items whose ``text`` is empty or whitespace-only.
        Empirically the LLM keeps emitting ``{"text": "", "source_field":
        "X_en"}`` to signal an absent field even when the prompt
        explicitly forbids it; rather than burn three retries on the
        same error, we drop the offending entries here. The schema
        remains semantically tight (an empty quote is not evidence) and
        the dropped entries are a no-op for the downstream agent
        (justification carries the absence-of-content information).
        """
        payload = json.loads(_strip_json_fence(raw))
        if isinstance(payload, dict):
            judgments_payload = payload.get("judgments")
        elif isinstance(payload, list):
            judgments_payload = payload
        else:
            raise ValueError("LLM output must be a JSON object or list")
        if not isinstance(judgments_payload, list):
            raise ValueError("LLM output must contain a judgments list")
        judgments_payload = [_drop_empty_evidences(item) for item in judgments_payload]
        judgments = [CriterionJudgment.model_validate(item) for item in judgments_payload]
        self._validate_criteria_coverage(judgments)
        return judgments

    def _validate_criteria_coverage(self, judgments: list[CriterionJudgment]) -> None:
        expected = set(self.criteria_codes)
        actual = [judgment.criterion_code for judgment in judgments]
        if len(actual) != len(expected) or set(actual) != expected:
            raise ValueError(f"expected judgments for {sorted(expected)}, got {sorted(actual)}")

    def _invoke_llm(self, prompt: str) -> str:
        client = self.llm_client
        if callable(client):
            result = client(prompt)
        elif hasattr(client, "generate"):
            result = client.generate(prompt)
        elif hasattr(client, "invoke"):
            result = client.invoke(prompt)
        else:
            raise TypeError("llm_client must be callable or expose generate()/invoke()")
        if isinstance(result, str):
            return result
        if hasattr(result, "text"):
            return str(result.text)
        if hasattr(result, "content"):
            return str(result.content)
        return str(result)

    def _retry_prompt(self, prompt: str, error: Exception | None) -> str:
        return (
            f"{prompt}\n\n"
            "ATTENZIONE: la risposta precedente non rispettava lo schema JSON richiesto. "
            "Rispondi di nuovo esclusivamente con JSON valido. "
            f"Errore di validazione: {error}"
        )

    def _chunk_to_context(self, criterion: str, chunk: Any) -> dict[str, Any]:
        metadata = dict(getattr(chunk, "metadata", {}) or {})
        return {
            "criterion_code": criterion,
            "chunk_id": getattr(chunk, "chunk_id"),
            "text": getattr(chunk, "text"),
            "metadata": metadata,
            "similarity_score": getattr(chunk, "similarity_score", None),
        }


def _compact_chunk_ref(item: dict[str, Any]) -> RetrievedChunkRef:
    """Turn a ``_retrieve_normative_context`` dict into a compact ref.

    ``item`` follows the shape produced by :meth:`BaseAgent._chunk_to_context`:
    ``{criterion_code, chunk_id, text, metadata, similarity_score}``. The
    full text is intentionally dropped — it lives in ChromaDB and is
    reproducible from ``chunk_id``.
    """
    metadata = item.get("metadata") or {}
    return RetrievedChunkRef(
        criterion_code=item.get("criterion_code", ""),
        chunk_id=item.get("chunk_id", ""),
        document_id=metadata.get("document_id"),
        section_ref=metadata.get("section_ref"),
        similarity_score=item.get("similarity_score"),
    )


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
    """Remove evidences whose text is empty or whitespace-only.

    Returns a new dict; the input is not mutated. If ``evidences`` is
    not a list (or is missing), the dict is returned unchanged so
    Pydantic can produce a clear validation error downstream.
    """
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
