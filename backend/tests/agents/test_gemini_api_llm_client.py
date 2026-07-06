# backend/tests/agents/test_gemini_api_llm_client.py
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config import ScientificConfig
from app.evaluation.agents import llm_client as mod
from app.evaluation.agents.llm_client import GeminiApiLLMClient


def test_constructs_with_api_key_not_vertex(monkeypatch):
    fake_client = MagicMock()
    captured = {}

    def fake_client_ctor(*args, **kwargs):
        captured.update(kwargs)
        return fake_client

    monkeypatch.setattr(mod.genai, "Client", fake_client_ctor)

    client = GeminiApiLLMClient(api_key="KEY", scientific=ScientificConfig())

    assert captured.get("api_key") == "KEY"
    assert "vertexai" not in captured
    assert client.model_name == ScientificConfig().llm_model


def test_backend_metadata_is_ai_studio(monkeypatch):
    monkeypatch.setattr(mod.genai, "Client", lambda *a, **k: MagicMock())
    client = GeminiApiLLMClient(api_key="KEY", scientific=ScientificConfig())
    assert client._backend_metadata() == {"backend": "ai_studio"}


def test_empty_api_key_raises():
    with pytest.raises(ValueError, match="api_key"):
        GeminiApiLLMClient(api_key="", scientific=ScientificConfig())
