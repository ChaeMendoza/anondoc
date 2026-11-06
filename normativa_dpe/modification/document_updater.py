"""
Módulo de modificación documental quirúrgica sobre DOCX.
Conserva formato institucional, tipografías, encabezados, tablas y estilos.
"""
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import docx
from docx.shared import Pt, RGBColor
from docx.text.paragraph import Paragraph

class DocumentUpdater:
    """Aplica modificaciones sobre documentos Word (.docx) preservando fielmente su formato."""

    @classmethod
    def replace_paragraph_text_preserving_style(cls, p: Paragraph, new_text: str):
        """
        Reemplaza el texto de un párrafo conservando el estilo, interlineado,
        alineación y propiedades tipográficas del run principal original.
        """
        font_name = None
        font_size = None
        is_bold = None
        is_italic = None
        font_color = None

        # Capturar formato del primer run que tenga propiedades definidas
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
                font_color = run.font.color.rgb
            if font_name or font_size:
                break

        # Limpiar runs existentes
        p.text = ""

        # Crear nuevo run con el contenido actualizado y las propiedades heredadas
        new_run = p.add_run(new_text)
        if font_name:
            new_run.font.name = font_name
        if font_size:
            new_run.font.size = font_size
        if is_bold is not None:
            new_run.bold = is_bold
        if is_italic is not None:
            new_run.italic = is_italic
        if font_color:
            new_run.font.color.rgb = font_color

    @classmethod
    def apply_modifications(
        cls,
        docx_path: str,
        output_docx_path: str,
        replacements: List[Dict[str, str]]
    ) -> int:
        """
        Aplica una lista de reemplazos [ {"target_pattern": str, "replacement_text": str} ]
        tanto en párrafos regulares como en celdas de tablas.
        Retorna la cantidad de párrafos modificados.
        """
        doc = docx.Document(docx_path)
        modified_count = 0

        # Función auxiliar para evaluar párrafos
        def check_and_replace(p: Paragraph) -> bool:
            nonlocal modified_count
            for rep in replacements:
                target = rep["target_pattern"]
                replacement = rep["replacement_text"]
                if target.lower() in p.text.lower():
                    cls.replace_paragraph_text_preserving_style(p, replacement)
                    modified_count += 1
                    return True
            return False

        # 1. Párrafos normales
        for p in doc.paragraphs:
            check_and_replace(p)

        # 2. Párrafos dentro de tablas
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for cp in cell.paragraphs:
                        check_and_replace(cp)

        # Guardar archivo modificado
        Path(output_docx_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_docx_path)
        return modified_count
