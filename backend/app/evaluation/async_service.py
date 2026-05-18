"""Async wrapper around the sync :class:`EvaluationService` (Phase 5.4.H.2).

The async layer is intentionally thin: it owns the asyncio loop, the
:class:`EvaluationRegistry` (queues for SSE consumers) and the
background task lifecycle. The sync service keeps doing the DB +
graph work in a worker thread; all SSE concerns live here.

Flow (one POST /api/evaluate/{seuid} request):

1. ``start_evaluation(seuid)`` synchronously calls
   :meth:`EvaluationService.create_pending_run` via ``asyncio.to_thread``.
   We block on this — the row must exist before we return ``202`` to
   the client.
2. Register the UUID with the registry (creates the SSE queue).
3. Publish ``evaluation_started`` so a consumer that connects
   immediately after the 202 sees the first frame.
4. Schedule a background task that runs
   :meth:`EvaluationService.execute_pending_run` in a worker thread,
   under a timeout. The publisher closure is captured by the thread
   and marshals events back to the loop via ``call_soon_threadsafe``.
5. On task completion (success / exception / timeout) emit either
   ``evaluation_completed`` or ``error``, then close the queue.

The wrapper is DB-free. It only knows how to spawn / monitor a sync
service call.
"""
from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.config import Settings, settings as default_settings
from app.evaluation.registry import EvaluationRegistry, evaluation_registry
from app.evaluation.service import (
    EvaluationService,
    PendingRun,
    ProgressPublisher,
    SyllabusNotFoundError,
)
from app.schemas.evaluation_event import ProgressEvent

logger = structlog.get_logger(__name__)


class AsyncEvaluationService:
    """Thin async wrapper around :class:`EvaluationService`."""

    def __init__(
        self,
        sync_service: EvaluationService,
        *,
        registry: EvaluationRegistry | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._sync = sync_service
        self._registry = registry or evaluation_registry
        self._settings = settings or default_settings
        # Track background tasks so we can await them in tests / shutdown.
        self._tasks: set[asyncio.Task[None]] = set()

    @property
    def registry(self) -> EvaluationRegistry:
        return self._registry

    async def start_evaluation(self, seuid: str) -> str:
        """Pre-allocate the run, emit ``evaluation_started``, schedule worker.

        Returns the ``evaluation_uuid`` so the HTTP layer can respond
        with 202 and the client knows which stream to subscribe to.

        Raises:
            SyllabusNotFoundError: if no syllabus matches ``seuid``.
        """
        pending = await asyncio.to_thread(self._sync.create_pending_run, seuid)
        self._registry.register(pending.evaluation_uuid)

        await self._publish_async(
            ProgressEvent(
                type="evaluation_started",
                evaluation_uuid=pending.evaluation_uuid,
                seuid=pending.seuid,
                course_name=pending.course_name,
            )
        )

        task = asyncio.create_task(self._run_in_background(pending))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return pending.evaluation_uuid

    async def _run_in_background(self, pending: PendingRun) -> None:
        """Run the blocking graph in a worker thread under timeout."""
        loop = asyncio.get_running_loop()
        publisher = self._make_publisher(pending.evaluation_uuid, loop)
        timeout = float(self._settings.evaluation_timeout_seconds)

        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    self._sync.execute_pending_run,
                    pending,
                    progress_publisher=publisher,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.error(
                "evaluation_timeout",
                evaluation_uuid=pending.evaluation_uuid,
                seuid=pending.seuid,
                timeout_seconds=timeout,
            )
            # Mark the row as failed (best-effort; the worker thread
            # cannot actually be killed but its DB write — if any —
            # will simply overwrite the failure marker).
            self._sync_persist_timeout(pending.evaluation_uuid, timeout)
            await self._publish_async(
                ProgressEvent(
                    type="error",
                    evaluation_uuid=pending.evaluation_uuid,
                    seuid=pending.seuid,
                    error_type="TimeoutError",
                    error_message=f"evaluation exceeded {int(timeout)}s timeout",
                )
            )
        except Exception as exc:  # noqa: BLE001 — surface every failure as ``error``
            logger.error(
                "async_evaluation_failed",
                evaluation_uuid=pending.evaluation_uuid,
                seuid=pending.seuid,
                error_type=type(exc).__name__,
                error_message=str(exc),
                exc_info=True,
            )
            await self._publish_async(
                ProgressEvent(
                    type="error",
                    evaluation_uuid=pending.evaluation_uuid,
                    seuid=pending.seuid,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            )
        else:
            row = await asyncio.to_thread(
                self._sync.get_evaluation, pending.evaluation_uuid
            )
            await self._publish_async(
                ProgressEvent(
                    type="evaluation_completed",
                    evaluation_uuid=pending.evaluation_uuid,
                    seuid=pending.seuid,
                    status=row.status,
                    core_score=row.core_score,
                    coverage=row.coverage,
                    duration_ms=row.duration_ms,
                )
            )
        finally:
            self._registry.complete(pending.evaluation_uuid, loop)

    def _make_publisher(
        self,
        evaluation_uuid: str,
        loop: asyncio.AbstractEventLoop,
    ) -> ProgressPublisher:
        """Closure used by the graph thread to enqueue events."""
        registry = self._registry

        def _publish(event: dict[str, Any]) -> None:
            payload = {**event, "evaluation_uuid": evaluation_uuid}
            try:
                model = ProgressEvent.model_validate(payload)
            except Exception:  # noqa: BLE001 — drop malformed event, never crash the graph
                logger.warning(
                    "progress_event_validation_failed",
                    evaluation_uuid=evaluation_uuid,
                    raw=event,
                )
                return
            registry.publish(evaluation_uuid, model, loop)

        return _publish

    async def _publish_async(self, event: ProgressEvent) -> None:
        """Publish from the loop thread (no thread-safe marshalling needed)."""
        state = self._registry.get(event.evaluation_uuid)
        if state is not None:
            await state.queue.put(event)

    def _sync_persist_timeout(
        self, evaluation_uuid: str, timeout_seconds: float
    ) -> None:
        """Mark the row as failed with a timeout-specific message."""
        try:
            self._sync._persist_failure(  # noqa: SLF001 — internal helper reused
                evaluation_uuid,
                TimeoutError(
                    f"evaluation exceeded {int(timeout_seconds)}s timeout"
                ),
            )
        except Exception:  # noqa: BLE001
            logger.error(
                "timeout_failure_persistence_failed",
                evaluation_uuid=evaluation_uuid,
                exc_info=True,
            )


__all__ = [
    "AsyncEvaluationService",
    "SyllabusNotFoundError",
]
