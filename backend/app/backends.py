# backend/app/backends.py
"""Backend selection for Gemini clients: Vertex AI vs Developer API (D080).

Vertex is the default and the reproducible thesis path. Setting
``GENAI_USE_VERTEX=false`` switches every LLM / embedding / OCR client to the
free Gemini Developer API (AI Studio) via ``GEMINI_API_KEY``. Imports are
function-local to avoid import cycles with the local-documents package.
"""
from __future__ import annotations

from app.config import ScientificConfig, Settings


def build_embeddings_client(settings: Settings):
    from app.evaluation.rag.embeddings import (
        GeminiApiEmbeddings,
        VertexAIEmbeddings,
    )

    sci = settings.scientific
    if settings.genai_use_vertex:
        project, location = settings.require_vertex_ai_config()
        return VertexAIEmbeddings(
            project_id=project,
            location=location,
            model_name=sci.embedding_model,
            output_dimensionality=sci.embedding_output_dimensionality,
        )
    return GeminiApiEmbeddings(
        api_key=settings.require_gemini_api_key(),
        model_name=sci.embedding_model,
        output_dimensionality=sci.embedding_output_dimensionality,
        rpm_limit=settings.gemini_api_embed_rpm_limit,
    )


def build_llm_client(settings: Settings, scientific: ScientificConfig):
    from app.evaluation.agents.llm_client import (
        GeminiApiLLMClient,
        VertexAILLMClient,
    )
    from app.evaluation.agents.rate_limit import MinIntervalLLMClient

    if settings.genai_use_vertex:
        project, location = settings.require_vertex_ai_config()
        return VertexAILLMClient(
            project_id=project, location=location, scientific=scientific
        )
    inner = GeminiApiLLMClient(
        api_key=settings.require_gemini_api_key(), scientific=scientific
    )
    return MinIntervalLLMClient(inner, settings.gemini_api_rpm_limit)


def build_pdf_ocr(settings: Settings):
    from google import genai
    from google.genai import types as genai_types

    from app.local_documents.ocr import VertexPdfOcr

    model = settings.scientific.llm_model
    if settings.genai_use_vertex:
        project, location = settings.require_vertex_ai_config()
        return VertexPdfOcr(project, location, model)
    client = genai.Client(
        api_key=settings.require_gemini_api_key(),
        http_options=genai_types.HttpOptions(api_version="v1"),
    )
    return VertexPdfOcr("", "", model, client=client)
