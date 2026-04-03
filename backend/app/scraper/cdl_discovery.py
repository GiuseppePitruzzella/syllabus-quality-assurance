"""
Scrape Corsi di Laurea from a department homepage sidebar.

The sidebar section "CORSI DI STUDIO" lists courses grouped under h3 headings
(e.g. "Triennali", "Magistrali"). Each course is a link inside a .border-bottom div.

Dottorati are excluded — they do not use the standard syllabus format.

Usage (CLI):
    cd backend && uv run python -m app.scraper.cdl_discovery \\
        --dept-url=https://web.dmi.unict.it --dept-id=1
"""
from __future__ import annotations

import argparse
import re
from urllib.parse import urljoin

from app.scraper.utils import RateLimitedSession, parse_html

# Map sidebar h3 headings → canonical type values
_TYPE_MAP: dict[str, str] = {
    "triennali": "Triennale",
    "magistrali": "Magistrale",
    "magistrale": "Magistrale",
    "triennale": "Triennale",
    "ciclo unico": "Ciclo Unico",
    "magistrali a ciclo unico": "Ciclo Unico",
    # interdipartimentali may contain mixed types; fall back to URL-based inference
}

# Code-prefix rules for inferring type when the heading doesn't tell us
# (e.g. interdipartimentali courses)
_CODE_PREFIX_RULES: list[tuple[str, str]] = [
    ("lm-", "Magistrale"),
    ("l-", "Triennale"),
    ("cu-", "Ciclo Unico"),
    ("lmg-", "Ciclo Unico"),  # giurisprudenza
]

# Headings whose courses must be excluded entirely
_EXCLUDED_HEADINGS: frozenset[str] = frozenset({"dottorati"})


def _normalise_heading(text: str) -> str:
    return text.strip().lower()


def _infer_type(heading: str) -> str | None:
    """Return canonical type from a sidebar heading, or None if unknown."""
    key = _normalise_heading(heading)
    return _TYPE_MAP.get(key)


def _infer_type_from_code(code: str) -> str | None:
    """Infer type from the CdL code (e.g. 'lm-18' → 'Magistrale')."""
    code_lower = code.lower()
    for prefix, cdl_type in _CODE_PREFIX_RULES:
        if code_lower.startswith(prefix):
            return cdl_type
    return None


def _extract_code_from_url(href: str) -> str:
    """Extract the CdL code from a URL path like 'corsi/lm-18' → 'lm-18'."""
    # Take the last non-empty path segment
    parts = [p for p in href.rstrip("/").split("/") if p]
    return parts[-1] if parts else ""


def parse_cdl_page(html: str, dept_url: str, dept_id: int) -> list[dict]:
    """
    Parse a department homepage HTML and return CdL dicts.

    Parameters
    ----------
    html:
        Raw HTML of the department homepage.
    dept_url:
        The base URL used to resolve relative hrefs (e.g. ``https://web.dmi.unict.it``).
    dept_id:
        Database ID of the department; stored in every returned dict.

    Returns
    -------
    list of dicts with keys: department_id, name, code, type, url
    """
    soup = parse_html(html)
    results: list[dict] = []

    # Locate the "CORSI DI STUDIO" block
    block = None
    for h2 in soup.find_all("h2"):
        if re.search(r"corsi di studio", h2.get_text(), re.IGNORECASE):
            block = h2.find_parent("div", class_="block")
            break

    if block is None:
        return results

    # The main view has two sub-sections: view-content (standard courses) and
    # view-footer (interdipartimentali + dottorati).
    # We process both but skip headings in _EXCLUDED_HEADINGS.

    view = block.find("div", class_=lambda c: c and "view-corsi-di-laurea" in " ".join(c))
    if view is None:
        # Fallback: search within the whole block
        view = block

    # Collect (section_element, relative_base) pairs to process
    sections_to_scan = []
    view_content = view.find("div", class_="view-content")
    view_footer = view.find("div", class_="view-footer")

    for section in filter(None, [view_content, view_footer]):
        sections_to_scan.append(section)

    current_type: str | None = None
    current_heading: str = ""
    excluded: bool = False

    for section in sections_to_scan:
        for child in section.children:
            if not hasattr(child, "name") or child.name is None:
                continue

            if child.name == "h3":
                heading_text = child.get_text(strip=True)
                current_heading = heading_text
                excluded = _normalise_heading(heading_text) in _EXCLUDED_HEADINGS
                current_type = _infer_type(heading_text)
                continue

            if child.name == "div" and "border-bottom" in child.get("class", []):
                if excluded:
                    continue

                a = child.find("a", href=True)
                if not a:
                    continue

                name = a.get_text(strip=True)
                href = a["href"].strip()

                # Build absolute URL
                absolute_url = urljoin(dept_url.rstrip("/") + "/", href)

                # Extract code from URL path
                code = _extract_code_from_url(href)

                # Determine type: use current_type if set, otherwise try to
                # infer from the CdL code (handles interdipartimentali, etc.)
                cdl_type = current_type
                if cdl_type is None:
                    cdl_type = _infer_type_from_code(code)
                if cdl_type is None:
                    # Skip courses whose type cannot be determined
                    continue

                results.append({
                    "department_id": dept_id,
                    "name": name,
                    "code": code,
                    "type": cdl_type,
                    "url": absolute_url,
                })

    return results


def scrape_cdl(
    dept_url: str,
    dept_id: int,
    session: RateLimitedSession | None = None,
) -> list[dict]:
    """
    Fetch the department homepage and parse the CdL sidebar.

    Falls back to ``dept_url/it`` if the main URL returns no results (some
    department sites use ``/it`` as their homepage).

    Parameters
    ----------
    dept_url:
        Homepage URL of the department (e.g. ``https://web.dmi.unict.it``).
    dept_id:
        Database ID of the department.
    session:
        Optional :class:`RateLimitedSession`; a new one is created if not given.

    Returns
    -------
    List of CdL dicts ready to be persisted.
    """
    if session is None:
        session = RateLimitedSession()

    response = session.get(dept_url)
    results = parse_cdl_page(response.text, dept_url, dept_id)

    if not results:
        fallback_url = dept_url.rstrip("/") + "/it"
        response = session.get(fallback_url)
        results = parse_cdl_page(response.text, dept_url, dept_id)

    return results


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Discover Corsi di Laurea from a department homepage."
    )
    p.add_argument(
        "--dept-url",
        required=True,
        help="Department homepage URL, e.g. https://web.dmi.unict.it",
    )
    p.add_argument(
        "--dept-id",
        required=True,
        type=int,
        help="Database ID of the department",
    )
    return p


if __name__ == "__main__":
    args = _build_parser().parse_args()
    cdl_list = scrape_cdl(dept_url=args.dept_url, dept_id=args.dept_id)
    print(f"Found {len(cdl_list)} CdL for department {args.dept_id} ({args.dept_url}):\n")
    for i, cdl in enumerate(cdl_list, 1):
        print(f"  {i:2d}. [{cdl['type']:20s}]  {cdl['name']:40s}  code={cdl['code']}  url={cdl['url']}")
