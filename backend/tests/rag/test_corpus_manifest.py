from pathlib import Path

from app.config import settings
from app.evaluation.rag.corpus_manifest import list_normative_corpus_documents


def test_corpus_manifest_lists_all_versioned_documents():
    docs = list_normative_corpus_documents(
        corpus_dir=Path(settings.normative_corpus_dir),
        tagging_rules_file=Path(settings.tagging_rules_file),
    )

    assert len(docs) == 7
    assert {doc.document_id for doc in docs} == {
        "ava3",
        "ava3_unict",
        "cpds_unict",
        "dm1154",
        "lg_unict",
        "lgsua_cds",
        "matrice_tuning",
    }
    assert all(len(doc.file_hash) == 64 for doc in docs)
    assert all(doc.chunk_count > 0 for doc in docs)


def test_lg_unict_covers_every_core_criterion():
    docs = list_normative_corpus_documents(
        corpus_dir=Path(settings.normative_corpus_dir),
        tagging_rules_file=Path(settings.tagging_rules_file),
    )
    lg_unict = next(doc for doc in docs if doc.document_id == "lg_unict")

    assert lg_unict.is_core_source is True
    assert lg_unict.core_criteria == [
        "C1",
        "C2",
        "C3",
        "C4",
        "C5",
        "C6",
        "C7",
        "C8",
        "C9",
    ]
    assert lg_unict.agents == ["A1", "A2", "A3", "A4"]
def test_active_corpus_contains_only_core_sources():
    docs = list_normative_corpus_documents(
        corpus_dir=Path(settings.normative_corpus_dir),
        tagging_rules_file=Path(settings.tagging_rules_file),
    )

    assert all(doc.is_core_source for doc in docs)
    assert all(doc.core_chunk_count > 0 for doc in docs)
