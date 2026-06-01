"""Deterministic report synthesizer (Ipotesi A — no LLM).

Composes a Markdown report from an ``AggregatedResult`` plus the four
``AgentOutput``s. The function is pure, deterministic and easy to test:
no LLM calls, no I/O, no randomness.

Per the rubric (D016) the evaluation pipeline produces TWO outputs:
the structured JSON (``AggregatedResult`` + per-agent judgments) and
a human-readable Markdown report (this module). The report is the
artefact the teacher reads first; the JSON is the artefact the
experimental validation reads.

The CRITERION_RECOMMENDATIONS templates use soft normative wording
("considera", "valuta se", "puoi") rather than prescriptive verbs
("devi", "obbligato"), consistent with D025+D030 and the A1/C5
methodological retrofit on a1_v4.
"""
from __future__ import annotations

from app.evaluation.agents.schemas import AgentOutput
from app.evaluation.aggregator import (
    ALL_CORE_CRITERIA,
    AggregatedResult,
    NACriterionRecord,
)


# Human-readable criterion names used in the report.
CRITERION_NAMES: dict[str, str] = {
    "C1": "Completezza strutturale e documentale",
    "C2": "Completezza bilingue",
    "C3": "Formulazione dei risultati di apprendimento",
    "C4": "Articolazione secondo i Descrittori di Dublino",
    "C5": "Chiarezza dei prerequisiti",
    "C6": "Modalità di verifica dell'apprendimento",
    "C7": "Chiarezza dei contenuti del corso",
    "C8": "Coerenza didattico-valutativa",
    "C9": "Cura editoriale del syllabus",
}

# Soft recommendations templated per criterion, used in the
# "Aree di miglioramento" section when a criterion scores 0 or 1.
# Wording is intentionally non-prescriptive: the LG UniCT raccomandano,
# non impongono (see D030 and the a1_v4 retrofit). Recommendations
# point the teacher at what to look at, not at what they must do.
CRITERION_RECOMMENDATIONS: dict[str, str] = {
    "C1": (
        "Considera di verificare che tutte e nove le sezioni obbligatorie "
        "(RA, PR, CN, MV, ED, TD, MS, MF, PRG) siano compilate con contenuto "
        "sostanziale, non solo come intestazione."
    ),
    "C2": (
        "Valuta se il perimetro minimo bilingue (titolo, risultati di "
        "apprendimento, contenuti, modalità di verifica) sia coperto anche "
        "in lingua inglese."
    ),
    "C3": (
        "Considera di riformulare i risultati di apprendimento in termini "
        "di conoscenze e abilità osservabili dello studente, evitando "
        "formulazioni che descrivono il corso ('il corso copre...') o "
        "espressioni generiche ('lo studente acquisirà conoscenze')."
    ),
    "C4": (
        "Valuta se ciascuno dei cinque Descrittori di Dublino sia "
        "articolato con contenuti specifici e differenziati; le Linee "
        "Guida UniCT raccomandano una formulazione esplicita per ciascun "
        "descrittore."
    ),
    "C5": (
        "Considera di rendere i prerequisiti più specifici (conoscenze e "
        "abilità, non solo codici di esami). Le Linee Guida UniCT "
        "raccomandano, quando applicabile, di esplicitare la gradazione "
        "(utili / importanti / indispensabili) e la distinzione fra "
        "propedeuticità culturali e formali."
    ),
    "C6": (
        "Considera di esplicitare criteri di attribuzione del voto e/o "
        "esempi di domande pertinenti agli obiettivi del corso. Le LG "
        "UniCT raccomandano questa esplicitazione come parte della "
        "trasparenza della verifica."
    ),
    "C7": (
        "Valuta se i contenuti possano essere organizzati con una "
        "scansione tematica più chiara (sezioni, progressione, schedule "
        "per lezioni), in modo che lo studente possa orientarsi rapidamente."
    ),
    "C8": (
        "Considera di verificare l'allineamento fra risultati di "
        "apprendimento, metodi didattici, contenuti e modalità di "
        "verifica: ogni risultato dichiarato dovrebbe essere "
        "ricostruibile dalla combinazione di contenuti, didattica e "
        "valutazione."
    ),
    "C9": (
        "Considera una rilettura editoriale del syllabus per refusi, "
        "incongruenze interne fra sezioni, completezza dei riferimenti "
        "bibliografici e residui di formattazione."
    ),
}


# Fixed methodological note that closes every report. References D001
# (system as support, not substitute) and the ongoing parser-residue
# investigation (ISSUE-PARSER-001/002/003 in PROGRESS.md).
_METHOD_NOTE = (
    "## Note metodologiche\n"
    "\n"
    "Il sistema è uno strumento di supporto alla valutazione e "
    "all'autovalutazione del syllabus, non un sostituto del giudizio "
    "del docente o degli organi di Assicurazione della Qualità.\n"
    "\n"
    "Le evidenze citate e i giudizi prodotti vanno verificati sul "
    "syllabus originale: il sistema lavora su dati estratti tramite "
    "scraping e parsing, e residui di estrazione (refusi apparenti, "
    "interruzioni di parola anomale, marker di template) possono "
    "essere artefatti dell'estrazione e non difetti del documento "
    "redatto dal docente.\n"
)


def synthesize_report(
    course_name: str,
    aggregation: AggregatedResult,
    agent_outputs: dict[str, AgentOutput | None],
) -> str:
    """Build a Markdown report from the aggregation and the agent outputs.

    Pure function: same inputs → same output. No LLM, no I/O.

    Args:
        course_name: Display name of the course, used in the report title.
        aggregation: The structured aggregation produced by
            :func:`app.evaluation.aggregator.aggregate`.
        agent_outputs: Map ``agent_code → AgentOutput | None`` produced
            by the orchestrator. Used to look up per-criterion
            full justifications for both the "Punti di forza" and the
            "Aree di miglioramento" sections.

    Returns:
        A Markdown string ready to be persisted in
        ``EvaluationResult.final_report`` (Phase 5.4.H).
    """
    judgments_by_code = _index_judgments(agent_outputs)

    parts: list[str] = []
    parts.append(_render_title(course_name))
    parts.append(_render_synthesis(aggregation))
    parts.append(_render_strengths(aggregation, judgments_by_code))
    parts.append(_render_improvements(aggregation, judgments_by_code))
    parts.append(_render_partial_failed_note(aggregation))
    parts.append(_METHOD_NOTE)
    # Drop empty sections (those return "" for the cases that don't apply).
    return "\n".join(p for p in parts if p).rstrip() + "\n"


# === internals ==============================================================


def _index_judgments(
    agent_outputs: dict[str, AgentOutput | None],
) -> dict[str, dict]:
    """Return a ``{criterion_code: {justification, evidences, ...}}`` map.

    Skips agents that did not produce output (None) or returned no
    judgments. Out-of-scope judgments from an agent (if any survived
    the agent_outputs validator) are also indexed: the synthesizer
    just walks ``aggregation.criterion_scores`` and picks what it
    finds, so a stray code does not change the report.
    """
    indexed: dict[str, dict] = {}
    for output in agent_outputs.values():
        if output is None:
            continue
        for judgment in output.judgments:
            indexed[judgment.criterion_code] = {
                "score": judgment.score,
                "is_na": judgment.is_na,
                "na_reason": judgment.na_reason,
                "justification": judgment.justification,
                "evidences": judgment.evidences,
                "confidence": judgment.confidence,
            }
    return indexed


def _render_title(course_name: str) -> str:
    return f"# Report di valutazione — {course_name}\n"


def _render_synthesis(aggregation: AggregatedResult) -> str:
    core = aggregation.core_score
    coverage = aggregation.coverage
    n_eval = sum(1 for v in aggregation.criterion_scores.values() if v is not None)
    n_total = len(aggregation.criterion_scores)
    core_str = "—" if core is None else f"{core:.2f}/2.00"

    lines = [
        "## Sintesi",
        "",
        f"- **CoreScore**: {core_str}",
        f"- **Copertura**: {coverage:.0%} ({n_eval}/{n_total} criteri valutati)",
        f"- **Stato**: {aggregation.status}",
        "",
    ]

    # Narrative paragraph that contextualises the score.
    if core is None:
        lines.append(
            "Nessun criterio del nucleo C1–C9 è risultato valutabile: "
            "consulta le note metodologiche per i dettagli sui criteri "
            "non valutati."
        )
    elif aggregation.status == "completed":
        lines.append(
            f"La valutazione è completa: tutti i {n_eval} criteri valutati "
            "dispongono di un punteggio motivato. Il CoreScore è la media "
            "aritmetica dei punteggi sulla scala 0/1/2 (D017)."
        )
    elif aggregation.status == "partial":
        lines.append(
            f"La valutazione è parziale: {n_eval} criteri su {n_total} hanno "
            "ricevuto un punteggio. I criteri non valutati sono elencati "
            "nelle note metodologiche con la rispettiva motivazione."
        )
    # status == "failed" is handled by _render_partial_failed_note + the
    # core_score is None branch above.
    return "\n".join(lines) + "\n"


def _render_strengths(
    aggregation: AggregatedResult, judgments_by_code: dict[str, dict]
) -> str:
    strengths = [
        (code, score)
        for code, score in aggregation.criterion_scores.items()
        if score == 2
    ]
    if not strengths:
        return ""
    lines = ["## Punti di forza", ""]
    # Preserve C1..C9 order, not the dict iteration order.
    strengths_sorted = sorted(strengths, key=lambda pair: ALL_CORE_CRITERIA.index(pair[0]))
    for code, _ in strengths_sorted:
        name = CRITERION_NAMES.get(code, code)
        j = judgments_by_code.get(code, {})
        just = _normalize_inline(j.get("justification", ""))
        lines.append(f"- **{code} — {name}** (score 2): {just}")
    return "\n".join(lines) + "\n"


def _render_improvements(
    aggregation: AggregatedResult, judgments_by_code: dict[str, dict]
) -> str:
    weaknesses = [
        (code, score)
        for code, score in aggregation.criterion_scores.items()
        if score is not None and score < 2
    ]
    if not weaknesses:
        return ""
    lines = ["## Aree di miglioramento", ""]
    weaknesses_sorted = sorted(weaknesses, key=lambda pair: ALL_CORE_CRITERIA.index(pair[0]))
    for code, score in weaknesses_sorted:
        name = CRITERION_NAMES.get(code, code)
        j = judgments_by_code.get(code, {})
        just = _normalize_inline(j.get("justification", ""))
        recommendation = CRITERION_RECOMMENDATIONS.get(code, "")
        lines.append(f"- **{code} — {name}** (score {score}): {just}")
        if recommendation:
            lines.append(f"  - *Raccomandazione*: {recommendation}")
    return "\n".join(lines) + "\n"


def _render_partial_failed_note(aggregation: AggregatedResult) -> str:
    if aggregation.status == "completed" and not aggregation.na_criteria:
        return ""
    lines = ["## Criteri non valutati"]
    if aggregation.status == "failed":
        lines.append("")
        lines.append(
            "Tutti gli agenti specialistici hanno incontrato un errore: il "
            "sistema non è stato in grado di produrre alcun punteggio per "
            "questo syllabus."
        )
    if aggregation.na_criteria:
        lines.append("")
        for record in sorted(
            aggregation.na_criteria,
            key=lambda r: ALL_CORE_CRITERIA.index(r.criterion_code),
        ):
            lines.append(_format_na_record(record))
    return "\n".join(lines) + "\n"


def _format_na_record(record: NACriterionRecord) -> str:
    name = CRITERION_NAMES.get(record.criterion_code, record.criterion_code)
    source_labels = {
        "agent": "NA esplicito dell'agente",
        "agent_error": "NA tecnico (errore agente)",
        "technical": "NA tecnico",
    }
    label = source_labels.get(record.source, record.source)
    return f"- **{record.criterion_code} — {name}** ({label}): {record.reason}"


def _normalize_inline(text: str) -> str:
    """Collapse whitespace while preserving the full justification text.

    The first report synthesizer capped justifications at ~420 chars to
    keep the Markdown compact. In the frontend this read as a broken /
    truncated report, especially because the UI already offers tabs and
    scrollable space. We now keep the full agent justification and let
    the renderer handle wrapping.
    """
    if not text:
        return ""
    return " ".join(text.split())
