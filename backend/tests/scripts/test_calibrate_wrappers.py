"""Signature tests for the per-agent calibration script wrappers.

Every ``calibrate_a{1..4}.py`` ships its own ``CapturingLLMClient`` that
wraps the production ``VertexAILLMClient`` to record prompts and
results. The wrapper signature must stay in sync with the inner
client: when Phase 5.4.J added the per-agent ``max_output_tokens``
override (D030.bis), forgetting to update one of these wrappers would
break the corresponding calibration with a ``TypeError`` only at
runtime (after we'd already burned Vertex tokens).

These tests are signature-only: they don't run the calibration. They
just import the wrapper class, inspect its ``__call__`` signature,
and assert the contract the calibration script needs.
"""
from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


@pytest.fixture(autouse=True)
def _add_scripts_to_syspath():
    """Make ``calibrate_a*.py`` importable as top-level modules."""
    path_str = str(_SCRIPTS_DIR)
    inserted = False
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = True
    yield
    if inserted:
        sys.path.remove(path_str)


@pytest.mark.parametrize("module_name", ["calibrate_a1", "calibrate_a2", "calibrate_a3", "calibrate_a4"])
def test_capturing_llm_client_accepts_max_output_tokens_kwarg(module_name):
    """Every calibration wrapper must accept the same kwargs as VertexAILLMClient.

    ``BaseAgent._invoke_llm`` passes ``max_output_tokens`` when the
    subclass declares ``max_output_tokens_override`` (e.g. ``CompletenessAgent``
    sets it to 16384 since a1_v5). If the wrapper signature drops the
    kwarg, the call site explodes with TypeError and the calibration
    fails after the first agent call.
    """
    module = importlib.import_module(module_name)
    cls = module.CapturingLLMClient
    sig = inspect.signature(cls.__call__)
    params = sig.parameters
    assert "max_output_tokens" in params, (
        f"{module_name}.CapturingLLMClient.__call__ does not accept "
        "'max_output_tokens'; this would break BaseAgent._invoke_llm "
        "for any agent that sets max_output_tokens_override."
    )
    # Also: it must be a keyword-only param with a default of None so callers
    # that don't pass it keep working (A2/A3/A4 today).
    p = params["max_output_tokens"]
    assert p.kind == inspect.Parameter.KEYWORD_ONLY
    assert p.default is None
