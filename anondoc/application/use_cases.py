"""
Application Use Cases Orchestrating Domain and Infrastructure Engines.
"""
import uuid
from pathlib import Path
from typing import List, Dict, Any, Tuple
from anondoc.domain.entities import (
    DocumentJob,
    PIIEntity,
    JobStatus,
    DocumentFormat,
    AnonymizationStrategy,
    DetectionConfidence
)
from anondoc.application.dtos import (
    DocumentUploadResponseDTO,
    AnalysisResponseDTO,
    PIIEntityDTO,
    UpdateDetectionsRequestDTO,
    AnonymizeRequestDTO,
    AnonymizeResponseDTO,
    HealthResponseDTO
)
from anondoc.application.job_manager import job_manager
from anondoc.infrastructure.storage.temp_storage import SecureStorageService
from anondoc.infrastructure.engines.pdf_engine import PDFEngine
from anondoc.infrastructure.engines.docx_engine import DOCXEngine
from anondoc.infrastructure.detection.pii_detector import HybridPIIDetector
from anondoc.config import AppConfig

class DocumentUseCases:
    """Orchestrates all document privacy workflows."""

    def __init__(self, storage: SecureStorageService = None):
        self.storage = storage or SecureStorageService()
        self.pdf_engine = PDFEngine()
        self.docx_engine = DOCXEngine()
        self.detector = HybridPIIDetector()

    def upload_document(self, filename: str, content: bytes) -> DocumentUploadResponseDTO:
        # Check format
        ext = Path(filename).suffix.lower()
        if ext == ".pdf":
            doc_format = DocumentFormat.PDF
        elif ext == ".docx":
            doc_format = DocumentFormat.DOCX
        else:
            raise ValueError(f"Formato no admitido '{ext}'. Debe ser un archivo .pdf o .docx.")

        job_id = str(uuid.uuid4())
        saved_path = self.storage.save_upload(job_id=job_id, filename=filename, content=content)

        job = DocumentJob(
            job_id=job_id,
            filename=filename,
            format=doc_format,
            file_size_bytes=len(content),
            original_path=saved_path,
            status=JobStatus.UPLOADED
        )
        job_manager.create_job(job)

        return DocumentUploadResponseDTO(
            job_id=job_id,
            filename=filename,
            format=doc_format,
            file_size_bytes=len(content),
            status=JobStatus.UPLOADED,
            message="Documento cargado e inspeccionado de manera segura."
        )

    def analyze_document(self, job_id: str) -> AnalysisResponseDTO:
        job = job_manager.get_job(job_id)
        if not job:
            raise KeyError(f"Trabajo '{job_id}' no encontrado o expirado.")

        job.status = JobStatus.ANALYZING
        job_manager.update_job(job)

        # 1. Extract text blocks based on format
        if job.format == DocumentFormat.PDF:
            blocks = self.pdf_engine.extract_text_and_blocks(job.original_path)
        else:
            blocks = self.docx_engine.extract_text_and_blocks(job.original_path)

        # 2. Run detection engine
        detected_entities = self.detector.detect_entities(blocks)
        job.entities = detected_entities
        job.status = JobStatus.ANALYZED
        job_manager.update_job(job)

        # 3. Build response DTO
        high_c = sum(1 for e in detected_entities if e.confidence == DetectionConfidence.HIGH)
        med_c = sum(1 for e in detected_entities if e.confidence == DetectionConfidence.MEDIUM)
        low_c = sum(1 for e in detected_entities if e.confidence == DetectionConfidence.LOW)
        categories = sorted(list({e.category.value for e in detected_entities}))

        entity_dtos = [
            PIIEntityDTO(
                id=e.id,
                category=e.category,
                original_text=e.original_text,
                confidence=e.confidence,
                context=e.context,
                page_or_section=e.page_or_section,
                selected=e.selected,
                is_manual=e.is_manual,
                validation_details=e.validation_details
            )
            for e in detected_entities
        ]

        return AnalysisResponseDTO(
            job_id=job.job_id,
            status=job.status,
            total_entities=len(detected_entities),
            high_confidence_count=high_c,
            medium_confidence_count=med_c,
            low_confidence_count=low_c,
            entities=entity_dtos,
            categories_found=categories
        )

    def update_detections(self, job_id: str, request: UpdateDetectionsRequestDTO) -> AnalysisResponseDTO:
        job = job_manager.get_job(job_id)
        if not job:
            raise KeyError(f"Trabajo '{job_id}' no encontrado o expirado.")

        # Map existing entities
        existing_map = {e.id: e for e in job.entities}
        updated_entities: List[PIIEntity] = []

        for item in request.entities:
            if item.id and item.id in existing_map:
                ent = existing_map[item.id]
                ent.selected = item.selected
                ent.category = item.category
                updated_entities.append(ent)
            else:
                # Add manual entity
                new_ent = PIIEntity(
                    id=item.id or str(uuid.uuid4()),
                    category=item.category,
                    original_text=item.original_text,
                    start_char=0,
                    end_char=len(item.original_text),
                    confidence=DetectionConfidence.HIGH,
                    context="Entidad agregada manualmente por el usuario",
                    page_or_section=item.page_or_section,
                    selected=item.selected,
                    is_manual=True,
                    validation_details="Validación manual de usuario"
                )
                updated_entities.append(new_ent)

        job.entities = updated_entities
        job_manager.update_job(job)

        return self.analyze_document_summary(job)

    def anonymize_document(self, job_id: str, request: AnonymizeRequestDTO) -> AnonymizeResponseDTO:
        job = job_manager.get_job(job_id)
        if not job:
            raise KeyError(f"Trabajo '{job_id}' no encontrado o expirado.")

        job.status = JobStatus.ANONYMIZING
        job.strategy = request.strategy
        job.custom_placeholder = request.custom_placeholder
        job_manager.update_job(job)

        job_dir = self.storage.get_job_dir(job.job_id)
        out_ext = ".pdf" if job.format == DocumentFormat.PDF else ".docx"
        out_filename = f"anonymized_{Path(job.filename).stem}{out_ext}"
        out_path = str(job_dir / out_filename)

        # Execute anonymization
        if job.format == DocumentFormat.PDF:
            success, warnings = self.pdf_engine.anonymize(
                input_path=job.original_path,
                output_path=out_path,
                entities=job.entities,
                strategy=request.strategy,
                pseudonym_map=job.pseudonym_map,
                custom_placeholder=request.custom_placeholder
            )
        else:
            success, warnings = self.docx_engine.anonymize(
                input_path=job.original_path,
                output_path=out_path,
                entities=job.entities,
                strategy=request.strategy,
                pseudonym_map=job.pseudonym_map,
                custom_placeholder=request.custom_placeholder
            )

        job.anonymized_path = out_path
        job.status = JobStatus.COMPLETED
        job.warnings = warnings
        
        selected_count = sum(1 for e in job.entities if e.selected)
        job.stats = {
            "total_selected": selected_count,
            "verification_passed": success,
            "strategy": request.strategy.value
        }
        job_manager.update_job(job)

        return AnonymizeResponseDTO(
            job_id=job.job_id,
            status=job.status,
            strategy_used=request.strategy,
            total_anonymized=selected_count,
            download_url=f"/api/v1/documents/{job.job_id}/download",
            warnings=warnings,
            stats=job.stats
        )

    def get_download_path(self, job_id: str) -> Tuple[str, str, str]:
        """Returns (file_path, filename, media_type)."""
        job = job_manager.get_job(job_id)
        if not job or not job.anonymized_path or not Path(job.anonymized_path).exists():
            raise FileNotFoundError(f"Documento anonimizado para trabajo '{job_id}' no disponible.")

        media_type = "application/pdf" if job.format == DocumentFormat.PDF else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return job.anonymized_path, Path(job.anonymized_path).name, media_type

    def delete_job(self, job_id: str) -> bool:
        self.storage.cleanup_job(job_id)
        return job_manager.delete_job(job_id)

    def analyze_document_summary(self, job: DocumentJob) -> AnalysisResponseDTO:
        high_c = sum(1 for e in job.entities if e.confidence == DetectionConfidence.HIGH)
        med_c = sum(1 for e in job.entities if e.confidence == DetectionConfidence.MEDIUM)
        low_c = sum(1 for e in job.entities if e.confidence == DetectionConfidence.LOW)
        categories = sorted(list({e.category.value for e in job.entities}))

        entity_dtos = [
            PIIEntityDTO(
                id=e.id,
                category=e.category,
                original_text=e.original_text,
                confidence=e.confidence,
                context=e.context,
                page_or_section=e.page_or_section,
                selected=e.selected,
                is_manual=e.is_manual,
                validation_details=e.validation_details
            )
            for e in job.entities
        ]

        return AnalysisResponseDTO(
            job_id=job.job_id,
            status=job.status,
            total_entities=len(job.entities),
            high_confidence_count=high_c,
            medium_confidence_count=med_c,
            low_confidence_count=low_c,
            entities=entity_dtos,
            categories_found=categories
        )

    def health_check(self) -> HealthResponseDTO:
        purged = self.storage.purge_expired_jobs()
        active = len(job_manager.list_jobs())
        return HealthResponseDTO(
            status="healthy",
            version=AppConfig.VERSION,
            temp_dir=str(self.storage.base_dir),
            active_jobs=active
        )
