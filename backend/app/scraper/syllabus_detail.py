"""Scraper for individual syllabus detail pages (IT + EN).

Extracts Dublin Descriptors, text sections, schedule table, and assessment
from Universita di Catania syllabus pages.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from typing import Any

from bs4 import BeautifulSoup, Tag

from app.scraper.utils import RateLimitedSession, parse_html

# ---------------------------------------------------------------------------
# Section heading maps  (H2 text -> field name)
# ---------------------------------------------------------------------------

_SECTION_MAP_IT: dict[str, str] = {
    "risultati di apprendimento attesi": "learning_outcomes",
    "modalità di svolgimento dell'insegnamento": "teaching_methods",
    "prerequisiti richiesti": "prerequisites",
    "frequenza lezioni": "attendance",
    "contenuti del corso": "course_content",
    "testi di riferimento": "references",
    "programmazione del corso": "schedule",
    "verifica dell'apprendimento": "assessment",
}

_SECTION_MAP_EN: dict[str, str] = {
    "expected learning outcomes": "learning_outcomes",
    "course structure": "teaching_methods",
    "required prerequisites": "prerequisites",
    "attendance of lessons": "attendance",
    "detailed course content": "course_content",
    "textbook information": "references",
    "course planning": "schedule",
    "learning assessment": "assessment",
}

# ---------------------------------------------------------------------------
# Dublin Descriptor label patterns
# ---------------------------------------------------------------------------

_DUBLIN_LABELS_IT: list[tuple[str, str]] = [
    ("dublin_knowledge", r"Conoscenza e capacit[àa] di comprensione"),
    ("dublin_applying", r"Capacit[àa] di applicare conoscenza e comprensione"),
    ("dublin_judgement", r"Autonomia di giudizio"),
    ("dublin_communication", r"Abilit[àa] comunicative"),
    ("dublin_learning", r"Capacit[àa] di apprendimento"),
]

_DUBLIN_LABELS_EN: list[tuple[str, str]] = [
    ("dublin_knowledge", r"Knowledge and understanding"),
    ("dublin_applying", r"Applying knowledge and understanding"),
    ("dublin_judgement", r"Making judgements"),
    ("dublin_communication", r"Communication skills"),
    ("dublin_learning", r"Learning skills"),
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_DANGLING_COMMENT_CLOSE_RE = re.compile(r"-->")
# Word-wrap hyphenation produced when a long word is broken across two
# lines in the source HTML, e.g. ``appren-\ndimento`` -> ``apprendimento``
# (ISSUE-PARSER-002). The pattern is conservative: it only fires when a
# word character is followed by a literal hyphen + newline + word
# character, never on intentional compound words like ``Marco-Polo``
# (the second part wouldn't be on a new line after a soft hyphen).
_SOFT_HYPHEN_LINEBREAK_RE = re.compile(r"(\w)-\n(\w)")

# Anchor texts of the SmartEdu language-switch button. The button sits
# outside any H2 in the source markup but the section walker captures
# it as a stray sibling, ending up at the tail of fields like
# ``sample_questions_it`` / ``assessment_methods_it`` (ISSUE-PARSER-003).
_LANGUAGE_SWITCH_ANCHOR_TEXTS: tuple[str, ...] = (
    "english version",
    "italian version",
    "versione inglese",
    "versione italiana",
)


def _strip_language_switch_anchors(soup: BeautifulSoup) -> None:
    """Remove the SmartEdu language-switch ``<a>`` button from the soup.

    The button carries text like ``ENGLISH VERSION`` / ``ITALIAN VERSION``
    and points to the page in the other language. It sits outside any
    H2 in the source HTML but ``_extract_sections`` collects it as a
    stray sibling and the text leaks into ``sample_questions`` and
    ``assessment_methods`` (ISSUE-PARSER-003). Decomposing the anchor
    in-place removes it before any text extraction runs.
    """
    for anchor in soup.find_all("a"):
        anchor_text = _normalize_inline_text(
            anchor.get_text(" ", strip=True)
        ).lower()
        if anchor_text in _LANGUAGE_SWITCH_ANCHOR_TEXTS:
            anchor.decompose()


def _strip_html_comments(html: str) -> str:
    """Remove HTML comments from raw markup BEFORE handing it to BeautifulSoup.

    SmartEdu pages are originally authored in Word/Outlook and inherit
    CDATA-wrapped comment blocks like ``<!--//--><![CDATA[//><!--...-->``
    that ``html.parser`` does not always recognise as a single ``Comment``
    node. The result is that the closing ``-->`` sequence leaks into the
    text output of ``get_text()`` and ends up in ``references_*``,
    ``assessment_methods_*`` and ``sample_questions_*``. Pre-stripping the
    standard ``<!-- ... -->`` form on the raw markup removes the bulk of
    these wrappers (ISSUE-PARSER-001).

    A safety net at the text level (``_normalize_inline_text``) drops any
    ``-->`` residue that survives malformed wrappers.
    """
    return _HTML_COMMENT_RE.sub("", html)


def _normalize_inline_text(text: str) -> str:
    """Normalize whitespace for stable heading and label matching.

    The dangling ``-->`` strip is the safety net for ISSUE-PARSER-001:
    ``_strip_html_comments`` removes well-formed comments on the raw
    HTML, but pathological CDATA-wrapped patterns can leave an orphan
    ``-->`` that surfaces in the text. Soft-hyphen line break collapse
    runs upstream in :func:`_extract_readable_text`, where ``\\n`` is
    still present (this function operates on a single line at a time).
    """
    text = unicodedata.normalize("NFKC", text.replace("\xa0", " "))
    text = _DANGLING_COMMENT_CLOSE_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_readable_text(tag: Tag) -> str:
    """Extract text while preserving boundaries between nested tags/list items.

    Soft-hyphen line break collapse (ISSUE-PARSER-002) runs on the raw
    text BEFORE splitting on ``\\n``: once the line is split the regex
    ``\\w-\\n\\w`` can no longer match. Empty lines (after normalisation)
    are dropped.
    """
    raw = tag.get_text("\n", strip=True)
    raw = _SOFT_HYPHEN_LINEBREAK_RE.sub(r"\1\2", raw)
    lines = []
    for line in raw.splitlines():
        line = _normalize_inline_text(line)
        if line:
            lines.append(line)
    return "\n".join(lines)


def _extract_sections(soup: BeautifulSoup, lang: str) -> dict[str, dict[str, Any]]:
    """Walk H2 headings and collect content between each pair.

    Returns a dict mapping field name -> {"text": str, "html": str}.
    """
    section_map = _SECTION_MAP_IT if lang == "it" else _SECTION_MAP_EN
    sections: dict[str, dict[str, Any]] = {}

    for h2 in soup.find_all("h2"):
        heading_text = _normalize_inline_text(h2.get_text(" ", strip=True)).lower()
        field_name = section_map.get(heading_text)
        if field_name is None:
            continue

        # Collect all sibling elements until the next H2
        parts_html: list[str] = []
        parts_text: list[str] = []
        for sib in h2.find_next_siblings():
            if isinstance(sib, Tag) and sib.name == "h2":
                break
            if isinstance(sib, Tag):
                parts_html.append(str(sib))
                text = _extract_readable_text(sib)
                if text:
                    parts_text.append(text)

        sections[field_name] = {
            "text": "\n".join(parts_text),
            "html": "\n".join(parts_html),
        }

    return sections


def _split_dublin_descriptors(
    text: str, lang: str
) -> dict[str, str]:
    """Split the learning outcomes section into 5 Dublin Descriptors.

    The section contains italic labels that delimit each descriptor.
    We use regex on the plain text to split them.
    """
    labels = _DUBLIN_LABELS_IT if lang == "it" else _DUBLIN_LABELS_EN
    result: dict[str, str] = {field: "" for field, _ in labels}

    # Find Dublin labels first, then slice the text between adjacent labels.
    # This is more robust than requiring a colon after every label: some
    # SmartEdu pages use rich-text formatting or omit punctuation.
    alternatives = "|".join(f"(?P<{field}>{pattern})" for field, pattern in labels)
    label_regex = re.compile(
        rf"(?:{alternatives})(?:\s*\([^)]*\))?\s*:?\s*",
        re.DOTALL | re.IGNORECASE,
    )
    matches = list(label_regex.finditer(text))
    if not matches:
        return result

    for i, match in enumerate(matches):
        field = match.lastgroup
        if field is None:
            continue
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        result[field] = text[start:end].strip(" \n:-")

    return result


def _parse_schedule_table(html_fragment: str) -> list[dict[str, str]] | None:
    """Parse a <table> from the schedule section.

    Returns a list of dicts with keys matching table headers, or None if no table.
    """
    soup = parse_html(html_fragment)
    table = soup.find("table")
    if table is None:
        return None

    # Extract headers
    header_row = table.find("tr")
    if header_row is None:
        return None

    raw_headers = [
        _normalize_inline_text(th.get_text(" ", strip=True))
        for th in header_row.find_all(["th", "td"])
    ]
    if not raw_headers:
        return None

    # Normalize headers to the canonical keys used by the frontend and agents.
    headers: list[str] = []
    for h in raw_headers:
        h = h.replace("\xa0", " ").strip().lower()
        h = re.sub(r"\s+", "_", h)
        h = re.sub(r"[^a-z0-9_àèéìòù]+", "", h)
        if h in {"", "n", "n°", "no", "number", "numero"}:
            h = "numero"
        elif h in {"argomenti", "argomento", "subjects", "subject", "topics", "topic"}:
            h = "argomenti"
        elif h in {
            "riferimenti_testi",
            "riferimenti",
            "testi",
            "text_references",
            "textbook_references",
            "references",
        }:
            h = "riferimenti_testi"
        headers.append(h)

    rows: list[dict[str, str]] = []
    for tr in table.find_all("tr")[1:]:  # skip header row
        cells = [
            _normalize_inline_text(td.get_text(" ", strip=True))
            for td in tr.find_all(["td", "th"])
        ]
        if not cells or all(c == "" for c in cells):
            continue
        # Pad or truncate cells to match headers
        while len(cells) < len(headers):
            cells.append("")
        row_dict = {headers[j]: cells[j] for j in range(len(headers))}
        rows.append(row_dict)

    return rows if rows else None


def _split_assessment(html_fragment: str, lang: str) -> dict[str, str]:
    """Split assessment section into methods and sample questions.

    The section is typically divided by H3 sub-headings.
    """
    soup = parse_html(html_fragment)
    methods = ""
    sample_questions = ""

    h3s = soup.find_all("h3")
    if not h3s:
        # No H3 headings: return entire text as methods
        return {
            "assessment_methods": _normalize_inline_text(
                soup.get_text(" ", strip=True)
            ),
            "sample_questions": "",
        }

    # Identify which H3 is "methods" and which is "sample questions"
    for h3 in h3s:
        h3_text = _normalize_inline_text(h3.get_text(" ", strip=True)).lower()

        # Collect text after this H3 until the next H3 or end
        parts: list[str] = []
        for sib in h3.find_next_siblings():
            if isinstance(sib, Tag) and sib.name == "h3":
                break
            if isinstance(sib, Tag):
                text = _extract_readable_text(sib)
                if text:
                    parts.append(text)
        section_text = "\n".join(parts)

        if lang == "it":
            if "modalità" in h3_text or "verifica" in h3_text:
                methods = section_text
            elif "esempi" in h3_text or "domande" in h3_text:
                sample_questions = section_text
        else:
            if "procedure" in h3_text or "assessment" in h3_text:
                methods = section_text
            elif "example" in h3_text or "question" in h3_text:
                sample_questions = section_text

    return {
        "assessment_methods": methods,
        "sample_questions": sample_questions,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_syllabus_page(html: str, lang: str = "it") -> dict[str, Any]:
    """Parse a single syllabus page (IT or EN) and return extracted fields.

    Returns a dict with keys:
        learning_outcomes,
        dublin_knowledge, dublin_applying, dublin_judgement,
        dublin_communication, dublin_learning,
        teaching_methods, prerequisites, attendance,
        course_content, references,
        schedule (list[dict] | None),
        assessment_methods, sample_questions
    """
    html = _strip_html_comments(html)
    soup = parse_html(html)
    _strip_language_switch_anchors(soup)
    sections = _extract_sections(soup, lang)

    # Dublin Descriptors from learning outcomes section
    lo = sections.get("learning_outcomes", {"text": "", "html": ""})
    dublin = _split_dublin_descriptors(lo["text"], lang)

    # Schedule table
    sched_section = sections.get("schedule", {"text": "", "html": ""})
    schedule = _parse_schedule_table(sched_section["html"])

    # Assessment split
    assess_section = sections.get("assessment", {"text": "", "html": ""})
    assessment = _split_assessment(assess_section["html"], lang)

    return {
        # Raw learning outcomes section, preserved even when it is not split
        # into the five Dublin Descriptor labels.
        "learning_outcomes": lo["text"],
        # Dublin Descriptors
        "dublin_knowledge": dublin.get("dublin_knowledge", ""),
        "dublin_applying": dublin.get("dublin_applying", ""),
        "dublin_judgement": dublin.get("dublin_judgement", ""),
        "dublin_communication": dublin.get("dublin_communication", ""),
        "dublin_learning": dublin.get("dublin_learning", ""),
        # Text sections
        "teaching_methods": sections.get("teaching_methods", {"text": ""})["text"],
        "prerequisites": sections.get("prerequisites", {"text": ""})["text"],
        "attendance": sections.get("attendance", {"text": ""})["text"],
        "course_content": sections.get("course_content", {"text": ""})["text"],
        "references": sections.get("references", {"text": ""})["text"],
        # Schedule
        "schedule": schedule,
        # Assessment
        "assessment_methods": assessment["assessment_methods"],
        "sample_questions": assessment["sample_questions"],
    }


def scrape_syllabus_detail(
    url_it: str,
    url_en: str,
    session: RateLimitedSession | None = None,
) -> dict[str, Any]:
    """Fetch and parse both IT and EN syllabus pages.

    Returns a dict with _it and _en suffixed keys matching the Syllabus model,
    plus a `has_english` boolean.
    """
    if session is None:
        session = RateLimitedSession()

    resp_it = session.get(url_it)
    parsed_it = parse_syllabus_page(resp_it.text, lang="it")

    resp_en = session.get(url_en)
    parsed_en = parse_syllabus_page(resp_en.text, lang="en")

    # Merge with _it / _en suffixes
    result: dict[str, Any] = {}
    for key, value in parsed_it.items():
        result[f"{key}_it"] = value
    for key, value in parsed_en.items():
        result[f"{key}_en"] = value

    # has_english: True if any parsed EN field contains real content.
    # Some SmartEdu pages provide English sections without Dublin labels; using
    # only dublin_* would hide an existing English version in the frontend.
    def _has_content(value: Any) -> bool:
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, list):
            return len(value) > 0
        return value is not None

    result["has_english"] = any(_has_content(value) for value in parsed_en.values())

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a UniCT syllabus detail page")
    parser.add_argument("--url", required=True, help="Syllabus page URL")
    parser.add_argument("--lang", default="it", choices=["it", "en"], help="Language")
    args = parser.parse_args()

    session = RateLimitedSession()
    resp = session.get(args.url)
    result = parse_syllabus_page(resp.text, lang=args.lang)

    for key, value in result.items():
        if isinstance(value, list):
            print(f"\n{key}:")
            print(json.dumps(value, indent=2, ensure_ascii=False))
        elif isinstance(value, str):
            preview = value[:200] + "..." if len(value) > 200 else value
            print(f"\n{key}: {preview}")
        else:
            print(f"\n{key}: {value}")


if __name__ == "__main__":
    main()
