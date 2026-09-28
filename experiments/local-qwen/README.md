# Local Qwen evaluation experiment (zero inference API cost)

This opt-in experiment tests **Qwen3.5-4B, Q4_K_M** on archived syllabus
evaluation prompts. It does not enable Qwen in the web application or replace
the existing cloud backend. It helps decide whether a local backend
deserves further development.

Read the [first MacBook Air M2 / 8 GB pilot](RESULTS.md) before running a larger
campaign. Completing a JSON response is not evidence of reliable scoring.

For one tiny connectivity/generation check without the syllabus pipeline, use
the [standalone smoke test](SMOKE_TEST.md). It also supports a directly addressed
private IPv4 Ollama server, requests two CPU threads and releases Qwen afterward.

To keep the repository and benchmarks on the Mac while running only Ollama
and Qwen on Windows, follow the [Mac → ThinkPad setup guide](MAC_THINKPAD.md).
It uses an authorized SSH tunnel and requires no project dependencies on Windows.

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
For two-machine runs, use `--inference-location ssh-tunnel`; for inference on
the benchmark host, use `--inference-location same-machine`. This records a
user declaration, not detected hardware, and does not establish a connection.
The default is `unspecified`. The manifest labels measurement scope explicitly:
platform, architecture and swap belong to the benchmark host, while runtime
identity and model allocations come from the Ollama server. Wall time includes
transport. The loopback-only URL restriction still applies.

## Method and limitations

### Restored anchors, source selections and fixed references — September 2026

The application prompt builders now obtain complete, validated score anchors
from `backend/app/evaluation/agents/prompts/core_rubric.py`. The existing anchor
texts were moved unchanged. The corresponding prompt versions are A1 v8,
A2 v2, A3 v2 and A4 v11; persisted version metadata uses the same catalog.
This fixes missing instructions, but does not establish better scoring accuracy.
The candidate rules in [RUBRIC_PROPOSAL_V2.md](RUBRIC_PROPOSAL_V2.md) are not activated.
The [September implementation and trial report](ANCHORS_EVIDENCE_RESULTS.md)
includes the failed first source protocol and the targeted correction.

Three independent experiment options support controlled comparisons:

| Option | Behavior |
|---|---|
| `--prompt-policy current_v1` | Current application builders on the archived syllabus and normative context; no live retrieval |
| `--prompt-policy current_without_anchors_v1` | Diagnostic control: identical to `current_v1` except that the criterion block contains the old description-only input |
| `--evidence-mode source_ids_v2` | Qwen selects numbered passages; original quotes and empty-field claims are checked against each criterion's allowed fields |
| `--evidence-mode source_ids_v1` | Legacy protocol retained to reproduce the trial that failed C1; no criterion-specific field restrictions |
| `--context-mode fixed_core_v1` | Fixed, deduplicated historical references for A2/A4; other agents are rejected before inference |

The defaults remain `archived`, `literal`, and archived context. The two
`current_*` policies use the same required-field decoding schema. Compare
them to isolate delivery of the specification block; comparisons to archived
Gemini also involve different prompt versions and are descriptive only.

Source selection annotates the entire syllabus without dropping text,
preserving nested fields and string offsets. Version 2 keeps text fields as
strings with inline passage markers; version 1 wraps them in passage objects.
Version 2 also restricts evidence and absence fields by criterion, preventing
English omissions from being used as proof of missing Italian sections in C1.
It supports current and separated policies, not historical rubric replay.
It changes presentation as well as the response contract. In particular,
current A4 normally uses readable
field blocks; the source protocol uses annotated JSON. All original values
remain recoverable. Unknown IDs, duplicate selections, unsupported absence
claims and score decisions without any source or verified absence fail
validation. Raw failed answers are retained. An empty field is not a quotation.
Source-ID fidelity is enforced by construction: **100% literal fidelity would
not establish that passages are relevant or that scores are correct.**
Allowed-field checks cannot verify all reasoning within those fields. Version 1
produced a serious C1 error despite perfect quote fidelity; keep it for
reproduction, not as the recommended source protocol.

The fixed reference pack selects exact texts from hashed archived fixtures,
with all criterion-to-passage associations retained. It stores selectors and
hashes without republishing a separate copy of the normative texts. A2's six
entries become four passages (9,732 → 6,150 text characters); A4 retains two.
The pack preserves historical version labels as metadata, including labels
that should not be treated as independently verified source editions. It is
not a UniCT 26.04 compliance profile. A1/A3 still need separate curation.
Neither the fixed pack nor source selection is enabled in the web application.

```sh
# Compare generated quotations with source selection on the same current prompts.
uv run --frozen python scripts/benchmark_local_qwen.py --execute \
  --prompt-policy current_v1 --evidence-mode source_ids_v2 \
  --seuid 0B53E8E2-4B90-426F-A25C-3AA31FA4B649

# Change only the context policy for the supported agents.
uv run --frozen python scripts/benchmark_local_qwen.py --execute \
  --prompt-policy current_v1 --evidence-mode source_ids_v2 \
  --context-mode fixed_core_v1 --agent A2 --agent A4 \
  --seuid 0B53E8E2-4B90-426F-A25C-3AA31FA4B649
```

The manifest records each option, source catalog and context hashes. The
local `*__sources.json` file maps IDs back to original paths and offsets.
Quotes, resolved decisions, raw outputs and failures are saved separately
within each record. No model output is silently rewritten into a passing score.

### Historical replay

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
web-app mode will also require validated local source selection (fixed or
retrieved) and document/OCR handling;
changing the generative model alone is insufficient.

Shared result/error types live in `llm_types.py`; the existing `llm_client.py`
imports remain compatible. The standalone runner imports neither application
settings nor the cloud SDK, so it also works with absent or invalid cloud
configuration.

## Offline regression checks

```sh
cd backend
uv run --frozen pytest -q tests/agents/test_ollama_client.py \
  tests/agents/test_core_rubric_delivery.py \
  tests/evaluation/analysis/test_local_benchmark.py \
  tests/evaluation/analysis/test_local_rubric.py \
  tests/evaluation/analysis/test_local_evidence.py \
  tests/evaluation/analysis/test_local_context.py \
  tests/scripts/test_benchmark_local_qwen.py
```

Tests require neither Ollama, API keys nor private corpus documents.

## Primary references

- [Ollama local-only configuration](https://docs.ollama.com/faq#how-do-i-disable-ollama-cloud-features)
- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
- [Ollama 0.32.15 request types](https://github.com/ollama/ollama/blob/v0.32.15/api/types.go)
- [Qwen3.5-4B model](https://huggingface.co/Qwen/Qwen3.5-4B)
