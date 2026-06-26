from types import SimpleNamespace

from app.evaluation.analysis.local_requirements import (
    normalize_text,
    scan_local_requirements,
)


def test_normalize_text_handles_accents_apostrophes_and_newlines():
    assert normalize_text("L’apprendimento\npotrà essere effettuato") == (
        "l apprendimento potra essere effettuato"
    )


def test_scan_detects_local_clauses_grid_and_complete_schedule():
    syllabus = SimpleNamespace(
        seuid="S1",
        course_name="Test",
        teaching_methods_it=(
            "Qualora l'insegnamento venisse impartito in modalità mista o a "
            "distanza potranno essere introdotte le necessarie variazioni "
            "rispetto al programma previsto."
        ),
        assessment_methods_it=(
            "Gli studenti con disabilità e/o DSA contattino il CInAP per le "
            "misure compensative. La verifica dell'apprendimento potrà essere "
            "effettuata anche per via telematica. Non approvato; 18-23; "
            "24-27; 28-30 e lode."
        ),
        schedule_it=[
            {"argomenti": "Introduzione", "riferimenti_testi": "Cap. 1"},
            {"argomenti": "Metodi", "riferimenti_testi": "Cap. 2"},
        ],
    )

    result = scan_local_requirements(syllabus)

    assert result["mixed_distance_clause"] is True
    assert result["cinap_dsa_clause"] is True
    assert result["telematic_assessment_clause"] is True
    assert result["grading_grid_complete"] is True
    assert result["schedule_topics_complete"] is True
    assert result["schedule_references_complete"] is True


def test_scan_keeps_partial_grid_and_schedule_signals_explicit():
    syllabus = SimpleNamespace(
        seuid="S2",
        course_name="Partial",
        teaching_methods_it="Lezioni frontali.",
        assessment_methods_it="Prova orale. 18-23 e 24-27.",
        schedule_it=[
            {"argomenti": "Introduzione", "riferimenti_testi": ""},
            {"argomenti": "", "riferimenti_testi": ""},
        ],
    )

    result = scan_local_requirements(syllabus)

    assert result["mixed_distance_clause"] is False
    assert result["grading_grid_complete"] is False
    assert result["grading_grid_signals"]["band_18_23"] is True
    assert result["grading_grid_signals"]["band_28_30"] is False
    assert result["schedule_present"] is True
    assert result["schedule_topics_complete"] is False
    assert result["schedule_references_any"] is False
