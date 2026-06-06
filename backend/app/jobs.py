import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.schemas.job import SseEvent


@dataclass
class JobState:
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    completed_at: datetime | None = None


class JobRegistry:
    """In-memory registry of active scraping jobs."""

    _CLEANUP_DELAY_SECONDS: float = 600.0

    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}

    def create_job(self) -> str:
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = JobState()
        return job_id

    def get_job(self, job_id: str) -> JobState | None:
        return self._jobs.get(job_id)

    def publish(self, job_id: str, event: SseEvent, loop: asyncio.AbstractEventLoop) -> None:
        """Thread-safe: schedule put on the event loop from a worker thread."""
        state = self._jobs.get(job_id)
        if state:
            loop.call_soon_threadsafe(state.queue.put_nowait, event)

    def complete(self, job_id: str, loop: asyncio.AbstractEventLoop) -> None:
        """Mark job as completed and enqueue sentinel None."""
        state = self._jobs.get(job_id)
        if state:
            state.completed_at = datetime.now(timezone.utc)
            loop.call_soon_threadsafe(state.queue.put_nowait, None)
            # A timer handle is sufficient here; unlike a sleeping
            # Task it does not produce "Task was destroyed but it is
            # pending" warnings when a short-lived TestClient loop
            # closes before the 10-minute grace period expires.
            loop.call_soon_threadsafe(
                lambda: loop.call_later(
                    self._CLEANUP_DELAY_SECONDS,
                    self._jobs.pop,
                    job_id,
                    None,
                )
            )


# Singleton instance
job_registry = JobRegistry()
