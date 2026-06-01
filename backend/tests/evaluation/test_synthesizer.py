"""Tests for the deterministic report synthesizer (Ipotesi A, no LLM)."""
from __future__ import annotations

from app.evaluation.agents.schemas import (
    AgentOutput,
    CriterionEvidence,
    CriterionJudgment,
)
from app.evaluation.aggregator import (
    AggregatedResult,
    NACriterionRecord,
    aggregate,
)
from app.evaluation.synthesizer import (
    CRITERION_NAMES,
    CRITERION_RECOMMENDATIONS,
    synthesize_report,
)


def _judgment(code: str, *, score: int | None = None, is_na: bool = False,
              na_reason: str | None = None, justification: str | None = None,
              ) -> CriterionJudgment:
    return CriterionJudgment(
        criterion_code=code,
        score=score,
        is_na=is_na,
        na_reason=na_reason,
        justification=justification or f"Giudizio sintetico per {code} (lunghezza minima rispettata).",
        evidences=[
            CriterionEvidence(text=f"evidenza-{code}", source_field="course_content_it")
        ],
        confidence="medium",
    )


def _output(agent_code: str, *judgments: CriterionJudgment) -> AgentOutput:
    return AgentOutput(agent_code=agent_code, judgments=list(judgments), execution_metadata={})


def _all_outputs_mixed() -> dict[str, AgentOutput]:
    """A realistic mixed run: some 2s, some 1s, one 0."""
    return {
        "A1": _output(
            "A1",
            _judgment("C1", score=2),
            _judgment("C2", score=1),
            _judgment("C5", score=1),
        ),
        "A2": _output(
            "A2",
            _judgment("C3", score=2),
            _judgment("C4", score=2),
        ),
        "A3": _output(
            "A3",
            _judgment("C6", score=2),
            _judgment("C7", score=2),
            _judgment("C8", score=2),
        ),
        "A4": _output("A4", _judgment("C9", score=0)),
    }


# ---------------------------------------------------------------------------
# Smoke / structure
# ---------------------------------------------------------------------------


def test_report_starts_with_course_title():
    outputs = _all_outputs_mixed()
    agg = aggregate(outputs, {})
    report = synthesize_report("Deep Learning", agg, outputs)
    assert report.startswith("# Report di valutazione — Deep Learning")


def test_report_contains_all_main_sections_when_mixed_scores():
    outputs = _all_outputs_mixed()
    agg = aggregate(outputs, {})
    report = synthesize_report("Course X", agg, outputs)
    assert "## Sintesi" in report
    assert "## Punti di forza" in report
    assert "## Aree di miglioramento" in report
    assert "## Note metodologiche" in report


def test_report_shows_core_score_and_coverage_in_sintesi():
    outputs = _all_outputs_mixed()
    agg = aggregate(outputs, {})
    report = synthesize_report("X", agg, outputs)
    # core_score is mean of [2,1,1,2,2,2,2,2,0] = 14/9 = 1.555… -> 1.56
    assert "1.56/2.00" in report
    assert "9/9 criteri valutati" in report


def test_report_lists_strengths_in_c1_to_c9_order():
    outputs = _all_outputs_mixed()
    agg = aggregate(outputs, {})
    report = synthesize_report("X", agg, outputs)
    # Strengths: C1, C3, C4, C6, C7, C8 (all 2s). C9 is 0 -> in improvements.
    strengths_block = report.split("## Punti di forza")[1].split("## Aree")[0]
    positions = [strengths_block.find(f"**{c}") for c in ("C1", "C3", "C4", "C6", "C7", "C8")]
    assert all(p > 0 for p in positions), positions
    assert positions == sorted(positions)


def test_report_lists_weaknesses_with_recommendations():
    outputs = _all_outputs_mixed()
    agg = aggregate(outputs, {})
    report = synthesize_report("X", agg, outputs)
    weaknesses = report.split("## Aree di miglioramento")[1].split("## ")[0]
    # C2 and C5 are 1s, C9 is a 0.
    assert "**C2 — " in weaknesses
    assert "**C5 — " in weaknesses
    assert "**C9 — " in weaknesses
    # Each weakness must carry its recommendation.
    assert "*Raccomandazione*" in weaknesses
    assert CRITERION_RECOMMENDATIONS["C2"][:30] in weaknesses
    assert CRITERION_RECOMMENDATIONS["C9"][:30] in weaknesses


def test_report_uses_soft_normative_wording_in_recommendations():
    """Recommendations must avoid prescriptive verbs like 'devi' / 'obbligato'.

    Note: 'obbligatorie' (e.g. 'sezioni obbligatorie') is part of the
    rubric vocabulary itself and is acceptable; we only ban the
    second-person prescriptive forms 'devi' / 'obbligato' / 'obbligatoriamente'.
    """
    forbidden_phrases = (" devi ", " obbligato ", " obbligatoriamente ", "obbligatoriamente.")
    for code, rec in CRITERION_RECOMMENDATIONS.items():
        # Pad with spaces so substring search doesn't false-positive on
        # 'obbligatorie' / 'obbligatorio' (legitimate rubric vocabulary).
        padded = f" {rec.lower()} "
        for phrase in forbidden_phrases:
            assert phrase not in padded, f"{code} uses prescriptive '{phrase.strip()}'"


def test_report_always_includes_fixed_methodological_note():
    outputs = _all_outputs_mixed()
    agg = aggregate(outputs, {})
    report = synthesize_report("X", agg, outputs)
    # D001 phrasing + parser caveat must always be present.
    assert "supporto alla valutazione" in report
    assert "sostituto del giudizio del docente" in report
    assert "scraping" in report or "parsing" in report


# ---------------------------------------------------------------------------
# Edge cases: empty strengths, NA-only, failed status
# ---------------------------------------------------------------------------


def test_report_omits_strengths_section_when_no_score_two():
    outputs = {
        "A1": _output("A1", _judgment("C1", score=1), _judgment("C2", score=1), _judgment("C5", score=1)),
        "A2": _output("A2", _judgment("C3", score=1), _judgment("C4", score=1)),
        "A3": _output("A3", _judgment("C6", score=1), _judgment("C7", score=1), _judgment("C8", score=1)),
        "A4": _output("A4", _judgment("C9", score=1)),
    }
    agg = aggregate(outputs, {})
    report = synthesize_report("X", agg, outputs)
    assert "## Punti di forza" not in report
    assert "## Aree di miglioramento" in report


def test_report_omits_improvements_section_when_all_twos():
    outputs = {
        "A1": _output("A1", _judgment("C1", score=2), _judgment("C2", score=2), _judgment("C5", score=2)),
        "A2": _output("A2", _judgment("C3", score=2), _judgment("C4", score=2)),
        "A3": _output("A3", _judgment("C6", score=2), _judgment("C7", score=2), _judgment("C8", score=2)),
        "A4": _output("A4", _judgment("C9", score=2)),
    }
    agg = aggregate(outputs, {})
    report = synthesize_report("X", agg, outputs)
    assert "## Punti di forza" in report
    assert "## Aree di miglioramento" not in report


def test_report_renders_failed_status_block():
    agg = aggregate({}, {"A1": "Boom", "A2": "Boom", "A3": "Boom", "A4": "Boom"})
    report = synthesize_report("X", agg, {})
    assert agg.status == "failed"
    assert "Tutti gli agenti specialistici hanno incontrato un errore" in report
    # CoreScore must be rendered as "—".
    assert "—" in report
    # And we must NOT show a Punti di forza or Aree di miglioramento section
    # (no scored criterion exists).
    assert "## Punti di forza" not in report
    assert "## Aree di miglioramento" not in report


def test_report_renders_partial_with_agent_error_na_records():
    outputs = {
        "A1": _output("A1", _judgment("C1", score=2), _judgment("C2", score=1), _judgment("C5", score=2)),
        "A2": None,
        "A3": _output("A3", _judgment("C6", score=2), _judgment("C7", score=2), _judgment("C8", score=2)),
        "A4": _output("A4", _judgment("C9", score=1)),
    }
    errors = {"A2": "LLMSafetyBlockedError: SAFETY"}
    agg = aggregate(outputs, errors)
    report = synthesize_report("X", agg, outputs)
    assert agg.status == "partial"
    # Criteri non valutati block must mention C3 and C4 with NA tecnico.
    nv_block = report.split("## Criteri non valutati")[1].split("## ")[0]
    assert "C3" in nv_block and "C4" in nv_block
    assert "NA tecnico" in nv_block
    assert "SAFETY" in nv_block


def test_report_renders_agent_explicit_na_record():
    outputs = {
        "A1": _output(
            "A1",
            _judgment("C1", score=2),
            _judgment(
                "C2",
                score=None,
                is_na=True,
                na_reason="campi inglesi non recuperati dal parser",
            ),
            _judgment("C5", score=2),
        ),
        "A2": _output("A2", _judgment("C3", score=2), _judgment("C4", score=2)),
        "A3": _output("A3", _judgment("C6", score=2), _judgment("C7", score=2), _judgment("C8", score=2)),
        "A4": _output("A4", _judgment("C9", score=2)),
    }
    agg = aggregate(outputs, {})
    report = synthesize_report("X", agg, outputs)
    nv_block = report.split("## Criteri non valutati")[1].split("## ")[0]
    assert "C2" in nv_block
    assert "NA esplicito dell'agente" in nv_block
    assert "parser" in nv_block


# ---------------------------------------------------------------------------
# Full justification & coverage sanity
# ---------------------------------------------------------------------------


def test_long_justifications_are_preserved_in_report():
    long_just = "ABCDEFGHIJ" * 100  # 1000 chars
    outputs = {
        "A1": _output(
            "A1",
            _judgment("C1", score=2, justification=long_just),
            _judgment("C2", score=2),
            _judgment("C5", score=2),
        ),
        "A2": _output("A2", _judgment("C3", score=2), _judgment("C4", score=2)),
        "A3": _output("A3", _judgment("C6", score=2), _judgment("C7", score=2), _judgment("C8", score=2)),
        "A4": _output("A4", _judgment("C9", score=2)),
    }
    agg = aggregate(outputs, {})
    report = synthesize_report("X", agg, outputs)
    assert long_just in report


def test_criterion_names_cover_c1_to_c9():
    assert set(CRITERION_NAMES.keys()) == set(f"C{i}" for i in range(1, 10))


def test_criterion_recommendations_cover_c1_to_c9():
    assert set(CRITERION_RECOMMENDATIONS.keys()) == set(f"C{i}" for i in range(1, 10))


# ---------------------------------------------------------------------------
# Deterministic output
# ---------------------------------------------------------------------------


def test_synthesize_report_is_deterministic():
    outputs = _all_outputs_mixed()
    agg = aggregate(outputs, {})
    report_a = synthesize_report("Course", agg, outputs)
    report_b = synthesize_report("Course", agg, outputs)
    assert report_a == report_b


# ---------------------------------------------------------------------------
# Boundary: standalone AggregatedResult (no agents)
# ---------------------------------------------------------------------------


def test_synthesize_report_accepts_aggregation_without_corresponding_outputs():
    """If agent_outputs is empty but aggregation has scores from elsewhere,
    the report still renders (justifications will simply be missing)."""
    agg = AggregatedResult(
        criterion_scores=dict.fromkeys((f"C{i}" for i in range(1, 10)), 2),
        core_score=2.0,
        coverage=1.0,
        na_criteria=[],
        status="completed",
        agent_statuses={"A1": "ok", "A2": "ok", "A3": "ok", "A4": "ok"},
    )
    report = synthesize_report("X", agg, {})
    assert "## Punti di forza" in report
    # Per-criterion bullets should still be present, with empty justification.
    for code in (f"C{i}" for i in range(1, 10)):
        assert f"**{code} —" in report


def test_na_record_can_have_technical_source():
    """The NA record with source='technical' is rendered with a generic label."""
    agg = AggregatedResult(
        criterion_scores={**dict.fromkeys((f"C{i}" for i in range(1, 10)), 2), "C5": None},
        core_score=2.0,
        coverage=8 / 9,
        na_criteria=[
            NACriterionRecord(
                criterion_code="C5",
                reason="payload malformato",
                source="technical",
            )
        ],
        status="completed",
        agent_statuses={"A1": "ok", "A2": "ok", "A3": "ok", "A4": "ok"},
    )
    report = synthesize_report("X", agg, {})
    assert "C5" in report
    assert "NA tecnico" in report
    assert "payload malformato" in report
