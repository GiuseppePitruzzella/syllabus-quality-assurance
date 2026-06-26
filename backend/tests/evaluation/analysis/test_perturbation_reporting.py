from app.evaluation.analysis.perturbation import (
    PERTURBATIONS,
    PerturbationMetrics,
    SideEffect,
    TargetVerdict,
    VariantResult,
)
from app.evaluation.analysis.perturbation_reporting import (
    render_analysis_md,
    render_perturbation_deltas_tex,
    render_protocol_md,
    render_side_effects_tex,
    render_summary_md,
)


def _verdict(crit, delta, verdict, passed):
    return TargetVerdict(
        criterion=crit, base_mean=2.0, base_range=0.0, pert_mean=2.0 + delta,
        pert_range=0.0, delta=delta, expected_direction="decrease",
        noise_floor=0.0, verdict=verdict, passed=passed,
    )


def _metrics():
    vr = VariantResult(
        variant_id="C6_strip_assessment", target_criteria=["C6"],
        primary_target="C6", target_verdicts=[_verdict("C6", -2.0, "PASS", True)],
        passed=True,
        side_effects=[SideEffect(criterion="C8", delta=-0.5,
                                 classification="spurious")],
        all_deltas={"C6": -2.0, "C8": -0.5},
        note="C6 PASS (delta -2.00, noise floor 0.00); side effect spuri: C8",
    )
    return PerturbationMetrics(base_seuid="DL", n_runs=3, variants=[vr])


def _manifest():
    return {
        "experiment": "perturbation_sensitivity_v1",
        "datetime": "2026-06-26T00:00:00+00:00",
        "git": {"commit": "abc", "branch": "feature/x", "dirty": False},
        "base_seuid": "DL", "n_runs": 3,
        "scientific_config": {
            "llm_model": "gemini-2.5-flash", "llm_temperature": 0.2,
            "llm_max_output_tokens": 8192, "embedding_model": "gemini-embedding-001",
            "embedding_output_dimensionality": 1536, "rag_top_k": 10,
            "rag_final_k": 5, "rag_similarity_threshold": 0.5,
        },
        "prompt_versions": {"A1": "v7"},
    }


def test_summary_md_has_verdict_table():
    md = render_summary_md(_metrics())
    assert "C6_strip_assessment" in md
    assert "PASS" in md
    assert "-2.00" in md
    assert "PASS robusti" in md
    assert "**FAIL:** nessuno" in md


def test_protocol_md_lists_perturbations_and_caveats():
    md = render_protocol_md(_manifest(), _metrics(), PERTURBATIONS)
    assert "validità di costrutto" in md
    assert "english_coverage" in md   # C2 refinement note
    assert "C1" in md and "C7" in md  # coupling declaration
    assert "C5 e C9 partono da baseline 1" not in md
    assert "Tutti i bersagli partono dal massimo" in md


def test_protocol_md_reports_limited_headroom_from_metrics():
    metrics = _metrics()
    metrics.variants[0].target_verdicts[0].base_mean = 1.0
    md = render_protocol_md(_manifest(), metrics, PERTURBATIONS)
    assert "C6 (baseline 1, delta minimo osservabile -1)" in md


def test_analysis_md_distinguishes_construct_result_and_limit():
    md = render_analysis_md(_metrics())
    assert "validità di costrutto" in md
    assert "C7_remove_schedule" in md
    assert "C9_editorial_noise" in md
    assert "limite di sensibilità" in md


def test_deltas_tex_is_tabularx():
    tex = render_perturbation_deltas_tex(_metrics())
    assert r"\begin{tabularx}" in tex
    assert "C6" in tex


def test_side_effects_tex_renders_rows():
    tex = render_side_effects_tex(_metrics())
    assert r"\begin{tabularx}" in tex
    assert "C8" in tex
