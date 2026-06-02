"""Schema / persistence tests for the expanded EvaluationResult model.

Verifies that the SQLAlchemy model accepts the full set of columns
introduced in Phase 5.4.H, that the Syllabus relationship is wired
correctly (``Syllabus.evaluations`` <-> ``EvaluationResult.syllabus``)
and that cascade deletes work as advertised.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import CorsoDiLaurea, Department, EvaluationResult, Syllabus


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()
        Base.metadata.drop_all(engine)


def _seed_syllabus(session) -> Syllabus:
    now = datetime(2026, 5, 17, tzinfo=timezone.utc)
    dept = Department(
        id=1,
        name="Dipartimento di Matematica e Informatica",
        area="Scientifica",
        website_url="https://x",
        email="dmi@example",
        phone="000",
        director="X",
        scraped_at=now,
    )
    cdl = CorsoDiLaurea(
        id=1,
        department_id=1,
        name="LM-18 Informatica",
        code="LM-18",
        type="laurea_magistrale",
        academic_year="2025/2026",
        url="https://x",
        scraped_at=now,
    )
    session.add_all([dept, cdl])
    session.flush()
    syllabus = Syllabus(
        cdl_id=1,
        seuid="SEUID-TEST",
        course_code="9999",
        course_name="Deep Learning",
        teacher="Mario Rossi",
        academic_year="2025/2026",
        year_of_study="2",
        url_it="https://x/it",
        url_en="https://x/en",
        has_english=True,
        scraped_at=now,
        learning_outcomes_it="RA narrativi",
        dublin_knowledge_it="Conoscenze.",
        dublin_applying_it="Applicare.",
        dublin_judgement_it="Giudicare.",
        dublin_communication_it="Comunicare.",
        dublin_learning_it="Imparare.",
        teaching_methods_it="Lezioni.",
        prerequisites_it="Algebra.",
        attendance_it="Non obbligatoria.",
        course_content_it="Topic A.",
        references_it="CLRS.",
        assessment_methods_it="Esame.",
        sample_questions_it="Domanda.",
    )
    session.add(syllabus)
    session.flush()
    return syllabus


def _make_record(syllabus: Syllabus, **overrides) -> EvaluationResult:
    defaults = dict(
        evaluation_uuid="11111111-2222-3333-4444-555555555555",
        syllabus_id=syllabus.id,
        syllabus_seuid_snapshot=syllabus.seuid,
        course_name_snapshot=syllabus.course_name,
        status="completed",
        started_at=datetime(2026, 5, 17, 12, 0, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 5, 17, 12, 2, 30, tzinfo=timezone.utc),
        duration_ms=150_000,
        llm_model="gemini-2.5-flash",
        embedding_model="gemini-embedding-001",
        embedding_dim=3072,
        llm_temperature=0.1,
        llm_max_output_tokens=8192,
        rag_top_k=5,
        rag_final_k=3,
        rag_similarity_threshold=0.6,
        gcp_project_id="test-project",
        gcp_location="europe-west1",
        prompt_versions={"A1": "a1_v5", "A2": "a2_v1", "A3": "a3_v1", "A4": "a4_v2"},
        core_score=1.78,
        coverage=1.0,
        criterion_scores={f"C{i}": 2 for i in range(1, 10)},
        na_criteria=[],
        agent_outputs={"A1": {"agent_code": "A1", "judgments": []}},
        agent_errors=None,
        retrieved_chunks={"C1": [{"chunk_id": "lg_unict__2__0", "similarity_score": 0.79}]},
        final_report="# Report di valutazione",
    )
    defaults.update(overrides)
    return EvaluationResult(**defaults)


def test_evaluation_result_can_be_persisted_with_full_schema(session):
    syllabus = _seed_syllabus(session)
    record = _make_record(syllabus)
    session.add(record)
    session.commit()

    fetched = session.query(EvaluationResult).filter_by(evaluation_uuid=record.evaluation_uuid).one()
    assert fetched.syllabus_id == syllabus.id
    assert fetched.syllabus_seuid_snapshot == "SEUID-TEST"
    assert fetched.course_name_snapshot == "Deep Learning"
    assert fetched.llm_model == "gemini-2.5-flash"
    assert fetched.embedding_dim == 3072
    assert fetched.gcp_project_id == "test-project"
    assert fetched.prompt_versions == {"A1": "a1_v5", "A2": "a2_v1", "A3": "a3_v1", "A4": "a4_v2"}
    assert fetched.core_score == 1.78
    assert fetched.coverage == 1.0
    assert fetched.criterion_scores == {f"C{i}": 2 for i in range(1, 10)}
    assert fetched.retrieved_chunks["C1"][0]["chunk_id"] == "lg_unict__2__0"
    assert fetched.duration_ms == 150_000
    assert fetched.final_report.startswith("# Report")


def test_evaluation_result_uuid_must_be_unique(session):
    from sqlalchemy.exc import IntegrityError

    syllabus = _seed_syllabus(session)
    session.add(_make_record(syllabus))
    session.commit()
    session.add(_make_record(syllabus))  # same UUID
    with pytest.raises(IntegrityError):
        session.commit()


def test_syllabus_has_evaluations_back_populates(session):
    syllabus = _seed_syllabus(session)
    a = _make_record(syllabus, evaluation_uuid="aaaa")
    b = _make_record(
        syllabus,
        evaluation_uuid="bbbb",
        started_at=datetime(2026, 5, 17, 13, 0, 0, tzinfo=timezone.utc),
    )
    session.add_all([a, b])
    session.commit()

    # Re-fetch through the syllabus relationship.
    fetched = session.query(Syllabus).filter_by(seuid="SEUID-TEST").one()
    uuids = {ev.evaluation_uuid for ev in fetched.evaluations}
    assert uuids == {"aaaa", "bbbb"}


def test_cascade_delete_removes_evaluations(session):
    syllabus = _seed_syllabus(session)
    session.add(_make_record(syllabus))
    session.commit()
    assert session.query(EvaluationResult).count() == 1

    session.delete(syllabus)
    session.commit()
    assert session.query(EvaluationResult).count() == 0


def test_pending_record_allows_null_results(session):
    """A pending record can be persisted with the result columns null."""
    syllabus = _seed_syllabus(session)
    record = _make_record(
        syllabus,
        status="pending",
        finished_at=None,
        duration_ms=None,
        core_score=None,
        coverage=None,
        criterion_scores=None,
        na_criteria=None,
        agent_outputs=None,
        agent_errors=None,
        retrieved_chunks=None,
        final_report=None,
    )
    session.add(record)
    session.commit()

    fetched = session.query(EvaluationResult).filter_by(evaluation_uuid=record.evaluation_uuid).one()
    assert fetched.status == "pending"
    assert fetched.finished_at is None
    assert fetched.core_score is None
