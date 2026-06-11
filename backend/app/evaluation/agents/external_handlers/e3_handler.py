"""E3 handler — Coerenza con Regolamento didattico."""
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
from app.evaluation.agents.external_prompts.e3_prompt import (
    E3_PROMPT_VERSION,
    build_e3_prompt,
)
from app.evaluation.agents.external_schemas import ExtendedCriterionCode
from app.evaluation.rag.external_retriever import ExternalDocumentRetriever

# E3 focuses on programmatic / administrative coherence: CFU,
# contents, prerequisites and assessment.
E3_SYLLABUS_FIELDS: tuple[str, ...] = (
    "course_name",
    "course_code",
    "academic_year",
    "year_of_study",
    "credits",
    "prerequisites_it",
    "course_content_it",
    "assessment_methods_it",
    "teaching_methods_it",
)


class E3Handler(ExternalHandler):
    """Single-document handler for Regolamento didattico coherence."""

    criterion_code: ClassVar[ExtendedCriterionCode] = "E3"
    prompt_version: ClassVar[str] = E3_PROMPT_VERSION

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
                f"E3 requires exactly one resolved document; got {len(document_ids)}",
            )
        document_id = document_ids[0]
        started = time.time()
        syllabus_fields = _select_fields(syllabus, E3_SYLLABUS_FIELDS)
        query = _query_from_admin_fields(syllabus_fields)
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
        prompt = build_e3_prompt(
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


def _query_from_admin_fields(fields: dict[str, Any]) -> str:
    """Build a retrieval query that nudges Chroma toward sections
    of the Regolamento about CFU, contents, prerequisites and verifica.
    """
    parts = [
        str(fields.get("course_name") or ""),
        f"CFU {fields.get('credits') or ''}".strip(),
        str(fields.get("prerequisites_it") or ""),
        str(fields.get("assessment_methods_it") or ""),
    ]
    query = " | ".join(p for p in parts if p.strip() and p != "CFU")
    return query.strip() or "regolamento didattico CFU prerequisiti modalità di verifica"


__all__ = ["E3Handler", "E3_SYLLABUS_FIELDS"]
