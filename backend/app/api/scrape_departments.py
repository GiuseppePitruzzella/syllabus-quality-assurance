import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.jobs import job_registry
from app.models.department import Department
from app.schemas.job import JobCreated, SseEvent
from app.scraper.departments import scrape_departments

router = APIRouter(prefix="/api", tags=["scrape"])


@router.post("/scrape/departments", response_model=JobCreated, status_code=202)
async def start_scrape_departments(db: Session = Depends(get_db)):
    job_id = job_registry.create_job()
    loop = asyncio.get_event_loop()

    def _run():
        try:
            departments = scrape_departments()
            total = len(departments)
            for i, dept_data in enumerate(departments, 1):
                event = SseEvent(
                    type="progress", current=i, total=total,
                    message=f"Salvato: {dept_data['name']}"
                )
                job_registry.publish(job_id, event, loop)

                existing = db.query(Department).filter_by(name=dept_data["name"]).first()
                if existing:
                    for key, value in dept_data.items():
                        setattr(existing, key, value)
                    existing.scraped_at = datetime.now(timezone.utc)
                else:
                    db.add(Department(**dept_data, scraped_at=datetime.now(timezone.utc)))
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
