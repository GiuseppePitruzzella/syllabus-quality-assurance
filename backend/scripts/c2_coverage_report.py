"""Deterministic C2 english_coverage report over the official human sample.

Offline: read-only SELECT on the local DB, no Vertex. Prints and writes
the english_coverage matrix + suggested C2 for each of the 8 syllabi, so
the suggested score can be inspected (and shown stable for the
previously-stable syllabi) without spending Vertex.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.evaluation.agents.english_coverage import english_coverage, suggest_c2  # noqa: E402
from app.evaluation.analysis.human_sample import OFFICIAL_HUMAN_SAMPLE  # noqa: E402
from app.evaluation.state import snapshot_syllabus  # noqa: E402
from app.models.syllabus import Syllabus  # noqa: E402


def main() -> None:
    out_dir = _PROJECT_ROOT / "data" / "calibration" / "c2_stability_v1"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    with SessionLocal() as session:
        for seuid, slug in OFFICIAL_HUMAN_SAMPLE:
            row = session.query(Syllabus).filter(Syllabus.seuid == seuid).first()
            if row is None:
                raise ValueError(f"seuid not found in DB: {seuid!r}")
            snap = snapshot_syllabus(row)
            cov = english_coverage(snap)
            rows.append({"seuid": seuid, "slug": slug,
                         "coverage": cov, "suggested_c2": suggest_c2(cov)})

    (out_dir / "coverage_report.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    lines = ["# C2 english_coverage — pre-check deterministico (8 syllabi)", "",
             "| Syllabus | title | LO | content | assess | suggested C2 |",
             "| --- | :-: | :-: | :-: | :-: | :-: |"]
    for r in rows:
        c = r["coverage"]
        lines.append(
            f"| {r['slug']} | {'Y' if c['title_en'] else '-'} "
            f"| {'Y' if c['learning_outcomes_en'] else '-'} "
            f"| {'Y' if c['course_content_en'] else '-'} "
            f"| {'Y' if c['assessment_methods_en'] else '-'} | {r['suggested_c2']} |"
        )
    (out_dir / "coverage_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWritten to {out_dir}")


if __name__ == "__main__":
    main()
