"""
High-Security DOCX Engine for Text Extraction, Surgical XML Run Replacement, and Metadata Scrubbing.
Supports paragraphs, tables, headers, footers, and core properties.
"""
from pathlib import Path
from typing import List, Dict, Any, Tuple
import docx
from docx.text.paragraph import Paragraph
from docx.table import Table

from anondoc.domain.entities import PIIEntity, AnonymizationStrategy
from anondoc.domain.interfaces import IDocumentExtractor, IDocumentAnonymizer
from anondoc.infrastructure.anonymization.anonymizer import AnonymizationStrategyEngine

class DOCXEngine(IDocumentExtractor, IDocumentAnonymizer):
    """Handles deep extraction and style-preserving anonymization for Word (.docx) files."""

    def extract_text_and_blocks(self, file_path: str) -> List[Dict[str, Any]]:
        doc = docx.Document(file_path)
        blocks: List[Dict[str, Any]] = []
        block_idx = 1

        # 1. Headers & Footers
        for s_idx, section in enumerate(doc.sections):
            # Header
            header_text = " ".join([p.text.strip() for p in section.header.paragraphs if p.text.strip()])
            if header_text:
                blocks.append({
                    "text": header_text,
                    "page_or_section": f"Encabezado Sección {s_idx + 1}",
                    "metadata": {"type": "header", "section": s_idx}
                })
            # Footer
            footer_text = " ".join([p.text.strip() for p in section.footer.paragraphs if p.text.strip()])
            if footer_text:
                blocks.append({
                    "text": footer_text,
                    "page_or_section": f"Pie de Página Sección {s_idx + 1}",
                    "metadata": {"type": "footer", "section": s_idx}
                })

        # 2. Main Paragraphs
        for p_idx, p in enumerate(doc.paragraphs):
            t = p.text.strip()
            if t:
                blocks.append({
                    "text": t,
                    "page_or_section": f"Párrafo {p_idx + 1}",
                    "metadata": {"type": "paragraph", "index": p_idx}
                })

        # 3. Tables & Cells
        for t_idx, table in enumerate(doc.tables):
            for r_idx, row in enumerate(table.rows):
                for c_idx, cell in enumerate(row.cells):
                    for cp_idx, cp in enumerate(cell.paragraphs):
                        ct = cp.text.strip()
                        if ct:
                            blocks.append({
                                "text": ct,
                                "page_or_section": f"Tabla {t_idx + 1} (Fila {r_idx + 1}, Col {c_idx + 1})",
                                "metadata": {
                                    "type": "table_cell",
                                    "table_index": t_idx,
                                    "row": r_idx,
                                    "col": c_idx
                                }
                            })

        return blocks

    def anonymize(
        self,
        input_path: str,
        output_path: str,
        entities: List[PIIEntity],
        strategy: AnonymizationStrategy,
        pseudonym_map: Dict[str, str],
        custom_placeholder: str = None
    ) -> Tuple[bool, List[str]]:
        """Performs surgical text replacement preserving typography, tables, and cleans metadata."""
        warnings: List[str] = []
        doc = docx.Document(input_path)
        category_counters: Dict[str, int] = {}

        selected_entities = [e for e in entities if e.selected and e.original_text.strip()]

        # Prepare replacement mapping: text -> replacement
        rep_map: Dict[str, str] = {}
        for entity in selected_entities:
            orig = entity.original_text.strip()
            if orig not in rep_map:
                rep_val = AnonymizationStrategyEngine.generate_replacement(
                    entity=entity,
                    strategy=strategy,
                    pseudonym_map=pseudonym_map,
                    category_counters=category_counters,
                    custom_placeholder=custom_placeholder
                )
                rep_map[orig] = rep_val

        # Sort replacements by length descending to prevent partial prefix replacements
        sorted_targets = sorted(rep_map.keys(), key=len, reverse=True)

        def replace_in_paragraph(p: Paragraph):
            if not p.text:
                return
            for target in sorted_targets:
                if target in p.text:
                    replacement = rep_map[target]
                    self._replace_text_in_runs(p, target, replacement)

        # 1. Process Headers & Footers
        for section in doc.sections:
            for p in section.header.paragraphs:
                replace_in_paragraph(p)
            for p in section.footer.paragraphs:
                replace_in_paragraph(p)

        # 2. Process Main Body Paragraphs
        for p in doc.paragraphs:
            replace_in_paragraph(p)

        # 3. Process Tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        replace_in_paragraph(p)

        # 4. Scrub Metadata and Core Properties
        try:
            core = doc.core_properties
            core.author = "AnonDoc Privacy Engine"
            core.last_modified_by = "AnonDoc Core v2.0"
            core.comments = "Documento procesado y anonimizado de forma segura."
            core.company = ""
            core.category = ""
            core.title = "Documento Anonimizado"
            core.subject = "Anonimización de datos personales"
        except Exception as e:
            warnings.append(f"No se pudieron limpiar todos los metadatos core: {str(e)}")

        out_file = Path(output_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out_file))

        # Verification pass
        verification_passed, residual_warnings = self.verify_redacted_docx(str(out_file), sorted_targets)
        warnings.extend(residual_warnings)

        return verification_passed, warnings

    @staticmethod
    def _replace_text_in_runs(p: Paragraph, target: str, replacement: str):
        """
        Safely replaces target text in a paragraph.
        If target is entirely inside a single run, replaces in that run to preserve other runs' styles.
        If target spans across multiple runs, replaces in whole paragraph text and preserves first run's style.
        """
        # Case 1: Target contained in a single run
        for run in p.runs:
            if target in run.text:
                run.text = run.text.replace(target, replacement)
                return

        # Case 2: Target spans across runs (run splitting)
        if target in p.text:
            # Capture style from primary run
            font_name = None
            font_size = None
            is_bold = None
            is_italic = None
            color = None

            for run in p.runs:
                if run.font.name:
                    font_name = run.font.name
                if run.font.size:
                    font_size = run.font.size
                if run.bold is not None:
                    is_bold = run.bold
                if run.italic is not None:
                    is_italic = run.italic
                if run.font.color and run.font.color.rgb:
                    color = run.font.color.rgb
                if font_name:
                    break

            new_full_text = p.text.replace(target, replacement)
            p.text = ""
            new_run = p.add_run(new_full_text)
            if font_name:
                new_run.font.name = font_name
            if font_size:
                new_run.font.size = font_size
            if is_bold is not None:
                new_run.bold = is_bold
            if is_italic is not None:
                new_run.italic = is_italic
            if color:
                new_run.font.color.rgb = color

    @staticmethod
    def verify_redacted_docx(docx_path: str, targets: List[str]) -> Tuple[bool, List[str]]:
        """Verifies that none of the original target strings remain in the output DOCX text."""
        doc = docx.Document(docx_path)
        full_text = []
        for p in doc.paragraphs:
            full_text.append(p.text)
        for t in doc.tables:
            for row in t.rows:
                for cell in row.cells:
                    full_text.append(cell.text)

        joined = " ".join(full_text).lower()
        warnings: List[str] = []
        passed = True

        for target in targets:
            clean_target = target.strip().lower()
            if len(clean_target) >= 4 and clean_target in joined:
                passed = False
                warnings.append(f"Alerta de seguridad: La cadena '{clean_target[:25]}' aún se encuentra presente en el DOCX.")

        return passed, warnings
