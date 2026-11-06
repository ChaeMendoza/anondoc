"""
Thread-safe ephemeral job registry with capability-token authorization.

Possessing a job_id is never enough: every access must present the secret
access token returned once at upload time (only its SHA-256 is stored).
"""
import hashlib
import hmac
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from anondoc.config import AppConfig
from anondoc.domain.entities import DocumentJob


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_job_id() -> str:
    return secrets.token_urlsafe(16)


def new_access_token() -> str:
    return secrets.token_urlsafe(32)


class JobLimitReached(Exception):
    pass


class JobManager:
    def __init__(self):
        self._jobs: Dict[str, DocumentJob] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _expired(job: DocumentJob) -> bool:
        return bool(job.expires_at and datetime.now(timezone.utc) > job.expires_at)

    def create_job(self, job: DocumentJob) -> DocumentJob:
        with self._lock:
            if len(self._jobs) >= AppConfig.MAX_ACTIVE_JOBS:
                raise JobLimitReached()
            job.expires_at = datetime.now(timezone.utc) + timedelta(seconds=AppConfig.JOB_TTL_SECONDS)
            self._jobs[job.job_id] = job
            return job

    def get_authorized_job(self, job_id: str, token: Optional[str]) -> Optional[DocumentJob]:
        """Returns the job only if the token matches; unknown, expired and forbidden are indistinguishable."""
        with self._lock:
            job = self._jobs.get(job_id)
            expected = job.access_token_hash if job else hash_token("")
            presented = hash_token(token or "")
            ok = hmac.compare_digest(expected, presented)
            if not job or not ok or not token:
                return None
            if self._expired(job):
                del self._jobs[job_id]
                return None
            return job

    def begin_operation(self, job: DocumentJob) -> bool:
        with self._lock:
            if job.busy:
                return False
            job.busy = True
            return True

    def end_operation(self, job: DocumentJob) -> None:
        with self._lock:
            job.busy = False

    def update_job(self, job: DocumentJob) -> None:
        with self._lock:
            if job.job_id in self._jobs:
                self._jobs[job.job_id] = job

    def delete_job(self, job_id: str) -> bool:
        with self._lock:
            return self._jobs.pop(job_id, None) is not None

    def pop_expired(self) -> List[str]:
        with self._lock:
            ids = [jid for jid, j in self._jobs.items() if self._expired(j)]
            for jid in ids:
                del self._jobs[jid]
            return ids

    def count_active(self) -> int:
        self.pop_expired()
        with self._lock:
            return len(self._jobs)


def issue_credentials() -> Tuple[str, str, str]:
    """Returns (job_id, access_token, token_hash)."""
    token = new_access_token()
    return new_job_id(), token, hash_token(token)


job_manager = JobManager()
