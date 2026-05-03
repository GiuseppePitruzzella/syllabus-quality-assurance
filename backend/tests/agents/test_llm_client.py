"""Unit tests for VertexAILLMClient.

Vertex AI is mocked: tests run offline and incur no API cost.
The retry logic is tested with a low call_count so the cumulative
back-off time stays under a couple of seconds.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import (
    DeadlineExceeded,
    ResourceExhausted,
    ServiceUnavailable,
)

from app.config import ScientificConfig


def _scientific(**overrides) -> ScientificConfig:
    """Build a fresh ScientificConfig (frozen) with optional overrides."""
    base = {
        "llm_model": "gemini-2.5-flash",
        "embedding_model": "gemini-embedding-001",
        "embedding_output_dimensionality": 3072,
        "llm_temperature": 0.1,
        "llm_max_output_tokens": 2048,
        "rag_top_k": 5,
        "rag_final_k": 3,
        "rag_similarity_threshold": 0.6,
    }
    base.update(overrides)
    return ScientificConfig(**base)


def _fake_response(
    *,
    text: str | None = "ok",
    finish_reason_name: str = "STOP",
    has_candidates: bool = True,
    prompt_block_reason: str | None = None,
) -> SimpleNamespace:
    """Build a SimpleNamespace mimicking the Vertex GenerationResponse."""
    if has_candidates:
        candidate = SimpleNamespace(
            finish_reason=SimpleNamespace(name=finish_reason_name)
        )
        candidates = [candidate]
    else:
        candidates = []
    feedback = (
        SimpleNamespace(block_reason=SimpleNamespace(name=prompt_block_reason))
        if prompt_block_reason
        else None
    )
    response = SimpleNamespace(candidates=candidates, prompt_feedback=feedback)
    if text is not None:
        response.text = text
    return response


def _patch_vertex(monkeypatch, response_or_exception=None) -> MagicMock:
    """Patch GenerativeModel and vertexai.init so no real API call happens."""
    fake_model = MagicMock()
    if isinstance(response_or_exception, BaseException):
        fake_model.generate_content.side_effect = response_or_exception
    elif callable(response_or_exception):
        fake_model.generate_content.side_effect = response_or_exception
    else:
        fake_model.generate_content.return_value = response_or_exception or _fake_response()

    monkeypatch.setattr(
        "app.evaluation.agents.llm_client.GenerativeModel",
        MagicMock(return_value=fake_model),
    )
    monkeypatch.setattr("app.evaluation.agents.llm_client.vertexai.init", MagicMock())
    return fake_model


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_init_rejects_empty_project_id(monkeypatch):
    _patch_vertex(monkeypatch)
    from app.evaluation.agents.llm_client import VertexAILLMClient

    with pytest.raises(ValueError, match="project_id"):
        VertexAILLMClient(project_id="", location="europe-west1", scientific=_scientific())


def test_init_uses_scientific_llm_model(monkeypatch):
    fake_factory = MagicMock(return_value=MagicMock())
    monkeypatch.setattr("app.evaluation.agents.llm_client.GenerativeModel", fake_factory)
    monkeypatch.setattr("app.evaluation.agents.llm_client.vertexai.init", MagicMock())

    from app.evaluation.agents.llm_client import VertexAILLMClient
    client = VertexAILLMClient(
        project_id="proj-x",
        location="europe-west1",
        scientific=_scientific(llm_model="gemini-2.5-flash"),
    )
    fake_factory.assert_called_once_with("gemini-2.5-flash")
    assert client.model_name == "gemini-2.5-flash"
    assert client.project_id == "proj-x"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_call_returns_text_and_metadata(monkeypatch):
    _patch_vertex(monkeypatch, _fake_response(text="hello"))
    from app.evaluation.agents.llm_client import VertexAILLMClient

    client = VertexAILLMClient("proj-1", "europe-west1", _scientific())
    result = client("ciao")
    assert result.text == "hello"
    md = result.metadata
    assert md["model"] == "gemini-2.5-flash"
    assert md["gcp_project_id"] == "proj-1"
    assert md["gcp_location"] == "europe-west1"
    assert md["temperature"] == 0.1
    assert md["max_output_tokens"] == 2048
    assert md["finish_reason"] == "STOP"
    assert md["prompt_chars"] == 4
    assert md["response_chars"] == 5
    assert md["latency_ms"] >= 0
    assert "seed" not in md  # seed not provided


def test_call_passes_temperature_and_max_tokens(monkeypatch):
    fake_model = _patch_vertex(monkeypatch, _fake_response())
    from app.evaluation.agents.llm_client import VertexAILLMClient

    client = VertexAILLMClient(
        "proj-1",
        "europe-west1",
        _scientific(llm_temperature=0.42, llm_max_output_tokens=1024),
    )
    client("test")
    args, kwargs = fake_model.generate_content.call_args
    assert args[0] == "test"
    config_dict = kwargs["generation_config"].to_dict()
    assert config_dict["temperature"] == 0.42
    assert config_dict["max_output_tokens"] == 1024
    assert "seed" not in config_dict  # not provided


def test_call_passes_seed_when_provided(monkeypatch):
    fake_model = _patch_vertex(monkeypatch, _fake_response())
    from app.evaluation.agents.llm_client import VertexAILLMClient

    client = VertexAILLMClient("proj-1", "europe-west1", _scientific())
    result = client("test", seed=42)
    args, kwargs = fake_model.generate_content.call_args
    assert kwargs["generation_config"].to_dict()["seed"] == 42
    assert result.metadata["seed"] == 42


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_call_rejects_empty_prompt(monkeypatch):
    fake_model = _patch_vertex(monkeypatch, _fake_response())
    from app.evaluation.agents.llm_client import VertexAILLMClient

    client = VertexAILLMClient("proj-1", "europe-west1", _scientific())
    with pytest.raises(ValueError, match="non-empty"):
        client("")
    with pytest.raises(ValueError, match="non-empty"):
        client("   \n  ")
    fake_model.generate_content.assert_not_called()


# ---------------------------------------------------------------------------
# Finish reasons -> typed errors
# ---------------------------------------------------------------------------


def test_safety_finish_raises_safety_blocked(monkeypatch):
    _patch_vertex(monkeypatch, _fake_response(finish_reason_name="SAFETY"))
    from app.evaluation.agents.llm_client import (
        LLMSafetyBlockedError,
        VertexAILLMClient,
    )

    client = VertexAILLMClient("p", "europe-west1", _scientific())
    with pytest.raises(LLMSafetyBlockedError) as exc_info:
        client("hi")
    assert exc_info.value.reason == "SAFETY"
    assert exc_info.value.prompt_blocked is False


@pytest.mark.parametrize(
    "reason", ["BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "RECITATION"]
)
def test_other_safety_reasons_also_raise(monkeypatch, reason):
    _patch_vertex(monkeypatch, _fake_response(finish_reason_name=reason))
    from app.evaluation.agents.llm_client import (
        LLMSafetyBlockedError,
        VertexAILLMClient,
    )

    client = VertexAILLMClient("p", "europe-west1", _scientific())
    with pytest.raises(LLMSafetyBlockedError) as exc_info:
        client("hi")
    assert exc_info.value.reason == reason


def test_max_tokens_finish_raises_truncated(monkeypatch):
    _patch_vertex(monkeypatch, _fake_response(finish_reason_name="MAX_TOKENS"))
    from app.evaluation.agents.llm_client import (
        LLMResponseTruncatedError,
        VertexAILLMClient,
    )

    client = VertexAILLMClient("p", "europe-west1", _scientific())
    with pytest.raises(LLMResponseTruncatedError, match="MAX_TOKENS"):
        client("hi")


def test_other_finish_raises_empty_response(monkeypatch):
    _patch_vertex(monkeypatch, _fake_response(finish_reason_name="OTHER"))
    from app.evaluation.agents.llm_client import (
        LLMEmptyResponseError,
        VertexAILLMClient,
    )

    client = VertexAILLMClient("p", "europe-west1", _scientific())
    with pytest.raises(LLMEmptyResponseError, match="OTHER"):
        client("hi")


def test_no_candidates_with_prompt_block_raises_safety(monkeypatch):
    """If the prompt itself is blocked, we report a prompt-level safety error."""
    _patch_vertex(
        monkeypatch,
        _fake_response(has_candidates=False, prompt_block_reason="PROHIBITED_CONTENT"),
    )
    from app.evaluation.agents.llm_client import (
        LLMSafetyBlockedError,
        VertexAILLMClient,
    )

    client = VertexAILLMClient("p", "europe-west1", _scientific())
    with pytest.raises(LLMSafetyBlockedError) as exc_info:
        client("hi")
    assert exc_info.value.prompt_blocked is True
    assert exc_info.value.reason == "PROHIBITED_CONTENT"


def test_no_candidates_without_prompt_block_raises_empty(monkeypatch):
    _patch_vertex(monkeypatch, _fake_response(has_candidates=False))
    from app.evaluation.agents.llm_client import (
        LLMEmptyResponseError,
        VertexAILLMClient,
    )

    client = VertexAILLMClient("p", "europe-west1", _scientific())
    with pytest.raises(LLMEmptyResponseError, match="no candidates"):
        client("hi")


# ---------------------------------------------------------------------------
# Retry on transient errors
# ---------------------------------------------------------------------------


def test_retries_on_resource_exhausted_then_succeeds(monkeypatch):
    """ResourceExhausted (429) is retried up to 3 times; we succeed on the 3rd."""
    call_count = {"n": 0}

    def _flaky(*_args, **_kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise ResourceExhausted("rate limited")
        return _fake_response(text="finally")

    _patch_vertex(monkeypatch, _flaky)
    from app.evaluation.agents.llm_client import VertexAILLMClient

    client = VertexAILLMClient("p", "europe-west1", _scientific())
    result = client("hi")
    assert result.text == "finally"
    assert call_count["n"] == 3


def test_retries_exhaust_and_propagate(monkeypatch):
    fake_model = MagicMock()
    fake_model.generate_content.side_effect = ServiceUnavailable("down")
    monkeypatch.setattr(
        "app.evaluation.agents.llm_client.GenerativeModel",
        MagicMock(return_value=fake_model),
    )
    monkeypatch.setattr("app.evaluation.agents.llm_client.vertexai.init", MagicMock())

    from app.evaluation.agents.llm_client import VertexAILLMClient
    client = VertexAILLMClient("p", "europe-west1", _scientific())
    with pytest.raises(ServiceUnavailable):
        client("hi")
    assert fake_model.generate_content.call_count == 3


def test_does_not_retry_on_safety_block(monkeypatch):
    """Safety blocks must not be retried — they are permanent for this prompt."""
    fake_model = _patch_vertex(monkeypatch, _fake_response(finish_reason_name="SAFETY"))
    from app.evaluation.agents.llm_client import (
        LLMSafetyBlockedError,
        VertexAILLMClient,
    )

    client = VertexAILLMClient("p", "europe-west1", _scientific())
    with pytest.raises(LLMSafetyBlockedError):
        client("hi")
    # Single call only — no retry
    assert fake_model.generate_content.call_count == 1


def test_does_not_retry_on_truncation(monkeypatch):
    """Truncation is not transient: the agent layer decides what to do next."""
    fake_model = _patch_vertex(monkeypatch, _fake_response(finish_reason_name="MAX_TOKENS"))
    from app.evaluation.agents.llm_client import (
        LLMResponseTruncatedError,
        VertexAILLMClient,
    )

    client = VertexAILLMClient("p", "europe-west1", _scientific())
    with pytest.raises(LLMResponseTruncatedError):
        client("hi")
    assert fake_model.generate_content.call_count == 1


@pytest.mark.parametrize("exc_cls", [ResourceExhausted, ServiceUnavailable, DeadlineExceeded])
def test_all_transient_exceptions_are_retried(monkeypatch, exc_cls):
    fake_model = MagicMock()
    fake_model.generate_content.side_effect = exc_cls("transient")
    monkeypatch.setattr(
        "app.evaluation.agents.llm_client.GenerativeModel",
        MagicMock(return_value=fake_model),
    )
    monkeypatch.setattr("app.evaluation.agents.llm_client.vertexai.init", MagicMock())

    from app.evaluation.agents.llm_client import VertexAILLMClient
    client = VertexAILLMClient("p", "europe-west1", _scientific())
    with pytest.raises(exc_cls):
        client("hi")
    assert fake_model.generate_content.call_count == 3


# ---------------------------------------------------------------------------
# BaseAgent integration: duck-typing via .text
# ---------------------------------------------------------------------------


def test_llm_result_is_compatible_with_base_agent_invoke(monkeypatch):
    """BaseAgent._invoke_llm extracts result.text — LLMResult provides it."""
    _patch_vertex(monkeypatch, _fake_response(text='{"judgments": []}'))
    from app.evaluation.agents.base import BaseAgent
    from app.evaluation.agents.llm_client import VertexAILLMClient

    client = VertexAILLMClient("p", "europe-west1", _scientific())

    # Subclass BaseAgent with a no-op get_relevant_syllabus_fields just to
    # bind the llm client and call _invoke_llm directly.
    class _Probe(BaseAgent):
        agent_code = "A1"
        criteria_codes = ["C1"]

        def get_relevant_syllabus_fields(self, syllabus):  # pragma: no cover
            return {}

    probe = _Probe(retriever=MagicMock(), llm_client=client, prompt_builder=lambda x: "p")
    text = probe._invoke_llm("hi")
    assert text == '{"judgments": []}'
