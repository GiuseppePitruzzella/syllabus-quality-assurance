"""Cross-evaluation results endpoints."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from app.api.evaluation import get_sync_service
from app.evaluation.service import EvaluationService
from app.schemas.results import ResultsSummary


router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("/summary", response_model=ResultsSummary)
async def get_results_summary(
    sync_service: EvaluationService = Depends(get_sync_service),
) -> ResultsSummary:
    """Return the Phase 12 cross-syllabus results summary.

    The service computes the latest terminal evaluation per syllabus,
    so this endpoint is a read-only snapshot of the current
    experimental picture, not a raw evaluation-history dump.
    """
    payload = await asyncio.to_thread(sync_service.build_results_summary)
    return ResultsSummary.model_validate(payload)
