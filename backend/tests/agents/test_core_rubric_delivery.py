"""Regression: the real agent path used to replace anchors with descriptions."""
import json
from types import SimpleNamespace

import pytest

from app.evaluation.agents.a1_completeness import CompletenessAgent
from app.evaluation.agents.a2_learning_outcomes import PedagogicalAgent
from app.evaluation.agents.a3_coherence import DidacticConsistencyAgent
from app.evaluation.agents.a4_editorial import EditorialCareAgent
from app.evaluation.agents.prompts.core_rubric import resolve_criteria_specs
from app.evaluation.analysis.local_rubric import extract_json_block

AGENTS = [CompletenessAgent, PedagogicalAgent, DidacticConsistencyAgent, EditorialCareAgent]


@pytest.mark.parametrize("agent_class", AGENTS)
def test_real_agent_delivers_every_score_anchor_to_client(agent_class):
    prompts = []

    def client(prompt, **kwargs):
        prompts.append(prompt)
        return json.dumps({"judgments": [
            {"criterion_code": code, "score": 2, "is_na": False,
             "justification": "Motivazione di esempio per il solo test del contratto.",
             "evidences": [], "confidence": "medium"}
            for code in agent_class.criteria_codes
        ]})

    agent = agent_class(SimpleNamespace(retrieve=lambda **kwargs: []), client)
    output = agent.evaluate(SimpleNamespace(seuid="test", course_name="Corso"))
    _, specs = extract_json_block(prompts[0], "SPECIFICHE CRITERI:")
    assert [s["criterion_code"] for s in specs] == agent.criteria_codes
    assert all(set(s["anchors"]) == {"0", "1", "2"} for s in specs)
    assert output.execution_metadata["prompt_version"] == agent.prompt_version


def test_description_only_partial_input_cannot_erase_other_criteria_or_anchors():
    specs = resolve_criteria_specs([{"criterion_code": "C2", "description": "Copertura"}], "A1")
    assert [s["criterion_code"] for s in specs] == ["C1", "C2", "C5"]
    assert all(set(s["anchors"]) == {"0", "1", "2"} for s in specs)
    specs[0]["anchors"].clear()
    assert set(resolve_criteria_specs([], "A1")[0]["anchors"]) == {"0", "1", "2"}


@pytest.mark.parametrize("specs", [
    [{"criterion_code": "C9"}],
    [{"criterion_code": "C1"}, {"criterion_code": "C1"}],
    [{"criterion_code": "C1", "owned_by": "A4"}],
    [{"criterion_code": "C1", "anchors": {"0": "Assente"}}],
    [{"criterion_code": "C1", "anchors": {"0": " ", "1": "Parziale", "2": "Completo"}}],
])
def test_invalid_override_cannot_silently_change_criterion_contract(specs):
    with pytest.raises(ValueError):
        resolve_criteria_specs(specs, "A1")
