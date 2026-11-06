"""
Paquete normativa_dpe: Auditoría y corrección automatizada de informes normativos para la Defensoría del Pueblo del Ecuador.
"""
from .pipeline import NormativeReviewPipeline
from .models import ChangeRecord, QualityControlReport, ValidationStatus

__version__ = "1.0.0"
__all__ = ["NormativeReviewPipeline", "ChangeRecord", "QualityControlReport", "ValidationStatus"]
