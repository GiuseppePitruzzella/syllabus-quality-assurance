"""Tests for the Phase 9.D.1 typed exposure of the extended-criteria
result and the audit-table view on ``GET /api/evaluations/{uuid}``.

These tests bypass the LangGraph orchestrator entirely: they seed
an ``EvaluationResult`` row + the relevant ``EvaluationExternalDocument``
audit rows + a ``LocalDocument`` directly into the in-memory DB,
then hit the HTTP endpoint and assert the response shape.

The invariants under test are exactly the user-contract decisions
fixed before 9.D.1:

  * ``extended_criteria_result`` is the compact, normalised payload —
    judgments and handler_prompt_versions are at TOP level, the raw
    ``agent_output`` envelope is dropped;
  * ``external_documents_used`` is sorted deterministically and is
    NEVER populated for E4;
  * a soft-deleted document still shows its title and
    ``deleted_at``;
  * legacy runs (no extended column, no audit rows) return
    ``extended_criteria_result == null`` and
    ``external_documents_used == []`` instead of crashing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

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
from app.models import CorsoDiLaurea, Department, EvaluationResult, Syllabus
from app.models.evaluation_external_document import EvaluationExternalDocument
from app.models.local_document import LocalDocument


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _seed_minimal_db(Session):
    """Seed Department + CdL + Syllabus and return the syllabus id."""
    now = datetime(2026, 6, 11, tzinfo=timezone.utc)
    with Session() as session:
        session.add_all(
            [
                Department(
                    id=1, name="DMI", area="Scientifica",
                    website_url="https://x", email="d@x",
                    phone="0", director="X", scraped_at=now,
                ),
                CorsoDiLaurea(
                    id=1, department_id=1, name="LM-18", code="LM-18",
                    type="laurea_magistrale", academic_year="2025/2026",
                    url="https://x", scraped_at=now,
                ),
            ]
        )
        session.flush()
        syl = Syllabus(
            cdl_id=1, seuid="SEUID-D1", course_code="9999",
            course_name="DL", teacher="MR",
            academic_year="2025/2026", year_of_study="2",
            url_it="https://x/it", url_en="https://x/en",
            has_english=True, scraped_at=now,
            learning_outcomes_it="RA",
            dublin_knowledge_it="K", dublin_applying_it="A",
            dublin_judgement_it="J", dublin_communication_it="C",
            dublin_learning_it="L", teaching_methods_it="L",
            prerequisites_it="P", attendance_it="A",
            course_content_it="C", references_it="R",
            assessment_methods_it="V", sample_questions_it="E",
        )
        session.add(syl)
        session.commit()
        return syl.id


def _seed_evaluation(Session, *, extended_dump=None) -> str:
    """Insert one EvaluationResult, return its uuid."""
    now = datetime(2026, 6, 11, tzinfo=timezone.utc)
    with Session() as session:
        evaluation = EvaluationResult(
            evaluation_uuid="uuid-d1",
            syllabus_id=1,
            syllabus_seuid_snapshot="SEUID-D1",
            course_name_snapshot="DL",
            status="completed",
            started_at=now,
            finished_at=now,
            duration_ms=1000,
            llm_model="gemini-2.5-flash",
            embedding_model="gemini-embedding-001",
            embedding_dim=3072,
            llm_temperature=0.1,
            llm_max_output_tokens=8192,
            rag_top_k=5,
            rag_final_k=3,
            rag_similarity_threshold=0.6,
            gcp_project_id="p",
            gcp_location="europe-west1",
            prompt_versions={
                "A1": "a1_v6", "A2": "a2_v1", "A3": "a3_v1",
                "A4": "a4_v10", "A5": "a5_v1",
            },
            core_score=2.0,
            coverage=1.0,
            criterion_scores={f"C{i}": 2 for i in range(1, 10)},
            na_criteria=[],
            agent_outputs=None,
            agent_errors=None,
            retrieved_chunks=None,
            final_report="# r",
            extended_criteria_result=extended_dump,
        )
        session.add(evaluation)
        session.commit()
        return evaluation.evaluation_uuid


def _seed_local_document(
    Session, *, doc_id: int, title: str, document_type: str = "sua_cds",
    deleted: bool = False,
) -> None:
    now = datetime(2026, 6, 11, tzinfo=timezone.utc)
    with Session() as session:
        doc = LocalDocument(
            id=doc_id,
            cdl_id=1,
            document_type=document_type,
            title=title,
            normalized_title=title.lower(),
            version=1,
            file_hash=f"h-{doc_id}",
            file_path=f"/p/{doc_id}.md",
            file_extension="md",
            file_size=1024,
            academic_year="2025-2026",
            enabled_criteria=["E1"] if document_type == "sua_cds" else ["E5"],
            status="indexed",
            uploaded_at=now,
            indexed_at=now,
            deleted_at=now if deleted else None,
        )
        session.add(doc)
        session.commit()


def _seed_audit_row(
    Session, *, evaluation_uuid: str, criterion_code: str,
    local_document_id: int, document_type: str, version: int = 1,
    file_hash: str | None = None,
    resolution_reason: str = "academic_year_match",
) -> None:
    with Session() as session:
        evaluation = (
            session.query(EvaluationResult)
            .filter_by(evaluation_uuid=evaluation_uuid)
            .one()
        )
        session.add(
            EvaluationExternalDocument(
                evaluation_result_id=evaluation.id,
                local_document_id=local_document_id,
                criterion_code=criterion_code,
                document_version_snapshot=version,
                file_hash_snapshot=file_hash or f"h-{local_document_id}",
                document_type_snapshot=document_type,
                resolution_reason=resolution_reason,
            ),
        )
        session.commit()


def _extended_dump_success() -> dict[str, Any]:
    """Mimic the JSON the C.5.3 persistence layer writes."""
    return {
        "criterion_scores": {
            "E1": 2, "E2": None, "E3": 2, "E4": 1, "E5": None,
        },
        "na_criteria": [
            {"criterion_code": "E2", "source": "resolver",
             "reason": "matrice not available"},
            {"criterion_code": "E5", "source": "handler_error",
             "reason": "LLM down"},
        ],
        "handler_errors": {"E5": "LLM down"},
        "status": "partial",
        "agent_output": {
            "agent_code": "A5",
            "judgments": [
                {
                    "criterion_code": "E1",
                    "score": 2,
                    "is_na": False,
                    "is_na_technical": False,
                    "na_reason": None,
                    "justification": (
                        "Allineamento sostanziale con SUA-CdS sui quadri "
                        "A4.b.2 e A4.c."
                    ),
                    "evidences": [
                        {"text": "Conoscenza dei modelli di consistenza.",
                         "source_field": "learning_outcomes_it"},
                        {"text": "RA quadro A4.b.2",
                         "source_document_id": 42,
                         "source_chunk_id": "external_42__chunk_0000"},
                    ],
                    "confidence": "high",
                },
                {
                    "criterion_code": "E4",
                    "score": 1,
                    "is_na": False,
                    "is_na_technical": False,
                    "na_reason": None,
                    "justification": (
                        "Equivalenza generale con derive terminologiche."
                    ),
                    "evidences": [
                        {"text": "RA in italiano",
                         "source_field": "learning_outcomes_it"},
                        {"text": "Learning outcomes in english",
                         "source_field": "learning_outcomes_en"},
                    ],
                    "confidence": "medium",
                },
            ],
            "handler_prompt_versions": {
                "E1": "e1_v1", "E3": "e3_v1", "E4": "e4_v1", "E5": "e5_v1",
            },
            "handler_errors": {"E5": "LLM down"},
            "execution_metadata": {"handlers_invoked": ["E1", "E3", "E4", "E5"]},
            "retrieved_chunks": [],
        },
    }


@pytest.fixture()
def client_and_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    _seed_minimal_db(Session)

    def _noop_invoker(initial_state, *, progress_publisher=None):
        return {**initial_state, "status": "completed"}

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


# ---------------------------------------------------------------------------
# Legacy runs
# ---------------------------------------------------------------------------


def test_legacy_run_returns_null_extended_and_empty_documents(client_and_factory):
    client, Session = client_and_factory
    uuid = _seed_evaluation(Session, extended_dump=None)  # legacy

    response = client.get(f"/api/evaluations/{uuid}")
    assert response.status_code == 200
    body = response.json()
    assert body["extended_criteria_result"] is None
    assert body["external_documents_used"] == []


# ---------------------------------------------------------------------------
# Extended payload — compact shape
# ---------------------------------------------------------------------------


def test_extended_payload_lifts_judgments_to_top_level(client_and_factory):
    client, Session = client_and_factory
    uuid = _seed_evaluation(Session, extended_dump=_extended_dump_success())

    body = client.get(f"/api/evaluations/{uuid}").json()
    ext = body["extended_criteria_result"]
    assert ext is not None
    assert ext["status"] == "partial"
    # judgments are at top level, NOT under agent_output.
    assert isinstance(ext["judgments"], list)
    assert len(ext["judgments"]) == 2
    codes = {j["criterion_code"] for j in ext["judgments"]}
    assert codes == {"E1", "E4"}
    # handler_prompt_versions promoted to top level.
    assert ext["handler_prompt_versions"] == {
        "E1": "e1_v1", "E3": "e3_v1", "E4": "e4_v1", "E5": "e5_v1",
    }
    # The opaque ``agent_output`` envelope must NOT appear in the
    # compact payload.
    assert "agent_output" not in ext


def test_extended_payload_typed_na_sources(client_and_factory):
    client, Session = client_and_factory
    uuid = _seed_evaluation(Session, extended_dump=_extended_dump_success())

    body = client.get(f"/api/evaluations/{uuid}").json()
    na = body["extended_criteria_result"]["na_criteria"]
    by_code = {n["criterion_code"]: n for n in na}
    assert by_code["E2"]["source"] == "resolver"
    assert by_code["E5"]["source"] == "handler_error"


def test_extended_judgment_evidence_shape(client_and_factory):
    client, Session = client_and_factory
    uuid = _seed_evaluation(Session, extended_dump=_extended_dump_success())

    body = client.get(f"/api/evaluations/{uuid}").json()
    judgments = body["extended_criteria_result"]["judgments"]
    e1 = next(j for j in judgments if j["criterion_code"] == "E1")
    assert e1["score"] == 2
    assert e1["is_na"] is False
    # Dual-source evidences: syllabus + document, both populated.
    evidences = e1["evidences"]
    assert any(e.get("source_field") for e in evidences)
    assert any(e.get("source_document_id") for e in evidences)
    e4 = next(j for j in judgments if j["criterion_code"] == "E4")
    # E4 evidences: paired prefix on the syllabus side; NO source_document_id.
    assert all(e.get("source_document_id") is None for e in e4["evidences"])
    fields = {e["source_field"] for e in e4["evidences"]}
    assert "learning_outcomes_it" in fields and "learning_outcomes_en" in fields


# ---------------------------------------------------------------------------
# Audit / external_documents_used
# ---------------------------------------------------------------------------


def test_external_documents_used_joins_live_title(client_and_factory):
    client, Session = client_and_factory
    uuid = _seed_evaluation(Session, extended_dump=_extended_dump_success())
    _seed_local_document(
        Session, doc_id=42, title="SUA-CdS LM-18 2025-2026",
        document_type="sua_cds",
    )
    _seed_audit_row(
        Session, evaluation_uuid=uuid, criterion_code="E1",
        local_document_id=42, document_type="sua_cds",
        file_hash="hash-sua",
    )

    body = client.get(f"/api/evaluations/{uuid}").json()
    docs = body["external_documents_used"]
    assert len(docs) == 1
    d = docs[0]
    assert d["criterion_code"] == "E1"
    assert d["local_document_id"] == 42
    assert d["document_type"] == "sua_cds"
    assert d["document_version"] == 1
    assert d["file_hash"] == "hash-sua"
    assert d["resolution_reason"] == "academic_year_match"
    assert d["title"] == "SUA-CdS LM-18 2025-2026"
    assert d["deleted_at"] is None


def test_external_documents_used_surfaces_soft_deleted_flag(client_and_factory):
    client, Session = client_and_factory
    uuid = _seed_evaluation(Session, extended_dump=_extended_dump_success())
    _seed_local_document(
        Session, doc_id=42, title="SUA archiviata", deleted=True,
    )
    _seed_audit_row(
        Session, evaluation_uuid=uuid, criterion_code="E1",
        local_document_id=42, document_type="sua_cds",
    )

    body = client.get(f"/api/evaluations/{uuid}").json()
    d = body["external_documents_used"][0]
    assert d["title"] == "SUA archiviata"
    assert d["deleted_at"] is not None  # ISO-formatted timestamp


def test_external_documents_used_deterministic_order(client_and_factory):
    """Sorted by (criterion_code asc, local_document_id asc).

    Seed in scrambled order; verify the API returns them sorted.
    """
    client, Session = client_and_factory
    uuid = _seed_evaluation(Session, extended_dump=_extended_dump_success())
    _seed_local_document(Session, doc_id=12, title="usi B")
    _seed_local_document(Session, doc_id=11, title="usi A")
    _seed_local_document(
        Session, doc_id=77, title="Regolamento",
        document_type="regolamento_didattico",
    )
    # Audit rows seeded in scrambled order — endpoint must sort.
    _seed_audit_row(
        Session, evaluation_uuid=uuid, criterion_code="E5",
        local_document_id=12, document_type="usi_dipartimentali",
    )
    _seed_audit_row(
        Session, evaluation_uuid=uuid, criterion_code="E5",
        local_document_id=11, document_type="usi_dipartimentali",
    )
    _seed_audit_row(
        Session, evaluation_uuid=uuid, criterion_code="E3",
        local_document_id=77, document_type="regolamento_didattico",
    )

    docs = client.get(f"/api/evaluations/{uuid}").json()["external_documents_used"]
    seq = [(d["criterion_code"], d["local_document_id"]) for d in docs]
    assert seq == [("E3", 77), ("E5", 11), ("E5", 12)]


def test_e4_never_appears_in_external_documents_used(client_and_factory):
    """E4 is served by the syllabus itself; the audit table never
    receives an E4 row (Phase 9.C.5.1). The endpoint MUST surface
    nothing for E4 in this list even when E4 is fully scored in the
    extended payload."""
    client, Session = client_and_factory
    uuid = _seed_evaluation(Session, extended_dump=_extended_dump_success())
    # Seed E1 only — no E4 (audit DB couldn't store it anyway).
    _seed_local_document(Session, doc_id=42, title="SUA")
    _seed_audit_row(
        Session, evaluation_uuid=uuid, criterion_code="E1",
        local_document_id=42, document_type="sua_cds",
    )
    body = client.get(f"/api/evaluations/{uuid}").json()
    codes = {d["criterion_code"] for d in body["external_documents_used"]}
    assert codes == {"E1"}  # E4 is in extended_criteria_result.judgments
    # but never in external_documents_used
    judgment_codes = {
        j["criterion_code"] for j in body["extended_criteria_result"]["judgments"]
    }
    assert "E4" in judgment_codes


# ---------------------------------------------------------------------------
# Backwards compatibility
# ---------------------------------------------------------------------------


def test_core_fields_untouched_by_extended_composition(client_and_factory):
    client, Session = client_and_factory
    uuid = _seed_evaluation(Session, extended_dump=_extended_dump_success())

    body = client.get(f"/api/evaluations/{uuid}").json()
    # Core fields preserved.
    assert body["status"] == "completed"
    assert body["core_score"] == 2.0
    assert body["coverage"] == 1.0
    assert set(body["criterion_scores"].keys()) == {
        f"C{i}" for i in range(1, 10)
    }
    # And the prompt_versions snapshot continues to include A5.
    assert "A5" in body["prompt_versions"]
