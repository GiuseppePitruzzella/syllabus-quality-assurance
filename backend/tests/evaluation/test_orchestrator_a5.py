"""Tests for the A5 wiring inside the LangGraph orchestrator (Phase 9.C.5.2).

The pre-existing four-agent tests (``test_orchestrator.py``) keep
working unchanged because they never supply a ``resolver_output``
in the initial state: the a5 node is then a no-op. These tests
cover the *active* A5 path, where the service-layer plumbing
already produced a :class:`ResolverOutput` and the orchestrator is
expected to:

  * run A5 sequentially after A4 (and never before);
  * keep ``agent_outputs`` core-only (A1..A4) — A5 lands in
    ``extended_agent_output`` instead, never in ``agent_outputs``;
  * compute ``extended_result`` in the aggregate node when a
    resolver was supplied;
  * leave the core ``status`` decoupled from A5 outcomes (A5
    completely failed → core run can still be ``completed``);
  * honour the ``external_agent_factory`` override (e.g. to inject
    a fake coordinator without touching Vertex / Chroma);
  * tolerate fresh installs where the external retriever is
    ``None`` — the a5 node is then skipped.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from app.evaluation.agents.external_schemas import (
    ExtendedAgentOutput,
    ExtendedCriterionJudgment,
)
from app.evaluation.agents.schemas import (
    AgentOutput,
    CriterionEvidence,
    CriterionJudgment,
)
from app.evaluation.orchestrator import build_graph
from app.local_documents.resolver import (
    CriterionResolution,
    ResolvedDocument,
    ResolverOutput,
)


# ---------------------------------------------------------------------------
# Fake A1..A4 agents (mirrors test_orchestrator helpers)
# ---------------------------------------------------------------------------


class _FakeAgent:
    def __init__(self, agent_code: str, output: AgentOutput | None,
                 exc: Exception | None = None):
        self.agent_code = agent_code
        self._output = output
        self._exc = exc

    def evaluate(self, syllabus: Any) -> AgentOutput:
        if self._exc is not None:
            raise self._exc
        return self._output


def _judgment(code: str, *, score: int = 2):
    return CriterionJudgment(
        criterion_code=code,
        score=score,
        is_na=False,
        justification=(
            f"Giudizio per {code} sufficientemente articolato per il validator."
        ),
        evidences=[
            CriterionEvidence(text=f"quote-{code}", source_field="course_content_it"),
        ],
        confidence="medium",
    )


def _build_core_outputs():
    return {
        "A1": AgentOutput(
            agent_code="A1",
            judgments=[_judgment("C1"), _judgment("C2"), _judgment("C5")],
            execution_metadata={"retry_count": 0},
        ),
        "A2": AgentOutput(
            agent_code="A2",
            judgments=[_judgment("C3"), _judgment("C4")],
            execution_metadata={"retry_count": 0},
        ),
        "A3": AgentOutput(
            agent_code="A3",
            judgments=[_judgment("C6"), _judgment("C7"), _judgment("C8")],
            execution_metadata={"retry_count": 0},
        ),
        "A4": AgentOutput(
            agent_code="A4",
            judgments=[_judgment("C9")],
            execution_metadata={"retry_count": 0},
        ),
    }


def _core_factory(outputs: dict[str, AgentOutput]):
    def _factory(agent_code: str, retriever: Any, llm_client: Any) -> _FakeAgent:
        return _FakeAgent(agent_code, outputs[agent_code])

    return _factory


# ---------------------------------------------------------------------------
# Fake A5 coordinator
# ---------------------------------------------------------------------------


def _e_judgment(code: str, *, score: int = 2, is_na: bool = False):
    if is_na:
        return ExtendedCriterionJudgment(
            criterion_code=code,
            score=None,
            is_na=True,
            is_na_technical=False,
            na_reason="documento non applicabile",
            justification=(
                "Il documento non contiene indicazioni applicabili al syllabus; "
                "criterio dichiarato NA semantico."
            ),
            evidences=[],
            confidence="medium",
        )
    if code == "E4":
        evidences = [
            {"text": "Conoscenza...", "source_field": "learning_outcomes_it"},
            {"text": "Knowledge...", "source_field": "learning_outcomes_en"},
        ]
    else:
        evidences = [
            {"text": "Citazione syllabus", "source_field": "learning_outcomes_it"},
            {"text": "Citazione documento esterno", "source_document_id": 42},
        ]
    return ExtendedCriterionJudgment(
        criterion_code=code,
        score=score,
        is_na=False,
        is_na_technical=False,
        justification=(
            f"{code} è allineato in modo sostanziale; le evidenze sono coerenti."
        ),
        evidences=evidences,
        confidence="high",
    )


class _FakeExternalAgent:
    """A coordinator-shaped object that returns a canned output."""

    agent_code = "A5"

    def __init__(self, *, output: ExtendedAgentOutput | None = None,
                 exc: Exception | None = None):
        self._output = output
        self._exc = exc
        self.evaluate_calls: list[dict[str, Any]] = []

    def evaluate(self, *, syllabus, cdl_id, resolver_output):
        self.evaluate_calls.append(
            {"syllabus": syllabus, "cdl_id": cdl_id, "resolver_output": resolver_output},
        )
        if self._exc is not None:
            raise self._exc
        return self._output


def _ext_output_all_success() -> ExtendedAgentOutput:
    return ExtendedAgentOutput(
        agent_code="A5",
        judgments=[
            _e_judgment("E1", score=2),
            _e_judgment("E2", score=1),
            _e_judgment("E3", score=2),
            _e_judgment("E4", score=2),
            _e_judgment("E5", score=1),
        ],
        handler_prompt_versions={
            "E1": "e1_v1", "E2": "e2_v1", "E3": "e3_v1",
            "E4": "e4_v1", "E5": "e5_v1",
        },
        handler_errors={},
        execution_metadata={"handlers_invoked": ["E1", "E2", "E3", "E4", "E5"]},
    )


def _ext_output_all_fail() -> ExtendedAgentOutput:
    """A5 ran but every handler crashed → all-technical-NA judgments."""
    return ExtendedAgentOutput(
        agent_code="A5",
        judgments=[
            ExtendedCriterionJudgment(
                criterion_code=c,
                score=None,
                is_na=True,
                is_na_technical=True,
                na_reason="errore tecnico: boom",
                justification=(
                    f"L'handler del criterio {c} non ha prodotto un giudizio valido."
                ),
                evidences=[],
                confidence="low",
            )
            for c in ("E1", "E2", "E3", "E4", "E5")
        ],
        handler_prompt_versions={
            "E1": "e1_v1", "E2": "e2_v1", "E3": "e3_v1",
            "E4": "e4_v1", "E5": "e5_v1",
        },
        handler_errors={c: "boom" for c in ("E1", "E2", "E3", "E4", "E5")},
        execution_metadata={"handlers_invoked": ["E1", "E2", "E3", "E4", "E5"]},
    )


# ---------------------------------------------------------------------------
# Resolver fixtures
# ---------------------------------------------------------------------------


def _resolved(code: str, doc_id: int) -> ResolvedDocument:
    return ResolvedDocument(
        criterion_code=code,
        local_document_id=doc_id,
        document_version_snapshot=1,
        file_hash_snapshot="hash",
        document_type_snapshot="sua_cds",
        resolution_reason="academic_year_match",
    )


def _resolver_all_applicable() -> ResolverOutput:
    return ResolverOutput(
        by_criterion={
            "E1": CriterionResolution(
                criterion_code="E1", applicable=True,
                documents=[_resolved("E1", 42)],
            ),
            "E2": CriterionResolution(
                criterion_code="E2", applicable=True,
                documents=[_resolved("E2", 51)],
            ),
            "E3": CriterionResolution(
                criterion_code="E3", applicable=True,
                documents=[_resolved("E3", 77)],
            ),
            "E4": CriterionResolution(
                criterion_code="E4", applicable=True, documents=[],
            ),
            "E5": CriterionResolution(
                criterion_code="E5", applicable=True,
                documents=[_resolved("E5", 11)],
            ),
        },
    )


def _resolver_all_hard_na() -> ResolverOutput:
    return ResolverOutput(
        by_criterion={
            "E1": CriterionResolution(criterion_code="E1", applicable=False,
                                       na_reason="no SUA"),
            "E2": CriterionResolution(criterion_code="E2", applicable=False,
                                       na_reason="no matrix"),
            "E3": CriterionResolution(criterion_code="E3", applicable=False,
                                       na_reason="no regolamento"),
            "E4": CriterionResolution(criterion_code="E4", applicable=False,
                                       na_reason="no EN"),
            "E5": CriterionResolution(criterion_code="E5", applicable=False,
                                       na_reason="no local doc"),
        },
    )


SNAPSHOT = {
    "course_name": "Test course",
    "has_english": True,
    "learning_outcomes_it": "RA",
    "course_content_it": "C",
    "assessment_methods_it": "V",
}


def _initial_state(resolver_output: ResolverOutput | None,
                   cdl_id: int | None = 3) -> dict[str, Any]:
    state: dict[str, Any] = {
        "syllabus_seuid": "SEUID-A5",
        "course_name": "Test course",
        "syllabus_snapshot": SNAPSHOT,
    }
    if resolver_output is not None:
        state["resolver_output"] = resolver_output
        state["cdl_id"] = cdl_id
    return state


# ---------------------------------------------------------------------------
# Active A5 path
# ---------------------------------------------------------------------------


def test_a5_runs_after_a4_and_populates_extended_agent_output():
    fake_a5 = _FakeExternalAgent(output=_ext_output_all_success())
    order: list[str] = []

    def core_factory_tracking(agent_code, retriever, llm_client):
        order.append(agent_code)
        return _FakeAgent(agent_code, _build_core_outputs()[agent_code])

    def ext_factory(_llm, _ret):
        order.append("A5")
        return fake_a5

    graph = build_graph(
        retriever=None,
        llm_client=None,
        external_retriever=MagicMock(),
        agent_factory=core_factory_tracking,
        external_agent_factory=ext_factory,
    )
    result = graph.invoke(_initial_state(_resolver_all_applicable()))

    # A5 ran AFTER A1..A4, never before.
    assert order == ["A1", "A2", "A3", "A4", "A5"]
    # Extended output landed in its own state slot.
    assert result["extended_agent_output"] is not None
    assert {j.criterion_code for j in result["extended_agent_output"].judgments} == {
        "E1", "E2", "E3", "E4", "E5"
    }
    # A5 receives cdl_id + resolver_output from the state.
    call = fake_a5.evaluate_calls[0]
    assert call["cdl_id"] == 3
    assert "E1" in call["resolver_output"].by_criterion


def test_agent_outputs_stays_core_only_with_a5_active():
    fake_a5 = _FakeExternalAgent(output=_ext_output_all_success())
    graph = build_graph(
        retriever=None,
        llm_client=None,
        external_retriever=MagicMock(),
        agent_factory=_core_factory(_build_core_outputs()),
        external_agent_factory=lambda _llm, _ret: fake_a5,
    )
    result = graph.invoke(_initial_state(_resolver_all_applicable()))
    # The four-agent contract holds: only A1..A4 appear in agent_outputs.
    assert set(result["agent_outputs"].keys()) == {"A1", "A2", "A3", "A4"}
    assert "A5" not in result["agent_outputs"]
    assert "A5" not in (result.get("agent_errors") or {})


def test_extended_result_is_computed_when_resolver_supplied():
    fake_a5 = _FakeExternalAgent(output=_ext_output_all_success())
    graph = build_graph(
        retriever=None,
        llm_client=None,
        external_retriever=MagicMock(),
        agent_factory=_core_factory(_build_core_outputs()),
        external_agent_factory=lambda _llm, _ret: fake_a5,
    )
    result = graph.invoke(_initial_state(_resolver_all_applicable()))
    ext = result["extended_result"]
    assert ext.status == "completed"
    assert ext.criterion_scores == {
        "E1": 2, "E2": 1, "E3": 2, "E4": 2, "E5": 1,
    }
    assert ext.handler_errors == {}


# ---------------------------------------------------------------------------
# Core / extended decoupling
# ---------------------------------------------------------------------------


def test_a5_failure_keeps_core_status_completed():
    """A5 raises → extended_agent_output=None, extended_result status=failed,
    BUT core run status stays ``completed``."""
    fake_a5 = _FakeExternalAgent(exc=RuntimeError("Vertex down"))
    graph = build_graph(
        retriever=None,
        llm_client=None,
        external_retriever=MagicMock(),
        agent_factory=_core_factory(_build_core_outputs()),
        external_agent_factory=lambda _llm, _ret: fake_a5,
    )
    result = graph.invoke(_initial_state(_resolver_all_applicable()))
    # Core completed: A1..A4 all scored 2.
    assert result["status"] == "completed"
    assert result["aggregation"].status == "completed"
    assert result["aggregation"].core_score == 2.0
    # A5 path: failed.
    assert result["extended_agent_output"] is None
    assert result["extended_result"].status == "failed"


def test_a5_all_handlers_failing_keeps_core_status_completed():
    """A5 returned an output but every E* is technical NA → extended_result
    status=failed; core unaffected."""
    fake_a5 = _FakeExternalAgent(output=_ext_output_all_fail())
    graph = build_graph(
        retriever=None,
        llm_client=None,
        external_retriever=MagicMock(),
        agent_factory=_core_factory(_build_core_outputs()),
        external_agent_factory=lambda _llm, _ret: fake_a5,
    )
    result = graph.invoke(_initial_state(_resolver_all_applicable()))
    assert result["status"] == "completed"
    assert result["extended_result"].status == "failed"
    assert set(result["extended_result"].handler_errors.keys()) == {
        "E1", "E2", "E3", "E4", "E5",
    }


def test_a5_all_resolver_na_yields_completed_extended_without_invoking_factory():
    """When the resolver hard-NAs every criterion, the coordinator's
    output may be ``None`` (factory may decide not to run, or just
    short-circuit) — the aggregator still produces extended_result
    with status='completed' (per Phase 9.C.1.fix)."""
    factory_calls: list[Any] = []

    def ext_factory(_llm, _ret):
        factory_calls.append("called")
        return _FakeExternalAgent(
            output=ExtendedAgentOutput(
                agent_code="A5",
                judgments=[],
                handler_prompt_versions={},
                handler_errors={},
                execution_metadata={},
            ),
        )

    graph = build_graph(
        retriever=None,
        llm_client=None,
        external_retriever=MagicMock(),
        agent_factory=_core_factory(_build_core_outputs()),
        external_agent_factory=ext_factory,
    )
    result = graph.invoke(_initial_state(_resolver_all_hard_na()))
    # Factory was still called once (we always go through a5 node when
    # resolver is supplied), but the aggregator collapses all-resolver-NA
    # to completed.
    assert len(factory_calls) == 1
    assert result["extended_result"].status == "completed"
    assert result["status"] == "completed"
    assert all(
        r.source == "resolver" for r in result["extended_result"].na_criteria
    )


# ---------------------------------------------------------------------------
# Skip semantics
# ---------------------------------------------------------------------------


def test_no_resolver_in_initial_state_skips_a5_entirely():
    """Legacy four-agent path. ``resolver_output`` missing →
    extended_agent_output absent, no extended_result computed."""
    fake_a5 = _FakeExternalAgent(output=_ext_output_all_success())
    graph = build_graph(
        retriever=None,
        llm_client=None,
        external_retriever=MagicMock(),
        agent_factory=_core_factory(_build_core_outputs()),
        external_agent_factory=lambda _llm, _ret: fake_a5,
    )
    # Initial state with NO resolver_output (legacy test invocation).
    result = graph.invoke({
        "syllabus_seuid": "SEUID",
        "course_name": "Test",
        "syllabus_snapshot": SNAPSHOT,
    })
    assert fake_a5.evaluate_calls == []
    assert "extended_agent_output" not in result or result.get("extended_agent_output") is None
    assert result.get("extended_result") is None


def test_external_factory_returns_none_when_external_retriever_is_none():
    """Fresh DB path: ``external_retriever=None`` → the default factory
    returns None and A5 is a no-op even when resolver_output is supplied."""
    # Use the DEFAULT external_agent_factory; pass external_retriever=None.
    graph = build_graph(
        retriever=None,
        llm_client=None,
        external_retriever=None,
        agent_factory=_core_factory(_build_core_outputs()),
        # default external_agent_factory
    )
    result = graph.invoke(_initial_state(_resolver_all_applicable()))
    # A5 skipped → no extended_agent_output.
    assert result.get("extended_agent_output") is None
    # But the aggregator still produces extended_result because the
    # resolver IS supplied — and with no A5 output it computes
    # status="failed" (some criteria were applicable). That signals
    # an operational misconfiguration in the report.
    assert result["extended_result"] is not None
    # Core status untouched.
    assert result["status"] == "completed"


def test_a5_path_isolated_from_a1_a2_a3_a4_failures():
    """A core agent failure must not prevent A5 from running."""
    outputs = _build_core_outputs()
    outputs["A2"] = None  # A2 will raise
    errors = {"A2": RuntimeError("LLM crashed in A2")}

    def factory(agent_code, retriever, llm_client):
        if agent_code in errors:
            return _FakeAgent(agent_code, None, exc=errors[agent_code])
        return _FakeAgent(agent_code, outputs[agent_code])

    fake_a5 = _FakeExternalAgent(output=_ext_output_all_success())
    graph = build_graph(
        retriever=None,
        llm_client=None,
        external_retriever=MagicMock(),
        agent_factory=factory,
        external_agent_factory=lambda _llm, _ret: fake_a5,
    )
    result = graph.invoke(_initial_state(_resolver_all_applicable()))
    # Core partial (A2 errored).
    assert result["status"] == "partial"
    # A5 still ran and produced its output.
    assert fake_a5.evaluate_calls
    assert result["extended_agent_output"] is not None
    assert result["extended_result"].status == "completed"
