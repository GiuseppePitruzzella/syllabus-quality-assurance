import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.evaluation.analysis.local_benchmark import load_case
from app.evaluation.analysis.local_evidence import (
    assess_source_response, prepare_source_prompt, source_catalog,
)
from app.evaluation.analysis.local_rubric import (
    CONTEXT_MARKER, SYLLABUS_MARKER, extract_json_block, prepare_prompt,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/llm_responses"
PATHS = sorted(FIXTURES.glob("a[1-4]_calibration_*.json"))


def _reconstruct(value):
    if isinstance(value, dict):
        if set(value) == {"passages"}:
            return "".join(p["text"] for p in value["passages"])
        return {k: _reconstruct(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_reconstruct(v) for v in value]
    return value


@pytest.mark.parametrize("path", PATHS, ids=lambda p: p.stem)
def test_every_archived_syllabus_is_preserved_exactly_with_nested_paths(path):
    case = load_case(path)
    annotated, passages, empty = source_catalog(case.syllabus)
    assert _reconstruct(annotated) == case.syllabus
    for p in passages.values():
        leaf = case.syllabus[p["source_field"]]
        for component in p["path"]:
            leaf = leaf[component]
        assert leaf[p["start"]:p["end"]] == p["text"]
    source = prepare_source_prompt(case, prepare_prompt(case, "current_v1"))
    assert _reconstruct(extract_json_block(source.prepared.text, SYLLABUS_MARKER)[1]) == case.syllabus
    assert extract_json_block(source.prepared.text, CONTEXT_MARKER)[1] == extract_json_block(
        case.prompt, CONTEXT_MARKER
    )[1]
    assert source.empty_fields == empty


def _sample():
    case = replace(load_case(PATHS[0]), criteria=["C1"], reference_scores={"C1": 2},
                   syllabus={"course_content_it": "Algoritmi, complessità e grafi.",
                             "assessment_methods_en": "", "schedule_it": [{"topic": "Àλ漢字"}]})
    annotated, passages, empty = source_catalog(case.syllabus)
    from app.evaluation.analysis.local_evidence import SourcePrompt
    from app.evaluation.analysis.local_rubric import PreparedPrompt
    source = SourcePrompt(PreparedPrompt("unused", {}), passages, empty)
    judgment = {"criterion_code": "C1", "score": 2, "is_na": False, "na_reason": None,
                "justification": "Il contenuto è presente nel passaggio selezionato.",
                "evidence_ids": ["S0001"], "absent_fields": [], "confidence": "medium"}
    return case, source, judgment


def test_quotes_come_from_original_and_verified_absence_is_distinct():
    case, source, judgment = _sample()
    judgment["absent_fields"] = ["assessment_methods_en"]
    result = assess_source_response(case, json.dumps({"judgments": [judgment]}), source)
    assert result["judgments"][0]["evidences"] == [{
        "text": case.syllabus["course_content_it"], "source_field": "course_content_it",
    }]
    assert result["source_selections"][0]["verified_absent_fields"] == ["assessment_methods_en"]
    assert all(e["verified"] for e in result["evidence_checks"])


@pytest.mark.parametrize("change", ["unknown_id", "duplicate_id", "fake_absence",
                                    "excluded_field", "invented_quote", "no_basis",
                                    "missing_score", "non_na_reason", "invalid_na",
                                    "wrong_criterion", "source_changed"])
def test_unsupported_decisions_fail_instead_of_becoming_valid_scores(change):
    case, source, judgment = _sample()
    if change == "unknown_id":
        judgment["evidence_ids"] = ["S9999"]
    elif change == "duplicate_id":
        judgment["evidence_ids"] *= 2
    elif change == "fake_absence":
        judgment["absent_fields"] = ["course_content_it"]
    elif change == "excluded_field":
        judgment["absent_fields"] = ["missing_from_payload"]
    elif change == "invented_quote":
        judgment["evidences"] = [{"text": "invented"}]
    elif change == "no_basis":
        judgment["evidence_ids"] = []
    elif change == "missing_score":
        del judgment["score"]
    elif change == "non_na_reason":
        judgment["na_reason"] = "Not null"
    elif change == "invalid_na":
        judgment["is_na"] = True
    elif change == "wrong_criterion":
        judgment["criterion_code"] = "C9"
    else:
        case.syllabus["course_content_it"] = "mutated source"
    with pytest.raises(ValueError):
        assess_source_response(case, json.dumps({"judgments": [judgment]}), source)


def test_empty_and_boolean_fields_are_not_confused_and_unicode_is_lossless():
    data = {"empty": {"items": [None, "  "]}, "flag": False, "number": 0,
            "body": "\nÀλ漢字  è. " * 200}
    annotated, passages, empty = source_catalog(data, max_chars=33)
    assert empty == ["empty"]
    assert _reconstruct(annotated) == data
    assert len(passages) > 1


@pytest.mark.parametrize("path", PATHS)
def test_anchor_control_changes_only_the_specification_block(path):
    case = load_case(path)
    restored = prepare_prompt(case, "current_v1")
    control = prepare_prompt(case, "current_without_anchors_v1")
    restored_block, specs = extract_json_block(restored.text, "SPECIFICHE CRITERI:")
    control_block, descriptions = extract_json_block(control.text, "SPECIFICHE CRITERI:")
    assert restored.text.replace(restored_block, "") == control.text.replace(control_block, "")
    assert all(set(s["anchors"]) == {"0", "1", "2"} for s in specs)
    assert all("anchors" not in s for s in descriptions)


@pytest.mark.parametrize("path", PATHS)
def test_inline_protocol_preserves_field_types_and_every_original_character(path):
    case = load_case(path)
    source = prepare_source_prompt(case, prepare_prompt(case, "current_v1"), "source_ids_v2")
    _, annotated = extract_json_block(source.prepared.text, SYLLABUS_MARKER)

    def check(original, marked, field, path):
        assert type(marked) is type(original)
        if isinstance(original, str):
            parts = [(key, p) for key, p in source.passages.items()
                     if p["source_field"] == field and p["path"] == path]
            if parts:
                assert "".join(p["text"] for _, p in parts) == original
                assert marked == "".join(f"⟦{key}⟧{p['text']}" for key, p in parts)
            else:
                assert marked == original
        elif isinstance(original, dict):
            assert marked.keys() == original.keys()
            for k, v in original.items():
                check(v, marked[k], field, [*path, k])
        elif isinstance(original, list):
            assert len(marked) == len(original)
            for i, v in enumerate(original):
                check(v, marked[i], field, [*path, i])
        else:
            assert marked == original

    for field in case.syllabus:
        check(case.syllabus[field], annotated[field], field, [])


def test_english_absence_cannot_be_used_to_score_italian_completeness():
    case, source, judgment = _sample()
    source = replace(source, prepared=replace(source.prepared,
                                             provenance={"evidence_mode": "source_ids_v2"}))
    judgment["absent_fields"] = ["assessment_methods_en"]
    with pytest.raises(ValueError, match="outside the criterion scope"):
        assess_source_response(case, json.dumps({"judgments": [judgment]}), source)


def test_v2_schema_restricts_absences_and_ids_for_each_criterion():
    from app.evaluation.analysis.local_evidence import _in_scope
    case = load_case(PATHS[0])
    source = prepare_source_prompt(case, prepare_prompt(case, "current_v1"), "source_ids_v2")
    branches = source.schema(case.criteria)["properties"]["judgments"]["items"]["anyOf"]
    for branch in branches:
        props = branch["properties"]
        code = props["criterion_code"]["enum"][0]
        ids = props["evidence_ids"]["items"].get("enum", [])
        assert all(_in_scope(code, source.passages[key]["source_field"]) for key in ids)
        fields = props["absent_fields"]["items"].get("enum", [])
        assert all(_in_scope(code, f, absence=True) for f in fields)
        if code == "C1":
            assert "assessment_methods_en" not in fields
            assert not any(source.passages[key]["source_field"] == "course_name" for key in ids)


def test_v1_experiment_prompt_is_not_silently_rewritten():
    # The compatibility protocol remains available for reproducing failed trials.
    case = load_case(PATHS[0])
    source = prepare_source_prompt(case, prepare_prompt(case, "current_v1"), "source_ids_v1")
    assert "struttura passages" in source.prepared.text
    assert "I campi testuali rimangono stringhe" not in source.prepared.text
