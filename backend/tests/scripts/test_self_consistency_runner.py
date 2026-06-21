import importlib.util
import json
from pathlib import Path

from app.evaluation.aggregator import AggregatedResult


def _load_runner():
    script = Path(__file__).resolve().parents[2] / "scripts" / "self_consistency.py"
    spec = importlib.util.spec_from_file_location("self_consistency_runner", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


def _final_state(scores, status="completed", core=2.0, coverage=1.0, errors=None):
    agg = AggregatedResult(
        criterion_scores=scores,
        core_score=core,
        coverage=coverage,
        na_criteria=[],
        status=status,
        agent_statuses={"A1": "ok", "A2": "ok", "A3": "ok", "A4": "ok"},
    )
    return {
        "aggregation": agg,
        "status": status,
        "agent_errors": errors or {},
        "final_report": "## report (ignored by metrics)\n",
    }


def test_execute_run_extracts_structured_fields():
    scores = {f"C{i}": 2 for i in range(1, 10)}
    invoker = lambda state: _final_state(scores)
    rec = runner.execute_run(invoker, "S1", {"course_name": "X"}, "X", 3)
    assert rec["seuid"] == "S1"
    assert rec["run_index"] == 3
    assert rec["status"] == "completed"
    assert rec["criterion_scores"]["C9"] == 2
    assert rec["core_score"] == 2.0
    assert "final_report" not in rec  # report text not carried into the record


def test_run_campaign_writes_n_dumps_and_resumes(tmp_path):
    scores = {f"C{i}": 1 for i in range(1, 10)}
    calls = {"n": 0}

    def invoker(state):
        calls["n"] += 1
        return _final_state(scores, core=1.0)

    sample = [("S1", "01_SLUG")]
    rows = {"S1": ({"course_name": "Corso"}, "Corso")}

    records = runner.run_campaign(
        seuids_with_slug=sample, runs=5, output_dir=tmp_path,
        graph_invoker=invoker, syllabus_rows=rows, resume=True,
    )
    assert len(records) == 5
    assert calls["n"] == 5
    dumps = sorted(tmp_path.glob("*__run*__evaluation.json"))
    assert len(dumps) == 5
    payload = json.loads(dumps[0].read_text())
    assert payload["phase"] == "self_consistency"
    assert payload["slug"] == "01_SLUG"

    # Re-run with resume: no new invocations, same count.
    records2 = runner.run_campaign(
        seuids_with_slug=sample, runs=5, output_dir=tmp_path,
        graph_invoker=invoker, syllabus_rows=rows, resume=True,
    )
    assert calls["n"] == 5  # unchanged: all resumed
    assert len(records2) == 5


def test_build_manifest_has_git_and_config():
    manifest = runner.build_manifest([("S1", "01_SLUG")], 5, Path("/tmp/out"))
    assert manifest["experiment"] == "self_consistency_v1"
    assert set(manifest["git"]) == {"commit", "branch", "dirty"}
    assert manifest["scientific_config"]["llm_model"] == "gemini-2.5-flash"
    assert manifest["prompt_versions"]  # non-empty


def test_write_outputs_creates_all_artifacts(tmp_path):
    scores = {f"C{i}": 2 for i in range(1, 10)}
    records = [
        {"seuid": "S1", "run_index": i, "status": "completed",
         "criterion_scores": scores, "core_score": 2.0, "coverage": 1.0,
         "na_criteria": [], "agent_errors": {}, "duration_ms": 1000}
        for i in range(1, 6)
    ]
    sample = [("S1", "01_COMPUTER_VISION_LAB")]
    manifest = runner.build_manifest(sample, 5, tmp_path)
    runner.write_outputs(tmp_path, records, sample, manifest)

    assert (tmp_path / "metrics.json").exists()
    assert (tmp_path / "runs_matrix.json").exists()
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "protocol.md").exists()
    assert (tmp_path / "summary.md").exists()
    assert (tmp_path / "tables" / "tbl_criterion_stability.tex").exists()
    assert (tmp_path / "tables" / "tbl_corescore_stability.tex").exists()
    assert (tmp_path / "tables" / "tbl_run_status.tex").exists()

    matrix = json.loads((tmp_path / "runs_matrix.json").read_text())
    assert matrix["S1"]["C1"] == [2, 2, 2, 2, 2]


def test_resolve_sample_defaults_to_official_eight():
    sample = runner.resolve_sample(None)
    assert len(sample) == 8
    assert sample[7][1] == "08_VULN_ASSESSMENT_PT"


def test_resolve_sample_custom_seuids_keep_known_slugs():
    sample = runner.resolve_sample(["46D62804-0FCD-4478-A51D-A752B64A7DCB", "ZZZ"])
    assert sample[0] == ("46D62804-0FCD-4478-A51D-A752B64A7DCB", "08_VULN_ASSESSMENT_PT")
    assert sample[1] == ("ZZZ", "CUSTOM")
