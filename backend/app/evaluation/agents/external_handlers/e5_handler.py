"""E5 handler — Aderenza agli usi dipartimentali / di CdL.

E5 supports multiple resolved local documents (e.g. a department-
wide usage note PLUS a CdL-specific template). The handler issues
one retrieval call per resolved document and consolidates all
chunks into a single LLM call so the judgment can cite multiple
documents via the ``source_document_id`` field.
"""
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
from app.evaluation.agents.external_prompts.e5_prompt import (
    E5_PROMPT_VERSION,
    build_e5_prompt,
)
from app.evaluation.agents.external_schemas import ExtendedCriterionCode
from app.evaluation.rag.external_retriever import ExternalDocumentRetriever

# E5 has the widest field surface among the extended handlers
# because departmental / CdL usages can target any redazional
# convention: prerequisites, contents, references, assessment,
# attendance, schedule, ...
E5_SYLLABUS_FIELDS: tuple[str, ...] = (
    "course_name",
    "academic_year",
    "year_of_study",
    "learning_outcomes_it",
    "prerequisites_it",
    "course_content_it",
    "assessment_methods_it",
    "sample_questions_it",
    "teaching_methods_it",
    "attendance_it",
    "references_it",
    "schedule_it",
)


class E5Handler(ExternalHandler):
    """Multi-document handler for local-usage adherence."""

    criterion_code: ClassVar[ExtendedCriterionCode] = "E5"
    prompt_version: ClassVar[str] = E5_PROMPT_VERSION

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
        if not document_ids:
            raise ExternalHandlerError(
                self.criterion_code,
                "E5 requires at least one resolved document",
            )
        started = time.time()
        syllabus_fields = _select_fields(syllabus, E5_SYLLABUS_FIELDS)
        query = _query_from_local_focus(syllabus_fields)

        chunks_by_document: list[dict[str, Any]] = []
        chunk_refs = []
        for document_id in document_ids:
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
                    f"retrieval failed for document {document_id}: {exc}",
                    original=exc,
                ) from exc
            if not chunks:
                # The document is enabled for E5 but the filtered
                # retrieval returned no above-threshold chunks. We
                # keep an empty group rather than skip — the LLM
                # should see that the document was consulted but
                # has no applicable section.
                chunks_by_document.append({
                    "document_id": document_id,
                    "document_type": "unknown",
                    "chunks": [],
                })
                continue
            chunks_by_document.append({
                "document_id": document_id,
                "document_type": chunks[0].document_type,
                "chunks": [_chunk_payload(c) for c in chunks],
            })
            chunk_refs.extend(
                _to_chunk_ref(c, self.criterion_code) for c in chunks
            )

        prompt = build_e5_prompt(
            syllabus_data=syllabus_fields,
            external_chunks_by_document=chunks_by_document,
        )
        judgment = self._call_llm_with_retry(prompt)
        return HandlerResult(
            judgment=judgment,
            retrieved_chunks=chunk_refs,
            prompt_version=self.prompt_version,
            retry_count=self._last_retry_count,
            execution_metadata=self._execution_metadata_base(started=started)
            | {
                "document_count": len(document_ids),
                "retrieved_chunks_count": len(chunk_refs),
            },
        )


def _query_from_local_focus(fields: dict[str, Any]) -> str:
    """E5 retrieval query — broad surface, biased toward the
    redazional aspects local usages typically address."""
    parts = [
        str(fields.get("course_name") or ""),
        str(fields.get("prerequisites_it") or ""),
        str(fields.get("assessment_methods_it") or ""),
        str(fields.get("references_it") or ""),
    ]
    query = " | ".join(p for p in parts if p.strip())
    return query.strip() or "usi dipartimentali corso di studio"


__all__ = ["E5Handler", "E5_SYLLABUS_FIELDS"]
