"""Tests for the Phase 9.C.5.1 service additions.

``EvaluationService.create_pending_run`` now:
  * runs the :class:`ExternalDocumentResolver` inside the same
    transaction that creates the pending ``EvaluationResult`` row;
  * inserts one ``EvaluationExternalDocument`` audit row per
    *resolved* document (E1 / E2 / E3 / E5; never E4);
  * carries the resolver verdict and the ``cdl_id`` on the
    returned :class:`PendingRun` so 9.C.5.2 can hand them to A5
    without re-querying;
  * rolls back the whole block on any error — there must never be
    an orphan pending row, nor an orphan audit row.

These tests work entirely offline against an in-memory SQLite
session factory. They never touch Vertex, Chroma or the graph;
the graph invoker is a no-op fake.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base
from app.evaluation.service import EvaluationService
from app.models import (
    CorsoDiLaurea,
    Department,
    EvaluationResult,
    Syllabus,
)
from app.models.evaluation_external_document import EvaluationExternalDocument
from app.models.local_document import LocalDocument


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield Session
    finally:
        Base.metadata.drop_all(engine)


@pytest.fixture()
def fake_settings():
    return Settings(gcp_project_id="test-project", gcp_location="europe-west1")


def _seed_syllabus(session_factory, *, has_english: bool = True) -> str:
    """Seed one syllabus and return its seuid."""
    now = datetime(2026, 5, 17, tzinfo=timezone.utc)
    with session_factory() as session:
        dept = Department(
            id=1, name="DMI", area="Scientifica", website_url="https://x",
            email="dmi@example", phone="000", director="X", scraped_at=now,
        )
        cdl = CorsoDiLaurea(
            id=1, department_id=1, name="LM-18", code="LM-18",
            type="laurea_magistrale", academic_year="2025/2026",
            url="https://x", scraped_at=now,
        )
        syllabus = Syllabus(
            cdl_id=1, seuid="SEUID-X", course_code="9999",
            course_name="Deep Learning", teacher="Mario Rossi",
            academic_year="2025/2026", year_of_study="2",
            url_it="https://x/it", url_en="https://x/en",
            has_english=has_english, scraped_at=now,
            learning_outcomes_it="RA",
            dublin_knowledge_it="K", dublin_applying_it="A",
            dublin_judgement_it="J", dublin_communication_it="C",
            dublin_learning_it="L", teaching_methods_it="Lezioni",
            prerequisites_it="Pre", attendance_it="Att",
            course_content_it="Cont", references_it="Ref",
            assessment_methods_it="Verifica", sample_questions_it="Esempi",
        )
        session.add_all([dept, cdl, syllabus])
        session.commit()
        return syllabus.seuid


def _seed_local_document(
    session_factory,
    *,
    document_type: str,
    enabled_criteria: list[str],
    academic_year: str = "2025-2026",
    cdl_id: int = 1,
    title: str = "Doc",
    version: int = 1,
) -> int:
    """Seed one indexed local document and return its id."""
    now = datetime(2026, 5, 17, tzinfo=timezone.utc)
    with session_factory() as session:
        doc = LocalDocument(
            cdl_id=cdl_id,
            document_type=document_type,
            title=title,
            normalized_title=title.lower(),
            version=version,
            file_hash=f"hash-{document_type}-{version}",
            file_path=f"/path/{document_type}.md",
            file_extension="md",
            file_size=1024,
            academic_year=academic_year,
            enabled_criteria=enabled_criteria,
            status="indexed",
            uploaded_at=now,
            indexed_at=now,
        )
        session.add(doc)
        session.commit()
        return doc.id


def _noop_invoker(initial_state, progress_publisher=None):  # pragma: no cover
    """Placeholder graph invoker. The C.5.1 tests never call it because
    they exercise ``create_pending_run`` only."""
    return {**initial_state, "status": "completed"}


def _service(session_factory, fake_settings) -> EvaluationService:
    return EvaluationService(
        session_factory=session_factory,
        graph_invoker=_noop_invoker,
        settings=fake_settings,
    )


# ---------------------------------------------------------------------------
# PendingRun shape
# ---------------------------------------------------------------------------


def test_create_pending_run_returns_resolver_output_and_cdl_id(
    session_factory, fake_settings,
):
    seuid = _seed_syllabus(session_factory)
    pending = _service(session_factory, fake_settings).create_pending_run(seuid)
    assert pending.cdl_id == 1
    # No local documents seeded → registry-served criteria hard-NA;
    # E4 is applicable (has_english=True).
    by_crit = pending.resolver_output.by_criterion
    assert by_crit["E1"].applicable is False
    assert by_crit["E2"].applicable is False
    assert by_crit["E3"].applicable is False
    assert by_crit["E4"].applicable is True
    assert by_crit["E5"].applicable is False


def test_create_pending_run_resolver_handles_has_english_false(
    session_factory, fake_settings,
):
    seuid = _seed_syllabus(session_factory, has_english=False)
    pending = _service(session_factory, fake_settings).create_pending_run(seuid)
    assert pending.resolver_output.by_criterion["E4"].applicable is False


# ---------------------------------------------------------------------------
# Audit-row persistence
# ---------------------------------------------------------------------------


def test_create_pending_run_persists_audit_rows_for_resolved_documents(
    session_factory, fake_settings,
):
    seuid = _seed_syllabus(session_factory)
    sua_id = _seed_local_document(
        session_factory, document_type="sua_cds", enabled_criteria=["E1"],
        title="SUA-CdS 2025-2026",
    )
    reg_id = _seed_local_document(
        session_factory, document_type="regolamento_didattico",
        enabled_criteria=["E3"], title="Regolamento 2025-2026",
    )
    pending = _service(session_factory, fake_settings).create_pending_run(seuid)

    with session_factory() as session:
        record = (
            session.query(EvaluationResult)
            .filter_by(evaluation_uuid=pending.evaluation_uuid)
            .one()
        )
        audit_rows = (
            session.query(EvaluationExternalDocument)
            .filter_by(evaluation_result_id=record.id)
            .all()
        )
        rows_by_code = {row.criterion_code: row for row in audit_rows}

    assert set(rows_by_code.keys()) == {"E1", "E3"}
    assert rows_by_code["E1"].local_document_id == sua_id
    assert rows_by_code["E1"].document_type_snapshot == "sua_cds"
    assert rows_by_code["E1"].file_hash_snapshot.startswith("hash-sua_cds")
    assert rows_by_code["E3"].local_document_id == reg_id
    assert rows_by_code["E3"].document_type_snapshot == "regolamento_didattico"


def test_create_pending_run_never_persists_an_audit_row_for_e4(
    session_factory, fake_settings,
):
    """E4 is served by the syllabus itself — no audit row, ever."""
    seuid = _seed_syllabus(session_factory)
    # No registry doc → registry-served criteria NA; E4 applicable.
    pending = _service(session_factory, fake_settings).create_pending_run(seuid)
    with session_factory() as session:
        rows = (
            session.query(EvaluationExternalDocument)
            .filter_by(
                evaluation_result_id=session.query(EvaluationResult)
                .filter_by(evaluation_uuid=pending.evaluation_uuid)
                .one()
                .id,
            )
            .all()
        )
    # E4 was the only applicable criterion → zero audit rows.
    assert rows == []
    assert pending.resolver_output.by_criterion["E4"].applicable is True


def test_create_pending_run_skips_audit_row_for_hard_na_criteria(
    session_factory, fake_settings,
):
    """When a criterion has no eligible document, no audit row is written."""
    seuid = _seed_syllabus(session_factory)
    # Seed an E5 document — but NOT E1/E2/E3.
    e5_id = _seed_local_document(
        session_factory, document_type="usi_dipartimentali",
        enabled_criteria=["E5"], title="Usi LM-18",
    )
    _service(session_factory, fake_settings).create_pending_run(seuid)
    with session_factory() as session:
        codes = sorted(
            row[0]
            for row in session.query(EvaluationExternalDocument.criterion_code).all()
        )
        local_ids = sorted(
            row[0]
            for row in session.query(
                EvaluationExternalDocument.local_document_id,
            ).all()
        )
    assert codes == ["E5"]
    assert local_ids == [e5_id]


def test_create_pending_run_persists_multiple_e5_documents_in_one_run(
    session_factory, fake_settings,
):
    seuid = _seed_syllabus(session_factory)
    a = _seed_local_document(
        session_factory, document_type="usi_dipartimentali",
        enabled_criteria=["E5"], title="Usi dipartimentali", version=1,
    )
    b = _seed_local_document(
        session_factory, document_type="linee_guida_cdl",
        enabled_criteria=["E5"], title="Linee guida CdL", version=1,
    )
    pending = _service(session_factory, fake_settings).create_pending_run(seuid)
    with session_factory() as session:
        e5_ids = sorted(
            r[0]
            for r in session.query(EvaluationExternalDocument.local_document_id)
            .filter_by(criterion_code="E5")
            .all()
        )
    assert e5_ids == sorted([a, b])
    assert {d.local_document_id for d in pending.resolver_output.by_criterion["E5"].documents} == {a, b}


# ---------------------------------------------------------------------------
# Transactional rollback
# ---------------------------------------------------------------------------


def test_resolver_failure_rolls_back_pending_record_and_audit(
    monkeypatch, session_factory, fake_settings,
):
    """If the resolver raises, the pending row must NOT be visible
    after ``create_pending_run`` returns."""
    seuid = _seed_syllabus(session_factory)
    _seed_local_document(
        session_factory, document_type="sua_cds", enabled_criteria=["E1"],
        title="SUA",
    )

    from app.evaluation import service as service_mod

    def _boom(self, request):  # pragma: no cover — exception path
        raise RuntimeError("resolver exploded")

    monkeypatch.setattr(
        service_mod.ExternalDocumentResolver, "resolve", _boom,
    )

    svc = _service(session_factory, fake_settings)
    with pytest.raises(RuntimeError, match="resolver exploded"):
        svc.create_pending_run(seuid)

    # Neither the pending row nor any audit row survives.
    with session_factory() as session:
        assert session.query(EvaluationResult).count() == 0
        assert session.query(EvaluationExternalDocument).count() == 0


def test_audit_persist_failure_rolls_back_pending_record(
    monkeypatch, session_factory, fake_settings,
):
    """If audit-row insertion raises after the pending row is flushed,
    the whole transaction must roll back."""
    seuid = _seed_syllabus(session_factory)
    _seed_local_document(
        session_factory, document_type="sua_cds", enabled_criteria=["E1"],
        title="SUA",
    )

    def _boom(self, session, *, evaluation_result_id, resolver_output):
        raise RuntimeError("cannot persist audit row")

    monkeypatch.setattr(
        EvaluationService, "_persist_external_documents", _boom,
    )

    svc = _service(session_factory, fake_settings)
    with pytest.raises(RuntimeError, match="cannot persist audit row"):
        svc.create_pending_run(seuid)

    with session_factory() as session:
        assert session.query(EvaluationResult).count() == 0
        assert session.query(EvaluationExternalDocument).count() == 0


def test_pending_run_remains_atomic_under_fk_violation(
    session_factory, fake_settings,
):
    """Defensive: simulate an FK violation in the audit insert.

    A non-existent ``local_document_id`` snuck into the resolver
    output should NOT leave behind an orphan pending row. SQLite
    needs PRAGMA foreign_keys=ON for the FK to actually fire.
    """
    seuid = _seed_syllabus(session_factory)

    from app.evaluation import service as service_mod
    from app.local_documents.resolver import (
        CriterionResolution,
        ResolvedDocument,
        ResolverOutput,
    )

    def _resolve_with_phantom(self, request):
        return ResolverOutput(
            by_criterion={
                "E1": CriterionResolution(
                    criterion_code="E1", applicable=True,
                    documents=[
                        ResolvedDocument(
                            criterion_code="E1",
                            local_document_id=999_999,  # does not exist
                            document_version_snapshot=1,
                            file_hash_snapshot="x",
                            document_type_snapshot="sua_cds",
                            resolution_reason="academic_year_match",
                        ),
                    ],
                ),
                "E2": CriterionResolution(
                    criterion_code="E2", applicable=False, na_reason="x",
                ),
                "E3": CriterionResolution(
                    criterion_code="E3", applicable=False, na_reason="x",
                ),
                "E4": CriterionResolution(
                    criterion_code="E4", applicable=True, documents=[],
                ),
                "E5": CriterionResolution(
                    criterion_code="E5", applicable=False, na_reason="x",
                ),
            },
        )

    # Patch the resolver on the service module so the FK violation
    # fires when the service flushes the audit rows.
    monkeypatch_target = service_mod.ExternalDocumentResolver.resolve
    service_mod.ExternalDocumentResolver.resolve = _resolve_with_phantom
    try:
        svc = _service(session_factory, fake_settings)
        # Force FK constraints on for this session series.
        # On SQLite, FK enforcement is per-connection.
        with session_factory() as s:
            s.execute(text("PRAGMA foreign_keys=ON"))
            s.commit()
        with pytest.raises(Exception):  # noqa: BLE001 — IntegrityError or similar
            svc.create_pending_run(seuid)
    finally:
        service_mod.ExternalDocumentResolver.resolve = monkeypatch_target

    with session_factory() as session:
        session.execute(text("PRAGMA foreign_keys=ON"))
        assert session.query(EvaluationResult).count() == 0
        assert session.query(EvaluationExternalDocument).count() == 0


# ---------------------------------------------------------------------------
# Sanity: selected_document_ids passthrough
# ---------------------------------------------------------------------------


def test_selected_document_ids_pins_explicit_version(
    session_factory, fake_settings,
):
    seuid = _seed_syllabus(session_factory)
    v1 = _seed_local_document(
        session_factory, document_type="sua_cds", enabled_criteria=["E1"],
        title="SUA", academic_year="2024-2025", version=1,
    )
    v2 = _seed_local_document(
        session_factory, document_type="sua_cds", enabled_criteria=["E1"],
        title="SUA", academic_year="2025-2026", version=2,
    )
    # Without selected_document_ids, the resolver picks v2 (academic_year_match).
    pending = _service(session_factory, fake_settings).create_pending_run(seuid)
    assert {d.local_document_id for d in pending.resolver_output.by_criterion["E1"].documents} == {v2}
    # With selected_document_ids=[v1], the explicit selection wins.
    pending2 = _service(session_factory, fake_settings).create_pending_run(
        seuid, selected_document_ids=[v1],
    )
    docs = pending2.resolver_output.by_criterion["E1"].documents
    assert {d.local_document_id for d in docs} == {v1}
    assert docs[0].resolution_reason == "explicit_selection"


# ---------------------------------------------------------------------------
# Defence: audit-row count returned by the helper
# ---------------------------------------------------------------------------


def test_audit_persistence_helper_returns_count(
    session_factory, fake_settings,
):
    seuid = _seed_syllabus(session_factory)
    _seed_local_document(
        session_factory, document_type="sua_cds", enabled_criteria=["E1"],
        title="SUA",
    )
    _seed_local_document(
        session_factory, document_type="regolamento_didattico",
        enabled_criteria=["E3"], title="Reg",
    )
    pending = _service(session_factory, fake_settings).create_pending_run(seuid)
    with session_factory() as session:
        cnt = (
            session.query(EvaluationExternalDocument)
            .filter_by(
                evaluation_result_id=session.query(EvaluationResult)
                .filter_by(evaluation_uuid=pending.evaluation_uuid)
                .one().id,
            )
            .count()
        )
    assert cnt == 2


# ---------------------------------------------------------------------------
# Backwards compatibility
# ---------------------------------------------------------------------------


def test_pending_run_remains_a_frozen_dataclass(
    session_factory, fake_settings,
):
    """PendingRun stays immutable so the async layer can pass it
    safely across thread boundaries."""
    seuid = _seed_syllabus(session_factory)
    pending = _service(session_factory, fake_settings).create_pending_run(seuid)
    with pytest.raises(Exception):  # noqa: BLE001
        pending.cdl_id = 999  # type: ignore[misc]


def _pending_kwargs_dump(pending: Any) -> dict[str, Any]:
    return {
        "evaluation_uuid": pending.evaluation_uuid,
        "seuid": pending.seuid,
        "course_name": pending.course_name,
        "cdl_id": pending.cdl_id,
    }


def test_pending_run_carries_all_pre_existing_fields(
    session_factory, fake_settings,
):
    seuid = _seed_syllabus(session_factory)
    pending = _service(session_factory, fake_settings).create_pending_run(seuid)
    dump = _pending_kwargs_dump(pending)
    assert dump["seuid"] == seuid
    assert dump["course_name"] == "Deep Learning"
    assert isinstance(dump["evaluation_uuid"], str)
    assert dump["cdl_id"] == 1
