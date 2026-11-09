"""
FastAPI REST routes for AnonDoc.

Every job endpoint requires `Authorization: Bearer <access_token>` (the token returned
at upload). Unknown, expired and unauthorized jobs all produce the same 404.
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response

from anondoc.application.dtos import (
    AnalysisResponseDTO,
    AnonymizeRequestDTO,
    AnonymizeResponseDTO,
    DocumentUploadResponseDTO,
    HealthResponseDTO,
    UpdateDetectionsRequestDTO,
)
from anondoc.application.job_manager import job_manager
from anondoc.application.use_cases import DocumentUseCases
from anondoc.config import AppConfig
from anondoc.domain.entities import DocumentJob
from anondoc.infrastructure.detection.factory import build_detector
from anondoc.infrastructure.security.inspector import DocumentRejected
from anondoc.infrastructure.storage.temp_storage import JOB_ID_RE

router = APIRouter(prefix="/api/v1", tags=["Documents"])
use_cases = DocumentUseCases(detector=build_detector())

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajo no encontrado o no autorizado.")


def authorized_job(job_id: str, authorization: Optional[str] = Header(default=None)) -> DocumentJob:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not JOB_ID_RE.fullmatch(job_id):
        raise NOT_FOUND
    job = job_manager.get_authorized_job(job_id, token)
    if job is None:
        raise NOT_FOUND
    return job


@router.post("/documents", response_model=DocumentUploadResponseDTO, status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...)):
    """Carga de un único documento PDF o DOCX; el formato real se determina por su contenido."""
    content = await file.read(AppConfig.MAX_FILE_SIZE_BYTES + 1)
    if len(content) > AppConfig.MAX_FILE_SIZE_BYTES:
        raise DocumentRejected("file_too_large", f"El archivo excede el tamaño máximo permitido ({AppConfig.MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB).")
    return await run_in_threadpool(use_cases.upload_document, file.filename or "", content)


@router.post("/documents/{job_id}/analyze", response_model=AnalysisResponseDTO)
def analyze_document(job: DocumentJob = Depends(authorized_job)):
    return use_cases.analyze_document(job)


@router.get("/documents/{job_id}/analysis", response_model=AnalysisResponseDTO)
def get_analysis(job: DocumentJob = Depends(authorized_job)):
    return use_cases.analysis_summary(job)


@router.patch("/documents/{job_id}/detections", response_model=AnalysisResponseDTO)
def update_detections(request: UpdateDetectionsRequestDTO, job: DocumentJob = Depends(authorized_job)):
    return use_cases.update_detections(job, request)


@router.post("/documents/{job_id}/anonymize", response_model=AnonymizeResponseDTO)
def anonymize_document(request: AnonymizeRequestDTO, job: DocumentJob = Depends(authorized_job)):
    return use_cases.anonymize_document(job, request)


@router.get("/documents/{job_id}/download")
def download_document(job: DocumentJob = Depends(authorized_job)):
    try:
        path, filename, media_type = use_cases.get_download_path(job)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento anonimizado no disponible.")
    return FileResponse(path=path, filename=filename, media_type=media_type)


@router.delete("/documents/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job: DocumentJob = Depends(authorized_job)):
    use_cases.delete_job(job)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/health", response_model=HealthResponseDTO)
def health():
    return use_cases.health_check()
