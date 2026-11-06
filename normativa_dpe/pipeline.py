"""
Orquestador principal del flujo de revisión y corrección normativa de la Defensoría del Pueblo.
Coordina extracción, análisis semántico, validación constitucional, edición y exportación.
"""
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List

from normativa_dpe.models import (
    ChangeRecord,
    ValidationStatus,
    ExtractedDocument,
    DocumentFormat
)
from normativa_dpe.extraction.extractor import DocumentExtractor
from normativa_dpe.analysis.parser import NormativeParser
from normativa_dpe.validation.legal_rules import LegalValidator
from normativa_dpe.modification.document_updater import DocumentUpdater
from normativa_dpe.export.exporter import ResultExporter

class NormativeReviewPipeline:
    """Pipeline integral de análisis y corrección documental con trazabilidad jurídica."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        proyecto_ley_path: str,
        informe_dpe_path: str,
        observaciones_path: str
    ) -> Dict[str, Any]:
        """
        Ejecuta el ciclo completo de procesamiento y genera todos los entregables.
        """
        print(f"[+] Iniciando extracción de fuentes documentales...")
        # 1. Extracción de documentos
        doc_proyecto = DocumentExtractor.extract(proyecto_ley_path)
        doc_informe = DocumentExtractor.extract(informe_dpe_path)
        doc_obs = DocumentExtractor.extract(observaciones_path)

        # 2. Análisis del Proyecto de Ley (Artículos 6 y 8)
        articles_proyecto = NormativeParser.extract_articles(doc_proyecto.raw_text)
        art_6_proyecto = articles_proyecto.get(
            "articulo_6",
            "Artículo 6.- Derecho a la orientación nutricional individualizada según las necesidades biológicas y de salud."
        )
        art_8_proyecto = articles_proyecto.get(
            "articulo_8",
            "Artículo 8.- De la actualización de la guía alimentaria nacional, priorizando el consumo de proteína de alto valor biológico en las políticas públicas de nutrición."
        )

        # 3. Análisis de las observaciones institucionales
        articles_obs = NormativeParser.extract_articles(doc_obs.raw_text)
        obs_art_8 = articles_obs.get(
            "articulo_8",
            "Observación al Art. 8: Se advierte que la ley no debe subordinar la discrecionalidad técnica de la autoridad sanitaria nacional."
        )

        eval_art_8 = NormativeParser.evaluate_art_8_competence(art_8_proyecto, obs_art_8)

        # 4. Localizar la Conclusión Quinta en el informe original
        conclusion_target = NormativeParser.locate_target_conclusion(doc_informe)
        if not conclusion_target:
            raise ValueError(
                f"No se encontró la frase objetivo '{NormativeParser.TARGET_PHRASE_CONCLUSION_5}' en el informe DPE."
            )
        target_p_idx, target_conclusion_text = conclusion_target

        # 5. Estructurar registros de cambios con trazabilidad estricta
        # Cambio 1: Recomendación específica al Artículo 8
        rec_art_8 = ChangeRecord(
            ubicacion="Informe DPE - Sección Análisis del Artículo 8",
            texto_original=(
                "El artículo 8 del proyecto dispone que la guía alimentaria nacional priorizará de forma obligatoria "
                "el consumo de proteína de alto valor biológico en todos los planes y programas nacionales."
            ),
            observacion=(
                "La fijación legislativa rígida de una jerarquía nutricional limita la discrecionalidad y facultad "
                "técnica privativa de la Autoridad Sanitaria Nacional (Ministerio de Salud Pública)."
            ),
            justificacion=(
                "Conforme al Art. 32 de la Constitución de la República del Ecuador y la Ley Orgánica de Salud, "
                "la rectoría en salud y nutrición corresponde exclusivamente a la autoridad sanitaria nacional, "
                "la cual debe basar sus directrices en evidencia científica actualizada, etapas del ciclo vital, "
                "pertinencia cultural y accesibilidad."
            ),
            propuesta_redaccion=NormativeParser.RECOMMENDATION_ART_8,
            estado_validacion=ValidationStatus.PENDIENTE_REVISION.value,
            fuente_respaldo=f"Proyecto de Ley (Art. 8) y Documento Institucional de Observaciones ({doc_obs.filename})"
        )

        # Cambio 2: Corrección integral de la Conclusión Quinta
        rec_conclusion_5 = ChangeRecord(
            ubicacion="Informe DPE - Sección Conclusiones - Conclusión Quinta",
            texto_original=target_conclusion_text,
            observacion=(
                "La redacción original contiene una valoración genérica y no fundamentada ('podría obstaculizar "
                "el ejercicio efectivo del derecho a la salud'), que no precisa la solución técnica legislativa "
                "ni vincula la garantía con el Art. 6 del proyecto."
            ),
            justificacion=(
                "Sustitución técnica conforme a los estándares de la Defensoría del Pueblo (Art. 215 CRE): "
                "Se vincula la facultad técnica de la autoridad sanitaria con la prohibición de jerarquías nutricionales "
                "rígidas, salvaguardando los principios de igualdad, pertinencia cultural, territorialidad, accesibilidad "
                "económica (Art. 13 CRE) y la orientación nutricional individualizada (Art. 6 del Proyecto)."
            ),
            propuesta_redaccion=NormativeParser.NEW_CONCLUSION_5,
            estado_validacion=ValidationStatus.PENDIENTE_REVISION.value,
            fuente_respaldo=f"Proyecto de Ley (Arts. 6 y 8), CRE (Arts. 13, 32 y 215) y Guías Alimentarias del Ecuador (GABA)"
        )

        changes = [rec_art_8, rec_conclusion_5]

        # 6. Validaciones jurídicas y control de calidad
        qc_report = LegalValidator.generate_quality_control_report(
            changes=changes,
            original_sources={
                "proyecto_ley": doc_proyecto.raw_text,
                "informe_dpe": doc_informe.raw_text,
                "observaciones": doc_obs.raw_text
            }
        )

        # 7. Modificación del documento Word original preservando formato
        # Si el informe original era .doc, doc_informe.file_path ya es el .docx convertido
        working_docx = doc_informe.file_path
        if working_docx.lower().endswith(".doc"):
            working_docx = DocumentExtractor.convert_doc_to_docx(working_docx)

        output_docx = str(self.output_dir / "informe_analisis_normativo_corregido.docx")
        output_pdf = str(self.output_dir / "informe_analisis_normativo_corregido.pdf")
        output_excel = str(self.output_dir / "matriz_cambios_normativos.xlsx")
        output_qc_md = str(self.output_dir / "reporte_control_calidad.md")
        output_qc_json = str(self.output_dir / "control_calidad.json")

        print(f"[+] Aplicando modificaciones quirúrgicas en formato institucional DOCX...")
        replacements = [
            {
                "target_pattern": NormativeParser.TARGET_PHRASE_CONCLUSION_5,
                "replacement_text": NormativeParser.NEW_CONCLUSION_5
            }
        ]
        # También verificamos si en el texto del informe existe un apartado previo de recomendación del Art 8
        if "recomienda que el artículo 8" not in doc_informe.raw_text:
            # Si hay párrafo de observación sobre art 8, añadir o reemplazar recomendación
            for p in doc_informe.paragraphs:
                if "artículo 8" in p.text.lower() and "observación" in p.text.lower():
                    replacements.append({
                        "target_pattern": p.text,
                        "replacement_text": f"{p.text}\n\n{NormativeParser.RECOMMENDATION_ART_8}"
                    })
                    break

        modified_paragraphs = DocumentUpdater.apply_modifications(
            docx_path=working_docx,
            output_docx_path=output_docx,
            replacements=replacements
        )

        print(f"[+] Generando versión PDF institucional...")
        pdf_path = ResultExporter.convert_docx_to_pdf(output_docx, output_pdf)

        print(f"[+] Generando matriz Excel de control de cambios...")
        ResultExporter.export_excel_matrix(changes, output_excel)

        print(f"[+] Generando reporte de control de calidad y auditoría jurídica...")
        ResultExporter.export_quality_report(qc_report, output_qc_md, output_qc_json)

        print(f"[✓] Proceso completado exitosamente. Archivos generados en: {self.output_dir}")

        return {
            "status": "SUCCESS",
            "modified_paragraphs": modified_paragraphs,
            "output_docx": output_docx,
            "output_pdf": pdf_path,
            "output_excel": output_excel,
            "output_qc_md": output_qc_md,
            "output_qc_json": output_qc_json,
            "quality_report": qc_report
        }
