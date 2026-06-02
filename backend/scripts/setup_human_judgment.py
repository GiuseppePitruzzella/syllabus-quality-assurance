"""Phase 5.8 — bootstrap the human-judgment validation artefacts.

Generates everything an evaluator needs to score the 8 LM-18 syllabi
shortlisted for inter-rater reliability against the system:

  - data/human_judgment/templates/blind/{slug}_blind.csv
        First-pass form. Anchors-only, NO system score visible.
        This is the form whose values feed Cohen's kappa.

  - data/human_judgment/templates/post_hoc/{slug}_posthoc.csv
        Second-pass form. System score + justification visible side by
        side. For qualitative discussion of disagreements only,
        NOT for kappa computation.

  - data/human_judgment/schema.json
        Canonical JSON schema for downstream export.

  - data/human_judgment/README.md
        Evaluator-facing instructions (blind protocol, anchors,
        timeline, file format, ground rules).

Run this script once. The aggregate script
``backend/scripts/aggregate_human_judgment.py`` then reads any number
of evaluator copies of the blind CSVs and computes weighted Cohen's
kappa + MAE + CoreScore comparison.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

VALIDATION = _PROJECT_ROOT / "data" / "calibration" / "validation_lm18"
HJ_DIR = _PROJECT_ROOT / "data" / "human_judgment"

# Order = display order in the shortlist (docs/human_validation_shortlist.md).
# Slug is filesystem-safe and human-readable.
SHORTLIST: list[tuple[str, str]] = [
    ("88B7C1CE-B595-46A5-A37A-C5414AD807B5", "01_COMPUTER_VISION_LAB"),
    ("0B53E8E2-4B90-426F-A25C-3AA31FA4B649", "02_INTERNET_OF_THINGS"),
    ("F4AF1512-9D7A-4256-B57D-E103E05B009B", "03_PEER_TO_PEER_LAB"),
    ("9A90BBCE-99E3-4FB0-BF91-CCAAA5C51791", "04_MULTIMEDIA_LAB"),
    ("89E21813-A17C-4C85-AF65-C295EE11ED59", "05_COMPUTER_VISION"),
    ("E2446DF6-59A1-46FD-B8D8-635EB937C1B3", "06_OTTIMIZZAZIONE"),
    ("3540D939-DA16-4C1D-983C-E6B85C403F2F", "07_DEEP_LEARNING"),
    ("FE97232C-4F07-41F8-A82F-FF73592265EC", "08_MACHINE_LEARNING"),
]

# Criteria definitions (kept aligned with the rubric in docs/progettazione.md
# and the prompts in app/evaluation/agents/prompts/*.py).
CRITERIA: dict[str, dict[str, str]] = {
    "C1": {
        "name": "Completezza strutturale",
        "owner": "A1",
        "summary": (
            "Presenza delle 9 sezioni obbligatorie del template UniCT (RA, "
            "PR, CN, MV, ED, TD, MS, MF, PRG)."
        ),
        "anchor_0": "Mancano 3 o più sezioni obbligatorie, o sono presenti ma vuote.",
        "anchor_1": "Tutte le sezioni presenti ma 1-2 hanno contenuto minimo o povero.",
        "anchor_2": "Tutte le sezioni presenti e compilate in modo sostanziale.",
    },
    "C2": {
        "name": "Completezza bilingue",
        "owner": "A1",
        "summary": (
            "Disponibilita della versione inglese per il perimetro minimo "
            "(titolo, RA, contenuti, modalita di verifica)."
        ),
        "anchor_0": "Versione inglese assente o gravemente parziale (manca >1 sezione del perimetro).",
        "anchor_1": "Versione inglese presente ma con lacune parziali su 1 sezione del perimetro.",
        "anchor_2": "Versione inglese completa sul perimetro minimo e coerente con l'IT.",
    },
    "C3": {
        "name": "Formulazione dei risultati di apprendimento",
        "owner": "A2",
        "summary": (
            "I risultati di apprendimento attesi sono formulati in modo "
            "specifico e centrato sullo studente."
        ),
        "anchor_0": "Risultati assenti, o solo descrizione del corso senza centratura sullo studente.",
        "anchor_1": "Risultati presenti ma generici o misti con la descrizione del corso.",
        "anchor_2": "Risultati specifici, centrati sullo studente, articolati in conoscenze/abilita.",
    },
    "C4": {
        "name": "Descrittori di Dublino",
        "owner": "A2",
        "summary": (
            "Presenza e qualita dei 5 descrittori di Dublino (conoscenza, "
            "applicazione, giudizio, comunicazione, apprendimento)."
        ),
        "anchor_0": "Mancano 2 o piu descrittori, o sono tutti ripetitivi/copiati l'uno dall'altro.",
        "anchor_1": "5 descrittori presenti ma con qualche genericita o ripetizione tra di essi.",
        "anchor_2": "5 descrittori presenti, articolati e ben differenziati tra loro.",
    },
    "C5": {
        "name": "Chiarezza dei prerequisiti",
        "owner": "A1",
        "summary": (
            "Prerequisiti specifici, formulati come conoscenze richieste, "
            "con distinzione esplicita tra culturali/generali e "
            "disciplinari/specialistici (rubrica a1_v5)."
        ),
        "anchor_0": "Prerequisiti assenti, generici, tautologici, o solo rimando a esami.",
        "anchor_1": "Prerequisiti specifici ma senza distinzione esplicita culturali/disciplinari.",
        "anchor_2": "Prerequisiti specifici E distinti esplicitamente culturali/disciplinari (o organizzazione equivalente).",
    },
    "C6": {
        "name": "Coerenza didattica RA/contenuti",
        "owner": "A3",
        "summary": (
            "I contenuti del corso coprono i risultati di apprendimento "
            "dichiarati (mapping ricostruibile dai testi)."
        ),
        "anchor_0": "Contenuti scollegati dai risultati di apprendimento o assenti.",
        "anchor_1": "Coperture parziali o ambigue tra RA e contenuti.",
        "anchor_2": "Contenuti coerenti con i RA, mapping ricostruibile dai testi.",
    },
    "C7": {
        "name": "Strutturazione contenuti",
        "owner": "A3",
        "summary": (
            "I contenuti sono organizzati in modo chiaro e ricostruibile "
            "da evidenze testuali concrete."
        ),
        "anchor_0": "Contenuti elencati in modo disorganizzato o assenti.",
        "anchor_1": "Elenco di topic ma senza struttura macro (moduli, blocchi).",
        "anchor_2": "Contenuti organizzati in macro-aree con descrizione introduttiva chiara.",
    },
    "C8": {
        "name": "Coerenza didattica RA/verifica",
        "owner": "A3",
        "summary": (
            "Le modalita di verifica permettono di valutare i risultati di "
            "apprendimento dichiarati."
        ),
        "anchor_0": "Modalita di verifica assenti o non in grado di valutare i RA.",
        "anchor_1": "Modalita presenti ma con corrispondenza parziale ai RA.",
        "anchor_2": "Modalita coerenti con i RA, articolate in prove/criteri di valutazione.",
    },
    "C9": {
        "name": "Cura editoriale",
        "owner": "A4",
        "summary": (
            "Il syllabus e curato a livello editoriale: niente refusi, "
            "formattazione coerente, riferimenti strutturati."
        ),
        "anchor_0": "Refusi diffusi, formattazione incoerente, riferimenti mancanti o caotici.",
        "anchor_1": "Cura discreta con qualche imperfezione (refusi sporadici, frammenti, riferimenti parziali).",
        "anchor_2": "Cura impeccabile: nessun refuso, formattazione coerente, riferimenti completi.",
    },
}


def _load_evaluation(seuid: str) -> dict:
    """Read the per-syllabus evaluation dump from validation_lm18."""
    path = VALIDATION / f"{seuid}__evaluation.json"
    # CE3B947A uses the rerun directory but is not in the shortlist;
    # all 8 selected syllabi have their evaluation in validation_lm18/.
    return json.loads(path.read_text(encoding="utf-8"))["evaluation"]


def _system_judgments(evaluation: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for agent_out in (evaluation.get("agent_outputs") or {}).values():
        if not agent_out:
            continue
        for j in agent_out.get("judgments") or []:
            out[j["criterion_code"]] = {
                "score": j.get("score"),
                "is_na": j.get("is_na", False),
                "na_reason": j.get("na_reason"),
                "justification": (j.get("justification") or "").strip(),
                "confidence": j.get("confidence"),
            }
    return out


def _write_blind_csv(slug: str, out_dir: Path) -> Path:
    """Anchors-only form for blind first-pass evaluation."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slug}_blind.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "criterion", "name", "summary",
            "anchor_0", "anchor_1", "anchor_2",
            "human_score", "is_na", "na_reason",
            "human_justification", "evidence_quote",
        ])
        for code, c in CRITERIA.items():
            w.writerow([
                code, c["name"], c["summary"],
                c["anchor_0"], c["anchor_1"], c["anchor_2"],
                "", "false", "", "", "",
            ])
    return path


def _write_posthoc_csv(
    slug: str, sys_judgments: dict[str, dict], out_dir: Path
) -> Path:
    """System-side visible form for the post-hoc qualitative discussion."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slug}_posthoc.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "criterion", "name", "summary",
            "system_score", "system_is_na", "system_justification",
            "human_score_blind", "agreement", "post_hoc_notes",
        ])
        for code, c in CRITERIA.items():
            s = sys_judgments.get(code, {})
            w.writerow([
                code, c["name"], c["summary"],
                "" if s.get("score") is None else s["score"],
                "true" if s.get("is_na") else "false",
                s.get("justification", ""),
                "", "", "",
            ])
    return path


def _syllabus_urls(seuids: list[str]) -> dict[str, dict[str, str]]:
    """Pull url_it / url_en / course_name for the shortlisted seuids."""
    db = _BACKEND_DIR / "data" / "syllabus_ai.db"
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    out: dict[str, dict[str, str]] = {}
    for s in seuids:
        row = con.execute(
            "SELECT course_name, course_name_en, url_it, url_en "
            "FROM syllabi WHERE seuid = ?",
            (s,),
        ).fetchone()
        if row is not None:
            out[s] = dict(row)
    con.close()
    return out


def _write_schema(out_path: Path) -> None:
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Human Judgment Export — Phase 5.8 syllabus validation",
        "description": (
            "Canonical JSON shape for one evaluator's blind judgment on "
            "one syllabus. The aggregate script reads CSVs directly for "
            "convenience; this schema is the reference format if/when an "
            "evaluator prefers to export to JSON for reproducibility."
        ),
        "type": "object",
        "required": [
            "seuid", "course_name", "evaluator_id",
            "phase", "completed_at", "judgments",
        ],
        "additionalProperties": False,
        "properties": {
            "seuid": {"type": "string"},
            "course_name": {"type": "string"},
            "evaluator_id": {"type": "string", "minLength": 1},
            "evaluator_name": {"type": ["string", "null"]},
            "phase": {"enum": ["blind", "post_hoc"]},
            "completed_at": {"type": "string", "format": "date-time"},
            "judgments": {
                "type": "object",
                "additionalProperties": False,
                "patternProperties": {
                    "^C[1-9]$": {
                        "type": "object",
                        "required": ["score", "is_na", "justification"],
                        "additionalProperties": False,
                        "properties": {
                            "score": {"type": ["integer", "null"], "enum": [0, 1, 2, None]},
                            "is_na": {"type": "boolean"},
                            "na_reason": {"type": ["string", "null"]},
                            "justification": {"type": "string"},
                            "evidence_quote": {"type": ["string", "null"]},
                        },
                    },
                },
            },
            "overall_notes": {"type": "string"},
        },
    }
    out_path.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _write_readme(
    out_path: Path, urls: dict[str, dict[str, str]]
) -> None:
    rows = []
    for i, (seuid, slug) in enumerate(SHORTLIST, 1):
        u = urls.get(seuid, {})
        rows.append(
            f"{i}. **{slug}** — `{seuid[:8]}`  \n"
            f"   {u.get('course_name', '?')}"
            + (f" / EN: *{u['course_name_en']}*" if u.get("course_name_en") else "")
            + "  \n"
            f"   IT: {u.get('url_it', '?')}  \n"
            f"   EN: {u.get('url_en', '?')}"
        )
    syllabi_block = "\n".join(rows)

    parts = [
        "# Phase 5.8 — Human-judgment validation protocol",
        "",
        "Eight LM-18 syllabi are evaluated by one or more domain experts",
        "against the same 9 criteria (C1-C9) the multi-agent system",
        "scored automatically in Phase 5.7. Inter-rater agreement",
        "(weighted Cohen's kappa, MAE, CoreScore correlation) is the",
        "external validation of the system's output.",
        "",
        "## Two phases",
        "",
        "### Phase 1 — BLIND",
        "",
        "- Form: `templates/blind/<slug>_blind.csv` (one per syllabus)",
        "- You see: criterion name, summary, anchors 0/1/2",
        "- You do NOT see: the system's score or justification",
        "- Goal: form your own judgment before any system anchoring",
        "- Output: filled-in CSV in `evaluators/<your_id>/blind/`",
        "",
        "### Phase 2 — POST-HOC (optional, qualitative)",
        "",
        "- Form: `templates/post_hoc/<slug>_posthoc.csv`",
        "- You see: your blind score + the system score + system",
        "  justification side by side",
        "- You discuss: WHY disagreements occurred. NOT for kappa.",
        "- Output: filled-in CSV in `evaluators/<your_id>/post_hoc/`",
        "",
        "## Ground rules (Phase 1, blind)",
        "",
        "- **Do not** open the system's report, summary, or evaluation",
        "  JSON before completing Phase 1. The anchoring bias they",
        "  would induce contaminates kappa.",
        "- Read the syllabus on the UniCT site (links below) before",
        "  filling in any score.",
        "- Score the 9 criteria for one syllabus in a single sitting",
        "  when possible (~30-40 min per syllabus, ~4h for all 8).",
        "- Use `NA` only for technical impossibility (e.g. the field",
        "  required by the criterion is genuinely absent and the",
        "  criterion cannot be evaluated). Absence-as-low-quality is",
        "  score 0, NOT NA.",
        "- Score scale (rubrica UniCT, see `docs/progettazione.md`):",
        "  - **0** = criterio non soddisfatto",
        "  - **1** = criterio soddisfatto parzialmente",
        "  - **2** = criterio pienamente soddisfatto",
        "",
        "## How to fill a CSV",
        "",
        "Open the CSV in Excel, Google Sheets, or LibreOffice. Each row",
        "is one criterion. Fill in:",
        "",
        "- `human_score`: integer 0, 1, or 2 (leave empty if `is_na = true`)",
        "- `is_na`: `true` only if technically impossible to evaluate",
        "- `na_reason`: free text (only if `is_na = true`)",
        "- `human_justification`: 1-3 sentences explaining the score",
        "- `evidence_quote`: a short literal quote from the syllabus",
        "  supporting the score (optional but encouraged)",
        "",
        "Save the file as CSV (UTF-8, comma-separated). Do not rename",
        "columns. Keep the order of the rows.",
        "",
        "## The 8 syllabi",
        "",
        syllabi_block,
        "",
        "## After Phase 1",
        "",
        "Copy your filled `*_blind.csv` files into a new folder named",
        "`evaluators/<your_id>/blind/`. Run:",
        "",
        "```bash",
        "cd backend",
        "uv run python scripts/aggregate_human_judgment.py",
        "```",
        "",
        "The aggregator computes weighted Cohen's kappa per criterion,",
        "MAE on integer scores, accuracy, CoreScore correlation, and",
        "the top-N strongest disagreements. Output:",
        "`data/human_judgment/aggregate.json` and `aggregate.md`.",
        "",
        "## Format details",
        "",
        "See `schema.json` for the canonical JSON shape if you prefer",
        "exporting to JSON instead of CSV.",
    ]
    out_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> None:
    HJ_DIR.mkdir(parents=True, exist_ok=True)
    blind_dir = HJ_DIR / "templates" / "blind"
    posthoc_dir = HJ_DIR / "templates" / "post_hoc"

    seuids = [s for s, _ in SHORTLIST]
    urls = _syllabus_urls(seuids)

    print(f"Output dir: {HJ_DIR}")
    print(f"Blind templates: {blind_dir}")
    print(f"Post-hoc templates: {posthoc_dir}")
    print()

    for seuid, slug in SHORTLIST:
        evaluation = _load_evaluation(seuid)
        sys_judgments = _system_judgments(evaluation)
        bp = _write_blind_csv(slug, blind_dir)
        pp = _write_posthoc_csv(slug, sys_judgments, posthoc_dir)
        print(f"  {slug:30s}  blind={bp.name}  posthoc={pp.name}")

    _write_schema(HJ_DIR / "schema.json")
    _write_readme(HJ_DIR / "README.md", urls)
    print()
    print(f"Wrote schema:  {HJ_DIR / 'schema.json'}")
    print(f"Wrote README:  {HJ_DIR / 'README.md'}")


if __name__ == "__main__":
    main()
