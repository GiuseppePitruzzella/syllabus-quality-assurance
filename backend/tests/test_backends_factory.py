# backend/tests/test_backends_factory.py
from __future__ import annotations

from unittest.mock import MagicMock

from app import backends
from app.config import Settings
from app.evaluation.agents import llm_client as llm_mod
from app.evaluation.agents.llm_client import GeminiApiLLMClient, VertexAILLMClient
from app.evaluation.agents.rate_limit import MinIntervalLLMClient
from app.evaluation.rag import embeddings as emb_mod
from app.evaluation.rag.embeddings import GeminiApiEmbeddings, VertexAIEmbeddings


def test_build_llm_vertex_by_default(monkeypatch):
    monkeypatch.setattr(llm_mod.genai, "Client", lambda *a, **k: MagicMock())
    s = Settings(_env_file=None, genai_use_vertex=True, gcp_project_id="proj")
    client = backends.build_llm_client(s, s.scientific)
    assert isinstance(client, VertexAILLMClient)


def test_build_llm_ai_studio_is_throttled(monkeypatch):
    monkeypatch.setattr(llm_mod.genai, "Client", lambda *a, **k: MagicMock())
    s = Settings(_env_file=None, genai_use_vertex=False, gemini_api_key="KEY")
    client = backends.build_llm_client(s, s.scientific)
    assert isinstance(client, MinIntervalLLMClient)
    assert isinstance(client._inner, GeminiApiLLMClient)


def test_build_embeddings_switches_on_flag(monkeypatch):
    monkeypatch.setattr(emb_mod.genai, "Client", lambda *a, **k: MagicMock())
    vertex = Settings(_env_file=None, genai_use_vertex=True, gcp_project_id="proj")
    ai = Settings(_env_file=None, genai_use_vertex=False, gemini_api_key="KEY")
    assert isinstance(backends.build_embeddings_client(vertex), VertexAIEmbeddings)
    assert isinstance(backends.build_embeddings_client(ai), GeminiApiEmbeddings)


def test_build_pdf_ocr_ai_studio(monkeypatch):
    from google import genai as google_genai

    monkeypatch.setattr(google_genai, "Client", lambda *a, **k: MagicMock())
    s = Settings(_env_file=None, genai_use_vertex=False, gemini_api_key="KEY")
    ocr = backends.build_pdf_ocr(s)
    # Injected client path: no project_id required.
    assert ocr._model_name == s.scientific.llm_model
