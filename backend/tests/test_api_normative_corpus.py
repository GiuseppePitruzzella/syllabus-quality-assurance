from fastapi.testclient import TestClient

from app.main import app


def test_normative_corpus_documents_endpoint_returns_core_inventory():
    with TestClient(app) as client:
        response = client.get("/api/normative-corpus/documents")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 7

    by_id = {row["document_id"]: row for row in payload}
    assert by_id["lg_unict"]["core_criteria"] == [
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
    assert "lg_cpds_unict" not in by_id
    assert all(row["is_core_source"] for row in payload)
    assert all(len(row["file_hash"]) == 64 for row in payload)
