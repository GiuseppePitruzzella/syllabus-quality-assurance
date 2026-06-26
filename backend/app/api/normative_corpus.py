"""Read-only endpoints for the versioned normative corpus."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from app.config import settings
from app.evaluation.rag.corpus_manifest import list_normative_corpus_documents
from app.schemas.normative_corpus import NormativeCorpusDocument

router = APIRouter(prefix="/api/normative-corpus", tags=["normative-corpus"])


@router.get("/documents", response_model=list[NormativeCorpusDocument])
async def list_documents() -> list[NormativeCorpusDocument]:
    """Return the corpus documents that can feed C1-C9/CoreScore.

    The payload is derived from repository files and tagging rules. No
    ChromaDB, Vertex AI, or database access is needed.
    """

    return list_normative_corpus_documents(
        corpus_dir=Path(settings.normative_corpus_dir),
        tagging_rules_file=Path(settings.tagging_rules_file),
    )
