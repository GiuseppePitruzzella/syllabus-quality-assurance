import json

from scripts.analyze_expert_feedback import (
    _c3_c4_overlap,
    _classify_c7_reason,
)


def test_c7_reason_classification_separates_format_conflict():
    assert _classify_c7_reason(
        "Non c'è una struttura a blocchi, ma le istruzioni chiedevano "
        "un ragionamento discorsivo."
    ) == "block_or_module_structure"


def test_c7_reason_classification_separates_detail_and_narrative():
    assert _classify_c7_reason(
        "La descrizione è molto stringata e potrebbe essere approfondita."
    ) == "insufficient_detail"
    assert _classify_c7_reason(
        "Potrebbero essere indicati in maniera più discorsiva."
    ) == "narrative_form"


def test_c3_c4_overlap_reads_validation_and_repeated_run_artifacts(tmp_path):
    validation_dir = tmp_path / "validation"
    consistency_dir = tmp_path / "consistency"
    validation_dir.mkdir()
    consistency_dir.mkdir()
    (validation_dir / "S1__evaluation.json").write_text(
        json.dumps(
            {
                "seuid": "S1",
                "evaluation": {
                    "course_name_snapshot": "Course one",
                    "criterion_scores": {"C3": 2, "C4": 2},
                },
            }
        ),
        encoding="utf-8",
    )
    (validation_dir / "S2__evaluation.json").write_text(
        json.dumps(
            {
                "seuid": "S2",
                "evaluation": {
                    "course_name_snapshot": "Course two",
                    "criterion_scores": {"C3": 1, "C4": 2},
                },
            }
        ),
        encoding="utf-8",
    )
    for run_index, scores in enumerate(((2, 2), (2, 1)), start=1):
        (consistency_dir / f"S1__run{run_index}__evaluation.json").write_text(
            json.dumps(
                {
                    "seuid": "S1",
                    "slug": "course_one",
                    "run_index": run_index,
                    "criterion_scores": {"C3": scores[0], "C4": scores[1]},
                }
            ),
            encoding="utf-8",
        )

    result = _c3_c4_overlap(validation_dir, consistency_dir)

    validation = result["validation_lm18"]
    assert validation["n_pairs"] == 2
    assert validation["exact_agreement_count"] == 1
    assert validation["both_score_2"] == 1
    assert validation["divergent_cases"][0]["seuid"] == "S2"
    consistency = result["self_consistency"]
    assert consistency["n_pairs"] == 2
    assert consistency["exact_agreement_count"] == 1
