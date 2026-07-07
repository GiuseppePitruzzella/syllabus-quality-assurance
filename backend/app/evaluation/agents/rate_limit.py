"""Client-side min-interval throttles for the free-tier Gemini backend.

The Gemini Developer API free tier caps gemini-2.5-flash at 5 requests/minute
and gemini-embedding-001 at 100 requests/minute (verified 2026-07, D080). The
evaluation graph runs sequentially and corpus ingestion embeds one chunk at a
time, so a simple min-interval gate before each call keeps a run under quota
instead of relying on the retry loop to absorb every 429.
"""
from __future__ import annotations

import threading
import time

from app.evaluation.agents.llm_client import LLMClient, LLMResult


class MinIntervalGate:
    """Thread-safe gate enforcing >= 60/rpm seconds between passes.

    ``rpm_limit <= 0`` disables throttling (``wait()`` is a no-op).
    """

    def __init__(self, rpm_limit: int) -> None:
        self._min_interval = 60.0 / rpm_limit if rpm_limit > 0 else 0.0
        self._lock = threading.Lock()
        self._last_call = 0.0

    def wait(self) -> None:
        if self._min_interval <= 0:
            return
        with self._lock:
            delay = self._min_interval - (time.monotonic() - self._last_call)
            if delay > 0:
                time.sleep(delay)
            self._last_call = time.monotonic()


class MinIntervalLLMClient:
    """Wrap an ``LLMClient`` and enforce >= 60/rpm seconds between calls."""

    def __init__(self, inner: LLMClient, rpm_limit: int) -> None:
        self._inner = inner
        self._gate = MinIntervalGate(rpm_limit)

    def __call__(
        self,
        prompt: str,
        *,
        seed: int | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResult:
        self._gate.wait()
        return self._inner(prompt, seed=seed, max_output_tokens=max_output_tokens)
