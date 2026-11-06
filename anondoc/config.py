"""
Centralized Configuration for AnonDoc.
Independent configuration using environment variables or safe defaults.
"""
import os
from pathlib import Path
from typing import List, Set


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_list(name: str) -> List[str]:
    return [v.strip() for v in os.getenv(name, "").split(",") if v.strip()]


class AppConfig:
    APP_NAME: str = "AnonDoc"
    VERSION: str = "2.0.0"
    DEBUG: bool = os.getenv("ANONDOC_DEBUG", "False").lower() in ("true", "1", "yes")

    # Storage & Lifecycle
    BASE_TEMP_DIR: Path = Path(os.getenv("ANONDOC_TEMP_DIR", "/tmp/anondoc")).resolve()  # nosec
    JOB_TTL_SECONDS: int = _env_int("ANONDOC_JOB_TTL", 1800)  # 30 minutos

    # Upload limits
    MAX_FILE_SIZE_BYTES: int = _env_int("ANONDOC_MAX_FILE_SIZE", 25 * 1024 * 1024)  # 25 MB
    MAX_PAGES_LIMIT: int = _env_int("ANONDOC_MAX_PAGES", 150)
    MAX_PDF_OBJECTS: int = _env_int("ANONDOC_MAX_PDF_OBJECTS", 200_000)

    # DOCX / ZIP limits
    MAX_DECOMPRESSED_RATIO: float = float(os.getenv("ANONDOC_MAX_ZIP_RATIO", "60"))
    MAX_DOCX_UNCOMPRESSED_BYTES: int = _env_int("ANONDOC_MAX_DOCX_UNCOMPRESSED", 100 * 1024 * 1024)
    MAX_ZIP_ENTRIES: int = _env_int("ANONDOC_MAX_ZIP_ENTRIES", 2000)
    MAX_ZIP_ENTRY_BYTES: int = _env_int("ANONDOC_MAX_ZIP_ENTRY_BYTES", 50 * 1024 * 1024)
    MAX_XML_NODES: int = _env_int("ANONDOC_MAX_XML_NODES", 2_000_000)

    # Processing / resource control
    MAX_CONCURRENT_JOBS: int = _env_int("ANONDOC_MAX_CONCURRENT_JOBS", 2)
    MAX_ACTIVE_JOBS: int = _env_int("ANONDOC_MAX_ACTIVE_JOBS", 100)
    WORKER_TIMEOUT_SECONDS: int = _env_int("ANONDOC_WORKER_TIMEOUT", 60)
    WORKER_MEMORY_BYTES: int = _env_int("ANONDOC_WORKER_MEMORY", 1024 * 1024 * 1024)
    WORKER_CPU_SECONDS: int = _env_int("ANONDOC_WORKER_CPU", 60)
    WORKER_MAX_OUTPUT_BYTES: int = _env_int("ANONDOC_WORKER_MAX_OUTPUT", 20 * 1024 * 1024)
    MAX_TEXT_BLOCK_CHARS: int = _env_int("ANONDOC_MAX_TEXT_BLOCK_CHARS", 200_000)
    MAX_ENTITIES_PER_JOB: int = _env_int("ANONDOC_MAX_ENTITIES", 5000)

    # Rate limiting (per client IP, in-memory, sliding window)
    RATE_LIMIT_REQUESTS: int = _env_int("ANONDOC_RATE_LIMIT", 120)
    RATE_LIMIT_WINDOW_SECONDS: int = _env_int("ANONDOC_RATE_WINDOW", 60)
    UPLOAD_RATE_LIMIT: int = _env_int("ANONDOC_UPLOAD_RATE_LIMIT", 10)

    # Formats: real type is decided from content, never from client-provided MIME.
    ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".docx"}

    # API & Network
    HOST: str = os.getenv("ANONDOC_HOST", "127.0.0.1")
    PORT: int = _env_int("ANONDOC_PORT", 8000)
    # Same-origin only by default. Example: ANONDOC_CORS_ORIGINS="https://a.example,https://b.example"
    CORS_ORIGINS: List[str] = _env_list("ANONDOC_CORS_ORIGINS")
    ENABLE_DOCS: bool = os.getenv("ANONDOC_ENABLE_DOCS", "False").lower() in ("true", "1", "yes")

    # Redaction defaults
    DEFAULT_REDACTION_PLACEHOLDER: str = "[DATO ANONIMIZADO]"

    @classmethod
    def ensure_directories(cls):
        cls.BASE_TEMP_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
