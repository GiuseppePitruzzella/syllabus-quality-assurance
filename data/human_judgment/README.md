# Phase 5.8 — Human-judgment validation protocol

Operational status: infrastructure ready; actual expert evaluation can proceed
with the thesis advisor as a single blind expert evaluator, or with additional
domain experts if they become available.

Eight LM-18 syllabi are evaluated against the same 9 criteria (C1-C9)
the multi-agent system scored automatically in Phase 5.7. With one
evaluator, the output is a single-rater diagnostic comparison between
system and expert. With two or more evaluators, inter-rater agreement
can additionally be reported as a rubric-stability check.

## Two phases

### Phase 1 — BLIND

- Form: `templates/blind/<slug>_blind.csv` (one per syllabus)
- You see: criterion name, summary, anchors 0/1/2
- You do NOT see: the system's score or justification
- Goal: form your own judgment before any system anchoring
- Output: filled-in CSV in `evaluators/<your_id>/blind/`

### Phase 2 — POST-HOC (optional, qualitative)

- Form: `templates/post_hoc/<slug>_posthoc.csv`
- You see: your blind score + the system score + system
  justification side by side
- You discuss: WHY disagreements occurred. NOT for kappa.
- Output: filled-in CSV in `evaluators/<your_id>/post_hoc/`

## Ground rules (Phase 1, blind)

- **Do not** open the system's report, summary, or evaluation
  JSON before completing Phase 1. The anchoring bias they
  would induce contaminates kappa.
- Read the syllabus on the UniCT site (links below) before
  filling in any score.
- Score the 9 criteria for one syllabus in a single sitting
  when possible (~30-40 min per syllabus, ~4h for all 8).
- Use `NA` only for technical impossibility (e.g. the field
  required by the criterion is genuinely absent and the
  criterion cannot be evaluated). Absence-as-low-quality is
  score 0, NOT NA.
- Score scale (rubrica UniCT, see `docs/progettazione.md`):
  - **0** = criterio non soddisfatto
  - **1** = criterio soddisfatto parzialmente
  - **2** = criterio pienamente soddisfatto

## How to fill a CSV

Open the CSV in Excel, Google Sheets, or LibreOffice. Each row
is one criterion. Fill in:

- `human_score`: integer 0, 1, or 2 (leave empty if `is_na = true`)
- `is_na`: `true` only if technically impossible to evaluate
- `na_reason`: free text (only if `is_na = true`)
- `human_justification`: 1-3 sentences explaining the score
- `evidence_quote`: a short literal quote from the syllabus
  supporting the score (optional but encouraged)

Save the file as CSV (UTF-8, comma-separated). Do not rename
columns. Keep the order of the rows.

## The 8 syllabi

1. **01_COMPUTER_VISION_LAB** — `88B7C1CE`
   COMPUTER VISION E LABORATORIO / EN: *COMPUTER VISION E LABORATORIO*
   IT: https://web.dmi.unict.it/corsi/lm-18/insegnamenti?seuid=88B7C1CE-B595-46A5-A37A-C5414AD807B5
   EN: https://web.dmi.unict.it/corsi/lm-18/insegnamenti?seuid=88B7C1CE-B595-46A5-A37A-C5414AD807B5&eng
2. **02_INTERNET_OF_THINGS** — `0B53E8E2`
   INTERNET OF THINGS / EN: *INTERNET OF THINGS*
   IT: https://web.dmi.unict.it/corsi/lm-18/insegnamenti?seuid=0B53E8E2-4B90-426F-A25C-3AA31FA4B649
   EN: https://web.dmi.unict.it/corsi/lm-18/insegnamenti?seuid=0B53E8E2-4B90-426F-A25C-3AA31FA4B649&eng
3. **03_PEER_TO_PEER_LAB** — `F4AF1512`
   PEER TO PEER AND WIRELESS NETWORKS E LABORATORIO / EN: *PEER TO PEER AND WIRELESS NETWORKS AND LABORATORY*
   IT: https://web.dmi.unict.it/corsi/lm-18/insegnamenti?seuid=F4AF1512-9D7A-4256-B57D-E103E05B009B
   EN: https://web.dmi.unict.it/corsi/lm-18/insegnamenti?seuid=F4AF1512-9D7A-4256-B57D-E103E05B009B&eng
4. **04_MULTIMEDIA_LAB** — `9A90BBCE`
   MULTIMEDIA E LABORATORIO / EN: *MULTIMEDIA AND LABORATORY*
   IT: https://web.dmi.unict.it/corsi/lm-18/insegnamenti?seuid=9A90BBCE-99E3-4FB0-BF91-CCAAA5C51791
   EN: https://web.dmi.unict.it/corsi/lm-18/insegnamenti?seuid=9A90BBCE-99E3-4FB0-BF91-CCAAA5C51791&eng
5. **05_COMPUTER_VISION** — `89E21813`
   COMPUTER VISION / EN: *COMPUTER VISION*
   IT: https://web.dmi.unict.it/corsi/lm-18/insegnamenti?seuid=89E21813-A17C-4C85-AF65-C295EE11ED59
   EN: https://web.dmi.unict.it/corsi/lm-18/insegnamenti?seuid=89E21813-A17C-4C85-AF65-C295EE11ED59&eng
6. **06_OTTIMIZZAZIONE** — `E2446DF6`
   OTTIMIZZAZIONE / EN: *OPTIMIZATION*
   IT: https://web.dmi.unict.it/corsi/lm-18/insegnamenti?seuid=E2446DF6-59A1-46FD-B8D8-635EB937C1B3
   EN: https://web.dmi.unict.it/corsi/lm-18/insegnamenti?seuid=E2446DF6-59A1-46FD-B8D8-635EB937C1B3&eng
7. **07_DEEP_LEARNING** — `3540D939`
   Deep Learning / EN: *Deep Learning*
   IT: https://web.dmi.unict.it/corsi/lm-18/insegnamenti?seuid=3540D939-DA16-4C1D-983C-E6B85C403F2F
   EN: https://web.dmi.unict.it/corsi/lm-18/insegnamenti?seuid=3540D939-DA16-4C1D-983C-E6B85C403F2F&eng
8. **08_VULN_ASSESSMENT_PT** — `46D62804`
   VULNERABILITY ASSESSMENT E PENETRATION TESTING (VAPT) / EN: *VULNERABILITY ASSESSMENT E PENETRATION TESTING (VAPT)*
   IT: https://web.dmi.unict.it/corsi/lm-18/insegnamenti?seuid=46D62804-0FCD-4478-A51D-A752B64A7DCB
   EN: https://web.dmi.unict.it/corsi/lm-18/insegnamenti?seuid=46D62804-0FCD-4478-A51D-A752B64A7DCB&eng

## After Phase 1

Copy your filled `*_blind.csv` files into a new folder named
`evaluators/<your_id>/blind/`. Run:

```bash
cd backend
uv run python scripts/aggregate_human_judgment.py
```

The aggregator computes weighted Cohen's kappa per criterion,
MAE on integer scores, accuracy, CoreScore comparison, explicit
NA/missing exclusion counts, and the top-N strongest disagreements.
NA and missing cells are excluded from primary metrics and reported
separately. No automatic majority/consensus score is computed. Output:
`data/human_judgment/aggregate.json` and `aggregate.md`.

## Format details

See `schema.json` for the canonical JSON shape if you prefer
exporting to JSON instead of CSV.

## Expert dataset received (2026-06-26 follow-up)

The thesis advisor returned the updated blind workbook after the minimal
follow-up request. For research-data integrity:

- the original bytes are archived under
  `evaluators/expert_01/source/expert_01_blind_raw.xlsx`;
- `source/acquisition_manifest.json` records SHA-256, size, receipt time and
  blind handling;
- `scripts/import_human_judgment_xlsx.py` converts the OpenXML workbook into
  canonical per-syllabus CSVs without modifying or re-saving the source;
- the imported workbook contains 72 numeric judgments and 0 missing values:
  the previously blank `08_VULN_ASSESSMENT_PT` sheet is now complete, and C6
  has been reviewed for all eight syllabus after the methodological
  clarification.

### Comparability gate

Before calculating system-vs-expert metrics, the delivered questionnaire was
compared with the prompt versions that generated `validation_lm18`
(`a1_v5`, `a2_v1`, `a3_v1`, `a4_v2`). Results are stored in
`analysis/comparability_audit.{json,md}`:

- primary comparison: C1, C3, C4, C5, C6;
- secondary/exploratory comparison: C2, C7, C8, C9;
- excluded from agreement metrics: none.

C6 is included in the primary comparison only for the updated workbook: the
template text remains legacy, but the evaluator explicitly revised C6 after the
follow-up clarification using the assessment-transparency construct measured by
the system.

`aggregate_human_judgment.py` retains the all-criteria descriptive output but
reports comparability-aware primary metrics first. Additional offline analyses
of C5, C6, C7 and LM-18 local requirements are written to
`analysis/expert_feedback_analysis.{json,md}`. The minimal clarification request
and its closure are recorded in `analysis/followup_request.md`.
