import json
from pathlib import Path

import pytest

from app.evaluation.analysis.local_benchmark import (
    ReplayCase, assess_response, load_case, response_schema, summarise,
)


def case():
    return ReplayCase(
        case_id="a1_test", fixture_name="fixture.json", fixture_sha256="hash",
        agent_code="A1", seuid="test", prompt="original prompt", prompt_version="a1_v5",
        syllabus={"prerequisites_it": "Conoscenza di algebra lineare."}, criteria=["C5"],
        reference_scores={"C5": 1}, reference_latency_ms=1000,
    )


def answer(**updates):
    judgment = {"criterion_code": "C5", "score": 1, "is_na": False, "na_reason": None,
                "justification": "Prerequisiti specifici ma non sufficientemente articolati.",
                "confidence": "medium", "evidences": [
                    {"text": "algebra lineare", "source_field": "prerequisites_it"}]}
    judgment.update(updates)
    return json.dumps({"judgments": [judgment]})


def test_agreement_and_literal_evidence():
    assessment = assess_response(case(), answer())
    assert assessment["comparisons"][0]["agrees"] is True
    assert assessment["evidence_checks"][0]["verified"] is True


@pytest.mark.parametrize("evidence", [
    {"text": "algebra lineare", "source_field": "invented_field"},
    {"text": "programmazione avanzata", "source_field": "prerequisites_it"},
])
def test_fabricated_quotes_are_flagged(evidence):
    assessment = assess_response(case(), answer(evidences=[evidence]))
    assert assessment["evidence_checks"][0]["verified"] is False


def test_na_disagreement_is_not_silently_zero_error():
    assessment = assess_response(case(), answer(score=None, is_na=True, na_reason="Parser error"))
    assert assessment["comparisons"][0]["na_disagreement"] is True
    assert assessment["comparisons"][0]["absolute_error"] is None


@pytest.mark.parametrize("raw", [
    "```json\n{}\n```", '{"judgments": []}', answer(criterion_code="C1"),
    answer(score=4), answer(is_na=True), answer(evidences=[{"text": "", "source_field": "x"}]),
])
def test_malformed_domain_or_schema_is_not_success(raw):
    with pytest.raises(ValueError):
        assess_response(case(), raw)


def test_duplicate_criteria_rejected():
    parsed = json.loads(answer())
    parsed["judgments"] *= 2
    with pytest.raises(ValueError, match="duplicate"):
        assess_response(case(), json.dumps(parsed))


def test_failures_remain_in_denominator_and_empty_evidence_not_perfect():
    records = [
        {"status": "valid", "wall_seconds": 2,
         "assessment": assess_response(case(), answer(evidences=[]))},
        {"status": "error", "wall_seconds": 10},
    ]
    summary = summarise(records)
    assert summary["valid_rate"] == .5
    assert summary["median_wall_seconds"] == 6
    assert summary["evidence_verification_rate"] is None
    assert summary["judgments_without_evidence"] == 1
    assert summary["api_cost_usd"] == 0


def test_schema_constrains_owned_criteria():
    schema = response_schema(["C1", "C2", "C5"])
    assert schema["properties"]["judgments"]["minItems"] == 3
    assert schema["$defs"]["CriterionJudgment"]["properties"]["criterion_code"]["enum"] == [
        "C1", "C2", "C5"]


def test_all_committed_fixtures_replay_without_db_or_corpus():
    fixtures = Path(__file__).resolve().parents[2] / "fixtures/llm_responses"
    cases = [load_case(p) for p in fixtures.glob("a[1-4]_calibration_*.json")]
    assert len(cases) == 20
    assert {c.agent_code for c in cases} == {"A1", "A2", "A3", "A4"}
    assert all(c.syllabus and len(c.fixture_sha256) == 64 for c in cases)
