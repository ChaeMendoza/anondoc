"""
Pruebas unitarias y de integración para el sistema de revisión normativa de la DPE.
"""
import os
from pathlib import Path
import pytest
import pandas as pd
import docx

from normativa_dpe.models import ChangeRecord, ValidationStatus
from normativa_dpe.extraction.extractor import DocumentExtractor
from normativa_dpe.analysis.parser import NormativeParser
from normativa_dpe.validation.legal_rules import LegalValidator
from normativa_dpe.modification.document_updater import DocumentUpdater
from normativa_dpe.export.exporter import ResultExporter
from normativa_dpe.pipeline import NormativeReviewPipeline

@pytest.fixture
def sample_paths(tmp_path):
    from create_sample_documents import build_sample_files
    samples_dir = tmp_path / "sample_input"
    build_sample_files(str(samples_dir))
    return {
        "proyecto": str(samples_dir / "proyecto_de_ley.docx"),
        "informe": str(samples_dir / "informe_dpe_original.docx"),
        "observaciones": str(samples_dir / "observaciones_institucionales.docx"),
        "out_dir": str(tmp_path / "output")
    }

def test_document_extraction(sample_paths):
    doc = DocumentExtractor.extract(sample_paths["proyecto"])
    assert doc.filename == "proyecto_de_ley.docx"
    assert len(doc.paragraphs) > 0
    assert "Artículo 6" in doc.raw_text
    assert "Artículo 8" in doc.raw_text

def test_normative_parser():
    text = (
        "Artículo 6.- Derecho a la orientación nutricional individualizada.\n"
        "Artículo 8.- De la actualización de la guía alimentaria nacional con rol prioritario.\n"
    )
    articles = NormativeParser.extract_articles(text)
    assert "articulo_6" in articles
    assert "articulo_8" in articles

def test_legal_validator_rejects_unfounded_claims():
    bad_change = ChangeRecord(
        ubicacion="Conclusiones",
        texto_original="Texto",
        observacion="Obs",
        justificacion="Just",
        propuesta_redaccion="Esta norma podría obstaculizar el ejercicio efectivo del derecho a la salud.",
        estado_validacion=ValidationStatus.PENDIENTE_REVISION.value,
        fuente_respaldo="Ninguna"
    )
    is_valid, issues = LegalValidator.validate_change(bad_change)
    assert not is_valid
    assert any("afirmaciones abstractas no fundamentadas" in iss for iss in issues)

def test_legal_validator_approves_compliant_conclusion():
    good_change = ChangeRecord(
        ubicacion="Informe DPE - Conclusión Quinta",
        texto_original="Texto",
        observacion="Obs",
        justificacion="Just",
        propuesta_redaccion=NormativeParser.NEW_CONCLUSION_5,
        estado_validacion=ValidationStatus.PENDIENTE_REVISION.value,
        fuente_respaldo="Constitución y Proyecto de Ley"
    )
    is_valid, issues = LegalValidator.validate_change(good_change)
    assert is_valid
    assert len(issues) == 0

def test_pipeline_integration(sample_paths):
    pipeline = NormativeReviewPipeline(output_dir=sample_paths["out_dir"])
    res = pipeline.run(
        proyecto_ley_path=sample_paths["proyecto"],
        informe_dpe_path=sample_paths["informe"],
        observaciones_path=sample_paths["observaciones"]
    )
    assert res["status"] == "SUCCESS"
    assert Path(res["output_docx"]).exists()
    assert Path(res["output_pdf"]).exists()
    assert Path(res["output_excel"]).exists()
    assert Path(res["output_qc_md"]).exists()
    assert Path(res["output_qc_json"]).exists()

    # Verificar columnas del Excel
    df = pd.read_excel(res["output_excel"])
    expected_cols = [
        "Ubicación",
        "Texto Original",
        "Observación",
        "Justificación",
        "Propuesta de Redacción",
        "Estado de Validación"
    ]
    assert list(df.columns) == expected_cols
    assert len(df) == 2

    # Verificar que el docx modificado contenga el texto reemplazado
    doc_corregido = docx.Document(res["output_docx"])
    text_corregido = " ".join([p.text for p in doc_corregido.paragraphs])
    assert "podría obstaculizar el ejercicio efectivo del derecho a la salud" not in text_corregido
    assert "facultad técnica y privativa de la Autoridad Sanitaria Nacional" in text_corregido
