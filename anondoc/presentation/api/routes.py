"""
FastAPI REST Routes for AnonDoc v2.0.
Strict versioning, Pydantic DTOs, and error handling.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import FileResponse
from typing import Dict, Any

from anondoc.application.dtos import (
    DocumentUploadResponseDTO,
    AnalysisResponseDTO,
    UpdateDetectionsRequestDTO,
    AnonymizeRequestDTO,
    AnonymizeResponseDTO,
    HealthResponseDTO
)
from anondoc.application.use_cases import DocumentUseCases

router = APIRouter(prefix="/api/v1", tags=["Documents"])
use_cases = DocumentUseCases()

@router.post("/documents", response_model=DocumentUploadResponseDTO, status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...)):
    """Carga de documento PDF o DOCX con validación de seguridad de bajo nivel."""
    try:
        content = await file.read()
        res = use_cases.upload_document(filename=file.filename, content=content)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al procesar archivo: {str(e)}")

@router.post("/documents/{job_id}/analyze", response_model=AnalysisResponseDTO)
async def analyze_document(job_id: str):
    """Ejecuta el análisis y detección de información personal y sensible."""
    try:
        return use_cases.analyze_document(job_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error durante el análisis: {str(e)}")

@router.get("/documents/{job_id}/analysis", response_model=AnalysisResponseDTO)
async def get_analysis(job_id: str):
    """Consulta las detecciones actuales del documento."""
    from anondoc.application.job_manager import job_manager
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Trabajo '{job_id}' no encontrado.")
    return use_cases.analyze_document_summary(job)

@router.patch("/documents/{job_id}/detections", response_model=AnalysisResponseDTO)
async def update_detections(job_id: str, request: UpdateDetectionsRequestDTO):
    """Permite al usuario revisar, corregir falsos positivos y añadir entidades manuales."""
    try:
        return use_cases.update_detections(job_id, request)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/documents/{job_id}/anonymize", response_model=AnonymizeResponseDTO)
async def anonymize_document(job_id: str, request: AnonymizeRequestDTO):
    """Aplica la estrategia de anonimización seleccionada sobre el documento."""
    try:
        return use_cases.anonymize_document(job_id, request)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al anonimizar: {str(e)}")

@router.get("/documents/{job_id}/download")
async def download_document(job_id: str):
    """Descarga el documento resultante anonimizado."""
    try:
        path, filename, media_type = use_cases.get_download_path(job_id)
        return FileResponse(
            path=path,
            filename=filename,
            media_type=media_type
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/documents/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: str):
    """Elimina de forma permanente el trabajo y los archivos temporales asociados."""
    success = use_cases.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajo no encontrado.")
    return None

@router.get("/health", response_model=HealthResponseDTO)
async def health():
    """Estado y métricas de salud del servicio."""
    return use_cases.health_check()
