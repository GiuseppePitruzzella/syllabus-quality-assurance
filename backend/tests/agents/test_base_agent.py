import json
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.evaluation.agents.base import BaseAgent


@dataclass
class FakeChunk:
    chunk_id: str
    text: str
    metadata: dict
    similarity_score: float


class FakeRetriever:
    def __init__(self):
        self.calls = []

    def retrieve(self, query, criterion, agent):
        self.calls.append((query, criterion, agent))
        return [
            FakeChunk(
                chunk_id=f"{criterion}-1",
                text="Tutte le sezioni presenti nella scheda insegnamento dovranno essere compilate.",
                metadata={"document_id": "lg_unict", "section_ref": "3"},
                similarity_score=0.8,
            )
        ]


class DummyAgent(BaseAgent):
    agent_code = "A1"
    criteria_codes = ["C1", "C2", "C5"]

    def get_relevant_syllabus_fields(self, syllabus):
        return {
            "seuid": syllabus.seuid,
            "course_name": syllabus.course_name,
            "prerequisites_it": "Algebra lineare e programmazione di base.",
            "has_english": True,
        }


def _valid_payload():
    return json.dumps(
        {
            "judgments": [
                {
                    "criterion_code": code,
                    "score": 2,
                    "is_na": False,
                    "na_reason": None,
                    "justification": "Il criterio è soddisfatto con evidenze sufficienti.",
                    "evidences": [
                        {"text": "Algebra lineare", "source_field": "prerequisites_it"}
                    ],
                    "confidence": "high",
                }
                for code in ["C1", "C2", "C5"]
            ]
        }
    )


def test_evaluate_runs_retrieval_prompt_llm_and_parsing():
    retriever = FakeRetriever()
    prompts = []

    def prompt_builder(agent_input):
        prompts.append(agent_input)
        return "prompt"

    agent = DummyAgent(retriever, lambda prompt: _valid_payload(), prompt_builder)
    output = agent.evaluate(SimpleNamespace(seuid="seuid-1", course_name="Deep Learning"))

    assert output.agent_code == "A1"
    assert [j.criterion_code for j in output.judgments] == ["C1", "C2", "C5"]
    assert output.execution_metadata["retrieved_chunks_count"] == 3
    assert [call[1] for call in retriever.calls] == ["C1", "C2", "C5"]
    assert prompts[0].syllabus_seuid == "seuid-1"


def test_call_llm_retries_until_output_validates():
    responses = iter(["not-json", _valid_payload()])
    agent = DummyAgent(FakeRetriever(), lambda prompt: next(responses), lambda _: "prompt")

    raw = agent._call_llm_with_retry("prompt", max_retries=2)

    assert json.loads(raw)["judgments"][0]["criterion_code"] == "C1"
    assert agent._last_retry_count == 1


def test_parse_response_rejects_missing_owned_criterion():
    payload = json.dumps(
        {
            "judgments": [
                {
                    "criterion_code": "C1",
                    "score": 2,
                    "is_na": False,
                    "justification": "Il criterio è soddisfatto con evidenze sufficienti.",
                    "evidences": [],
                    "confidence": "high",
                }
            ]
        }
    )
    agent = DummyAgent(FakeRetriever(), lambda prompt: payload, lambda _: "prompt")

    with pytest.raises(ValueError, match="expected judgments"):
        agent._parse_response(payload)


def test_parse_response_rejects_duplicate_owned_criterion():
    payload = json.dumps(
        {
            "judgments": [
                {
                    "criterion_code": code,
                    "score": 2,
                    "is_na": False,
                    "justification": "Il criterio è soddisfatto con evidenze sufficienti.",
                    "evidences": [],
                    "confidence": "high",
                }
                for code in ["C1", "C1", "C2", "C5"]
            ]
        }
    )
    agent = DummyAgent(FakeRetriever(), lambda prompt: payload, lambda _: "prompt")

    with pytest.raises(ValueError, match="expected judgments"):
        agent._parse_response(payload)
