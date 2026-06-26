"""Controlled single-aspect perturbations + directional sensitivity metrics.

Pure functions. No Vertex AI, no DB, no LangGraph. Perturbations operate on
the syllabus *snapshot dict* (``snapshot_syllabus`` output), so variant
generation is deterministic and unit-testable offline. Metrics consume only
structured per-run fields (scores / NA), never the report text.

Spec: docs/superpowers/specs/2026-06-26-perturbation-sensitivity-test-design.md
"""
from __future__ import annotations

import copy
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.evaluation.analysis.self_consistency import CRITERIA_ORDER, RunRecord

Snapshot = dict[str, Any]
PerturbFn = Callable[[Snapshot], Snapshot]

_GENERIC_IT = (
    "Il corso fornisce conoscenze e competenze sugli argomenti trattati a lezione."
)
_GENERIC_EN = (
    "The course provides knowledge and skills on the topics covered in class."
)


@dataclass(frozen=True)
class Perturbation:
    """One controlled, single-aspect degradation of a base snapshot."""

    id: str
    target_criteria: tuple[str, ...]      # primary target = first element
    expected_direction: str               # always "decrease" here
    description: str
    plausible_coupling: tuple[str, ...]   # non-target criteria allowed to move
    apply: PerturbFn

    def meta(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "target_criteria": list(self.target_criteria),
            "primary_target": self.target_criteria[0],
            "expected_direction": self.expected_direction,
            "description": self.description,
            "plausible_coupling": list(self.plausible_coupling),
        }


def _blank(snap: Snapshot, *fields: str) -> Snapshot:
    out = copy.deepcopy(snap)
    for f in fields:
        out[f] = [] if isinstance(out.get(f), list) else ""
    return out


def _set(snap: Snapshot, **values: Any) -> Snapshot:
    out = copy.deepcopy(snap)
    out.update(values)
    return out


def _flatten(text: str | None) -> str:
    return " ".join((text or "").split())


def _inject_noise(text: str) -> str:
    typo = (text or "").replace(" e ", " ee ").replace(" di ", " dii ")
    return "[TODO]\n\n### " + typo + " �\n\n\t  "


def perturb_c1_remove_sections(snap: Snapshot) -> Snapshot:
    return _blank(
        snap, "teaching_methods_it", "teaching_methods_en",
        "attendance_it", "attendance_en", "references_it", "references_en",
    )


def perturb_c2_strip_english(snap: Snapshot) -> Snapshot:
    return _blank(
        snap, "course_name_en", "learning_outcomes_en",
        "dublin_knowledge_en", "dublin_applying_en", "dublin_judgement_en",
        "dublin_communication_en", "dublin_learning_en",
        "course_content_en", "assessment_methods_en",
    )


def perturb_c3c4_generic_outcomes(snap: Snapshot) -> Snapshot:
    out = copy.deepcopy(snap)
    for f in ("learning_outcomes_it", "dublin_knowledge_it", "dublin_applying_it",
              "dublin_judgement_it", "dublin_communication_it", "dublin_learning_it"):
        out[f] = _GENERIC_IT
    for f in ("learning_outcomes_en", "dublin_knowledge_en", "dublin_applying_en",
              "dublin_judgement_en", "dublin_communication_en", "dublin_learning_en"):
        out[f] = _GENERIC_EN
    return out


def perturb_c5_blank_prerequisites(snap: Snapshot) -> Snapshot:
    return _set(
        snap,
        prerequisites_it="Prerequisiti non indicati.",
        prerequisites_en="Prerequisites not specified.",
    )


def perturb_c6_strip_assessment(snap: Snapshot) -> Snapshot:
    return _set(
        snap,
        assessment_methods_it="L'esame consiste in una prova.",
        assessment_methods_en="The exam consists of a test.",
        sample_questions_it="",
        sample_questions_en="",
    )


def perturb_c7_destructure_content(snap: Snapshot) -> Snapshot:
    out = copy.deepcopy(snap)
    out["schedule_it"] = []
    out["schedule_en"] = []
    out["course_content_it"] = _flatten(out.get("course_content_it"))
    out["course_content_en"] = _flatten(out.get("course_content_en"))
    return out


def perturb_c9_editorial_noise(snap: Snapshot) -> Snapshot:
    out = copy.deepcopy(snap)
    for f in ("learning_outcomes_it", "course_content_it",
              "assessment_methods_it", "teaching_methods_it"):
        v = out.get(f)
        if isinstance(v, str) and v:
            out[f] = _inject_noise(v)
    return out


PERTURBATIONS: tuple[Perturbation, ...] = (
    Perturbation(
        "C1_remove_sections", ("C1",), "decrease",
        "Svuota 3 sezioni obbligatorie (metodi didattici, frequenza, riferimenti).",
        ("C7", "C8", "C9"), perturb_c1_remove_sections,
    ),
    Perturbation(
        "C2_strip_english", ("C2",), "decrease",
        "Svuota i campi EN rilevanti (titolo, risultati, descrittori, contenuti, verifica).",
        ("C1",), perturb_c2_strip_english,
    ),
    Perturbation(
        "C3C4_generic_outcomes", ("C3", "C4"), "decrease",
        "Rende i risultati di apprendimento generici, corso-centrici e ripetitivi.",
        (), perturb_c3c4_generic_outcomes,
    ),
    Perturbation(
        "C5_blank_prerequisites", ("C5",), "decrease",
        "Sostituisce i prerequisiti con 'Prerequisiti non indicati'.",
        ("C1",), perturb_c5_blank_prerequisites,
    ),
    Perturbation(
        "C6_strip_assessment", ("C6",), "decrease",
        "Rimuove griglia/fasce/criteri/pesi/esempi dalla verifica.",
        (), perturb_c6_strip_assessment,
    ),
    Perturbation(
        "C7_destructure_content", ("C7",), "decrease",
        "Svuota la programmazione (schedule) e appiattisce i contenuti.",
        ("C8",), perturb_c7_destructure_content,
    ),
    Perturbation(
        "C9_editorial_noise", ("C9",), "decrease",
        "Inietta refusi, marker tecnici e formattazione sporca nei campi IT.",
        (), perturb_c9_editorial_noise,
    ),
)

_BY_ID = {p.id: p for p in PERTURBATIONS}


def perturbation_by_id(variant_id: str) -> Perturbation:
    return _BY_ID[variant_id]


def generate_variants(
    base_snapshot: Snapshot,
    perturbations: tuple[Perturbation, ...] = PERTURBATIONS,
) -> dict[str, Snapshot]:
    """Return {variant_id: perturbed snapshot}. The base is left untouched."""
    return {p.id: p.apply(base_snapshot) for p in perturbations}


class TargetVerdict(BaseModel):
    criterion: str
    base_mean: float | None
    base_range: float | None
    pert_mean: float | None
    pert_range: float | None
    delta: float | None
    expected_direction: str
    noise_floor: float | None
    verdict: str   # PASS | WEAK | FAIL | TARGET_BECAME_NA | insufficient_base_data
    passed: bool


def _mean_range(scores: list[int | None]) -> tuple[float | None, float | None, int]:
    numeric = [s for s in scores if s is not None]
    if not numeric:
        return None, None, 0
    rng = float(max(numeric) - min(numeric))
    return round(statistics.mean(numeric), 4), rng, len(numeric)


def classify_verdict(
    criterion: str,
    base_scores: list[int | None],
    pert_scores: list[int | None],
    expected_direction: str = "decrease",
    min_delta: float = 0.5,
) -> TargetVerdict:
    """Three-way verdict for one target criterion using the base run-to-run
    range as an empirical noise floor.

    PASS  : correct direction AND |delta| >= min_delta AND |delta| > base_range.
    WEAK  : correct direction AND |delta| >= min_delta but within base noise.
    FAIL  : wrong direction OR |delta| < min_delta.
    Special: TARGET_BECAME_NA (>=2 of 3 variant runs NA),
             insufficient_base_data (<2 valid base runs).
    """
    base_mean, base_range, n_base = _mean_range(base_scores)
    pert_mean, pert_range, n_pert = _mean_range(pert_scores)
    n_pert_na = len(pert_scores) - n_pert

    delta: float | None = None
    if n_base < 2 or base_mean is None:
        verdict, passed = "insufficient_base_data", False
    elif n_pert_na >= 2:
        verdict, passed = "TARGET_BECAME_NA", False
    else:
        delta = round(pert_mean - base_mean, 4)
        correct = delta < 0 if expected_direction == "decrease" else delta > 0
        if not correct or abs(delta) < min_delta:
            verdict, passed = "FAIL", False
        elif abs(delta) > base_range:
            verdict, passed = "PASS", True
        else:
            verdict, passed = "WEAK", False

    return TargetVerdict(
        criterion=criterion, base_mean=base_mean, base_range=base_range,
        pert_mean=pert_mean, pert_range=pert_range, delta=delta,
        expected_direction=expected_direction, noise_floor=base_range,
        verdict=verdict, passed=passed,
    )


class SideEffect(BaseModel):
    criterion: str
    delta: float
    classification: str   # expected_coupling | spurious


class VariantResult(BaseModel):
    variant_id: str
    target_criteria: list[str]
    primary_target: str
    target_verdicts: list[TargetVerdict]
    passed: bool
    side_effects: list[SideEffect]
    all_deltas: dict[str, float | None]
    note: str


class PerturbationMetrics(BaseModel):
    base_seuid: str
    n_runs: int
    variants: list[VariantResult]


def _score_matrix(records: list[RunRecord]) -> dict[str, list[int | None]]:
    runs = sorted(records, key=lambda r: r.run_index)
    return {c: [r.criterion_scores.get(c) for r in runs] for c in CRITERIA_ORDER}


def compute_side_effects(
    base_matrix: dict[str, list[int | None]],
    pert_matrix: dict[str, list[int | None]],
    target_criteria: tuple[str, ...],
    coupling: tuple[str, ...],
    min_delta: float = 0.5,
) -> tuple[list[SideEffect], dict[str, float | None]]:
    effects: list[SideEffect] = []
    all_deltas: dict[str, float | None] = {}
    for c in CRITERIA_ORDER:
        b_mean, _, _ = _mean_range(base_matrix[c])
        p_mean, _, _ = _mean_range(pert_matrix[c])
        d = (
            round(p_mean - b_mean, 4)
            if (b_mean is not None and p_mean is not None)
            else None
        )
        all_deltas[c] = d
        if c in target_criteria or d is None or abs(d) < min_delta:
            continue
        cls = "expected_coupling" if c in coupling else "spurious"
        effects.append(SideEffect(criterion=c, delta=d, classification=cls))
    return effects, all_deltas


def _variant_note(verdicts: list[TargetVerdict], effects: list[SideEffect]) -> str:
    primary = verdicts[0]
    spurious = [e.criterion for e in effects if e.classification == "spurious"]
    note = f"{primary.criterion} {primary.verdict}"
    if primary.delta is not None:
        note += f" (delta {primary.delta:+.2f}, noise floor {primary.noise_floor:.2f})"
    if spurious:
        note += f"; side effect spuri: {', '.join(spurious)}"
    return note


def compute_perturbation_metrics(
    base_records: list[RunRecord],
    variant_records: dict[str, list[RunRecord]],
    perturbations: tuple[Perturbation, ...] = PERTURBATIONS,
    base_seuid: str = "",
    n_runs: int = 3,
) -> PerturbationMetrics:
    base_matrix = _score_matrix(base_records)
    results: list[VariantResult] = []
    for p in perturbations:
        pert_matrix = _score_matrix(variant_records[p.id])
        verdicts = [
            classify_verdict(c, base_matrix[c], pert_matrix[c], p.expected_direction)
            for c in p.target_criteria
        ]
        primary = p.target_criteria[0]
        passed = next(v.passed for v in verdicts if v.criterion == primary)
        effects, all_deltas = compute_side_effects(
            base_matrix, pert_matrix, p.target_criteria, p.plausible_coupling
        )
        results.append(VariantResult(
            variant_id=p.id, target_criteria=list(p.target_criteria),
            primary_target=primary, target_verdicts=verdicts, passed=passed,
            side_effects=effects, all_deltas=all_deltas,
            note=_variant_note(verdicts, effects),
        ))
    return PerturbationMetrics(
        base_seuid=base_seuid, n_runs=n_runs, variants=results
    )
