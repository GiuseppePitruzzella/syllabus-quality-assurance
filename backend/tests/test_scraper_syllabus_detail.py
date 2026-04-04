"""Tests for the syllabus detail parser."""

from pathlib import Path

import pytest

from app.scraper.syllabus_detail import parse_syllabus_page

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def it_html() -> str:
    return (FIXTURES / "syllabus_it.html").read_text(encoding="utf-8")


@pytest.fixture
def en_html() -> str:
    return (FIXTURES / "syllabus_en.html").read_text(encoding="utf-8")


@pytest.fixture
def parsed_it(it_html) -> dict:
    return parse_syllabus_page(it_html, lang="it")


@pytest.fixture
def parsed_en(en_html) -> dict:
    return parse_syllabus_page(en_html, lang="en")


# ---------------------------------------------------------------------------
# Basic shape
# ---------------------------------------------------------------------------


def test_parse_it_returns_dict(parsed_it):
    assert isinstance(parsed_it, dict)


def test_parse_en_returns_dict(parsed_en):
    assert isinstance(parsed_en, dict)


def test_it_has_all_expected_keys(parsed_it):
    expected_keys = {
        "dublin_knowledge",
        "dublin_applying",
        "dublin_judgement",
        "dublin_communication",
        "dublin_learning",
        "teaching_methods",
        "prerequisites",
        "attendance",
        "course_content",
        "references",
        "schedule",
        "assessment_methods",
        "sample_questions",
    }
    assert expected_keys.issubset(parsed_it.keys()), (
        f"Missing keys: {expected_keys - parsed_it.keys()}"
    )


def test_en_has_all_expected_keys(parsed_en):
    expected_keys = {
        "dublin_knowledge",
        "dublin_applying",
        "dublin_judgement",
        "dublin_communication",
        "dublin_learning",
        "teaching_methods",
        "prerequisites",
        "attendance",
        "course_content",
        "references",
        "schedule",
        "assessment_methods",
        "sample_questions",
    }
    assert expected_keys.issubset(parsed_en.keys()), (
        f"Missing keys: {expected_keys - parsed_en.keys()}"
    )


# ---------------------------------------------------------------------------
# Dublin Descriptors — Italian
# ---------------------------------------------------------------------------


def test_it_dublin_knowledge_nonempty(parsed_it):
    assert parsed_it["dublin_knowledge"], "dublin_knowledge should not be empty (IT)"


def test_it_dublin_applying_nonempty(parsed_it):
    assert parsed_it["dublin_applying"], "dublin_applying should not be empty (IT)"


def test_it_dublin_judgement_nonempty(parsed_it):
    assert parsed_it["dublin_judgement"], "dublin_judgement should not be empty (IT)"


def test_it_dublin_communication_nonempty(parsed_it):
    assert parsed_it["dublin_communication"], "dublin_communication should not be empty (IT)"


def test_it_dublin_learning_nonempty(parsed_it):
    assert parsed_it["dublin_learning"], "dublin_learning should not be empty (IT)"


# ---------------------------------------------------------------------------
# Dublin Descriptors — English
# ---------------------------------------------------------------------------


def test_en_dublin_knowledge_exists(parsed_en):
    """EN Dublin Descriptors exist as keys (may be empty if not translated)."""
    assert "dublin_knowledge" in parsed_en


def test_en_dublin_applying_exists(parsed_en):
    assert "dublin_applying" in parsed_en


def test_en_dublin_judgement_exists(parsed_en):
    assert "dublin_judgement" in parsed_en


def test_en_dublin_communication_exists(parsed_en):
    assert "dublin_communication" in parsed_en


def test_en_dublin_learning_exists(parsed_en):
    assert "dublin_learning" in parsed_en


def test_en_dublin_descriptors_nonempty(parsed_en):
    """This specific fixture has EN translations, so they should be non-empty."""
    dublin_keys = [
        "dublin_knowledge", "dublin_applying", "dublin_judgement",
        "dublin_communication", "dublin_learning",
    ]
    non_empty = [k for k in dublin_keys if parsed_en[k]]
    assert len(non_empty) > 0, "Expected at least some EN Dublin Descriptors to be non-empty"


# ---------------------------------------------------------------------------
# Content sections — Italian
# ---------------------------------------------------------------------------


def test_it_teaching_methods_nonempty(parsed_it):
    assert parsed_it["teaching_methods"], "teaching_methods should not be empty (IT)"


def test_it_prerequisites_nonempty(parsed_it):
    assert parsed_it["prerequisites"], "prerequisites should not be empty (IT)"


def test_it_attendance_nonempty(parsed_it):
    assert parsed_it["attendance"], "attendance should not be empty (IT)"


def test_it_course_content_nonempty(parsed_it):
    assert parsed_it["course_content"], "course_content should not be empty (IT)"


def test_it_references_nonempty(parsed_it):
    assert parsed_it["references"], "references should not be empty (IT)"


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------


def test_it_schedule_is_list_or_none(parsed_it):
    sched = parsed_it["schedule"]
    assert sched is None or isinstance(sched, list)


def test_it_schedule_has_entries(parsed_it):
    """This fixture has a schedule table, so it should parse to a non-empty list."""
    sched = parsed_it["schedule"]
    assert isinstance(sched, list), "Expected schedule to be a list for this fixture"
    assert len(sched) > 0, "Expected schedule to have entries"


def test_it_schedule_entries_are_dicts(parsed_it):
    sched = parsed_it["schedule"]
    if sched:
        for entry in sched:
            assert isinstance(entry, dict), f"Schedule entry should be dict, got {type(entry)}"


def test_it_schedule_entry_has_argomenti_key(parsed_it):
    """Schedule entries should contain normalized 'argomenti' key."""
    sched = parsed_it["schedule"]
    if sched:
        assert "argomenti" in sched[0], f"Expected 'argomenti' key, got {list(sched[0].keys())}"


def test_en_schedule_is_list_or_none(parsed_en):
    sched = parsed_en["schedule"]
    assert sched is None or isinstance(sched, list)


def test_en_schedule_has_entries(parsed_en):
    """EN fixture also has a schedule table."""
    sched = parsed_en["schedule"]
    assert isinstance(sched, list), "Expected EN schedule to be a list"
    assert len(sched) > 0


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


def test_it_assessment_methods_nonempty(parsed_it):
    assert parsed_it["assessment_methods"], "assessment_methods should not be empty (IT)"


def test_it_sample_questions_nonempty(parsed_it):
    assert parsed_it["sample_questions"], "sample_questions should not be empty (IT)"


def test_en_assessment_methods_nonempty(parsed_en):
    assert parsed_en["assessment_methods"], "assessment_methods should not be empty (EN)"


def test_en_sample_questions_nonempty(parsed_en):
    assert parsed_en["sample_questions"], "sample_questions should not be empty (EN)"


# ---------------------------------------------------------------------------
# Empty / malformed HTML
# ---------------------------------------------------------------------------


def test_empty_html_returns_dict_with_all_keys():
    result = parse_syllabus_page("<html><body></body></html>", lang="it")
    assert isinstance(result, dict)
    assert "dublin_knowledge" in result
    assert result["dublin_knowledge"] == ""
    assert result["schedule"] is None
    assert result["assessment_methods"] == ""


def test_empty_html_en_returns_dict():
    result = parse_syllabus_page("<html><body></body></html>", lang="en")
    assert isinstance(result, dict)
    assert "dublin_knowledge" in result
