"""HTTP response schemas for the evaluation endpoints (Phase 5.4.H.2)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EvaluationCreated(BaseModel):
    """Returned by ``POST /api/evaluate/{seuid}`` (status 202)."""

    evaluation_uuid: str


class EvaluationSummary(BaseModel):
    """Lightweight summary for history lists."""

    evaluation_uuid: str
    syllabus_seuid_snapshot: str
    course_name_snapshot: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    core_score: float | None = None
    coverage: float | None = None
    llm_model: str
    embedding_model: str
    prompt_versions: dict[str, Any]

    model_config = {"from_attributes": True}


class EvaluationDetail(EvaluationSummary):
    """Full payload — used by ``GET /api/evaluations/{evaluation_uuid}``."""

    embedding_dim: int
    llm_temperature: float
    llm_max_output_tokens: int
    rag_top_k: int
    rag_final_k: int
    rag_similarity_threshold: float
    gcp_project_id: str
    gcp_location: str

    error_message: str | None = None
    criterion_scores: dict[str, Any] | None = None
    na_criteria: list[Any] | None = None
    agent_outputs: dict[str, Any] | None = None
    agent_errors: dict[str, Any] | None = None
    retrieved_chunks: dict[str, Any] | None = None
    final_report: str | None = None
