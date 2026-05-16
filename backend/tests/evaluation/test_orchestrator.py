"""End-to-end tests for the LangGraph orchestrator.

Every test uses fake agent classes injected through ``agent_factory``:
no Vertex AI calls, no ChromaDB queries, fully deterministic.

We focus on graph topology + error containment + state propagation.
The aggregate/synthesizer logic is exercised by their own test modules.
"""
from __future__ import annotations

from typing import Any

from app.evaluation.agents.schemas import (
    AgentOutput,
    CriterionEvidence,
    CriterionJudgment,
)
from app.evaluation.orchestrator import build_graph


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeAgent:
    """Minimal stand-in for any BaseAgent subclass."""

    def __init__(self, agent_code: str, output: AgentOutput | None, exc: Exception | None = None):
        self.agent_code = agent_code
        self._output = output
        self._exc = exc
        self.evaluate_calls: list[Any] = []

    def evaluate(self, syllabus: Any) -> AgentOutput:
        self.evaluate_calls.append(syllabus)
        if self._exc is not None:
            raise self._exc
        return self._output


def _judgment(code: str, *, score: int | None = 2, is_na: bool = False, na_reason: str | None = None):
    return CriterionJudgment(
        criterion_code=code,
        score=score,
        is_na=is_na,
        na_reason=na_reason,
        justification=f"Giudizio per {code} sufficientemente articolato per superare la validation.",
        evidences=[
            CriterionEvidence(text=f"quote-{code}", source_field="course_content_it")
        ],
        confidence="medium",
    )


def _build_outputs(*, all_two: bool = True) -> dict[str, AgentOutput]:
    """Return canned AgentOutput for each agent code."""
    score = 2 if all_two else 1
    return {
        "A1": AgentOutput(
            agent_code="A1",
            judgments=[
                _judgment("C1", score=score),
                _judgment("C2", score=score),
                _judgment("C5", score=score),
            ],
            execution_metadata={"retry_count": 0},
        ),
        "A2": AgentOutput(
            agent_code="A2",
            judgments=[_judgment("C3", score=score), _judgment("C4", score=score)],
            execution_metadata={"retry_count": 0},
        ),
        "A3": AgentOutput(
            agent_code="A3",
            judgments=[
                _judgment("C6", score=score),
                _judgment("C7", score=score),
                _judgment("C8", score=score),
            ],
            execution_metadata={"retry_count": 0},
        ),
        "A4": AgentOutput(
            agent_code="A4",
            judgments=[_judgment("C9", score=score)],
            execution_metadata={"retry_count": 0},
        ),
    }


def _make_factory(
    outputs: dict[str, AgentOutput | None] | None = None,
    errors: dict[str, Exception] | None = None,
):
    """Return an ``agent_factory`` that emits the per-code outputs/errors."""
    outputs = outputs or {}
    errors = errors or {}

    def _factory(agent_code: str, retriever: Any, llm_client: Any) -> _FakeAgent:
        return _FakeAgent(agent_code, outputs.get(agent_code), errors.get(agent_code))

    return _factory


_SYLLABUS_SNAPSHOT = {
    "course_name": "Sample course",
    "has_english": True,
    "learning_outcomes_it": "RA narrativi.",
    "course_content_it": "Topic A.",
    "assessment_methods_it": "Esame orale.",
}


def _initial_state(snapshot: dict | None = None) -> dict[str, Any]:
    return {
        "syllabus_seuid": "SEUID-TEST",
        "course_name": "Sample course",
        "syllabus_snapshot": snapshot or _SYLLABUS_SNAPSHOT,
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_graph_runs_all_four_agents_in_order_when_no_errors():
    outputs = _build_outputs(all_two=True)
    invocations: list[str] = []

    def tracking_factory(agent_code: str, retriever: Any, llm_client: Any) -> _FakeAgent:
        invocations.append(agent_code)
        return _FakeAgent(agent_code, outputs[agent_code])

    graph = build_graph(retriever=None, llm_client=None, agent_factory=tracking_factory)
    result = graph.invoke(_initial_state())

    assert invocations == ["A1", "A2", "A3", "A4"]
    assert result["status"] == "completed"
    assert result["aggregation"].core_score == 2.0
    assert result["aggregation"].coverage == 1.0
    assert result["final_report"].startswith("# Report di valutazione — Sample course")


def test_graph_populates_agent_outputs_dict_for_all_agents():
    outputs = _build_outputs()
    graph = build_graph(None, None, agent_factory=_make_factory(outputs))
    result = graph.invoke(_initial_state())

    assert set(result["agent_outputs"].keys()) == {"A1", "A2", "A3", "A4"}
    assert all(v is not None for v in result["agent_outputs"].values())
    assert result["agent_errors"] == {}


def test_graph_sets_started_at_and_finished_at():
    graph = build_graph(None, None, agent_factory=_make_factory(_build_outputs()))
    result = graph.invoke(_initial_state())

    assert result["started_at"] is not None
    assert result["finished_at"] is not None
    assert result["finished_at"] >= result["started_at"]


def test_caller_provides_snapshot_via_snapshot_syllabus_helper():
    """The caller is responsible for snapshotting BEFORE invoking the graph.

    The orchestrator never receives the raw SQLAlchemy row: only the
    plain-dict snapshot. The state.snapshot_syllabus helper exists for
    the caller (e.g. the EvaluationService in 5.4.H) to make this easy.
    """
    from types import SimpleNamespace

    from app.evaluation.state import snapshot_syllabus

    raw = SimpleNamespace(
        course_name="Deep Learning",
        has_english=True,
        learning_outcomes_it="RA",
    )
    snapshot = snapshot_syllabus(raw)
    graph = build_graph(None, None, agent_factory=_make_factory(_build_outputs()))
    result = graph.invoke({"syllabus_seuid": "X", "syllabus_snapshot": snapshot})

    snap = result["syllabus_snapshot"]
    assert snap["course_name"] == "Deep Learning"
    assert snap["learning_outcomes_it"] == "RA"


# ---------------------------------------------------------------------------
# Error containment (partial)
# ---------------------------------------------------------------------------


def test_one_agent_failure_yields_partial_status_and_continues_graph():
    outputs = _build_outputs()
    outputs["A2"] = None  # A2 will raise
    errors = {"A2": RuntimeError("LLM crashed in A2")}

    graph = build_graph(None, None, agent_factory=_make_factory(outputs, errors))
    result = graph.invoke(_initial_state())

    assert result["status"] == "partial"
    # Three agents succeeded.
    assert result["agent_outputs"]["A1"] is not None
    assert result["agent_outputs"]["A3"] is not None
    assert result["agent_outputs"]["A4"] is not None
    # A2 has None in outputs and an entry in errors.
    assert result["agent_outputs"]["A2"] is None
    assert "A2" in result["agent_errors"]
    assert "RuntimeError" in result["agent_errors"]["A2"]
    # Aggregation marks C3 and C4 as NA tecnico from agent_error.
    agg = result["aggregation"]
    assert agg.criterion_scores["C3"] is None
    assert agg.criterion_scores["C4"] is None
    na_codes = {r.criterion_code: r for r in agg.na_criteria}
    assert na_codes["C3"].source == "agent_error"
    assert na_codes["C4"].source == "agent_error"
    # Report still gets produced.
    assert result["final_report"]
    assert "## Criteri non valutati" in result["final_report"]


def test_multiple_agent_failures_still_partial_when_some_run():
    outputs = _build_outputs()
    outputs["A3"] = None
    outputs["A4"] = None
    errors = {
        "A3": ValueError("schema parsing error"),
        "A4": RuntimeError("safety filter"),
    }

    graph = build_graph(None, None, agent_factory=_make_factory(outputs, errors))
    result = graph.invoke(_initial_state())

    assert result["status"] == "partial"
    # 4 criteria valutati (C1, C2, C5, C3, C4) -> 5/9 coverage
    agg = result["aggregation"]
    assert agg.coverage == 5 / 9
    # C6/C7/C8 (A3) + C9 (A4) all NA tecnico.
    for code in ("C6", "C7", "C8", "C9"):
        assert agg.criterion_scores[code] is None


# ---------------------------------------------------------------------------
# All agents fail (failed status)
# ---------------------------------------------------------------------------


def test_all_agents_failure_yields_failed_status():
    errors = {
        "A1": RuntimeError("boom"),
        "A2": RuntimeError("boom"),
        "A3": RuntimeError("boom"),
        "A4": RuntimeError("boom"),
    }
    outputs = {"A1": None, "A2": None, "A3": None, "A4": None}

    graph = build_graph(None, None, agent_factory=_make_factory(outputs, errors))
    result = graph.invoke(_initial_state())

    assert result["status"] == "failed"
    agg = result["aggregation"]
    assert agg.core_score is None
    assert agg.coverage == 0.0
    assert len(agg.na_criteria) == 9
    # All NA records carry agent_error as source.
    assert {r.source for r in agg.na_criteria} == {"agent_error"}
    # Report still produced, with the failure banner.
    assert "Tutti gli agenti specialistici hanno incontrato un errore" in result["final_report"]


# ---------------------------------------------------------------------------
# Mix of valid scores + explicit NA
# ---------------------------------------------------------------------------


def test_explicit_na_judgment_is_preserved_and_status_stays_completed():
    outputs = _build_outputs()
    # A1 returns C2 as is_na=True with a parsing reason.
    outputs["A1"] = AgentOutput(
        agent_code="A1",
        judgments=[
            _judgment("C1", score=2),
            _judgment(
                "C2",
                score=None,
                is_na=True,
                na_reason="campo learning_outcomes_en non recuperato",
            ),
            _judgment("C5", score=2),
        ],
        execution_metadata={"retry_count": 0},
    )

    graph = build_graph(None, None, agent_factory=_make_factory(outputs))
    result = graph.invoke(_initial_state())

    assert result["status"] == "completed"  # all agents ran -> still completed
    agg = result["aggregation"]
    assert agg.criterion_scores["C2"] is None
    # Core = mean of 8 valid 2s = 2.0
    assert agg.core_score == 2.0
    # NA record with source="agent" (explicit), not "agent_error".
    na = next(r for r in agg.na_criteria if r.criterion_code == "C2")
    assert na.source == "agent"
    assert "non recuperato" in na.reason


# ---------------------------------------------------------------------------
# Coverage / CoreScore math through the graph
# ---------------------------------------------------------------------------


def test_mixed_scores_through_graph_produce_correct_core_score():
    """Six 2s and three 1s -> CoreScore = (12+3)/9 = 1.67."""
    outputs = {
        "A1": AgentOutput(
            agent_code="A1",
            judgments=[
                _judgment("C1", score=2),
                _judgment("C2", score=1),
                _judgment("C5", score=1),
            ],
            execution_metadata={"retry_count": 0},
        ),
        "A2": AgentOutput(
            agent_code="A2",
            judgments=[_judgment("C3", score=2), _judgment("C4", score=2)],
            execution_metadata={"retry_count": 0},
        ),
        "A3": AgentOutput(
            agent_code="A3",
            judgments=[
                _judgment("C6", score=2),
                _judgment("C7", score=2),
                _judgment("C8", score=2),
            ],
            execution_metadata={"retry_count": 0},
        ),
        "A4": AgentOutput(
            agent_code="A4",
            judgments=[_judgment("C9", score=1)],
            execution_metadata={"retry_count": 0},
        ),
    }
    graph = build_graph(None, None, agent_factory=_make_factory(outputs))
    result = graph.invoke(_initial_state())

    assert result["aggregation"].core_score == 1.67
    assert result["aggregation"].coverage == 1.0
    assert result["aggregation"].status == "completed"


# ---------------------------------------------------------------------------
# Snapshot is passed to agents
# ---------------------------------------------------------------------------


def test_agents_receive_syllabus_snapshot_not_raw_row():
    """The agents' ``evaluate(...)`` is invoked with the dict snapshot.

    This guards against a regression where the graph passes the
    SQLAlchemy row through instead of the snapshot.
    """
    seen_inputs: dict[str, Any] = {}

    def recording_factory(agent_code: str, retriever: Any, llm_client: Any):
        agent = _FakeAgent(agent_code, _build_outputs()[agent_code])
        original = agent.evaluate

        def _spy(syllabus):
            seen_inputs[agent_code] = syllabus
            return original(syllabus)

        agent.evaluate = _spy  # type: ignore[method-assign]
        return agent

    graph = build_graph(None, None, agent_factory=recording_factory)
    graph.invoke(_initial_state())

    for code in ("A1", "A2", "A3", "A4"):
        assert isinstance(seen_inputs[code], dict)
        assert seen_inputs[code]["course_name"] == "Sample course"


# ---------------------------------------------------------------------------
# Defensive: prepare_context requires syllabus input
# ---------------------------------------------------------------------------


def test_graph_raises_when_no_syllabus_provided():
    import pytest

    graph = build_graph(None, None, agent_factory=_make_factory(_build_outputs()))
    with pytest.raises(ValueError, match="syllabus_snapshot"):
        graph.invoke({"syllabus_seuid": "X"})
