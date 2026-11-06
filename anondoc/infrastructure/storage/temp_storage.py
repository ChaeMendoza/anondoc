"""
Secure temporary storage: random job identifiers, per-job private directories,
fixed server-side file names (user-supplied names are never used as paths).
"""
import os
import re
import shutil
import time
from pathlib import Path

from anondoc.config import AppConfig

JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{22}$")


class SecureStorageService:
    """Manages ephemeral files with strict per-job isolation."""

    def __init__(self, base_dir: Path = None):
        self.base_dir = (base_dir or AppConfig.BASE_TEMP_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    def get_job_dir(self, job_id: str) -> Path:
        """Returns the job directory; rejects any identifier that is not one we generated."""
        if not isinstance(job_id, str) or not JOB_ID_RE.fullmatch(job_id):
            raise ValueError("Identificador de trabajo inválido.")
        job_dir = (self.base_dir / job_id).resolve()
        if job_dir.parent != self.base_dir:
            raise ValueError("Identificador de trabajo inválido.")
        return job_dir

    def create_job_dir(self, job_id: str) -> Path:
        job_dir = self.get_job_dir(job_id)
        job_dir.mkdir(mode=0o700, exist_ok=False)
        return job_dir

    def save_upload(self, job_id: str, extension: str, content: bytes) -> str:
        """Writes the original upload as <job_dir>/original<ext>; ext must be .pdf or .docx."""
        if extension not in AppConfig.ALLOWED_EXTENSIONS:
            raise ValueError("Formato no admitido.")
        job_dir = self.create_job_dir(job_id)
        dest = job_dir / f"original{extension}"
        fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
        return str(dest)

    def output_path(self, job_id: str, extension: str) -> str:
        if extension not in AppConfig.ALLOWED_EXTENSIONS:
            raise ValueError("Formato no admitido.")
        return str(self.get_job_dir(job_id) / f"anonymized{extension}")

    def remove_file(self, path: str) -> None:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass

    def cleanup_job(self, job_id: str) -> bool:
        """Removes the entire job folder."""
        job_dir = self.get_job_dir(job_id)
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
            return True
        return False

    def purge_expired_jobs(self, max_age_seconds: int = None) -> int:
        """Purges job directories older than the TTL (0 purges everything)."""
        ttl = AppConfig.JOB_TTL_SECONDS if max_age_seconds is None else max_age_seconds
        now = time.time()
        purged = 0
        if not self.base_dir.exists():
            return 0

        for item in self.base_dir.iterdir():
            if item.is_dir() and not item.is_symlink():
                if (now - item.stat().st_mtime) >= ttl:
                    shutil.rmtree(item, ignore_errors=True)
                    purged += 1
        return purged
