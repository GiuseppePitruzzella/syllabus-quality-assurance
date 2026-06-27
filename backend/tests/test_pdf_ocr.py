from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from reportlab.pdfgen import canvas

from app.local_documents.ocr import PdfOcrError, VertexPdfOcr


class _FakeModels:
    def __init__(self, responses: list[str]) -> None:
        self._responses = iter(responses)
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text=next(self._responses))


class _FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self.models = _FakeModels(responses)


def _make_blank_pdf(path: Path, pages: int) -> None:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for _ in range(pages):
        pdf.showPage()
    pdf.save()
    path.write_bytes(buffer.getvalue())


def test_vertex_pdf_ocr_transcribes_each_page(tmp_path):
    path = tmp_path / "matrix.pdf"
    _make_blank_pdf(path, pages=2)
    client = _FakeClient(
        [
            "```text\nRisultato | Insegnamento\nR1 | Analisi\n```",
            "Attività | CFU\nLaboratorio | 6",
        ]
    )
    ocr = VertexPdfOcr(
        "test-project",
        "europe-west1",
        "gemini-2.5-flash",
        client=client,
    )

    text = ocr(path)

    assert "Pagina 1\nRisultato | Insegnamento" in text
    assert "Pagina 2\nAttività | CFU" in text
    assert len(client.models.calls) == 2
    image_part = client.models.calls[0]["contents"][1]
    assert image_part.inline_data.mime_type == "image/jpeg"


def test_vertex_pdf_ocr_rejects_excessive_page_count(tmp_path):
    path = tmp_path / "long.pdf"
    _make_blank_pdf(path, pages=2)
    ocr = VertexPdfOcr(
        "test-project",
        "europe-west1",
        "gemini-2.5-flash",
        client=_FakeClient([]),
        max_pages=1,
    )

    with pytest.raises(PdfOcrError, match="OCR limit is 1"):
        ocr(path)


def test_vertex_pdf_ocr_rejects_empty_model_output(tmp_path):
    path = tmp_path / "empty.pdf"
    _make_blank_pdf(path, pages=1)
    ocr = VertexPdfOcr(
        "test-project",
        "europe-west1",
        "gemini-2.5-flash",
        client=_FakeClient(["   "]),
    )

    with pytest.raises(PdfOcrError, match="produced no usable text"):
        ocr(path)
