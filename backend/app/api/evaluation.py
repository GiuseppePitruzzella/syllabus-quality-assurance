from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["evaluation"])


@router.post("/evaluate/{seuid}")
async def evaluate_syllabus(seuid: str):
    raise HTTPException(status_code=501, detail="Evaluation pipeline not implemented yet")


@router.get("/evaluations/{seuid}")
async def get_evaluation(seuid: str):
    raise HTTPException(status_code=501, detail="Evaluation pipeline not implemented yet")
