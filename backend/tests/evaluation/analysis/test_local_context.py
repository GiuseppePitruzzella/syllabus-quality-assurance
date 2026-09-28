import json
from pathlib import Path

import pytest

from app.evaluation.analysis.local_benchmark import load_case
from app.evaluation.analysis.local_context import deduplicate_context, prepare_fixed_context
from app.evaluation.analysis.local_rubric import CONTEXT_MARKER, extract_json_block, prepare_prompt

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/llm_responses"


@pytest.mark.parametrize("agent", ["a2", "a4"])
def test_fixed_sources_preserve_all_criterion_text_associations_on_five_cases(agent):
    results = []
    for path in sorted(FIXTURES.glob(agent + "_calibration_*.json")):
        case = load_case(path)
        base = prepare_prompt(case, "current_v1")
        fixed = prepare_fixed_context(base, case.agent_code)
        old_block, old = extract_json_block(base.text, CONTEXT_MARKER)
        new_block, new = extract_json_block(fixed.text, CONTEXT_MARKER)
        assert base.text.replace(old_block, "") == fixed.text.replace(new_block, "")
        assert {(x["criterion_code"], x["chunk_id"], x["text"]) for x in old} == {
            (code, x["chunk_id"], x["text"]) for x in new for code in x["criterion_codes"]
        }
        assert len(new) == (4 if agent == "a2" else 2)
        assert fixed.provenance["context_text_chars_after"] <= fixed.provenance[
            "context_text_chars_before"
        ]
        results.append(new_block)
    assert len(results) == 5
    assert len(set(results)) == 1


def test_conflicting_source_cannot_be_silently_deduplicated():
    chunk = {"metadata": {"document_id": "guide", "document_version": "1"},
             "criterion_code": "C3", "chunk_id": "section", "text": "Original"}
    with pytest.raises(ValueError, match="Conflicting"):
        deduplicate_context([chunk, chunk | {"text": "Changed"}])


@pytest.mark.parametrize("agent", ["a1", "a3"])
def test_uncurated_agents_have_no_silent_fallback(agent):
    case = load_case(next(FIXTURES.glob(agent + "_calibration_*.json")))
    with pytest.raises(ValueError, match="only for A2/A4"):
        prepare_fixed_context(prepare_prompt(case, "current_v1"), case.agent_code)


@pytest.mark.parametrize("defect", ["text", "criteria", "missing", "duplicate", "version"])
def test_corrupted_pack_fails_before_inference(monkeypatch, tmp_path, defect):
    from app.evaluation.analysis import local_context
    pack = json.loads(local_context.PACK_PATH.read_text())
    entries = pack["agents"]["A2"]["passages"]
    if defect == "text":
        entries[0]["text_sha256"] = "0" * 64
    elif defect == "criteria":
        entries[0]["criterion_codes"] = ["C9"]
    elif defect == "missing":
        pack["agents"]["A2"]["passages"] = []
    elif defect == "duplicate":
        entries.append(entries[0])
    else:
        pack["policy"] = "wrong"
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(pack))
    monkeypatch.setattr(local_context, "PACK_PATH", path)
    case = load_case(next(FIXTURES.glob("a2_calibration_*.json")))
    with pytest.raises(ValueError):
        prepare_fixed_context(prepare_prompt(case, "current_v1"), "A2")
