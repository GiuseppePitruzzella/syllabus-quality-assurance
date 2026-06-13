"""HTTP response schemas for the evaluation endpoints.

Phase 5.4.H.2 introduced ``EvaluationCreated`` / ``EvaluationSummary``
/ ``EvaluationDetail``.

Phase 9.D.1 extends ``EvaluationDetail`` with two typed surfaces so
the frontend (Phase 9.D.2/3) and any external consumer can read the
A5 results without doing JSON archaeology on the opaque dump:

  - ``extended_criteria_result``: a normalised, *compact* Pydantic
    model with per-criterion judgments at top level, dropping the
    raw ``agent_output`` envelope. Per-criterion fields are
    typed (E1..E5 closed enum, score 0/1/2/null, NA source closed
    enum, ...) so the UI gets autocompletion and validation, and a
    drifted persisted value would surface as a clear schema error.

  - ``external_documents_used``: the audit-table view of which
    registry documents fed which extended criterion in this run.
    Each entry carries the snapshot fields (type, version, hash,
    resolution_reason) and joins the live ``LocalDocument`` row so
    the consumer can also show the title and a ``deleted_at`` flag
    when the document was soft-deleted post-run.

The methodological invariant is preserved at the type level:
``ExternalDocumentUsedPayload.criterion_code`` is a closed
``Literal["E1", "E2", "E3", "E5"]`` — never E4, which is served by
the syllabus itself and never produces an audit row by
construction.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ExtendedCriterionCode = Literal["E1", "E2", "E3", "E4", "E5"]
ExtendedNASource = Literal["resolver", "handler_na", "handler_error"]
ExtendedStatus = Literal["completed", "partial", "failed"]
ResolutionReason = Literal[
    "explicit_selection", "academic_year_match", "latest_available_fallback",
]
RegistryServedCriterion = Literal["E1", "E2", "E3", "E5"]


class EvaluationCreated(BaseModel):
    """Returned by ``POST /api/evaluate/{seuid}`` (status 202)."""

    evaluation_uuid: str


class EvaluateRequest(BaseModel):
    """Optional body of ``POST /api/evaluate/{seuid}`` (Phase 9.E.1).

    ``selected_document_ids`` lets the caller pin specific
    ``LocalDocument`` versions instead of letting the resolver pick
    via the standard precedence ladder
    (``academic_year_match`` → ``latest_available_fallback``).
    Criteria not covered by any explicit id continue to be
    resolved automatically — the override is *additive*, not
    exclusive.

    Validation rules (see service.validate_selected_document_ids):

      * no duplicates;
      * every id must exist and have ``status == "indexed"``;
      * archived documents (``deleted_at`` set) are rejected for new
        runs — historical reproducibility is provided by the
        existing audit table, not by allowing fresh runs against
        retired sources;
      * every id must belong to the syllabus's CdL;
      * every id must declare at least one ``enabled_criteria``
        (a document with ``enabled_criteria=[]`` is registry junk
        the resolver would silently skip — the API surfaces the
        error early).
    """

    selected_document_ids: list[int] | None = None


class EvaluationSummary(BaseModel):
    """Lightweight summary for history lists."""

    evaluation_uuid: str
    syllabus_seuid_snapshot: str
    course_name_snapshot: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    core_score: float | None = None
    coverage: float | None = None
    llm_model: str
    embedding_model: str
    prompt_versions: dict[str, Any]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Extended criteria payloads
# ---------------------------------------------------------------------------


class ExtendedEvidencePayload(BaseModel):
    """A single literal-quoted evidence from a Pydantic-validated A5 judgment.

    The shape mirrors ``ExtendedEvidence`` from
    ``app.evaluation.agents.external_schemas``, but is duplicated here
    on purpose: the schema there is the *agent-side contract* (with
    its own validators), this one is the *API-side contract*.
    Decoupling means a future agent-side tightening cannot
    silently break clients.
    """

    text: str
    source_field: str | None = None
    source_document_id: int | None = None
    source_chunk_id: str | None = None


class ExtendedJudgmentPayload(BaseModel):
    """One judgment for an extended criterion (E1..E5)."""

    criterion_code: ExtendedCriterionCode
    score: Literal[0, 1, 2] | None = None
    is_na: bool
    is_na_technical: bool = False
    na_reason: str | None = None
    justification: str
    evidences: list[ExtendedEvidencePayload] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"]


class ExtendedNAPayload(BaseModel):
    """A per-criterion NA record with its provenance.

    ``source`` is a closed enum:
      * ``resolver``: the resolver said the criterion is not
        applicable (e.g. no SUA-CdS available for E1). The handler
        was never invoked.
      * ``handler_na``: the handler ran and decided the criterion is
        semantically NA (e.g. the document has no applicable
        section). Counts as a legitimate criterion outcome.
      * ``handler_error``: the handler crashed or exhausted its
        validation retries. Counts as a *technical* NA — the UI
        should surface it distinctly from the previous two.
    """

    criterion_code: ExtendedCriterionCode
    source: ExtendedNASource
    reason: str


class ExtendedCriteriaResultPayload(BaseModel):
    """Compact, top-level shape of the A5 result for one run.

    Unlike the raw JSON dump stored in
    ``EvaluationResult.extended_criteria_result``, this model:
      * promotes ``judgments`` and ``handler_prompt_versions`` from
        the ``agent_output`` envelope to top level;
      * drops the rest of ``agent_output`` (execution_metadata,
        retrieved_chunks, ...) — they belong to a future debug
        endpoint, not to the user-facing detail.
    """

    status: ExtendedStatus
    criterion_scores: dict[str, int | None]
    na_criteria: list[ExtendedNAPayload] = Field(default_factory=list)
    handler_errors: dict[str, str] = Field(default_factory=dict)
    judgments: list[ExtendedJudgmentPayload] = Field(default_factory=list)
    handler_prompt_versions: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_dump(
        cls, raw: dict[str, Any] | None,
    ) -> "ExtendedCriteriaResultPayload | None":
        """Build a compact payload from the raw JSON dump.

        ``raw`` is what the persistence layer wrote to the column
        in Phase 9.C.5.3. ``None`` (legacy runs) propagates as
        ``None``: the consumer is expected to render an
        EmptyState. A *malformed* dump (missing required keys)
        is not silently coerced — Pydantic validation surfaces it.
        """
        if raw is None:
            return None
        agent_output = raw.get("agent_output") or {}
        return cls(
            status=raw.get("status"),
            criterion_scores=raw.get("criterion_scores") or {},
            na_criteria=raw.get("na_criteria") or [],
            handler_errors=raw.get("handler_errors") or {},
            judgments=agent_output.get("judgments") or [],
            handler_prompt_versions=(
                agent_output.get("handler_prompt_versions") or {}
            ),
        )


class ExternalDocumentUsedPayload(BaseModel):
    """One audit-table row, joined with the live document title.

    The ``criterion_code`` is typed as the closed
    ``RegistryServedCriterion`` set: E4 is excluded *by
    construction* because the C.5.1 audit-persistence path never
    writes rows for E4.

    ``deleted_at`` reflects the *current* state of the registry row.
    When set, the run consumed a document that has since been
    soft-deleted (Phase 9.B.3). The snapshot fields
    (``document_type``, ``document_version``, ``file_hash``) remain
    valid for reproducibility regardless.
    """

    criterion_code: RegistryServedCriterion
    local_document_id: int
    document_type: str
    document_version: int
    file_hash: str
    resolution_reason: ResolutionReason
    title: str | None = None
    deleted_at: datetime | None = None


# ---------------------------------------------------------------------------
# EvaluationDetail
# ---------------------------------------------------------------------------


class EvaluationDetail(EvaluationSummary):
    """Full payload — used by ``GET /api/evaluations/{evaluation_uuid}``."""

    embedding_dim: int
    llm_temperature: float
    llm_max_output_tokens: int
    rag_top_k: int
    rag_final_k: int
    rag_similarity_threshold: float
    gcp_project_id: str
    gcp_location: str

    error_message: str | None = None
    criterion_scores: dict[str, Any] | None = None
    na_criteria: list[Any] | None = None
    agent_outputs: dict[str, Any] | None = None
    agent_errors: dict[str, Any] | None = None
    retrieved_chunks: dict[str, Any] | None = None
    final_report: str | None = None

    # Phase 9.D.1 — typed extended surface.
    #
    # ``extended_criteria_result`` is ``None`` for legacy runs
    # produced before Phase 9.C.5.3 (the column was added then),
    # and the frontend renders an explicit EmptyState for that
    # case in 9.D.3.
    extended_criteria_result: ExtendedCriteriaResultPayload | None = None
    # ``external_documents_used`` is always a list (empty when no
    # registry document fed the run). The order is deterministic:
    # by criterion_code asc, then local_document_id asc.
    external_documents_used: list[ExternalDocumentUsedPayload] = Field(
        default_factory=list,
    )


# ---------------------------------------------------------------------------
# Phase 9.E.1 — resolution preview
# ---------------------------------------------------------------------------


class ResolutionPreviewCandidate(BaseModel):
    """One LocalDocument the resolver could pick for a given criterion.

    The candidate carries the audit-friendly snapshot fields and
    two display-only flags (``is_auto_resolved``, ``selectable``)
    so the frontend can render the radio/dropdown without
    additional queries.
    """

    local_document_id: int
    title: str
    document_type: str
    version: int
    file_hash: str
    academic_year: str
    enabled_criteria: list[str]
    # The resolver's pick (when ``is_auto_resolved=True``) carries
    # the precedence-ladder reason it was selected; alternatives
    # leave the field ``None``.
    is_auto_resolved: bool
    resolution_reason: ResolutionReason | None = None
    # Archived documents (``deleted_at`` set) are visible for
    # transparency but ``selectable=False`` — Phase 9.E policy:
    # historical reproducibility is provided by the audit table,
    # not by allowing fresh runs against retired sources.
    deleted_at: datetime | None = None
    selectable: bool


class ResolutionPreviewCriterion(BaseModel):
    """Per-extended-criterion view: who serves it, how it would resolve,
    what alternatives exist.

    ``served_by`` is the source of the criterion's evidence:
      * ``"registry"`` — E1/E2/E3/E5 use local documents;
      * ``"syllabus"`` — E4 uses the syllabus's own ``*_en`` fields;
      * ``"none"`` — no source is available (resolver hard-NA on
        registry-served criteria; ``has_english=False`` on E4).
    """

    criterion_code: ExtendedCriterionCode
    served_by: Literal["registry", "syllabus", "none"]
    applicable: bool
    na_reason: str | None = None
    # Empty for E4 (always) and for ``served_by="none"``.
    candidates: list[ResolutionPreviewCandidate] = Field(default_factory=list)


class ResolutionPreview(BaseModel):
    """Top-level resolution preview for one syllabus.

    Returned by ``GET /api/syllabi/{seuid}/resolution-preview``.
    Deterministic — the same syllabus + registry state always
    yields the same preview, including the per-criterion order
    of candidates (by ``local_document_id`` ascending).
    """

    seuid: str
    cdl_id: int
    academic_year: str | None = None
    has_english: bool
    by_criterion: dict[str, ResolutionPreviewCriterion]
