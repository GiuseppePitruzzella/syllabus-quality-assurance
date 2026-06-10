"""Tests for the A5 per-criterion handlers (Phase 9.C.3.B).

These tests focus on the handler-level contract:
    - successful path: the handler retrieves, prompts, parses and
      returns a :class:`HandlerResult` with the correct judgment,
      chunk refs and prompt version;
    - retry on validation failure: the handler retries up to
      ``max_retries`` times before raising ``ExternalHandlerError``;
    - retrieval failure surfaces as ``ExternalHandlerError`` (the
      coordinator turns it into a technical NA);
    - E4 pre-LLM check: with no paired prefix, the handler returns
      a SEMANTIC NA without calling the LLM;
    - E5 multi-document: one retrieval per resolved document,
      chunks grouped per document in the prompt payload.

All LLM and retriever interactions are stubbed; the tests are
offline and incur no Vertex / Chroma cost.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.evaluation.agents.external_handlers import (
    E1Handler,
    E2Handler,
    E3Handler,
    E4Handler,
    E5Handler,
    ExternalHandlerError,
)
from app.evaluation.rag.external_retriever import ExternalRetrievedChunk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _syllabus(**overrides):
    base = dict(
        seuid="9999-XX-LM18",
        course_name="Sistemi distribuiti",
        course_code="CS-DS-01",
        academic_year=2025,
        year_of_study=2,
        credits=9,
        has_english=True,
        # IT / EN paired side
        course_title_it="Sistemi distribuiti",
        course_title_en="Distributed Systems",
        learning_outcomes_it="Conoscenza dei modelli di consistenza.",
        learning_outcomes_en="Knowledge of consistency models.",
        course_content_it="Modelli, consenso, replicazione.",
        course_content_en="Models, consensus, replication.",
        prerequisites_it="Programmazione concorrente.",
        prerequisites_en="Concurrent programming.",
        assessment_methods_it="Esame orale e progetto.",
        assessment_methods_en="Oral exam and project.",
        # Dublin descriptors (IT side only by default)
        dublin_knowledge_it="Conoscenza dei principi.",
        dublin_knowledge_en="Knowledge of principles.",
        dublin_applying_it="Capacità di applicare.",
        dublin_applying_en="Ability to apply.",
        dublin_judgement_it="",
        dublin_judgement_en="",
        dublin_communication_it="",
        dublin_communication_en="",
        dublin_learning_it="",
        dublin_learning_en="",
        # IT-only optional fields
        sample_questions_it="Domanda esempio.",
        teaching_methods_it="Lezioni frontali.",
        attendance_it="Frequenza facoltativa.",
        references_it="Tanenbaum, Distributed Systems.",
        schedule_it=[],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _chunk(*, doc_id: int = 42, idx: int = 0, doc_type: str = "sua_cds"):
    return ExternalRetrievedChunk(
        chunk_id=f"external_{doc_id}_v1__chunk_{idx:04d}",
        text=f"Estratto del documento {doc_id} frammento {idx}.",
        metadata={"document_id": doc_id, "section": f"§{idx}"},
        similarity_score=0.85 - 0.05 * idx,
        local_document_id=doc_id,
        document_type=doc_type,
        document_version=1,
    )


def _llm_returning(payload):
    """Return a callable that, on each call, returns the next
    string from ``payload``. ``payload`` may be a single string or
    a list — useful to script retry sequences."""
    if isinstance(payload, str):
        payload = [payload]
    seq = iter(payload)

    def _call(prompt: str) -> str:
        return next(seq)

    return MagicMock(side_effect=_call)


def _valid_e_judgment(
    criterion: str,
    *,
    score: int | None = 2,
    is_na: bool = False,
    document_id: int | None = 42,
    paired_for_e4: bool = False,
) -> str:
    """Produce a JSON string that the handler's parser will accept."""
    if is_na:
        body = {
            "criterion_code": criterion,
            "score": None,
            "is_na": True,
            "na_reason": "documento non applicabile",
            "is_na_technical": False,
            "justification": (
                "Il documento esterno non riporta indicazioni applicabili "
                "all'insegnamento; il criterio è semanticamente NA."
            ),
            "evidences": [],
            "confidence": "medium",
        }
        return json.dumps({"judgment": body})

    if criterion == "E4":
        if paired_for_e4:
            evidences = [
                {
                    "text": "Conoscenza dei modelli di consistenza.",
                    "source_field": "learning_outcomes_it",
                },
                {
                    "text": "Knowledge of consistency models.",
                    "source_field": "learning_outcomes_en",
                },
            ]
        else:
            evidences = []
    else:
        evidences = [
            {
                "text": "Conoscenza dei modelli di consistenza.",
                "source_field": "learning_outcomes_it",
            },
            {
                "text": f"Estratto del documento {document_id} frammento 0.",
                "source_document_id": document_id,
                "source_chunk_id": f"external_{document_id}_v1__chunk_0000",
            },
        ]

    body = {
        "criterion_code": criterion,
        "score": score,
        "is_na": False,
        "na_reason": None,
        "is_na_technical": False,
        "justification": (
            "Il syllabus risulta sostanzialmente allineato al documento "
            "esterno, con riferimenti tracciabili in entrambe le fonti."
        ),
        "evidences": evidences,
        "confidence": "high",
    }
    return json.dumps({"judgment": body})


# ---------------------------------------------------------------------------
# Success path: E1 / E2 / E3
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "criterion, handler_cls, doc_id",
    [("E1", E1Handler, 42), ("E2", E2Handler, 51), ("E3", E3Handler, 77)],
)
def test_single_doc_handler_happy_path(criterion, handler_cls, doc_id):
    retriever = MagicMock()
    retriever.retrieve_for.return_value = [_chunk(doc_id=doc_id, idx=0)]
    llm = _llm_returning(
        _valid_e_judgment(criterion, document_id=doc_id),
    )

    handler = handler_cls(llm_client=llm, external_retriever=retriever)
    result = handler.evaluate(
        syllabus=_syllabus(),
        cdl_id=3,
        document_ids=[doc_id],
    )

    # Retriever called with the criterion-specific filter triple.
    args, kwargs = retriever.retrieve_for.call_args
    assert kwargs["criterion"] == criterion
    assert kwargs["cdl_id"] == 3
    assert kwargs["local_document_id"] == doc_id

    # Judgment shape.
    assert result.judgment.criterion_code == criterion
    assert result.judgment.score == 2
    assert result.judgment.is_na is False
    assert result.prompt_version == f"{criterion.lower()}_v1"
    assert result.retry_count == 0

    # Chunk refs were lifted from the retrieved chunks.
    assert len(result.retrieved_chunks) == 1
    ref = result.retrieved_chunks[0]
    assert ref.criterion_code == criterion
    assert ref.local_document_id == doc_id
    assert ref.document_type in ("sua_cds", "matrice_tuning", "regolamento_didattico")


@pytest.mark.parametrize(
    "handler_cls", [E1Handler, E2Handler, E3Handler],
)
def test_single_doc_handler_rejects_zero_or_many_documents(handler_cls):
    retriever = MagicMock()
    handler = handler_cls(llm_client=MagicMock(), external_retriever=retriever)
    with pytest.raises(ExternalHandlerError):
        handler.evaluate(syllabus=_syllabus(), cdl_id=3, document_ids=[])
    with pytest.raises(ExternalHandlerError):
        handler.evaluate(syllabus=_syllabus(), cdl_id=3, document_ids=[1, 2])
    # Retriever was never reached.
    assert retriever.retrieve_for.call_count == 0


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------


def test_handler_retries_on_invalid_json_and_succeeds():
    """First two attempts produce invalid JSON, third returns valid."""
    retriever = MagicMock()
    retriever.retrieve_for.return_value = [_chunk(doc_id=42)]
    llm = _llm_returning(
        [
            "not json at all",
            '{"judgment": {"criterion_code": "E1"}}',  # incomplete
            _valid_e_judgment("E1", document_id=42),
        ],
    )
    handler = E1Handler(llm_client=llm, external_retriever=retriever)
    result = handler.evaluate(
        syllabus=_syllabus(), cdl_id=3, document_ids=[42],
    )
    assert result.judgment.score == 2
    assert result.retry_count == 2
    assert llm.call_count == 3


def test_handler_raises_external_handler_error_after_retry_exhaustion():
    retriever = MagicMock()
    retriever.retrieve_for.return_value = [_chunk(doc_id=42)]
    llm = _llm_returning(
        ["nope", "still nope", "give up", "extra ignored"],
    )
    handler = E1Handler(llm_client=llm, external_retriever=retriever)
    with pytest.raises(ExternalHandlerError) as excinfo:
        handler.evaluate(
            syllabus=_syllabus(), cdl_id=3, document_ids=[42],
        )
    assert excinfo.value.criterion_code == "E1"
    assert excinfo.value.retry_count == 3  # max_retries=2 → 3 attempts
    assert llm.call_count == 3  # never a 4th call


def test_handler_wraps_retriever_exception_into_external_handler_error():
    retriever = MagicMock()
    retriever.retrieve_for.side_effect = RuntimeError("chroma exploded")
    llm = MagicMock()
    handler = E1Handler(llm_client=llm, external_retriever=retriever)
    with pytest.raises(ExternalHandlerError) as excinfo:
        handler.evaluate(
            syllabus=_syllabus(), cdl_id=3, document_ids=[42],
        )
    assert "retrieval failed" in str(excinfo.value)
    assert isinstance(excinfo.value.original, RuntimeError)
    # LLM was never called.
    assert llm.call_count == 0


# ---------------------------------------------------------------------------
# Dual-source validator integration
# ---------------------------------------------------------------------------


def test_handler_retries_when_llm_omits_external_evidence():
    """The dual-source validator rejects an E1 numeric judgment
    without a ``source_document_id`` evidence — the handler should
    retry and eventually fail if the LLM keeps refusing."""
    retriever = MagicMock()
    retriever.retrieve_for.return_value = [_chunk(doc_id=42)]
    # Build a judgment that has only a syllabus evidence — should
    # fail the dual-source validator on every attempt.
    bad_body = {
        "criterion_code": "E1",
        "score": 2,
        "is_na": False,
        "na_reason": None,
        "is_na_technical": False,
        "justification": (
            "Allineamento sostanziale ma senza citazione del documento esterno."
        ),
        "evidences": [
            {
                "text": "Conoscenza dei modelli di consistenza.",
                "source_field": "learning_outcomes_it",
            },
        ],
        "confidence": "medium",
    }
    bad = json.dumps({"judgment": bad_body})
    llm = _llm_returning([bad, bad, bad])
    handler = E1Handler(llm_client=llm, external_retriever=retriever)
    with pytest.raises(ExternalHandlerError):
        handler.evaluate(syllabus=_syllabus(), cdl_id=3, document_ids=[42])
    assert llm.call_count == 3


# ---------------------------------------------------------------------------
# E4 special behaviour
# ---------------------------------------------------------------------------


def test_e4_returns_semantic_na_when_no_paired_prefix_without_calling_llm():
    """When the syllabus has has_english=True but no paired *_it/*_en
    field with content, E4 short-circuits to a semantic NA."""
    llm = MagicMock()
    syllabus = _syllabus(
        course_title_en="", learning_outcomes_en="",
        course_content_en="", prerequisites_en="",
        assessment_methods_en="",
        dublin_knowledge_en="", dublin_applying_en="",
    )
    handler = E4Handler(llm_client=llm)
    result = handler.evaluate(
        syllabus=syllabus, cdl_id=3, document_ids=[],
    )
    assert result.judgment.is_na is True
    assert result.judgment.is_na_technical is False
    assert result.judgment.score is None
    assert result.retrieved_chunks == []
    # LLM never called: the pre-LLM check decided.
    assert llm.call_count == 0


def test_e4_happy_path_calls_llm_when_paired_prefix_present():
    llm = _llm_returning(
        _valid_e_judgment("E4", paired_for_e4=True),
    )
    handler = E4Handler(llm_client=llm)
    result = handler.evaluate(
        syllabus=_syllabus(), cdl_id=3, document_ids=[],
    )
    assert result.judgment.criterion_code == "E4"
    assert result.judgment.score == 2
    assert llm.call_count == 1
    assert result.retrieved_chunks == []
    # Execution metadata records the paired-prefix count.
    assert result.execution_metadata["paired_prefixes_count"] >= 1


def test_e4_handler_ignores_document_ids():
    """E4 must not require document_ids — the field is informational."""
    llm = _llm_returning(_valid_e_judgment("E4", paired_for_e4=True))
    handler = E4Handler(llm_client=llm)
    # Empty AND non-empty document_ids are both acceptable.
    result = handler.evaluate(
        syllabus=_syllabus(), cdl_id=3, document_ids=[],
    )
    assert result.judgment.score == 2


# ---------------------------------------------------------------------------
# E5 multi-document behaviour
# ---------------------------------------------------------------------------


def test_e5_issues_one_retrieval_per_resolved_document():
    retriever = MagicMock()
    retriever.retrieve_for.side_effect = [
        [_chunk(doc_id=11, doc_type="usi_dipartimentali")],
        [_chunk(doc_id=12, doc_type="linee_guida_cdl")],
        [_chunk(doc_id=13, doc_type="template_locale")],
    ]
    # Build an E5 judgment that cites multiple documents (the
    # dual-source rule only requires ONE external + ONE syllabus
    # evidence; multi-doc is just a richer evidence set).
    body = {
        "criterion_code": "E5",
        "score": 1,
        "is_na": False,
        "na_reason": None,
        "is_na_technical": False,
        "justification": (
            "Il syllabus aderisce parzialmente alle indicazioni locali; "
            "alcuni aspetti sono coerenti, altri non risultano applicati."
        ),
        "evidences": [
            {
                "text": "Programmazione concorrente.",
                "source_field": "prerequisites_it",
            },
            {
                "text": "Estratto del documento 11 frammento 0.",
                "source_document_id": 11,
            },
            {
                "text": "Estratto del documento 12 frammento 0.",
                "source_document_id": 12,
            },
        ],
        "confidence": "medium",
    }
    llm = _llm_returning(json.dumps({"judgment": body}))
    handler = E5Handler(llm_client=llm, external_retriever=retriever)
    result = handler.evaluate(
        syllabus=_syllabus(), cdl_id=3, document_ids=[11, 12, 13],
    )

    # One retrieval per document.
    assert retriever.retrieve_for.call_count == 3
    called_doc_ids = [
        c.kwargs["local_document_id"]
        for c in retriever.retrieve_for.call_args_list
    ]
    assert called_doc_ids == [11, 12, 13]
    # All chunks rolled up into the result.
    assert {ref.local_document_id for ref in result.retrieved_chunks} == {11, 12, 13}
    assert result.judgment.score == 1
    assert result.execution_metadata["document_count"] == 3


def test_e5_requires_at_least_one_document():
    retriever = MagicMock()
    handler = E5Handler(llm_client=MagicMock(), external_retriever=retriever)
    with pytest.raises(ExternalHandlerError):
        handler.evaluate(syllabus=_syllabus(), cdl_id=3, document_ids=[])
    assert retriever.retrieve_for.call_count == 0


def test_e5_keeps_empty_group_when_a_document_returns_no_chunks():
    """If one of the resolved documents has no above-threshold
    chunks, the handler MUST still pass the document_id to the LLM
    so the judgment can mention that the document was consulted."""
    retriever = MagicMock()
    retriever.retrieve_for.side_effect = [
        [_chunk(doc_id=11, doc_type="usi_dipartimentali")],
        [],  # doc 12 underfilled
    ]
    body = {
        "criterion_code": "E5",
        "score": 2,
        "is_na": False,
        "na_reason": None,
        "is_na_technical": False,
        "justification": (
            "Il documento 11 fornisce indicazioni rispettate dal syllabus; "
            "il documento 12 è stato consultato ma non riporta indicazioni applicabili."
        ),
        "evidences": [
            {"text": "Programmazione concorrente.", "source_field": "prerequisites_it"},
            {"text": "Estratto del documento 11 frammento 0.", "source_document_id": 11},
        ],
        "confidence": "medium",
    }
    llm = _llm_returning(json.dumps({"judgment": body}))
    handler = E5Handler(llm_client=llm, external_retriever=retriever)
    result = handler.evaluate(
        syllabus=_syllabus(), cdl_id=3, document_ids=[11, 12],
    )
    assert retriever.retrieve_for.call_count == 2
    # Both documents are visible in the prompt payload (the LLM
    # call was made — that's the point), even if only doc 11
    # contributes chunks.
    assert result.judgment.score == 2
    assert {ref.local_document_id for ref in result.retrieved_chunks} == {11}
