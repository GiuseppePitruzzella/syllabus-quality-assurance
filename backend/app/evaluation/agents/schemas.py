"""Shared Pydantic schemas for evaluation agents."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class CriterionEvidence(BaseModel):
    """A literal syllabus quote used as evidence for one criterion judgment."""

    text: str = Field(..., min_length=1, description="Literal quoted fragment")
    source_field: str = Field(
        ...,
        min_length=1,
        description="Syllabus field name, e.g. 'prerequisites_it'",
    )


class CriterionJudgment(BaseModel):
    """Judgment for a single rubric criterion."""

    criterion_code: str = Field(..., pattern=r"^C[1-9]$")
    score: Literal[0, 1, 2] | None = None
    is_na: bool = False
    na_reason: str | None = None
    justification: str = Field(..., min_length=20)
    evidences: list[CriterionEvidence] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"]

    @model_validator(mode="after")
    def validate_score_na_consistency(self) -> "CriterionJudgment":
        """Keep NA semantically distinct from score 0."""
        if self.is_na:
            if self.score is not None:
                raise ValueError("score must be null when is_na=true")
            if not self.na_reason or not self.na_reason.strip():
                raise ValueError("na_reason is required when is_na=true")
            return self
        if self.score is None:
            raise ValueError("score is required when is_na=false")
        return self


class AgentInput(BaseModel):
    """Standardized input passed to an evaluation agent prompt builder."""

    syllabus_data: dict[str, Any]
    criteria_specs: list[dict[str, Any]]
    normative_context: list[dict[str, Any]]
    syllabus_seuid: str = Field(..., min_length=1)


class AgentOutput(BaseModel):
    """Standardized output returned by each evaluation agent."""

    agent_code: str = Field(..., pattern=r"^A[1-4]$")
    judgments: list[CriterionJudgment]
    execution_metadata: dict[str, Any] = Field(default_factory=dict)
