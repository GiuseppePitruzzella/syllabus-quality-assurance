from unittest.mock import Mock

import pytest
import requests

from app.evaluation.agents.llm_client import LLMResponseTruncatedError
from app.evaluation.agents.ollama_client import (
    LocalInferenceError, OllamaConfig, OllamaLLMClient,
)


def reply(body, status=200):
    return Mock(status_code=status, json=lambda: body, text=str(body))


def ready_client(monkeypatch, *, response=None, show=None, entry=None, version="0.32.15"):
    client = OllamaLLMClient()
    transport = Mock(side_effect=[
        reply({"version": version}),
        reply({"models": [entry or {"name": "qwen3.5:4b", "digest": "sha256:test",
                                    "size": 3389983735}]}),
        reply(show or {"details": {"family": "qwen35", "quantization_level": "Q4_K_M"}}),
        reply(response or {"done": True, "done_reason": "stop",
                           "message": {"content": '{"judgments": []}'},
                           "prompt_eval_count": 5000, "eval_count": 100}),
    ])
    monkeypatch.setattr(client._session, "request", transport)
    return client, transport


@pytest.mark.parametrize("url", [
    "https://ollama.com", "http://example.com", "http://192.168.1.5:11434",
    "http://127.0.0.1.evil.example", "http://user:pass@127.0.0.1",
    "http://127.0.0.1/proxy", "http://127.0.0.1?remote=1", "file:///tmp/socket",
])
def test_remote_or_ambiguous_endpoint_refused(url):
    with pytest.raises(ValueError):
        OllamaConfig(base_url=url)


def test_localhost_normalised_without_dns():
    assert OllamaConfig(base_url="http://localhost:11434/").base_url == "http://127.0.0.1:11434"


@pytest.mark.parametrize("model", ["qwen3.5:cloud", "qwen3.5:9b", "remote/qwen3.5:4b"])
def test_unapproved_models_refused(model):
    with pytest.raises(ValueError):
        OllamaConfig(model=model)


def test_local_request_schema_budget_and_no_cloud(monkeypatch):
    from google import genai
    monkeypatch.setattr(genai, "Client", Mock(side_effect=AssertionError("cloud constructed")))
    client, transport = ready_client(monkeypatch)
    assert client._session.trust_env is False
    client.response_schema = {"type": "object"}
    result = client("Full archived prompt", seed=7, max_output_tokens=16384)
    assert result.metadata["backend"] == "ollama_local"
    assert result.metadata["max_output_tokens"] == 2048
    assert result.metadata["requested_max_output_tokens"] == 16384
    assert result.metadata["prompt_eval_count"] == 5000
    assert result.metadata["api_cost_usd"] == 0
    args, kwargs = transport.call_args
    assert args == ("POST", "http://127.0.0.1:11435/api/chat")
    assert kwargs["allow_redirects"] is False
    payload = kwargs["json"]
    assert payload["truncate"] is False and payload["shift"] is False
    assert payload["think"] is False and payload["stream"] is False
    assert payload["messages"] == [{"role": "user", "content": "Full archived prompt"}]
    assert payload["format"] == {"type": "object"}
    assert payload["options"]["seed"] == 7
    assert payload["options"]["num_ctx"] == 16384


def test_remote_model_alias_blocked_before_inference(monkeypatch):
    client, transport = ready_client(monkeypatch, show={
        "remote_host": "https://ollama.com", "details": {
            "family": "qwen35", "quantization_level": "Q4_K_M"},
    })
    with pytest.raises(LocalInferenceError, match="refused"):
        client("prompt")
    assert transport.call_count == 3


def test_old_server_refused_before_prompt(monkeypatch):
    client, transport = ready_client(monkeypatch, version="0.18.0")
    with pytest.raises(LocalInferenceError, match="0.32.15"):
        client("prompt")
    assert transport.call_count == 1


def test_missing_model_never_downloads(monkeypatch):
    client, transport = ready_client(monkeypatch, entry={"name": "another-model"})
    with pytest.raises(LocalInferenceError, match="already exist"):
        client("prompt")
    assert transport.call_count == 2


@pytest.mark.parametrize("response", [
    {"done": True, "done_reason": "length", "message": {"content": "partial"}},
    {"done": True, "done_reason": "length", "message": {"content": '{"judgments": []}'}},
])
def test_truncation_is_failure_even_for_valid_json(monkeypatch, response):
    client, _ = ready_client(monkeypatch, response=response)
    with pytest.raises(LLMResponseTruncatedError):
        client("prompt")


def test_redirect_never_followed(monkeypatch):
    client = OllamaLLMClient()
    transport = Mock(return_value=reply({}, 307))
    monkeypatch.setattr(client._session, "request", transport)
    with pytest.raises(LocalInferenceError, match="307"):
        client("prompt")
    assert transport.call_count == 1
    assert transport.call_args.kwargs["allow_redirects"] is False


def test_connection_failure_does_not_retry_or_fallback(monkeypatch):
    client = OllamaLLMClient()
    transport = Mock(side_effect=requests.ConnectionError("offline"))
    monkeypatch.setattr(client._session, "request", transport)
    with pytest.raises(LocalInferenceError, match="no cloud fallback"):
        client("prompt")
    assert transport.call_count == 1


def test_existing_completeness_agent_consumes_local_result(monkeypatch):
    import json
    from app.evaluation.agents.a1_completeness import CompletenessAgent
    judgments = [{"criterion_code": code, "score": 0, "is_na": False,
                  "justification": "La sezione richiesta risulta completamente assente.",
                  "evidences": [], "confidence": "high"} for code in ["C1", "C2", "C5"]]
    client, transport = ready_client(monkeypatch, response={
        "done": True, "done_reason": "stop",
        "message": {"content": json.dumps({"judgments": judgments})},
    })
    agent = CompletenessAgent(retriever=Mock(retrieve=Mock(return_value=[])), llm_client=client)
    output = agent.evaluate({"course_name": "Synthetic test"})
    assert len(output.judgments) == 3
    assert output.execution_metadata["llm_metadata"]["backend"] == "ollama_local"
    assert transport.call_args.kwargs["json"]["options"]["num_predict"] == 2048


def test_memory_snapshot_labels_model_allocation(monkeypatch):
    client = OllamaLLMClient()
    monkeypatch.setattr(client._session, "request", Mock(return_value=reply({"models": [{
        "name": "qwen3.5:4b", "size": 4_000_000_000, "size_vram": 4_000_000_000,
        "context_length": 16384,
    }]})))
    assert client.memory_snapshot() == {
        "size": 4_000_000_000, "size_vram": 4_000_000_000, "context_length": 16384,
    }
