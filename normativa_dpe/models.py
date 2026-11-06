"""
Modelos de datos para el sistema de revisión y control normativo de la Defensoría del Pueblo del Ecuador.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

class DocumentFormat(str, Enum):
    DOC = "doc"
    DOCX = "docx"
    PDF = "pdf"

class ValidationStatus(str, Enum):
    PENDIENTE_REVISION = "PENDIENTE DE REVISIÓN TÉCNICA"
    VALIDADO_CONFORME = "VALIDADO JURÍDICAMENTE (SUJETO A FIRMA)"
    REQUIERE_AJUSTE = "REQUIERE AJUSTE TÉCNICO"

@dataclass
class DocumentParagraph:
    index: int
    text: str
    style_name: Optional[str] = None
    is_heading: bool = False
    heading_level: Optional[int] = None
    table_index: Optional[int] = None
    row_index: Optional[int] = None
    col_index: Optional[int] = None

@dataclass
class ExtractedDocument:
    filename: str
    file_path: str
    format: DocumentFormat
    paragraphs: List[DocumentParagraph] = field(default_factory=list)
    raw_text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ChangeRecord:
    ubicacion: str
    texto_original: str
    observacion: str
    justificacion: str
    propuesta_redaccion: str
    estado_validacion: str = ValidationStatus.PENDIENTE_REVISION.value
    fuente_respaldo: str = ""

@dataclass
class QualityControlReport:
    total_modifications: int
    modifications_backed_by_sources: bool
    unwarranted_claims_eliminated: bool
    sanitary_authority_competence_preserved: bool
    human_review_required: bool
    changes: List[ChangeRecord] = field(default_factory=list)
    audit_notes: List[str] = field(default_factory=list)
