import importlib.util
from pathlib import Path

from app.evaluation.analysis.human_sample import OFFICIAL_HUMAN_SAMPLE


def _load_shortlist():
    script = Path(__file__).resolve().parents[3] / "scripts" / "setup_human_judgment.py"
    spec = importlib.util.spec_from_file_location("setup_human_judgment", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SHORTLIST


def test_official_sample_has_eight_entries():
    assert len(OFFICIAL_HUMAN_SAMPLE) == 8
    assert all(len(item) == 2 for item in OFFICIAL_HUMAN_SAMPLE)


def test_official_sample_matches_human_shortlist():
    # Single source of truth: the experiment default must equal the
    # human-validation shortlist. If setup_human_judgment changes, this
    # fails loudly instead of silently diverging.
    assert list(OFFICIAL_HUMAN_SAMPLE) == list(_load_shortlist())
