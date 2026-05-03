import pytest
from pydantic import ValidationError

from app.evaluation.agents.schemas import AgentInput, AgentOutput, CriterionJudgment


def test_criterion_judgment_requires_score_when_not_na():
    with pytest.raises(ValidationError, match="score is required"):
        CriterionJudgment.model_validate(
            {
                "criterion_code": "C1",
                "score": None,
                "is_na": False,
                "justification": "Giustificazione sufficientemente lunga.",
                "evidences": [],
                "confidence": "medium",
            }
        )


def test_criterion_judgment_requires_na_reason_when_na():
    with pytest.raises(ValidationError, match="na_reason is required"):
        CriterionJudgment.model_validate(
            {
                "criterion_code": "C1",
                "score": None,
                "is_na": True,
                "justification": "Giustificazione sufficientemente lunga.",
                "evidences": [],
                "confidence": "low",
            }
        )


def test_criterion_judgment_rejects_score_when_na():
    with pytest.raises(ValidationError, match="score must be null"):
        CriterionJudgment.model_validate(
            {
                "criterion_code": "C1",
                "score": 0,
                "is_na": True,
                "na_reason": "Campo non recuperato.",
                "justification": "Giustificazione sufficientemente lunga.",
                "evidences": [],
                "confidence": "low",
            }
        )


def test_agent_input_and_output_validate_minimal_payloads():
    agent_input = AgentInput.model_validate(
        {
            "syllabus_data": {"course_name": "Deep Learning"},
            "criteria_specs": [],
            "normative_context": [],
            "syllabus_seuid": "abc",
        }
    )
    assert agent_input.syllabus_data["course_name"] == "Deep Learning"

    output = AgentOutput.model_validate(
        {
            "agent_code": "A1",
            "judgments": [
                {
                    "criterion_code": "C1",
                    "score": 2,
                    "is_na": False,
                    "justification": "Il criterio è soddisfatto in modo chiaro.",
                    "evidences": [
                        {"text": "Prerequisiti richiesti", "source_field": "prerequisites_it"}
                    ],
                    "confidence": "high",
                }
            ],
            "execution_metadata": {"retry_count": 0},
        }
    )
    assert output.agent_code == "A1"
