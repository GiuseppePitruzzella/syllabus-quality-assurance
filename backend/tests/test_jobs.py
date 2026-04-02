import asyncio
import pytest
from app.jobs import JobRegistry, SseEvent


@pytest.fixture
def registry():
    reg = JobRegistry()
    reg._jobs.clear()
    return reg


def test_create_job(registry):
    job_id = registry.create_job()
    assert job_id in registry._jobs
    state = registry._jobs[job_id]
    assert state.completed_at is None


def test_get_nonexistent_job(registry):
    assert registry.get_job("nonexistent") is None


@pytest.mark.asyncio
async def test_publish_and_consume(registry):
    job_id = registry.create_job()
    loop = asyncio.get_event_loop()
    event = SseEvent(type="progress", current=1, total=10, message="test")

    registry.publish(job_id, event, loop)

    state = registry.get_job(job_id)
    received = await asyncio.wait_for(state.queue.get(), timeout=1.0)
    assert received.type == "progress"
    assert received.current == 1


@pytest.mark.asyncio
async def test_complete_job(registry):
    job_id = registry.create_job()
    loop = asyncio.get_event_loop()
    registry.complete(job_id, loop)

    state = registry.get_job(job_id)
    assert state.completed_at is not None

    # A sentinel None should be in the queue to signal end
    sentinel = await asyncio.wait_for(state.queue.get(), timeout=1.0)
    assert sentinel is None
