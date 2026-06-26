"""Regression tests for Phase 5.8 human-judgment aggregation."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts import aggregate_human_judgment as agg


def test_metric_summary_excludes_na_and_missing_from_primary_metrics():
    pairs = [
        (2, 2),
        (2, 1),
        (1, "NA"),
        ("MISSING", 1),
    ]

    summary = agg._metric_summary(pairs)

    assert summary["n_observations"] == 4
    assert summary["n_primary_pairs"] == 2
    assert summary["n_excluded_na"] == 1
    assert summary["n_excluded_missing"] == 1
    assert summary["accuracy"] == 0.5
    assert summary["mae"] == 0.5


def test_confusion_matrix_keeps_process_labels_for_audit():
    pairs = [(2, 2), (1, "NA"), ("MISSING", 0)]

    matrix = agg._confusion_matrix(pairs)

    assert matrix["2"]["2"] == 1
    assert matrix["1"]["NA"] == 1
    assert matrix["MISSING"]["0"] == 1


def test_evaluator_analysis_reports_na_and_missing_separately(
    tmp_path: Path,
    monkeypatch,
):
    seuid = "TEST-SEUID-0001"
    slug = "01_TEST_SYLLABUS"
    validation_dir = tmp_path / "validation_lm18"
    blind_dir = tmp_path / "evaluators" / "eval_01" / "blind"
    validation_dir.mkdir()
    blind_dir.mkdir(parents=True)
    monkeypatch.setattr(agg, "VALIDATION", validation_dir)

    _write_system_evaluation(validation_dir / f"{seuid}__evaluation.json")
    _write_blind_csv(
        blind_dir / f"{slug}_blind.csv",
        {
            "C1": ("2", "false"),
            "C2": ("1", "false"),
            "C3": ("", "false"),
            "C4": ("", "true"),
            "C5": ("2", "false"),
            "C6": ("2", "false"),
            "C7": ("2", "false"),
            "C8": ("2", "false"),
            "C9": ("2", "false"),
        },
    )

    report = agg._evaluator_analysis("eval_01", blind_dir, {seuid: slug})

    assert report["macro"]["n_observations"] == 9
    assert report["macro"]["n_primary_pairs"] == 7
    assert report["macro"]["n_excluded_na"] == 1
    assert report["macro"]["n_excluded_missing"] == 1
    assert report["per_criterion"]["C3"]["n_excluded_missing"] == 1
    assert report["per_criterion"]["C4"]["n_excluded_na"] == 1
    assert report["tier_metrics"]["primary"]["criteria"] == ["C1", "C3", "C4", "C5", "C6"]
    assert report["tier_metrics"]["primary"]["n_primary_pairs"] == 3
    assert report["tier_metrics"]["secondary"]["n_primary_pairs"] == 4
    assert report["tier_metrics"]["excluded"]["criteria"] == []
    assert report["top_disagreements"][0]["criterion"] == "C4"
    assert {d["criterion"] for d in report["top_disagreements"]} == {"C2", "C4"}


def test_single_rater_markdown_declares_diagnostic_scope():
    markdown = agg._render_markdown({
        "generated_at": "2026-06-17T00:00:00+00:00",
        "evaluators": [{
            "evaluator_id": "relatore",
            "n_syllabi": 1,
            "macro": {
                "n_observations": 9,
                "n_primary_pairs": 9,
                "n_excluded_na": 0,
                "n_excluded_missing": 0,
                "kappa_linear_weighted": 1.0,
                "accuracy": 1.0,
                "mae": 0.0,
            },
            "per_criterion": {
                c: {
                    "n_observations": 1,
                    "n_primary_pairs": 1,
                    "n_excluded_na": 0,
                    "n_excluded_missing": 0,
                    "kappa_linear_weighted": 1.0,
                    "accuracy": 1.0,
                    "mae": 0.0,
                }
                for c in agg.CRITERIA
            },
            "core_score_comparison": {
                "mean_absolute_error": 0.0,
                "per_syllabus": {
                    "TEST-SEUID-0001": {
                        "course_name": "Test course",
                        "system_core": 2.0,
                        "human_core": 2.0,
                    }
                },
            },
            "top_disagreements": [],
        }],
        "human_human": None,
    })

    assert "Single-rater diagnostic validation" in markdown
    assert "No automatic majority/consensus score is computed." in markdown
    assert "Inter-evaluator agreement" not in markdown


def _write_system_evaluation(path: Path) -> None:
    judgments = [
        {
            "criterion_code": c,
            "score": 2,
            "is_na": False,
            "justification": f"System justification for {c}",
        }
        for c in agg.CRITERIA
    ]
    path.write_text(
        json.dumps({
            "evaluation": {
                "course_name_snapshot": "Test course",
                "agent_outputs": {
                    "A": {"judgments": judgments},
                },
            }
        }),
        encoding="utf-8",
    )


def _write_blind_csv(path: Path, rows: dict[str, tuple[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "criterion",
            "human_score",
            "is_na",
            "na_reason",
            "human_justification",
            "evidence_quote",
        ])
        for criterion, (score, is_na) in rows.items():
            writer.writerow([
                criterion,
                score,
                is_na,
                "technical NA" if is_na == "true" else "",
                f"Human justification for {criterion}",
                f"Evidence for {criterion}",
            ])
