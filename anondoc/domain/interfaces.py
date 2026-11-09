"""
Domain Interfaces for Document Processing and Anonymization Engines.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
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
    def get_job_dir(self, job_id: str) -> Path:
        """Returns the private job directory path."""
        pass

    @abstractmethod
    def save_upload(self, job_id: str, extension: str, content: bytes) -> str:
        """Saves uploaded file securely and returns file path."""
        pass

    @abstractmethod
    def output_path(self, job_id: str, extension: str) -> str:
        """Returns the destination path for anonymized document."""
        pass

    @abstractmethod
    def remove_file(self, path: str) -> None:
        """Removes an individual file safely."""
        pass

    @abstractmethod
    def cleanup_job(self, job_id: str) -> bool:
        """Deletes all files associated with a job."""
        pass

    @abstractmethod
    def purge_expired_jobs(self, max_age_seconds: Optional[int] = None) -> int:
        """Purges job directories older than the TTL."""
        pass
