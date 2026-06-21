"""Deterministic renderers: Markdown protocol/summary + LaTeX tables.

Pure string functions. No LLM, no I/O. The runner writes the returned
strings to disk. Tables target the thesis/ conventions (booktabs +
siunitx S-columns inside tabularx).
"""
from __future__ import annotations

from app.evaluation.analysis.self_consistency import (
    CRITERIA_ORDER,
    SelfConsistencyMetrics,
)


def render_protocol_md(
    manifest: dict, metrics: SelfConsistencyMetrics, slug_map: dict[str, str]
) -> str:
    sci = manifest["scientific_config"]
    git = manifest["git"]
    sample_lines = [
        f"- `{seuid}` — {slug_map.get(seuid, '(custom)')}"
        for seuid in metrics.n_runs_per_seuid
    ]
    prompt_lines = [f"  - {k}: {v}" for k, v in sorted(manifest["prompt_versions"].items())]
    lines = [
        "# Protocollo — Esperimento test-retest / self-consistency",
        "",
        f"- Data esecuzione: {manifest['datetime']}",
        f"- Git commit: `{git['commit']}` (branch `{git['branch']}`, "
        f"dirty: {'sì' if git['dirty'] else 'no'})",
        f"- Esperimento: {manifest['experiment']}",
        f"- Ripetizioni per syllabus (N): {manifest['n_runs_per_seuid']}",
        "",
        "## Configurazione scientifica (di produzione)",
        "",
        f"- Modello LLM: {sci['llm_model']}",
        f"- Temperatura LLM: {sci['llm_temperature']}",
        f"- Max output tokens: {sci['llm_max_output_tokens']}",
        f"- Modello embedding: {sci['embedding_model']} "
        f"(dim {sci['embedding_output_dimensionality']})",
        f"- RAG top_k/final_k/soglia: {sci['rag_top_k']}/{sci['rag_final_k']}/"
        f"{sci['rag_similarity_threshold']}",
        "- Versioni prompt:",
        *prompt_lines,
        "",
        "## Campione",
        "",
        *sample_lines,
        "",
        "## Fonte di non-determinismo",
        "",
        "Le run sono eseguite a parità di input e configurazione. La variabilità "
        "run-to-run deriva dalla stocasticità del modello generativo "
        f"({sci['llm_model']}) alla temperatura di produzione "
        f"({sci['llm_temperature']}) e dal *thinking* abilitato di default in "
        "Gemini 2.5 Flash.",
        "",
        "## Metriche",
        "",
        "Il grafo è eseguito **come in produzione** (inclusa la sintesi del "
        "report testuale), ma le metriche di self-consistency usano **solo** "
        "campi strutturati: punteggi C1–C9, stato NA, CoreScore, coverage, "
        "status e agent_errors. Il **testo** del report/justification non entra "
        "in alcuna metrica.",
        "",
        "Definizioni (per coppia syllabus×criterio, su N run):",
        "",
        "- **accordo modale** = conteggio(moda) / N, con NA come categoria distinta;",
        "- **unanime** = tutte le N run uguali e non-NA;",
        "- **range** e **deviazione standard** (di popolazione) sui soli valori numerici;",
        "- **NA-flip** = criterio NA in alcune run e valutato in altre.",
        "",
        "Aggregati per criterio: tasso di unanimità, stdev media intra-item, "
        "flip rate = media di (1 − accordo modale), swing massimo, incidenza NA-flip. "
        "CoreScore: stdev e range per syllabus, più stdev media e swing massimo aggregati.",
        "",
    ]
    return "\n".join(lines) + "\n"


def render_summary_md(
    metrics: SelfConsistencyMetrics, slug_map: dict[str, str]
) -> str:
    by_crit = {ca.criterion: ca for ca in metrics.criterion_aggregates}

    most_stable = max(metrics.criterion_aggregates, key=lambda c: c.unanimity_rate)
    least_stable = min(metrics.criterion_aggregates, key=lambda c: c.unanimity_rate)

    crit_rows = [
        f"| {c} | {by_crit[c].unanimity_rate:.2f} | {by_crit[c].mean_stdev:.2f} "
        f"| {by_crit[c].flip_rate:.2f} | {by_crit[c].max_swing} "
        f"| {by_crit[c].na_flip_count} |"
        for c in CRITERIA_ORDER
    ]
    cs_rows = [
        f"| {slug_map.get(it.seuid, it.seuid)} "
        f"| {('%.2f' % it.mean) if it.mean is not None else '—'} "
        f"| {('%.2f' % it.stdev) if it.stdev is not None else '—'} "
        f"| {('%.2f' % it.score_range) if it.score_range is not None else '—'} |"
        for it in metrics.corescore_items
    ]
    rs = metrics.run_status
    lines = [
        "# Risultati — Self-consistency (test-retest)",
        "",
        f"Campione: {metrics.n_seuids} syllabi × N run. "
        f"Run totali: {rs.total} (completed {rs.completed}, partial {rs.partial}, "
        f"failed {rs.failed}; run con agent_errors: {rs.agent_error_incidence}).",
        "",
        f"Criterio più stabile: **{most_stable.criterion}** "
        f"(unanimità {most_stable.unanimity_rate:.2f}). "
        f"Criterio meno stabile: **{least_stable.criterion}** "
        f"(unanimità {least_stable.unanimity_rate:.2f}).",
        "",
        "## Stabilità per criterio",
        "",
        "| Criterio | Unanimità | Stdev media | Flip rate | Swing max | NA-flip |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        *crit_rows,
        "",
        "## Stabilità del CoreScore per syllabus",
        "",
        "| Syllabus | CoreScore medio | Stdev | Range |",
        "| --- | ---: | ---: | ---: |",
        *cs_rows,
        "",
        f"CoreScore: stdev media {metrics.corescore_aggregate.mean_stdev:.2f}, "
        f"swing massimo {metrics.corescore_aggregate.max_swing:.2f}.",
        "",
        "## Caveat",
        "",
        "- Campione ridotto (N e numero di syllabi limitati): le metriche sono "
        "descrittive, non inferenziali.",
        "- La variabilità è misurata alla temperatura di produzione; un setting "
        "diverso (es. temperatura 0) darebbe stabilità diversa.",
        "",
    ]
    return "\n".join(lines) + "\n"
