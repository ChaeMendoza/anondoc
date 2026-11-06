"""
Domain Interfaces for Document Processing and Anonymization Engines.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
from anondoc.domain.entities import PIIEntity, AnonymizationStrategy

class IDocumentExtractor(ABC):
    @abstractmethod
    def extract_text_and_blocks(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extracts structured blocks of text with page/section coordinates or identifiers.
        Returns a list of dicts: [{"text": str, "page_or_section": str, "metadata": dict}]
        """
        pass

class IPIIDetector(ABC):
    @abstractmethod
    def detect_entities(self, text_blocks: List[Dict[str, Any]]) -> List[PIIEntity]:
        """Detects PII entities across extracted text blocks."""
        pass

class IDocumentAnonymizer(ABC):
    @abstractmethod
    def anonymize(
        self,
        input_path: str,
        output_path: str,
        entities: List[PIIEntity],
        strategy: AnonymizationStrategy,
        pseudonym_map: Dict[str, str],
        custom_placeholder: str = None
    ) -> Tuple[bool, List[str]]:
        """
        Applies redactions/pseudonymization to document.
        Returns (success: bool, warnings: List[str]).
        """
        pass

class IStorageService(ABC):
    @abstractmethod
    def save_upload(self, filename: str, content: bytes) -> str:
        """Saves uploaded file securely and returns file path."""
        pass

    @abstractmethod
    def cleanup_job(self, job_id: str) -> bool:
        """Deletes all files associated with a job."""
        pass
