"""Builds the PII detector configured for this deployment."""
import logging

from anondoc.config import AppConfig
from anondoc.domain.interfaces import IPIIDetector
from anondoc.infrastructure.detection.composite_detector import CompositePIIDetector
from anondoc.infrastructure.detection.gliner_detector import GLiNERDetector
from anondoc.infrastructure.detection.pii_detector import HybridPIIDetector

ops_log = logging.getLogger("anondoc.ops")


def build_detector() -> IPIIDetector:
    """Deterministic engine by default; deterministic + local GLiNER when ANONDOC_ENABLE_GLINER is set."""
    if not AppConfig.ENABLE_GLINER:
        return HybridPIIDetector()
    ops_log.info("op=build_detector mode=hybrid_gliner")
    return CompositePIIDetector(semantic_detector=GLiNERDetector())
