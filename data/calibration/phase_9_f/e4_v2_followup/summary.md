# Phase 9.F follow-up — phase_9_f_e4_v2_followup

- Protocol: `phase_9_f_v1`
- E4 prompt version: `e4_v2`
- E5 prompt version: `e5_v1`
- E5 fixture: `v1` (sha ab953d4)
- E5 document id: `1` v1 (hash ab953d4, reused)
- Started: 2026-06-12T13:45:44.430453+00:00
- Finished: 2026-06-12T13:57:02.982184+00:00
- Duration: 678.55s

## Overall verdict: GREEN — every expectation met

| Role | SEUID | Course | Expected E4 | Observed E4 | Verdict |
|---|---|---|---|---|---|
| real | `3ED4B3BB…` | Advanced Computer Graphics | `score:1` | `score:1` | **OK** |
| real | `3540D939…` | Deep Learning | `score:2` | `score:2` | **OK** |
| real | `0B53E8E2…` | Internet of Things | `NA-handler_na` | `NA-handler_na` | **OK** |
| real | `FE97232C…` | Machine Learning | `score:0` | `score:0` | **OK** |
| synth | `SYNTHETI…` | Sistemi distribuiti avanzati (ctrl) | `score:2` | `score:2` | **OK** |

## Per-run notes

- `3ED4B3BB-D25C-4EA3-BC50-14A310BEF4FF` — Advanced Computer Graphics
  - course_content_en is empty; e4_v2 must surface the omission via it_only_substantial and refuse score 2.
  - accepted set: ['score:0', 'score:1']
  - verdict: OK — score:1 ∈ accepted ['score:0', 'score:1']
- `3540D939-DA16-4C1D-983C-E6B85C403F2F` — Deep Learning
  - Fully bilingual baseline case: e4_v2 must not penalise a syllabus with no omission via the new threshold rule.
  - accepted set: ['score:2']
  - verdict: OK — score:2 ∈ accepted ['score:2']
- `0B53E8E2-4B90-426F-A25C-3AA31FA4B649` — Internet of Things
  - has_english=True but no paired prefix has substantial content on both sides. Must remain semantic NA (resolver or handler), never technical NA.
  - accepted set: ['NA-handler_na', 'NA-resolver']
  - verdict: OK — NA-handler_na ∈ accepted ['NA-handler_na', 'NA-resolver']
- `FE97232C-4F07-41F8-A82F-FF73592265EC` — Machine Learning
  - Baseline had E4=0 with explicit contradictions on the EN side; e4_v2 must not relax this verdict.
  - accepted set: ['score:0']
  - verdict: OK — score:0 ∈ accepted ['score:0']
- `SYNTHETIC-9F-POSITIVE-E5-V1` — Sistemi distribuiti avanzati (ctrl)
  - Positive control with IT/EN paired on every prefix; must reach the maximum.
  - accepted set: ['score:2']
  - verdict: OK — score:2 ∈ accepted ['score:2']

## Distributions

- Observed E4: {'score:1': 1, 'score:2': 2, 'NA-handler_na': 1, 'score:0': 1}
- Extended status: {'completed': 5}