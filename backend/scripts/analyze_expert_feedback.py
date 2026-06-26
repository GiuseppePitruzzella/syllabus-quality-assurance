"""Offline analyses prompted by the Phase 5.8 expert feedback."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
import sys
from typing import Any

import typer

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.evaluation.analysis.local_requirements import (  # noqa: E402
    scan_local_requirements,
)
from app.models import Syllabus  # noqa: E402
from scripts.aggregate_human_judgment import (  # noqa: E402
    _metric_summary,
    _read_blind_csv,
    _read_system_judgments,
    _load_shortlist_slugs,
)


HJ_DIR = _PROJECT_ROOT / "data" / "human_judgment"
VALIDATION = _PROJECT_ROOT / "data" / "calibration" / "validation_lm18"
SELF_CONSISTENCY = _PROJECT_ROOT / "data" / "calibration" / "self_consistency_v1"
SELECTED_SEUIDS = (
    _PROJECT_ROOT / "data" / "calibration" / "validation_lm18"
    / "selected_seuids.json"
)

app = typer.Typer(help=__doc__, no_args_is_help=False)


def build_analysis(evaluator_id: str = "expert_01") -> dict[str, Any]:
    shortlist = _load_shortlist_slugs()
    human = _load_human(evaluator_id, shortlist)
    historical = {
        seuid: _read_system_judgments(seuid)
        for seuid in shortlist
    }
    current_c5 = _modal_scores(criterion="C5")

    c5_historical_pairs = _criterion_pairs(human, historical, "C5")
    c5_current_pairs = [
        (current_c5[seuid], judgments["C5"]["score"])
        for seuid, judgments in human.items()
        if seuid in current_c5 and isinstance(judgments["C5"]["score"], int)
    ]

    c7_pairs = _criterion_pairs(human, historical, "C7")
    c7_counterfactual_pairs: list[tuple[int, int]] = []
    c7_reason_categories: Counter[str] = Counter()
    for seuid, judgments in human.items():
        human_judgment = judgments["C7"]
        human_score = human_judgment["score"]
        system_score = historical[seuid]["C7"]["score"]
        if not isinstance(human_score, int) or not isinstance(system_score, int):
            continue
        justification = human_judgment["justification"].lower()
        category = _classify_c7_reason(justification)
        c7_reason_categories[category] += 1
        counterfactual = human_score
        if (
            human_score == 1
            and "struttura a blocchi" in justification
            and "istruzioni" in justification
            and "discorsiv" in justification
        ):
            counterfactual = 2
        c7_counterfactual_pairs.append((system_score, counterfactual))

    c6_pairs = _criterion_pairs(human, historical, "C6")
    self_consistency_metrics = json.loads(
        (SELF_CONSISTENCY / "metrics.json").read_text(encoding="utf-8")
    )
    c6_stability = next(
        item
        for item in self_consistency_metrics["criterion_aggregates"]
        if item["criterion"] == "C6"
    )

    local_scan = _scan_lm18()
    return {
        "phase": "5.8_expert_feedback_analysis_v1",
        "evaluator_id": evaluator_id,
        "human_data": {
            "syllabi_received": len(human),
            "complete_syllabi": sum(
                all(isinstance(j["score"], int) for j in judgments.values())
                for judgments in human.values()
            ),
            "missing_syllabi": [
                shortlist[seuid]
                for seuid, judgments in human.items()
                if not all(isinstance(j["score"], int) for j in judgments.values())
            ],
        },
        "c3_c4_overlap": _c3_c4_overlap(),
        "c5_sensitivity": {
            "historical_a1_v5": _metric_summary(c5_historical_pairs),
            "relaxed_a1_v6_modal": _metric_summary(c5_current_pairs),
            "interpretation": (
                "The historical comparison remains valid. The relaxed rule is "
                "a counterfactual sensitivity analysis, not a replacement of "
                "the blind human scores."
            ),
        },
        "c6_machine_vs_human": {
            "invalid_numeric_comparison": _metric_summary(c6_pairs),
            "self_consistency": c6_stability,
            "interpretation": (
                "C6 is perfectly stable intra-system, but the human instrument "
                "measured RA-content mapping while the system measured "
                "assessment transparency. Stability cannot establish validity."
            ),
        },
        "c7_sensitivity": {
            "observed": _metric_summary(c7_pairs),
            "narrow_counterfactual": _metric_summary(c7_counterfactual_pairs),
            "reason_categories": dict(sorted(c7_reason_categories.items())),
            "interpretation": (
                "Only the score explicitly tied to the block-vs-discursive "
                "instruction conflict is changed in the narrow sensitivity. "
                "Original expert scores remain untouched."
            ),
        },
        "local_requirements_scan": local_scan,
    }


def render_markdown(analysis: dict[str, Any]) -> str:
    c3_c4 = analysis["c3_c4_overlap"]
    c5 = analysis["c5_sensitivity"]
    c6 = analysis["c6_machine_vs_human"]
    c7 = analysis["c7_sensitivity"]
    local = analysis["local_requirements_scan"]
    lines = [
        "# Phase 5.8 — Analisi mirata del feedback esperto",
        "",
        "Analisi interamente offline: nessuna chiamata Vertex e nessuna nuova "
        "valutazione LLM.",
        "",
        "## Completezza del dato umano",
        "",
        f"- Syllabus nel workbook: {analysis['human_data']['syllabi_received']}.",
        f"- Syllabus completi: {analysis['human_data']['complete_syllabi']}.",
        f"- Fogli senza punteggi: "
        f"{', '.join(analysis['human_data']['missing_syllabi']) or 'nessuno'}.",
        "",
        "## C3/C4 — Stessa area, costrutti distinti",
        "",
        _overlap_line("Validation LM-18", c3_c4["validation_lm18"]),
        _overlap_line("Self-consistency", c3_c4["self_consistency"]),
        "",
        "L'accordo esatto è elevato, ma è favorito dall'effetto soffitto: "
        "molti syllabus ricevono 2 in entrambi i criteri. Il kappa pesato "
        "resta soltanto debole/moderato e sono presenti casi in cui C3 e C4 "
        "divergono. I criteri restano quindi separati come sottodimensioni "
        "della macro-area Risultati di apprendimento: C3 valuta osservabilità "
        "e verificabilità degli outcome; C4 presenza e differenziazione dei "
        "cinque Descrittori di Dublino.",
        "",
        "## C5 — Requisiti culturali/disciplinari",
        "",
        _metric_line("Confronto storico A1 a1_v5", c5["historical_a1_v5"]),
        _metric_line(
            "Sensibilità con score modale A1 a1_v6",
            c5["relaxed_a1_v6_modal"],
        ),
        "",
        "Il confronto storico resta valido perché questionario e A1 a1_v5 "
        "usavano la stessa regola. La seconda riga misura soltanto quanto "
        "cambierebbe l'accordo con la ridefinizione successiva.",
        "",
        "## C6 — Difficile per l'uomo, facile per la macchina?",
        "",
        _metric_line(
            "Accordo numerico non interpretabile",
            c6["invalid_numeric_comparison"],
        ),
        f"- Self-consistency C6: unanimità "
        f"{c6['self_consistency']['unanimity_rate']:.2f}, stdev media "
        f"{c6['self_consistency']['mean_stdev']:.2f}.",
        "",
        "C6 è stabile per la macchina, ma il questionario umano misurava un "
        "altro costrutto. Non è possibile concludere che la macchina sia più "
        "brava finché l'esperto non valuta la trasparenza della verifica.",
        "",
        "## C7 — Forma discorsiva vs struttura a blocchi",
        "",
        _metric_line("Confronto osservato", c7["observed"]),
        _metric_line(
            "Sensibilità stretta (solo conflitto esplicito blocchi/istruzioni)",
            c7["narrow_counterfactual"],
        ),
        f"- Categorie delle motivazioni: {c7['reason_categories']}.",
        "",
        "## Checklist locale LM-18 sui 30 syllabus",
        "",
        "| Controllo | Presenti | Totale |",
        "| --- | ---: | ---: |",
    ]
    for label, key in (
        ("Clausola modalità mista/distanza", "mixed_distance_clause"),
        ("Clausola CInAP/DSA", "cinap_dsa_clause"),
        ("Clausola verifica telematica", "telematic_assessment_clause"),
        ("Griglia completa delle fasce di voto", "grading_grid_complete"),
        ("Programmazione presente", "schedule_present"),
        ("Programmazione con tutti gli argomenti", "schedule_topics_complete"),
        ("Programmazione con almeno un riferimento", "schedule_references_any"),
        (
            "Programmazione con riferimenti in tutte le righe",
            "schedule_references_complete",
        ),
    ):
        lines.append(
            f"| {label} | {local['counts'][key]} | {local['n_syllabi']} |"
        )
    lines.extend(
        [
            "",
            "### Syllabus che non soddisfano ciascun controllo",
            "",
        ]
    )
    for label, key in (
        ("Clausola modalità mista/distanza", "mixed_distance_clause"),
        ("Clausola CInAP/DSA", "cinap_dsa_clause"),
        ("Clausola verifica telematica", "telematic_assessment_clause"),
        ("Griglia completa", "grading_grid_complete"),
        ("Programmazione presente", "schedule_present"),
        ("Programmazione con tutti gli argomenti", "schedule_topics_complete"),
        ("Programmazione con almeno un riferimento", "schedule_references_any"),
        (
            "Programmazione con riferimenti in tutte le righe",
            "schedule_references_complete",
        ),
    ):
        missing = [
            f"`{row['seuid'][:8]}` {row['course_name']}"
            for row in local["per_syllabus"]
            if not row[key]
        ]
        lines.append(f"- **{label}:** {', '.join(missing) or 'nessuno'}.")
    lines.extend(
        [
            "",
            "Questi controlli sono requisiti locali configurabili, non nuovi "
            "criteri core. La tabella completa per syllabus è disponibile nel "
            "JSON associato.",
            "",
        ]
    )
    return "\n".join(lines)


def _metric_line(label: str, summary: dict[str, Any]) -> str:
    return (
        f"- {label}: n={summary['n_primary_pairs']}, "
        f"κ={summary['kappa_linear_weighted']}, "
        f"accuracy={summary['accuracy']}, MAE={summary['mae']}."
    )


def _overlap_line(label: str, summary: dict[str, Any]) -> str:
    return (
        f"- {label}: n={summary['n_pairs']}, accordo esatto "
        f"{summary['exact_agreement_count']}/{summary['n_pairs']} "
        f"({summary['exact_agreement_rate']:.3f}), "
        f"κ={summary['kappa_linear_weighted']}, "
        f"MAE={summary['mae']}, coppie 2/2={summary['both_score_2']}."
    )


def _c3_c4_overlap(
    validation_dir: Path = VALIDATION,
    self_consistency_dir: Path = SELF_CONSISTENCY,
) -> dict[str, Any]:
    validation_records: list[dict[str, Any]] = []
    for path in validation_dir.glob("*__evaluation.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        evaluation = payload.get("evaluation") or {}
        scores = evaluation.get("criterion_scores") or {}
        validation_records.append(
            {
                "seuid": payload.get("seuid"),
                "course_name": evaluation.get("course_name_snapshot"),
                "c3": scores.get("C3"),
                "c4": scores.get("C4"),
            }
        )

    self_consistency_records: list[dict[str, Any]] = []
    for path in self_consistency_dir.glob("*__evaluation.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        scores = payload.get("criterion_scores") or {}
        self_consistency_records.append(
            {
                "seuid": payload.get("seuid"),
                "course_name": payload.get("slug"),
                "run_index": payload.get("run_index"),
                "c3": scores.get("C3"),
                "c4": scores.get("C4"),
            }
        )

    return {
        "validation_lm18": _overlap_summary(validation_records),
        "self_consistency": _overlap_summary(self_consistency_records),
        "interpretation": (
            "High raw agreement is dominated by ceiling scores and does not "
            "establish construct equivalence. Divergent cases support keeping "
            "C3 and C4 as separate subdimensions of learning outcomes."
        ),
    }


def _overlap_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [
        record
        for record in records
        if isinstance(record.get("c3"), int) and isinstance(record.get("c4"), int)
    ]
    pairs = [(record["c3"], record["c4"]) for record in valid]
    metrics = _metric_summary(pairs)
    exact = sum(c3 == c4 for c3, c4 in pairs)
    return {
        "n_pairs": len(pairs),
        "exact_agreement_count": exact,
        "exact_agreement_rate": round(exact / len(pairs), 3) if pairs else None,
        "kappa_linear_weighted": metrics["kappa_linear_weighted"],
        "mae": metrics["mae"],
        "both_score_2": sum(c3 == 2 and c4 == 2 for c3, c4 in pairs),
        "c3_distribution": dict(sorted(Counter(c3 for c3, _ in pairs).items())),
        "c4_distribution": dict(sorted(Counter(c4 for _, c4 in pairs).items())),
        "divergent_cases": [
            record
            for record in valid
            if record["c3"] != record["c4"]
        ],
    }


def _load_human(
    evaluator_id: str,
    shortlist: dict[str, str],
) -> dict[str, dict[str, dict[str, Any]]]:
    blind_dir = HJ_DIR / "evaluators" / evaluator_id / "blind"
    output = {}
    for seuid, slug in shortlist.items():
        path = blind_dir / f"{slug}_blind.csv"
        if path.exists():
            output[seuid] = _read_blind_csv(path)
    return output


def _criterion_pairs(
    human: dict[str, dict[str, dict[str, Any]]],
    system: dict[str, dict[str, dict[str, Any]]],
    criterion: str,
) -> list[tuple[int, int]]:
    return [
        (system[seuid][criterion]["score"], judgments[criterion]["score"])
        for seuid, judgments in human.items()
        if isinstance(judgments[criterion]["score"], int)
        and isinstance(system.get(seuid, {}).get(criterion, {}).get("score"), int)
    ]


def _modal_scores(criterion: str) -> dict[str, int]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for path in SELF_CONSISTENCY.glob("*__evaluation.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        score = (payload.get("criterion_scores") or {}).get(criterion)
        if isinstance(score, int):
            grouped[payload["seuid"]].append(score)
    return {
        seuid: Counter(scores).most_common(1)[0][0]
        for seuid, scores in grouped.items()
    }


def _classify_c7_reason(justification: str) -> str:
    if not justification:
        return "no_written_reason"
    if "struttura a blocchi" in justification or "modul" in justification:
        return "block_or_module_structure"
    if "discorsiv" in justification:
        return "narrative_form"
    if "stringat" in justification or "approfond" in justification:
        return "insufficient_detail"
    if "organizz" in justification:
        return "organization"
    return "other"


def _scan_lm18() -> dict[str, Any]:
    seuids = json.loads(SELECTED_SEUIDS.read_text(encoding="utf-8"))
    with SessionLocal() as session:
        rows = (
            session.query(Syllabus)
            .filter(Syllabus.seuid.in_(seuids))
            .order_by(Syllabus.course_name, Syllabus.seuid)
            .all()
        )
        results = [scan_local_requirements(row) for row in rows]
    keys = (
        "mixed_distance_clause",
        "cinap_dsa_clause",
        "telematic_assessment_clause",
        "grading_grid_complete",
        "schedule_present",
        "schedule_topics_complete",
        "schedule_references_any",
        "schedule_references_complete",
    )
    return {
        "n_syllabi": len(results),
        "counts": {
            key: sum(bool(result[key]) for result in results)
            for key in keys
        },
        "per_syllabus": results,
    }


@app.command()
def main(
    output_dir: Path = typer.Option(
        HJ_DIR / "analysis",
        file_okay=False,
    ),
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    analysis = build_analysis()
    (output_dir / "expert_feedback_analysis.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "expert_feedback_analysis.md").write_text(
        render_markdown(analysis),
        encoding="utf-8",
    )
    typer.echo("Expert-feedback analysis written without Vertex calls.")


if __name__ == "__main__":
    app()
