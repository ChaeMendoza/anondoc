"""Corrección de falsos positivos PERSON en expresiones institucionales, jurídicas y documentales (Fase 3)."""
import json
from pathlib import Path

import pytest

from anondoc.domain.entities import DetectionConfidence, EntityCategory, PIIEntity
from anondoc.infrastructure.detection.composite_detector import CompositePIIDetector
from anondoc.infrastructure.detection.pii_detector import HybridPIIDetector

detector = HybridPIIDetector()
DATASET = Path(__file__).parent / "benchmark" / "dataset_person_fp.jsonl"


def _persons(text):
    ents = detector.detect_entities([{"text": text, "page_or_section": "1"}])
    return [e.original_text for e in ents if e.category == EntityCategory.PERSON]


# Los doce falsos positivos reportados, en un contexto realista.
REPORTED_CASES = [
    ("RESOLUCIÓN DEL HOSPITAL BÁSICO DE Machachi. Se resuelve.", "DEL HOSPITAL BÁSICO DE"),
    ("De conformidad con la Constitución Art. 88 del Estado.", "Constitución Art"),
    ("Ley Orgánica de Garantías Jurisdiccionales y Control Constitucional.", "Garantías Jurisdiccionales"),
    ("Ley Orgánica de Garantías Jurisdiccionales y Control Constitucional.", "Control Constitucional"),
    ("La Policía Nacional informó el hecho.", "Policía Nacional"),
    ("Resolvió la Corte Constitucional del Ecuador.", "Corte Constitucional"),
    ("Afiliado al Instituto Ecuatoriano de Seguridad Social.", "Instituto Ecuatoriano"),
    ("Cobertura de la Seguridad Social vigente.", "Seguridad Social"),
    ("Atención en el Hospital Básico de la zona.", "Hospital Básico"),
    ("Acción de Protección Nro. 17230-2026 ingresada.", "Protección Nro"),
    ("Matrícula Nro. 123456 del profesional.", "Matrícula Nro"),
    ("Firmado Digitalmente\nEl documento continúa.", "Firmado Digitalmente"),
]


@pytest.mark.parametrize("text,fragment", REPORTED_CASES)
def test_reported_false_positives_are_not_persons(text, fragment):
    assert fragment in text
    assert not any(fragment in p or p in fragment for p in _persons(text)), _persons(text)


def test_stacked_headers_on_separate_lines_are_not_persons():
    text = (
        "Garantías Jurisdiccionales\nControl Constitucional\nPolicía Nacional\nCorte Constitucional\n"
        "Firmado Digitalmente\nHospital Básico\nSeguridad Social\nMatrícula Nro.\nProtección Nro.\n"
    )
    assert _persons(text) == []


def test_name_after_firmado_digitalmente_por_is_detected_without_header():
    assert _persons("Firmado Digitalmente por GALITO JAPÓN NÚÑEZ") == ["GALITO JAPÓN NÚÑEZ"]
    assert _persons("Firmado digitalmente por Juan Pérez Andrade") == ["Juan Pérez Andrade"]


@pytest.mark.parametrize(
    "text,name",
    [
        ("Responsable: Juan Carlos Pérez.", "Juan Carlos Pérez"),
        ("Elaborado por María Fernanda López.", "María Fernanda López"),
        ("Notificado a Carlos Luis Tamayo Delgado.", "Carlos Luis Tamayo Delgado"),
        ("En la audiencia intervino Ana Lucía Paredes Guerrero y otros.", "Ana Lucía Paredes Guerrero"),
    ],
)
def test_real_names_are_still_detected(text, name):
    assert name in _persons(text)


def test_name_after_stacked_header_keeps_all_its_words():
    # Una línea de encabezado seguida de un nombre largo no debe partir el nombre en dos entidades.
    assert _persons("Departamento Jurídico\nAndrés Felipe Mora Villacís") == ["Andrés Felipe Mora Villacís"]
    assert _persons("Ante el Hospital Básico\nPedro Pablo Salazar Cueva, compareció.") == ["Pedro Pablo Salazar Cueva"]


def test_institutions_next_to_valid_personal_data():
    text = "Víctor Hugo Zambrano Pilco, cédula 1743602037, fue atendido en el Hospital Básico por la Policía Nacional."
    ents = detector.detect_entities([{"text": text, "page_or_section": "1"}])
    assert "Víctor Hugo Zambrano Pilco" in [e.original_text for e in ents if e.category == EntityCategory.PERSON]
    assert any(e.category == EntityCategory.ECUADOR_CEDULA for e in ents)
    assert not any(e.original_text in ("Hospital Básico", "Policía Nacional") for e in ents)


def test_document_identifiers_are_not_persons():
    assert _persons("Matrícula Nro. 123456, Oficio Nro. 001-2026, Resolución Nro. 045.") == []


class _StubSemantic:
    is_ready = True

    def __init__(self, text, start, end):
        self._entity = PIIEntity(
            category=EntityCategory.PERSON, original_text=text[start:end], start_char=start, end_char=end,
            confidence=DetectionConfidence.HIGH, context=text, page_or_section="1", validation_details="GLiNER stub",
        )

    def detect_entities(self, blocks):
        return [self._entity]


def test_fusion_does_not_widen_person_into_administrative_header():
    text = "Firmado Digitalmente por Juan Pérez"
    merged = CompositePIIDetector(semantic_detector=_StubSemantic(text, 0, len(text))).detect_entities(
        [{"text": text, "page_or_section": "1"}]
    )
    persons = [e for e in merged if e.category == EntityCategory.PERSON]
    assert [(e.start_char, e.end_char) for e in persons] == [(21, 35)]


def test_fusion_still_widens_person_with_a_longer_semantic_name():
    text = "Responsable: Juan Pérez Andrade"
    start = text.index("Juan")
    merged = CompositePIIDetector(semantic_detector=_StubSemantic(text, start, len(text))).detect_entities(
        [{"text": text, "page_or_section": "1"}]
    )
    persons = [e for e in merged if e.category == EntityCategory.PERSON]
    assert [(e.start_char, e.end_char) for e in persons] == [(start, len(text))]


def _overlaps(a_start, a_end, b_start, b_end):
    return max(a_start, b_start) < min(a_end, b_end)


def test_person_fp_dataset_ground_truth_and_preservation():
    docs = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines()]
    assert len(docs) >= 8
    for doc in docs:
        ents = detector.detect_entities([{"text": doc["text"], "page_or_section": "1"}])
        persons = [e for e in ents if e.category == EntityCategory.PERSON]
        for span in doc["preserve"]:
            assert not any(_overlaps(e.start_char, e.end_char, span["start_char"], span["end_char"]) for e in persons), (
                doc["id"], span, [e.original_text for e in persons])
        for gt in doc["entities"]:
            if gt["category"] == "PERSON":
                assert any(_overlaps(e.start_char, e.end_char, gt["start_char"], gt["end_char"]) for e in persons), (
                    doc["id"], gt["text"])
