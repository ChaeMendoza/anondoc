"""
Thread-safe Ephemeral Job Manager for Isolated Document Workflows.
"""
import threading
from typing import Dict, Optional, List
from datetime import datetime, timezone, timedelta
from anondoc.domain.entities import DocumentJob, JobStatus
from anondoc.config import AppConfig

class JobManager:
    """Stores active jobs in memory with automatic expiration."""

    def __init__(self):
        self._jobs: Dict[str, DocumentJob] = {}
        self._lock = threading.Lock()

    def create_job(self, job: DocumentJob) -> DocumentJob:
        with self._lock:
            job.expires_at = datetime.now(timezone.utc) + timedelta(seconds=AppConfig.JOB_TTL_SECONDS)
            self._jobs[job.job_id] = job
            return job

    def get_job(self, job_id: str) -> Optional[DocumentJob]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            # Check expiration
            if job.expires_at and datetime.now(timezone.utc) > job.expires_at:
                del self._jobs[job_id]
                return None
            return job

    def update_job(self, job: DocumentJob):
        with self._lock:
            self._jobs[job.job_id] = job

    def delete_job(self, job_id: str) -> bool:
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                return True
            return False

    def list_jobs(self) -> List[DocumentJob]:
        with self._lock:
            now = datetime.now(timezone.utc)
            active = []
            for jid, job in list(self._jobs.items()):
                if job.expires_at and now > job.expires_at:
                    del self._jobs[jid]
                else:
                    active.append(job)
            return active

# Global singleton instance
job_manager = JobManager()
