"""In-memory registry of in-flight evaluation runs (Phase 5.4.H.2).

One asyncio queue per evaluation UUID. The :class:`AsyncEvaluationService`
publishes typed :class:`ProgressEvent` frames; the SSE stream endpoint
drains them and writes them to the client.

The registry is intentionally tiny and in-memory: the thesis prototype
runs as a single uvicorn process (D023), so no IPC is required. After
the terminal event (``evaluation_completed`` or ``error``) we enqueue a
``None`` sentinel so the stream loop can break, then schedule a
delayed cleanup so a late-joining consumer can still drain the buffer.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.schemas.evaluation_event import ProgressEvent


@dataclass
class EvaluationStreamState:
    """Per-evaluation state held by the registry."""

    queue: asyncio.Queue[ProgressEvent | None] = field(default_factory=asyncio.Queue)
    completed_at: datetime | None = None


class EvaluationRegistry:
    """In-memory map ``evaluation_uuid -> EvaluationStreamState``."""

    # How long to keep the queue around after the terminal event, so a
    # late-joining SSE consumer can still drain it. 10 minutes matches
    # the scraping JobRegistry.
    _CLEANUP_DELAY_SECONDS: float = 600.0

    def __init__(self) -> None:
        self._states: dict[str, EvaluationStreamState] = {}

    def register(self, evaluation_uuid: str) -> EvaluationStreamState:
        """Create an empty stream state for ``evaluation_uuid``.

        Idempotent: returns the existing state if already registered.
        """
        state = self._states.get(evaluation_uuid)
        if state is None:
            state = EvaluationStreamState()
            self._states[evaluation_uuid] = state
        return state

    def get(self, evaluation_uuid: str) -> EvaluationStreamState | None:
        return self._states.get(evaluation_uuid)

    def publish(
        self,
        evaluation_uuid: str,
        event: ProgressEvent,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Thread-safe: schedule put on the loop from a worker thread.

        The graph runs in ``asyncio.to_thread``, so we cross the
        thread/loop boundary explicitly. Events for an unknown UUID are
        dropped silently — the caller (the publisher closure) cannot
        cancel an in-flight evaluation cleanly mid-graph.
        """
        state = self._states.get(evaluation_uuid)
        if state is None:
            return
        loop.call_soon_threadsafe(state.queue.put_nowait, event)

    def complete(
        self,
        evaluation_uuid: str,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Enqueue the ``None`` sentinel and schedule delayed cleanup."""
        state = self._states.get(evaluation_uuid)
        if state is None:
            return
        state.completed_at = datetime.now(timezone.utc)
        loop.call_soon_threadsafe(state.queue.put_nowait, None)
        loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(
                self._cleanup_after(evaluation_uuid, self._CLEANUP_DELAY_SECONDS)
            )
        )

    async def _cleanup_after(self, evaluation_uuid: str, delay: float) -> None:
        await asyncio.sleep(delay)
        self._states.pop(evaluation_uuid, None)


# Singleton instance used by the API layer.
evaluation_registry = EvaluationRegistry()
