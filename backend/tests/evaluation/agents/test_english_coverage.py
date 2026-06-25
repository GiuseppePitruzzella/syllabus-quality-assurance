from app.evaluation.agents.english_coverage import (
    english_coverage,
    suggest_c2,
)


def _fields(**kw):
    base = {
        "course_name_en": None,
        "learning_outcomes_en": None,
        "course_content_en": None,
        "assessment_methods_en": None,
    }
    base.update(kw)
    return base


def test_full_informative_coverage_suggests_2():
    cov = english_coverage(_fields(
        course_name_en="Computer Vision",
        learning_outcomes_en="The student will be able to design CV pipelines and evaluate models.",
        course_content_en="Convolutional networks, detection, segmentation, transformers.",
        assessment_methods_en="Written exam plus a graded project with an oral discussion.",
    ))
    assert cov == {"title_en": True, "learning_outcomes_en": True,
                   "course_content_en": True, "assessment_methods_en": True}
    assert suggest_c2(cov) == 2


def test_missing_assessment_suggests_1():
    cov = english_coverage(_fields(
        course_name_en="Computer Vision",
        learning_outcomes_en="The student will be able to design CV pipelines and evaluate models.",
        course_content_en="Convolutional networks, detection, segmentation.",
        assessment_methods_en="",
    ))
    assert cov["assessment_methods_en"] is False
    assert suggest_c2(cov) == 1


def test_title_only_suggests_0():
    cov = english_coverage(_fields(course_name_en="Internet of Things"))
    assert cov == {"title_en": True, "learning_outcomes_en": False,
                   "course_content_en": False, "assessment_methods_en": False}
    assert suggest_c2(cov) == 0


def test_title_missing_but_informative_present_suggests_2():
    # title non-blocking: no course_name_en, but 3 informative sections present
    cov = english_coverage(_fields(
        learning_outcomes_en="The student will be able to design CV pipelines and evaluate models.",
        course_content_en="Convolutional networks, detection, segmentation, transformers.",
        assessment_methods_en="Written exam plus a graded project with an oral discussion.",
    ))
    assert cov["title_en"] is False
    assert suggest_c2(cov) == 2


def test_placeholder_denylist_counts_as_absent():
    for placeholder in ("n/a", "Not available", "See Italian version for details",
                        "VERSIONE IN ITALIANO", "—"):
        cov = english_coverage(_fields(
            learning_outcomes_en=placeholder,
            course_content_en=placeholder,
            assessment_methods_en=placeholder,
        ))
        assert cov["learning_outcomes_en"] is False, placeholder
        assert suggest_c2(cov) == 0, placeholder


def test_min_chars_boundary():
    # 9 chars -> absent; 10 chars -> present
    nine = "123456789"
    ten = "1234567890"
    assert english_coverage(_fields(learning_outcomes_en=nine))["learning_outcomes_en"] is False
    assert english_coverage(_fields(learning_outcomes_en=ten))["learning_outcomes_en"] is True
