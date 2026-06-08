"""Phase 9.A.B — read-only compatibility scan for the local-document
registry against the new ALLOWED_CRITERIA_BY_DOCUMENT_TYPE contract.

Reports every ``LocalDocument`` row whose ``enabled_criteria`` is
no longer a subset of the type's allowed set under the consolidated
Phase 9.A mapping. The Phase 8 defaults bound, for instance,
``regolamento_didattico`` to E1, while Phase 9.A binds it to E3 —
existing rows from Phase 8 would now violate the contract.

The script DOES NOT mutate anything. It is intentional that no
automatic startup migration is shipped: every incoherent row
deserves an explicit, audited fix (PATCH + reindex), not a silent
flip on first server boot.

Usage::

    cd backend
    uv run python scripts/scan_phase_9_a_b_compatibility.py

Exit code:
    0 — no incoherent rows.
    1 — at least one incoherent row found. The summary lists each
        offending row with its document_type, current
        enabled_criteria, the codes that are no longer allowed,
        and a suggested fix.
"""
from __future__ import annotations

import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models.local_document import LocalDocument  # noqa: E402
from app.schemas.local_document import (  # noqa: E402
    ALLOWED_CRITERIA_BY_DOCUMENT_TYPE,
    DEFAULT_ENABLED_CRITERIA,
)


def main() -> int:
    print("Phase 9.A.B — registry compatibility scan")
    print("------------------------------------------")
    print("Read-only: no row is mutated. Suggests a PATCH per row.")
    print()

    db = SessionLocal()
    try:
        rows = (
            db.query(LocalDocument)
            .filter(LocalDocument.deleted_at.is_(None))
            .order_by(LocalDocument.id.asc())
            .all()
        )
        if not rows:
            print("No local documents in the registry. Nothing to scan.")
            return 0

        incoherent: list[tuple[LocalDocument, list[str]]] = []
        for row in rows:
            allowed = set(
                ALLOWED_CRITERIA_BY_DOCUMENT_TYPE.get(row.document_type, [])
            )
            current = list(row.enabled_criteria or [])
            offending = [c for c in current if c not in allowed]
            if offending:
                incoherent.append((row, offending))

        print(f"Rows scanned: {len(rows)}")
        print(f"Incoherent rows: {len(incoherent)}")
        print()
        if not incoherent:
            print("OK — every row's enabled_criteria is a subset of the allowed set.")
            return 0

        for row, offending in incoherent:
            suggested = DEFAULT_ENABLED_CRITERIA.get(row.document_type, [])
            print(
                f"  id={row.id} cdl_id={row.cdl_id} type={row.document_type!r} "
                f"version={row.version}"
            )
            print(
                f"    title={row.title!r}"
            )
            print(
                f"    enabled_criteria (current): {current_or_dash(row.enabled_criteria)}"
            )
            print(
                f"    codes not allowed for this type: {offending}"
            )
            print(
                f"    suggested fix: PATCH /api/local-documents/{row.id} -> "
                f"enabled_criteria={suggested!r}"
                + (
                    "   (auto-triggers reindex if status=indexed)"
                    if suggested
                    else "   (no auto reindex; status flips back to uploaded)"
                )
            )
            print()

        print(
            "Apply the fixes via PATCH (the regular API path) and let the "
            "scheduler reindex the affected rows; do not migrate at startup."
        )
        return 1
    finally:
        db.close()


def current_or_dash(value):
    if not value:
        return "[]"
    return value


if __name__ == "__main__":
    raise SystemExit(main())
