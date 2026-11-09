"""
Domain Entities for AnonDoc.
Pure domain layer without external framework dependencies.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
import uuid

class EntityCategory(str, Enum):
    PERSON = "PERSON"
    ECUADOR_CEDULA = "ECUADOR_CEDULA"
    ECUADOR_RUC = "ECUADOR_RUC"
    PASSPORT = "PASSPORT"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    CREDIT_CARD = "CREDIT_CARD"
    BANK_ACCOUNT = "BANK_ACCOUNT"
    DATE_OF_BIRTH = "DATE_OF_BIRTH"
    IP_ADDRESS = "IP_ADDRESS"
    VEHICLE_PLATE = "VEHICLE_PLATE"
    ADDRESS = "ADDRESS"
    USERNAME = "USERNAME"
    MEDICAL_DATA = "MEDICAL_DATA"
    FINANCIAL_DATA = "FINANCIAL_DATA"

class DetectionConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class AnonymizationStrategy(str, Enum):
    REDACTION = "REDACTION"
    PSEUDONYMIZATION = "PSEUDONYMIZATION"
    MASKING = "MASKING"

class DocumentFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"

class JobStatus(str, Enum):
    UPLOADED = "UPLOADED"
    ANALYZING = "ANALYZING"
    ANALYZED = "ANALYZED"
    ANONYMIZING = "ANONYMIZING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"

@dataclass
class PIIEntity:
    """Represents a single detected or manual personal identification item."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    category: EntityCategory = EntityCategory.PERSON
    original_text: str = ""
    start_char: int = 0
    end_char: int = 0
    confidence: DetectionConfidence = DetectionConfidence.MEDIUM
    context: str = ""
    page_or_section: str = "1"
    selected: bool = True
    replacement_value: Optional[str] = None
    is_manual: bool = False
    validation_details: Optional[str] = None

@dataclass
class DocumentJob:
    """Represents an isolated document anonymization job."""
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    filename: str = ""
    format: DocumentFormat = DocumentFormat.PDF
    file_size_bytes: int = 0
    original_path: str = ""
    anonymized_path: Optional[str] = None
    status: JobStatus = JobStatus.UPLOADED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    entities: List[PIIEntity] = field(default_factory=list)
    strategy: AnonymizationStrategy = AnonymizationStrategy.REDACTION
    custom_placeholder: Optional[str] = None
    stats: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    pseudonym_map: Dict[str, str] = field(default_factory=dict)
    access_token_hash: str = ""
    limitations: List[str] = field(default_factory=list)
    busy: bool = False
    analysis_partial: bool = False
    partial_reason: Optional[str] = None
