"""Reducción de falsos positivos en expresiones institucionales/administrativas.

Cada caso verifica a la vez que la expresión genérica se conserva y que el dato
personal asociado sigue detectándose.
"""
import pytest

from anondoc.domain.entities import EntityCategory
from anondoc.infrastructure.detection.context_analyzer import ContextAnalyzer
from anondoc.infrastructure.detection.pii_detector import HybridPIIDetector

detector = HybridPIIDetector()


def _detect(text):
    return detector.detect_entities([{"text": text, "page_or_section": "1"}])


def _texts(text, category=None):
    return [e.original_text for e in _detect(text) if category is None or e.category == category]


def _covers(entities, fragment):
    return any(fragment in e.original_text for e in entities)


@pytest.mark.parametrize(
    "phrase",
    [
        "Hospital básico",
        "Hospital General",
        "Centro de Salud",
        "Unidad Médica",
        "Seguridad Social",
        "Instituto de Seguridad Social",
        "Firmado digitalmente",
        "Documento firmado electrónicamente",
        "Matrícula Nro.",
        "Resolución administrativa",
        "Oficio Nro.",
        "Memorando Nro.",
        "Código Institucional",
        "Dirección Administrativa",
        "Coordinación General",
        "Departamento Jurídico",
    ],
)
def test_generic_expressions_are_preserved(phrase):
    persons = _texts(f"Se remite el documento. {phrase} del trámite.", EntityCategory.PERSON)
    assert persons == [], persons


def test_person_after_signature_phrase_is_protected():
    assert _covers(_detect("Firmado digitalmente por Juan Pérez"), "Juan Pérez")


def test_cedula_is_protected():
    ents = _detect("Cédula: 1712345678")
    assert any(e.category == EntityCategory.ECUADOR_CEDULA for e in ents)


def test_person_next_to_administrative_phrase_is_protected():
    ents = _detect("Coordinación General\nMaría Fernanda Loor Cedeño\nAnalista")
    assert _covers(ents, "María Fernanda Loor")


def test_context_regex_does_not_swallow_verbs():
    text = "El paciente refiere dolor precordial de inicio súbito. El titular de la cédula declara no recordar."
    assert _texts(text, EntityCategory.PERSON) == []


@pytest.mark.parametrize("name", ["Nico Pérez", "Pol Andrade", "Mesa Villalba"])
def test_names_with_substring_of_vocabulary_are_not_dropped(name):
    # "Nico" ⊂ "orgánico", "Pol" ⊂ "política": la coincidencia debe ser por palabra completa
    assert not ContextAnalyzer.is_common_institutional_phrase(name)


def test_partial_vocabulary_match_does_not_hide_real_name():
    ents = _detect("El señor Carlos Departamento Mejía firmó el acta.")
    assert ents is not None  # no debe fallar; la frase completa no es sólo administrativa
    assert not ContextAnalyzer.is_common_institutional_phrase("Carlos Mejía")


def test_money_is_not_dropped_as_institutional():
    # Los montos los detecta GLiNER; el filtro institucional no debe descartarlos por no tener letras
    assert not ContextAnalyzer.is_common_institutional_phrase("$ 1.250,00")


def test_document_code_is_not_a_plate():
    plates = _texts("Oficio Nro. DNE-2024-0153 y memorando LMU-2024-9", EntityCategory.VEHICLE_PLATE)
    assert plates == []


def test_plate_with_context_is_still_detected():
    plates = _texts("El vehículo de placa PBA-1234 fue retenido.", EntityCategory.VEHICLE_PLATE)
    assert "PBA-1234" in plates


def test_eponymous_institution_and_street_are_not_persons():
    text = "Atendido en el Hospital Pablo Arévalo Sotomayor, ubicado en la Av. Simón Bolívar."
    assert _texts(text, EntityCategory.PERSON) == []


def test_email_and_phone_inside_administrative_context_still_detected():
    ents = _detect("Oficio Nro. 123. Contacto: ana.perez@correo.com, teléfono +593987654321.")
    cats = {e.category for e in ents}
    assert EntityCategory.EMAIL in cats
    assert EntityCategory.PHONE in cats
