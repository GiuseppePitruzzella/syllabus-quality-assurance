"""Unit tests for the Vertex AI embeddings wrapper.

The tests mock the Vertex AI ``TextEmbeddingModel`` so they run offline
and incur no API cost.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable


def _patch_vertex(monkeypatch, fake_embeddings: list[list[float]] | Exception | None = None):
    """Return a fake TextEmbeddingModel set up to return fake embeddings.

    If ``fake_embeddings`` is an Exception, ``get_embeddings`` raises it.
    """
    fake_model = MagicMock()
    if isinstance(fake_embeddings, Exception):
        fake_model.get_embeddings.side_effect = fake_embeddings
    else:
        # Each call returns a list with one TextEmbedding-like object.
        def _fake_call(*_args, **_kwargs):
            vec = fake_embeddings if fake_embeddings is not None else [0.1] * 3072
            emb = MagicMock()
            emb.values = vec
            return [emb]

        fake_model.get_embeddings.side_effect = _fake_call

    monkeypatch.setattr(
        "app.evaluation.rag.embeddings.TextEmbeddingModel.from_pretrained",
        MagicMock(return_value=fake_model),
    )
    monkeypatch.setattr("app.evaluation.rag.embeddings.vertexai.init", MagicMock())
    return fake_model


def test_init_rejects_empty_project_id(monkeypatch):
    _patch_vertex(monkeypatch)
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    with pytest.raises(ValueError, match="project_id"):
        VertexAIEmbeddings(project_id="", location="europe-west1")


def test_embed_documents_empty_list_returns_empty(monkeypatch):
    fake = _patch_vertex(monkeypatch)
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    assert emb.embed_documents([]) == []
    fake.get_embeddings.assert_not_called()


def test_embed_documents_calls_api_per_text(monkeypatch):
    fake = _patch_vertex(monkeypatch, fake_embeddings=[0.5] * 3072)
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    out = emb.embed_documents(["a", "b", "c"])
    assert len(out) == 3
    assert all(len(v) == 3072 for v in out)
    # gemini-embedding-001 batch size = 1, so 3 inputs => 3 API calls
    assert fake.get_embeddings.call_count == 3


def test_embed_documents_uses_retrieval_document_task_type(monkeypatch):
    fake = _patch_vertex(monkeypatch, fake_embeddings=[0.5] * 3072)
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    emb.embed_documents(["hello"])
    args, _ = fake.get_embeddings.call_args
    inputs = args[0]
    assert len(inputs) == 1
    assert inputs[0].task_type == "RETRIEVAL_DOCUMENT"


def test_embed_query_uses_retrieval_query_task_type(monkeypatch):
    fake = _patch_vertex(monkeypatch, fake_embeddings=[0.5] * 3072)
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    out = emb.embed_query("query?")
    assert len(out) == 3072
    args, _ = fake.get_embeddings.call_args
    assert args[0][0].task_type == "RETRIEVAL_QUERY"


def test_embed_passes_output_dimensionality(monkeypatch):
    fake = _patch_vertex(monkeypatch, fake_embeddings=[0.5] * 768)
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    emb = VertexAIEmbeddings(
        project_id="test", location="europe-west1", output_dimensionality=768
    )
    emb.embed_query("q")
    _, kwargs = fake.get_embeddings.call_args
    assert kwargs["output_dimensionality"] == 768


def test_embed_rejects_empty_text(monkeypatch):
    _patch_vertex(monkeypatch)
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    with pytest.raises(ValueError, match="non-empty"):
        emb.embed_query("")
    with pytest.raises(ValueError, match="non-empty"):
        emb.embed_query("   \n\t  ")


def test_embed_raises_on_dimension_mismatch(monkeypatch):
    """If Vertex AI returns the wrong dimension, fail loudly."""
    _patch_vertex(monkeypatch, fake_embeddings=[0.1] * 768)  # claimed 3072, got 768
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    emb = VertexAIEmbeddings(
        project_id="test", location="europe-west1", output_dimensionality=3072
    )
    with pytest.raises(RuntimeError, match="dimension"):
        emb.embed_query("query")


def test_embed_retries_on_resource_exhausted(monkeypatch):
    """Retry logic: ResourceExhausted (429) is retried up to 3 times."""
    fake_model = MagicMock()

    call_count = {"n": 0}

    def _flaky(*_args, **_kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise ResourceExhausted("rate limited")
        emb = MagicMock()
        emb.values = [0.5] * 3072
        return [emb]

    fake_model.get_embeddings.side_effect = _flaky
    monkeypatch.setattr(
        "app.evaluation.rag.embeddings.TextEmbeddingModel.from_pretrained",
        MagicMock(return_value=fake_model),
    )
    monkeypatch.setattr("app.evaluation.rag.embeddings.vertexai.init", MagicMock())

    # Tenacity's wait_exponential is configured at class-definition time;
    # the first retry waits ~1s, the second ~4s. We accept the short wait
    # rather than introduce a complex monkeypatch on the bound decorator.
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    out = emb.embed_query("text")
    assert len(out) == 3072
    assert call_count["n"] == 3


def test_embed_does_not_retry_on_value_error(monkeypatch):
    """Permanent errors (ValueError, etc.) are not retried."""
    fake_model = MagicMock()
    fake_model.get_embeddings.side_effect = ValueError("invalid")
    monkeypatch.setattr(
        "app.evaluation.rag.embeddings.TextEmbeddingModel.from_pretrained",
        MagicMock(return_value=fake_model),
    )
    monkeypatch.setattr("app.evaluation.rag.embeddings.vertexai.init", MagicMock())

    from app.evaluation.rag.embeddings import VertexAIEmbeddings
    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    with pytest.raises(ValueError):
        emb.embed_query("x")
    # Single attempt only
    assert fake_model.get_embeddings.call_count == 1


def test_embed_propagates_after_exhausting_retries(monkeypatch):
    """After 3 retries, ResourceExhausted propagates."""
    fake_model = MagicMock()
    fake_model.get_embeddings.side_effect = ServiceUnavailable("down")
    monkeypatch.setattr(
        "app.evaluation.rag.embeddings.TextEmbeddingModel.from_pretrained",
        MagicMock(return_value=fake_model),
    )
    monkeypatch.setattr("app.evaluation.rag.embeddings.vertexai.init", MagicMock())

    from app.evaluation.rag.embeddings import VertexAIEmbeddings
    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    with pytest.raises(ServiceUnavailable):
        emb.embed_query("x")
    assert fake_model.get_embeddings.call_count == 3


def test_properties_expose_config(monkeypatch):
    _patch_vertex(monkeypatch)
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    emb = VertexAIEmbeddings(
        project_id="test",
        location="europe-west1",
        model_name="gemini-embedding-001",
        output_dimensionality=3072,
    )
    assert emb.model_name == "gemini-embedding-001"
    assert emb.output_dimensionality == 3072
