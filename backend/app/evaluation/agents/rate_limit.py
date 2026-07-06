# backend/app/evaluation/agents/rate_limit.py
"""Client-side min-interval throttle for the LLM client.

The Gemini Developer API free tier caps gemini-2.5-flash at a few requests
per minute (5 RPM verified 2026-07-06, D080). The evaluation graph runs the
four agents sequentially, so a simple min-interval gate before each call keeps
a run under the quota instead of relying on the retry loop to absorb every
429. Embeddings use a separate, higher quota and are not throttled here.
"""
from __future__ import annotations

import threading
import time

from app.evaluation.agents.llm_client import LLMClient, LLMResult


class MinIntervalLLMClient:
    """Wrap an ``LLMClient`` and enforce >= 60/rpm seconds between calls."""

    def __init__(self, inner: LLMClient, rpm_limit: int) -> None:
        self._inner = inner
        self._min_interval = 60.0 / rpm_limit if rpm_limit > 0 else 0.0
        self._lock = threading.Lock()
        self._last_call = 0.0

    def __call__(
        self,
        prompt: str,
        *,
        seed: int | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResult:
        with self._lock:
            wait = self._min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
        return self._inner(prompt, seed=seed, max_output_tokens=max_output_tokens)
