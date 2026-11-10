"""
Comprehensive Test Suite for AnonDoc v2.0.
Verifies Domain Validators, PII Detection, Native Redaction, Security, and REST API.
"""
import io
from pathlib import Path
import pytest
import pymupdf
import docx
from fastapi.testclient import TestClient

from anondoc.domain.entities import (
    EntityCategory,
    AnonymizationStrategy,
    PIIEntity
)
from anondoc.domain.validators import PIIValidators
from anondoc.infrastructure.detection.pii_detector import HybridPIIDetector
from anondoc.infrastructure.anonymization.anonymizer import AnonymizationStrategyEngine
from anondoc.infrastructure.storage.temp_storage import SecureStorageService
from anondoc.infrastructure.engines.pdf_engine import PDFEngine
from anondoc.infrastructure.engines.docx_engine import DOCXEngine
from anondoc.infrastructure.security.inspector import DocumentRejected, detect_format
from anondoc.main import app

client = TestClient(app)

# -------------------------------------------------------------
# 1. PRUEBAS DE VALIDACIÓN ALGORÍTMICA (DOMAIN)
# -------------------------------------------------------------

def test_ecuador_cedula_valid():
    # Cédula válida conocida de Pichincha (17): 1710034065
    is_valid, msg = PIIValidators.validate_ecuador_cedula("1710034065")
    assert is_valid is True

def test_ecuador_cedula_invalid_checksum():
    # Cambiamos el dígito verificador final
    is_valid, msg = PIIValidators.validate_ecuador_cedula("1710034069")
    assert is_valid is False
    assert "Dígito verificador incorrecto" in msg

def test_ecuador_cedula_invalid_province():
    is_valid, msg = PIIValidators.validate_ecuador_cedula("9910034065")
    assert is_valid is False
    assert "provincia no válido" in msg

def test_ecuador_ruc_natural():
    # RUC persona natural: cédula válida + 001
    is_valid, msg = PIIValidators.validate_ecuador_ruc("1710034065001")
    assert is_valid is True
    assert "Persona Natural" in msg

def test_luhn_credit_card():
    # Tarjeta de prueba válida según Luhn (453201511283034)
    valid_card = "453201511283034"
    is_valid, _ = PIIValidators.validate_luhn(valid_card)
    assert is_valid is True

    # Tarjeta inválida
    is_valid_bad, _ = PIIValidators.validate_luhn("453201511283039")
    assert is_valid_bad is False

def test_ipv4_validation():
    assert PIIValidators.validate_ipv4("192.168.1.100")[0] is True
    assert PIIValidators.validate_ipv4("999.168.1.1")[0] is False

# -------------------------------------------------------------
# 2. PRUEBAS DE DETECCIÓN HÍBRIDA PII
# -------------------------------------------------------------

def test_hybrid_pii_detection():
    detector = HybridPIIDetector()
    sample_text = (
        "El Dr. Carlos Mendoza con cédula 1710034065 y correo carlos.mendoza@empresa.com "
        "se comunicó desde el teléfono +593987654321 reportando IP 10.0.0.1. "
        "El vehículo con placa PBN-4567 comparece ante la Asamblea Nacional."
    )
    blocks = [{"text": sample_text, "page_or_section": "1"}]
    entities = detector.detect_entities(blocks)

    categories_found = {e.category for e in entities}
    assert EntityCategory.EMAIL in categories_found
    assert EntityCategory.ECUADOR_CEDULA in categories_found
    assert EntityCategory.PHONE in categories_found
    assert EntityCategory.IP_ADDRESS in categories_found
    assert EntityCategory.VEHICLE_PLATE in categories_found
    assert EntityCategory.PERSON in categories_found

    # Verificar que 'Asamblea Nacional' NO fue clasificada como persona (filtro de contexto)
    person_texts = [e.original_text for e in entities if e.category == EntityCategory.PERSON]
    assert not any("Asamblea Nacional" in p for p in person_texts)
    assert any("Carlos Mendoza" in p for p in person_texts)

# -------------------------------------------------------------
# 3. PRUEBAS DE ESTRATEGIAS DE ANONIMIZACIÓN
# -------------------------------------------------------------

def test_anonymization_strategies():
    ent = PIIEntity(
        category=EntityCategory.EMAIL,
        original_text="usuario.confidencial@seguridad.ec"
    )
    pmap = {}
    counters = {}

    # Redaction
    red = AnonymizationStrategyEngine.generate_replacement(
        ent, AnonymizationStrategy.REDACTION, pmap, counters
    )
    assert red == "[EMAIL_ANONIMIZADO]"

    # Pseudonymization
    pseudo1 = AnonymizationStrategyEngine.generate_replacement(
        ent, AnonymizationStrategy.PSEUDONYMIZATION, pmap, counters
    )
    assert pseudo1 == "EMAIL_001"
    # Consistencia en segunda llamada con mismo texto
    pseudo2 = AnonymizationStrategyEngine.generate_replacement(
        ent, AnonymizationStrategy.PSEUDONYMIZATION, pmap, counters
    )
    assert pseudo2 == "EMAIL_001"

    # Masking
    mask = AnonymizationStrategyEngine.generate_replacement(
        ent, AnonymizationStrategy.MASKING, pmap, counters
    )
    assert "@seguridad.ec" in mask
    assert mask.startswith("u*")

# -------------------------------------------------------------
# 4. PRUEBAS DE SEGURIDAD EN ALMACENAMIENTO Y UPLOAD
# -------------------------------------------------------------

def test_storage_security_path_traversal(tmp_path):
    storage = SecureStorageService(base_dir=tmp_path)
    with pytest.raises(ValueError):
        storage.get_job_dir("../../etc/cron.d")

def test_format_detection_ignores_extension():
    with pytest.raises(DocumentRejected):
        detect_format(b"#!/bin/bash\necho 'hacked'")

# -------------------------------------------------------------
# 5. PRUEBAS DE MOTOR DOCUMENTAL PDF (REDACCIÓN FÍSICA Y VERIFICACIÓN)
# -------------------------------------------------------------

def test_pdf_native_redaction_and_verification(tmp_path):
    pdf_path = tmp_path / "test_doc.pdf"
    out_pdf_path = tmp_path / "test_doc_anonymized.pdf"

    # 1. Crear PDF sintético
    doc = pymupdf.open()
    page = doc.new_page()
    secret_text = "Dra. Elena Ramos titular con cédula 1710034065 y correo elena@privado.org"
    page.insert_text((50, 100), secret_text)
    doc.save(str(pdf_path))
    doc.close()

    # 2. Extraer y detectar
    engine = PDFEngine()
    blocks = engine.extract_text_and_blocks(str(pdf_path))
    detector = HybridPIIDetector()
    entities = detector.detect_entities(blocks)
    assert len(entities) >= 2

    # 3. Aplicar anonimización física
    success, warnings = engine.anonymize(
        input_path=str(pdf_path),
        output_path=str(out_pdf_path),
        entities=entities,
        strategy=AnonymizationStrategy.REDACTION,
        pseudonym_map={}
    )
    assert success is True
    assert Path(out_pdf_path).exists()

    # 4. Verificar físicamente que el texto NO es extraíble ni recuperable
    verify_doc = pymupdf.open(str(out_pdf_path))
    extracted = verify_doc[0].get_text("text")
    verify_doc.close()

    assert "1710034065" not in extracted
    assert "elena@privado.org" not in extracted
    assert "[CEDULA_ANONIMIZADO]" in extracted or "[EMAIL_ANONIMIZADO]" in extracted

# -------------------------------------------------------------
# 6. PRUEBAS DE MOTOR DOCUMENTAL DOCX (PARÁGRAFOS, TABLAS Y METADATOS)
# -------------------------------------------------------------

def test_docx_anonymization_and_metadata_scrubbing(tmp_path):
    docx_path = tmp_path / "test_doc.docx"
    out_docx_path = tmp_path / "test_doc_anonymized.docx"

    # 1. Crear DOCX sintético con párrafos, tabla y metadatos
    doc = docx.Document()
    doc.core_properties.author = "Investigador Secreto"
    doc.add_paragraph("Informe emitido por el Abg. Roberto Salazar para el cliente privado.")
    
    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Identificación:"
    table.rows[0].cells[1].text = "1710034065"
    table.rows[1].cells[0].text = "Contacto:"
    table.rows[1].cells[1].text = "roberto.salazar@estudio.ec"
    doc.save(str(docx_path))

    # 2. Extraer y detectar
    engine = DOCXEngine()
    blocks = engine.extract_text_and_blocks(str(docx_path))
    detector = HybridPIIDetector()
    entities = detector.detect_entities(blocks)
    assert len(entities) >= 2

    # 3. Anonimizar
    success, warnings = engine.anonymize(
        input_path=str(docx_path),
        output_path=str(out_docx_path),
        entities=entities,
        strategy=AnonymizationStrategy.PSEUDONYMIZATION,
        pseudonym_map={}
    )
    assert success is True

    # 4. Verificar eliminación y limpieza de metadatos
    doc_res = docx.Document(str(out_docx_path))
    all_text = " ".join([p.text for p in doc_res.paragraphs] + [c.text for row in doc_res.tables[0].rows for c in row.cells])
    
    assert "1710034065" not in all_text
    assert "roberto.salazar@estudio.ec" not in all_text
    assert doc_res.core_properties.author == "AnonDoc Privacy Engine"

# -------------------------------------------------------------
# 7. PRUEBAS DE INTEGRACIÓN END-TO-END VÍA REST API
# -------------------------------------------------------------

def test_rest_api_e2e_flow(tmp_path):
    # 1. Crear archivo DOCX de prueba en memoria
    doc = docx.Document()
    doc.add_paragraph("El usuario Juan Pérez con cédula 1710034065 y correo juan@test.com solicita revisión.")
    bio = io.BytesIO()
    doc.save(bio)
    file_bytes = bio.getvalue()

    # 2. Upload: POST /api/v1/documents
    upload_res = client.post(
        "/api/v1/documents",
        files={"file": ("contrato_confidencial.docx", file_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )
    assert upload_res.status_code == 201
    upload_data = upload_res.json()
    job_id = upload_data["job_id"]
    assert job_id is not None
    client.headers["Authorization"] = f"Bearer {upload_data['access_token']}"

    # 3. Analyze: POST /api/v1/documents/{job_id}/analyze
    analyze_res = client.post(f"/api/v1/documents/{job_id}/analyze")
    assert analyze_res.status_code == 200
    analyze_data = analyze_res.json()
    assert analyze_data["total_entities"] >= 2
    entities = analyze_data["entities"]

    # 4. Patch detections (selección y agregar manual): PATCH /api/v1/documents/{job_id}/detections
    patch_payload = {
        "entities": [
            {
                "id": entities[0]["id"],
                "category": entities[0]["category"],
                "original_text": entities[0]["original_text"],
                "selected": True,
                "page_or_section": entities[0]["page_or_section"]
            },
            {
                "category": "MEDICAL_DATA",
                "original_text": "revisión",
                "selected": True,
                "page_or_section": "1",
                "is_manual": True
            }
        ]
    }
    patch_res = client.patch(f"/api/v1/documents/{job_id}/detections", json=patch_payload)
    assert patch_res.status_code == 200

    # 5. Anonymize: POST /api/v1/documents/{job_id}/anonymize
    anon_payload = {
        "strategy": "REDACTION",
        "custom_placeholder": "[CONFIDENCIAL]"
    }
    anon_res = client.post(f"/api/v1/documents/{job_id}/anonymize", json=anon_payload)
    assert anon_res.status_code == 200
    anon_data = anon_res.json()
    assert anon_data["status"] == "COMPLETED"

    # 6. Download: GET /api/v1/documents/{job_id}/download
    download_res = client.get(f"/api/v1/documents/{job_id}/download")
    assert download_res.status_code == 200
    assert len(download_res.content) > 0

    # 7. Delete: DELETE /api/v1/documents/{job_id}
    del_res = client.delete(f"/api/v1/documents/{job_id}")
    assert del_res.status_code == 204

    # 8. Health: GET /api/v1/health
    health_res = client.get("/api/v1/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"
    client.headers.pop("Authorization")


def test_use_cases_dependency_injection():
    """Verifies that DocumentUseCases allows clean injection with explicit None handling."""
    from anondoc.domain.interfaces import IPIIDetector, IStorageService
    from anondoc.application.use_cases import DocumentUseCases
    from anondoc.infrastructure.detection.pii_detector import HybridPIIDetector
    from anondoc.infrastructure.storage.temp_storage import SecureStorageService

    # 1. Default arguments
    uc_default = DocumentUseCases()
    assert isinstance(uc_default.detector, HybridPIIDetector)
    assert isinstance(uc_default.storage, SecureStorageService)

    # 2. Explicit None arguments fall back to defaults
    uc_none = DocumentUseCases(storage=None, detector=None)
    assert isinstance(uc_none.detector, HybridPIIDetector)
    assert isinstance(uc_none.storage, SecureStorageService)

    # 3. Custom implementations are strictly preserved
    class DummyDetector(IPIIDetector):
        def detect_entities(self, text_blocks):
            return []

    class DummyStorage(IStorageService):
        def get_job_dir(self, job_id: str):
            return Path("/tmp")
        def save_upload(self, job_id: str, extension: str, content: bytes) -> str:
            return "/tmp/fake.pdf"
        def output_path(self, job_id: str, extension: str) -> str:
            return "/tmp/fake_anon.pdf"
        def remove_file(self, path: str) -> None:
            pass
        def cleanup_job(self, job_id: str) -> bool:
            return True
        def purge_expired_jobs(self, max_age_seconds: int = None) -> int:
            return 0

    custom_detector = DummyDetector()
    custom_storage = DummyStorage()
    uc_custom = DocumentUseCases(storage=custom_storage, detector=custom_detector)

    assert uc_custom.detector is custom_detector
    assert uc_custom.storage is custom_storage


def test_gliner_and_composite_detectors():
    """Verifies that GLiNERDetector and CompositePIIDetector execute correctly in the pipeline."""
    from anondoc.infrastructure.detection.gliner_detector import GLiNERDetector
    from anondoc.infrastructure.detection.composite_detector import CompositePIIDetector

    gliner = GLiNERDetector(threshold=0.5)
    if not gliner.is_ready:
        pytest.skip("GLiNER model not available in current environment")

    blocks = [{"text": "El ciudadano Mateo Morales de la Torre comparece en la ciudad de Quito.", "page_or_section": "1"}]
    entities = gliner.detect_entities(blocks)
    assert any(e.category == EntityCategory.PERSON for e in entities)

    composite = CompositePIIDetector(semantic_detector=gliner)
    merged = composite.detect_entities(blocks)
    assert any(e.category == EntityCategory.PERSON for e in merged)
