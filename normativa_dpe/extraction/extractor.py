"""
Módulo de extracción documental: soporte robusto para DOC, DOCX y PDF.
Conserva estructura, jerarquía de títulos, artículos, párrafos y tablas.
"""
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional
import docx
import pymupdf

from normativa_dpe.models import ExtractedDocument, DocumentParagraph, DocumentFormat

class DocumentExtractor:
    """Extrae contenido documental preservando jerarquía y trazabilidad."""

    @classmethod
    def convert_doc_to_docx(cls, doc_path: str) -> str:
        """Convierte archivos .doc binarios heredados a .docx mediante LibreOffice headless."""
        doc_file = Path(doc_path).resolve()
        if not doc_file.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {doc_path}")

        temp_dir = tempfile.mkdtemp(prefix="doc_conv_")
        cmd = [
            "libreoffice",
            "--headless",
            "--convert-to",
            "docx",
            str(doc_file),
            "--outdir",
            temp_dir
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Error al convertir DOC a DOCX: {res.stderr}")

        converted_docx = Path(temp_dir) / f"{doc_file.stem}.docx"
        if not converted_docx.exists():
            raise FileNotFoundError(f"No se generó el archivo convertido: {converted_docx}")
        return str(converted_docx)

    @classmethod
    def extract(cls, file_path: str) -> ExtractedDocument:
        """Punto de entrada general para extraer DOC, DOCX o PDF."""
        path = Path(file_path).resolve()
        suffix = path.suffix.lower()

        if suffix == ".doc":
            converted_path = cls.convert_doc_to_docx(str(path))
            doc = cls._extract_docx(converted_path)
            doc.format = DocumentFormat.DOC
            doc.file_path = str(path)
            return doc
        elif suffix == ".docx":
            return cls._extract_docx(str(path))
        elif suffix == ".pdf":
            return cls._extract_pdf(str(path))
        else:
            raise ValueError(f"Formato no soportado: {suffix}. Formatos válidos: .doc, .docx, .pdf")

    @classmethod
    def _extract_docx(cls, docx_path: str) -> ExtractedDocument:
        doc = docx.Document(docx_path)
        paragraphs_list: List[DocumentParagraph] = []
        raw_lines: List[str] = []

        idx = 0
        # 1. Párrafos normales
        for p in doc.paragraphs:
            text = p.text.strip()
            style_name = p.style.name if p.style else "Normal"
            is_heading = "heading" in style_name.lower() or "título" in style_name.lower()
            h_level = None
            if is_heading:
                # Extraer nivel si existe
                for part in style_name.split():
                    if part.isdigit():
                        h_level = int(part)
                        break

            dp = DocumentParagraph(
                index=idx,
                text=text,
                style_name=style_name,
                is_heading=is_heading,
                heading_level=h_level
            )
            paragraphs_list.append(dp)
            if text:
                raw_lines.append(text)
            idx += 1

        # 2. Tablas
        for t_idx, table in enumerate(doc.tables):
            for r_idx, row in enumerate(table.rows):
                for c_idx, cell in enumerate(row.cells):
                    for cp in cell.paragraphs:
                        text = cp.text.strip()
                        if text:
                            dp = DocumentParagraph(
                                index=idx,
                                text=text,
                                style_name=cp.style.name if cp.style else "Table Cell",
                                is_heading=False,
                                table_index=t_idx,
                                row_index=r_idx,
                                col_index=c_idx
                            )
                            paragraphs_list.append(dp)
                            raw_lines.append(f"[Tabla {t_idx+1} Fila {r_idx+1}] {text}")
                            idx += 1

        return ExtractedDocument(
            filename=Path(docx_path).name,
            file_path=docx_path,
            format=DocumentFormat.DOCX,
            paragraphs=paragraphs_list,
            raw_text="\n".join(raw_lines),
            metadata={"num_paragraphs": len(paragraphs_list), "num_tables": len(doc.tables)}
        )

    @classmethod
    def _extract_pdf(cls, pdf_path: str) -> ExtractedDocument:
        pdf = pymupdf.open(pdf_path)
        paragraphs_list: List[DocumentParagraph] = []
        raw_lines: List[str] = []
        idx = 0

        for page_idx, page in enumerate(pdf):
            blocks = page.get_text("blocks")
            # blocks format: (x0, y0, x1, y1, "text", block_no, block_type)
            for block in blocks:
                text = block[4].strip()
                if not text:
                    continue
                # Detección heurística de encabezado por longitud y mayúsculas
                is_heading = (len(text.splitlines()) == 1 and len(text) < 120 and (text.isupper() or text.startswith("Artículo") or text.startswith("ARTÍCULO") or text.startswith("CONCLUSI")))
                dp = DocumentParagraph(
                    index=idx,
                    text=text,
                    style_name="PDF_Block",
                    is_heading=is_heading,
                    heading_level=1 if is_heading else None,
                    table_index=None
                )
                paragraphs_list.append(dp)
                raw_lines.append(text)
                idx += 1

        return ExtractedDocument(
            filename=Path(pdf_path).name,
            file_path=pdf_path,
            format=DocumentFormat.PDF,
            paragraphs=paragraphs_list,
            raw_text="\n".join(raw_lines),
            metadata={"pages": len(pdf), "total_blocks": len(paragraphs_list)}
        )
