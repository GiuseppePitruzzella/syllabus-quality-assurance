"""Download endpoints for non-technical evaluation DOCX exports."""
from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.evaluation.docx_export import (
    EvaluationExportNotFoundError,
    build_evaluation_docx,
    cdl_zip_filename,
    export_filename,
    load_cdl_export_bundles,
    load_evaluation_export_bundle,
)


router = APIRouter(prefix="/api/exports", tags=["exports"])

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
ZIP_MEDIA_TYPE = "application/zip"


@router.get("/evaluations/{evaluation_uuid}.docx")
def export_evaluation_docx(
    evaluation_uuid: str,
    db: Session = Depends(get_db),
) -> Response:
    """Export one exact completed/partial evaluation as a DOCX."""
    try:
        bundle = load_evaluation_export_bundle(db, evaluation_uuid)
    except EvaluationExportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=build_evaluation_docx(bundle),
        media_type=DOCX_MEDIA_TYPE,
        headers=_download_headers(export_filename(bundle)),
    )


@router.get("/cdl/{cdl_id}.zip")
def export_cdl_evaluations(
    cdl_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Export one DOCX per syllabus using its latest non-failed terminal run."""
    try:
        cdl, bundles = load_cdl_export_bundles(db, cdl_id)
    except EvaluationExportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not bundles:
        raise HTTPException(
            status_code=404,
            detail=f"no exportable evaluations for cdl_id={cdl_id}",
        )

    buffer = BytesIO()
    used_names: set[str] = set()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for bundle in bundles:
            filename = _unique_filename(export_filename(bundle), used_names)
            archive.writestr(filename, build_evaluation_docx(bundle))
    return Response(
        content=buffer.getvalue(),
        media_type=ZIP_MEDIA_TYPE,
        headers=_download_headers(cdl_zip_filename(cdl)),
    )


def _download_headers(filename: str) -> dict[str, str]:
    return {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Content-Type-Options": "nosniff",
    }


def _unique_filename(filename: str, used: set[str]) -> str:
    if filename not in used:
        used.add(filename)
        return filename
    stem, suffix = filename.rsplit(".", 1)
    index = 2
    while f"{stem}__{index}.{suffix}" in used:
        index += 1
    candidate = f"{stem}__{index}.{suffix}"
    used.add(candidate)
    return candidate
