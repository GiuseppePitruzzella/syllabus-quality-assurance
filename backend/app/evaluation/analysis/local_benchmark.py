"""Offline fixtures and descriptive metrics for local-model replay.

Agreement with archived Gemini outputs is NOT accuracy against human experts.
Historical prompts are replayed verbatim; their versions are recorded.
"""
from __future__ import annotations

import hashlib
import json
import re
import statistics
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.evaluation.agents.schemas import CriterionJudgment


class JudgmentResponse(BaseModel):
    judgments: list[CriterionJudgment] = Field(min_length=1, max_length=9)


def response_schema(criteria: list[str]) -> dict[str, Any]:
    schema = JudgmentResponse.model_json_schema()
    schema["properties"]["judgments"].update(minItems=len(criteria), maxItems=len(criteria))
    code = schema["$defs"]["CriterionJudgment"]["properties"]["criterion_code"]
    code.pop("pattern", None)
    code["enum"] = criteria
    return schema


@dataclass(frozen=True)
class ReplayCase:
    case_id: str
    fixture_name: str
    fixture_sha256: str
    agent_code: str
    seuid: str
    prompt: str
    prompt_version: str
    syllabus: dict[str, Any]
    criteria: list[str]
    reference_scores: dict[str, int | None]
    reference_latency_ms: int | None


def load_case(path: Path) -> ReplayCase:
    content = path.read_bytes()
    fixture = json.loads(content)
    agent = fixture["agent_code"]
    if agent not in {"A1", "A2", "A3", "A4"} or fixture.get("error"):
        raise ValueError(f"{path.name}: requires a successful core-agent fixture")
    calls = fixture["llm_calls"]
    # First prompt is the original, not the validation-repair prompt.
    prompt = calls[0]["prompt"]
    match = re.search(r"DATI DEL SYLLABUS DA VALUTARE:\s*```json\s*", prompt)
    if not match:
        raise ValueError(f"{path.name}: cannot identify the syllabus JSON")
    syllabus, _ = json.JSONDecoder().raw_decode(prompt[match.end():])
    if not isinstance(syllabus, dict):
        raise ValueError("Expected syllabus JSON object")
    output = fixture["agent_output"]
    reference = JudgmentResponse.model_validate({"judgments": output["judgments"]})
    criteria = fixture["criteria_codes"]
    validate_coverage(reference.judgments, criteria)
    successful = [c for c in calls if c.get("raw_response_text") and not c.get("error")]
    metadata = successful[-1].get("metadata") or {} if successful else {}
    return ReplayCase(
        case_id=f"{agent.lower()}_{fixture['seuid']}", fixture_name=path.name,
        fixture_sha256=hashlib.sha256(content).hexdigest(), agent_code=agent,
        seuid=fixture["seuid"], prompt=prompt,
        prompt_version=output["execution_metadata"]["prompt_version"],
        syllabus=syllabus, criteria=criteria,
        reference_scores={j.criterion_code: j.score for j in reference.judgments},
        reference_latency_ms=metadata.get("latency_ms"),
    )


def validate_coverage(judgments: list[CriterionJudgment], criteria: list[str]) -> None:
    if Counter(j.criterion_code for j in judgments) != Counter(criteria):
        raise ValueError("Missing, duplicate or unexpected criteria")


def _normalise(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def _field_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(_field_text(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(_field_text(v) for v in value)
    return "" if value is None else str(value)


def assess_response(case: ReplayCase, raw: str) -> dict[str, Any]:
    """Strict JSON/domain validation plus deterministic source-quote checks."""
    parsed = JudgmentResponse.model_validate_json(raw)
    validate_coverage(parsed.judgments, case.criteria)
    comparisons, evidence_checks = [], []
    for judgment in parsed.judgments:
        expected = case.reference_scores[judgment.criterion_code]
        comparisons.append({
            "criterion": judgment.criterion_code, "reference": expected,
            "local": judgment.score, "agrees": expected == judgment.score,
            "absolute_error": abs(expected - judgment.score)
            if expected is not None and judgment.score is not None else None,
            "na_disagreement": (expected is None) != judgment.is_na,
        })
        for evidence in judgment.evidences:
            field_exists = evidence.source_field in case.syllabus
            source = _normalise(_field_text(case.syllabus.get(evidence.source_field)))
            quote = _normalise(evidence.text)
            evidence_checks.append({
                "criterion": judgment.criterion_code, "source_field": evidence.source_field,
                "text": evidence.text,
                "verified": field_exists and bool(quote) and quote in source,
            })
    return {
        "judgments": [j.model_dump() for j in parsed.judgments],
        "comparisons": comparisons, "evidence_checks": evidence_checks,
        "judgments_without_evidence": sum(not j.evidences for j in parsed.judgments),
    }


def summarise(records: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [r for r in records if r["status"] == "valid"]
    comparisons = [c for r in valid for c in r["assessment"]["comparisons"]]
    checks = [c for r in valid for c in r["assessment"]["evidence_checks"]]
    errors = [c["absolute_error"] for c in comparisons if c["absolute_error"] is not None]
    times = [r["wall_seconds"] for r in records]
    by_criterion = {}
    for code in sorted({c["criterion"] for c in comparisons}):
        subset = [c for c in comparisons if c["criterion"] == code]
        by_criterion[code] = {
            "n": len(subset), "agreement": sum(c["agrees"] for c in subset) / len(subset),
        }
    return {
        "attempted": len(records), "valid": len(valid),
        "valid_rate": len(valid) / len(records) if records else None,
        "compared_criteria": len(comparisons),
        "agreement_with_archived_gemini": sum(c["agrees"] for c in comparisons)
        / len(comparisons) if comparisons else None,
        "numeric_mae": statistics.mean(errors) if errors else None,
        "na_disagreements": sum(c["na_disagreement"] for c in comparisons),
        "evidences": len(checks), "verified_evidences": sum(c["verified"] for c in checks),
        "evidence_verification_rate": sum(c["verified"] for c in checks)
        / len(checks) if checks else None,
        "judgments_without_evidence": sum(
            r["assessment"]["judgments_without_evidence"] for r in valid
        ),
        "median_wall_seconds": statistics.median(times) if times else None,
        "max_wall_seconds": max(times) if times else None,
        "api_cost_usd": 0, "per_criterion": by_criterion,
        "interpretation": "Diagnostic replay; not human accuracy or a production acceptance gate.",
    }
