"""Deterministic English-coverage pre-check for criterion C2.

Pure functions. No I/O, no Vertex, no DB. Given the A1 syllabus fields,
compute which English fields are *present* (objective field-presence
check) and a *suggested* C2 score. A1's LLM adopts the suggestion unless
it has clear textual evidence the matrix is wrong (hybrid). The title is
diagnostic but NOT part of the score (title non-blocking). See spec
2026-06-23-c2-stability-design.md.
"""
from __future__ import annotations

from typing import Any

# A field counts as present only if its normalised text is at least this
# long, to drop whitespace/fragment placeholders.
MIN_CHARS: int = 10

# Normalised (lowercased, stripped) values that are NOT real content even
# when long enough. Matched by exact-equality OR startswith, so e.g.
# "see italian version for details" is caught.
DENYLIST: tuple[str, ...] = (
    "",
    "-",
    "—",
    "n/a",
    "na",
    "not available",
    "see italian version",
    "same as italian version",
    "versione in italiano",
    "italian version",
)

# The three informative sections that drive the C2 score (title excluded).
_INFORMATIVE_FIELDS: tuple[str, ...] = (
    "learning_outcomes_en",
    "course_content_en",
    "assessment_methods_en",
)


def _normalise(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())


def _is_present(value: Any) -> bool:
    """True iff the field carries real English content (not a placeholder)."""
    norm = _normalise(value)
    if len(norm) < MIN_CHARS:
        return False
    low = norm.lower()
    return not any(low == d or low.startswith(d) for d in DENYLIST if d)


def english_coverage(fields: dict[str, Any]) -> dict[str, bool]:
    """Return the English-coverage matrix for C2.

    Keys: ``title_en`` (diagnostic), and the three informative sections
    ``learning_outcomes_en`` / ``course_content_en`` /
    ``assessment_methods_en``. Missing keys are treated as absent.
    """
    return {
        "title_en": _is_present(fields.get("course_name_en")),
        "learning_outcomes_en": _is_present(fields.get("learning_outcomes_en")),
        "course_content_en": _is_present(fields.get("course_content_en")),
        "assessment_methods_en": _is_present(fields.get("assessment_methods_en")),
    }


def suggest_c2(coverage: dict[str, bool]) -> int:
    """Suggested C2 score from the coverage matrix (title excluded).

    2 = all 3 informative sections present; 1 = 1 or 2 present;
    0 = none present (EN absent or title-only).
    """
    n = sum(1 for f in _INFORMATIVE_FIELDS if coverage.get(f))
    if n == 3:
        return 2
    if n >= 1:
        return 1
    return 0
