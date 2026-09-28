"""One tiny Qwen request to a local computer; no syllabus pipeline or cloud SDK.

Run from the Mac with its existing Python environment. The target must already
run Ollama and have the selected Qwen3.5 Q4_K_M model downloaded. Defaults to an
offline preview; --execute explicitly enables requests. Nothing is installed remotely.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import time

import requests

MODEL = "qwen3.5:4b"
MODELS = (MODEL, "qwen3.5:9b")
LOCAL_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    "127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16",
))


def local_address(value: str) -> str:
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as exc:
        raise argparse.ArgumentTypeError("Indicare un indirizzo IPv4, non un URL o hostname") from exc
    if not any(address in network for network in LOCAL_NETWORKS):
        raise argparse.ArgumentTypeError("Sono ammessi solo indirizzi locali, privati o link-local")
    return str(address)


def request_json(session, base_url, path, *, timeout, payload=None):
    response = session.request(
        "GET" if payload is None else "POST", base_url + path,
        json=payload, timeout=(5, timeout), allow_redirects=False,
    )
    if response.status_code != 200:
        raise ValueError(f"{path}: HTTP {response.status_code}; nessun tentativo alternativo")
    body = response.json()
    if not isinstance(body, dict) or body.get("error"):
        raise ValueError(f"{path}: risposta Ollama non valida")
    return body


def chat_payload(model: str) -> dict:
    return {
        "model": model,
        "messages": [{"role": "user", "content":
                      "Quanto fa 2 + 2? Rispondi in JSON con il solo campo intero risposta."}],
        "format": {"type": "object", "properties": {"risposta": {"type": "integer"}},
                   "required": ["risposta"], "additionalProperties": False},
        "stream": False, "think": False, "keep_alive": 0,
        "options": {"num_ctx": 2048, "num_predict": 32, "num_thread": 2,
                    "temperature": 0, "seed": 42},
    }


def run_probe(session, base_url: str, timeout: float, model: str = MODEL) -> dict:
    def api(path, payload=None):
        return request_json(session, base_url, path, timeout=timeout, payload=payload)

    version = api("/api/version").get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("Il server non restituisce una versione Ollama valida")
    models = api("/api/tags").get("models", [])
    if not isinstance(models, list) or any(not isinstance(model, dict) for model in models):
        raise ValueError("Elenco modelli Ollama non valido")
    entry = next((entry for entry in models if entry.get("name") == model), None)
    if not entry or entry.get("remote_host") or entry.get("remote_model"):
        raise ValueError(f"{model} deve essere gia scaricato localmente sul computer indicato")
    show = api("/api/show", {"model": model})
    details = show.get("details", {})
    if (not isinstance(details, dict) or show.get("remote_host") or show.get("remote_model")
            or details.get("family") != "qwen35"
            or details.get("quantization_level") != "Q4_K_M"
            or not entry.get("digest") or entry.get("size", 0) <= 0):
        raise ValueError(f"Sono richiesti pesi locali {model} Q4_K_M; nessun fallback cloud")
    print(f"Ollama {version} raggiungibile; modello locale verificato. Invio una domanda.",
          flush=True)
    started = time.monotonic()
    result = api("/api/chat", chat_payload(model))
    elapsed = round(time.monotonic() - started, 3)
    message = result.get("message")
    raw = message.get("content", "") if isinstance(message, dict) else ""
    load_duration = result.get("load_duration")
    report = {
        "ollama_version": version, "model": model, "model_digest": entry["digest"],
        "raw_response": raw, "wall_seconds": elapsed,
        "load_seconds": load_duration / 1_000_000_000
        if isinstance(load_duration, (int, float)) else None,
        "generated_tokens": result.get("eval_count"),
        "finish_reason": result.get("done_reason"),
        "unload_requested": True, "api_cost_usd": 0,
    }
    try:
        answer = json.loads(raw)
    except (ValueError, TypeError):
        answer = None
    report["passed"] = (result.get("done") is True and result.get("done_reason") == "stop"
                        and answer == {"risposta": 4})
    try:
        running = api("/api/ps")["models"]
        if not isinstance(running, list) or any(not isinstance(model, dict) for model in running):
            raise ValueError("Elenco modelli caricati non valido")
        report["model_still_loaded"] = any(entry.get("name") == model for entry in running)
    except (requests.RequestException, ValueError, KeyError, TypeError):
        report["model_still_loaded"] = None
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, type=local_address,
                        help="IPv4 del ThinkPad; 127.0.0.1 testa invece il computer corrente")
    parser.add_argument("--model", choices=MODELS, default=MODEL)
    parser.add_argument("--execute", action="store_true",
                        help="Esegue le richieste; senza questo flag mostra solo un piano offline")
    parser.add_argument("--port", type=int, default=11434)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535 or not 1 <= args.timeout <= 600:
        parser.error("Porta: 1..65535; timeout: 1..600 secondi")
    base_url = f"http://{args.host}:{args.port}"
    if not args.execute:
        print(json.dumps({
            "mode": "offline_preview", "target": base_url, "model": args.model,
            "requests_if_executed": [
                {"method": "GET", "path": "/api/version"},
                {"method": "GET", "path": "/api/tags"},
                {"method": "POST", "path": "/api/show", "body": {"model": args.model}},
                {"method": "POST", "path": "/api/chat", "body": chat_payload(args.model)},
                {"method": "GET", "path": "/api/ps"},
            ],
        }, ensure_ascii=False, indent=2))
        print("Anteprima soltanto: nessun collegamento, lettura remota o caricamento del modello. "
              "Aggiungere --execute solo dopo aver approvato tutte le operazioni mostrate.")
        return 0
    with requests.Session() as session:
        session.trust_env = False
        try:
            report = run_probe(session, base_url, args.timeout, args.model)
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            print(json.dumps({"passed": False, "error": str(exc), "api_cost_usd": 0},
                             ensure_ascii=False, indent=2))
            print("Nessun retry o fallback. Se la richiesta e stata interrotta, controllare "
                  f"ollama ps sul ThinkPad; ollama stop {args.model} libera il modello.")
            return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
