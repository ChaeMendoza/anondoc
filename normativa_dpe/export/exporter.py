"""
Módulo de exportación multi-formato:
- Generación de informe corregido en Word (.docx)
- Generación de versión PDF mediante LibreOffice headless
- Matriz Excel con formato institucional de control de cambios (openpyxl)
- Reporte de control de calidad y trazabilidad jurídica en Markdown y JSON
"""
import os
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from normativa_dpe.models import ChangeRecord, QualityControlReport

class ResultExporter:
    """Exporta los productos documentales, la matriz de cambios y las auditorías de calidad."""

    @classmethod
    def convert_docx_to_pdf(cls, docx_path: str, output_pdf_path: str) -> str:
        """Convierte el documento DOCX a PDF usando LibreOffice headless."""
        docx_file = Path(docx_path).resolve()
        out_dir = Path(output_pdf_path).parent.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "libreoffice",
            "--headless",
            "--convert-to",
            "pdf",
            str(docx_file),
            "--outdir",
            str(out_dir)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Error al convertir DOCX a PDF: {res.stderr}")

        expected_pdf = out_dir / f"{docx_file.stem}.pdf"
        target_pdf = Path(output_pdf_path).resolve()
        if expected_pdf.exists() and expected_pdf != target_pdf:
            expected_pdf.rename(target_pdf)
        return str(target_pdf)

    @classmethod
    def export_excel_matrix(cls, changes: List[ChangeRecord], output_path: str):
        """
        Genera la matriz Excel de control de cambios con las 6 columnas requeridas
        y estilo formal institucional de la Defensoría del Pueblo.
        """
        data = []
        for c in changes:
            data.append({
                "Ubicación": c.ubicacion,
                "Texto Original": c.texto_original,
                "Observación": c.observacion,
                "Justificación": c.justificacion,
                "Propuesta de Redacción": c.propuesta_redaccion,
                "Estado de Validación": c.estado_validacion
            })

        df = pd.DataFrame(data)
        out_file = Path(output_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Escribir con openpyxl para estilizar
        df.to_excel(out_file, index=False, engine="openpyxl", sheet_name="Matriz de Cambios")

        wb = load_workbook(out_file)
        ws = wb.active
        ws.title = "Control de Cambios Normativos"

        # Estilo institucional: Azul marino y texto blanco
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        cell_font = Font(name="Calibri", size=10)
        thin_border = Border(
            left=Side(style='thin', color='D9D9D9'),
            right=Side(style='thin', color='D9D9D9'),
            top=Side(style='thin', color='D9D9D9'),
            bottom=Side(style='thin', color='D9D9D9')
        )

        for col_idx, col in enumerate(ws.iter_cols(min_row=1, max_row=1), start=1):
            cell = col[0]
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        for row in ws.iter_rows(min_row=2, max_row=len(changes)+1):
            for cell in row:
                cell.font = cell_font
                cell.border = thin_border
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                # Resaltar estado de validación
                if "PENDIENTE" in str(cell.value):
                    cell.fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
                    cell.font = Font(name="Calibri", size=10, bold=True, color="B25900")

        # Ajuste de anchos de columna
        column_widths = {
            "A": 28,  # Ubicación
            "B": 42,  # Texto Original
            "C": 38,  # Observación
            "D": 45,  # Justificación
            "E": 55,  # Propuesta de Redacción
            "F": 30   # Estado de Validación
        }
        for col_letter, width in column_widths.items():
            ws.column_dimensions[col_letter].width = width

        wb.save(out_file)

    @classmethod
    def export_quality_report(cls, qc: QualityControlReport, output_md_path: str, output_json_path: str):
        """Exporta el reporte de control de calidad en formato Markdown y JSON."""
        # 1. Exportar JSON
        qc_dict = {
            "total_modificaciones": qc.total_modifications,
            "modificaciones_respaldadas_por_fuentes": qc.modifications_backed_by_sources,
            "afirmaciones_infundadas_eliminadas": qc.unwarranted_claims_eliminated,
            "competencia_autoridad_sanitaria_preservada": qc.sanitary_authority_competence_preserved,
            "requiere_revision_humana_previa_firma": qc.human_review_required,
            "notas_auditoria": qc.audit_notes,
            "cambios": [
                {
                    "ubicacion": c.ubicacion,
                    "texto_original": c.texto_original,
                    "observacion": c.observacion,
                    "justificacion": c.justificacion,
                    "propuesta_redaccion": c.propuesta_redaccion,
                    "estado_validacion": c.estado_validacion,
                    "fuente_respaldo": c.fuente_respaldo
                }
                for c in qc.changes
            ]
        }
        json_file = Path(output_json_path).resolve()
        json_file.parent.mkdir(parents=True, exist_ok=True)
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(qc_dict, f, ensure_ascii=False, indent=2)

        # 2. Exportar Markdown
        md_file = Path(output_md_path).resolve()
        md_content = [
            "# REPORTE DE CONTROL DE CALIDAD Y AUDITORÍA JURÍDICO-DOCUMENTAL",
            "**Institución:** Defensoría del Pueblo del Ecuador (DPE)",
            "**Asunto:** Revisión y corrección del Informe de Análisis Normativo sobre el Proyecto de Ley de Fomento a la Alimentación Saludable y al Consumo de Proteína de Alto Valor Biológico",
            "",
            "---",
            "## 1. Resumen Ejecutivo de Verificación",
            f"- **Total de modificaciones analizadas:** {qc.total_modifications}",
            f"- **Modificaciones respaldadas documentalmente por las fuentes:** {'SÍ (100% trazable)' if qc.modifications_backed_by_sources else 'NO'}",
            f"- **Eliminación de valoraciones genéricas o no sustentadas:** {'SÍ (Completado)' if qc.unwarranted_claims_eliminated else 'PENDIENTE'}",
            f"- **Preservación de la facultad técnica de la Autoridad Sanitaria Nacional (MSP):** {'SÍ (Garantizada)' if qc.sanitary_authority_competence_preserved else 'NO'}",
            f"- **Condición Human-in-the-Loop:** {'Requiere revisión humana final previa a firma oficial' if qc.human_review_required else 'No requerido'}",
            "",
            "---",
            "## 2. Notas de Auditoría y Fundamentación Constitucional",
        ]
        for note in qc.audit_notes:
            md_content.append(f"- {note}")

        md_content.extend([
            "",
            "---",
            "## 3. Detalle de Modificaciones y Trazabilidad",
        ])

        for idx, c in enumerate(qc.changes, 1):
            md_content.extend([
                f"### Modificación #{idx}: {c.ubicacion}",
                f"- **Estado de Validación:** `{c.estado_validacion}`",
                f"- **Fuente Documental de Respaldo:** {c.fuente_respaldo}",
                f"- **Texto Original:**",
                f"  > *\"{c.texto_original}\"*",
                f"- **Observación:** {c.observacion}",
                f"- **Justificación Jurídica:** {c.justificacion}",
                f"- **Propuesta de Redacción:**",
                f"  > **\"{c.propuesta_redaccion}\"**",
                ""
            ])

        with open(md_file, "w", encoding="utf-8") as f:
            f.write("\n".join(md_content))
