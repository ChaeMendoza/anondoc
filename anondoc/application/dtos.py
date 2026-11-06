"""
Data Transfer Objects (DTOs) for Application and API Layers.
"""
from pydantic import BaseModel, Field
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

class AnalysisResponseDTO(BaseModel):
    job_id: str
    status: JobStatus
    total_entities: int
    high_confidence_count: int
    medium_confidence_count: int
    low_confidence_count: int
    entities: List[PIIEntityDTO]
    categories_found: List[str]

class EntityUpdateItemDTO(BaseModel):
    id: Optional[str] = None
    category: EntityCategory
    original_text: str
    selected: bool = True
    page_or_section: str = "1"
    is_manual: bool = False

class UpdateDetectionsRequestDTO(BaseModel):
    entities: List[EntityUpdateItemDTO]

class AnonymizeRequestDTO(BaseModel):
    strategy: AnonymizationStrategy = AnonymizationStrategy.REDACTION
    custom_placeholder: Optional[str] = None

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
    temp_dir: str
    active_jobs: int
