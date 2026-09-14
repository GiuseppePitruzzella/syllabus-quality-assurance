"""Local-only Qwen transport for opt-in experiments, never a cloud fallback.

No settings/.env, API keys, embeddings, database or production factories are
used here. Ollama must already be running and the model already downloaded.
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
import time
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlsplit

import requests

from app.evaluation.agents.llm_types import (
    LLMEmptyResponseError,
    LLMError,
    LLMResponseTruncatedError,
    LLMResult,
)


class LocalInferenceError(LLMError):
    """Local preflight, transport or context failure; never retry remotely."""


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str = "http://127.0.0.1:11435"
    model: str = "qwen3.5:4b"
    num_ctx: int = 16384
    max_output_tokens: int = 2048
    timeout_seconds: float = 600
    temperature: float = 0.1
    seed: int = 42

    def __post_init__(self) -> None:
        parsed = urlsplit(self.base_url)
        host = parsed.hostname
        if host == "localhost":
            host = "127.0.0.1"
        try:
            local = ipaddress.ip_address(host or "").is_loopback
            port = parsed.port or 11435
        except ValueError as exc:
            raise ValueError("Ollama URL must use a loopback IP or localhost") from exc
        if (not local or parsed.scheme != "http" or parsed.username or parsed.password
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
            raise ValueError("Only a plain HTTP loopback Ollama endpoint is allowed")
        address = f"[{host}]" if ":" in host else host
        object.__setattr__(self, "base_url", f"http://{address}:{port}")
        if self.model not in {"qwen3.5:4b", "qwen3.5:4b-q4_K_M"}:
            raise ValueError("This experiment only permits local Qwen3.5-4B Q4_K_M")
        if not 2048 <= self.num_ctx <= 32768:
            raise ValueError("num_ctx must be between 2048 and 32768")
        if not 1 <= self.max_output_tokens < self.num_ctx:
            raise ValueError("max_output_tokens must be positive and below num_ctx")
        if not 0 < self.timeout_seconds <= 3600:
            raise ValueError("timeout_seconds must be in (0, 3600]")
        if not 0 <= self.temperature <= 2:
            raise ValueError("temperature must be in [0, 2]")


class OllamaLLMClient:
    """Callable compatible with BaseAgent; opt-in and restricted to loopback.

    Truncation and context shifting are disabled: incomplete input must never
    masquerade as a valid benchmark. The local output cap bounds even A1's
    larger Gemini-specific override, and both budgets are recorded.
    """

    def __init__(self, config: OllamaConfig | None = None, *,
                 response_schema: dict[str, Any] | None = None) -> None:
        self.config = config or OllamaConfig()
        self.response_schema = response_schema
        self._session = requests.Session()
        self._session.trust_env = False  # Never forward prompts through env proxies.
        self.identity: dict[str, Any] | None = None
        self.last_response: dict[str, Any] | None = None

    def close(self) -> None:
        self._session.close()

    def memory_snapshot(self) -> dict[str, Any] | None:
        """Ollama allocation at sampling time, NOT total/peak machine RAM."""
        try:
            models = self._request("GET", "/api/ps").get("models", [])
        except LocalInferenceError:
            return None
        entry = next((m for m in models if m.get("name") == self.config.model), None)
        if entry is None:
            return None
        return {key: entry.get(key) for key in ("size", "size_vram", "context_length")}

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._session.request(
                method, self.config.base_url + path, allow_redirects=False,
                timeout=(5, self.config.timeout_seconds), **kwargs,
            )
        except requests.RequestException as exc:
            raise LocalInferenceError(
                f"Local Ollama request failed ({type(exc).__name__}); no cloud fallback."
            ) from exc
        if response.status_code != 200:
            # Ollama returns useful context/OOM diagnostics, not the request prompt.
            raise LocalInferenceError(
                f"Ollama HTTP {response.status_code}: {response.text[:500]}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise LocalInferenceError("Ollama returned a non-JSON response") from exc
        if not isinstance(body, dict) or body.get("error"):
            raise LocalInferenceError(f"Invalid Ollama response: {str(body)[:500]}")
        return body

    def preflight(self) -> dict[str, Any]:
        version = self._request("GET", "/api/version").get("version", "")
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:[-+].*)?", version)
        if not match or tuple(map(int, match.groups())) < (0, 32, 15):
            raise LocalInferenceError("Ollama >= 0.32.15 required for strict context handling")
        models = self._request("GET", "/api/tags").get("models", [])
        entry = next((m for m in models if m.get("name") == self.config.model), None)
        if not entry or entry.get("remote_host") or entry.get("remote_model"):
            raise LocalInferenceError("The selected model must already exist locally")
        show = self._request("POST", "/api/show", json={"model": self.config.model})
        details = show.get("details", {})
        if (show.get("remote_host") or show.get("remote_model")
                or details.get("family") != "qwen35"
                or details.get("quantization_level") != "Q4_K_M"
                or not entry.get("digest") or entry.get("size", 0) <= 0):
            raise LocalInferenceError("Expected local Qwen3.5 Q4_K_M weights; refused model")
        self.identity = {
            "ollama_version": version, "model": self.config.model,
            "model_digest": entry["digest"], "model_size_bytes": entry["size"],
            "details": details, "model_parameters": show.get("parameters", ""),
            "template_sha256": hashlib.sha256(show.get("template", "").encode()).hexdigest(),
            "config": asdict(self.config), "api_cost_usd": 0,
        }
        return self.identity

    def __call__(self, prompt: str, *, seed: int | None = None,
                 max_output_tokens: int | None = None) -> LLMResult:
        self.last_response = None
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        if max_output_tokens is not None and max_output_tokens < 1:
            raise ValueError("max_output_tokens must be positive")
        if self.identity is None:
            self.preflight()
        budget = min(max_output_tokens or self.config.max_output_tokens,
                     self.config.max_output_tokens)
        started = time.monotonic()
        body = self._request("POST", "/api/chat", json={
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False, "think": False, "truncate": False, "shift": False,
            "format": self.response_schema or "json", "keep_alive": "5m",
            "options": {"num_ctx": self.config.num_ctx, "num_predict": budget,
                        "temperature": self.config.temperature,
                        "seed": self.config.seed if seed is None else seed},
        })
        self.last_response = body
        reason = body.get("done_reason")
        if reason == "length":
            raise LLMResponseTruncatedError("Local response reached the output/context limit")
        if body.get("done") is not True or reason != "stop":
            raise LocalInferenceError(f"Incomplete local response: {reason!r}")
        message = body.get("message") or {}
        text = message.get("content")
        if not isinstance(text, str) or not text.strip():
            raise LLMEmptyResponseError("Ollama returned no answer text")
        metadata = {
            "backend": "ollama_local", "model": self.config.model,
            "model_digest": self.identity["model_digest"],
            "finish_reason": "STOP", "num_ctx": self.config.num_ctx,
            "max_output_tokens": budget, "requested_max_output_tokens": max_output_tokens,
            "temperature": self.config.temperature,
            "seed": self.config.seed if seed is None else seed, "thinking": False,
            "prompt_chars": len(prompt), "response_chars": len(text),
            "latency_ms": round((time.monotonic() - started) * 1000),
            "api_cost_usd": 0,
        }
        for key in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration",
                    "prompt_eval_count", "prompt_eval_cached_count", "eval_count"):
            metadata[key] = body.get(key)
        return LLMResult(text=text, metadata=metadata)
