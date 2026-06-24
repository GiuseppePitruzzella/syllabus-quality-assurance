"""Tests for the LangGraph state module (snapshot + merge helpers)."""
from __future__ import annotations

from types import SimpleNamespace

from app.evaluation.agents.schemas import (
    AgentOutput,
    CriterionEvidence,
    CriterionJudgment,
)
from app.evaluation.state import (
    merge_agent_error,
    merge_agent_output,
    snapshot_syllabus,
)


def _output(agent_code: str, criterion: str) -> AgentOutput:
    return AgentOutput(
        agent_code=agent_code,
        judgments=[
            CriterionJudgment(
                criterion_code=criterion,
                score=2,
                is_na=False,
                na_reason=None,
                justification="Tutti gli elementi sono presenti e ben formulati.",
                evidences=[
                    CriterionEvidence(text="quote", source_field="course_content_it")
                ],
                confidence="high",
            )
        ],
        execution_metadata={},
    )


# ---------------------------------------------------------------------------
# snapshot_syllabus
# ---------------------------------------------------------------------------


def test_snapshot_includes_editorial_metadata_and_it_en_content():
    s = SimpleNamespace(
        course_code="9999X",
        course_name="Sample",
        module=None,
        teacher="Mario Rossi",
        academic_year="2025/2026",
        year_of_study=2,
        has_english=True,
        learning_outcomes_it="RA narrativi.",
        learning_outcomes_en="Narrative outcomes.",
        prerequisites_it="Algebra.",
        course_content_it="Topic A.",
        schedule_it=[{"numero": "1", "argomenti": "Intro"}],
    )
    snap = snapshot_syllabus(s)
    assert snap["course_code"] == "9999X"
    assert snap["teacher"] == "Mario Rossi"
    assert snap["learning_outcomes_it"] == "RA narrativi."
    assert snap["learning_outcomes_en"] == "Narrative outcomes."
    assert snap["schedule_it"] == [{"numero": "1", "argomenti": "Intro"}]


def test_snapshot_defaults_missing_fields_to_none():
    minimal = SimpleNamespace(course_name="X", has_english=False)
    snap = snapshot_syllabus(minimal)
    assert snap["course_name"] == "X"
    assert snap["has_english"] is False
    assert snap["prerequisites_it"] is None
    assert snap["learning_outcomes_en"] is None


def test_snapshot_accepts_dict_syllabus():
    snap = snapshot_syllabus({"course_name": "X", "course_content_it": "Body."})
    assert snap["course_name"] == "X"
    assert snap["course_content_it"] == "Body."


def test_snapshot_drops_unknown_fields():
    """Only the explicit field list is included; ad-hoc attributes are ignored."""
    s = SimpleNamespace(course_name="X", random_attr="should not appear")
    snap = snapshot_syllabus(s)
    assert "random_attr" not in snap


def test_snapshot_includes_english_title():
    """Verify that course_name_en is included in the snapshot."""
    row = {"course_name": "Visione", "course_name_en": "Computer Vision"}
    snap = snapshot_syllabus(row)
    assert snap.get("course_name_en") == "Computer Vision"


def test_snapshot_coerces_non_primitives_to_str():
    """SQLAlchemy may return e.g. a Decimal in non-content fields; coerce to str."""
    from decimal import Decimal

    s = SimpleNamespace(course_name="X", year_of_study=Decimal("2"))
    snap = snapshot_syllabus(s)
    assert snap["year_of_study"] in ("2", 2, Decimal("2"))


# ---------------------------------------------------------------------------
# merge_agent_output / merge_agent_error
# ---------------------------------------------------------------------------


def test_merge_agent_output_creates_dict_when_missing():
    out = _output("A1", "C1")
    patch = merge_agent_output({}, "A1", out)
    assert patch == {"agent_outputs": {"A1": out}}


def test_merge_agent_output_preserves_prior_entries():
    a1 = _output("A1", "C1")
    a2 = _output("A2", "C3")
    patch = merge_agent_output({"agent_outputs": {"A1": a1}}, "A2", a2)
    assert patch["agent_outputs"]["A1"] is a1
    assert patch["agent_outputs"]["A2"] is a2


def test_merge_agent_error_creates_both_entries():
    patch = merge_agent_error({}, "A1", "RuntimeError: oh no")
    assert patch["agent_outputs"] == {"A1": None}
    assert patch["agent_errors"] == {"A1": "RuntimeError: oh no"}


def test_merge_agent_error_preserves_prior_entries():
    a1 = _output("A1", "C1")
    state = {
        "agent_outputs": {"A1": a1},
        "agent_errors": {},
    }
    patch = merge_agent_error(state, "A2", "ValueError: bad json")
    assert patch["agent_outputs"]["A1"] is a1
    assert patch["agent_outputs"]["A2"] is None
    assert patch["agent_errors"] == {"A2": "ValueError: bad json"}
