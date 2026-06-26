from app.evaluation.analysis.human_comparability import (
    AUDIT,
    audit_payload,
    criteria_for_tier,
    render_audit_markdown,
)


def test_audit_covers_each_core_criterion_once():
    assert [item.criterion for item in AUDIT] == [f"C{i}" for i in range(1, 10)]


def test_analysis_tiers_separate_primary_secondary_and_excluded():
    assert criteria_for_tier("primary") == ["C1", "C3", "C4", "C5", "C6"]
    assert criteria_for_tier("secondary") == ["C2", "C7", "C8", "C9"]
    assert criteria_for_tier("excluded") == []


def test_payload_anchors_comparison_to_historical_prompt_versions():
    payload = audit_payload()

    assert payload["system_prompt_versions"] == {
        "A1": "a1_v5",
        "A2": "a2_v1",
        "A3": "a3_v1",
        "A4": "a4_v2",
    }
    c5 = next(item for item in payload["criteria"] if item["criterion"] == "C5")
    assert c5["status"] == "comparable"
    c6 = next(item for item in payload["criteria"] if item["criterion"] == "C6")
    assert c6["status"] == "comparable"
    assert payload["protocol"] == "phase_5_8_comparability_v2"
    assert "C6 revised" in payload["followup_scope"]


def test_markdown_states_the_primary_perimeter_and_followup_c6():
    markdown = render_audit_markdown()

    assert "**Primario:** C1, C3, C4, C5, C6." in markdown
    assert "**Escluso dalle metriche di accordo:** nessuno." in markdown
    assert "C6 rientra nel perimetro primario" in markdown
    assert "A1 `a1_v5`" in markdown
