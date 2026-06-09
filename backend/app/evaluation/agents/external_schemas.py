"""Pydantic schemas for the A5 ExternalConsistencyAgent (Phase 9.C.1).

A5 lives outside the C1-C9 contract: its judgments are
**always** kept separate from ``AggregatedResult`` so that any
failure in the extended-criteria path can never demote a core
``completed`` run to ``partial``. The shapes below mirror the
core ones (``CriterionJudgment`` / ``AgentOutput``) where it
makes sense — but the differences are intentional:

  - ``ExtendedCriterionJudgment.criterion_code`` accepts
    ``E1..E5`` instead of ``C1..C9``.
  - ``evidences`` can cite either the syllabus (via
    ``source_field``) or an external registry document (via
    ``source_document_id`` + ``source_chunk_id``); the validator
    requires at least one of the two when a numeric score is set.
  - Per-handler prompt versions are recorded on
    ``ExtendedAgentOutput`` so each E* run is independently
    reproducible (mirrors D026 for the core agents).
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


# Single-letter prefix kept distinct from C1..C9 so the union of
# core + extended codes is unambiguous (used by the report
# synthesizer to render the right rubric section).
ExtendedCriterionCode = Literal["E1", "E2", "E3", "E4", "E5"]


class ExtendedEvidence(BaseModel):
    """A literal quote used as evidence for an extended judgment.

    The evidence can come from either the syllabus (``source_field``
    set, e.g. ``"prerequisites_it"``) or from an external registry
    document (``source_document_id`` set, optionally with
    ``source_chunk_id``). At least one of the two sources must be
    present — empty evidence is rejected by the validator.
    """

    text: str = Field(..., min_length=1, description="Literal quoted fragment")
    source_field: str | None = Field(
        default=None,
        description="Syllabus field name when the evidence comes from the syllabus.",
    )
    source_document_id: int | None = Field(
        default=None,
        description="local_document_id when the evidence comes from a registry doc.",
    )
    source_chunk_id: str | None = Field(
        default=None,
        description="Optional chunk id within the source document.",
    )

    @model_validator(mode="after")
    def _exactly_one_origin(self) -> "ExtendedEvidence":
        has_syllabus = self.source_field is not None and self.source_field.strip()
        has_document = self.source_document_id is not None
        if not has_syllabus and not has_document:
            raise ValueError(
                "evidence must cite either source_field (syllabus) or "
                "source_document_id (registry document)",
            )
        return self


class ExtendedCriterionJudgment(BaseModel):
    """Judgment for a single extended criterion.

    Dual-source rule (E1/E2/E3/E5): when ``score`` is a numeric
    value (0/1/2), the validator requires at least one evidence
    from the syllabus AND at least one evidence from an external
    document. This is the contract decision from 9.C — A5 must
    not produce a numeric score without grounding it on both
    sides.

    E4 is special-cased: the second side is the syllabus's own
    ``*_en`` field, which is itself recorded as ``source_field``
    (e.g. ``"learning_outcomes_en"``). So E4 numeric judgments
    require at least two distinct ``source_field`` values — one
    from the IT side and one from the EN side.

    NA judgments (``is_na=True``) are exempt from the dual-source
    rule.
    """

    criterion_code: ExtendedCriterionCode
    score: Literal[0, 1, 2] | None = None
    is_na: bool = False
    na_reason: str | None = None
    # ``is_na_technical`` flag: when True, the NA was forced by
    # the resolver (no applicable document) or by repeated
    # validation failures in the handler — NOT by a semantic
    # judgment of "non-applicable content". The report can show
    # both NA paths but the calibration in 9.F treats them
    # separately.
    is_na_technical: bool = False
    justification: str = Field(..., min_length=20)
    evidences: list[ExtendedEvidence] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"]

    @model_validator(mode="after")
    def _validate_score_na(self) -> "ExtendedCriterionJudgment":
        if self.is_na:
            if self.score is not None:
                raise ValueError("score must be null when is_na=true")
            if not self.na_reason or not self.na_reason.strip():
                raise ValueError("na_reason is required when is_na=true")
            return self
        if self.score is None:
            raise ValueError("score is required when is_na=false")
        if self.is_na_technical:
            raise ValueError(
                "is_na_technical can only be set together with is_na=true",
            )
        return self

    @model_validator(mode="after")
    def _validate_dual_source(self) -> "ExtendedCriterionJudgment":
        """Numeric scores require dual-source evidence.

        For E1/E2/E3/E5: at least one syllabus evidence (source_field)
        AND at least one external-document evidence (source_document_id).

        For E4: at least one IT-side syllabus evidence AND at least
        one EN-side syllabus evidence. Heuristic: source_field
        ending in ``_it`` vs ``_en``.
        """
        if self.is_na or self.score is None:
            return self
        if self.criterion_code == "E4":
            it_evidence = any(
                ev.source_field and ev.source_field.endswith("_it")
                for ev in self.evidences
            )
            en_evidence = any(
                ev.source_field and ev.source_field.endswith("_en")
                for ev in self.evidences
            )
            if not (it_evidence and en_evidence):
                raise ValueError(
                    "E4 numeric judgments require at least one IT-side "
                    "and one EN-side syllabus evidence",
                )
            return self
        # E1 / E2 / E3 / E5
        has_syllabus = any(ev.source_field for ev in self.evidences)
        has_document = any(
            ev.source_document_id is not None for ev in self.evidences
        )
        if not (has_syllabus and has_document):
            raise ValueError(
                f"{self.criterion_code} numeric judgments require dual-source "
                "evidence (syllabus + external document)",
            )
        return self


class ExtendedRetrievedChunkRef(BaseModel):
    """Compact reference to a registry chunk consumed by an E* handler.

    Mirrors ``RetrievedChunkRef`` from the core schemas but the
    document id is an integer (the registry FK) rather than the
    string-id used by the normative corpus.
    """

    criterion_code: ExtendedCriterionCode
    chunk_id: str
    local_document_id: int
    document_type: str
    document_version: int
    similarity_score: float | None = None


class ExtendedAgentOutput(BaseModel):
    """Output of the A5 coordinator — one bag of E* judgments.

    Kept separate from ``AgentOutput`` so the core aggregator can
    never accidentally include E* judgments in the C1-C9
    CoreScore.

    ``handler_prompt_versions`` records the version of each
    handler's prompt actually used in the run. Per E*: a string
    like ``"e1_v1"``. Mirrors ``DEFAULT_PROMPT_VERSIONS`` from the
    core service for D026 reproducibility.

    ``handler_errors`` records any exception caught at handler
    level. The presence of an entry here does NOT imply the
    criterion is missing from ``judgments`` — the coordinator
    must still emit a technical NA judgment for the criterion,
    so consumers see the criterion in both lists.
    """

    agent_code: Literal["A5"] = "A5"
    judgments: list[ExtendedCriterionJudgment]
    handler_prompt_versions: dict[str, str] = Field(default_factory=dict)
    handler_errors: dict[str, str] = Field(default_factory=dict)
    execution_metadata: dict[str, Any] = Field(default_factory=dict)
    retrieved_chunks: list[ExtendedRetrievedChunkRef] = Field(default_factory=list)


__all__ = [
    "ExtendedCriterionCode",
    "ExtendedEvidence",
    "ExtendedCriterionJudgment",
    "ExtendedRetrievedChunkRef",
    "ExtendedAgentOutput",
]
