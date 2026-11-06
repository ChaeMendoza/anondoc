"""
Application use cases orchestrating storage, the isolated worker and PII detection.

Authorization is enforced by the API layer before any use case receives a job.
Logs contain only operational data (job id, operation, outcome, error code).
"""
import logging
import re
import time
import uuid
from pathlib import Path
from typing import List, Tuple

from anondoc.application.dtos import (
    AnalysisResponseDTO,
    AnonymizeRequestDTO,
    AnonymizeResponseDTO,
    DocumentUploadResponseDTO,
    HealthResponseDTO,
    PIIEntityDTO,
    UpdateDetectionsRequestDTO,
)
from anondoc.application.job_manager import issue_credentials, job_manager
from anondoc.config import AppConfig
from anondoc.domain.entities import (
    DetectionConfidence,
    DocumentFormat,
    DocumentJob,
    JobStatus,
    PIIEntity,
)
from anondoc.infrastructure.detection.pii_detector import HybridPIIDetector
from anondoc.infrastructure.sandbox.runner import WorkerError, run_worker
from anondoc.infrastructure.security.inspector import DocumentRejected, detect_format
from anondoc.infrastructure.storage.temp_storage import SecureStorageService

security_log = logging.getLogger("anondoc.security")
ops_log = logging.getLogger("anondoc.ops")

MEDIA_TYPES = {
    DocumentFormat.PDF: "application/pdf",
    DocumentFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class JobBusy(Exception):
    """Another operation is already running on the same job."""


class JobStateError(Exception):
    """The job is not in a state that allows the requested operation."""


class VerificationFailed(Exception):
    """Post-anonymization verification failed; no document is delivered."""


def display_name(filename: str) -> str:
    """Display-only name: basename, no control characters, bounded length. Never used as a path."""
    base = re.split(r"[\\/]", filename or "")[-1]
    base = re.sub(r"[\x00-\x1f\x7f]", "", base).strip()
    return (base or "documento")[:100]


class DocumentUseCases:
    def __init__(self, storage: SecureStorageService = None):
        self.storage = storage or SecureStorageService()
        self.detector = HybridPIIDetector()

    # ------------------------------------------------------------------ upload
    def upload_document(self, filename: str, content: bytes) -> DocumentUploadResponseDTO:
        if len(content) == 0:
            raise DocumentRejected("empty_file", "El archivo está vacío.")
        if len(content) > AppConfig.MAX_FILE_SIZE_BYTES:
            raise DocumentRejected("file_too_large", f"El archivo excede el tamaño máximo permitido ({AppConfig.MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB).")

        fmt = detect_format(content[:8])
        ext = ".pdf" if fmt == "pdf" else ".docx"
        declared = Path(display_name(filename)).suffix.lower()
        if declared != ext:
            raise DocumentRejected("extension_mismatch", "La extensión no coincide con el contenido real del archivo.")
        doc_format = DocumentFormat.PDF if fmt == "pdf" else DocumentFormat.DOCX

        job_id, token, token_hash = issue_credentials()
        saved_path = self.storage.save_upload(job_id=job_id, extension=ext, content=content)
        started = time.monotonic()
        try:
            info = run_worker(
                {"op": "inspect", "fmt": fmt, "path": saved_path, "size": len(content)},
                cwd=str(self.storage.get_job_dir(job_id)),
            )
            job = DocumentJob(
                job_id=job_id,
                filename=display_name(filename),
                format=doc_format,
                file_size_bytes=len(content),
                original_path=saved_path,
                status=JobStatus.UPLOADED,
                access_token_hash=token_hash,
                limitations=info.get("limitations", []),
            )
            job_manager.create_job(job)
        except (WorkerError, DocumentRejected) as exc:
            self.storage.cleanup_job(job_id)
            security_log.warning("event=upload_rejected job=%s code=%s", job_id, exc.code)
            raise
        except Exception:
            self.storage.cleanup_job(job_id)
            raise
        ops_log.info("op=upload job=%s result=ok duration_ms=%d", job_id, (time.monotonic() - started) * 1000)

        return DocumentUploadResponseDTO(
            job_id=job_id,
            filename=job.filename,
            format=doc_format,
            file_size_bytes=len(content),
            status=JobStatus.UPLOADED,
            message="Documento cargado e inspeccionado.",
            access_token=token,
        )

    # ------------------------------------------------------------------ analysis
    def analyze_document(self, job: DocumentJob) -> AnalysisResponseDTO:
        if job.status not in (JobStatus.UPLOADED, JobStatus.ANALYZED):
            raise JobStateError("El trabajo no admite análisis en su estado actual.")
        if not job_manager.begin_operation(job):
            raise JobBusy()
        started = time.monotonic()
        try:
            job.status = JobStatus.ANALYZING
            try:
                resp = run_worker(
                    {"op": "extract", "fmt": job.format.value, "path": job.original_path, "size": job.file_size_bytes},
                    cwd=str(self.storage.get_job_dir(job.job_id)),
                )
            except WorkerError as exc:
                job.status = JobStatus.UPLOADED
                security_log.warning("event=analysis_failed job=%s code=%s", job.job_id, exc.code)
                raise
            entities = self.detector.detect_entities(resp["blocks"])
            job.entities = entities[: AppConfig.MAX_ENTITIES_PER_JOB]
            job.limitations = resp.get("limitations", job.limitations)
            job.status = JobStatus.ANALYZED
            job_manager.update_job(job)
            ops_log.info("op=analyze job=%s result=ok entities=%d duration_ms=%d",
                         job.job_id, len(job.entities), (time.monotonic() - started) * 1000)
            return self.analysis_summary(job)
        finally:
            if job.status == JobStatus.ANALYZING:
                job.status = JobStatus.UPLOADED
            job_manager.end_operation(job)

    def update_detections(self, job: DocumentJob, request: UpdateDetectionsRequestDTO) -> AnalysisResponseDTO:
        if job.status != JobStatus.ANALYZED:
            raise JobStateError("El trabajo no admite cambios en su estado actual.")
        existing = {e.id: e for e in job.entities}
        updated: List[PIIEntity] = []
        used_ids = set()

        for item in request.entities:
            if item.id and item.id in existing and item.id not in used_ids:
                ent = existing[item.id]
                ent.selected = item.selected
                ent.category = item.category
                updated.append(ent)
                used_ids.add(ent.id)
            elif item.original_text.strip():
                new_id = item.id if item.id and item.id not in existing and item.id not in used_ids else str(uuid.uuid4())
                used_ids.add(new_id)
                updated.append(PIIEntity(
                    id=new_id,
                    category=item.category,
                    original_text=item.original_text,
                    start_char=0,
                    end_char=len(item.original_text),
                    confidence=DetectionConfidence.HIGH,
                    context="Entidad agregada manualmente por el usuario",
                    page_or_section=item.page_or_section,
                    selected=item.selected,
                    is_manual=True,
                    validation_details="Validación manual de usuario",
                ))

        job.entities = updated[: AppConfig.MAX_ENTITIES_PER_JOB]
        job_manager.update_job(job)
        return self.analysis_summary(job)

    # ------------------------------------------------------------------ anonymization
    def anonymize_document(self, job: DocumentJob, request: AnonymizeRequestDTO) -> AnonymizeResponseDTO:
        if job.status != JobStatus.ANALYZED:
            raise JobStateError("El documento debe analizarse antes de anonimizarse.")
        if not job_manager.begin_operation(job):
            raise JobBusy()
        started = time.monotonic()
        out_path = self.storage.output_path(job.job_id, ".pdf" if job.format == DocumentFormat.PDF else ".docx")
        try:
            job.status = JobStatus.ANONYMIZING
            try:
                resp = run_worker(
                    {
                        "op": "anonymize",
                        "fmt": job.format.value,
                        "path": job.original_path,
                        "size": job.file_size_bytes,
                        "output": out_path,
                        "strategy": request.strategy.value,
                        "placeholder": request.custom_placeholder,
                        "entities": [
                            {"id": e.id, "category": e.category.value, "original_text": e.original_text, "selected": e.selected}
                            for e in job.entities
                        ],
                    },
                    cwd=str(self.storage.get_job_dir(job.job_id)),
                )
            except WorkerError as exc:
                self.storage.remove_file(out_path)
                job.status = JobStatus.ANALYZED
                security_log.warning("event=anonymize_failed job=%s code=%s", job.job_id, exc.code)
                raise

            if not resp.get("verification_passed"):
                self.storage.remove_file(out_path)
                job.status = JobStatus.ANALYZED
                security_log.warning("event=verification_failed job=%s", job.job_id)
                raise VerificationFailed("; ".join(resp.get("warnings", [])))

            selected_count = sum(1 for e in job.entities if e.selected)
            job.anonymized_path = out_path
            job.status = JobStatus.COMPLETED
            job.strategy = request.strategy
            job.warnings = resp.get("warnings", [])
            job.stats = {
                "total_selected": selected_count,
                "verification_passed": True,
                "strategy": request.strategy.value,
            }
            # Data minimization: the original and the detected values are not kept after success.
            self.storage.remove_file(job.original_path)
            job.original_path = ""
            job.entities = []
            job.pseudonym_map.clear()
            job_manager.update_job(job)
            ops_log.info("op=anonymize job=%s result=ok duration_ms=%d", job.job_id, (time.monotonic() - started) * 1000)

            return AnonymizeResponseDTO(
                job_id=job.job_id,
                status=job.status,
                strategy_used=request.strategy,
                total_anonymized=selected_count,
                download_url=f"/api/v1/documents/{job.job_id}/download",
                warnings=job.warnings,
                stats=job.stats,
            )
        finally:
            if job.status == JobStatus.ANONYMIZING:
                self.storage.remove_file(out_path)
                job.status = JobStatus.ANALYZED
            job_manager.end_operation(job)

    def get_download_path(self, job: DocumentJob) -> Tuple[str, str, str]:
        """Returns (file_path, download_name, media_type)."""
        if job.status != JobStatus.COMPLETED or not job.anonymized_path or not Path(job.anonymized_path).exists():
            raise FileNotFoundError("Documento anonimizado no disponible.")
        ext = Path(job.anonymized_path).suffix
        return job.anonymized_path, f"anonymized_{job.job_id[:8]}{ext}", MEDIA_TYPES[job.format]

    def delete_job(self, job: DocumentJob) -> bool:
        self.storage.cleanup_job(job.job_id)
        return job_manager.delete_job(job.job_id)

    # ------------------------------------------------------------------ helpers
    def analysis_summary(self, job: DocumentJob) -> AnalysisResponseDTO:
        counts = {c: sum(1 for e in job.entities if e.confidence == c) for c in DetectionConfidence}
        return AnalysisResponseDTO(
            job_id=job.job_id,
            status=job.status,
            total_entities=len(job.entities),
            high_confidence_count=counts[DetectionConfidence.HIGH],
            medium_confidence_count=counts[DetectionConfidence.MEDIUM],
            low_confidence_count=counts[DetectionConfidence.LOW],
            entities=[
                PIIEntityDTO(
                    id=e.id,
                    category=e.category,
                    original_text=e.original_text,
                    confidence=e.confidence,
                    context=e.context,
                    page_or_section=e.page_or_section,
                    selected=e.selected,
                    is_manual=e.is_manual,
                    validation_details=e.validation_details,
                )
                for e in job.entities
            ],
            categories_found=sorted({e.category.value for e in job.entities}),
            limitations=job.limitations,
        )

    def purge_expired(self) -> int:
        for job_id in job_manager.pop_expired():
            self.storage.cleanup_job(job_id)
        return self.storage.purge_expired_jobs()

    def health_check(self) -> HealthResponseDTO:
        return HealthResponseDTO(status="healthy", version=AppConfig.VERSION, active_jobs=job_manager.count_active())
