"""Tests for the A5 ExternalConsistencyAgent coordinator (Phase 9.C.4).

These tests use stub handlers (no LLM, no Chroma) so the
coordinator's contract can be exercised in isolation:

  * deterministic E1→E2→E3→E4→E5 order;
  * resolver hard-NA short-circuit (no handler invocation, no
    prompt_version, no chunks recorded);
  * ExternalHandlerError isolation (failure on Ek does not
    cascade to Ek+1...);
  * unexpected-exception isolation (same treatment for any
    Exception raised by a handler);
  * honest bookkeeping: handler_prompt_versions and
    retrieved_chunks reflect only handlers actually invoked /
    chunks actually returned;
  * end-to-end status via aggregate_extended: completed / partial
    / failed per the user's contract.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.evaluation.agents.external_consistency_agent import (
    EXTENDED_CRITERIA_ORDER,
    ExternalConsistencyAgent,
    build_default_handlers,
    resolver_na_map,
)
from app.evaluation.agents.external_handlers import (
    ExternalHandler,
    ExternalHandlerError,
    HandlerResult,
)
from app.evaluation.agents.external_schemas import (
    ExtendedCriterionJudgment,
    ExtendedRetrievedChunkRef,
)
from app.evaluation.extended_aggregator import aggregate_extended
from app.local_documents.resolver import (
    CriterionResolution,
    ResolvedDocument,
    ResolverOutput,
)


# ---------------------------------------------------------------------------
# Stub handlers
# ---------------------------------------------------------------------------


class _StubSuccessHandler(ExternalHandler):
    """A handler that returns a canned numeric judgment."""

    def __init__(self, criterion: str, *, score: int = 2, chunks: int = 1):
        super().__init__(llm_client=MagicMock())
        # ClassVars are typically set on the class, but stub objects
        # only live in tests so a per-instance assignment is fine.
        self.criterion_code = criterion  # type: ignore[assignment]
        self.prompt_version = f"{criterion.lower()}_v1"  # type: ignore[assignment]
        self._score = score
        self._chunks_count = chunks
        self.calls: list[dict[str, Any]] = []

    def evaluate(self, *, syllabus, cdl_id, document_ids):
        self.calls.append(
            {"syllabus": syllabus, "cdl_id": cdl_id, "document_ids": document_ids},
        )
        judgment = _make_judgment(
            self.criterion_code, score=self._score, document_id=(
                document_ids[0] if document_ids else None
            ),
        )
        chunks = [
            _make_chunk_ref(self.criterion_code, document_ids[0] if document_ids else 0, i)
            for i in range(self._chunks_count)
        ]
        return HandlerResult(
            judgment=judgment,
            retrieved_chunks=chunks,
            prompt_version=self.prompt_version,
            retry_count=0,
        )


class _StubRaisingHandler(ExternalHandler):
    """A handler that always raises ExternalHandlerError."""

    def __init__(self, criterion: str, *, message: str = "boom"):
        super().__init__(llm_client=MagicMock())
        self.criterion_code = criterion  # type: ignore[assignment]
        self.prompt_version = f"{criterion.lower()}_v1"  # type: ignore[assignment]
        self._message = message
        self.calls: list[dict[str, Any]] = []

    def evaluate(self, *, syllabus, cdl_id, document_ids):
        self.calls.append(
            {"syllabus": syllabus, "cdl_id": cdl_id, "document_ids": document_ids},
        )
        raise ExternalHandlerError(self.criterion_code, self._message)


class _StubUnexpectedHandler(ExternalHandler):
    """A handler that raises a non-ExternalHandlerError exception."""

    def __init__(self, criterion: str):
        super().__init__(llm_client=MagicMock())
        self.criterion_code = criterion  # type: ignore[assignment]
        self.prompt_version = f"{criterion.lower()}_v1"  # type: ignore[assignment]
        self.calls: list[dict[str, Any]] = []

    def evaluate(self, *, syllabus, cdl_id, document_ids):
        self.calls.append(
            {"syllabus": syllabus, "cdl_id": cdl_id, "document_ids": document_ids},
        )
        raise RuntimeError("something broke")


def _make_judgment(criterion, *, score, document_id) -> ExtendedCriterionJudgment:
    if criterion == "E4":
        evidences = [
            {"text": "RA in italiano", "source_field": "learning_outcomes_it"},
            {"text": "Learning outcomes in english", "source_field": "learning_outcomes_en"},
        ]
    else:
        evidences = [
            {"text": "Citazione dal syllabus", "source_field": "learning_outcomes_it"},
            {
                "text": "Citazione dal documento esterno",
                "source_document_id": document_id or 1,
            },
        ]
    return ExtendedCriterionJudgment(
        criterion_code=criterion,
        score=score,
        is_na=False,
        is_na_technical=False,
        na_reason=None,
        justification=(
            f"{criterion} è allineato in modo sostanziale; le evidenze "
            f"da entrambe le fonti sono coerenti con gli anchor del criterio."
        ),
        evidences=evidences,
        confidence="high",
    )


def _make_chunk_ref(criterion, document_id, idx) -> ExtendedRetrievedChunkRef:
    return ExtendedRetrievedChunkRef(
        criterion_code=criterion,
        chunk_id=f"external_{document_id}__chunk_{idx:04d}",
        local_document_id=document_id,
        document_type="sua_cds",
        document_version=1,
        similarity_score=0.85,
    )


# ---------------------------------------------------------------------------
# Resolver fixtures
# ---------------------------------------------------------------------------


def _resolved_doc(criterion, doc_id):
    return ResolvedDocument(
        criterion_code=criterion,
        local_document_id=doc_id,
        document_version_snapshot=1,
        file_hash_snapshot="abc",
        document_type_snapshot="sua_cds",
        resolution_reason="academic_year_match",
    )


def _resolver_all_applicable() -> ResolverOutput:
    """Every criterion applicable, one document per E1/E2/E3, two for E5."""
    return ResolverOutput(
        by_criterion={
            "E1": CriterionResolution(
                criterion_code="E1", applicable=True,
                documents=[_resolved_doc("E1", 42)],
            ),
            "E2": CriterionResolution(
                criterion_code="E2", applicable=True,
                documents=[_resolved_doc("E2", 51)],
            ),
            "E3": CriterionResolution(
                criterion_code="E3", applicable=True,
                documents=[_resolved_doc("E3", 77)],
            ),
            "E4": CriterionResolution(
                criterion_code="E4", applicable=True, documents=[],
            ),
            "E5": CriterionResolution(
                criterion_code="E5", applicable=True,
                documents=[_resolved_doc("E5", 11), _resolved_doc("E5", 12)],
            ),
        },
    )


def _resolver_all_hard_na() -> ResolverOutput:
    return ResolverOutput(
        by_criterion={
            "E1": CriterionResolution(
                criterion_code="E1", applicable=False,
                na_reason="no SUA-CdS available",
            ),
            "E2": CriterionResolution(
                criterion_code="E2", applicable=False,
                na_reason="matrice di tuning missing",
            ),
            "E3": CriterionResolution(
                criterion_code="E3", applicable=False,
                na_reason="regolamento didattico missing",
            ),
            "E4": CriterionResolution(
                criterion_code="E4", applicable=False,
                na_reason="has_english=False",
            ),
            "E5": CriterionResolution(
                criterion_code="E5", applicable=False,
                na_reason="no local-usage document",
            ),
        },
    )


def _syllabus():
    return SimpleNamespace(seuid="9999-TEST", course_name="Stub Course")


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def test_coordinator_rejects_incomplete_handler_bag():
    with pytest.raises(ValueError, match="E3"):
        ExternalConsistencyAgent(
            handlers={
                "E1": _StubSuccessHandler("E1"),
                "E2": _StubSuccessHandler("E2"),
                # missing E3 / E4 / E5
            },
        )


def test_coordinator_reorders_handler_bag_to_canonical_order():
    """Even if the caller passes a dict in shuffled order, the
    coordinator must iterate in the canonical order."""
    handlers = {
        "E5": _StubSuccessHandler("E5"),
        "E1": _StubSuccessHandler("E1"),
        "E3": _StubSuccessHandler("E3"),
        "E2": _StubSuccessHandler("E2"),
        "E4": _StubSuccessHandler("E4"),
    }
    agent = ExternalConsistencyAgent(handlers=handlers)
    output = agent.evaluate(
        syllabus=_syllabus(), cdl_id=3,
        resolver_output=_resolver_all_applicable(),
    )
    # Judgments come out in E1..E5 order.
    assert [j.criterion_code for j in output.judgments] == list(EXTENDED_CRITERIA_ORDER)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_all_applicable_all_handlers_succeed_yields_5_numeric_judgments():
    handlers = {c: _StubSuccessHandler(c) for c in EXTENDED_CRITERIA_ORDER}
    agent = ExternalConsistencyAgent(handlers=handlers)
    output = agent.evaluate(
        syllabus=_syllabus(), cdl_id=3,
        resolver_output=_resolver_all_applicable(),
    )
    # 5 numeric judgments, no errors, prompt_versions for all 5.
    assert len(output.judgments) == 5
    assert all(j.score == 2 for j in output.judgments)
    assert output.handler_errors == {}
    assert set(output.handler_prompt_versions.keys()) == set(EXTENDED_CRITERIA_ORDER)
    # Aggregator confirms status = completed.
    result = aggregate_extended(
        output,
        resolver_na=resolver_na_map(_resolver_all_applicable()),
    )
    assert result.status == "completed"


def test_handler_receives_document_ids_from_resolver():
    handlers = {c: _StubSuccessHandler(c) for c in EXTENDED_CRITERIA_ORDER}
    agent = ExternalConsistencyAgent(handlers=handlers)
    agent.evaluate(
        syllabus=_syllabus(), cdl_id=3,
        resolver_output=_resolver_all_applicable(),
    )
    assert handlers["E1"].calls[0]["document_ids"] == [42]
    assert handlers["E3"].calls[0]["document_ids"] == [77]
    assert handlers["E4"].calls[0]["document_ids"] == []
    assert handlers["E5"].calls[0]["document_ids"] == [11, 12]


def test_retrieved_chunks_consolidate_across_handlers():
    handlers = {
        "E1": _StubSuccessHandler("E1", chunks=2),
        "E2": _StubSuccessHandler("E2", chunks=1),
        "E3": _StubSuccessHandler("E3", chunks=1),
        "E4": _StubSuccessHandler("E4", chunks=0),  # E4 never adds chunks
        "E5": _StubSuccessHandler("E5", chunks=3),
    }
    agent = ExternalConsistencyAgent(handlers=handlers)
    output = agent.evaluate(
        syllabus=_syllabus(), cdl_id=3,
        resolver_output=_resolver_all_applicable(),
    )
    # 2 + 1 + 1 + 0 + 3 = 7 chunks, in E1..E5 order.
    assert len(output.retrieved_chunks) == 7
    criteria_in_order = [ref.criterion_code for ref in output.retrieved_chunks]
    # The first chunks must be E1, then E2, ..., and no E4 should appear.
    assert criteria_in_order[:2] == ["E1", "E1"]
    assert criteria_in_order[2] == "E2"
    assert criteria_in_order[3] == "E3"
    assert criteria_in_order[-3:] == ["E5", "E5", "E5"]
    assert "E4" not in criteria_in_order


# ---------------------------------------------------------------------------
# Resolver hard-NA
# ---------------------------------------------------------------------------


def test_resolver_hard_na_skips_handlers_and_emits_semantic_na():
    """Hard NA: handlers must not be invoked at all."""
    handlers = {c: _StubSuccessHandler(c) for c in EXTENDED_CRITERIA_ORDER}
    agent = ExternalConsistencyAgent(handlers=handlers)
    output = agent.evaluate(
        syllabus=_syllabus(), cdl_id=3,
        resolver_output=_resolver_all_hard_na(),
    )
    # 5 semantic NA judgments; none of them technical.
    assert len(output.judgments) == 5
    assert all(j.is_na is True for j in output.judgments)
    assert all(j.is_na_technical is False for j in output.judgments)
    # Resolver na_reason is preserved on each judgment.
    by_code = {j.criterion_code: j for j in output.judgments}
    assert "no SUA-CdS available" in (by_code["E1"].na_reason or "")
    assert "matrice di tuning missing" in (by_code["E2"].na_reason or "")
    # NO handler was invoked: zero calls, no prompt_versions, no errors, no chunks.
    for c in EXTENDED_CRITERIA_ORDER:
        assert handlers[c].calls == []
    assert output.handler_prompt_versions == {}
    assert output.handler_errors == {}
    assert output.retrieved_chunks == []
    # Aggregator: all-resolver-NA → completed (per C.1.fix).
    result = aggregate_extended(
        output, resolver_na=resolver_na_map(_resolver_all_hard_na()),
    )
    assert result.status == "completed"


def test_resolver_skipped_criteria_recorded_in_execution_metadata():
    handlers = {c: _StubSuccessHandler(c) for c in EXTENDED_CRITERIA_ORDER}
    agent = ExternalConsistencyAgent(handlers=handlers)
    # E2 / E4 hard-NA; the other three applicable.
    resolver = ResolverOutput(
        by_criterion={
            "E1": CriterionResolution(
                criterion_code="E1", applicable=True,
                documents=[_resolved_doc("E1", 42)],
            ),
            "E2": CriterionResolution(
                criterion_code="E2", applicable=False, na_reason="missing",
            ),
            "E3": CriterionResolution(
                criterion_code="E3", applicable=True,
                documents=[_resolved_doc("E3", 77)],
            ),
            "E4": CriterionResolution(
                criterion_code="E4", applicable=False, na_reason="has_english=False",
            ),
            "E5": CriterionResolution(
                criterion_code="E5", applicable=True,
                documents=[_resolved_doc("E5", 11)],
            ),
        },
    )
    output = agent.evaluate(
        syllabus=_syllabus(), cdl_id=3, resolver_output=resolver,
    )
    assert output.execution_metadata["resolver_skipped"] == ["E2", "E4"]
    assert output.execution_metadata["handlers_invoked"] == ["E1", "E3", "E5"]


# ---------------------------------------------------------------------------
# Per-handler error isolation
# ---------------------------------------------------------------------------


def test_handler_error_does_not_stop_subsequent_handlers():
    handlers: dict[str, ExternalHandler] = {
        "E1": _StubSuccessHandler("E1"),
        "E2": _StubRaisingHandler("E2", message="LLM timeout"),
        "E3": _StubSuccessHandler("E3"),
        "E4": _StubRaisingHandler("E4", message="parse error"),
        "E5": _StubSuccessHandler("E5"),
    }
    agent = ExternalConsistencyAgent(handlers=handlers)
    output = agent.evaluate(
        syllabus=_syllabus(), cdl_id=3,
        resolver_output=_resolver_all_applicable(),
    )
    # All 5 judgments emitted. The errored ones are technical NA.
    by_code = {j.criterion_code: j for j in output.judgments}
    assert by_code["E1"].score == 2
    assert by_code["E2"].is_na is True
    assert by_code["E2"].is_na_technical is True
    assert by_code["E3"].score == 2
    assert by_code["E4"].is_na is True
    assert by_code["E4"].is_na_technical is True
    assert by_code["E5"].score == 2
    # handler_errors records E2 and E4 only.
    assert set(output.handler_errors.keys()) == {"E2", "E4"}
    assert "LLM timeout" in output.handler_errors["E2"]
    assert "parse error" in output.handler_errors["E4"]
    # E3 / E5 ran successfully even though earlier handlers errored.
    assert handlers["E3"].calls and handlers["E5"].calls  # type: ignore[union-attr]
    # Aggregator: mix → partial.
    result = aggregate_extended(
        output,
        resolver_na=resolver_na_map(_resolver_all_applicable()),
    )
    assert result.status == "partial"


def test_unexpected_exception_is_isolated_like_handler_error():
    handlers: dict[str, ExternalHandler] = {
        "E1": _StubSuccessHandler("E1"),
        "E2": _StubUnexpectedHandler("E2"),  # raises RuntimeError
        "E3": _StubSuccessHandler("E3"),
        "E4": _StubSuccessHandler("E4"),
        "E5": _StubSuccessHandler("E5"),
    }
    agent = ExternalConsistencyAgent(handlers=handlers)
    output = agent.evaluate(
        syllabus=_syllabus(), cdl_id=3,
        resolver_output=_resolver_all_applicable(),
    )
    by_code = {j.criterion_code: j for j in output.judgments}
    assert by_code["E2"].is_na_technical is True
    assert "something broke" in output.handler_errors["E2"]
    # The other 4 still produced numeric judgments.
    for c in ("E1", "E3", "E4", "E5"):
        assert by_code[c].score == 2


def test_all_handlers_fail_yields_failed_status():
    handlers: dict[str, ExternalHandler] = {
        c: _StubRaisingHandler(c, message="LLM down") for c in EXTENDED_CRITERIA_ORDER
    }
    agent = ExternalConsistencyAgent(handlers=handlers)
    output = agent.evaluate(
        syllabus=_syllabus(), cdl_id=3,
        resolver_output=_resolver_all_applicable(),
    )
    assert all(j.is_na_technical for j in output.judgments)
    assert set(output.handler_errors.keys()) == set(EXTENDED_CRITERIA_ORDER)
    result = aggregate_extended(
        output,
        resolver_na=resolver_na_map(_resolver_all_applicable()),
    )
    assert result.status == "failed"


def test_handler_prompt_versions_only_recorded_for_invoked_handlers():
    """Resolver hard-NA on E2; the rest applicable; E5 errors."""
    handlers: dict[str, ExternalHandler] = {
        "E1": _StubSuccessHandler("E1"),
        "E2": _StubSuccessHandler("E2"),
        "E3": _StubSuccessHandler("E3"),
        "E4": _StubSuccessHandler("E4"),
        "E5": _StubRaisingHandler("E5", message="boom"),
    }
    agent = ExternalConsistencyAgent(handlers=handlers)
    resolver = ResolverOutput(
        by_criterion={
            "E1": CriterionResolution(
                criterion_code="E1", applicable=True,
                documents=[_resolved_doc("E1", 1)],
            ),
            "E2": CriterionResolution(
                criterion_code="E2", applicable=False, na_reason="missing",
            ),
            "E3": CriterionResolution(
                criterion_code="E3", applicable=True,
                documents=[_resolved_doc("E3", 3)],
            ),
            "E4": CriterionResolution(
                criterion_code="E4", applicable=True, documents=[],
            ),
            "E5": CriterionResolution(
                criterion_code="E5", applicable=True,
                documents=[_resolved_doc("E5", 5)],
            ),
        },
    )
    output = agent.evaluate(
        syllabus=_syllabus(), cdl_id=3, resolver_output=resolver,
    )
    # E2 was resolver-skipped → not in prompt_versions.
    # E5 errored → still in prompt_versions (handler WAS invoked).
    assert set(output.handler_prompt_versions.keys()) == {"E1", "E3", "E4", "E5"}
    # handler_errors only carries E5.
    assert set(output.handler_errors.keys()) == {"E5"}


# ---------------------------------------------------------------------------
# Missing-entry defence
# ---------------------------------------------------------------------------


def test_missing_resolver_entry_falls_through_to_technical_na():
    """If the resolver omitted a criterion altogether the coordinator
    must still emit a judgment for it (so all 5 codes appear in the
    output) and record the situation as a handler error."""
    handlers = {c: _StubSuccessHandler(c) for c in EXTENDED_CRITERIA_ORDER}
    agent = ExternalConsistencyAgent(handlers=handlers)
    # Resolver missing E3 entirely.
    resolver = ResolverOutput(
        by_criterion={
            "E1": CriterionResolution(
                criterion_code="E1", applicable=True,
                documents=[_resolved_doc("E1", 42)],
            ),
            "E2": CriterionResolution(
                criterion_code="E2", applicable=True,
                documents=[_resolved_doc("E2", 51)],
            ),
            "E4": CriterionResolution(
                criterion_code="E4", applicable=True, documents=[],
            ),
            "E5": CriterionResolution(
                criterion_code="E5", applicable=True,
                documents=[_resolved_doc("E5", 11)],
            ),
        },
    )
    output = agent.evaluate(
        syllabus=_syllabus(), cdl_id=3, resolver_output=resolver,
    )
    by_code = {j.criterion_code: j for j in output.judgments}
    assert by_code["E3"].is_na_technical is True
    assert "E3" in output.handler_errors


# ---------------------------------------------------------------------------
# build_default_handlers / resolver_na_map helpers
# ---------------------------------------------------------------------------


def test_build_default_handlers_covers_all_five_criteria():
    handlers = build_default_handlers(
        llm_client=MagicMock(), external_retriever=MagicMock(),
    )
    assert set(handlers.keys()) == set(EXTENDED_CRITERIA_ORDER)
    # Each criterion's handler self-reports its code.
    for code, h in handlers.items():
        assert h.criterion_code == code


def test_resolver_na_map_extracts_only_non_applicable_codes():
    resolver = ResolverOutput(
        by_criterion={
            "E1": CriterionResolution(
                criterion_code="E1", applicable=True,
                documents=[_resolved_doc("E1", 42)],
            ),
            "E2": CriterionResolution(
                criterion_code="E2", applicable=False, na_reason="missing",
            ),
            "E3": CriterionResolution(
                criterion_code="E3", applicable=False, na_reason=None,
            ),
            "E4": CriterionResolution(
                criterion_code="E4", applicable=True, documents=[],
            ),
            "E5": CriterionResolution(
                criterion_code="E5", applicable=True,
                documents=[_resolved_doc("E5", 11)],
            ),
        },
    )
    na = resolver_na_map(resolver)
    assert set(na.keys()) == {"E2", "E3"}
    assert na["E2"] == "missing"
    # Missing na_reason gets a fallback message rather than empty string.
    assert na["E3"] and na["E3"].strip()
