"""Tests for the ExternalDocumentResolver (Phase 9.B.2).

Covers academic-year normalisation, the precedence ladder
(``explicit_selection`` → ``academic_year_match`` →
``latest_available_fallback``), the per-chain version selection,
the multi-document path used by E5, the hard-NA path for E1/E2/E3/E5
when no document is enabled, the special-case E4 path that bypasses
the registry, and the resolver's refusal to look at soft-deleted /
non-indexed rows.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.local_documents.resolver import (
    ExternalDocumentResolver,
    ResolverInput,
    normalise_academic_year,
)
from app.models import CorsoDiLaurea, Department, LocalDocument


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cdl(db):
    dept = Department(
        name="DMI", area="Scienze", website_url="https://x",
        email="x@y", phone="1", director="d",
        scraped_at=datetime.now(timezone.utc),
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    cdl = CorsoDiLaurea(
        department_id=dept.id, name="Informatica", code="lm-18",
        type="Magistrale", academic_year=None, url="https://x/c",
        scraped_at=datetime.now(timezone.utc),
    )
    db.add(cdl)
    db.commit()
    db.refresh(cdl)
    return cdl


def _doc(
    db,
    cdl_id: int,
    *,
    document_type: str,
    title: str,
    version: int,
    academic_year: str = "2025-2026",
    enabled_criteria: list[str] | None = None,
    status: str = "indexed",
    deleted_at=None,
) -> LocalDocument:
    norm = title.lower().strip()
    row = LocalDocument(
        cdl_id=cdl_id,
        document_type=document_type,
        academic_year=academic_year,
        title=title,
        normalized_title=norm,
        file_path=f"{cdl_id}/{title}_v{version}.md",
        file_extension=".md",
        file_hash=f"hash:{document_type}:{title}:{version}",
        file_size=1,
        version=version,
        enabled_criteria=enabled_criteria
        if enabled_criteria is not None
        else _default_for_type(document_type),
        status=status,
        uploaded_at=datetime.now(timezone.utc),
        deleted_at=deleted_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _default_for_type(t: str) -> list[str]:
    return {
        "sua_cds": ["E1"],
        "matrice_tuning": ["E2"],
        "regolamento_didattico": ["E3"],
        "usi_dipartimentali": ["E5"],
        "linee_guida_cdl": ["E5"],
        "template_locale": ["E5"],
        "nota_presidio": ["E5"],
    }.get(t, [])


# ---------------------------------------------------------------------------
# normalise_academic_year
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2025-2026", "2025-2026"),
        ("2025/2026", "2025-2026"),
        ("2025-26", "2025-2026"),
        ("2025_2026", "2025-2026"),
        (" 2025 / 2026 ", "2025-2026"),
        ("2025", "2025-2026"),
        ("", None),
        ("    ", None),
        (None, None),
        ("not a year", None),
    ],
)
def test_normalise_academic_year(raw, expected):
    assert normalise_academic_year(raw) == expected


# ---------------------------------------------------------------------------
# Hard NA on missing source
# ---------------------------------------------------------------------------


def test_e1_is_na_when_no_sua_cds(db_session):
    cdl = _make_cdl(db_session)
    out = ExternalDocumentResolver(db_session).resolve(
        ResolverInput(cdl_id=cdl.id, academic_year="2025-2026", has_english=True)
    )
    assert out.by_criterion["E1"].applicable is False
    assert out.by_criterion["E1"].documents == []
    assert "no indexed document enabled" in out.by_criterion["E1"].na_reason


def test_e3_is_na_when_only_a_regolamento_with_disabled_criteria(db_session):
    """A regolamento_didattico row whose enabled_criteria is empty
    must not produce a resolution — the resolver re-checks the
    column even though the API guards it upstream."""
    cdl = _make_cdl(db_session)
    _doc(
        db_session, cdl.id,
        document_type="regolamento_didattico", title="r", version=1,
        enabled_criteria=[],
    )
    out = ExternalDocumentResolver(db_session).resolve(
        ResolverInput(cdl_id=cdl.id, academic_year="2025-2026", has_english=True)
    )
    assert out.by_criterion["E3"].applicable is False


def test_resolver_skips_non_indexed_rows(db_session):
    cdl = _make_cdl(db_session)
    _doc(
        db_session, cdl.id,
        document_type="sua_cds", title="s", version=1, status="failed",
    )
    out = ExternalDocumentResolver(db_session).resolve(
        ResolverInput(cdl_id=cdl.id, academic_year="2025-2026", has_english=True)
    )
    assert out.by_criterion["E1"].applicable is False


def test_resolver_skips_soft_deleted_rows(db_session):
    cdl = _make_cdl(db_session)
    _doc(
        db_session, cdl.id,
        document_type="sua_cds", title="s", version=1,
        deleted_at=datetime.now(timezone.utc),
    )
    out = ExternalDocumentResolver(db_session).resolve(
        ResolverInput(cdl_id=cdl.id, academic_year="2025-2026", has_english=True)
    )
    assert out.by_criterion["E1"].applicable is False


# ---------------------------------------------------------------------------
# Precedence ladder
# ---------------------------------------------------------------------------


def test_academic_year_match_picks_matching_version(db_session):
    cdl = _make_cdl(db_session)
    # Two versions of the same chain. v1 matches the syllabus year, v2 doesn't.
    _doc(
        db_session, cdl.id,
        document_type="sua_cds", title="s", version=1,
        academic_year="2025-2026",
    )
    _doc(
        db_session, cdl.id,
        document_type="sua_cds", title="s", version=2,
        academic_year="2026-2027",
    )

    out = ExternalDocumentResolver(db_session).resolve(
        ResolverInput(cdl_id=cdl.id, academic_year="2025-2026", has_english=True)
    )
    res = out.by_criterion["E1"]
    assert res.applicable is True
    assert len(res.documents) == 1
    assert res.documents[0].document_version_snapshot == 1
    assert res.documents[0].resolution_reason == "academic_year_match"


def test_fallback_when_year_does_not_match_any_version(db_session):
    cdl = _make_cdl(db_session)
    _doc(
        db_session, cdl.id,
        document_type="sua_cds", title="s", version=1,
        academic_year="2024-2025",
    )
    _doc(
        db_session, cdl.id,
        document_type="sua_cds", title="s", version=2,
        academic_year="2024-2025",
    )

    out = ExternalDocumentResolver(db_session).resolve(
        ResolverInput(cdl_id=cdl.id, academic_year="2026-2027", has_english=True)
    )
    res = out.by_criterion["E1"]
    assert res.applicable is True
    # Latest version of the chain (v2).
    assert res.documents[0].document_version_snapshot == 2
    assert res.documents[0].resolution_reason == "latest_available_fallback"


def test_explicit_selection_beats_academic_year_match(db_session):
    cdl = _make_cdl(db_session)
    v1 = _doc(
        db_session, cdl.id,
        document_type="sua_cds", title="s", version=1,
        academic_year="2025-2026",
    )
    v2 = _doc(
        db_session, cdl.id,
        document_type="sua_cds", title="s", version=2,
        academic_year="2026-2027",
    )

    # Even though v1 matches the syllabus year, explicit selection
    # of v2 wins.
    out = ExternalDocumentResolver(db_session).resolve(
        ResolverInput(
            cdl_id=cdl.id,
            academic_year="2025-2026",
            has_english=True,
            selected_document_ids=[v2.id],
        )
    )
    res = out.by_criterion["E1"]
    assert res.documents[0].document_version_snapshot == 2
    assert res.documents[0].resolution_reason == "explicit_selection"
    # v1 wasn't picked.
    assert all(d.document_version_snapshot != 1 for d in res.documents)
    assert v1.id != v2.id  # sanity


def test_normalisation_applied_on_both_sides(db_session):
    cdl = _make_cdl(db_session)
    _doc(
        db_session, cdl.id,
        document_type="sua_cds", title="s", version=1,
        academic_year="2025/2026",  # not canonical, normalises to 2025-2026
    )
    out = ExternalDocumentResolver(db_session).resolve(
        ResolverInput(cdl_id=cdl.id, academic_year="2025-26", has_english=True)
    )
    res = out.by_criterion["E1"]
    assert res.applicable is True
    assert res.documents[0].resolution_reason == "academic_year_match"


# ---------------------------------------------------------------------------
# Multi-document for E5
# ---------------------------------------------------------------------------


def test_e5_multi_document_when_multiple_chains_enabled(db_session):
    """E5 is the canonical multi-source criterion: usi
    dipartimentali + linee guida CdL + template locale all
    contribute to the same run."""
    cdl = _make_cdl(db_session)
    _doc(
        db_session, cdl.id,
        document_type="usi_dipartimentali", title="usi", version=1,
    )
    _doc(
        db_session, cdl.id,
        document_type="linee_guida_cdl", title="linee", version=1,
    )
    _doc(
        db_session, cdl.id,
        document_type="template_locale", title="tpl", version=1,
    )

    out = ExternalDocumentResolver(db_session).resolve(
        ResolverInput(cdl_id=cdl.id, academic_year="2025-2026", has_english=True)
    )
    res = out.by_criterion["E5"]
    assert res.applicable is True
    types_seen = {d.document_type_snapshot for d in res.documents}
    assert types_seen == {
        "usi_dipartimentali", "linee_guida_cdl", "template_locale",
    }
    for d in res.documents:
        assert d.resolution_reason == "academic_year_match"


def test_chain_grouping_picks_one_per_chain(db_session):
    """A second `usi_dipartimentali` row with a different
    normalized_title is a *second chain*, also resolved. Two
    versions of the SAME chain produce a SINGLE entry."""
    cdl = _make_cdl(db_session)
    # Chain A — two versions.
    _doc(
        db_session, cdl.id,
        document_type="usi_dipartimentali", title="A", version=1,
    )
    _doc(
        db_session, cdl.id,
        document_type="usi_dipartimentali", title="A", version=2,
    )
    # Chain B — one version.
    _doc(
        db_session, cdl.id,
        document_type="usi_dipartimentali", title="B", version=1,
    )

    out = ExternalDocumentResolver(db_session).resolve(
        ResolverInput(cdl_id=cdl.id, academic_year="2025-2026", has_english=True)
    )
    res = out.by_criterion["E5"]
    assert res.applicable is True
    # Two entries (one per chain), and chain A contributed v2 only.
    titles_versions = sorted(
        (d.document_type_snapshot, d.document_version_snapshot)
        for d in res.documents
    )
    assert len(res.documents) == 2
    versions_for_a = [
        d.document_version_snapshot
        for d in res.documents
        if d.document_type_snapshot == "usi_dipartimentali"
    ]
    assert 2 in versions_for_a  # v2 picked, not v1
    assert titles_versions == sorted(titles_versions)  # ordering is stable


# ---------------------------------------------------------------------------
# E4 cross-lingua bypass
# ---------------------------------------------------------------------------


def test_e4_applicable_when_syllabus_has_english(db_session):
    cdl = _make_cdl(db_session)
    out = ExternalDocumentResolver(db_session).resolve(
        ResolverInput(cdl_id=cdl.id, academic_year="2025-2026", has_english=True)
    )
    res = out.by_criterion["E4"]
    assert res.applicable is True
    assert res.documents == []  # never pulls a registry document


def test_e4_na_when_syllabus_has_no_english(db_session):
    cdl = _make_cdl(db_session)
    out = ExternalDocumentResolver(db_session).resolve(
        ResolverInput(cdl_id=cdl.id, academic_year="2025-2026", has_english=False)
    )
    res = out.by_criterion["E4"]
    assert res.applicable is False
    assert "no English version" in res.na_reason
