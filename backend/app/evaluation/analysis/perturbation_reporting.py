"""Deterministic renderers for the perturbation experiment.

Pure string functions. No LLM, no I/O. Reuses the thesis LaTeX helpers
(_tex_escape / _tabularx) from the self-consistency reporter.
"""
from __future__ import annotations

from app.evaluation.analysis.perturbation import Perturbation, PerturbationMetrics
from app.evaluation.analysis.reporting import _tabularx, _tex_escape


def render_protocol_md(
    manifest: dict, metrics: PerturbationMetrics,
    perturbations: tuple[Perturbation, ...],
) -> str:
    sci = manifest["scientific_config"]
    git = manifest["git"]
    pert_lines = [
        f"- **{p.id}** → bersaglio {', '.join(p.target_criteria)}; "
        f"coupling plausibile: {', '.join(p.plausible_coupling) or '—'}; {p.description}"
        for p in perturbations
    ]
    lines = [
        "# Protocollo — Perturbation / Sensitivity Test",
        "",
        f"- Data esecuzione: {manifest['datetime']}",
        f"- Git commit: `{git['commit']}` (branch `{git['branch']}`, "
        f"dirty: {'sì' if git['dirty'] else 'no'})",
        f"- Esperimento: {manifest['experiment']}",
        f"- Syllabus base (seuid): `{manifest['base_seuid']}`",
        f"- Run per condizione (N): {manifest['n_runs']} "
        f"(1 base + {len(perturbations)} varianti = "
        f"{(1 + len(perturbations)) * manifest['n_runs']} run totali)",
        "",
        "## Scopo",
        "",
        "Questo test dimostra la **validità di costrutto / sensibilità "
        "direzionale** del sistema: a fronte di una perturbazione controllata "
        "che degrada un singolo aspetto, il criterio bersaglio deve peggiorare. "
        "**Non** misura accordo umano e **non** sostituisce Phase 5.8; complementa "
        "la self-consistency (di cui riusa il rumore run-to-run come noise floor).",
        "",
        "## Configurazione scientifica (di produzione)",
        "",
        f"- Modello LLM: {sci['llm_model']} (temperatura {sci['llm_temperature']})",
        f"- Embedding: {sci['embedding_model']} "
        f"(dim {sci['embedding_output_dimensionality']})",
        f"- RAG top_k/final_k/soglia: {sci['rag_top_k']}/{sci['rag_final_k']}/"
        f"{sci['rag_similarity_threshold']}",
        f"- Versioni prompt: {manifest['prompt_versions']}",
        "",
        "## Perturbazioni",
        "",
        *pert_lines,
        "",
        "## Definizione del verdetto",
        "",
        "Per il criterio bersaglio: `delta = media(variante) − media(base)`; "
        "`noise_floor = range delle 3 run base`. "
        "**PASS** = direzione corretta, `|delta| ≥ 0.5` e `|delta| > noise_floor`; "
        "**WEAK** = direzione corretta e `|delta| ≥ 0.5` ma entro il rumore della base; "
        "**FAIL** = direzione sbagliata o `|delta| < 0.5`. "
        "NA non è 0: `TARGET_BECAME_NA` e `insufficient_base_data` sono esiti distinti.",
        "",
        "## Note metodologiche (refinement)",
        "",
        "- **C1**: rimuovere sezioni obbligatorie non è mai isolato → coupling "
        "plausibile dichiarato con C7/C8/C9.",
        "- **C2**: oggi guidato dal pre-check deterministico `english_coverage`; "
        "atteso comportamento molto stabile (un calo netto conferma la correzione C2).",
        "- **C5**: perturbazione chiaramente negativa ('Prerequisiti non indicati'), "
        "non 'Nessun prerequisito' (interpretabile come informazione legittima).",
        "",
        "## Caveat",
        "",
        "- N piccolo (3/condizione); perturbazioni sintetiche; singola base "
        "(LM-18 Deep Learning) → generalizzabilità limitata.",
        "- C5 e C9 partono da baseline 1 → delta massimo osservabile −1.",
        "",
    ]
    return "\n".join(lines) + "\n"


def render_summary_md(metrics: PerturbationMetrics) -> str:
    rows = []
    for vr in metrics.variants:
        for tv in vr.target_verdicts:
            se = ", ".join(
                f"{e.criterion}({e.delta:+.1f},{e.classification[:4]})"
                for e in vr.side_effects
            ) or "—"
            rows.append(
                f"| {vr.variant_id} | {tv.criterion} "
                f"| {tv.base_mean if tv.base_mean is not None else '—'} "
                f"| {tv.pert_mean if tv.pert_mean is not None else '—'} "
                f"| {('%+.2f' % tv.delta) if tv.delta is not None else '—'} "
                f"| {tv.expected_direction} | {tv.verdict} | {se} |"
            )
    n_pass = sum(1 for v in metrics.variants if v.passed)
    lines = [
        "# Risultati — Perturbation / Sensitivity Test",
        "",
        f"Base `{metrics.base_seuid}`, N={metrics.n_runs} run/condizione. "
        f"Varianti che superano (PASS robusto sul bersaglio primario): "
        f"{n_pass}/{len(metrics.variants)}.",
        "",
        "| Variante | Bersaglio | Base | Perturbato | Delta | Atteso | Verdict "
        "| Side effects |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- |",
        *rows,
        "",
        "Legenda verdict: PASS = sensibilità robusta (oltre il rumore della base); "
        "WEAK = direzione corretta ma entro il rumore; FAIL = nessun calo significativo.",
        "",
    ]
    return "\n".join(lines) + "\n"


def render_perturbation_deltas_tex(metrics: PerturbationMetrics) -> str:
    colspec = (
        "l l S[table-format=1.2] S[table-format=1.2] "
        "S[table-format=+1.2] l"
    )
    header = "Variante & Crit. & {Base} & {Pert.} & {Delta} & Verdict"

    def _num(v):
        return f"{v:.2f}" if v is not None else "{--}"

    rows = []
    for vr in metrics.variants:
        for tv in vr.target_verdicts:
            delta = f"{tv.delta:+.2f}" if tv.delta is not None else "{--}"
            rows.append(
                f"{_tex_escape(vr.variant_id)} & {tv.criterion} & "
                f"{_num(tv.base_mean)} & {_num(tv.pert_mean)} & {delta} & {tv.verdict}"
            )
    return _tabularx(colspec, header, rows)


def render_side_effects_tex(metrics: PerturbationMetrics) -> str:
    colspec = "l l S[table-format=+1.2] l"
    header = "Variante & Crit. & {Delta} & Classificazione"
    rows = [
        f"{_tex_escape(vr.variant_id)} & {e.criterion} & {e.delta:+.2f} "
        f"& {e.classification}"
        for vr in metrics.variants for e in vr.side_effects
    ]
    if not rows:
        rows = ["{--} & {--} & {--} & nessun side effect"]
    return _tabularx(colspec, header, rows)
