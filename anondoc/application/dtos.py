"""
Data Transfer Objects (DTOs) for Application and API Layers.
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any
from anondoc.domain.entities import EntityCategory, DetectionConfidence, AnonymizationStrategy, JobStatus, DocumentFormat

class PIIEntityDTO(BaseModel):
    id: str
    category: EntityCategory
    original_text: str
    confidence: DetectionConfidence
    context: str
    page_or_section: str
    selected: bool
    replacement_value: Optional[str] = None
    is_manual: bool = False
    validation_details: Optional[str] = None

class DocumentUploadResponseDTO(BaseModel):
    job_id: str
    filename: str
    format: DocumentFormat
    file_size_bytes: int
    status: JobStatus
    message: str
    access_token: str

class AnalysisResponseDTO(BaseModel):
    job_id: str
    status: JobStatus
    total_entities: int
    high_confidence_count: int
    medium_confidence_count: int
    low_confidence_count: int
    entities: List[PIIEntityDTO]
    categories_found: List[str]
    limitations: List[str] = Field(default_factory=list)

class EntityUpdateItemDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: Optional[str] = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    category: EntityCategory
    original_text: str = Field(max_length=500)
    selected: bool = True
    page_or_section: str = Field(default="1", max_length=100)
    is_manual: bool = False

class UpdateDetectionsRequestDTO(BaseModel):
    entities: List[EntityUpdateItemDTO] = Field(max_length=5000)

class AnonymizeRequestDTO(BaseModel):
    strategy: AnonymizationStrategy = AnonymizationStrategy.REDACTION
    custom_placeholder: Optional[str] = Field(default=None, max_length=64)

class AnonymizeResponseDTO(BaseModel):
    job_id: str
    status: JobStatus
    strategy_used: AnonymizationStrategy
    total_anonymized: int
    download_url: str
    warnings: List[str]
    stats: Dict[str, Any]

class HealthResponseDTO(BaseModel):
    status: str
    version: str
    active_jobs: int
