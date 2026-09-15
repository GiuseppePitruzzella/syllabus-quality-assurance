"""Replay archived core-agent prompts through local Qwen, with zero cloud calls.

Defaults to a dry run. --execute explicitly enables local inference. No DB,
RAG or production backend is constructed. See experiments/local-qwen/README.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.evaluation.agents.ollama_client import (  # noqa: E402
    LocalInferenceError, OllamaConfig, OllamaLLMClient,
)
from app.evaluation.analysis.local_benchmark import (  # noqa: E402
    assess_response, load_case, response_schema, summarise,
)
from app.evaluation.analysis.local_rubric import (  # noqa: E402
    POLICY, RUBRIC_PATH, prepare_prompt,
)


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_summary(output: Path, records: list[dict], policy: str = "archived") -> None:
    summary = summarise(records)
    summary["prompt_policy"] = policy
    summary["rubric_changed"] = policy != "archived"
    if policy != "archived":
        summary["interpretation"] = (
            "Different experimental rubric; archived Gemini agreement is descriptive only. "
            "Not a test of accuracy, normative compliance or isolated wording improvements."
        )
    write_json(output / "summary.json", summary)
    lines = ["# Local Qwen diagnostic replay", "",
             "Archived Gemini agreement is not accuracy against human experts.", "",
             f"- Prompt policy: {policy}; rubric changed: {summary['rubric_changed']}",
             summary["interpretation"], "",
             f"- Attempted: {summary['attempted']}; valid: {summary['valid']}",
             f"- Score agreement: {summary['agreement_with_archived_gemini']}",
             f"- Numeric MAE: {summary['numeric_mae']}",
             f"- Verified evidence: {summary['verified_evidences']}/{summary['evidences']}",
             f"- Judgments without evidence: {summary['judgments_without_evidence']}",
             f"- Median wall time: {summary['median_wall_seconds']} seconds",
             "- Inference API cost: $0 (local only)", "",
             "| Case | Status | Seconds | Error |", "|---|---|---:|---|"]
    for record in records:
        error = str(record.get("error", "")).replace("|", "/").replace("\n", " ")
        lines.append(f"| {record['case_id']} | {record['status']} | "
                     f"{record['wall_seconds']:.1f} | {error} |")
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def swap_snapshot() -> str | None:
    """Best-effort macOS swap snapshot; no hardware identifiers or credentials."""
    if sys.platform != "darwin":
        return None
    try:
        result = subprocess.run(["/usr/sbin/sysctl", "-n", "vm.swapusage"],
                                capture_output=True, text=True, check=False, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Run local inference; default: plan")
    parser.add_argument("--fixtures-dir", type=Path,
                        default=BACKEND / "tests/fixtures/llm_responses")
    parser.add_argument("--agent", choices=["A1", "A2", "A3", "A4"], action="append")
    parser.add_argument("--seuid", action="append")
    parser.add_argument("--limit", type=int, default=0, help="0 means all selected cases")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--prompt-policy", choices=["archived", POLICY], default="archived",
                        help="Historical replay or separately versioned experimental rubric")
    parser.add_argument("--base-url", default="http://127.0.0.1:11435")
    parser.add_argument("--num-ctx", type=int, default=16384)
    parser.add_argument("--max-output-tokens", type=int, default=2048)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if args.limit < 0 or args.runs < 1:
        parser.error("limit must be nonnegative and runs must be positive")
    try:
        config = OllamaConfig(base_url=args.base_url, num_ctx=args.num_ctx,
                              max_output_tokens=args.max_output_tokens,
                              timeout_seconds=args.timeout, seed=args.seed)
    except ValueError as exc:
        parser.error(str(exc))
    cases = [load_case(p) for p in sorted(args.fixtures_dir.glob("a[1-4]_calibration_*.json"))]
    cases = [c for c in cases if (not args.agent or c.agent_code in args.agent)
             and (not args.seuid or c.seuid in args.seuid)]
    if args.limit:
        cases = cases[:args.limit]
    if not cases:
        parser.error("No matching replay cases")
    try:
        prompts = {c.case_id: prepare_prompt(c, args.prompt_policy) for c in cases}
    except ValueError as exc:
        parser.error(str(exc))
    for case in cases:
        print(f"{case.case_id}: {len(prompts[case.case_id].text)} chars; "
              f"archived {case.prompt_version}; policy {args.prompt_policy}")
    if args.prompt_policy != "archived":
        print("Experimental rubric differs from Gemini's archived rubric; agreement is descriptive.")
    print(f"{len(cases) * args.runs} local calls planned. Inference API cost: $0.", flush=True)
    if not args.execute:
        print("Dry run only. Add --execute to contact local Ollama.")
        return 0
    output = args.output_dir or BACKEND.parent / "data/local_benchmarks" / datetime.now(
        timezone.utc
    ).strftime("qwen_%Y%m%dT%H%M%S_%fZ")
    # Never overwrite past experiments, including interrupted ones.
    output.mkdir(parents=True, exist_ok=False)
    client = OllamaLLMClient(config)
    records: list[dict] = []
    try:
        try:
            identity = client.preflight()
        except LocalInferenceError as exc:
            write_json(output / "preflight_error.json", {"error": str(exc), "api_cost_usd": 0})
            print(f"Local preflight failed: {exc}", file=sys.stderr)
            return 2
        git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=BACKEND,
                             capture_output=True, text=True, check=False)
        manifest = {
            "experiment": "local_qwen_replay_v1", "created_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": git.stdout.strip(), "platform": platform.platform(),
            "machine": platform.machine(), "config": asdict(config), "runtime": identity,
            "runs_per_case": args.runs, "retrieval": "frozen in archived prompt; no embeddings",
            "prompt_policy": args.prompt_policy,
            "require_all_response_fields": args.prompt_policy != "archived",
            "method": "versioned prompt policy; structured output; thinking disabled; no retries",
            "implementation_sha256": {
                str(p.relative_to(BACKEND)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in [Path(__file__).resolve(),
                          BACKEND / "app/evaluation/agents/ollama_client.py",
                          BACKEND / "app/evaluation/agents/llm_types.py",
                          BACKEND / "app/evaluation/analysis/local_benchmark.py",
                          BACKEND / "app/evaluation/analysis/local_rubric.py", RUBRIC_PATH]
            },
            "cases": [{"case_id": c.case_id, "fixture": c.fixture_name,
                       "fixture_sha256": c.fixture_sha256, "prompt_version": c.prompt_version,
                       "prompt_sha256": hashlib.sha256(c.prompt.encode()).hexdigest(),
                       "prompt_chars": len(c.prompt), "reference_scores": c.reference_scores,
                       "effective_prompt_chars": len(prompts[c.case_id].text),
                       "prompt_provenance": prompts[c.case_id].provenance,
                       "reference_last_call_latency_ms": c.reference_latency_ms} for c in cases],
        }
        write_json(output / "manifest.json", manifest)
        for case in cases:
            prepared = prompts[case.case_id]
            (output / f"{case.case_id}__prompt.txt").write_text(prepared.text, encoding="utf-8")
            client.response_schema = response_schema(
                case.criteria, require_all_fields=args.prompt_policy != "archived"
            )
            for run in range(1, args.runs + 1):
                started = time.monotonic()
                record = {"case_id": case.case_id, "run": run, "status": "error",
                          "prompt_provenance": prepared.provenance}
                record["swap_before"] = swap_snapshot()
                print(f"Running {case.case_id} #{run} ...", flush=True)
                try:
                    result = client(prepared.text)
                    record["raw_response"] = result.text
                    record["metadata"] = result.metadata
                    record["assessment"] = assess_response(case, result.text)
                    record["status"] = "valid"
                except Exception as exc:
                    record["error"] = f"{type(exc).__name__}: {exc}"
                    record["ollama_response"] = client.last_response
                record["wall_seconds"] = round(time.monotonic() - started, 3)
                record["swap_after"] = swap_snapshot()
                record["model_memory_after"] = client.memory_snapshot()
                write_json(output / f"{case.case_id}__run{run}.json", record)
                records.append(record)
                write_summary(output, records, args.prompt_policy)
                print(f"  {record['status']} in {record['wall_seconds']}s", flush=True)
        print(f"Results: {output}")
        return 0 if all(r["status"] == "valid" for r in records) else 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
