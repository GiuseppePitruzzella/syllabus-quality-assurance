"""Schemas for the read-only normative corpus surface."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


CoreCriterionCode = Literal["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"]
CoreAgentCode = Literal["A1", "A2", "A3", "A4"]


class NormativeCorpusDocument(BaseModel):
    """One Markdown document in the versioned normative corpus.

    The payload is derived from ``data/normative_corpus`` plus
    ``data/tagging_rules.yaml``. It intentionally exposes only
    reproducibility metadata and criterion/agent tags: the full
    document body remains in the repository, not in the API payload.
    """

    document_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    version: str
    source_type: str
    priority: int
    filename: str
    file_hash: str = Field(..., min_length=64, max_length=64)
    file_size: int = Field(..., ge=0)
    chunk_count: int = Field(..., ge=0)
    core_chunk_count: int = Field(..., ge=0)
    core_criteria: list[CoreCriterionCode]
    agents: list[CoreAgentCode]
    is_core_source: bool
