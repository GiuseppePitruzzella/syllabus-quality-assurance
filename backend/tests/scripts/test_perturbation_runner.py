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
