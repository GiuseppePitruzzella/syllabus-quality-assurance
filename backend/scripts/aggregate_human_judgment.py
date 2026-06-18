"""Phase 5.8 — aggregate human judgments against the system.

Reads the filled-in blind CSVs from `data/human_judgment/evaluators/<id>/blind/`
and computes external-validation metrics against the system scores
recorded in `data/calibration/validation_lm18/<seuid>__evaluation.json`.

Metrics per criterion (C1..C9):

  - weighted Cohen's kappa (linear weights on numeric 0/1/2 pairs only)
  - accuracy (exact agreement on numeric 0/1/2 pairs only)
  - mean absolute error (numeric 0/1/2 pairs only)
  - coverage counts for NA and missing cells, reported separately
  - confusion matrix system × human, including NA/missing process labels

Aggregate (across criteria):

  - macro-kappa, macro-accuracy, macro-MAE
  - CoreScore comparison per syllabus (system vs human)
  - top-N strongest disagreements (criterion + syllabus + scores + quotes)

When two or more evaluators are present:

  - human-human kappa for the first two evaluators as a rubric stability check
  - system vs each evaluator separately

No majority/consensus score is computed automatically. With two evaluators,
consensus must be produced only through a documented post-hoc discussion.

Output: `data/human_judgment/aggregate.json` + `aggregate.md`.
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import typer  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

VALIDATION = _PROJECT_ROOT / "data" / "calibration" / "validation_lm18"
HJ_DIR = _PROJECT_ROOT / "data" / "human_judgment"

CRITERIA = ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9")
# Primary metrics are defined only on the ordinal score scale.
SCORE_LABELS: tuple[int, ...] = (0, 1, 2)
# Process labels are retained for audit, confusion matrices, and exclusions.
REPORT_LABELS: tuple[str | int, ...] = (0, 1, 2, "NA", "MISSING")

console = Console()
app = typer.Typer(help=__doc__, no_args_is_help=False)


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


def _parse_score(value: str) -> int | None:
    value = (value or "").strip()
    if value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_bool(value: str) -> bool:
    return (value or "").strip().lower() in {"true", "1", "yes", "y"}


def _slug_to_seuid(slug: str, shortlist: dict[str, str]) -> str | None:
    for seuid, s in shortlist.items():
        if s in slug:
            return seuid
    return None


def _load_shortlist_slugs() -> dict[str, str]:
    """Read the seuid -> slug map from setup_human_judgment.SHORTLIST."""
    from setup_human_judgment import SHORTLIST  # noqa: E402

    return {seuid: slug for seuid, slug in SHORTLIST}


def _read_blind_csv(path: Path) -> dict[str, dict[str, Any]]:
    """Parse a filled-in blind CSV. Returns {criterion: {score, is_na, ...}}."""
    out: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = (row.get("criterion") or "").strip()
            if code not in CRITERIA:
                continue
            out[code] = {
                "score": _parse_score(row.get("human_score", "")),
                "is_na": _parse_bool(row.get("is_na", "")),
                "na_reason": (row.get("na_reason") or "").strip() or None,
                "justification": (row.get("human_justification") or "").strip(),
                "evidence": (row.get("evidence_quote") or "").strip(),
            }
    return out


def _read_system_judgments(seuid: str) -> dict[str, dict[str, Any]]:
    """Load the system's per-criterion judgments for one syllabus."""
    path = VALIDATION / f"{seuid}__evaluation.json"
    if not path.exists():
        return {}
    e = json.loads(path.read_text(encoding="utf-8"))["evaluation"]
    out: dict[str, dict[str, Any]] = {}
    for agent_out in (e.get("agent_outputs") or {}).values():
        if not agent_out:
            continue
        for j in agent_out.get("judgments") or []:
            out[j["criterion_code"]] = {
                "score": j.get("score"),
                "is_na": j.get("is_na", False),
                "justification": (j.get("justification") or "").strip(),
                "course_name": e.get("course_name_snapshot"),
            }
    return out


# ---------------------------------------------------------------------------
# Metrics (pure-python, no scikit-learn dependency)
# ---------------------------------------------------------------------------


def _label_of(score: int | None, is_na: bool) -> str | int | None:
    if is_na:
        return "NA"
    if score is None:
        return "MISSING"
    if score not in SCORE_LABELS:
        return "MISSING"
    return score


def _weighted_cohen_kappa(
    pairs: list[tuple[Any, Any]], weights: str = "linear"
) -> float | None:
    """Weighted Cohen's kappa over numeric labels 0, 1 and 2.

    NA and missing values are intentionally excluded before this helper is
    called. They are reported as process counts, not treated as ordinal quality
    categories.
    """
    if not pairs:
        return None
    labels = SCORE_LABELS
    obs = {(a, b): 0 for a in labels for b in labels}
    a_marg = dict.fromkeys(labels, 0)
    b_marg = dict.fromkeys(labels, 0)
    n = 0
    for a, b in pairs:
        if a not in labels or b not in labels:
            continue
        n += 1
        obs[(a, b)] += 1
        a_marg[a] += 1
        b_marg[b] += 1
    if n == 0:
        return None

    def w(x: Any, y: Any) -> float:
        if x == y:
            return 0.0
        return abs(int(x) - int(y)) / 2.0

    obs_disagree = sum(w(a, b) * c for (a, b), c in obs.items()) / n
    exp_disagree = sum(
        w(a, b) * (a_marg[a] * b_marg[b]) for a in labels for b in labels
    ) / (n * n)
    if exp_disagree == 0:
        return 1.0 if obs_disagree == 0 else None
    return round(1.0 - obs_disagree / exp_disagree, 3)


def _accuracy(pairs: list[tuple[Any, Any]]) -> float | None:
    if not pairs:
        return None
    return round(sum(1 for a, b in pairs if a == b) / len(pairs), 3)


def _mae(pairs: list[tuple[Any, Any]]) -> float | None:
    """MAE over integer score pairs."""
    if not pairs:
        return None
    return round(sum(abs(a - b) for a, b in pairs) / len(pairs), 3)


def _confusion_matrix(pairs: list[tuple[Any, Any]]) -> dict[str, dict[str, int]]:
    """Confusion matrix system (rows) × human (cols), including process labels."""
    mat: dict[str, dict[str, int]] = {
        str(a): {str(b): 0 for b in REPORT_LABELS} for a in REPORT_LABELS
    }
    for sys_l, hum_l in pairs:
        if sys_l in REPORT_LABELS and hum_l in REPORT_LABELS:
            mat[str(sys_l)][str(hum_l)] += 1
    return mat


def _primary_pairs(pairs: list[tuple[Any, Any]]) -> list[tuple[int, int]]:
    """Return only numeric 0/1/2 pairs used by primary metrics."""
    return [
        (a, b)
        for a, b in pairs
        if isinstance(a, int) and isinstance(b, int)
    ]


def _exclusion_counts(pairs: list[tuple[Any, Any]]) -> dict[str, int]:
    """Count why observations do not enter primary metrics."""
    missing = 0
    na = 0
    for a, b in pairs:
        if a == "MISSING" or b == "MISSING":
            missing += 1
        elif a == "NA" or b == "NA":
            na += 1
    return {"n_excluded_na": na, "n_excluded_missing": missing}


def _metric_summary(pairs: list[tuple[Any, Any]]) -> dict[str, Any]:
    """Primary metrics plus explicit NA/missing exclusions."""
    primary = _primary_pairs(pairs)
    counts = _exclusion_counts(pairs)
    return {
        "n_observations": len(pairs),
        "n_primary_pairs": len(primary),
        **counts,
        "kappa_linear_weighted": _weighted_cohen_kappa(primary),
        "accuracy": _accuracy(primary),
        "mae": _mae(primary),
    }


# ---------------------------------------------------------------------------
# Per-evaluator analysis
# ---------------------------------------------------------------------------


def _evaluator_analysis(
    evaluator_id: str,
    blind_dir: Path,
    shortlist: dict[str, str],
) -> dict[str, Any]:
    """Compute system-vs-evaluator metrics for one evaluator."""
    judgments_by_seuid: dict[str, dict[str, dict[str, Any]]] = {}
    files_read: list[str] = []

    for csv_path in sorted(blind_dir.glob("*_blind.csv")):
        seuid = _slug_to_seuid(csv_path.stem, shortlist)
        if seuid is None:
            console.print(f"[yellow]skip[/yellow] {csv_path.name}: unknown slug")
            continue
        judgments_by_seuid[seuid] = _read_blind_csv(csv_path)
        files_read.append(csv_path.name)

    if not judgments_by_seuid:
        return {"evaluator_id": evaluator_id, "error": "no CSVs found"}

    # Pairs aggregated per criterion
    per_criterion_pairs: dict[str, list[tuple[Any, Any, str]]] = defaultdict(list)
    syllabus_core_scores: dict[str, dict[str, float | None]] = {}

    for seuid, hum in judgments_by_seuid.items():
        sys_j = _read_system_judgments(seuid)
        course = next(iter(sys_j.values()), {}).get("course_name", seuid)
        # CoreScore for system + human
        sys_scores = [
            sys_j[c]["score"]
            for c in CRITERIA
            if c in sys_j
            and isinstance(sys_j[c]["score"], int)
            and not sys_j[c].get("is_na")
        ]
        hum_scores = [
            hum[c]["score"]
            for c in CRITERIA
            if c in hum and isinstance(hum[c]["score"], int) and not hum[c]["is_na"]
        ]
        syllabus_core_scores[seuid] = {
            "course_name": course,
            "system_core": (
                round(statistics.mean(sys_scores), 2) if sys_scores else None
            ),
            "human_core": (
                round(statistics.mean(hum_scores), 2) if hum_scores else None
            ),
            "n_human_evaluated": len(hum_scores),
        }
        for c in CRITERIA:
            s = sys_j.get(c, {})
            h = hum.get(c, {})
            sys_label = _label_of(s.get("score"), s.get("is_na", False))
            hum_label = _label_of(h.get("score"), h.get("is_na", False))
            per_criterion_pairs[c].append((sys_label, hum_label, seuid))

    # Per-criterion metrics
    per_criterion = {}
    all_pairs: list[tuple[Any, Any]] = []
    disagreements: list[dict[str, Any]] = []
    for c in CRITERIA:
        triples = per_criterion_pairs[c]
        pairs = [(a, b) for a, b, _ in triples]
        per_criterion[c] = {
            **_metric_summary(pairs),
            "confusion_matrix": _confusion_matrix(pairs),
        }
        all_pairs.extend(pairs)
        for sys_label, hum_label, seuid in triples:
            if sys_label != hum_label and "MISSING" not in {sys_label, hum_label}:
                hum_j = judgments_by_seuid[seuid].get(c, {})
                sys_j = _read_system_judgments(seuid).get(c, {})
                disagreements.append({
                    "criterion": c,
                    "seuid": seuid,
                    "course_name": syllabus_core_scores[seuid]["course_name"],
                    "system_score": sys_label,
                    "human_score": hum_label,
                    "delta": _label_distance(sys_label, hum_label),
                    "system_justification": sys_j.get("justification", "")[:240],
                    "human_justification": hum_j.get("justification", "")[:240],
                    "evidence_quote": hum_j.get("evidence", ""),
                })
    disagreements.sort(key=lambda d: -d["delta"])

    macro = {
        **_metric_summary(all_pairs),
    }

    # CoreScore correlation (system vs human)
    sys_h = [
        (v["system_core"], v["human_core"])
        for v in syllabus_core_scores.values()
        if v["system_core"] is not None and v["human_core"] is not None
    ]
    core_mae = (
        round(sum(abs(a - b) for a, b in sys_h) / len(sys_h), 3) if sys_h else None
    )

    return {
        "evaluator_id": evaluator_id,
        "files_read": files_read,
        "n_syllabi": len(judgments_by_seuid),
        "macro": macro,
        "per_criterion": per_criterion,
        "core_score_comparison": {
            "n_pairs": len(sys_h),
            "mean_absolute_error": core_mae,
            "per_syllabus": syllabus_core_scores,
        },
        "top_disagreements": disagreements[:15],
    }


def _label_distance(a: Any, b: Any) -> float:
    if a == b:
        return 0.0
    if a in {"NA", "MISSING"} or b in {"NA", "MISSING"}:
        return 2.0
    return abs(int(a) - int(b))


# ---------------------------------------------------------------------------
# Inter-evaluator (when N >= 2)
# ---------------------------------------------------------------------------


def _human_human_analysis(
    evaluators: list[dict[str, Any]], shortlist: dict[str, str]
) -> dict[str, Any] | None:
    if len(evaluators) < 2:
        return None
    # For simplicity, compare evaluator 1 vs 2 (the first two by id)
    e1_id = evaluators[0]["evaluator_id"]
    e2_id = evaluators[1]["evaluator_id"]
    e1_dir = HJ_DIR / "evaluators" / e1_id / "blind"
    e2_dir = HJ_DIR / "evaluators" / e2_id / "blind"

    pairs_by_criterion: dict[str, list[tuple[Any, Any]]] = defaultdict(list)
    for csv1 in sorted(e1_dir.glob("*_blind.csv")):
        seuid = _slug_to_seuid(csv1.stem, shortlist)
        csv2 = e2_dir / csv1.name
        if seuid is None or not csv2.exists():
            continue
        h1 = _read_blind_csv(csv1)
        h2 = _read_blind_csv(csv2)
        for c in CRITERIA:
            a = _label_of(h1.get(c, {}).get("score"), h1.get(c, {}).get("is_na", False))
            b = _label_of(h2.get(c, {}).get("score"), h2.get(c, {}).get("is_na", False))
            pairs_by_criterion[c].append((a, b))

    per_crit = {}
    all_pairs: list[tuple[Any, Any]] = []
    for c in CRITERIA:
        pairs = pairs_by_criterion[c]
        per_crit[c] = {
            **_metric_summary(pairs),
        }
        all_pairs.extend(pairs)
    return {
        "evaluator_a": e1_id,
        "evaluator_b": e2_id,
        "macro": {
            **_metric_summary(all_pairs),
        },
        "per_criterion": per_crit,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _render_markdown(report: dict[str, Any]) -> str:
    L = ["# Phase 5.8 — Human-judgment aggregate report", ""]
    L += [
        f"- Generated at: `{report['generated_at']}`",
        f"- Evaluators: **{len(report['evaluators'])}**",
        "- Primary metrics exclude `NA` and missing cells; those observations "
        "are reported separately as process counts.",
        "- No automatic majority/consensus score is computed.",
        "",
    ]
    if len(report["evaluators"]) == 1:
        L += [
            "> Single-rater diagnostic validation: this report supports a "
            "system-vs-expert comparison, not inter-rater reliability.",
            "",
        ]
    if report.get("human_human"):
        hh = report["human_human"]
        L += [
            "## Inter-evaluator agreement (human vs human)",
            "",
            f"- {hh['evaluator_a']} vs {hh['evaluator_b']}",
            f"- Total observations = {hh['macro']['n_observations']}",
            f"- Primary numeric pairs = {hh['macro']['n_primary_pairs']}",
            f"- Excluded NA = {hh['macro']['n_excluded_na']}",
            f"- Excluded missing = {hh['macro']['n_excluded_missing']}",
            f"- Macro kappa = **{hh['macro']['kappa_linear_weighted']}**",
            f"- Macro accuracy = **{hh['macro']['accuracy']}**",
            f"- Macro MAE = **{hh['macro']['mae']}**",
            "",
            "| Crit | obs | primary | NA excl. | missing excl. | κ | acc | MAE |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for c in CRITERIA:
            s = hh["per_criterion"][c]
            L.append(
                f"| {c} | {s['n_observations']} | {s['n_primary_pairs']} | "
                f"{s['n_excluded_na']} | {s['n_excluded_missing']} | "
                f"{s['kappa_linear_weighted']} | {s['accuracy']} | {s['mae']} |"
            )
        L.append("")

    for ev in report["evaluators"]:
        L += [
            f"## System vs evaluator `{ev['evaluator_id']}`",
            "",
            f"- N syllabi: **{ev['n_syllabi']}**",
            f"- Total observations: **{ev['macro']['n_observations']}**",
            f"- Primary numeric pairs: **{ev['macro']['n_primary_pairs']}**",
            f"- Excluded NA: **{ev['macro']['n_excluded_na']}**",
            f"- Excluded missing: **{ev['macro']['n_excluded_missing']}**",
            f"- Macro kappa = **{ev['macro']['kappa_linear_weighted']}**",
            f"- Macro accuracy = **{ev['macro']['accuracy']}**",
            f"- Macro MAE = **{ev['macro']['mae']}**",
            "",
            f"- CoreScore MAE (system vs human, per syllabus): "
            f"**{ev['core_score_comparison']['mean_absolute_error']}**",
            "",
            "### Per-criterion (system vs this evaluator)",
            "",
            "| Crit | obs | primary | NA excl. | missing excl. | κ weighted | acc | MAE |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for c in CRITERIA:
            s = ev["per_criterion"][c]
            L.append(
                f"| {c} | {s['n_observations']} | {s['n_primary_pairs']} | "
                f"{s['n_excluded_na']} | {s['n_excluded_missing']} | "
                f"{s['kappa_linear_weighted']} | {s['accuracy']} | {s['mae']} |"
            )
        L += [
            "",
            "### CoreScore per syllabus (system vs human)",
            "",
            "| Syllabus | system | human | delta |",
            "| --- | ---: | ---: | ---: |",
        ]
        for seuid, v in ev["core_score_comparison"]["per_syllabus"].items():
            sc = v["system_core"]
            hc = v["human_core"]
            delta = round(abs(sc - hc), 2) if (sc is not None and hc is not None) else "—"
            L.append(
                f"| `{seuid[:8]}` {v['course_name']} | "
                f"{sc if sc is not None else '—'} | "
                f"{hc if hc is not None else '—'} | {delta} |"
            )
        L += ["", "### Top disagreements (system vs this evaluator)", ""]
        for d in ev["top_disagreements"][:10]:
            L += [
                f"- **{d['criterion']}** on `{d['seuid'][:8]}` ({d['course_name']}) — "
                f"system={d['system_score']} vs human={d['human_score']}  "
                f"(delta {d['delta']})",
                f"  - system: {d['system_justification']}",
                f"  - human:  {d['human_justification']}"
                + (f" (evidence: \"{d['evidence_quote']}\")" if d['evidence_quote'] else ""),
            ]
        L.append("")
    return "\n".join(L).rstrip() + "\n"


def _print_summary_table(report: dict[str, Any]) -> None:
    table = Table(title="System vs human — macro metrics", show_header=True)
    table.add_column("evaluator")
    table.add_column("n_syllabi", justify="right")
    table.add_column("primary", justify="right")
    table.add_column("NA excl.", justify="right")
    table.add_column("missing excl.", justify="right")
    table.add_column("κ weighted", justify="right")
    table.add_column("accuracy", justify="right")
    table.add_column("MAE", justify="right")
    table.add_column("CoreScore MAE", justify="right")
    for ev in report["evaluators"]:
        table.add_row(
            ev["evaluator_id"],
            str(ev["n_syllabi"]),
            str(ev["macro"]["n_primary_pairs"]),
            str(ev["macro"]["n_excluded_na"]),
            str(ev["macro"]["n_excluded_missing"]),
            str(ev["macro"]["kappa_linear_weighted"]),
            str(ev["macro"]["accuracy"]),
            str(ev["macro"]["mae"]),
            str(ev["core_score_comparison"]["mean_absolute_error"]),
        )
    console.print(table)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@app.command()
def main(
    output_dir: Path = typer.Option(
        HJ_DIR, "--output-dir", help="Where to write aggregate.{json,md}."
    ),
) -> None:
    """Read all evaluators' blind CSVs and compute external-validation metrics."""
    from datetime import datetime, timezone

    shortlist = _load_shortlist_slugs()
    evaluators_root = HJ_DIR / "evaluators"
    if not evaluators_root.exists():
        console.print(
            f"[red]No evaluators directory found:[/red] {evaluators_root}\n"
            "Each evaluator should place their filled CSVs under "
            "`data/human_judgment/evaluators/<id>/blind/`."
        )
        raise typer.Exit(code=1)

    evaluators: list[dict[str, Any]] = []
    for ev_dir in sorted(evaluators_root.iterdir()):
        if not ev_dir.is_dir():
            continue
        blind_dir = ev_dir / "blind"
        if not blind_dir.exists():
            console.print(f"[yellow]skip[/yellow] {ev_dir.name}: no blind/ folder")
            continue
        console.rule(f"[bold]Evaluator[/bold] {ev_dir.name}")
        ev_report = _evaluator_analysis(ev_dir.name, blind_dir, shortlist)
        evaluators.append(ev_report)

    if not evaluators:
        console.print("[red]No evaluator data found.[/red]")
        raise typer.Exit(code=1)

    human_human = _human_human_analysis(evaluators, shortlist)

    report = {
        "phase": "5.8",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_evaluators": len(evaluators),
        "evaluators": evaluators,
        "human_human": human_human,
    }

    out_json = output_dir / "aggregate.json"
    out_md = output_dir / "aggregate.md"
    out_json.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    out_md.write_text(_render_markdown(report), encoding="utf-8")

    console.print()
    _print_summary_table(report)
    console.print(f"\n[green]Wrote[/green] {out_json}")
    console.print(f"[green]Wrote[/green] {out_md}")


if __name__ == "__main__":
    app()
