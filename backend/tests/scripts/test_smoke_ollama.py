import argparse
import json
import os
import subprocess
import sys
from unittest.mock import MagicMock, Mock

import pytest
import requests

from scripts import smoke_ollama as smoke


def server(monkeypatch, *, entry=None, show=None, answer='{"risposta": 4}', reason="stop",
           model=smoke.MODEL):
    bodies = [
        {"version": "0.32.15"},
        {"models": [entry or {"name": model, "size": 3_000_000_000, "digest": "fixture"}]},
        show or {"details": {"family": "qwen35", "quantization_level": "Q4_K_M"}},
        {"message": {"content": answer}, "done": True, "done_reason": reason,
         "load_duration": 2_000_000_000, "eval_count": 8},
        {"models": []},
    ]
    session = MagicMock()
    session.__enter__.return_value = session
    session.request.side_effect = [Mock(status_code=200, json=Mock(return_value=b)) for b in bodies]
    monkeypatch.setattr(smoke.requests, "Session", lambda: session)
    return session


@pytest.mark.parametrize("model", smoke.MODELS)
def test_single_small_generation_without_proxy_then_model_release(monkeypatch, capsys, model):
    session = server(monkeypatch, model=model)
    assert smoke.main(["--execute", "--host", "192.168.1.50", "--model", model]) == 0
    assert session.trust_env is False
    calls = session.request.call_args_list
    assert len(calls) == 5
    assert all(call.kwargs["allow_redirects"] is False for call in calls)
    assert [call.args[1].rsplit("/", 1)[1] for call in calls] == [
        "version", "tags", "show", "chat", "ps",
    ]
    payload = calls[3].kwargs["json"]
    assert payload["model"] == calls[2].kwargs["json"]["model"] == model
    assert payload["keep_alive"] == 0
    assert payload["think"] is False and payload["stream"] is False
    assert payload["options"]["num_ctx"] == 2048
    assert payload["options"]["num_predict"] == 32
    assert payload["options"]["num_thread"] == 2
    output = capsys.readouterr().out
    assert '"passed": true' in output
    assert '"model_still_loaded": false' in output


@pytest.mark.parametrize("answer, reason", [
    ('{"risposta": 5}', "stop"), ('{"risposta": 4}', "length"), ("not JSON", "stop"),
])
def test_wrong_or_truncated_answer_is_failure_without_retry(monkeypatch, capsys, answer, reason):
    session = server(monkeypatch, answer=answer, reason=reason)
    assert smoke.main(["--execute", "--host", "192.168.1.50"]) == 1
    assert session.request.call_count == 5
    assert json.dumps(answer) in capsys.readouterr().out


@pytest.mark.parametrize("entry, show, expected_calls", [
    ({"name": "missing"}, None, 2),
    ({"name": smoke.MODEL, "remote_model": "remote"}, None, 2),
    (None, {"remote_host": "https://ollama.com"}, 3),
    (None, {"details": {"family": "qwen35", "quantization_level": "Q8_0"}}, 3),
])
def test_missing_or_nonlocal_model_is_never_generated(monkeypatch, entry, show, expected_calls):
    session = server(monkeypatch, entry=entry, show=show)
    assert smoke.main(["--execute", "--host", "192.168.1.50"]) == 1
    assert session.request.call_count == expected_calls


@pytest.mark.parametrize("host", ["8.8.8.8", "0.0.0.0", "ollama.com", "http://192.168.1.50"])
def test_public_or_ambiguous_address_is_rejected(host):
    with pytest.raises(argparse.ArgumentTypeError):
        smoke.local_address(host)


@pytest.mark.parametrize("failure", [
    Mock(status_code=302), requests.ConnectionError("offline"),
])
def test_redirect_and_network_failure_do_not_trigger_another_request(monkeypatch, failure):
    session = server(monkeypatch)
    session.request.side_effect = [failure]
    assert smoke.main(["--execute", "--host", "192.168.1.50"]) == 1
    assert session.request.call_count == 1


def test_model_release_check_failure_does_not_hide_successful_generation(monkeypatch, capsys):
    session = server(monkeypatch)
    calls = list(session.request.side_effect)
    calls[-1] = requests.ConnectionError("server unavailable after generation")
    session.request.side_effect = calls
    assert smoke.main(["--execute", "--host", "192.168.1.50"]) == 0
    assert '"model_still_loaded": null' in capsys.readouterr().out


def test_default_preview_never_constructs_network_session(monkeypatch, capsys):
    monkeypatch.setattr(smoke.requests, "Session", Mock(side_effect=AssertionError("network")))
    assert smoke.main(["--host", "192.168.1.50", "--model", "qwen3.5:9b"]) == 0
    output = capsys.readouterr().out
    assert '"mode": "offline_preview"' in output
    assert '"model": "qwen3.5:9b"' in output
    assert '"path": "/api/chat"' in output
    assert "nessun collegamento" in output


def test_request_for_9b_does_not_substitute_available_4b(monkeypatch):
    session = server(monkeypatch, model="qwen3.5:4b")
    assert smoke.main(["--execute", "--host", "192.168.1.50", "--model", "qwen3.5:9b"]) == 1
    assert session.request.call_count == 2


def test_script_does_not_import_application_or_cloud_sdk():
    check = """
import runpy, sys
runpy.run_path('scripts/smoke_ollama.py')
assert not any(name == 'app' or name.startswith('app.') for name in sys.modules)
assert 'google.genai' not in sys.modules
"""
    result = subprocess.run([sys.executable, "-c", check],
                            env={**os.environ, "GENAI_USE_VERTEX": "invalid"},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
