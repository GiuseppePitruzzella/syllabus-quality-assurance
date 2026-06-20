"""
Scrape the list of syllabi from a CdL's /programmi page.

The /programmi page contains a single HTML table with three columns:
  - Insegnamento (course link: code + name)
  - Modulo       (module name, may be empty)
  - Docente      (teacher link)

Year-of-study changes are signalled by a row with a single colspan=3 cell
that contains text like "1° anno", "2° anno", etc.

Usage (CLI):
    cd backend && uv run python -m app.scraper.syllabus_list \\
        --cdl-url=https://web.dmi.unict.it/corsi/lm-18 --cdl-id=1
"""
from __future__ import annotations

import argparse
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from app.scraper.utils import RateLimitedSession, parse_html

# Matches "1° anno", "2° anno", … (ASCII degree sign or ordinal indicator)
_YEAR_RE = re.compile(r"(\d+)\s*[°º]?\s*anno", re.IGNORECASE)
# Matches "NNN - Course Name" or just "NNN - Course Name" where NNN is the code
_COURSE_RE = re.compile(r"^(\S+)\s+-\s+(.+)$")


def _extract_seuid(href: str) -> str | None:
    """Return the seuid (or seuidm) value from a query string, or None."""
    qs = parse_qs(urlparse(href).query)
    for key in ("seuid", "seuidm"):
        if key in qs:
            return qs[key][0]
    return None


def build_english_syllabus_url(url_it: str) -> str:
    """Return UniCT's canonical English syllabus URL for an IT detail URL.

    SmartEdu used to serve English syllabi by appending ``&eng`` to the
    Italian ``/corsi/{code}/insegnamenti`` endpoint. The current public
    website exposes the real English page under
    ``/en/courses/{code}/course-units`` instead; ``&eng`` now resolves to
    Italian content and makes the detail scraper think no EN sections exist.
    """
    parsed = urlparse(url_it)
    qs = parse_qs(parsed.query)
    query_key = next((key for key in ("seuid", "seuidm") if qs.get(key)), None)
    query_value = qs[query_key][0] if query_key is not None else None

    path_match = re.match(
        r"^/(?:en/)?(?:corsi|courses)/([^/]+)/(?:insegnamenti|course-units)/?$",
        parsed.path,
    )
    if path_match and query_key is not None and query_value:
        cdl_code = path_match.group(1)
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                f"/en/courses/{cdl_code}/course-units",
                "",
                urlencode({query_key: query_value}),
                "",
            )
        )

    if "eng" in parse_qs(parsed.query, keep_blank_values=True):
        return url_it
    separator = "&" if parsed.query else "?"
    return f"{url_it}{separator}eng"


def parse_syllabus_list(html: str, cdl_url: str, cdl_id: int) -> list[dict]:
    """
    Parse the /programmi HTML and return a list of syllabus metadata dicts.

    Parameters
    ----------
    html:
        Raw HTML of the ``{cdl_url}/programmi`` page.
    cdl_url:
        Base URL of the CdL (e.g. ``https://web.dmi.unict.it/corsi/lm-18``).
        Used to build absolute URLs.
    cdl_id:
        Database ID of the CorsoDiLaurea; stored in every returned dict.

    Returns
    -------
    List of dicts suitable for Syllabus upsert.
    """
    soup = parse_html(html)
    table = soup.find("table")
    if table is None:
        return []

    rows = table.find_all("tr")
    results: list[dict] = []
    current_year = "1"

    for row in rows:
        cells = row.find_all(["th", "td"])

        # ------------------------------------------------------------------ #
        # Year-header row: single cell with colspan=3                         #
        # ------------------------------------------------------------------ #
        if len(cells) == 1:
            text = cells[0].get_text(strip=True)
            m = _YEAR_RE.search(text)
            if m:
                current_year = m.group(1)
            continue

        # ------------------------------------------------------------------ #
        # Header row (th elements only — the first row)                       #
        # ------------------------------------------------------------------ #
        if all(c.name == "th" for c in cells):
            continue

        # ------------------------------------------------------------------ #
        # Data row: must have at least 3 cells                                #
        # ------------------------------------------------------------------ #
        if len(cells) < 3:
            continue

        # Cell 0: course link
        course_cell = cells[0]
        a_course = course_cell.find("a", href=True)
        if a_course is None:
            continue

        href = a_course["href"].strip()
        seuid = _extract_seuid(href)
        if not seuid:
            continue

        # Build absolute URLs
        # href is a relative path like /corsi/lm-18/insegnamenti?seuid=...
        # urljoin with the site root handles this correctly
        parsed_cdl = urlparse(cdl_url)
        site_root = f"{parsed_cdl.scheme}://{parsed_cdl.netloc}"
        url_it = urljoin(site_root, href)
        url_en = build_english_syllabus_url(url_it)

        # Parse course code + name from link text.
        # Collapse all whitespace (including embedded newlines) to single spaces.
        raw_text = " ".join(a_course.get_text().split())
        m_course = _COURSE_RE.match(raw_text)
        if m_course:
            course_code = m_course.group(1)
            course_name = m_course.group(2).strip()
        else:
            course_code = ""
            course_name = raw_text

        # Cell 1: module (may be empty string)
        module_text = cells[1].get_text(strip=True)
        module = module_text if module_text else None

        # Cell 2: teacher
        teacher_text = cells[2].get_text(strip=True)

        results.append(
            {
                "cdl_id": cdl_id,
                "seuid": seuid,
                "course_code": course_code,
                "course_name": course_name,
                "module": module,
                "teacher": teacher_text,
                "academic_year": "",
                "year_of_study": current_year,
                "url_it": url_it,
                "url_en": url_en,
            }
        )

    return results


def scrape_syllabus_list(
    cdl_url: str,
    cdl_id: int,
    session: RateLimitedSession | None = None,
) -> list[dict]:
    """
    Fetch ``{cdl_url}/programmi`` and parse the syllabus list.

    Parameters
    ----------
    cdl_url:
        Base URL of the CdL (e.g. ``https://web.dmi.unict.it/corsi/lm-18``).
    cdl_id:
        Database ID of the CorsoDiLaurea.
    session:
        Optional :class:`RateLimitedSession`; a new one is created if not given.

    Returns
    -------
    List of syllabus metadata dicts.
    """
    if session is None:
        session = RateLimitedSession()

    url = cdl_url.rstrip("/") + "/programmi"
    response = session.get(url)
    return parse_syllabus_list(response.text, cdl_url, cdl_id)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Scrape syllabus list from a CdL /programmi page."
    )
    p.add_argument(
        "--cdl-url",
        required=True,
        help="CdL base URL, e.g. https://web.dmi.unict.it/corsi/lm-18",
    )
    p.add_argument(
        "--cdl-id",
        required=True,
        type=int,
        help="Database ID of the CorsoDiLaurea",
    )
    return p


if __name__ == "__main__":
    args = _build_parser().parse_args()
    syllabi = scrape_syllabus_list(cdl_url=args.cdl_url, cdl_id=args.cdl_id)
    print(f"Found {len(syllabi)} syllabi for CdL {args.cdl_id} ({args.cdl_url}):\n")
    for i, s in enumerate(syllabi, 1):
        print(
            f"  {i:3d}. [{s['year_of_study']}° anno]  "
            f"{s['course_code']:10s}  {s['course_name'][:45]:45s}  "
            f"module={s['module'] or '—':30s}  teacher={s['teacher']}"
        )
