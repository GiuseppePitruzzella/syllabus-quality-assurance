"""E2 handler — Allineamento con Matrice di Tuning."""
from __future__ import annotations

import time
from typing import Any, ClassVar

from app.evaluation.agents.external_handlers.base import (
    ExternalHandler,
    ExternalHandlerError,
    HandlerResult,
)
from app.evaluation.agents.external_handlers.e1_handler import (
    _chunk_payload,
    _select_fields,
    _to_chunk_ref,
)
from app.evaluation.agents.external_prompts.e2_prompt import (
    E2_PROMPT_VERSION,
    build_e2_prompt,
)
from app.evaluation.agents.external_schemas import ExtendedCriterionCode
from app.evaluation.rag.external_retriever import ExternalDocumentRetriever

# E2 reads competence-level outcomes; same field set as E1 — the
# matrix-side comparison is about competences attributed to the
# insegnamento, mirroring outcomes alignment.
E2_SYLLABUS_FIELDS: tuple[str, ...] = (
    "course_name",
    "learning_outcomes_it",
    "dublin_knowledge_it",
    "dublin_applying_it",
    "dublin_judgement_it",
    "dublin_communication_it",
    "dublin_learning_it",
)


class E2Handler(ExternalHandler):
    """Single-document handler for Matrice di Tuning alignment."""

    criterion_code: ClassVar[ExtendedCriterionCode] = "E2"
    prompt_version: ClassVar[str] = E2_PROMPT_VERSION

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
                f"E2 requires exactly one resolved document; got {len(document_ids)}",
            )
        document_id = document_ids[0]
        started = time.time()
        syllabus_fields = _select_fields(syllabus, E2_SYLLABUS_FIELDS)
        # Build query around outcomes — the matrix lists competences
        # attributable to each insegnamento.
        course = str(syllabus_fields.get("course_name") or "")
        outcomes = str(syllabus_fields.get("learning_outcomes_it") or "")
        query = f"{course} | {outcomes}".strip(" |") or "competenze attese"
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
        prompt = build_e2_prompt(
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


__all__ = ["E2Handler", "E2_SYLLABUS_FIELDS"]
