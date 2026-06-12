# Phase 9.F targeted_v1 — phase_9_f_targeted_v1

- Protocol: `phase_9_f_v1`
- E5 fixture (document): `v1` (sha ab953d4)
- Synthetic syllabus fixture: `v1` (sha fe99d60)
- E5 document id: `1` version 1 hash ab953d4 (reused)
- Prompts: E4=`e4_v1`, E5=`e5_v1`
- Synthetic SEUID: `SYNTHETIC-9F-POSITIVE-E5-V1`
- Started: 2026-06-12T10:15:33.250444+00:00
- Finished: 2026-06-12T10:25:12.270233+00:00
- Duration: 579.02s

## Per-syllabus

| Ruolo | SEUID | core | core_score | E4 | E5 |
|---|---|---|---:|---|---|
| real | `3ED4B3BB…` | completed | 1.56 | score (2) | score (1) |
| real | `B99A46CC…` | completed | 1.56 | score (0) | score (1) |
| real | `DADC30FD…` | completed | 1.67 | score (2) | score (1) |
| synth | `SYNTHETI…` | completed | 1.67 | score (2) | score (2) |

## Verdetto automatico

- synthetic E5: **2**
- real E5 (boundary): [1, 1, 1]

> synthetic reached E5=2 and the real boundary cases scored at least 1: e5_v1 is well-calibrated; the Machine Learning baseline outcome looks like a defensible outlier.

## Distributions

- E4 outcomes: {'score': 4}
- E5 outcomes: {'score': 4}
- Technical NA: 0 (handler_errors=0)
- Durations (s): {'n': 4, 'mean': 144.7475, 'median': 147.86, 'min': 123.53, 'max': 159.74}