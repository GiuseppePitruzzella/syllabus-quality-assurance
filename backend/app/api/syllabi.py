"""Syllabi API endpoints."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.jobs import job_registry
from app.models.cdl import CorsoDiLaurea
from app.models.syllabus import Syllabus
from app.schemas.job import JobCreated, SseEvent
from app.schemas.syllabus import SyllabusDetail, SyllabusListItem
from app.scraper.syllabus_detail import scrape_syllabus_detail
from app.scraper.syllabus_list import scrape_syllabus_list
from app.scraper.utils import RateLimitedSession

router = APIRouter(prefix="/api", tags=["syllabi"])

# Italian content fields that must be set to "" when creating from list scraper
_IT_CONTENT_FIELDS = [
    "dublin_knowledge_it",
    "dublin_applying_it",
    "dublin_judgement_it",
    "dublin_communication_it",
    "dublin_learning_it",
    "teaching_methods_it",
    "prerequisites_it",
    "attendance_it",
    "course_content_it",
    "references_it",
    "assessment_methods_it",
    "sample_questions_it",
]


@router.get("/cdl/{cdl_id}/syllabi", response_model=list[SyllabusListItem])
def list_syllabi(
    cdl_id: int,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    """List syllabi for a CdL, ordered by year_of_study then course_name."""
    cdl = db.query(CorsoDiLaurea).filter(CorsoDiLaurea.id == cdl_id).first()
    if cdl is None:
        raise HTTPException(status_code=404, detail="CdL not found")

    q = db.query(Syllabus).filter(Syllabus.cdl_id == cdl_id)

    if search:
        pattern = f"%{search}%"
        q = q.filter(
            Syllabus.course_name.ilike(pattern) | Syllabus.course_code.ilike(pattern)
        )

    syllabi = q.order_by(Syllabus.year_of_study, Syllabus.course_name).all()
    return syllabi


@router.post("/scrape/cdl/{cdl_id}/syllabi", response_model=JobCreated, status_code=202)
async def start_scrape_syllabi(cdl_id: int, db: Session = Depends(get_db)):
    """Start an async job that scrapes and upserts the syllabus list for a CdL."""
    cdl = db.query(CorsoDiLaurea).filter(CorsoDiLaurea.id == cdl_id).first()
    if cdl is None:
        raise HTTPException(status_code=404, detail="CdL not found")

    job_id = job_registry.create_job()
    loop = asyncio.get_event_loop()

    cdl_url = cdl.url
    cdl_id_val = cdl.id

    def _run():
        try:
            results = scrape_syllabus_list(cdl_url, cdl_id_val)
            total = len(results)
            for i, syl_data in enumerate(results, 1):
                event = SseEvent(
                    type="progress",
                    current=i,
                    total=total,
                    message=f"Trovato: {syl_data['course_name']}",
                )
                job_registry.publish(job_id, event, loop)

                existing = (
                    db.query(Syllabus)
                    .filter(Syllabus.seuid == syl_data["seuid"])
                    .first()
                )
                if existing:
                    # Update only metadata fields — preserve content fields
                    for key in (
                        "cdl_id",
                        "course_code",
                        "course_name",
                        "module",
                        "teacher",
                        "academic_year",
                        "year_of_study",
                        "url_it",
                        "url_en",
                    ):
                        setattr(existing, key, syl_data[key])
                else:
                    db.add(
                        Syllabus(
                            **syl_data,
                            has_english=False,
                            **{field: "" for field in _IT_CONTENT_FIELDS},
                            schedule_it=None,
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


@router.get("/syllabi/{seuid}", response_model=SyllabusDetail)
def get_syllabus(seuid: str, db: Session = Depends(get_db)):
    """Return full syllabus detail by seuid."""
    syl = db.query(Syllabus).filter(Syllabus.seuid == seuid).first()
    if syl is None:
        raise HTTPException(status_code=404, detail="Syllabus not found")
    return syl


# ---------------------------------------------------------------------------
# Syllabus detail scraping
# ---------------------------------------------------------------------------


@router.post("/scrape/syllabi/{seuid}", response_model=SyllabusDetail)
def scrape_single_syllabus(seuid: str, db: Session = Depends(get_db)):
    """Scrape full content for a single syllabus (IT + EN). Synchronous ~3s."""
    syllabus = db.query(Syllabus).filter(Syllabus.seuid == seuid).first()
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found")

    data = scrape_syllabus_detail(syllabus.url_it, syllabus.url_en)
    for key, value in data.items():
        setattr(syllabus, key, value)
    syllabus.scraped_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(syllabus)
    return syllabus


@router.post("/scrape/cdl/{cdl_id}/syllabi/all", response_model=JobCreated, status_code=202)
async def scrape_all_syllabi(cdl_id: int, db: Session = Depends(get_db)):
    """Batch scrape all syllabi content for a CdL. Async with SSE progress."""
    cdl = db.query(CorsoDiLaurea).filter(CorsoDiLaurea.id == cdl_id).first()
    if not cdl:
        raise HTTPException(status_code=404, detail="CdL not found")

    syllabi = db.query(Syllabus).filter(Syllabus.cdl_id == cdl_id).all()
    if not syllabi:
        raise HTTPException(status_code=404, detail="No syllabi found for this CdL")

    job_id = job_registry.create_job()
    loop = asyncio.get_event_loop()

    syllabi_data = [(s.seuid, s.url_it, s.url_en) for s in syllabi]
    total = len(syllabi_data)

    def _run():
        session_http = RateLimitedSession()
        scraped = 0
        errors = 0

        for i, (s_seuid, url_it, url_en) in enumerate(syllabi_data, 1):
            try:
                data = scrape_syllabus_detail(url_it, url_en, session=session_http)
                syl = db.query(Syllabus).filter(Syllabus.seuid == s_seuid).first()
                if syl:
                    for key, value in data.items():
                        setattr(syl, key, value)
                    syl.scraped_at = datetime.now(timezone.utc)
                    db.commit()
                scraped += 1
                event = SseEvent(
                    type="progress", current=i, total=total,
                    message=f"Scraped: {syl.course_name if syl else s_seuid}",
                )
            except Exception as e:
                errors += 1
                event = SseEvent(
                    type="progress", current=i, total=total,
                    message=f"Error on {s_seuid}: {str(e)[:100]}",
                )
            job_registry.publish(job_id, event, loop)

        done = SseEvent(type="done", scraped=scraped, errors=errors)
        job_registry.publish(job_id, done, loop)
        job_registry.complete(job_id, loop)

    loop.run_in_executor(None, _run)
    return JobCreated(job_id=job_id)
