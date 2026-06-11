"""Persisted result of one multi-agent syllabus evaluation run.

Schema designed for Phase 5.4.H per the spec in Appendix C of the
plan, plus the additions agreed in the 5.4.H design checkpoint:
``duration_ms``, ``syllabus_seuid_snapshot``, ``course_name_snapshot``.

The relationship name on the Syllabus side is ``evaluations`` (an
existing convention in the codebase), not ``evaluation_results``.

The table is rewritten (drop + recreate) at startup in ``app.main``
when the live SQLite DB carries the old stub schema. No Alembic for
this prototype (D020 + scope tesi).
"""
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EvaluationResult(Base):
    """One evaluation run on a single syllabus.

    A syllabus can have many ``EvaluationResult`` rows (history,
    decision D038). Each row captures: the rubric scores, the report,
    the full per-agent output, the retrieved RAG chunks, AND the
    scientific configuration of the run (model versions, RAG params,
    GCP project ID per D027) so that any record is independently
    reproducible.
    """

    __tablename__ = "evaluation_results"

    # === Identifiers ==================================================
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evaluation_uuid: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, index=True
    )
    syllabus_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("syllabi.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # === Syllabus identity snapshot (audit-friendly, survives renames) ==
    syllabus_seuid_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    course_name_snapshot: Mapped[str] = mapped_column(Text, nullable=False)

    # === Run lifecycle ================================================
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="pending", index=True
    )
    # "pending" | "running" | "completed" | "partial" | "failed"
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # === Scientific configuration (D025 + D026 + D027 + D030) =========
    llm_model: Mapped[str] = mapped_column(String, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String, nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    llm_temperature: Mapped[float] = mapped_column(Float, nullable=False)
    llm_max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    rag_top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    rag_final_k: Mapped[int] = mapped_column(Integer, nullable=False)
    rag_similarity_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    gcp_project_id: Mapped[str] = mapped_column(String, nullable=False)
    gcp_location: Mapped[str] = mapped_column(String, nullable=False)
    # Per-agent prompt version, e.g. {"A1": "a1_v4", "A2": "a2_v1", ...}
    prompt_versions: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    # === Aggregated rubric output =====================================
    core_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    coverage: Mapped[float | None] = mapped_column(Float, nullable=True)

    # === Structured per-criterion / per-agent output ==================
    # {"C1": 2, "C2": null, "C3": 2, ...}
    criterion_scores: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # [{"criterion_code": "C2", "reason": "...", "source": "agent"}, ...]
    na_criteria: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    # {"A1": <AgentOutput dump>, "A2": ..., "A3": ..., "A4": ...}
    agent_outputs: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # {"A2": "LLMSafetyBlockedError: SAFETY", ...}
    agent_errors: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # {"C1": [{"chunk_id": "...", "document_id": "...", "section_ref": "...",
    #          "similarity_score": 0.79}, ...], ...}
    retrieved_chunks: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # === Extended criteria (A5 ExternalConsistencyAgent — Phase 9.C.5.3) ===
    # Persisted alongside but STRICTLY SEPARATE from the core
    # ``core_score`` / ``coverage`` / ``criterion_scores`` /
    # ``na_criteria`` fields. A failed or skipped A5 path NEVER
    # changes ``status``, ``core_score`` or any other core field —
    # the run can ship its C1-C9 ``completed`` status with this
    # column carrying ``{"status": "failed", ...}``.
    #
    # Shape::
    #
    #     {
    #         "criterion_scores": {"E1": int|null, ... "E5": int|null},
    #         "na_criteria":     [{"criterion_code": "E2",
    #                              "source": "resolver",
    #                              "reason": "..."}, ...],
    #         "handler_errors":  {"E2": "...", ...},
    #         "status":          "completed" | "partial" | "failed",
    #         "agent_output":    <ExtendedAgentOutput.model_dump()>
    #     }
    #
    # ``agent_output.handler_prompt_versions`` carries the per-E*
    # prompt versions actually used in this run (D026 traceability
    # symmetric to the core ``prompt_versions`` column).
    extended_criteria_result: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
    )

    # === Final user-facing report =====================================
    final_report: Mapped[str | None] = mapped_column(Text, nullable=True)

    # === Relationship =================================================
    syllabus = relationship("Syllabus", back_populates="evaluations")
