import asyncio

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.jobs import job_registry

router = APIRouter(prefix="/api", tags=["scrape"])


@router.get("/scrape/stream/{job_id}")
async def scrape_stream(job_id: str):
    state = job_registry.get_job(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        while True:
            event = await state.queue.get()
            if event is None:
                # Sentinel — job completed
                break
            yield {"data": event.model_dump_json()}

    return EventSourceResponse(event_generator())
