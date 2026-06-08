"""Deterministic resolver that picks the registry documents an
evaluation run will consume for the extended criteria E1-E5.

Phase 9.B.2 — service-layer only. No LLM call, no graph wiring.
Phase 9.C will plug this into ``EvaluationService`` (one
invocation per run, immediately before A5 starts).

Contract
--------

For each extended criterion ``E1`` / ``E2`` / ``E3`` / ``E5``, the
resolver enumerates every *document chain* — keyed on
``(cdl_id, document_type, normalized_title)`` — that the
:mod:`app.schemas.local_document::ALLOWED_CRITERIA_BY_DOCUMENT_TYPE`
contract says is admissible for that criterion. For each chain
the resolver picks the **latest** ``indexed`` and not-soft-deleted
version, then applies the precedence ladder:

1. ``explicit_selection`` — the caller supplied a
   ``selected_document_ids`` list; the version's id appears in it.
2. ``academic_year_match`` — the version's ``academic_year``
   matches the syllabus's after canonical normalisation
   (``2025/2026`` and ``2025-26`` both normalise to ``2025-2026``).
3. ``latest_available_fallback`` — neither, but the chain still
   has an ``indexed`` version. Tracked so an audit can later flag
   the run as having used a year-mismatched source.

If no chain produces an applicable version, the criterion is
reported as ``NA``.

E5 (and, by symmetry, E1 / E2 / E3 when the registry happens to
hold multiple chains for the same type — rare but legal)
admits multi-document resolutions: every applicable chain yields
one entry in the resolution list.

E4 (cross-lingua) does not use the registry. The resolver inspects
the syllabus's ``has_english`` flag and treats E4 as applicable
when it's true. A future refinement may look at the EN field
content; today it suffices because the syllabus parser already
materialises ``has_english`` from real EN content.

The resolver is pure (no I/O outside the DB query, no LLM, no
Chroma). Its output is the (deterministic, audit-friendly)
sequence of ``ExternalDocumentRef`` rows the orchestrator will
persist via the audit table — but persistence itself lives in
9.C, NOT here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.orm import Session

from app.models.local_document import LocalDocument
from app.schemas.evaluation_external_document import (
    RegistryServedCriterion,
    ResolutionReason,
)
from app.schemas.local_document import ALLOWED_CRITERIA_BY_DOCUMENT_TYPE

# Criteria that the registry serves; E4 is handled separately.
REGISTRY_SERVED: tuple[RegistryServedCriterion, ...] = ("E1", "E2", "E3", "E5")

# What status a registry row must hold to be a candidate for resolution.
_INDEXABLE_STATUS = "indexed"


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedDocument:
    """One applicable document for a criterion, with a typed reason."""

    criterion_code: RegistryServedCriterion
    local_document_id: int
    document_version_snapshot: int
    file_hash_snapshot: str
    document_type_snapshot: str
    resolution_reason: ResolutionReason


@dataclass(frozen=True)
class CriterionResolution:
    """The resolver's verdict for a single extended criterion.

    ``applicable`` is True when at least one document was resolved
    (or, for E4, when the syllabus has English content). Otherwise
    the criterion is NA and ``documents`` is empty.
    """

    criterion_code: Literal["E1", "E2", "E3", "E4", "E5"]
    applicable: bool
    documents: list[ResolvedDocument] = field(default_factory=list)
    # Free-text human reason — used in the EvaluationResult report
    # when the criterion is NA.
    na_reason: str | None = None


@dataclass(frozen=True)
class ResolverInput:
    """All the resolver needs to make decisions for a single run."""

    cdl_id: int
    academic_year: str | None
    has_english: bool
    selected_document_ids: list[int] | None = None


@dataclass(frozen=True)
class ResolverOutput:
    """Per-criterion verdict for the whole run."""

    by_criterion: dict[str, CriterionResolution]


# ---------------------------------------------------------------------------
# Academic-year normalisation
# ---------------------------------------------------------------------------


_AY_TWO_TOKENS = re.compile(r"^\s*(\d{4})[\s/\-_.]+(\d{2,4})\s*$")
_AY_SINGLE = re.compile(r"^\s*(\d{4})\s*$")


def normalise_academic_year(raw: str | None) -> str | None:
    """Map common academic-year writings to the canonical
    ``YYYY-YYYY`` form. Returns None when input is falsy or
    unrecognisable.

    Examples::

        "2025/2026"   -> "2025-2026"
        "2025-26"     -> "2025-2026"
        "2025"        -> "2025-2026"  (single-year shorthand)
        "  2025_2026" -> "2025-2026"
    """
    if not raw or not raw.strip():
        return None
    m = _AY_TWO_TOKENS.match(raw)
    if m:
        start, end = m.group(1), m.group(2)
        if len(end) == 2:
            end = start[:2] + end
        if len(end) != 4:
            return None
        return f"{start}-{end}"
    m = _AY_SINGLE.match(raw)
    if m:
        start = int(m.group(1))
        return f"{start}-{start + 1}"
    return None


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


class ExternalDocumentResolver:
    """Resolve extended-criteria sources for a single run.

    Constructed per request. The DB session is the only piece of
    state; everything else flows through :meth:`resolve`'s input.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def resolve(self, request: ResolverInput) -> ResolverOutput:
        normalised_year = normalise_academic_year(request.academic_year)
        selected = set(request.selected_document_ids or [])

        by_crit: dict[str, CriterionResolution] = {}

        # E1 / E2 / E3 / E5 — registry-served.
        for criterion in REGISTRY_SERVED:
            by_crit[criterion] = self._resolve_registry_criterion(
                criterion,
                cdl_id=request.cdl_id,
                normalised_year=normalised_year,
                selected_ids=selected,
            )

        # E4 — cross-lingua, served by the syllabus itself.
        by_crit["E4"] = self._resolve_cross_lingua(request.has_english)

        return ResolverOutput(by_criterion=by_crit)

    # ------------------------------------------------------------------
    # E1 / E2 / E3 / E5
    # ------------------------------------------------------------------

    def _resolve_registry_criterion(
        self,
        criterion: RegistryServedCriterion,
        *,
        cdl_id: int,
        normalised_year: str | None,
        selected_ids: set[int],
    ) -> CriterionResolution:
        # Which document_types are allowed to serve this criterion?
        allowed_types = [
            t
            for t, codes in ALLOWED_CRITERIA_BY_DOCUMENT_TYPE.items()
            if criterion in codes
        ]
        if not allowed_types:
            # Defensive: the contract guarantees at least one type
            # per criterion. Should be impossible in practice.
            return CriterionResolution(
                criterion_code=criterion,
                applicable=False,
                na_reason=(
                    f"no document type is admissible for criterion {criterion}"
                ),
            )

        # Pull every candidate row: indexed, not soft-deleted, on
        # the right CdL, the right type, the criterion in
        # `enabled_criteria` (which the registry guarantees is a
        # subset of allowed by Phase 9.A).
        candidates = (
            self._db.query(LocalDocument)
            .filter(LocalDocument.cdl_id == cdl_id)
            .filter(LocalDocument.document_type.in_(allowed_types))
            .filter(LocalDocument.status == _INDEXABLE_STATUS)
            .filter(LocalDocument.deleted_at.is_(None))
            .order_by(
                LocalDocument.document_type.asc(),
                LocalDocument.normalized_title.asc(),
                LocalDocument.version.desc(),
            )
            .all()
        )
        # Keep only rows whose enabled_criteria includes this
        # criterion (the JSON column can carry anything ⊆ allowed,
        # including the empty list — Phase 9.A.B's UI gating
        # prevents writing impossible values, but we re-check here
        # so a hand-edit in the DB can't tip the resolver into the
        # wrong document).
        candidates = [
            c for c in candidates
            if criterion in (c.enabled_criteria or [])
        ]

        if not candidates:
            return CriterionResolution(
                criterion_code=criterion,
                applicable=False,
                na_reason=(
                    f"no indexed document enabled for {criterion} "
                    f"on cdl_id={cdl_id}"
                ),
            )

        # Group candidates by chain (cdl_id, document_type,
        # normalized_title) so each chain contributes at most ONE
        # version to the resolution. We keep the highest version
        # per chain because the DB query already ordered by
        # version desc.
        by_chain: dict[tuple[int, str, str], list[LocalDocument]] = {}
        for c in candidates:
            key = (c.cdl_id, c.document_type, c.normalized_title)
            by_chain.setdefault(key, []).append(c)

        resolved: list[ResolvedDocument] = []
        for chain_rows in by_chain.values():
            doc = self._pick_chain_version(
                chain_rows,
                normalised_year=normalised_year,
                selected_ids=selected_ids,
            )
            if doc is None:
                continue
            resolved.append(
                ResolvedDocument(
                    criterion_code=criterion,
                    local_document_id=doc.row.id,
                    document_version_snapshot=doc.row.version,
                    file_hash_snapshot=doc.row.file_hash,
                    document_type_snapshot=doc.row.document_type,
                    resolution_reason=doc.reason,
                )
            )

        if not resolved:
            return CriterionResolution(
                criterion_code=criterion,
                applicable=False,
                na_reason=(
                    f"every candidate chain for {criterion} failed to "
                    f"produce an applicable version"
                ),
            )

        # Stable ordering: by document_id ascending so the output
        # is reproducible across runs with the same registry state.
        resolved.sort(key=lambda r: r.local_document_id)
        return CriterionResolution(
            criterion_code=criterion,
            applicable=True,
            documents=resolved,
        )

    def _pick_chain_version(
        self,
        chain_rows: list[LocalDocument],
        *,
        normalised_year: str | None,
        selected_ids: set[int],
    ) -> _Picked | None:
        # 1. Explicit selection: any row whose id was passed by the
        #    caller. Preserve the highest version among the
        #    explicitly selected ones.
        explicit = [r for r in chain_rows if r.id in selected_ids]
        if explicit:
            # chain_rows are already version desc; pick the first.
            return _Picked(row=explicit[0], reason="explicit_selection")

        # 2. Academic-year match.
        if normalised_year is not None:
            for r in chain_rows:
                if normalise_academic_year(r.academic_year) == normalised_year:
                    return _Picked(row=r, reason="academic_year_match")

        # 3. Latest available fallback.
        return _Picked(row=chain_rows[0], reason="latest_available_fallback")

    # ------------------------------------------------------------------
    # E4
    # ------------------------------------------------------------------

    def _resolve_cross_lingua(self, has_english: bool) -> CriterionResolution:
        if not has_english:
            return CriterionResolution(
                criterion_code="E4",
                applicable=False,
                na_reason=(
                    "syllabus has no English version available for "
                    "cross-lingua comparison"
                ),
            )
        return CriterionResolution(criterion_code="E4", applicable=True)


@dataclass(frozen=True)
class _Picked:
    row: LocalDocument
    reason: ResolutionReason


__all__ = [
    "ExternalDocumentResolver",
    "ResolverInput",
    "ResolverOutput",
    "CriterionResolution",
    "ResolvedDocument",
    "normalise_academic_year",
    "REGISTRY_SERVED",
]
