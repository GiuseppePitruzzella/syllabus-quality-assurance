"""Phase 8 — registry-side helpers for external/local documents.

This package owns the storage-side glue around the
`LocalDocument` registry: file path resolution / safety,
text extraction, and (later, in Phase 8.B.2) chunking + ingestion.
No knowledge of the evaluation graph lives here — A5 wiring is
Phase 9.
"""

from app.local_documents.extractors import (
    ExtractionError,
    extract_text,
    resolve_local_document_path,
)

__all__ = [
    "ExtractionError",
    "extract_text",
    "resolve_local_document_path",
]
