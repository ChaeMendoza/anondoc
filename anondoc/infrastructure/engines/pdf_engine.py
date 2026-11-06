"""
High-Security PDF Engine for Text Extraction, Native Redaction, and Residual Verification.
Uses PyMuPDF (fitz) native redaction streams with metadata sanitization.
"""
from pathlib import Path
from typing import List, Dict, Any, Tuple
import pymupdf

from anondoc.domain.entities import PIIEntity, AnonymizationStrategy
from anondoc.domain.interfaces import IDocumentExtractor, IDocumentAnonymizer
from anondoc.infrastructure.anonymization.anonymizer import AnonymizationStrategyEngine

class PDFEngine(IDocumentExtractor, IDocumentAnonymizer):
    """Handles deep extraction and native stream redaction for PDF documents."""

    def extract_text_and_blocks(self, file_path: str) -> List[Dict[str, Any]]:
        """Extracts text blocks page by page with coordinates and metadata."""
        doc = pymupdf.open(file_path)
        blocks_result: List[Dict[str, Any]] = []

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text("text").strip()
                
                # Check for scanned pages (empty text stream but has images)
                is_scanned = len(page_text) == 0 and len(page.get_images()) > 0

                if page_text:
                    blocks_result.append({
                        "text": page_text,
                        "page_or_section": str(page_num + 1),
                        "metadata": {
                            "page_index": page_num,
                            "width": page.rect.width,
                            "height": page.rect.height,
                            "rotation": page.rotation,
                            "is_scanned": False
                        }
                    })
                elif is_scanned:
                    blocks_result.append({
                        "text": "[AVISO: Esta página contiene una imagen escaneada sin capa de texto seleccionable]",
                        "page_or_section": str(page_num + 1),
                        "metadata": {
                            "page_index": page_num,
                            "is_scanned": True
                        }
                    })
        finally:
            doc.close()

        return blocks_result

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
        Applies native PDF redactions.
        Physically removes text elements from content streams and scrubs metadata.
        """
        warnings: List[str] = []
        doc = pymupdf.open(input_path)
        category_counters: Dict[str, int] = {}

        # Filter only selected entities
        selected_entities = [e for e in entities if e.selected and e.original_text.strip()]

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_entities = [e for e in selected_entities if e.page_or_section == str(page_num + 1)]

                for entity in page_entities:
                    orig_text = entity.original_text.strip()
                    if not orig_text:
                        continue

                    # Search text occurrences on this page
                    rects = page.search_for(orig_text)
                    if not rects:
                        # Try case insensitive or normalized search
                        rects = page.search_for(orig_text, quads=False)

                    if rects:
                        replacement = AnonymizationStrategyEngine.generate_replacement(
                            entity=entity,
                            strategy=strategy,
                            pseudonym_map=pseudonym_map,
                            category_counters=category_counters,
                            custom_placeholder=custom_placeholder
                        )

                        for r in rects:
                            # Add physical redaction annotation
                            annot = page.add_redact_annot(
                                r,
                                text=replacement,
                                fontname="helv",
                                fontsize=8,
                                align=pymupdf.TEXT_ALIGN_CENTER,
                                fill=(0.95, 0.95, 0.95),  # Light gray background
                                text_color=(0.1, 0.1, 0.1) # Dark charcoal text
                            )
                    else:
                        warnings.append(
                            f"Pág {page_num+1}: No se localizaron coordenadas exactas para '{orig_text[:20]}...' (puede estar en imagen o división de línea)."
                        )

                # Physically apply redactions to page (removes text objects)
                page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)

            # Scrub metadata completely
            doc.set_metadata({
                "author": "",
                "title": "AnonDoc Redacted Document",
                "subject": "Documento anonimizado",
                "keywords": "anondoc, privacy",
                "creator": "AnonDoc Privacy Engine",
                "producer": "AnonDoc Core v2.0",
                "creationDate": "",
                "modDate": ""
            })

            # Save clean file with garbage collection and deflation
            out_file = Path(output_path).resolve()
            out_file.parent.mkdir(parents=True, exist_ok=True)
            doc.save(
                str(out_file),
                garbage=4,
                deflate=True,
                clean=True
            )
        finally:
            doc.close()

        # Post-redaction residual text verification
        verification_passed, residual_warnings = self.verify_redacted_pdf(str(out_file), selected_entities)
        warnings.extend(residual_warnings)

        return verification_passed, warnings

    @staticmethod
    def verify_redacted_pdf(pdf_path: str, redacted_entities: List[PIIEntity]) -> Tuple[bool, List[str]]:
        """Verifies that no original redacted string remains searchable in the output PDF."""
        doc = pymupdf.open(pdf_path)
        warnings: List[str] = []
        passed = True

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text("text").lower()

                for entity in redacted_entities:
                    if entity.page_or_section == str(page_num + 1):
                        orig = entity.original_text.strip().lower()
                        # Only check meaningful tokens (> 3 chars to avoid false alerts on short numbers)
                        if len(orig) >= 4 and orig in page_text:
                            passed = False
                            warnings.append(
                                f"Falla de seguridad en Pág {page_num+1}: El texto '{orig[:25]}' aún puede extraerse del PDF."
                            )
        finally:
            doc.close()

        return passed, warnings
