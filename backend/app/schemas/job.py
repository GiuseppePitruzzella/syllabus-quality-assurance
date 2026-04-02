from pydantic import BaseModel


class JobCreated(BaseModel):
    job_id: str


class SseEvent(BaseModel):
    type: str  # "progress" | "done" | "error"
    current: int | None = None
    total: int | None = None
    message: str | None = None
    scraped: int | None = None
    errors: int | None = None
