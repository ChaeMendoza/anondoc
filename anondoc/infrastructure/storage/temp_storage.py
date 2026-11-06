"""
Secure Temporary Storage Service with Path Traversal, Magic Byte & Zip Bomb Protections.
"""
import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import Tuple
from anondoc.config import AppConfig

class SecureStorageService:
    """Manages ephemeral files securely with strict isolation and validation."""

    def __init__(self, base_dir: Path = None):
        self.base_dir = (base_dir or AppConfig.BASE_TEMP_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_job_dir(self, job_id: str) -> Path:
        """Returns safe isolated directory for a job, verifying against path traversal."""
        job_dir = (self.base_dir / job_id).resolve()
        if not str(job_dir).startswith(str(self.base_dir)):
            raise ValueError("Acceso no autorizado: intento de Path Traversal detectado.")
        return job_dir

    def validate_file_security(self, content: bytes, filename: str) -> Tuple[bool, str]:
        """
        Validates:
        1. File size limit.
        2. Extension whitelist.
        3. Magic bytes sniffing.
        4. Zip bomb inspection for DOCX.
        """
        # 1. Size check
        if len(content) > AppConfig.MAX_FILE_SIZE_BYTES:
            return False, f"El archivo excede el tamaño máximo permitido ({AppConfig.MAX_FILE_SIZE_BYTES // (1024*1024)} MB)."

        # 2. Extension check
        ext = Path(filename).suffix.lower()
        if ext not in AppConfig.ALLOWED_EXTENSIONS:
            return False, f"Extensión '{ext}' no soportada. Formatos válidos: PDF, DOCX."

        # 3. Magic bytes check
        if ext == ".pdf":
            if not content.startswith(b"%PDF-"):
                return False, "Firma de archivo PDF inválida (magic bytes corruptos o no auténticos)."
        elif ext == ".docx":
            if not content.startswith(b"PK\x03\x04"):
                return False, "Firma de archivo DOCX inválida (el archivo debe ser un contenedor ZIP OOXML legítimo)."

            # 4. Zip Bomb & XML integrity check for DOCX
            try:
                import io
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    total_uncompressed = 0
                    total_compressed = len(content)
                    
                    # Must contain word/document.xml
                    has_document_xml = False
                    for info in zf.infolist():
                        # Prevent zip slip
                        if ".." in info.filename or info.filename.startswith("/"):
                            return False, "Riesgo de seguridad: archivo ZIP contiene rutas maliciosas (Zip Slip)."
                        total_uncompressed += info.file_size
                        if info.filename == "word/document.xml":
                            has_document_xml = True

                    if not has_document_xml:
                        return False, "Estructura de documento Word inválida (falta word/document.xml)."

                    if total_compressed > 0 and total_uncompressed > 5 * 1024 * 1024:
                        ratio = total_uncompressed / total_compressed
                        if ratio > AppConfig.MAX_DECOMPRESSED_RATIO:
                            return False, f"Riesgo de seguridad: archivo comprimido excede ratio de descompresión seguro ({ratio:.1f}x)."

                    if total_uncompressed > AppConfig.MAX_DOCX_UNCOMPRESSED_BYTES:
                        return False, "Riesgo de seguridad: archivo descomprimido excede límite de memoria permitido."

            except zipfile.BadZipFile:
                return False, "El archivo DOCX está dañado o no es un ZIP válido."

        return True, "Archivo válido y seguro."

    def save_upload(self, job_id: str, filename: str, content: bytes) -> str:
        """Saves file inside isolated job directory."""
        valid, msg = self.validate_file_security(content, filename)
        if not valid:
            raise ValueError(msg)

        job_dir = self.get_job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = Path(filename).name  # Strips any directory components
        dest_path = job_dir / f"original_{safe_filename}"
        dest_path.write_bytes(content)
        return str(dest_path)

    def cleanup_job(self, job_id: str) -> bool:
        """Removes the entire job folder."""
        job_dir = self.get_job_dir(job_id)
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
            return True
        return False

    def purge_expired_jobs(self, max_age_seconds: int = None) -> int:
        """Purges any directory older than TTL."""
        ttl = max_age_seconds or AppConfig.JOB_TTL_SECONDS
        now = time.time()
        purged = 0
        if not self.base_dir.exists():
            return 0

        for item in self.base_dir.iterdir():
            if item.is_dir():
                mtime = item.stat().st_mtime
                if (now - mtime) > ttl:
                    shutil.rmtree(item, ignore_errors=True)
                    purged += 1
        return purged
