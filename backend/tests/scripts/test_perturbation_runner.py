import importlib.util
import json
from pathlib import Path

from app.evaluation.aggregator import AggregatedResult


def _load_runner():
    script = Path(__file__).resolve().parents[2] / "scripts" / "perturbation_sensitivity.py"
    spec = importlib.util.spec_from_file_location("perturbation_runner", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


def _final_state(scores, status="completed", core=2.0):
    agg = AggregatedResult(
        criterion_scores=scores, core_score=core, coverage=1.0, na_criteria=[],
        status=status, agent_statuses={"A1": "ok"},
    )
    return {"aggregation": agg, "status": status, "agent_errors": {},
            "final_report": "## ignored\n"}


def _base_snapshot():
    return {
        "course_name": "Deep Learning", "course_name_en": "Deep Learning",
        "has_english": True,
        "learning_outcomes_it": "x", "learning_outcomes_en": "x",
        "dublin_knowledge_it": "x", "dublin_applying_it": "x",
        "dublin_judgement_it": "x", "dublin_communication_it": "x",
        "dublin_learning_it": "x", "dublin_knowledge_en": "x",
        "dublin_applying_en": "x", "dublin_judgement_en": "x",
        "dublin_communication_en": "x", "dublin_learning_en": "x",
        "teaching_methods_it": "x", "teaching_methods_en": "x",
        "prerequisites_it": "x", "prerequisites_en": "x",
        "attendance_it": "x", "attendance_en": "x",
        "course_content_it": "1\n2", "course_content_en": "1\n2",
        "references_it": "x", "references_en": "x",
        "schedule_it": [{"numero": "1"}], "schedule_en": [{"numero": "1"}],
        "assessment_methods_it": "Griglia x", "assessment_methods_en": "Grid x",
        "sample_questions_it": "x", "sample_questions_en": "x",
    }


def test_execute_run_drops_report_text():
    scores = {f"C{i}": 2 for i in range(1, 10)}
    rec = runner.execute_run(lambda s: _final_state(scores),
                             "base", _base_snapshot(), "Deep Learning", 1)
    assert rec["condition"] == "base"
    assert rec["run_index"] == 1
    assert rec["criterion_scores"]["C1"] == 2
    assert "final_report" not in rec


def test_build_variants_freezes_eight_snapshots(tmp_path):
    conditions = runner.build_variants(_base_snapshot(), tmp_path)
    ids = [c[0] for c in conditions]
    assert ids[0] == "base"
    assert len(conditions) == 8
    assert (tmp_path / "variants" / "base.json").exists()
    assert (tmp_path / "variants" / "C6_strip_assessment.json").exists()
    frozen = json.loads((tmp_path / "variants" / "C5_blank_prerequisites.json").read_text())
    assert frozen["prerequisites_it"] == "Prerequisiti non indicati."


def test_run_campaign_writes_24_dumps_and_resumes(tmp_path):
    calls = {"n": 0}

    def invoker(state):
        calls["n"] += 1
        return _final_state({f"C{i}": 2 for i in range(1, 10)})

    conditions = runner.build_variants(_base_snapshot(), tmp_path)
    records = runner.run_campaign(
        conditions=conditions, runs=3, output_dir=tmp_path,
        graph_invoker=invoker, course_name="Deep Learning", resume=True,
    )
    assert len(records) == 24
    assert calls["n"] == 24
    dumps = sorted((tmp_path / "runs").glob("*__run*__evaluation.json"))
    assert len(dumps) == 24

    runner.run_campaign(
        conditions=conditions, runs=3, output_dir=tmp_path,
        graph_invoker=invoker, course_name="Deep Learning", resume=True,
    )
    assert calls["n"] == 24  # all resumed, no new invocations


def test_build_manifest_has_git_and_config():
    manifest = runner.build_manifest("DL", 3, Path("/tmp/out"))
    assert manifest["experiment"] == "perturbation_sensitivity_v1"
    assert manifest["base_seuid"] == "DL"
    assert set(manifest["git"]) == {"commit", "branch", "dirty"}
    assert manifest["scientific_config"]["llm_model"]
    assert manifest["prompt_versions"]


def test_write_outputs_creates_all_artifacts(tmp_path):
    full2 = {f"C{i}": 2 for i in range(1, 10)}
    c6_low = {**full2, "C6": 0}
    records = []
    for i in range(1, 4):
        records.append({"condition": "base", "run_index": i, "status": "completed",
                        "criterion_scores": full2, "core_score": 2.0, "coverage": 1.0,
                        "na_criteria": [], "agent_errors": {}, "duration_ms": 1})
    for p in runner.PERTURBATIONS:
        sc = c6_low if p.id == "C6_strip_assessment" else full2
        for i in range(1, 4):
            records.append({"condition": p.id, "run_index": i, "status": "completed",
                            "criterion_scores": sc, "core_score": 2.0, "coverage": 1.0,
                            "na_criteria": [], "agent_errors": {}, "duration_ms": 1})

    manifest = runner.build_manifest("DL", 3, tmp_path)
    runner.write_outputs(tmp_path, records, manifest)

    assert (tmp_path / "metrics.json").exists()
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "protocol.md").exists()
    assert (tmp_path / "summary.md").exists()
    assert (tmp_path / "analysis.md").exists()
    assert (tmp_path / "tables" / "tbl_perturbation_deltas.tex").exists()
    assert (tmp_path / "tables" / "tbl_side_effects.tex").exists()

    metrics = json.loads((tmp_path / "metrics.json").read_text())
    by_id = {v["variant_id"]: v for v in metrics["variants"]}
    assert by_id["C6_strip_assessment"]["passed"] is True


def test_dry_run_plan_lists_variants_and_expectations(tmp_path):
    plan = runner.format_plan("DL", "Deep Learning", 3,
                              runner.build_variants(_base_snapshot(), tmp_path))
    assert "24" in plan          # total runs
    assert "C6_strip_assessment" in plan
    assert "C6" in plan          # expected target shown
