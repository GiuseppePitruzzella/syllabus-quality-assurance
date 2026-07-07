# backend/tests/rag/test_gemini_api_embeddings.py
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from app.evaluation.rag import embeddings as mod
from app.evaluation.rag.embeddings import GeminiApiEmbeddings


def _fake_client_with_dim(dim: int) -> MagicMock:
    client = MagicMock()
    resp = MagicMock()
    emb = MagicMock()
    emb.values = [0.0] * dim
    resp.embeddings = [emb]
    client.models.embed_content.return_value = resp
    return client


def test_constructs_with_api_key(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        mod.genai, "Client",
        lambda *a, **k: captured.update(k) or _fake_client_with_dim(3072),
    )
    emb = GeminiApiEmbeddings(api_key="KEY")
    assert captured.get("api_key") == "KEY"
    assert "vertexai" not in captured
    assert emb.output_dimensionality == 3072


def test_embed_query_returns_expected_dim(monkeypatch):
    monkeypatch.setattr(mod.genai, "Client", lambda *a, **k: _fake_client_with_dim(3072))
    emb = GeminiApiEmbeddings(api_key="KEY")
    vec = emb.embed_query("un testo di prova")
    assert len(vec) == 3072


def test_empty_api_key_raises():
    with pytest.raises(ValueError, match="api_key"):
        GeminiApiEmbeddings(api_key="")


def test_rpm_limit_throttles_embedding_calls(monkeypatch):
    # Free-tier embedding quota is 100/min; a positive rpm_limit must space
    # per-chunk calls so corpus ingestion stays under quota.
    monkeypatch.setattr(mod.genai, "Client", lambda *a, **k: _fake_client_with_dim(3072))
    emb = GeminiApiEmbeddings(api_key="KEY", rpm_limit=600)  # 0.1s interval
    start = time.monotonic()
    emb.embed_query("a")
    emb.embed_query("b")
    assert time.monotonic() - start >= 0.1


def test_default_has_no_throttle(monkeypatch):
    monkeypatch.setattr(mod.genai, "Client", lambda *a, **k: _fake_client_with_dim(3072))
    emb = GeminiApiEmbeddings(api_key="KEY")  # rpm_limit defaults to 0
    start = time.monotonic()
    emb.embed_query("a")
    emb.embed_query("b")
    assert time.monotonic() - start < 0.1
