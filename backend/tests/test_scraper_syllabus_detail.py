"""Tests for the syllabus detail parser."""

from pathlib import Path

import pytest

from app.scraper.syllabus_detail import parse_syllabus_page, scrape_syllabus_detail

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
        "learning_outcomes",
        "learning_outcomes",
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


def test_it_learning_outcomes_nonempty(parsed_it):
    assert parsed_it["learning_outcomes"], "learning_outcomes should not be empty (IT)"


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


def test_en_learning_outcomes_nonempty(parsed_en):
    assert parsed_en["learning_outcomes"], "learning_outcomes should not be empty (EN)"


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


def test_en_schedule_uses_canonical_keys(parsed_en):
    sched = parsed_en["schedule"]
    assert isinstance(sched, list)
    assert "argomenti" in sched[0]
    assert "riferimenti_testi" in sched[0]


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


def test_learning_outcomes_without_dublin_labels_are_preserved():
    html = """
    <html><body>
      <h2>Expected Learning Outcomes</h2>
      <p>The course aims to provide theoretical and practical skills.</p>
      <h2>Course Structure</h2>
      <p>Lectures and laboratory.</p>
    </body></html>
    """
    result = parse_syllabus_page(html, lang="en")
    assert result["learning_outcomes"] == (
        "The course aims to provide theoretical and practical skills."
    )
    assert result["dublin_knowledge"] == ""


def test_scrape_detail_marks_english_true_when_non_dublin_en_content_exists():
    class Response:
        def __init__(self, text: str):
            self.text = text

    class FakeSession:
        def __init__(self):
            self.responses = [
                Response("<html><body></body></html>"),
                Response("""
                <html><body>
                  <h2>Expected Learning Outcomes</h2>
                  <p>English learning outcomes exist but are not split.</p>
                  <h2>Detailed Course Content</h2>
                  <p>English content exists.</p>
                </body></html>
                """),
            ]

        def get(self, _url):
            return self.responses.pop(0)

    result = scrape_syllabus_detail("http://it", "http://en", session=FakeSession())
    assert result["has_english"] is True
    assert result["learning_outcomes_en"] == (
        "English learning outcomes exist but are not split."
    )


def test_empty_html_returns_dict_with_all_keys():
    result = parse_syllabus_page("<html><body></body></html>", lang="it")
    assert isinstance(result, dict)
    assert "learning_outcomes" in result
    assert "dublin_knowledge" in result
    assert result["learning_outcomes"] == ""
    assert result["dublin_knowledge"] == ""
    assert result["schedule"] is None
    assert result["assessment_methods"] == ""


def test_empty_html_en_returns_dict():
    result = parse_syllabus_page("<html><body></body></html>", lang="en")
    assert isinstance(result, dict)
    assert "dublin_knowledge" in result


# ---------------------------------------------------------------------------
# Phase 5.4.K.1 — ISSUE-PARSER-001: HTML comment residues
# ---------------------------------------------------------------------------


def test_no_html_comment_close_residues_in_any_field(parsed_it, parsed_en):
    """ISSUE-PARSER-001 regression guard on the real LM-18 fixture.

    Before the fix the SmartEdu CDATA-wrapped Word/Outlook style block
    leaked ``-->`` at the head of ``references_it``, ``assessment_methods_it``,
    ``sample_questions_it`` and the EN counterparts. The fix combines
    a pre-strip on the raw HTML with a safety net in
    ``_normalize_inline_text``; this test asserts nothing leaks into
    any extracted field.
    """
    for label, parsed in (("IT", parsed_it), ("EN", parsed_en)):
        for key, value in parsed.items():
            if isinstance(value, str):
                assert "-->" not in value, f"{label}/{key} still leaks '-->'"


def test_word_conditional_comments_are_stripped_pre_parse():
    """ISSUE-PARSER-001: synthetic Word ``<!--[if !supportLists]-->`` is removed."""
    html = """
    <html><body>
      <h2>Contenuti del corso</h2>
      <p><!--[if !supportLists]--><span>•</span><!--[endif]-->
         Argomento di prova
      </p>
    </body></html>
    """
    out = parse_syllabus_page(html, lang="it")
    assert "-->" not in out["course_content"]
    assert "<!--" not in out["course_content"]
    assert "Argomento di prova" in out["course_content"]


def test_cdata_wrapped_comment_with_dangling_close_is_cleaned():
    """ISSUE-PARSER-001: the CDATA-wrapped Word pattern is fully cleaned.

    This is the exact shape that produced the regression on the LM-18
    syllabi: an outer comment that the HTML parser fails to recognise
    as a single ``Comment`` node, leaving the closing ``-->`` orphan
    in the text output.
    """
    html = """
    <html><body>
      <style class="WebKit-mso-list-quirks-stylesheet"><!--
        /* css */
      --></style>
      <h2>Verifica dell'apprendimento</h2>
      <p>Esame orale.</p>
    </body></html>
    """
    out = parse_syllabus_page(html, lang="it")
    assert "-->" not in out["assessment_methods"]
    assert "Esame orale." in out["assessment_methods"]


# ---------------------------------------------------------------------------
# Phase 5.4.K.2 — ISSUE-PARSER-002: soft-hyphen word splits
# ---------------------------------------------------------------------------


def test_soft_hyphen_linebreak_is_collapsed():
    """ISSUE-PARSER-002: ``parola1-\\nparola2`` is rejoined as ``parola1parola2``.

    Word / PDF imports often word-wrap with a soft hyphen at the line
    break. The conservative fix only collapses the pattern
    ``\\w-\\n\\w`` so genuine compound words (e.g. ``Marco-Polo``,
    where the second part is on the same line) are untouched.
    """
    html = """
    <html><body>
      <h2>Contenuti del corso</h2>
      <p>Modelli di appren-\ndimento profondo per applicazioni reali.</p>
    </body></html>
    """
    out = parse_syllabus_page(html, lang="it")
    assert "apprendimento" in out["course_content"]
    assert "appren-" not in out["course_content"]


def test_adjacent_inline_spans_get_word_boundary():
    """Side-effect of ISSUE-PARSER-001 cleanup: adjacent ``<span>`` tags
    no longer collide on the assessment / schedule paths.

    Before the fix those paths used ``get_text(strip=True)`` without a
    separator, so ``<span>Modalità</span><span>verifica</span>``
    collapsed to ``Modalitàverifica``. Extending the 001 cleanup to
    these paths (via ``_extract_readable_text`` + ``_normalize_inline_text``)
    restored the word boundary as a bonus.
    """
    html = """
    <html><body>
      <h2>Verifica dell'apprendimento</h2>
      <h3>Modalità di verifica</h3>
      <p><span>Esame</span><span>orale</span> di trenta minuti.</p>
    </body></html>
    """
    out = parse_syllabus_page(html, lang="it")
    # The two words are kept distinct (the failure mode would be ``Esameorale``).
    assert "Esameorale" not in out["assessment_methods"]
    assert "Esame" in out["assessment_methods"]
    assert "orale" in out["assessment_methods"]
