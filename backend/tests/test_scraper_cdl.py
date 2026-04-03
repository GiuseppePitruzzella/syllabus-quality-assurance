"""Tests for the CdL discovery scraper."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.scraper.cdl_discovery import parse_cdl_page, scrape_cdl

FIXTURES = Path(__file__).parent / "fixtures"
DEPT_URL = "https://web.dmi.unict.it"
DEPT_ID = 1
VALID_TYPES = {"Triennale", "Magistrale", "Ciclo Unico"}


@pytest.fixture
def dmi_html() -> str:
    return (FIXTURES / "dmi_homepage.html").read_text(encoding="utf-8")


@pytest.fixture
def dmi_cdl_list(dmi_html) -> list[dict]:
    return parse_cdl_page(dmi_html, DEPT_URL, DEPT_ID)


# ---------------------------------------------------------------------------
# Basic shape
# ---------------------------------------------------------------------------


def test_parse_returns_nonempty_list(dmi_cdl_list):
    """Parser must find at least one CdL."""
    assert isinstance(dmi_cdl_list, list)
    assert len(dmi_cdl_list) > 0


def test_each_cdl_has_required_fields(dmi_cdl_list):
    """Every CdL dict must have the mandatory keys."""
    required = {"department_id", "name", "code", "type", "url"}
    for cdl in dmi_cdl_list:
        assert required.issubset(cdl.keys()), f"Missing keys in {cdl}"


# ---------------------------------------------------------------------------
# Field values
# ---------------------------------------------------------------------------


def test_name_is_nonempty_string(dmi_cdl_list):
    for cdl in dmi_cdl_list:
        assert isinstance(cdl["name"], str) and cdl["name"].strip() != "", \
            f"Empty name: {cdl}"


def test_code_is_nonempty_string(dmi_cdl_list):
    for cdl in dmi_cdl_list:
        assert isinstance(cdl["code"], str) and cdl["code"].strip() != "", \
            f"Empty code: {cdl}"


def test_type_is_valid(dmi_cdl_list):
    """type must be one of the three canonical values."""
    for cdl in dmi_cdl_list:
        assert cdl["type"] in VALID_TYPES, \
            f"Unexpected type {cdl['type']!r} for {cdl['name']}"


def test_url_starts_with_http(dmi_cdl_list):
    for cdl in dmi_cdl_list:
        assert cdl["url"].startswith("http"), \
            f"Bad URL {cdl['url']!r} for {cdl['name']}"


def test_department_id_matches(dmi_cdl_list):
    for cdl in dmi_cdl_list:
        assert cdl["department_id"] == DEPT_ID


# ---------------------------------------------------------------------------
# No dottorati
# ---------------------------------------------------------------------------


def test_no_dottorati(dmi_cdl_list):
    """Dottorati must not appear in results."""
    for cdl in dmi_cdl_list:
        assert "dottorat" not in cdl["name"].lower(), \
            f"Dottorato found in results: {cdl}"
        assert "dottorat" not in cdl["url"].lower(), \
            f"Dottorato URL found in results: {cdl}"


# ---------------------------------------------------------------------------
# DMI-specific known courses
# ---------------------------------------------------------------------------


def test_known_courses_present(dmi_cdl_list):
    """DMI should expose at least Informatica and Matematica."""
    names = {cdl["name"] for cdl in dmi_cdl_list}
    assert "Informatica" in names, f"Informatica not found. Got: {names}"
    assert "Matematica" in names, f"Matematica not found. Got: {names}"


def test_triennale_informatica_code(dmi_cdl_list):
    """Triennale Informatica should have code l-31."""
    triennali = [c for c in dmi_cdl_list if c["type"] == "Triennale" and c["name"] == "Informatica"]
    assert triennali, "No Triennale Informatica found"
    assert triennali[0]["code"] == "l-31"


def test_magistrale_informatica_code(dmi_cdl_list):
    """Magistrale Informatica should have code lm-18."""
    magistrali = [c for c in dmi_cdl_list if c["type"] == "Magistrale" and c["name"] == "Informatica"]
    assert magistrali, "No Magistrale Informatica found"
    assert magistrali[0]["code"] == "lm-18"


# ---------------------------------------------------------------------------
# scrape_cdl fallback behaviour
# ---------------------------------------------------------------------------


def test_scrape_cdl_fallback_to_it(dmi_html):
    """If primary URL yields nothing, scrape_cdl should retry with /it."""
    empty_response = MagicMock()
    empty_response.text = "<html><body>No courses here</body></html>"

    real_response = MagicMock()
    real_response.text = dmi_html

    session = MagicMock()
    # First call (primary URL) returns empty page; second call (/it) returns real page.
    session.get.side_effect = [empty_response, real_response]

    results = scrape_cdl(dept_url=DEPT_URL, dept_id=DEPT_ID, session=session)

    assert session.get.call_count == 2
    assert session.get.call_args_list[1][0][0] == DEPT_URL.rstrip("/") + "/it"
    assert len(results) > 0


def test_scrape_cdl_no_fallback_when_results_found(dmi_html):
    """If primary URL yields results, scrape_cdl should NOT make a second request."""
    real_response = MagicMock()
    real_response.text = dmi_html

    session = MagicMock()
    session.get.return_value = real_response

    results = scrape_cdl(dept_url=DEPT_URL, dept_id=DEPT_ID, session=session)

    assert session.get.call_count == 1
    assert len(results) > 0
