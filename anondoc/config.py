"""
Centralized Configuration for AnonDoc.
Independent configuration using environment variables or safe defaults.
"""
import os
from pathlib import Path
from typing import Set

class AppConfig:
    APP_NAME: str = "AnonDoc"
    VERSION: str = "2.0.0"
    DEBUG: bool = os.getenv("ANONDOC_DEBUG", "False").lower() in ("true", "1", "yes")

    # Storage & Lifecycle
    BASE_TEMP_DIR: Path = Path(os.getenv("ANONDOC_TEMP_DIR", "/tmp/anondoc")).resolve()
    JOB_TTL_SECONDS: int = int(os.getenv("ANONDOC_JOB_TTL", "1800"))  # 30 minutos

    # Security Limits
    MAX_FILE_SIZE_BYTES: int = int(os.getenv("ANONDOC_MAX_FILE_SIZE", str(25 * 1024 * 1024))) # 25 MB
    MAX_PAGES_LIMIT: int = int(os.getenv("ANONDOC_MAX_PAGES", "150"))
    MAX_DECOMPRESSED_RATIO: float = 60.0  # Zip Bomb protection ratio threshold
    MAX_DOCX_UNCOMPRESSED_BYTES: int = 100 * 1024 * 1024  # 100 MB max uncompressed

    # Formats & MIME types
    ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".docx"}
    ALLOWED_MIMES: Set[str] = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip"
    }

    # API & Network
    HOST: str = os.getenv("ANONDOC_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("ANONDOC_PORT", "8000"))
    CORS_ORIGINS: list[str] = ["*"]

    # Redaction defaults
    DEFAULT_REDACTION_PLACEHOLDER: str = "[DATO ANONIMIZADO]"

    @classmethod
    def ensure_directories(cls):
        cls.BASE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
