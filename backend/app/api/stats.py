"""Stats endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cdl import CorsoDiLaurea
from app.models.department import Department
from app.models.syllabus import Syllabus

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Return aggregate counts."""
    departments = db.query(Department).count()
    cdl = db.query(CorsoDiLaurea).count()
    syllabi = db.query(Syllabus).count()
    with_english = db.query(Syllabus).filter(Syllabus.has_english == True).count()  # noqa: E712
    return {
        "departments": departments,
        "cdl": cdl,
        "syllabi": syllabi,
        "with_english": with_english,
    }
