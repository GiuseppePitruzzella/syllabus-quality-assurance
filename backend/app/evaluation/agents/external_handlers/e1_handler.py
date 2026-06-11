"""E1 handler — Allineamento con SUA-CdS."""
from __future__ import annotations

import time
from typing import Any, ClassVar

from app.evaluation.agents.external_handlers.base import (
    ExternalHandler,
    ExternalHandlerError,
    HandlerResult,
)
from app.evaluation.agents.external_prompts.e1_prompt import (
    E1_PROMPT_VERSION,
    build_e1_prompt,
)
from app.evaluation.agents.external_schemas import (
    ExtendedCriterionCode,
    ExtendedRetrievedChunkRef,
)
from app.evaluation.rag.external_retriever import ExternalDocumentRetriever

# Syllabus fields relevant to E1: the outcomes (RA + Dublin descriptors)
# are the core comparison target with the SUA-CdS quadri A4.b.2 / A4.c.
# Course identity is added to give the LLM a stable handle on the
# insegnamento being judged.
E1_SYLLABUS_FIELDS: tuple[str, ...] = (
    "course_name",
    "learning_outcomes_it",
    "dublin_knowledge_it",
    "dublin_applying_it",
    "dublin_judgement_it",
    "dublin_communication_it",
    "dublin_learning_it",
)


class E1Handler(ExternalHandler):
    """Single-document handler for SUA-CdS alignment."""

    criterion_code: ClassVar[ExtendedCriterionCode] = "E1"
    prompt_version: ClassVar[str] = E1_PROMPT_VERSION

    def __init__(
        self,
        llm_client: Any,
        external_retriever: ExternalDocumentRetriever,
    ) -> None:
        super().__init__(llm_client)
        self.external_retriever = external_retriever

    def evaluate(
        self,
        *,
        syllabus: Any,
        cdl_id: int,
        document_ids: list[int],
    ) -> HandlerResult:
        if len(document_ids) != 1:
            raise ExternalHandlerError(
                self.criterion_code,
                f"E1 requires exactly one resolved document; got {len(document_ids)}",
            )
        document_id = document_ids[0]
        started = time.time()
        syllabus_fields = _select_fields(syllabus, E1_SYLLABUS_FIELDS)
        query = _query_from_outcomes(syllabus_fields)
        try:
            chunks = self.external_retriever.retrieve_for(
                criterion=self.criterion_code,
                cdl_id=cdl_id,
                local_document_id=document_id,
                query=query,
            )
        except Exception as exc:
            raise ExternalHandlerError(
                self.criterion_code,
                f"retrieval failed: {exc}",
                original=exc,
            ) from exc
        chunks_payload = [_chunk_payload(c) for c in chunks]
        prompt = build_e1_prompt(
            syllabus_data=syllabus_fields,
            external_chunks=chunks_payload,
            document_id=document_id,
        )
        judgment = self._call_llm_with_retry(prompt)
        chunk_refs = [_to_chunk_ref(c, self.criterion_code) for c in chunks]
        return HandlerResult(
            judgment=judgment,
            retrieved_chunks=chunk_refs,
            prompt_version=self.prompt_version,
            retry_count=self._last_retry_count,
            execution_metadata=self._execution_metadata_base(started=started)
            | {"retrieved_chunks_count": len(chunks)},
        )


def _select_fields(syllabus: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in fields:
        if isinstance(syllabus, dict):
            out[f] = syllabus.get(f)
        else:
            out[f] = getattr(syllabus, f, None)
    return out


def _query_from_outcomes(fields: dict[str, Any]) -> str:
    parts = [str(fields.get(k) or "") for k in (
        "course_name", "learning_outcomes_it",
        "dublin_knowledge_it", "dublin_applying_it",
    )]
    query = " | ".join(p for p in parts if p.strip())
    return query.strip() or "risultati di apprendimento"


def _chunk_payload(chunk: Any) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "text": chunk.text,
        "metadata": dict(chunk.metadata),
        "similarity_score": chunk.similarity_score,
    }


def _to_chunk_ref(chunk: Any, criterion: ExtendedCriterionCode) -> ExtendedRetrievedChunkRef:
    return ExtendedRetrievedChunkRef(
        criterion_code=criterion,
        chunk_id=chunk.chunk_id,
        local_document_id=chunk.local_document_id,
        document_type=chunk.document_type,
        document_version=chunk.document_version,
        similarity_score=chunk.similarity_score,
    )


__all__ = ["E1Handler", "E1_SYLLABUS_FIELDS"]
