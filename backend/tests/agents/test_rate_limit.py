# backend/tests/agents/test_rate_limit.py
from __future__ import annotations

import time

from app.evaluation.agents.llm_client import LLMResult
from app.evaluation.agents.rate_limit import MinIntervalLLMClient


class _RecordingClient:
    def __init__(self):
        self.calls = []

    def __call__(self, prompt, *, seed=None, max_output_tokens=None):
        self.calls.append((prompt, seed, max_output_tokens))
        return LLMResult(text="ok", metadata={})


def test_forwards_call_and_returns_result():
    inner = _RecordingClient()
    client = MinIntervalLLMClient(inner, rpm_limit=6000)  # interval 0.01s
    result = client("hello", seed=7, max_output_tokens=128)
    assert result.text == "ok"
    assert inner.calls == [("hello", 7, 128)]


def test_spaces_consecutive_calls():
    inner = _RecordingClient()
    client = MinIntervalLLMClient(inner, rpm_limit=600)  # interval 0.1s
    start = time.monotonic()
    client("a")
    client("b")
    assert time.monotonic() - start >= 0.1


def test_zero_rpm_disables_throttle():
    inner = _RecordingClient()
    client = MinIntervalLLMClient(inner, rpm_limit=0)
    client("a")
    client("b")
    assert len(inner.calls) == 2
