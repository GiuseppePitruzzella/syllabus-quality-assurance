import json
from unittest.mock import Mock

import pytest

from scripts import benchmark_local_qwen as runner
from app.evaluation.agents.llm_client import LLMResult


def test_default_dry_run_never_constructs_client(monkeypatch, capsys):
    monkeypatch.setattr(runner, "OllamaLLMClient", Mock(side_effect=AssertionError("network")))
    assert runner.main(["--agent", "A4", "--limit", "1"]) == 0
    assert "Dry run only" in capsys.readouterr().out


def test_replay_imports_neither_cloud_sdk_nor_application_settings():
    import os
    import subprocess
    import sys
    # Invalid cloud configuration would fail if the local runner loaded .env/settings.
    environment = {**os.environ, "GENAI_USE_VERTEX": "deliberately-invalid-boolean"}
    check = """
import runpy, sys
sys.argv = ['benchmark_local_qwen.py', '--limit', '1']
namespace = runpy.run_path('scripts/benchmark_local_qwen.py')
assert namespace['main'](['--limit', '1']) == 0
assert namespace['main'](['--prompt-policy', 'separated_v1', '--limit', '1']) == 0
assert namespace['main'](['--prompt-policy', 'current_v1', '--evidence-mode',
                         'source_ids_v1', '--limit', '1']) == 0
assert namespace['main'](['--prompt-policy', 'current_v1', '--evidence-mode',
                         'source_ids_v2', '--limit', '1']) == 0
assert namespace['main'](['--prompt-policy', 'current_v1', '--agent', 'A2',
                         '--context-mode', 'fixed_core_v1', '--limit', '1']) == 0
assert 'app.config' not in sys.modules
assert 'google.genai' not in sys.modules
"""
    result = subprocess.run([sys.executable, "-c", check], cwd=runner.BACKEND,
                            env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_record_survives_failure_and_summary_counts_it(monkeypatch, tmp_path):
    client = Mock(side_effect=RuntimeError("local out of memory"))
    client.preflight.return_value = {"model_digest": "fixture"}
    client.last_response = None
    client.memory_snapshot.return_value = None
    monkeypatch.setattr(runner, "OllamaLLMClient", lambda _: client)
    output = tmp_path / "run"
    assert runner.main(["--execute", "--agent", "A4", "--limit", "1",
                        "--output-dir", str(output)]) == 1
    summary = json.loads((output / "summary.json").read_text())
    assert summary["attempted"] == 1 and summary["valid"] == 0
    assert summary["agreement_with_archived_gemini"] is None
    client.close.assert_called_once()


def test_experimental_policy_is_sent_and_saved_with_distinct_provenance(monkeypatch, tmp_path):
    client = Mock(return_value=LLMResult("invalid JSON", {"backend": "ollama_local"}))
    client.preflight.return_value = {}
    client.last_response = None
    client.memory_snapshot.return_value = None
    monkeypatch.setattr(runner, "OllamaLLMClient", lambda _: client)
    output = tmp_path / "revised"
    assert runner.main(["--execute", "--agent", "A4", "--limit", "1",
                        "--prompt-policy", "separated_v1", "--output-dir", str(output)]) == 1
    manifest = json.loads((output / "manifest.json").read_text())
    provenance = manifest["cases"][0]["prompt_provenance"]
    assert provenance["archived_prompt_sha256"] != provenance["effective_prompt_sha256"]
    assert provenance["rubric_changed"] is True
    assert manifest["require_all_response_fields"] is True
    assert "score" in client.response_schema["$defs"]["CriterionJudgment"]["required"]
    prompt = next(output.glob("*__prompt.txt")).read_text()
    client.assert_called_once_with(prompt)
    summary = json.loads((output / "summary.json").read_text())
    assert summary["prompt_policy"] == "separated_v1"
    assert "Different experimental rubric" in summary["interpretation"]


def test_past_experiment_is_never_overwritten(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "OllamaLLMClient", Mock(side_effect=AssertionError("network")))
    with pytest.raises(FileExistsError):
        runner.main(["--execute", "--limit", "1", "--output-dir", str(tmp_path)])


def test_raw_answer_preserved_on_validation_failure(monkeypatch, tmp_path):
    client = Mock(return_value=LLMResult("invalid JSON", {"backend": "ollama_local"}))
    client.preflight.return_value = {}
    client.last_response = None
    client.memory_snapshot.return_value = None
    monkeypatch.setattr(runner, "OllamaLLMClient", lambda _: client)
    output = tmp_path / "run"
    runner.main(["--execute", "--limit", "1", "--output-dir", str(output)])
    files = [p for p in output.glob("*__run1.json")]
    assert json.loads(files[0].read_text())["raw_response"] == "invalid JSON"


def test_preflight_failure_has_a_saved_diagnostic(monkeypatch, tmp_path):
    from app.evaluation.agents.ollama_client import LocalInferenceError
    client = Mock()
    client.preflight.side_effect = LocalInferenceError("model missing")
    monkeypatch.setattr(runner, "OllamaLLMClient", lambda _: client)
    output = tmp_path / "run"
    assert runner.main(["--execute", "--limit", "1", "--output-dir", str(output)]) == 2
    assert json.loads((output / "preflight_error.json").read_text())["api_cost_usd"] == 0
    client.assert_not_called()
    client.close.assert_called_once()


@pytest.mark.parametrize("valid", [True, False])
@pytest.mark.parametrize("mode", ["source_ids_v1", "source_ids_v2"])
def test_source_protocol_records_selection_or_rejection_without_hiding_raw_answer(
    monkeypatch, tmp_path, valid, mode,
):
    payload = {"judgments": [{"criterion_code": "C9", "score": 2, "is_na": False,
                             "na_reason": None, "confidence": "medium",
                             "justification": "Motivazione di prova del contratto delle evidenze.",
                             "evidence_ids": ["S0001" if valid else "S9999"],
                             "absent_fields": []}]}
    client = Mock(return_value=LLMResult(json.dumps(payload), {}))
    client.preflight.return_value = {}
    client.last_response = None
    client.memory_snapshot.return_value = None
    monkeypatch.setattr(runner, "OllamaLLMClient", lambda _: client)
    output = tmp_path / "sources"
    code = runner.main(["--execute", "--agent", "A4", "--limit", "1",
                        "--prompt-policy", "current_v1", "--evidence-mode", mode,
                        "--context-mode", "fixed_core_v1", "--output-dir", str(output)])
    assert code == (0 if valid else 1)
    record = json.loads(next(output.glob("*__run1.json")).read_text())
    assert json.loads(record["raw_response"]) == payload
    summary = json.loads((output / "summary.json").read_text())
    assert summary["attempted"] == 1 and summary["valid"] == int(valid)
    assert "by construction" in summary["interpretation"]
    assert summary["context_mode"] == "fixed_core_v1"
    assert next(output.glob("*__sources.json")).is_file()
    assert "evidence_ids" in client.response_schema["$defs"]["SourceJudgment"]["required"]
    if valid:
        assert record["assessment"]["source_selections"][0]["evidence_ids"] == ["S0001"]
    else:
        assert "Unknown source" in record["error"]
