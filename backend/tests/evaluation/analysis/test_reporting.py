from app.evaluation.analysis.self_consistency import (
    CRITERIA_ORDER,
    RunRecord,
    compute_self_consistency,
)
from app.evaluation.analysis.reporting import (
    render_protocol_md,
    render_summary_md,
)


def _metrics():
    records = []
    for i in range(1, 6):
        records.append(RunRecord(
            seuid="S1", run_index=i, status="completed",
            criterion_scores={c: 2 for c in CRITERIA_ORDER},
            core_score=2.0, coverage=1.0,
        ))
    return compute_self_consistency(records)


def _manifest():
    return {
        "experiment": "self_consistency_v1",
        "datetime": "2026-06-20T18:00:00+00:00",
        "git": {"commit": "abc1234", "branch": "feature/self-consistency-experiment",
                "dirty": False},
        "n_runs_per_seuid": 5,
        "scientific_config": {
            "llm_model": "gemini-2.5-flash", "llm_temperature": 0.1,
            "llm_max_output_tokens": 8192, "embedding_model": "gemini-embedding-001",
            "embedding_output_dimensionality": 3072, "rag_top_k": 5,
            "rag_final_k": 3, "rag_similarity_threshold": 0.6,
        },
        "prompt_versions": {"A1": "a1_v5", "A2": "a2_v1", "A3": "a3_v1", "A4": "a4_v2"},
    }


SLUGS = {"S1": "01_COMPUTER_VISION_LAB"}


def test_protocol_md_records_config_and_caveats():
    md = render_protocol_md(_manifest(), _metrics(), SLUGS)
    assert "# Protocollo" in md
    assert "abc1234" in md           # git commit
    assert "gemini-2.5-flash" in md  # model
    assert "0.1" in md               # temperature (non-determinism source)
    assert "thinking" in md.lower()  # non-determinism note
    assert "a1_v5" in md             # prompt version
    # metrics use only structured fields, not report text:
    assert "report" in md.lower()


def test_summary_md_has_tables_and_narrative():
    md = render_summary_md(_metrics(), SLUGS)
    assert "# Risultati" in md
    assert "| Criterio |" in md
    assert "| C9 |" in md
    assert "CoreScore" in md
    assert "01_COMPUTER_VISION_LAB" in md


def test_criterion_stability_tex_is_booktabs():
    from app.evaluation.analysis.reporting import render_criterion_stability_tex
    tex = render_criterion_stability_tex(_metrics())
    assert r"\begin{tabularx}{\textwidth}" in tex
    assert r"\toprule" in tex and r"\midrule" in tex and r"\bottomrule" in tex
    assert r"\end{tabularx}" in tex
    assert "{Unanimità}" in tex          # braced siunitx header
    assert "C9 &" in tex
    # every C1..C9 row present
    for c in CRITERIA_ORDER:
        assert f"{c} &" in tex


def test_corescore_stability_tex_handles_slug_and_missing():
    from app.evaluation.analysis.reporting import render_corescore_stability_tex
    tex = render_corescore_stability_tex(_metrics(), SLUGS)
    assert r"\begin{tabularx}{\textwidth}" in tex
    assert "01\\_COMPUTER\\_VISION\\_LAB" in tex  # underscores escaped for LaTeX


def test_run_status_tex_present():
    from app.evaluation.analysis.reporting import render_run_status_tex
    tex = render_run_status_tex(_metrics())
    assert r"\begin{tabularx}{\textwidth}" in tex
    assert "completed" in tex
