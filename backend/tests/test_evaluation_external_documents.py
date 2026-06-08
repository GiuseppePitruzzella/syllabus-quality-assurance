"""Tests for the EvaluationExternalDocument audit table (Phase 9.B.1).

Asserts the table exists with the expected indices / constraints,
the FK policies are honoured (CASCADE on evaluation_result_id,
RESTRICT on local_document_id), and the unique constraint per
(run, criterion, document) is enforced.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.models import (
    CorsoDiLaurea,
    Department,
    EvaluationExternalDocument,
    EvaluationResult,
    LocalDocument,
    Syllabus,
)


def _make_dept(db):
    dept = Department(
        name="DMI", area="Scienze", website_url="https://x",
        email="x@y", phone="1", director="d",
        scraped_at=datetime.now(timezone.utc),
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


def _make_cdl(db, dept_id):
    cdl = CorsoDiLaurea(
        department_id=dept_id, name="Informatica", code="lm-18",
        type="Magistrale", academic_year=None, url="https://x/c",
        scraped_at=datetime.now(timezone.utc),
    )
    db.add(cdl)
    db.commit()
    db.refresh(cdl)
    return cdl


def _make_syllabus(db, cdl_id):
    syllabus = Syllabus(
        cdl_id=cdl_id,
        seuid="lm18-test-2025",
        course_code="TEST-001",
        course_name="Test Course",
        teacher="docente",
        academic_year="2025-2026",
        year_of_study="1",
        url_it="https://example.com/it",
        url_en="https://example.com/en",
        has_english=True,
        learning_outcomes_it="ra",
        dublin_knowledge_it="",
        dublin_applying_it="",
        dublin_judgement_it="",
        dublin_communication_it="",
        dublin_learning_it="",
        teaching_methods_it="",
        prerequisites_it="",
        attendance_it="",
        course_content_it="",
        references_it="",
        assessment_methods_it="",
        sample_questions_it="",
        scraped_at=datetime.now(timezone.utc),
    )
    db.add(syllabus)
    db.commit()
    db.refresh(syllabus)
    return syllabus


def _make_evaluation(db, syllabus_id, uuid="test-uuid-1"):
    ev = EvaluationResult(
        evaluation_uuid=uuid,
        syllabus_id=syllabus_id,
        syllabus_seuid_snapshot="lm18-test-2025",
        course_name_snapshot="Test Course",
        status="completed",
        llm_model="gemini-2.5-flash",
        embedding_model="gemini-embedding-001",
        embedding_dim=3072,
        llm_temperature=0.1,
        llm_max_output_tokens=8192,
        rag_top_k=5,
        rag_final_k=3,
        rag_similarity_threshold=0.6,
        gcp_project_id="proj-test",
        gcp_location="europe-west1",
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def _make_local_doc(db, cdl_id, *, document_type="sua_cds", title="t"):
    doc = LocalDocument(
        cdl_id=cdl_id,
        document_type=document_type,
        academic_year="2025-2026",
        title=title,
        normalized_title=title.lower(),
        file_path=f"{cdl_id}/x.md",
        file_extension=".md",
        file_hash="hash" + title,
        file_size=10,
        version=1,
        enabled_criteria=["E1"],
        status="indexed",
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_table_is_created(db_session):
    inspector = inspect(db_session.bind)
    assert "evaluation_external_documents" in inspector.get_table_names()


def test_table_has_expected_indices(db_session):
    inspector = inspect(db_session.bind)
    names = {ix["name"] for ix in inspector.get_indexes("evaluation_external_documents")}
    assert "ix_evaluation_external_docs_run_crit" in names
    assert "ix_evaluation_external_docs_local_doc" in names
    # The UNIQUE constraint is also reflected in indexes for SQLite.
    uniques = {
        uc["name"]
        for uc in inspector.get_unique_constraints("evaluation_external_documents")
    }
    assert "uq_evaluation_external_docs_run_crit_doc" in uniques


def test_insert_happy_path(db_session):
    dept = _make_dept(db_session)
    cdl = _make_cdl(db_session, dept.id)
    syl = _make_syllabus(db_session, cdl.id)
    ev = _make_evaluation(db_session, syl.id)
    doc = _make_local_doc(db_session, cdl.id)

    ref = EvaluationExternalDocument(
        evaluation_result_id=ev.id,
        local_document_id=doc.id,
        criterion_code="E1",
        document_version_snapshot=doc.version,
        file_hash_snapshot=doc.file_hash,
        document_type_snapshot=doc.document_type,
        resolution_reason="academic_year_match",
    )
    db_session.add(ref)
    db_session.commit()
    db_session.refresh(ref)
    assert ref.id is not None
    assert ref.created_at is not None


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------


def test_unique_per_run_criterion_document(db_session):
    dept = _make_dept(db_session)
    cdl = _make_cdl(db_session, dept.id)
    syl = _make_syllabus(db_session, cdl.id)
    ev = _make_evaluation(db_session, syl.id)
    doc = _make_local_doc(db_session, cdl.id)

    db_session.add(
        EvaluationExternalDocument(
            evaluation_result_id=ev.id,
            local_document_id=doc.id,
            criterion_code="E1",
            document_version_snapshot=1,
            file_hash_snapshot="h",
            document_type_snapshot="sua_cds",
            resolution_reason="academic_year_match",
        )
    )
    db_session.commit()

    db_session.add(
        EvaluationExternalDocument(
            evaluation_result_id=ev.id,
            local_document_id=doc.id,
            criterion_code="E1",
            document_version_snapshot=1,
            file_hash_snapshot="h",
            document_type_snapshot="sua_cds",
            resolution_reason="explicit_selection",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_same_run_same_criterion_different_documents_allowed(db_session):
    """E5 typically pulls multiple documents for the same run/criterion;
    the unique key includes local_document_id so this is legal."""
    dept = _make_dept(db_session)
    cdl = _make_cdl(db_session, dept.id)
    syl = _make_syllabus(db_session, cdl.id)
    ev = _make_evaluation(db_session, syl.id)
    doc_a = _make_local_doc(
        db_session, cdl.id, document_type="usi_dipartimentali", title="a",
    )
    doc_b = _make_local_doc(
        db_session, cdl.id, document_type="linee_guida_cdl", title="b",
    )

    for d in (doc_a, doc_b):
        db_session.add(
            EvaluationExternalDocument(
                evaluation_result_id=ev.id,
                local_document_id=d.id,
                criterion_code="E5",
                document_version_snapshot=d.version,
                file_hash_snapshot=d.file_hash,
                document_type_snapshot=d.document_type,
                resolution_reason="academic_year_match",
            )
        )
    db_session.commit()  # must not raise

    refs = (
        db_session.query(EvaluationExternalDocument)
        .filter(EvaluationExternalDocument.evaluation_result_id == ev.id)
        .filter(EvaluationExternalDocument.criterion_code == "E5")
        .all()
    )
    assert len(refs) == 2


def test_cascade_delete_from_evaluation_result(db_session):
    """Deleting an EvaluationResult cascades on the join rows."""
    from sqlalchemy import text

    dept = _make_dept(db_session)
    cdl = _make_cdl(db_session, dept.id)
    syl = _make_syllabus(db_session, cdl.id)
    ev = _make_evaluation(db_session, syl.id)
    doc = _make_local_doc(db_session, cdl.id)

    db_session.add(
        EvaluationExternalDocument(
            evaluation_result_id=ev.id,
            local_document_id=doc.id,
            criterion_code="E1",
            document_version_snapshot=1,
            file_hash_snapshot="h",
            document_type_snapshot="sua_cds",
            resolution_reason="academic_year_match",
        )
    )
    db_session.commit()

    # SQLite ignores ON DELETE ... clauses unless `PRAGMA foreign_keys`
    # is on. The production app enables it via the database module;
    # we mirror that here so the cascade actually fires.
    db_session.execute(text("PRAGMA foreign_keys=ON"))
    db_session.delete(ev)
    db_session.commit()

    leftover = db_session.query(EvaluationExternalDocument).count()
    assert leftover == 0
    # And the registry document is still alive (RESTRICT shielded it).
    assert (
        db_session.query(LocalDocument).filter(LocalDocument.id == doc.id).first()
        is not None
    )


def test_restrict_delete_on_referenced_local_document(db_session):
    """Phase 9.B.1: the DB itself refuses to drop a registry row that
    any audit reference points at. The API-level soft-delete in
    Phase 9.B.3 sits on top of this guard."""
    dept = _make_dept(db_session)
    cdl = _make_cdl(db_session, dept.id)
    syl = _make_syllabus(db_session, cdl.id)
    ev = _make_evaluation(db_session, syl.id)
    doc = _make_local_doc(db_session, cdl.id)

    db_session.add(
        EvaluationExternalDocument(
            evaluation_result_id=ev.id,
            local_document_id=doc.id,
            criterion_code="E1",
            document_version_snapshot=1,
            file_hash_snapshot="h",
            document_type_snapshot="sua_cds",
            resolution_reason="academic_year_match",
        )
    )
    db_session.commit()

    # SQLite enforces FK only when PRAGMA foreign_keys is ON. We
    # enable it explicitly here so the RESTRICT clause is exercised.
    db_session.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys=ON"))
    db_session.delete(doc)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
