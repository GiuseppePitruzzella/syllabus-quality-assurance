# backend/tests/test_config_backend_selection.py
from __future__ import annotations

import pytest

from app.config import Settings


def test_defaults_prefer_vertex():
    s = Settings(_env_file=None)
    assert s.genai_use_vertex is True
    assert s.gemini_api_key == ""
    assert s.gemini_api_rpm_limit == 5


def test_require_gemini_api_key_raises_when_empty():
    s = Settings(_env_file=None, genai_use_vertex=False, gemini_api_key="")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        s.require_gemini_api_key()


def test_require_gemini_api_key_returns_value():
    s = Settings(_env_file=None, gemini_api_key="abc123")
    assert s.require_gemini_api_key() == "abc123"
