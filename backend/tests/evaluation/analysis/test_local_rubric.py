import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.evaluation.analysis.local_benchmark import load_case
from app.evaluation.analysis.local_rubric import (
    CONTEXT_MARKER, POLICY, SYLLABUS_MARKER, extract_json_block, load_rubric, prepare_prompt,
    sha256,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/llm_responses"
PATHS = sorted(FIXTURES.glob("a[1-4]_calibration_*.json"))


@pytest.mark.parametrize("path", PATHS, ids=lambda p: p.stem)
def test_historical_replay_remains_byte_identical(path):
    case = load_case(path)
    prepared = prepare_prompt(case)
    assert prepared.text.encode() == case.prompt.encode()
    assert prepared.provenance["effective_prompt_sha256"] == sha256(case.prompt)
    assert not prepared.provenance["rubric_changed"]


@pytest.mark.parametrize("path", PATHS, ids=lambda p: p.stem)
def test_revised_prompts_preserve_all_data_and_cannot_lose_anchors(path):
    case = load_case(path)
    prepared = prepare_prompt(case, POLICY)
    for marker in (SYLLABUS_MARKER, CONTEXT_MARKER):
        assert extract_json_block(prepared.text, marker) == extract_json_block(case.prompt, marker)
    _, block = extract_json_block(
        prepared.text, "SPECIFICHE CRITERI (unica regola di assegnazione dei punteggi):"
    )
    assert [c["criterion_code"] for c in block["criteria"]] == case.criteria
    assert all(set(c["anchors"]) == {"0", "1", "2"} for c in block["criteria"])
    assert block["criteria"] == [c for c in load_rubric()["criteria"]
                                 if c["owned_by"] == case.agent_code]
    assert prepared.provenance["rubric_changed"]
    assert prepared.provenance["effective_prompt_sha256"] != sha256(case.prompt)
    assert prepared.provenance["syllabus_block_sha256"] == sha256(
        extract_json_block(case.prompt, SYLLABUS_MARKER)[0]
    )


@pytest.mark.parametrize("change", ["missing_context", "duplicate_context", "bad_fence",
                                    "wrong_syllabus", "wrong_owner", "unknown_policy"])
def test_invalid_or_ambiguous_inputs_fail_before_inference(change):
    case = load_case(PATHS[0])
    policy = POLICY
    if change == "missing_context":
        case = replace(case, prompt=case.prompt.replace(CONTEXT_MARKER, "removed:"))
    elif change == "duplicate_context":
        case = replace(case, prompt=case.prompt + "\n" + extract_json_block(
            case.prompt, CONTEXT_MARKER)[0])
    elif change == "bad_fence":
        block, _ = extract_json_block(case.prompt, CONTEXT_MARKER)
        case = replace(case, prompt=case.prompt.replace(block, block[:-3] + "broken"))
    elif change == "wrong_syllabus":
        case = replace(case, syllabus={"changed": True})
    elif change == "wrong_owner":
        case = replace(case, criteria=["C9"])
    else:
        policy = "unversioned"
    with pytest.raises(ValueError):
        prepare_prompt(case, policy)


def test_json_content_with_fences_and_marker_text_is_preserved():
    value = {"text": "Esempio ``` e newline\n" + CONTEXT_MARKER}
    block = SYLLABUS_MARKER + "\n```json\n" + json.dumps(value) + "\n```"
    assert extract_json_block(block, SYLLABUS_MARKER) == (block, value)


@pytest.mark.parametrize("defect", ["duplicate", "missing_anchor", "wrong_owner", "empty_scope"])
def test_invalid_catalog_cannot_silently_supply_incomplete_specs(monkeypatch, tmp_path, defect):
    from app.evaluation.analysis import local_rubric
    rubric = load_rubric()
    if defect == "duplicate":
        rubric["criteria"].append(rubric["criteria"][0])
    elif defect == "missing_anchor":
        del rubric["criteria"][0]["anchors"]["2"]
    elif defect == "wrong_owner":
        rubric["criteria"][0]["owned_by"] = "A4"
    else:
        rubric["criteria"][0]["scope"] = ""
    path = tmp_path / "rubric.json"
    path.write_text(json.dumps(rubric))
    monkeypatch.setattr(local_rubric, "RUBRIC_PATH", path)
    with pytest.raises(ValueError):
        load_rubric()
