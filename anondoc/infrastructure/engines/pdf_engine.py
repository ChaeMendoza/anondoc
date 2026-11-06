"""
PDF Engine: text extraction, native redaction, sanitization and residual verification (PyMuPDF).

Runs inside the isolated worker process, never in the API process.
"""
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pymupdf

from anondoc.config import AppConfig
from anondoc.domain.entities import AnonymizationStrategy, PIIEntity
from anondoc.domain.interfaces import IDocumentAnonymizer, IDocumentExtractor
from anondoc.infrastructure.anonymization.anonymizer import AnonymizationStrategyEngine


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


class PDFEngine(IDocumentExtractor, IDocumentAnonymizer):
    """Handles extraction and native stream redaction for PDF documents."""

    def extract_text_and_blocks(self, file_path: str) -> List[Dict[str, Any]]:
        doc = pymupdf.open(file_path)
        blocks_result: List[Dict[str, Any]] = []

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text("text").strip()[: AppConfig.MAX_TEXT_BLOCK_CHARS]
                is_scanned = len(page_text) == 0 and len(page.get_images()) > 0

                if page_text:
                    blocks_result.append({
                        "text": page_text,
                        "page_or_section": str(page_num + 1),
                        "metadata": {"page_index": page_num, "is_scanned": False},
                    })
                elif is_scanned:
                    blocks_result.append({
                        "text": "[AVISO: Esta página contiene una imagen escaneada sin capa de texto seleccionable]",
                        "page_or_section": str(page_num + 1),
                        "metadata": {"page_index": page_num, "is_scanned": True},
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
        custom_placeholder: str = None,
    ) -> Tuple[bool, List[str]]:
        """
        Redacts every occurrence of each selected entity on every page, strips
        active/attached content and metadata, then verifies the saved file.
        """
        warnings: List[str] = []
        category_counters: Dict[str, int] = {}
        selected = [e for e in entities if e.selected and e.original_text.strip()]
        out_file = Path(output_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)

        doc = pymupdf.open(input_path)
        try:
            located = set()
            for page in doc:
                for entity in selected:
                    orig = entity.original_text.strip()
                    rects = page.search_for(orig)
                    if not rects:
                        continue
                    located.add(entity.id)
                    replacement = AnonymizationStrategyEngine.generate_replacement(
                        entity=entity,
                        strategy=strategy,
                        pseudonym_map=pseudonym_map,
                        category_counters=category_counters,
                        custom_placeholder=custom_placeholder,
                    )
                    for r in rects:
                        page.add_redact_annot(
                            r,
                            text=replacement,
                            fontname="helv",
                            fontsize=8,
                            align=pymupdf.TEXT_ALIGN_CENTER,
                            fill=(0.95, 0.95, 0.95),
                            text_color=(0.1, 0.1, 0.1),
                        )
                page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)

            missing = sum(1 for e in selected if e.id not in located)
            if missing:
                warnings.append(
                    f"{missing} entidad(es) seleccionada(s) no se localizaron en la capa de texto "
                    "(pueden estar en imágenes o divididas entre líneas); revise el resultado."
                )

            for page in doc:
                for annot in list(page.annots() or []):
                    page.delete_annot(annot)

            # Remove attachments, JavaScript, form data, thumbnails, XMP/metadata, links and hidden text.
            doc.scrub(
                attached_files=True,
                embedded_files=True,
                javascript=True,
                metadata=True,
                xml_metadata=True,
                thumbnails=True,
                hidden_text=True,
                remove_links=True,
                reset_fields=True,
                reset_responses=True,
                clean_pages=True,
            )
            doc.save(str(out_file), garbage=4, deflate=True, clean=True)
        finally:
            doc.close()

        passed, residual = self.verify_redacted_pdf(str(out_file), selected)
        warnings.extend(residual)
        return passed, warnings

    @staticmethod
    def verify_redacted_pdf(pdf_path: str, redacted_entities: List[PIIEntity]) -> Tuple[bool, List[str]]:
        """Fails if any selected value is still extractable or if attachments/annotations/metadata remain."""
        doc = pymupdf.open(pdf_path)
        warnings: List[str] = []
        passed = True
        targets = [(e, _norm(e.original_text)) for e in redacted_entities if e.original_text.strip()]

        try:
            for page_num, page in enumerate(doc, start=1):
                texts = [_norm(page.get_text("text"))]
                for annot in page.annots() or []:
                    texts.append(_norm(annot.info.get("content", "") or ""))
                page_text = " | ".join(texts)
                for entity, orig in targets:
                    if orig and orig in page_text:
                        passed = False
                        warnings.append(
                            f"Falla de verificación en la página {page_num}: un valor de categoría "
                            f"{entity.category.value} aún es extraíble."
                        )
            if doc.embfile_count() > 0:
                passed = False
                warnings.append("Falla de verificación: el resultado aún contiene archivos adjuntos.")
            meta = " ".join(str(v) for v in (doc.metadata or {}).values() if v)
            for entity, orig in targets:
                if orig and orig in _norm(meta):
                    passed = False
                    warnings.append("Falla de verificación: un valor seleccionado persiste en los metadatos.")
        finally:
            doc.close()

        return passed, warnings
