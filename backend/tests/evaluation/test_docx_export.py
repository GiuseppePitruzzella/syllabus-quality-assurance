from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from docx import Document

from app.evaluation.docx_export import (
    EvaluationExportBundle,
    EvaluationExportNotFoundError,
    build_evaluation_docx,
    export_filename,
    load_cdl_export_bundles,
    load_evaluation_export_bundle,
)
from app.models import CorsoDiLaurea, Department, EvaluationResult, Syllabus


def test_build_docx_contains_evaluation_sections_and_real_comment():
    bundle = _synthetic_bundle()

    payload = build_evaluation_docx(bundle)

    doc = Document(BytesIO(payload))
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    assert "Valutazione della qualità del syllabus" in text
    assert "Revisione dei criteri C1-C9" in text
    assert "Criteri estesi E1-E5" in text
    assert "Syllabus annotato" in text
    assert "Report di valutazione" in text
    assert "Dettagli tecnici" not in text
    with ZipFile(BytesIO(payload)) as archive:
        assert "word/comments.xml" in archive.namelist()
        comments = archive.read("word/comments.xml").decode()
        document = archive.read("word/document.xml").decode()
    assert "C5 · Chiarezza dei prerequisiti" in comments
    assert "Indicazione:" in comments
    assert "commentRangeStart" in document
    assert "commentRangeEnd" in document
    assert "commentReference" in document


def test_export_filename_is_stable_and_safe():
    bundle = _synthetic_bundle()

    assert export_filename(bundle) == (
        "LM_18__Deep_Learning__2026-06-25__evaluation.docx"
    )


def test_load_bundle_rejects_failed_evaluation(db_session):
    _seed_catalog(db_session)
    _seed_evaluation(db_session, uuid="failed", status="failed", offset=0)

    with pytest.raises(EvaluationExportNotFoundError):
        load_evaluation_export_bundle(db_session, "failed")


def test_cdl_export_uses_latest_non_failed_run_per_syllabus(db_session):
    _seed_catalog(db_session)
    _seed_evaluation(db_session, uuid="old", status="completed", offset=-3)
    _seed_evaluation(db_session, uuid="latest", status="partial", offset=-1)
    _seed_evaluation(db_session, uuid="failed-newer", status="failed", offset=0)

    cdl, bundles = load_cdl_export_bundles(db_session, 1)

    assert cdl.code == "LM-18"
    assert [bundle.evaluation.evaluation_uuid for bundle in bundles] == ["latest"]


def _synthetic_bundle() -> EvaluationExportBundle:
    now = datetime(2026, 6, 25, 10, 0, tzinfo=timezone.utc)
    scores = {f"C{i}": 2 for i in range(1, 10)}
    scores["C5"] = 1
    evaluation = SimpleNamespace(
        course_name_snapshot="Deep Learning",
        status="completed",
        started_at=now,
        core_score=1.89,
        coverage=1.0,
        criterion_scores=scores,
        na_criteria=[],
        agent_outputs={
            "A1": {
                "judgments": [
                    {
                        "criterion_code": "C5",
                        "score": 1,
                        "is_na": False,
                        "justification": "I prerequisiti sono presenti ma migliorabili.",
                        "evidences": [
                            {
                                "text": "Solide basi di Machine Learning",
                                "source_field": "prerequisites_it",
                            }
                        ],
                        "confidence": "high",
                    }
                ]
            }
        },
        extended_criteria_result={
            "criterion_scores": {
                "E1": None, "E2": None, "E3": None, "E4": 2, "E5": 2,
            },
            "na_criteria": [
                {"criterion_code": "E1", "reason": "Documento non disponibile"},
                {"criterion_code": "E2", "reason": "Documento non disponibile"},
                {"criterion_code": "E3", "reason": "Documento non disponibile"},
            ],
            "agent_output": {
                "judgments": [
                    {
                        "criterion_code": "E4",
                        "score": 2,
                        "justification": "Le versioni sono coerenti.",
                        "evidences": [],
                    },
                    {
                        "criterion_code": "E5",
                        "score": 2,
                        "justification": "Gli usi locali sono rispettati.",
                        "evidences": [],
                    },
                ]
            },
        },
        final_report="# Sintesi\n\n- Documento complessivamente adeguato.",
    )
    syllabus_fields = {
        "course_name": "Deep Learning",
        "teacher": "Antonino Furnari",
        "academic_year": "2025/2026",
        "has_english": True,
        "learning_outcomes_it": "Lo studente acquisisce competenze avanzate.",
        "dublin_knowledge_it": "",
        "dublin_applying_it": "",
        "dublin_judgement_it": "",
        "dublin_communication_it": "",
        "dublin_learning_it": "",
        "teaching_methods_it": "Lezioni e laboratorio.",
        "prerequisites_it": "Solide basi di Machine Learning e Python.",
        "attendance_it": "Consigliata.",
        "course_content_it": "Reti neurali e modelli generativi.",
        "references_it": "Goodfellow et al., Deep Learning.",
        "schedule_it": [{"numero": 1, "argomenti": "Introduzione"}],
        "assessment_methods_it": "Prova scritta e progetto.",
        "sample_questions_it": "Descrivere la backpropagation.",
        "learning_outcomes_en": "The student acquires advanced skills.",
        "dublin_knowledge_en": None,
        "dublin_applying_en": None,
        "dublin_judgement_en": None,
        "dublin_communication_en": None,
        "dublin_learning_en": None,
        "teaching_methods_en": "Lectures and laboratory.",
        "prerequisites_en": "Machine Learning and Python.",
        "attendance_en": "Recommended.",
        "course_content_en": "Neural networks and generative models.",
        "references_en": "Goodfellow et al., Deep Learning.",
        "schedule_en": [{"numero": 1, "subjects": "Introduction"}],
        "assessment_methods_en": "Written exam and project.",
        "sample_questions_en": "Describe backpropagation.",
    }
    return EvaluationExportBundle(
        evaluation=evaluation,
        syllabus=SimpleNamespace(**syllabus_fields),
        cdl=SimpleNamespace(code="LM-18", name="Informatica"),
        department=SimpleNamespace(name="Matematica e Informatica"),
    )


def _seed_catalog(session) -> None:
    now = datetime(2026, 6, 25, tzinfo=timezone.utc)
    session.add(
        Department(
            id=1,
            name="DMI",
            area="Scientifica",
            website_url="https://example.test",
            email="dmi@example.test",
            phone="0",
            director="Direttore",
            scraped_at=now,
        )
    )
    session.add(
        CorsoDiLaurea(
            id=1,
            department_id=1,
            name="Informatica",
            code="LM-18",
            type="Magistrale",
            academic_year="2025/2026",
            url="https://example.test/lm18",
            scraped_at=now,
        )
    )
    fields = {
        "id": 1,
        "cdl_id": 1,
        "seuid": "SEUID-1",
        "course_code": "CODE-1",
        "course_name": "Deep Learning",
        "teacher": "Docente",
        "academic_year": "2025/2026",
        "year_of_study": "1",
        "url_it": "https://example.test/it",
        "url_en": "https://example.test/en",
        "has_english": False,
        "scraped_at": now,
    }
    for field in (
        "learning_outcomes_it", "dublin_knowledge_it", "dublin_applying_it",
        "dublin_judgement_it", "dublin_communication_it", "dublin_learning_it",
        "teaching_methods_it", "prerequisites_it", "attendance_it",
        "course_content_it", "references_it", "assessment_methods_it",
        "sample_questions_it",
    ):
        fields[field] = f"Testo {field}"
    session.add(Syllabus(**fields))
    session.commit()


def _seed_evaluation(session, *, uuid: str, status: str, offset: int) -> None:
    started = datetime(2026, 6, 25, tzinfo=timezone.utc) + timedelta(hours=offset)
    session.add(
        EvaluationResult(
            evaluation_uuid=uuid,
            syllabus_id=1,
            syllabus_seuid_snapshot="SEUID-1",
            course_name_snapshot="Deep Learning",
            status=status,
            started_at=started,
            finished_at=started + timedelta(seconds=5),
            duration_ms=5000,
            llm_model="gemini-2.5-flash",
            embedding_model="gemini-embedding-001",
            embedding_dim=3072,
            llm_temperature=0.1,
            llm_max_output_tokens=8192,
            rag_top_k=5,
            rag_final_k=3,
            rag_similarity_threshold=0.6,
            gcp_project_id="test",
            gcp_location="europe-west8",
            prompt_versions={},
            core_score=1.5,
            coverage=1.0,
            criterion_scores={f"C{i}": 2 for i in range(1, 10)},
            na_criteria=[],
            agent_outputs={},
            agent_errors={},
            retrieved_chunks={},
            final_report="Report",
        )
    )
    session.commit()
