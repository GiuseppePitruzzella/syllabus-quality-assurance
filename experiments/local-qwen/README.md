# Local Qwen evaluation experiment (zero inference API cost)

This opt-in experiment tests **Qwen3.5-4B, Q4_K_M** on archived syllabus
evaluation prompts. It does not enable Qwen in the web application or replace
the validated Gemini configuration. It helps decide whether a local backend
deserves further development.

Read the [first MacBook Air M2 / 8 GB pilot](RESULTS.md) before running a larger
campaign. Completing a JSON response is not evidence of reliable scoring.

The [documentary review and separated rubric](RUBRIC_REVIEW.md) introduces the
opt-in `separated_v1` policy. It changes some scoring rules as well as wording;
it is neither a validated replacement nor a complete 2026 compliance check.

## Cost boundary

- No Gemini, Vertex AI, remote embeddings, OCR or production database calls.
- Only a loopback HTTP address and the local 4B model are accepted;
  remote model aliases, redirects and environment proxies are refused.
- No automatic downloads or fallback. Start Ollama with cloud disabled.
- After installing the free runtime and downloading the weights, inference
  needs no Internet connection. API charges are **$0**; electricity, disk space
  and local computing resources are still consumed.
- The existing web app and historical calibration scripts still use their
  existing Google backends. **They are not the local experiment entry point.**

## Setup on macOS

Install [Ollama](https://ollama.com/download/mac) and obtain the model once:

```sh
ollama pull qwen3.5:4b
```

This is a free download of approximately 3.4 GB. The runner requires **Ollama
0.32.15 or newer**, including strict input truncation/context-shift controls.
It records the actual model digest, quantization, template hash and version.

Run this isolated server in a separate terminal. If the normal Ollama app has
another model loaded, unload it or quit that app first to reclaim RAM.
No permanent machine settings need to change:

```sh
OLLAMA_HOST=127.0.0.1:11435 \
OLLAMA_NO_CLOUD=1 \
OLLAMA_NUM_PARALLEL=1 \
OLLAMA_MAX_LOADED_MODELS=1 \
ollama serve
```

Run Ollama natively on macOS: Docker Desktop does not expose the Mac GPU to
its Linux containers. On an 8 GB Mac use one request at a time. A 16,384-token
context is an experimental starting point, not guaranteed fit or speed.
Smaller contexts can reject longer prompts; input is never silently shortened
to improve benchmark results.

## Run

From the repository's `backend` directory:

```sh
# List all 20 archived cases; no Ollama connection or generation.
uv run --frozen python scripts/benchmark_local_qwen.py

# Small first test: A4 on Internet of Things.
uv run --frozen python scripts/benchmark_local_qwen.py --execute \
  --agent A4 --seuid 0B53E8E2-4B90-426F-A25C-3AA31FA4B649

# All four agents on the same syllabus.
uv run --frozen python scripts/benchmark_local_qwen.py --execute \
  --seuid 0B53E8E2-4B90-426F-A25C-3AA31FA4B649

# Revised criterion boundaries and complete score anchors, local only.
uv run --frozen python scripts/benchmark_local_qwen.py --execute \
  --prompt-policy separated_v1 \
  --seuid 0B53E8E2-4B90-426F-A25C-3AA31FA4B649

# Full initial sample: 5 syllabi x 4 agents. Allow substantial time on an Air.
uv run --frozen python scripts/benchmark_local_qwen.py --execute
```

`--runs 3` repeats each case with the same seed. Select agents with repeated
`--agent`, syllabi with repeated `--seuid`. `--limit` selects the first N cases
in filename order, **not a representative sample**. Memory/output controls:
`--num-ctx 16384 --max-output-tokens 2048 --timeout 600`.

Results go into a new, ignored `data/local_benchmarks/<timestamp>/` directory.
`--output-dir` can select another **nonexistent** directory. Existing results
are never overwritten. Each completed attempt is saved immediately. Failed
attempts remain in the denominator; any transport, context, JSON or domain
failure makes the command exit with a nonzero status.

Records include raw responses, score differences, evidence checks, token
counts, prompt/generation/load durations and best-effort memory snapshots.
The `/api/ps` allocation and before/after macOS swap readings are **not peak RAM
measurements**. Raw experiment artifacts stay local until reviewed.

## Method and limitations

Committed `backend/tests/fixtures/llm_responses/` files contain complete
historical prompts, including syllabus and selected normative passages.
By default (`--prompt-policy archived`), each first prompt is replayed verbatim.
`--prompt-policy separated_v1` replaces the instructions using a versioned
catalog, preserving the syllabus and retrieved JSON blocks byte for byte.
Final archived Gemini judgments supply comparison scores. No retriever or
embedding model runs. Under the revised rubric, agreement with the old scores
is descriptive only: both the rubric and the prompt have changed.

The manifest records original and effective prompt hashes, catalog and source
code hashes, plus hashes of the preserved data blocks for revised prompts.
Each effective prompt is saved alongside raw results for local review.
The experimental policy also requires every response field in the decoding
schema, including an explicit score-or-NA decision. The archived policy keeps
its original decoding schema. This is another controlled configuration
difference, not evidence of an isolated wording effect.

- Historical prompt versions may differ from current prompts. Versions and
  input hashes are saved in the manifest.
- Local generation uses a JSON schema, temperature 0.1, seed 42, thinking off
  and a 2,048-token output cap. Gemini used different generation controls.
- One local attempt per case/run, without hidden repair retries.
- Local wall time includes loading and communication; archived last-call
  Gemini time, when available, excludes earlier repair calls and RAG.
  Their ratio is not a full-pipeline speedup.
- Gemini agreement is **not accuracy against human experts**.
- Quote checks use the named syllabus field, normalising Unicode and
  whitespace only. Re-escaped newlines, paraphrases and changed punctuation
  are flagged for review. Empty evidence lists are counted separately and
  never interpreted as 100% verified evidence.
- Valid JSON does not establish correct reasoning, Italian quality, criterion
  boundaries or supported judgments. Human reading remains necessary.

## Acceptance and next step

There is no automatic "Qwen equals Gemini" gate. Review failures, quotes and
criterion contamination first, then expand to all 20 cases and repeated runs.
A later campaign should use held-out human judgments and current prompts,
versioned separately from historical replay. Only after that evidence supports
it should the web application offer local scoring.

The transport implements the existing `LLMClient` callable interface for future
`BaseAgent` integration without an Ollama SDK dependency. A complete offline
web-app mode will also require validated local retrieval/embeddings and OCR;
changing the generative model alone is insufficient.

Shared result/error types live in `llm_types.py`; the existing `llm_client.py`
imports remain compatible. The standalone runner imports neither application
settings nor the cloud SDK, so it also works with absent or invalid cloud
configuration.

## Offline regression checks

```sh
cd backend
uv run --frozen pytest -q tests/agents/test_ollama_client.py \
  tests/evaluation/analysis/test_local_benchmark.py \
  tests/evaluation/analysis/test_local_rubric.py \
  tests/scripts/test_benchmark_local_qwen.py
```

Tests require neither Ollama, API keys nor private corpus documents.

## Primary references

- [Ollama local-only configuration](https://docs.ollama.com/faq#how-do-i-disable-ollama-cloud-features)
- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
- [Ollama 0.32.15 request types](https://github.com/ollama/ollama/blob/v0.32.15/api/types.go)
- [Qwen3.5-4B model](https://huggingface.co/Qwen/Qwen3.5-4B)
