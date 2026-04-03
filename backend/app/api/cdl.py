"""CdL API endpoints: list and scrape-trigger."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.jobs import job_registry
from app.models.cdl import CorsoDiLaurea
from app.models.department import Department
from app.schemas.cdl import CdLResponse
from app.schemas.job import JobCreated, SseEvent
from app.scraper.cdl_discovery import scrape_cdl

router = APIRouter(prefix="/api", tags=["cdl"])

# Ordering: Triennale=0, Magistrale=1, Ciclo Unico=2
_TYPE_ORDER = {"Triennale": 0, "Magistrale": 1, "Ciclo Unico": 2}


@router.get("/departments/{dept_id}/cdl", response_model=list[CdLResponse])
def list_cdl(dept_id: int, db: Session = Depends(get_db)):
    """List CdL for a department, ordered by type then name."""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if dept is None:
        raise HTTPException(status_code=404, detail="Department not found")

    cdl_list = db.query(CorsoDiLaurea).filter(CorsoDiLaurea.department_id == dept_id).all()
    cdl_list.sort(key=lambda c: (_TYPE_ORDER.get(c.type, 99), c.name))
    return cdl_list


@router.post("/scrape/departments/{dept_id}/cdl", response_model=JobCreated, status_code=202)
async def start_scrape_cdl(dept_id: int, db: Session = Depends(get_db)):
    """Start an async job that scrapes and upserts CdL for a department."""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if dept is None:
        raise HTTPException(status_code=404, detail="Department not found")

    job_id = job_registry.create_job()
    loop = asyncio.get_event_loop()

    dept_url = dept.website_url
    dept_id_val = dept.id

    def _run():
        try:
            results = scrape_cdl(dept_url, dept_id_val)
            total = len(results)
            for i, cdl_data in enumerate(results, 1):
                event = SseEvent(
                    type="progress",
                    current=i,
                    total=total,
                    message=f"Trovato: {cdl_data['name']}",
                )
                job_registry.publish(job_id, event, loop)

                existing = (
                    db.query(CorsoDiLaurea)
                    .filter(
                        CorsoDiLaurea.department_id == cdl_data["department_id"],
                        CorsoDiLaurea.code == cdl_data["code"],
                    )
                    .first()
                )
                if existing:
                    for key, value in cdl_data.items():
                        setattr(existing, key, value)
                    existing.scraped_at = datetime.now(timezone.utc)
                else:
                    db.add(
                        CorsoDiLaurea(
                            **cdl_data,
                            academic_year=None,
                            scraped_at=datetime.now(timezone.utc),
                        )
                    )
                db.commit()

            done = SseEvent(type="done", scraped=total, errors=0)
            job_registry.publish(job_id, done, loop)
        except Exception as e:
            error = SseEvent(type="error", message=str(e))
            job_registry.publish(job_id, error, loop)
        finally:
            job_registry.complete(job_id, loop)

    loop.run_in_executor(None, _run)
    return JobCreated(job_id=job_id)
