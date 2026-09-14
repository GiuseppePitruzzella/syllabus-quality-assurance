# First local Qwen pilot — 13 September 2026

**Decision: retain the opt-in local adapter and benchmark, but do not enable
Qwen as the application's evaluator yet.** The pilot demonstrates that this
Mac can execute the existing evaluation format without API charges. It does
not establish equivalent quality to Gemini or reliable autonomous scoring.

The improvement delivered here is a reproducible way to measure that question,
with explicit failures, provenance and evidence checks. The production scoring
configuration and previously calibrated results remain unchanged.

## Setup and scope

- MacBook Air M2, 8 GiB unified memory, macOS 26.5.2.
- Ollama 0.32.15, native Metal backend, GGUF `qwen3.5:4b`, Q4_K_M.
- Model download: 3,389,983,735 bytes. Ollama reports parameter size `4.7B`.
- Digest: `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`.
- Context 16,384; output cap 2,048; temperature 0.1; seed 42; thinking disabled;
  JSON schema; no input truncation, context shifting or repair retries.
- One local request at a time, cloud disabled on a separate loopback server.
  The model was already installed. No paid services or fresh Gemini calls ran.

Four agents evaluated the same **Internet of Things** syllabus. A4 also
evaluated **Deep Learning**, selected to exercise a longer input. This is five
calls over two syllabi, not the full 20-case fixture collection. There was one
attempt per case and no repeatability or held-out accuracy study.

Prompts and retrieved passages were replayed from committed fixtures, with
historical versions **a1_v5, a2_v1, a3_v1 and a4_v2**. These are not all current
production prompt versions. Scores were compared with final archived Gemini
outputs, not expert ground truth. The local generation policy also differs
from the original Gemini policy.

## Observed results

| Syllabus / agent | Valid structure | Matching scores | Literal evidence checks | Local wall time | Archived Gemini last-call time |
|---|---|---|---|---:|---:|
| Internet of Things / A1 | Yes | 2/3 | 4/6 | 176.984 s | 16.860 s |
| Internet of Things / A2 | Yes | 1/2 | 6/10 | 233.747 s | 21.032 s |
| Internet of Things / A3 | Yes | 1/3 | 7/10 | 363.246 s | 34.694 s |
| Internet of Things / A4 | Yes | 1/1 | 3/5 | 99.237 s | 12.886 s |
| Deep Learning / A4 | Yes | 1/1 | 2/3 | 74.264 s | 15.360 s |

All five responses passed JSON, domain and criterion-coverage validation.
There were **6/10 matching scores**, numeric mean absolute difference **0.4**,
and no NA disagreements. For IoT, C1, C4, C6 and C7 were all one point lower
than the archived reference. All other compared scores matched.

The literal quote checker verified **22/34 evidence entries (64.7%)**. The
remaining 12 require review; they must not all be labelled hallucinations.
Inspection found re-escaped characters, punctuation changes and reordered
fragments among the causes. No judgment had an empty evidence list.

Qualitative inspection also exposed limitations that JSON validation misses:

- IoT A4 brings missing English fields into its editorial-quality rationale,
  despite recognising that language completeness belongs to C2.
- IoT A2 mentions English completeness while discussing C3, and its C4
  rationale describes distinct Dublin descriptors as overly similar.
- IoT A3's C6 rationale adds expectations about example questions and detailed
  rubrics that need checking against the actual scoring anchor. Its C7
  rationale also invokes hours per topic. These are substantive reasons to
  review criterion boundaries, even when a cited fragment is literal.
- Deep Learning A4 matches the archived C9 score, but one bibliographic quote
  fails literal verification. Score agreement alone would miss this.

Median local wall time was **176.984 seconds**, with a **74.264–363.246 second**
range. The four IoT agent calls totalled about **14.6 minutes**. This does not
include scraping, retrieval, orchestration or database persistence. Archived
Gemini timings cover only the last call, excluding earlier repair attempts
and retrieval. These observations do not establish a full-pipeline speed
comparison; the local calls were slower than those archived last calls.

The Mac was also used for development, and the runs include differing cache
states. The first IoT A4 call includes model loading; later calls reuse the
loaded model. This was not a controlled thermal or throughput benchmark.
MLX was not benchmarked.

## Memory and context handling

After the Deep Learning call, Ollama reported a model allocation of
4,187,435,821 bytes, of which 3,133,690,345 bytes were reported as GPU memory.
These values overlap on unified memory: **do not add them together**. They are
an allocation snapshot, not process RSS or peak total memory.

During that call, system-wide swap readings increased from 6,405.62 MiB to
6,606.94 MiB. Other applications were active, so this cannot all be attributed
to Qwen. It nevertheless prevents a claim that this workload comfortably fits
an 8 GB machine without swapping. Earlier IoT calls did not record before/after
swap snapshots.

A separate negative test deliberately submitted the complete 5,822-token IoT
A4 input with a 2,048-token context. Ollama returned HTTP 400 with
`exceed_context_size_error`, and the runner saved the failure and exited 1.
**No shortened input was scored.** This expected rejection is reported
separately from the five quality attempts because its configuration was
intentionally insufficient.

The temporary model and server were stopped after the tests to release memory.

## Reproducibility and validation

[Machine-readable results](pilot-2026-09-13.json) contain input hashes, model
identity, scores, evidence counts, timing and token metadata, and the negative
test. Full unreviewed response files remain under ignored
`data/local_benchmarks/`; their hashes identify the exact source artifacts.

This was a development pilot. IoT runs preceded addition of source hashes,
memory snapshots and extraction of shared result types into `llm_types.py`.
The generation policy was unchanged. Deep Learning and the context test
record the implementation hashes; their manifests refer to the pre-change
Git commit because the implementation was uncommitted during execution.
The recorded hashes preserve execution-time files; a final trailing-blank-line
cleanup in `llm_types.py` changes its published hash without changing behavior.

After implementation:

- **42 new offline tests passed**, covering local-only transport, no fallback,
  schema/coverage validation, quote checks, failure recording, context/output
  controls and compatibility with the existing A1 agent.
- Full backend suite: **1,115 passed, 3 failed**. The same three corpus-inventory
  tests failed before this change (**1,073 passed, 3 failed**): the local corpus
  inventory counts its README as an eighth document instead of seven. No new
  failures were introduced. These pre-existing failures were not suppressed.
- Ruff on all changed Python files and `git diff --check` passed.
- Inference API charges: **$0**. Runtime and model are free; local electricity
  and hardware resources are still required.

The next useful experiment is to address the observed evidence/criterion
issues under a separately versioned prompt policy, then test current prompts
against held-out human judgments. The existing 20-case replay and repeated
runs are available through the documented runner. They have not all been run,
and the evidence here does not justify switching the web app to local scoring.
