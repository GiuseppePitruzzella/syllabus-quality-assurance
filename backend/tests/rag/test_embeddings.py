"""Unit tests for the Gen AI SDK embeddings wrapper.

The tests mock ``google.genai.Client`` so they run offline and
incur no API cost. The public surface of :class:`VertexAIEmbeddings`
is unchanged after the SDK migration, so test intent is the same as
before — only the mock surface has been adapted from
``TextEmbeddingModel.from_pretrained`` to ``genai.Client``.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable
from google.genai import errors as genai_errors


def _client_error(code: int) -> genai_errors.ClientError:
    """Construct a `ClientError` mimicking a Gen AI SDK HTTP error.

    `ClientError.__init__(code, response_json, response=None)`
    populates the `code` attribute the retry predicate inspects.
    """
    return genai_errors.ClientError(
        code, {"error": {"code": code, "status": "TEST", "message": "test"}}, None,
    )


def _server_error(code: int = 503) -> genai_errors.ServerError:
    return genai_errors.ServerError(
        code, {"error": {"code": code, "status": "TEST", "message": "test"}}, None,
    )


def _patch_genai(
    monkeypatch,
    fake_embeddings: list[float] | Exception | None = None,
):
    """Patch ``genai.Client`` so no real Vertex call is issued.

    When ``fake_embeddings`` is an Exception it is raised by every
    ``embed_content`` call; otherwise the call returns a response
    object whose ``.embeddings[0].values`` is ``fake_embeddings``
    (defaulting to a 3072-long vector).
    """
    fake_client = MagicMock()
    fake_models = MagicMock()
    fake_client.models = fake_models

    if isinstance(fake_embeddings, Exception):
        fake_models.embed_content.side_effect = fake_embeddings
    else:
        def _fake_call(*_args, **_kwargs):
            vec = fake_embeddings if fake_embeddings is not None else [0.1] * 3072
            emb = MagicMock()
            emb.values = vec
            response = MagicMock()
            response.embeddings = [emb]
            return response

        fake_models.embed_content.side_effect = _fake_call

    monkeypatch.setattr(
        "app.evaluation.rag.embeddings.genai.Client",
        MagicMock(return_value=fake_client),
    )
    return fake_models


def test_init_rejects_empty_project_id(monkeypatch):
    _patch_genai(monkeypatch)
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    with pytest.raises(ValueError, match="project_id"):
        VertexAIEmbeddings(project_id="", location="europe-west1")


def test_embed_documents_empty_list_returns_empty(monkeypatch):
    fake = _patch_genai(monkeypatch)
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    assert emb.embed_documents([]) == []
    fake.embed_content.assert_not_called()


def test_embed_documents_calls_api_per_text(monkeypatch):
    fake = _patch_genai(monkeypatch, fake_embeddings=[0.5] * 3072)
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    out = emb.embed_documents(["a", "b", "c"])
    assert len(out) == 3
    assert all(len(v) == 3072 for v in out)
    # gemini-embedding-001 batch size = 1, so 3 inputs => 3 API calls
    assert fake.embed_content.call_count == 3


def test_embed_documents_uses_retrieval_document_task_type(monkeypatch):
    fake = _patch_genai(monkeypatch, fake_embeddings=[0.5] * 3072)
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    emb.embed_documents(["hello"])
    _args, kwargs = fake.embed_content.call_args
    assert kwargs["contents"] == "hello"
    assert kwargs["config"].task_type == "RETRIEVAL_DOCUMENT"


def test_embed_query_uses_retrieval_query_task_type(monkeypatch):
    fake = _patch_genai(monkeypatch, fake_embeddings=[0.5] * 3072)
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    out = emb.embed_query("query?")
    assert len(out) == 3072
    _args, kwargs = fake.embed_content.call_args
    assert kwargs["contents"] == "query?"
    assert kwargs["config"].task_type == "RETRIEVAL_QUERY"


def test_embed_passes_output_dimensionality(monkeypatch):
    fake = _patch_genai(monkeypatch, fake_embeddings=[0.5] * 768)
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    emb = VertexAIEmbeddings(
        project_id="test", location="europe-west1", output_dimensionality=768
    )
    emb.embed_query("q")
    _args, kwargs = fake.embed_content.call_args
    assert kwargs["config"].output_dimensionality == 768


def test_embed_rejects_empty_text(monkeypatch):
    _patch_genai(monkeypatch)
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    with pytest.raises(ValueError, match="non-empty"):
        emb.embed_query("")
    with pytest.raises(ValueError, match="non-empty"):
        emb.embed_query("   \n\t  ")


def test_embed_raises_on_dimension_mismatch(monkeypatch):
    """If the SDK returns the wrong dimension, fail loudly."""
    _patch_genai(monkeypatch, fake_embeddings=[0.1] * 768)  # claimed 3072, got 768
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    emb = VertexAIEmbeddings(
        project_id="test", location="europe-west1", output_dimensionality=3072
    )
    with pytest.raises(RuntimeError, match="dimension"):
        emb.embed_query("query")


def test_embed_retries_on_resource_exhausted(monkeypatch):
    """Retry logic: ResourceExhausted (429) is retried up to 3 times."""
    fake_client = MagicMock()
    fake_models = MagicMock()
    fake_client.models = fake_models

    call_count = {"n": 0}

    def _flaky(*_args, **_kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise ResourceExhausted("rate limited")
        emb = MagicMock()
        emb.values = [0.5] * 3072
        response = MagicMock()
        response.embeddings = [emb]
        return response

    fake_models.embed_content.side_effect = _flaky
    monkeypatch.setattr(
        "app.evaluation.rag.embeddings.genai.Client",
        MagicMock(return_value=fake_client),
    )

    # Tenacity's wait_exponential is configured at class-definition
    # time; the first retry waits ~1s, the second ~4s. We accept the
    # short wait rather than introduce a complex monkeypatch on the
    # bound decorator.
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    out = emb.embed_query("text")
    assert len(out) == 3072
    assert call_count["n"] == 3


def test_embed_does_not_retry_on_value_error(monkeypatch):
    """Permanent errors (ValueError, etc.) are not retried."""
    fake_client = MagicMock()
    fake_models = MagicMock()
    fake_client.models = fake_models
    fake_models.embed_content.side_effect = ValueError("invalid")
    monkeypatch.setattr(
        "app.evaluation.rag.embeddings.genai.Client",
        MagicMock(return_value=fake_client),
    )

    from app.evaluation.rag.embeddings import VertexAIEmbeddings
    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    with pytest.raises(ValueError):
        emb.embed_query("x")
    # Single attempt only
    assert fake_models.embed_content.call_count == 1


def test_embed_propagates_after_exhausting_retries(monkeypatch):
    """After 3 retries, ServiceUnavailable propagates."""
    fake_client = MagicMock()
    fake_models = MagicMock()
    fake_client.models = fake_models
    fake_models.embed_content.side_effect = ServiceUnavailable("down")
    monkeypatch.setattr(
        "app.evaluation.rag.embeddings.genai.Client",
        MagicMock(return_value=fake_client),
    )

    from app.evaluation.rag.embeddings import VertexAIEmbeddings
    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    with pytest.raises(ServiceUnavailable):
        emb.embed_query("x")
    assert fake_models.embed_content.call_count == 3


def test_embed_retries_on_client_error_429(monkeypatch):
    """ClientError(429) (rate limit) must be retried — regression guard.

    The new SDK surfaces rate-limit errors as `ClientError(code=429)`,
    distinct from the legacy `ResourceExhausted` path. Without an
    explicit `code == 429` check in the retry predicate, a real
    429 would NOT be retried.
    """
    fake_client = MagicMock()
    fake_models = MagicMock()
    fake_client.models = fake_models

    call_count = {"n": 0}

    def _flaky(*_args, **_kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise _client_error(429)
        emb = MagicMock()
        emb.values = [0.5] * 3072
        response = MagicMock()
        response.embeddings = [emb]
        return response

    fake_models.embed_content.side_effect = _flaky
    monkeypatch.setattr(
        "app.evaluation.rag.embeddings.genai.Client",
        MagicMock(return_value=fake_client),
    )

    from app.evaluation.rag.embeddings import VertexAIEmbeddings
    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    out = emb.embed_query("text")
    assert len(out) == 3072
    assert call_count["n"] == 3


@pytest.mark.parametrize("code", [400, 403, 404])
def test_embed_does_not_retry_on_non_429_client_error(monkeypatch, code):
    """Non-429 4xx must NOT be retried (invalid argument, forbidden, etc.)."""
    fake_client = MagicMock()
    fake_models = MagicMock()
    fake_client.models = fake_models
    fake_models.embed_content.side_effect = _client_error(code)
    monkeypatch.setattr(
        "app.evaluation.rag.embeddings.genai.Client",
        MagicMock(return_value=fake_client),
    )

    from app.evaluation.rag.embeddings import VertexAIEmbeddings
    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    with pytest.raises(genai_errors.ClientError):
        emb.embed_query("x")
    # Single attempt only — no retry on permanent 4xx.
    assert fake_models.embed_content.call_count == 1


def test_embed_retries_on_genai_server_error(monkeypatch):
    """ServerError (5xx from the new SDK) is retried."""
    fake_client = MagicMock()
    fake_models = MagicMock()
    fake_client.models = fake_models

    call_count = {"n": 0}

    def _flaky(*_args, **_kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise _server_error(503)
        emb = MagicMock()
        emb.values = [0.5] * 3072
        response = MagicMock()
        response.embeddings = [emb]
        return response

    fake_models.embed_content.side_effect = _flaky
    monkeypatch.setattr(
        "app.evaluation.rag.embeddings.genai.Client",
        MagicMock(return_value=fake_client),
    )

    from app.evaluation.rag.embeddings import VertexAIEmbeddings
    emb = VertexAIEmbeddings(project_id="test", location="europe-west1")
    out = emb.embed_query("text")
    assert len(out) == 3072
    assert call_count["n"] == 3


def test_client_constructed_with_api_version_v1(monkeypatch):
    """genai.Client must be constructed with HttpOptions(api_version='v1').

    Pinning the stable surface protects EvaluationResult
    reproducibility — beta endpoints can shift response shape and
    finish-reason sets between runs.
    """
    fake_constructor = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(
        "app.evaluation.rag.embeddings.genai.Client", fake_constructor,
    )

    from app.evaluation.rag.embeddings import VertexAIEmbeddings
    VertexAIEmbeddings(project_id="test", location="europe-west1")

    _args, kwargs = fake_constructor.call_args
    assert kwargs.get("vertexai") is True
    assert kwargs.get("project") == "test"
    assert kwargs.get("location") == "europe-west1"
    http_options = kwargs.get("http_options")
    assert http_options is not None, "HttpOptions must be passed to the client"
    assert http_options.api_version == "v1"


def test_properties_expose_config(monkeypatch):
    _patch_genai(monkeypatch)
    from app.evaluation.rag.embeddings import VertexAIEmbeddings

    emb = VertexAIEmbeddings(
        project_id="test",
        location="europe-west1",
        model_name="gemini-embedding-001",
        output_dimensionality=3072,
    )
    assert emb.model_name == "gemini-embedding-001"
    assert emb.output_dimensionality == 3072
