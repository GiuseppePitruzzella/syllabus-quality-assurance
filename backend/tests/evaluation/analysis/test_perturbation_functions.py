import copy

from app.evaluation.analysis.perturbation import (
    PERTURBATIONS,
    generate_variants,
    perturbation_by_id,
)


def _base():
    return {
        "course_name": "Deep Learning",
        "course_name_en": "Deep Learning",
        "has_english": True,
        "learning_outcomes_it": "Conoscenza approfondita di X e Y.",
        "learning_outcomes_en": "In-depth knowledge of X and Y.",
        "dublin_knowledge_it": "kn it", "dublin_applying_it": "ap it",
        "dublin_judgement_it": "ju it", "dublin_communication_it": "co it",
        "dublin_learning_it": "le it",
        "dublin_knowledge_en": "kn en", "dublin_applying_en": "ap en",
        "dublin_judgement_en": "ju en", "dublin_communication_en": "co en",
        "dublin_learning_en": "le en",
        "teaching_methods_it": "Lezioni frontali e laboratorio.",
        "teaching_methods_en": "Lectures and lab.",
        "prerequisites_it": "Solide basi di reti neurali.",
        "prerequisites_en": "Solid foundations of neural networks.",
        "attendance_it": "Frequenza consigliata.",
        "attendance_en": "Attendance recommended.",
        "course_content_it": "1. Metric learning\n2. Transformer",
        "course_content_en": "1. Metric learning\n2. Transformer",
        "references_it": "1. Materiale del docente",
        "references_en": "1. Teacher material",
        "schedule_it": [{"numero": "1", "argomenti": "Metric Learning"}],
        "schedule_en": [{"numero": "1", "argomenti": "Metric Learning"}],
        "assessment_methods_it": "Griglia: 0-17 insufficiente ... peso 50%.",
        "assessment_methods_en": "Grid: 0-17 fail ... weight 50%.",
        "sample_questions_it": "Illustrare il metric learning.",
        "sample_questions_en": "Illustrate metric learning.",
    }


def test_registry_has_seven_perturbations_with_unique_ids():
    ids = [p.id for p in PERTURBATIONS]
    assert ids == [
        "C1_remove_sections", "C2_strip_english", "C3C4_generic_outcomes",
        "C5_blank_prerequisites", "C6_strip_assessment",
        "C7_remove_schedule", "C9_editorial_noise",
    ]
    assert len(set(ids)) == 7
    assert all(p.expected_direction == "decrease" for p in PERTURBATIONS)


def test_perturbations_do_not_mutate_the_base_in_place():
    base = _base()
    frozen = copy.deepcopy(base)
    for p in PERTURBATIONS:
        p.apply(base)
    assert base == frozen  # pure: base untouched


def test_c1_blanks_three_sections_only():
    out = perturbation_by_id("C1_remove_sections").apply(_base())
    for f in ("teaching_methods_it", "teaching_methods_en", "attendance_it",
              "attendance_en", "references_it", "references_en"):
        assert out[f] == ""
    assert out["prerequisites_it"] != ""  # stays distinct from C5
    assert out["learning_outcomes_it"] != ""  # untouched


def test_c2_blanks_relevant_english_fields():
    out = perturbation_by_id("C2_strip_english").apply(_base())
    for f in ("course_name_en", "learning_outcomes_en", "dublin_knowledge_en",
              "dublin_applying_en", "dublin_judgement_en",
              "dublin_communication_en", "dublin_learning_en",
              "course_content_en", "assessment_methods_en"):
        assert out[f] == ""
    assert out["learning_outcomes_it"] != ""  # IT untouched


def test_c3c4_makes_outcomes_generic_and_repetitive():
    out = perturbation_by_id("C3C4_generic_outcomes").apply(_base())
    it_vals = {out["learning_outcomes_it"], out["dublin_knowledge_it"],
               out["dublin_applying_it"], out["dublin_judgement_it"]}
    assert len(it_vals) == 1  # repetitive across descriptors
    assert "fornisce conoscenze" in out["learning_outcomes_it"]


def test_c5_uses_clearly_negative_prerequisites():
    out = perturbation_by_id("C5_blank_prerequisites").apply(_base())
    assert out["prerequisites_it"] == "Prerequisiti non indicati."
    assert out["prerequisites_en"] == "Prerequisites not specified."


def test_c6_strips_grid_and_blanks_sample_questions():
    out = perturbation_by_id("C6_strip_assessment").apply(_base())
    assert "Griglia" not in out["assessment_methods_it"]
    assert out["sample_questions_it"] == ""
    assert out["sample_questions_en"] == ""


def test_c7_empties_schedule_and_flattens_content():
    out = perturbation_by_id("C7_remove_schedule").apply(_base())
    assert out["schedule_it"] == []
    assert out["schedule_en"] == []
    assert "\n" not in out["course_content_it"]  # flattened blob


def test_c9_injects_markers_and_typos():
    out = perturbation_by_id("C9_editorial_noise").apply(_base())
    assert "[TODO]" in out["course_content_it"]
    assert "�" in out["course_content_it"]
    assert out["learning_outcomes_it"] != _base()["learning_outcomes_it"]


def test_generate_variants_returns_all_seven_snapshots():
    variants = generate_variants(_base())
    assert set(variants) == {p.id for p in PERTURBATIONS}
    assert all(isinstance(v, dict) for v in variants.values())
