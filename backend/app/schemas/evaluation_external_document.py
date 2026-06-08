"""Schema definition for the future ``evaluation_external_documents``
table (Phase 9.A — documentation only, persisted in 9.B).

Phase 9.B will:
  - add the SQLAlchemy model bound to ``Base`` (so
    ``Base.metadata.create_all`` creates the table on startup);
  - register the relationship on ``EvaluationResult``;
  - implement the resolver that writes a row per (run, criterion,
    document) tuple;
  - rewire ``DELETE /api/local-documents/{id}`` to query this
    table and fall back to soft-delete when the document is
    referenced by any past run.

In 9.A we only **declare** the contract: the Pydantic shape below
is the source of truth for the JSON payload the API exposes (via
``EvaluationResult.external_documents_used``) and for the
relational schema the migration in 9.B will create. This way the
contract can be reviewed without flipping a switch on
``create_all``.

Authoritative table layout (target, 9.B):

::

    evaluation_external_documents
    -----------------------------
    id                             integer  primary key
    evaluation_result_id           integer  fk -> evaluation_results.id
    local_document_id              integer  fk -> local_documents.id
    criterion_code                 text     "E1" | "E2" | "E3" | "E5"
    document_version_snapshot      integer  copy of local_documents.version at run time
    file_hash_snapshot             text     copy of local_documents.file_hash at run time
    document_type_snapshot         text     copy of local_documents.document_type at run time
    resolution_reason              text     "academic_year_match"
                                            | "explicit_selection"
                                            | "latest_available_fallback"
    created_at                     datetime

E4 is intentionally absent from the ``criterion_code`` set: the
cross-lingua criterion uses the syllabus's own ``*_en`` fields and
never resolves a registry document.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Closed enum of criterion codes the registry can resolve a
# document for. Excludes E4 by design (see module docstring).
RegistryServedCriterion = Literal["E1", "E2", "E3", "E5"]

# Why this specific document version was chosen for a run. The
# resolver in 9.B records the highest-priority reason that
# applies, in the order:
#   1. explicit_selection      — caller picked the version
#   2. academic_year_match     — academic_year matched the syllabus
#   3. latest_available_fallback — neither, but a row was indexed
ResolutionReason = Literal[
    "explicit_selection",
    "academic_year_match",
    "latest_available_fallback",
]


class ExternalDocumentRef(BaseModel):
    """One (criterion, document, version) tuple used by a run.

    Mirrors a single row of the future
    ``evaluation_external_documents`` table. The Pydantic class
    doubles as the JSON shape the API serves via
    ``EvaluationResult.external_documents_used``.

    Snapshot fields (``document_version_snapshot``,
    ``file_hash_snapshot``, ``document_type_snapshot``) freeze the
    state of the registry row at run time so a later edit on the
    registry — or an eventual hard delete in the rare cases that
    survives the Phase 9.B soft-delete guard — can't drift the
    historical context of a past evaluation.
    """

    criterion_code: RegistryServedCriterion = Field(
        ..., description='One of "E1", "E2", "E3", "E5". E4 is served by the syllabus itself.',
    )
    local_document_id: int = Field(
        ..., description="FK to local_documents.id at the time of the run.",
    )
    document_version_snapshot: int = Field(
        ..., description="The version of the document used by the run.",
    )
    file_hash_snapshot: str = Field(
        ..., description="sha256 of the file used by the run.",
    )
    document_type_snapshot: str = Field(
        ..., description="document_type at the time of the run.",
    )
    resolution_reason: ResolutionReason = Field(
        ..., description="Why this specific version was chosen for this run.",
    )
    created_at: datetime | None = Field(
        default=None,
        description=(
            "Populated by the DB on insert (9.B). May be None on "
            "the API request shape."
        ),
    )

    model_config = {"from_attributes": True}


__all__ = [
    "ExternalDocumentRef",
    "RegistryServedCriterion",
    "ResolutionReason",
]
