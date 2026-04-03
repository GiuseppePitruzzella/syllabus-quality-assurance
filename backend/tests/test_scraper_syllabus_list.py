"""Tests for the syllabus list scraper."""
from pathlib import Path

import pytest

from app.scraper.syllabus_list import parse_syllabus_list

FIXTURES = Path(__file__).parent / "fixtures"
CDL_URL = "https://web.dmi.unict.it/corsi/lm-18"
CDL_ID = 1


@pytest.fixture
def lm18_html() -> str:
    return (FIXTURES / "lm18_programmi.html").read_text(encoding="utf-8")


@pytest.fixture
def lm18_syllabi(lm18_html) -> list[dict]:
    return parse_syllabus_list(lm18_html, CDL_URL, CDL_ID)


# ---------------------------------------------------------------------------
# Basic shape
# ---------------------------------------------------------------------------


def test_parse_returns_nonempty_list(lm18_syllabi):
    assert isinstance(lm18_syllabi, list)
    assert len(lm18_syllabi) > 0


def test_all_required_fields_present(lm18_syllabi):
    required = {
        "cdl_id",
        "seuid",
        "course_code",
        "course_name",
        "module",
        "teacher",
        "academic_year",
        "year_of_study",
        "url_it",
        "url_en",
    }
    for syl in lm18_syllabi:
        assert required.issubset(syl.keys()), f"Missing keys in {syl}"


# ---------------------------------------------------------------------------
# Field values
# ---------------------------------------------------------------------------


def test_seuid_never_empty(lm18_syllabi):
    for syl in lm18_syllabi:
        assert syl["seuid"], f"Empty seuid for {syl}"


def test_course_code_nonempty(lm18_syllabi):
    for syl in lm18_syllabi:
        assert syl["course_code"], f"Empty course_code for {syl}"


def test_course_name_nonempty(lm18_syllabi):
    for syl in lm18_syllabi:
        assert syl["course_name"], f"Empty course_name for {syl}"


def test_teacher_nonempty(lm18_syllabi):
    for syl in lm18_syllabi:
        assert syl["teacher"], f"Empty teacher for {syl}"


def test_cdl_id_matches(lm18_syllabi):
    for syl in lm18_syllabi:
        assert syl["cdl_id"] == CDL_ID


def test_url_it_starts_with_http(lm18_syllabi):
    for syl in lm18_syllabi:
        assert syl["url_it"].startswith("http"), f"Bad url_it: {syl['url_it']}"


def test_url_en_ends_with_eng(lm18_syllabi):
    for syl in lm18_syllabi:
        assert syl["url_en"].endswith("&eng"), f"Bad url_en: {syl['url_en']}"


def test_url_en_is_url_it_plus_eng(lm18_syllabi):
    for syl in lm18_syllabi:
        assert syl["url_en"] == syl["url_it"] + "&eng"


# ---------------------------------------------------------------------------
# Year tracking
# ---------------------------------------------------------------------------


def test_at_least_two_different_years(lm18_syllabi):
    years = {syl["year_of_study"] for syl in lm18_syllabi}
    assert len(years) >= 2, f"Expected >= 2 year values, got: {years}"


def test_year_of_study_is_digit_string(lm18_syllabi):
    for syl in lm18_syllabi:
        assert syl["year_of_study"].isdigit(), (
            f"year_of_study not a digit string: {syl['year_of_study']!r}"
        )


def test_year_1_appears_first(lm18_syllabi):
    """The first syllabus entry should belong to year 1."""
    assert lm18_syllabi[0]["year_of_study"] == "1"


def test_year_2_also_present(lm18_syllabi):
    years = {syl["year_of_study"] for syl in lm18_syllabi}
    assert "2" in years, f"year 2 not found; years present: {years}"


# ---------------------------------------------------------------------------
# Module handling
# ---------------------------------------------------------------------------


def test_module_can_be_none(lm18_syllabi):
    """Some courses have no module — module field should be None (not empty string)."""
    no_module = [s for s in lm18_syllabi if s["module"] is None]
    assert len(no_module) > 0, "Expected at least one entry with module=None"


def test_module_can_be_nonempty(lm18_syllabi):
    """Some courses have a module name."""
    with_module = [s for s in lm18_syllabi if s["module"] is not None]
    assert len(with_module) > 0, "Expected at least one entry with a module"


# ---------------------------------------------------------------------------
# Empty HTML
# ---------------------------------------------------------------------------


def test_empty_html_returns_empty_list():
    result = parse_syllabus_list("<html><body></body></html>", CDL_URL, CDL_ID)
    assert result == []
