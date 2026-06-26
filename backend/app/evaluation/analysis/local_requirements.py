"""Deterministic LM-18 local-requirement checks over syllabus snapshots."""
from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalize_text(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace("’", "'")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def scan_local_requirements(syllabus: Any) -> dict[str, Any]:
    teaching = normalize_text(getattr(syllabus, "teaching_methods_it", ""))
    assessment = normalize_text(getattr(syllabus, "assessment_methods_it", ""))
    schedule = getattr(syllabus, "schedule_it", None)
    schedule_rows = schedule if isinstance(schedule, list) else []

    mixed_distance_clause = all(
        token in teaching
        for token in (
            "modalita mista o a distanza",
            "necessarie variazioni",
            "programma previsto",
        )
    )
    cinap_dsa_clause = (
        "cinap" in assessment
        and ("disabilita" in assessment or "dsa" in assessment)
        and "misure compensative" in assessment
    )
    telematic_assessment_clause = (
        "verifica dell apprendimento" in assessment
        and "via telematica" in assessment
    )
    grading_grid_signals = {
        "not_approved": (
            "non approvato" in assessment or "not approved" in assessment
        ),
        "band_18_23": _contains_band(assessment, 18, 23),
        "band_24_27": _contains_band(assessment, 24, 27),
        "band_28_30": _contains_band(assessment, 28, 30),
    }
    schedule_topics = [
        _schedule_value(row, ("argomenti", "subjects", "subject", "topics", "topic"))
        for row in schedule_rows
        if isinstance(row, dict)
    ]
    schedule_references = [
        _schedule_value(
            row,
            (
                "riferimenti_testi",
                "text_references",
                "textbook_references",
                "references",
            ),
        )
        for row in schedule_rows
        if isinstance(row, dict)
    ]
    topic_count = sum(bool(value) for value in schedule_topics)
    reference_count = sum(bool(value) for value in schedule_references)
    return {
        "seuid": getattr(syllabus, "seuid", None),
        "course_name": getattr(syllabus, "course_name", None),
        "mixed_distance_clause": mixed_distance_clause,
        "cinap_dsa_clause": cinap_dsa_clause,
        "telematic_assessment_clause": telematic_assessment_clause,
        "grading_grid_complete": all(grading_grid_signals.values()),
        "grading_grid_signals": grading_grid_signals,
        "schedule_present": bool(schedule_rows),
        "schedule_entries": len(schedule_rows),
        "schedule_topic_count": topic_count,
        "schedule_reference_count": reference_count,
        "schedule_topics_complete": bool(schedule_rows)
        and topic_count == len(schedule_rows),
        "schedule_references_any": reference_count > 0,
        "schedule_references_complete": bool(schedule_rows)
        and reference_count == len(schedule_rows),
    }


def _contains_band(text: str, low: int, high: int) -> bool:
    return bool(re.search(rf"\b{low}\s+(?:a\s+)?{high}\b", text))


def _schedule_value(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""
