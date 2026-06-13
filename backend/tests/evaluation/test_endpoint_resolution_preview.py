"""Tests for the Phase 9.E.1 resolution-preview endpoint and the
``selected_document_ids`` validation on ``POST /api/evaluate/{seuid}``.

These tests bypass the LangGraph orchestrator and the resolver's
LLM dependencies entirely: they seed Department + CdL + Syllabus
+ LocalDocument rows directly, then hit the HTTP endpoints and
assert the response shape and the validation error semantics.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.evaluation import get_async_service
from app.config import Settings
from app.database import Base
from app.evaluation.async_service import AsyncEvaluationService
from app.evaluation.registry import EvaluationRegistry
from app.evaluation.service import EvaluationService
from app.main import app
from app.models import CorsoDiLaurea, Department, Syllabus
from app.models.local_document import LocalDocument


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


SEUID = "SEUID-9E1"


def _seed_db(Session, *, has_english: bool = True, academic_year: str = "2025/2026"):
    now = datetime(2026, 6, 12, tzinfo=timezone.utc)
    with Session() as session:
        session.add_all(
            [
                Department(
                    id=1, name="DMI", area="Scientifica",
                    website_url="https://x", email="d@x", phone="0",
                    director="X", scraped_at=now,
                ),
                CorsoDiLaurea(
                    id=1, department_id=1, name="LM-18", code="LM-18",
                    type="laurea_magistrale", academic_year="2025/2026",
                    url="https://x", scraped_at=now,
                ),
                CorsoDiLaurea(
                    id=2, department_id=1, name="OTHER-CDL", code="L-31",
                    type="laurea_triennale", academic_year="2025/2026",
                    url="https://y", scraped_at=now,
                ),
            ],
        )
        session.flush()
        session.add(
            Syllabus(
                cdl_id=1, seuid=SEUID, course_code="9999",
                course_name="Test course", teacher="MR",
                academic_year=academic_year, year_of_study="2",
                url_it="https://x/it", url_en="https://x/en",
                has_english=has_english, scraped_at=now,
                learning_outcomes_it="RA",
                dublin_knowledge_it="K", dublin_applying_it="A",
                dublin_judgement_it="J", dublin_communication_it="C",
                dublin_learning_it="L", teaching_methods_it="L",
                prerequisites_it="P", attendance_it="A",
                course_content_it="C", references_it="R",
                assessment_methods_it="V", sample_questions_it="E",
            ),
        )
        session.commit()


_UNSET = object()


def _seed_local_document(
    Session, *,
    doc_id: int,
    title: str,
    document_type: str = "sua_cds",
    enabled_criteria=_UNSET,
    academic_year: str = "2025-2026",
    cdl_id: int = 1,
    status: str = "indexed",
    deleted: bool = False,
    version: int = 1,
) -> None:
    """Seed one LocalDocument. ``enabled_criteria`` defaults to ``["E1"]``
    but accepts the explicit empty list ``[]`` to test the
    ``no_enabled_criteria`` validation branch."""
    if enabled_criteria is _UNSET:
        enabled_criteria = ["E1"]
    now = datetime(2026, 6, 12, tzinfo=timezone.utc)
    with Session() as session:
        session.add(
            LocalDocument(
                id=doc_id,
                cdl_id=cdl_id,
                document_type=document_type,
                title=title,
                normalized_title=title.lower(),
                version=version,
                file_hash=f"hash-{doc_id}",
                file_path=f"/p/{doc_id}.md",
                file_extension="md",
                file_size=1024,
                academic_year=academic_year,
                enabled_criteria=enabled_criteria,
                status=status,
                uploaded_at=now,
                indexed_at=now if status == "indexed" else None,
                deleted_at=now if deleted else None,
            ),
        )
        session.commit()


def _noop_invoker(initial_state, *, progress_publisher=None):
    return {**initial_state, "status": "completed"}


@pytest.fixture()
def client_and_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(gcp_project_id="p", gcp_location="europe-west1")
    sync = EvaluationService(
        session_factory=Session, graph_invoker=_noop_invoker, settings=settings,
    )
    async_svc = AsyncEvaluationService(
        sync_service=sync, registry=EvaluationRegistry(), settings=settings,
    )
    app.dependency_overrides[get_async_service] = lambda: async_svc
    with TestClient(app) as client:
        yield client, Session
    app.dependency_overrides.clear()


# ===========================================================================
# GET /api/syllabi/{seuid}/resolution-preview
# ===========================================================================


def test_preview_404_when_syllabus_missing(client_and_session):
    client, _ = client_and_session
    r = client.get("/api/syllabi/DOES-NOT-EXIST/resolution-preview")
    assert r.status_code == 404


def test_preview_empty_registry_renders_resolver_na_and_e4_applicable(
    client_and_session,
):
    client, Session = client_and_session
    _seed_db(Session)

    body = client.get(f"/api/syllabi/{SEUID}/resolution-preview").json()
    assert body["seuid"] == SEUID
    assert body["cdl_id"] == 1
    assert body["has_english"] is True
    by_crit = body["by_criterion"]

    # E1/E2/E3/E5 are registry-served but have no documents → "none"
    # with na_reason from the resolver. The frontend renders this
    # as "no documents available".
    for code in ("E1", "E2", "E3", "E5"):
        c = by_crit[code]
        assert c["criterion_code"] == code
        assert c["served_by"] == "registry"
        assert c["applicable"] is False
        assert c["na_reason"]
        assert c["candidates"] == []

    # E4 is syllabus-served and applicable when has_english=True.
    e4 = by_crit["E4"]
    assert e4["served_by"] == "syllabus"
    assert e4["applicable"] is True
    assert e4["candidates"] == []


def test_preview_e4_none_when_has_english_false(client_and_session):
    client, Session = client_and_session
    _seed_db(Session, has_english=False)
    body = client.get(f"/api/syllabi/{SEUID}/resolution-preview").json()
    e4 = body["by_criterion"]["E4"]
    assert e4["served_by"] == "none"
    assert e4["applicable"] is False
    assert e4["na_reason"]


def test_preview_flags_auto_resolved_candidate(client_and_session):
    """The resolver's pick (one per ``(cdl, type, normalized_title)``
    chain) is flagged ``is_auto_resolved=True`` with the
    ``resolution_reason``; the older versions of the same chain
    leave those fields empty.
    """
    client, Session = client_and_session
    _seed_db(Session)
    # Same chain (cdl=1, type=sua_cds, normalized_title='sua-cds') with
    # two versions: v2 matches the syllabus's academic year, v1 is the
    # previous year's edition.
    _seed_local_document(
        Session, doc_id=10, title="SUA-CdS",
        document_type="sua_cds", enabled_criteria=["E1"],
        academic_year="2024-2025", version=1,
    )
    _seed_local_document(
        Session, doc_id=11, title="SUA-CdS",
        document_type="sua_cds", enabled_criteria=["E1"],
        academic_year="2025-2026", version=2,
    )

    body = client.get(f"/api/syllabi/{SEUID}/resolution-preview").json()
    e1_cands = body["by_criterion"]["E1"]["candidates"]
    assert len(e1_cands) == 2
    # Order is by local_document_id asc.
    assert [c["local_document_id"] for c in e1_cands] == [10, 11]
    # Doc 11 wins on academic_year_match (single pick per chain).
    by_id = {c["local_document_id"]: c for c in e1_cands}
    assert by_id[11]["is_auto_resolved"] is True
    assert by_id[11]["resolution_reason"] == "academic_year_match"
    assert by_id[10]["is_auto_resolved"] is False
    assert by_id[10]["resolution_reason"] is None
    assert all(c["selectable"] is True for c in e1_cands)


def test_preview_marks_soft_deleted_as_not_selectable(client_and_session):
    client, Session = client_and_session
    _seed_db(Session)
    _seed_local_document(
        Session, doc_id=10, title="SUA archiviata",
        enabled_criteria=["E1"], deleted=True,
    )
    body = client.get(f"/api/syllabi/{SEUID}/resolution-preview").json()
    e1_cands = body["by_criterion"]["E1"]["candidates"]
    # Visible for transparency, but NOT selectable for new runs.
    assert len(e1_cands) == 1
    c = e1_cands[0]
    assert c["selectable"] is False
    assert c["deleted_at"] is not None


def test_preview_excludes_non_indexed_candidates(client_and_session):
    client, Session = client_and_session
    _seed_db(Session)
    _seed_local_document(
        Session, doc_id=10, title="SUA indicizzata",
        enabled_criteria=["E1"], status="indexed",
    )
    _seed_local_document(
        Session, doc_id=11, title="SUA in indicizzazione",
        enabled_criteria=["E1"], status="indexing",
    )
    body = client.get(f"/api/syllabi/{SEUID}/resolution-preview").json()
    ids = [c["local_document_id"] for c in body["by_criterion"]["E1"]["candidates"]]
    assert ids == [10]


def test_preview_buckets_documents_by_criterion(client_and_session):
    client, Session = client_and_session
    _seed_db(Session)
    _seed_local_document(
        Session, doc_id=10, title="SUA",
        document_type="sua_cds", enabled_criteria=["E1"],
    )
    _seed_local_document(
        Session, doc_id=20, title="Reg",
        document_type="regolamento_didattico", enabled_criteria=["E3"],
    )
    _seed_local_document(
        Session, doc_id=30, title="Usi LM-18",
        document_type="usi_dipartimentali", enabled_criteria=["E5"],
    )

    body = client.get(f"/api/syllabi/{SEUID}/resolution-preview").json()
    by_crit = body["by_criterion"]
    assert [c["local_document_id"] for c in by_crit["E1"]["candidates"]] == [10]
    assert [c["local_document_id"] for c in by_crit["E3"]["candidates"]] == [20]
    assert [c["local_document_id"] for c in by_crit["E5"]["candidates"]] == [30]
    assert by_crit["E2"]["candidates"] == []  # no matrix doc


# ===========================================================================
# POST /api/evaluate/{seuid} with selected_document_ids
# ===========================================================================


def test_evaluate_post_without_body_still_works(client_and_session):
    """Legacy behaviour: no body → resolver picks automatically."""
    client, Session = client_and_session
    _seed_db(Session)
    r = client.post(f"/api/evaluate/{SEUID}")
    assert r.status_code == 202
    assert r.json()["evaluation_uuid"]


def test_evaluate_post_with_explicit_selection_succeeds(client_and_session):
    client, Session = client_and_session
    _seed_db(Session)
    _seed_local_document(
        Session, doc_id=10, title="SUA",
        document_type="sua_cds", enabled_criteria=["E1"],
    )
    r = client.post(
        f"/api/evaluate/{SEUID}",
        json={"selected_document_ids": [10]},
    )
    assert r.status_code == 202


def test_evaluate_post_rejects_unknown_id(client_and_session):
    client, Session = client_and_session
    _seed_db(Session)
    r = client.post(
        f"/api/evaluate/{SEUID}",
        json={"selected_document_ids": [9999]},
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["code"] == "unknown"


def test_evaluate_post_rejects_duplicates(client_and_session):
    client, Session = client_and_session
    _seed_db(Session)
    _seed_local_document(
        Session, doc_id=10, title="SUA", enabled_criteria=["E1"],
    )
    r = client.post(
        f"/api/evaluate/{SEUID}",
        json={"selected_document_ids": [10, 10]},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "duplicate"


def test_evaluate_post_rejects_archived(client_and_session):
    client, Session = client_and_session
    _seed_db(Session)
    _seed_local_document(
        Session, doc_id=10, title="SUA",
        enabled_criteria=["E1"], deleted=True,
    )
    r = client.post(
        f"/api/evaluate/{SEUID}",
        json={"selected_document_ids": [10]},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "archived"


def test_evaluate_post_rejects_non_indexed(client_and_session):
    client, Session = client_and_session
    _seed_db(Session)
    _seed_local_document(
        Session, doc_id=10, title="SUA",
        enabled_criteria=["E1"], status="indexing",
    )
    r = client.post(
        f"/api/evaluate/{SEUID}",
        json={"selected_document_ids": [10]},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "not_indexed"


def test_evaluate_post_rejects_wrong_cdl(client_and_session):
    client, Session = client_and_session
    _seed_db(Session)
    _seed_local_document(
        Session, doc_id=10, title="SUA",
        enabled_criteria=["E1"], cdl_id=2,  # other CdL
    )
    r = client.post(
        f"/api/evaluate/{SEUID}",
        json={"selected_document_ids": [10]},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "wrong_cdl"


def test_evaluate_post_rejects_doc_without_enabled_criteria(client_and_session):
    client, Session = client_and_session
    _seed_db(Session)
    _seed_local_document(
        Session, doc_id=10, title="SUA orfana",
        enabled_criteria=[],
    )
    r = client.post(
        f"/api/evaluate/{SEUID}",
        json={"selected_document_ids": [10]},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "no_enabled_criteria"


def test_evaluate_post_returns_404_when_syllabus_missing(client_and_session):
    client, _ = client_and_session
    r = client.post(
        "/api/evaluate/DOES-NOT-EXIST",
        json={"selected_document_ids": [10]},
    )
    assert r.status_code == 404
