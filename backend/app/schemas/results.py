"""Schemas for the cross-evaluation Results summary page.

Phase 12 deliberately separates this surface from the single-run
``EvaluationDetail`` endpoint. The payload answers a different
question: what is the current picture across the evaluated syllabi?

The aggregation rule is methodological, not just technical:
``GET /api/results/summary`` considers the latest terminal evaluation
for each syllabus. Repeated runs therefore do not inflate the
experimental picture, while failed runs are still counted in status
statistics and excluded from score averages/distributions.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field


CoreCriterionCode = Literal["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"]
TerminalEvaluationStatus = Literal["completed", "partial", "failed"]


class ResultsOverview(BaseModel):
    """High-level counters and averages for the latest terminal runs."""

    latest_evaluations_count: int
    terminal_runs_count: int
    completed_count: int
    partial_count: int
    failed_count: int
    average_core_score: float | None
    average_coverage: float | None
    total_critical_criteria: int
    total_improvable_criteria: int
    total_na_criteria: int


class CriterionDistribution(BaseModel):
    """Distribution for one C1-C9 criterion across scorable latest runs."""

    criterion_code: CoreCriterionCode
    score_0: int = 0
    score_1: int = 0
    score_2: int = 0
    na: int = 0

    @computed_field
    @property
    def evaluated(self) -> int:
        return self.score_0 + self.score_1 + self.score_2


class ResultsEvaluationRow(BaseModel):
    """Table row for one latest terminal evaluation per syllabus."""

    evaluation_uuid: str
    syllabus_seuid: str
    course_name: str
    cdl_name: str | None = None
    cdl_code: str | None = None
    department_name: str | None = None
    status: TerminalEvaluationStatus
    started_at: datetime
    finished_at: datetime | None = None
    core_score: float | None = None
    coverage: float | None = None
    critical_count: int
    improvable_count: int
    adequate_count: int
    na_count: int


class HumanValidationSummary(BaseModel):
    """Placeholder surface for the Phase 5.8 human-judgment campaign."""

    status: Literal["not_available", "in_preparation"] = "in_preparation"
    title: str = "Validazione umana in preparazione"
    description: str = (
        "La sezione raccoglierà il confronto tra giudizi del sistema e "
        "valutazione esperta: accordo per criterio, errore medio e casi "
        "di maggiore disaccordo."
    )


class ResultsSummary(BaseModel):
    """Payload consumed by the frontend ``/results`` page."""

    generated_at: datetime
    overview: ResultsOverview
    criteria: list[CriterionDistribution] = Field(default_factory=list)
    evaluations: list[ResultsEvaluationRow] = Field(default_factory=list)
    human_validation: HumanValidationSummary = Field(
        default_factory=HumanValidationSummary,
    )
