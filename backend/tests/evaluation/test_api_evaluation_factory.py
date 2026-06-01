"""Regression tests for production evaluation API wiring."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_vite_origin_is_allowed_by_cors() -> None:
    client = TestClient(app)

    response = client.options(
        "/api/evaluate/SEUID",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_production_async_service_uses_vertex_clients(monkeypatch) -> None:
    """The API factory must instantiate concrete clients, not Protocols."""
    import chromadb

    from app import config as config_module
    from app.api import evaluation as evaluation_api
    from app.config import ScientificConfig
    from app.evaluation.agents import llm_client as llm_module
    from app.evaluation.rag import embeddings as embeddings_module
    from app.evaluation.rag import retriever as retriever_module

    calls: dict[str, object] = {}
    scientific = ScientificConfig()

    class FakeSettings:
        chroma_persist_dir = "/tmp/chroma-test"

        @property
        def scientific(self) -> ScientificConfig:
            return scientific

        def require_vertex_ai_config(self) -> tuple[str, str]:
            return ("proj-test", "europe-west1")

    class FakeChromaClient:
        pass

    class FakeEmbeddings:
        def __init__(
            self,
            *,
            project_id: str,
            location: str,
            model_name: str,
            output_dimensionality: int,
        ) -> None:
            calls["embeddings"] = {
                "project_id": project_id,
                "location": location,
                "model_name": model_name,
                "output_dimensionality": output_dimensionality,
            }

    class FakeRetriever:
        def __init__(self, chroma_client, embeddings, scientific_config) -> None:
            calls["retriever"] = (chroma_client, embeddings, scientific_config)

    class FakeLLMClient:
        def __init__(self, *, project_id: str, location: str, scientific) -> None:
            calls["llm"] = {
                "project_id": project_id,
                "location": location,
                "scientific": scientific,
            }

    def fake_persistent_client(*, path: str):
        calls["chroma_path"] = path
        return FakeChromaClient()

    evaluation_api._production_async_service.cache_clear()
    monkeypatch.setattr(chromadb, "PersistentClient", fake_persistent_client)
    monkeypatch.setattr(config_module, "settings", FakeSettings())
    monkeypatch.setattr(embeddings_module, "VertexAIEmbeddings", FakeEmbeddings)
    monkeypatch.setattr(retriever_module, "NormativeRetriever", FakeRetriever)
    monkeypatch.setattr(llm_module, "VertexAILLMClient", FakeLLMClient)

    service = evaluation_api._production_async_service()

    assert service is not None
    assert calls["chroma_path"] == "/tmp/chroma-test"
    assert calls["embeddings"] == {
        "project_id": "proj-test",
        "location": "europe-west1",
        "model_name": scientific.embedding_model,
        "output_dimensionality": scientific.embedding_output_dimensionality,
    }
    assert calls["llm"] == {
        "project_id": "proj-test",
        "location": "europe-west1",
        "scientific": scientific,
    }

    evaluation_api._production_async_service.cache_clear()
