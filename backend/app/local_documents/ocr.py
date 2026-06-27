"""OCR fallback for scanned PDF documents.

The registry first attempts deterministic text extraction with
``pdfplumber``. Only PDFs that contain no extractable text reach
this module. Each page is rendered to a JPEG and transcribed with
the existing Vertex Gemini model so the fallback requires no local
Tesseract installation or additional Google Cloud product.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
import structlog
from google import genai
from google.api_core.exceptions import (
    DeadlineExceeded,
    ResourceExhausted,
    ServiceUnavailable,
)
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger(__name__)

_OCR_PROMPT = """\
Trascrivi integralmente il testo visibile in questa pagina di un documento
accademico. Non riassumere, non correggere e non aggiungere informazioni.

Regole di output:
- restituisci soltanto la trascrizione, senza introduzioni o blocchi di codice;
- conserva titoli, etichette e ordine di lettura;
- per le tabelle, scrivi una riga per ogni riga della tabella e separa le celle
  con ` | `;
- usa `[illeggibile]` solo quando un frammento non può essere decifrato;
- ignora elementi puramente decorativi.
"""


class PdfOcrError(Exception):
    """Raised when the OCR fallback cannot produce usable text."""


def _is_retryable_error(exc: BaseException) -> bool:
    if isinstance(
        exc,
        (ResourceExhausted, ServiceUnavailable, DeadlineExceeded),
    ):
        return True
    if isinstance(exc, genai_errors.ServerError):
        return True
    if isinstance(exc, genai_errors.ClientError):
        return getattr(exc, "code", None) == 429
    return False


class VertexPdfOcr:
    """Render and transcribe scanned PDF pages with Vertex Gemini."""

    def __init__(
        self,
        project_id: str,
        location: str,
        model_name: str,
        *,
        client: Any | None = None,
        max_pages: int = 50,
        render_scale: float = 2.0,
    ) -> None:
        if not project_id:
            raise ValueError("project_id is required for PDF OCR")
        self._client = client or genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
            http_options=genai_types.HttpOptions(api_version="v1"),
        )
        self._model_name = model_name
        self._max_pages = max_pages
        self._render_scale = render_scale

    def __call__(self, path: Path) -> str:
        """Return a page-labelled plain-text transcription."""
        try:
            pdf = pdfium.PdfDocument(str(path))
        except Exception as exc:
            raise PdfOcrError(f"Unable to render PDF for OCR: {exc}") from exc

        try:
            page_count = len(pdf)
            if page_count == 0:
                raise PdfOcrError("PDF has no pages to transcribe")
            if page_count > self._max_pages:
                raise PdfOcrError(
                    f"PDF has {page_count} pages; OCR limit is {self._max_pages}"
                )

            logger.info(
                "pdf_ocr_started",
                file_name=path.name,
                pages=page_count,
                model=self._model_name,
            )
            transcriptions: list[str] = []
            for index in range(page_count):
                text = self._transcribe_page(pdf[index], page_number=index + 1)
                if text:
                    transcriptions.append(f"Pagina {index + 1}\n{text}")
        finally:
            pdf.close()

        output = "\n\n".join(transcriptions).strip()
        if not output:
            raise PdfOcrError("OCR completed but produced no usable text")

        logger.info(
            "pdf_ocr_completed",
            file_name=path.name,
            pages=page_count,
            output_chars=len(output),
            model=self._model_name,
        )
        return output

    def _transcribe_page(self, page: Any, *, page_number: int) -> str:
        bitmap = None
        image = None
        try:
            bitmap = page.render(scale=self._render_scale)
            image = bitmap.to_pil().convert("RGB")
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=90, optimize=True)
            text = self._generate_page_text(buffer.getvalue())
        except Exception as exc:
            raise PdfOcrError(
                f"OCR failed on page {page_number}: {exc}"
            ) from exc
        finally:
            if image is not None:
                image.close()
            if bitmap is not None:
                bitmap.close()
            page.close()

        if not isinstance(text, str):
            raise PdfOcrError(
                f"OCR returned no text for page {page_number}"
            )
        return _strip_markdown_fence(text)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        retry=retry_if_exception(_is_retryable_error),
        reraise=True,
    )
    def _generate_page_text(self, image_bytes: bytes) -> str | None:
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=[
                _OCR_PROMPT,
                genai_types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/jpeg",
                ),
            ],
            config=genai_types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=16384,
                thinking_config=genai_types.ThinkingConfig(
                    thinking_budget=0,
                ),
            ),
        )
        return getattr(response, "text", None)


def _strip_markdown_fence(text: str) -> str:
    """Remove a model-added outer code fence without altering content."""
    stripped = text.strip()
    if not stripped.startswith("```") or not stripped.endswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) < 3:
        return stripped
    return "\n".join(lines[1:-1]).strip()


__all__ = ["PdfOcrError", "VertexPdfOcr"]
