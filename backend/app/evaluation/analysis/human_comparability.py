"""Comparability contract for the Phase 5.8 expert validation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


ComparabilityStatus = Literal[
    "comparable",
    "partially_comparable",
    "not_comparable",
]


@dataclass(frozen=True)
class CriterionComparability:
    criterion: str
    human_construct: str
    system_construct: str
    status: ComparabilityStatus
    analysis_tier: Literal["primary", "secondary", "excluded"]
    rationale: str
    follow_up: str


AUDIT: tuple[CriterionComparability, ...] = (
    CriterionComparability(
        criterion="C1",
        human_construct="Presenza sostanziale delle nove sezioni del template.",
        system_construct="Completezza strutturale delle stesse nove sezioni.",
        status="comparable",
        analysis_tier="primary",
        rationale="Perimetro e soglie sono sostanzialmente equivalenti.",
        follow_up="Nessuna correzione controfattuale necessaria.",
    ),
    CriterionComparability(
        criterion="C2",
        human_construct=(
            "Copertura bilingue del perimetro minimo, includendo coerenza con "
            "la versione italiana."
        ),
        system_construct=(
            "Presenza della versione inglese per titolo, risultati, contenuti "
            "e modalità di verifica."
        ),
        status="partially_comparable",
        analysis_tier="secondary",
        rationale=(
            "Il questionario aggiunge un requisito di coerenza IT/EN che A1 "
            "a1_v5 non valutava; le soglie sulla copertura sono inoltre "
            "formulate in modo leggermente diverso."
        ),
        follow_up="Riportare separatamente i disaccordi legati alla coerenza IT/EN.",
    ),
    CriterionComparability(
        criterion="C3",
        human_construct=(
            "Risultati di apprendimento specifici e centrati sullo studente."
        ),
        system_construct=(
            "Risultati specifici, verificabili e formulati come conoscenze o "
            "abilità osservabili."
        ),
        status="comparable",
        analysis_tier="primary",
        rationale=(
            "Le formulazioni differiscono, ma operazionalizzano lo stesso "
            "costrutto di qualità formulativa degli outcome."
        ),
        follow_up="Discutere congiuntamente a C4 la sovrapposizione documentale.",
    ),
    CriterionComparability(
        criterion="C4",
        human_construct=(
            "Presenza e differenziazione dei cinque Descrittori di Dublino."
        ),
        system_construct=(
            "Presenza, specificità e differenziazione dei cinque Descrittori."
        ),
        status="comparable",
        analysis_tier="primary",
        rationale="Costrutto e anchor sono sostanzialmente equivalenti.",
        follow_up="Mantenere separato da C3 ma sotto la stessa macro-area RA.",
    ),
    CriterionComparability(
        criterion="C5",
        human_construct=(
            "Prerequisiti specifici con distinzione culturali/disciplinari."
        ),
        system_construct=(
            "A1 a1_v5 richiedeva la stessa distinzione per il punteggio massimo."
        ),
        status="comparable",
        analysis_tier="primary",
        rationale=(
            "Il confronto storico è valido perché validation_lm18 usava "
            "a1_v5. La rubrica corrente a1_v7 è stata successivamente "
            "ridefinita e non va usata retroattivamente."
        ),
        follow_up=(
            "Eseguire una sensibilità controfattuale con la regola a1_v7, "
            "che rende la tassonomia un segnale non obbligatorio."
        ),
    ),
    CriterionComparability(
        criterion="C6",
        human_construct=(
            "Trasparenza delle modalità di verifica rivalutata dopo follow-up: "
            "tipologia delle prove, contributo al voto, criteri o fasce di "
            "valutazione, rubriche o esempi."
        ),
        system_construct=(
            "Trasparenza delle modalità di verifica: tipologia, criteri di "
            "voto, rubriche o esempi."
        ),
        status="comparable",
        analysis_tier="primary",
        rationale=(
            "La prima consegna usava un testo di template non allineato al "
            "sistema; dopo il follow-up il valutatore ha rivisto C6 per tutti "
            "i syllabus secondo la definizione corretta. Il testo legacy nel "
            "workbook resta un limite documentale, ma i punteggi aggiornati "
            "sono confrontabili."
        ),
        follow_up=(
            "Usare i punteggi C6 aggiornati nella metrica primaria e dichiarare "
            "che derivano da una micro-rivalutazione post-follow-up."
        ),
    ),
    CriterionComparability(
        criterion="C7",
        human_construct=(
            "Strutturazione in macro-aree o blocchi, con preferenza dichiarata "
            "dal valutatore per una narrazione discorsiva."
        ),
        system_construct=(
            "Chiarezza informativa di contenuti e programmazione; ammette "
            "sezioni, progressione, schedule o altra struttura riconoscibile."
        ),
        status="partially_comparable",
        analysis_tier="secondary",
        rationale=(
            "Entrambi valutano la comprensibilità dei contenuti, ma il "
            "questionario premia esplicitamente macro-blocchi e può confliggere "
            "con le istruzioni locali favorevoli alla forma discorsiva."
        ),
        follow_up="Eseguire una sensibilità che rimuova il requisito dei moduli.",
    ),
    CriterionComparability(
        criterion="C8",
        human_construct="Coerenza tra risultati di apprendimento e verifica.",
        system_construct=(
            "Constructive alignment complessivo tra risultati, contenuti, "
            "metodi didattici e verifica."
        ),
        status="partially_comparable",
        analysis_tier="secondary",
        rationale=(
            "Il giudizio umano copre un sottoinsieme del costrutto usato dal "
            "sistema; l'accordo resta informativo ma non pienamente equivalente."
        ),
        follow_up="Separare i disaccordi dovuti a contenuti/metodi didattici.",
    ),
    CriterionComparability(
        criterion="C9",
        human_construct=(
            "Cura editoriale del syllabus osservato sulla pagina ufficiale."
        ),
        system_construct=(
            "Cura editoriale valutata sullo snapshot estratto dal portale."
        ),
        status="partially_comparable",
        analysis_tier="secondary",
        rationale=(
            "Il costrutto è lo stesso, ma le fonti osservate non sono "
            "equivalenti: parser e portale possono introdurre marker o "
            "interruzioni non visibili al valutatore."
        ),
        follow_up=(
            "Classificare i disaccordi come difetti reali o artefatti di "
            "estrazione prima di interpretarli."
        ),
    ),
)


def audit_payload() -> dict[str, object]:
    return {
        "protocol": "phase_5_8_comparability_v2",
        "human_instrument": "expert_01_blind_raw.xlsx",
        "followup_scope": "VAPT completed; C6 revised for all syllabi after clarification",
        "system_artifacts": "data/calibration/validation_lm18/",
        "system_code_commit": "f5b57c9e1154c109ca32e5ee3659b0263cebe3b3",
        "system_prompt_versions": {
            "A1": "a1_v5",
            "A2": "a2_v1",
            "A3": "a3_v1",
            "A4": "a4_v2",
        },
        "criteria": [asdict(item) for item in AUDIT],
        "primary_criteria": criteria_for_tier("primary"),
        "secondary_criteria": criteria_for_tier("secondary"),
        "excluded_criteria": criteria_for_tier("excluded"),
    }


def criteria_for_tier(tier: str) -> list[str]:
    return [item.criterion for item in AUDIT if item.analysis_tier == tier]


def render_audit_markdown() -> str:
    labels = {
        "comparable": "Comparabile",
        "partially_comparable": "Parzialmente comparabile",
        "not_comparable": "Non comparabile",
    }
    lines = [
        "# Audit di comparabilità — Phase 5.8",
        "",
        "Il confronto usa il questionario blind ricevuto dal valutatore e le "
        "valutazioni storiche `validation_lm18`, generate con A1 `a1_v5`, "
        "A2 `a2_v1`, A3 `a3_v1` e A4 `a4_v2`.",
        "",
        "| Criterio | Stato | Livello analisi | Motivazione |",
        "| --- | --- | --- | --- |",
    ]
    for item in AUDIT:
        lines.append(
            f"| {item.criterion} | {labels[item.status]} | "
            f"{item.analysis_tier} | {item.rationale} |"
        )
    lines.extend(
        [
            "",
            "## Perimetro delle metriche",
            "",
            f"- **Primario:** {', '.join(criteria_for_tier('primary'))}.",
            f"- **Secondario/esplorativo:** "
            f"{', '.join(criteria_for_tier('secondary'))}.",
            f"- **Escluso dalle metriche di accordo:** "
            f"{', '.join(criteria_for_tier('excluded')) or 'nessuno'}.",
            "",
            "C6 rientra nel perimetro primario soltanto nella versione "
            "aggiornata del workbook: il valutatore ha completato VAPT e "
            "rivalutato C6 dopo il chiarimento metodologico. C5 resta "
            "comparabile nel confronto storico perché sia il questionario sia "
            "A1 `a1_v5` usavano la tassonomia culturali/disciplinari; la "
            "successiva ridefinizione `a1_v7` sarà trattata soltanto come "
            "analisi controfattuale.",
            "",
        ]
    )
    return "\n".join(lines)
