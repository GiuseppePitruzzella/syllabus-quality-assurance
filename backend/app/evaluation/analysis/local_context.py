"""Fixed historical references for the two empirically stable agent contexts.

The pack is a frozen research input, not a current normative compliance profile.
No retrieval, embedding or cloud SDK is used. A1/A3 need separate curation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.evaluation.analysis.local_benchmark import load_case
from app.evaluation.analysis.local_rubric import (
    CONTEXT_MARKER, OWNERS, PreparedPrompt, extract_json_block, sha256,
)

CONTEXT_MODE = "fixed_core_v1"
PACK_PATH = Path(__file__).with_name("local_context_v1.json")
SOURCE_KEYS = ("document_id", "document_title", "document_version", "section_ref",
               "section_title", "source_type")


def deduplicate_context(context: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep each source text once with all its original criterion associations."""
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in context:
        meta = item["metadata"]
        identity = (meta["document_id"], meta["document_version"], item["chunk_id"])
        if identity not in unique:
            unique[identity] = {
                "chunk_id": item["chunk_id"], "text": item["text"],
                "text_sha256": sha256(item["text"]), "criterion_codes": [],
                "metadata": {k: meta[k] for k in SOURCE_KEYS if k in meta},
            }
        entry = unique[identity]
        if entry["text"] != item["text"]:
            raise ValueError("Conflicting text for the same versioned source chunk")
        if item["criterion_code"] not in entry["criterion_codes"]:
            entry["criterion_codes"].append(item["criterion_code"])
    return list(unique.values())


def prepare_fixed_context(prepared: PreparedPrompt, agent: str,
                          fixtures_dir: Path | None = None) -> PreparedPrompt:
    pack_bytes = PACK_PATH.read_bytes()
    pack = json.loads(pack_bytes)
    if pack["policy"] != CONTEXT_MODE or agent not in pack["agents"]:
        raise ValueError("fixed_core_v1 is curated only for A2/A4; select those agents explicitly")
    entry = pack["agents"][agent]
    source_ref = entry["fixtures"][0]
    if Path(source_ref["name"]).name != source_ref["name"]:
        raise ValueError("Fixed source fixture must be a plain filename")
    directory = fixtures_dir or Path(__file__).resolve().parents[3] / "tests/fixtures/llm_responses"
    source_case = load_case(directory / source_ref["name"])
    if source_case.fixture_sha256 != source_ref["sha256"] or source_case.agent_code != agent:
        raise ValueError("Fixed reference fixture has changed; curate a new pack version")
    _, source_context = extract_json_block(source_case.prompt, CONTEXT_MARKER)
    candidates = deduplicate_context(source_context)
    passages = []
    seen = set()
    covered = set()
    for selector in entry["passages"]:
        matching = [p for p in candidates if {k: v for k, v in p.items() if k != "text"} == selector]
        if len(matching) != 1:
            raise ValueError("Fixed passage selector does not match the archived source")
        item = matching[0]
        identity = (item["metadata"]["document_id"], item["metadata"]["document_version"],
                    item["chunk_id"])
        if identity in seen or sha256(item["text"]) != item["text_sha256"]:
            raise ValueError("Fixed context contains duplicate or corrupted passages")
        if not item["criterion_codes"] or not set(item["criterion_codes"]) <= set(OWNERS[agent]):
            raise ValueError("Fixed source assigned to the wrong criterion")
        seen.add(identity)
        covered.update(item["criterion_codes"])
        passages.append(item)
    if covered != set(OWNERS[agent]) or len(passages) != len(candidates):
        raise ValueError("Fixed context does not preserve every source/criterion association")
    previous_block, previous = extract_json_block(prepared.text, CONTEXT_MARKER)
    replacement = CONTEXT_MARKER + "\n```json\n" + json.dumps(
        passages, ensure_ascii=False, indent=2
    ) + "\n```"
    prompt = prepared.text.replace(previous_block, replacement, 1)
    return PreparedPrompt(prompt, prepared.provenance | {
        "context_mode": CONTEXT_MODE, "context_profile": pack["profile"],
        "context_pack_sha256": sha256(pack_bytes.decode("utf-8")),
        "fixed_source_fixture_sha256": source_case.fixture_sha256,
        "base_context_block_sha256": sha256(previous_block),
        "normative_context_block_sha256": sha256(replacement),
        "effective_prompt_sha256": sha256(prompt),
        "context_text_chars_before": sum(len(c["text"]) for c in previous),
        "context_text_chars_after": sum(len(c["text"]) for c in passages),
        "fixed_context_limit": "Historical sources only. Version labels are archived metadata. "
                               "Not a 26.04 profile or proof of coverage for every syllabus.",
    })
