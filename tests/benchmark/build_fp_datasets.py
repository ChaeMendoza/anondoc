"""
False-positive reduction datasets for AnonDoc (Fase 2).

Two strictly separated sets, independent from the historical Fase 0 / Fase 1 datasets
(`dataset.jsonl`, `dataset_eval_holdout.jsonl`), which are never touched by this script:

- `dataset_fp_tuning.jsonl`: documents used to inspect failures and tune rules.
- `dataset_fp_holdout.jsonl`: documents written independently; only scored, never used to tune.

Annotation conventions (all offsets verified character by character on build):
- `entities`: ground truth PII that MUST be detected (category + exact span).
- `preserve`: non-personal institutional / administrative expressions that MUST NOT be flagged.
  A prediction overlapping a preserved span is counted as a preservation violation.
- `ambiguous`: expressions whose treatment is an open policy question (e.g. identifiers with no
  matching taxonomy category). They are reported separately and never counted as TP/FP/FN.

Each raw entry is `(category, substring)` or `(category, substring, occurrence)`; preserve / ambiguous
entries are `substring` or `(substring, occurrence)`; `occurrence` is the 0-based index of the match.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

Raw = Union[Tuple[str, str], Tuple[str, str, int]]
Span = Union[str, Tuple[str, int]]

TUNING_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "id": "fp_tune_01_hospital",
        "domain": "salud_institucional",
        "title": "Parte de atención hospitalaria",
        "text": (
            "HOSPITAL GENERAL DOCENTE DE CALDERÓN - UNIDAD MÉDICA DE EMERGENCIAS\n"
            "El Hospital General recibió al paciente Rosa Elena Cabezas Mora, cédula 1743602037, derivado desde "
            "el Centro de Salud de Chimbacalle. El Instituto Ecuatoriano de Seguridad Social cubre la atención "
            "conforme a la Seguridad Social vigente. Contacto de la familia: 0991234567."
        ),
        "raw_entities": [
            ("PERSON", "Rosa Elena Cabezas Mora"),
            ("ECUADOR_CEDULA", "1743602037"),
            ("PHONE", "0991234567"),
        ],
        "preserve": ["Hospital General", "Instituto Ecuatoriano de Seguridad Social", "Seguridad Social"],
    },
    {
        "id": "fp_tune_02_firma_electronica",
        "domain": "documental",
        "title": "Pie de documento con firma electrónica",
        "text": (
            "Documento firmado electrónicamente. Firmado digitalmente por Juan Carlos Pérez Andrade el día de la "
            "emisión. Validar la firma en el Sistema de Gestión Documental. Revisado por Mónica Alexandra Tapia "
            "Reyes, correo monica.tapia@institucion.gob.ec."
        ),
        "raw_entities": [
            ("PERSON", "Juan Carlos Pérez Andrade"),
            ("PERSON", "Mónica Alexandra Tapia Reyes"),
            ("EMAIL", "monica.tapia@institucion.gob.ec"),
        ],
        "preserve": [
            "Documento firmado electrónicamente",
            "Firmado digitalmente",
            "Gestión Documental",
        ],
    },
    {
        "id": "fp_tune_03_matricula_afiliacion",
        "domain": "profesional",
        "title": "Certificación de matrícula profesional",
        "text": (
            "Matrícula Nro. 458921 del Colegio de Abogados. Titular: Abg. Fernando Xavier Loor Mendieta, cédula "
            "1111392252. Número de afiliación: 7745123 a la Seguridad Social. Fecha de nacimiento: 22/08/1979."
        ),
        "raw_entities": [
            ("PERSON", "Fernando Xavier Loor Mendieta"),
            ("ECUADOR_CEDULA", "1111392252"),
            ("DATE_OF_BIRTH", "22/08/1979"),
        ],
        "preserve": ["Matrícula Nro", "Seguridad Social"],
        "ambiguous": ["458921", "7745123"],
    },
    {
        "id": "fp_tune_04_oficios",
        "domain": "administrativo",
        "title": "Encabezado de oficio y memorando",
        "text": (
            "Oficio Nro. MSP-DNE-2024-0456-O\n"
            "Memorando Nro. IESS-DG-2024-0789-M\n"
            "Asunto: Código Institucional del trámite 2024-117. Atentamente, Ing. Paola Beltrán Haro, "
            "Coordinadora General."
        ),
        "raw_entities": [("PERSON", "Paola Beltrán Haro")],
        "preserve": [
            "Oficio Nro",
            "MSP-DNE-2024-0456-O",
            "Memorando Nro",
            "IESS-DG-2024-0789-M",
            "Código Institucional",
            "Coordinadora General",
        ],
    },
    {
        "id": "fp_tune_05_resolucion",
        "domain": "administrativo",
        "title": "Resolución administrativa con bloque de firma",
        "text": (
            "RESOLUCIÓN ADMINISTRATIVA No. 045-2024\n"
            "La Dirección Administrativa y la Coordinación General, mediante el Departamento Jurídico, resuelven "
            "notificar al servidor Hugo Armando Salazar Ponce, quien reside en Calle Los Cedros N45-12 y Av. "
            "Mariana de Jesús, y cuyo correo es hugo.salazar@entidad.gob.ec.\n"
            "Departamento Jurídico\n"
            "Andrés Felipe Mora Villacís"
        ),
        "raw_entities": [
            ("PERSON", "Hugo Armando Salazar Ponce"),
            ("ADDRESS", "Calle Los Cedros N45-12 y Av. Mariana de Jesús"),
            ("EMAIL", "hugo.salazar@entidad.gob.ec"),
            ("PERSON", "Andrés Felipe Mora Villacís"),
        ],
        "preserve": [
            "Dirección Administrativa",
            "Coordinación General",
            ("Departamento Jurídico", 0),
            ("Departamento Jurídico", 1),
        ],
    },
    {
        "id": "fp_tune_06_nombres_institucionales",
        "domain": "salud_institucional",
        "title": "Instituciones con nombre de persona frente a persona homónima",
        "text": (
            "El Hospital Pablo Arévalo Sotomayor y la Unidad Educativa Eugenio Espejo figuran en el convenio. "
            "El paciente Pablo Arévalo Sotomayor nació el 14/03/1985 y su cédula es 1108136324. "
            "La ambulancia circuló por la Av. Simón Bolívar hacia el Hospital Básico."
        ),
        "raw_entities": [
            ("PERSON", "Pablo Arévalo Sotomayor", 1),
            ("DATE_OF_BIRTH", "14/03/1985"),
            ("ECUADOR_CEDULA", "1108136324"),
        ],
        "preserve": [
            "Hospital Pablo Arévalo Sotomayor",
            "Unidad Educativa Eugenio Espejo",
            "Simón Bolívar",
            "Hospital Básico",
        ],
    },
    {
        "id": "fp_tune_07_identificadores_con_expresion",
        "domain": "identificacion",
        "title": "Identificadores personales junto a expresiones genéricas",
        "text": (
            "Seguridad Social del Ecuador - Afiliación individual. Cédula: 1717028755. Cédula de identidad "
            "Nro. 1739383022 del cónyuge. Pasaporte Nro. PA1234567. Teléfono celular 0987654321."
        ),
        "raw_entities": [
            ("ECUADOR_CEDULA", "1717028755"),
            ("ECUADOR_CEDULA", "1739383022"),
            ("PASSPORT", "PA1234567"),
            ("PHONE", "0987654321"),
        ],
        "preserve": ["Seguridad Social"],
    },
    {
        "id": "fp_tune_08_control_negativo_institucional",
        "domain": "control_negativo",
        "title": "Texto institucional sin datos personales",
        "text": (
            "MINISTERIO DE SALUD PÚBLICA\n"
            "Coordinación Zonal 9 - Dirección Distrital 17D03\n"
            "El Centro de Salud Tipo C Chimbacalle, el Hospital Básico de Cayambe y el Hospital General Enrique "
            "Garcés son parte de la Red Pública Integral de Salud. La Gerencia Hospitalaria y el Departamento "
            "Financiero aprobaron el Plan Operativo Anual."
        ),
        "raw_entities": [],
        "preserve": [
            "Coordinación Zonal",
            "Dirección Distrital",
            "Centro de Salud Tipo C Chimbacalle",
            "Hospital Básico de Cayambe",
            "Hospital General Enrique Garcés",
            "Red Pública Integral",
            "Gerencia Hospitalaria",
            "Departamento Financiero",
            "Plan Operativo Anual",
        ],
    },
    {
        "id": "fp_tune_09_comparecencia_notarial",
        "domain": "notarial",
        "title": "Comparecencia ante notaría con nombres sin tratamiento",
        "text": (
            "Comparecen ante la Notaría Primera Gabriela Alejandra Moncayo Ruiz y Santiago Rafael Paredes "
            "Naranjo, con cédulas 1823905896 y 0948878327 respectivamente. Domicilio: Pasaje Los Pinos 123, "
            "sector La Floresta. El compareciente declara bajo juramento no adeudar al Servicio de Rentas "
            "Internas."
        ),
        "raw_entities": [
            ("PERSON", "Gabriela Alejandra Moncayo Ruiz"),
            ("PERSON", "Santiago Rafael Paredes Naranjo"),
            ("ECUADOR_CEDULA", "1823905896"),
            ("ECUADOR_CEDULA", "0948878327"),
            ("ADDRESS", "Pasaje Los Pinos 123, sector La Floresta"),
        ],
        "preserve": ["Notaría Primera", "declara bajo juramento no", "Rentas Internas"],
    },
    {
        "id": "fp_tune_10_titulos_y_cargos",
        "domain": "administrativo",
        "title": "Títulos y cargos que preceden a expresiones no personales",
        "text": (
            "El paciente refiere dolor precordial desde ayer. La señora Diana Lucía Vera Caicedo es titular de "
            "la cédula 1010577920. Se dirige al Señor Director General del Registro Civil la presente solicitud "
            "para la licencia de construcción No. LMU-2024-8971."
        ),
        "raw_entities": [
            ("PERSON", "Diana Lucía Vera Caicedo"),
            ("ECUADOR_CEDULA", "1010577920"),
        ],
        "preserve": [
            "refiere dolor precordial",
            "titular de la cédula",
            "Director General del Registro Civil",
            "LMU-2024-8971",
        ],
    },
]

HOLDOUT_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "id": "fp_hold_01_registro_civil",
        "domain": "registro_civil",
        "title": "Certificación de partida de nacimiento",
        "text": (
            "DIRECCIÓN GENERAL DE REGISTRO CIVIL, IDENTIFICACIÓN Y CEDULACIÓN\n"
            "La Dirección Provincial de Pichincha certifica que Gloria Esperanza Quishpe Tipán, con cédula "
            "1734509258, solicitó la partida de nacimiento en la Agencia Matriz del Registro Civil. Contacto: "
            "gloria.quishpe@correo.com."
        ),
        "raw_entities": [
            ("PERSON", "Gloria Esperanza Quishpe Tipán"),
            ("ECUADOR_CEDULA", "1734509258"),
            ("EMAIL", "gloria.quishpe@correo.com"),
        ],
        "preserve": ["Dirección Provincial", "Agencia Matriz", "Registro Civil"],
    },
    {
        "id": "fp_hold_02_unidad_judicial",
        "domain": "judicial",
        "title": "Providencia de unidad judicial",
        "text": (
            "UNIDAD JUDICIAL DE FAMILIA, MUJER, NIÑEZ Y ADOLESCENCIA\n"
            "El Secretario de la Unidad Judicial notifica a Marcos Vinicio Aguirre Toapanta, con cédula 1309211975, "
            "la Resolución Judicial dictada en el proceso. La Fiscalía General y el Consejo de la Judicatura "
            "recibieron copia. Teléfono: 0998765432."
        ),
        "raw_entities": [
            ("PERSON", "Marcos Vinicio Aguirre Toapanta"),
            ("ECUADOR_CEDULA", "1309211975"),
            ("PHONE", "0998765432"),
        ],
        "preserve": ["Resolución Judicial", "Fiscalía General"],
    },
    {
        "id": "fp_hold_03_clinica_privada",
        "domain": "salud",
        "title": "Resumen clínico con institución privada",
        "text": (
            "Clínica Metropolitana de Especialidades. El paciente Iván Eduardo Cárdenas Bravo, cédula 1138156086, "
            "acude a la Unidad de Cuidados Intensivos con diagnóstico: neumonía bilateral. La Seguridad Social "
            "autoriza el Código de Prestación 8841."
        ),
        "raw_entities": [
            ("PERSON", "Iván Eduardo Cárdenas Bravo"),
            ("ECUADOR_CEDULA", "1138156086"),
            ("MEDICAL_DATA", "diagnóstico: neumonía bilateral"),
        ],
        "preserve": ["Seguridad Social", "Código de Prestación", "Unidad de Cuidados Intensivos"],
    },
    {
        "id": "fp_hold_04_gobierno_local",
        "domain": "municipal",
        "title": "Notificación de Gobierno Autónomo Descentralizado",
        "text": (
            "Gobierno Autónomo Descentralizado Municipal. Junta Parroquial Rural de Conocoto.\n"
            "Se notifica a la ciudadana Verónica Alexandra Jácome Rueda, domiciliada en Avenida Los Shyris N34-56, "
            "que la Secretaría Técnica emitió el Acta de Inspección Nro. 0098-2024."
        ),
        "raw_entities": [
            ("PERSON", "Verónica Alexandra Jácome Rueda"),
            ("ADDRESS", "Avenida Los Shyris N34-56"),
        ],
        "preserve": ["Junta Parroquial Rural", "Secretaría Técnica", "Acta de Inspección Nro"],
    },
    {
        "id": "fp_hold_05_pie_de_pagina",
        "domain": "documental",
        "title": "Firmas electrónicas múltiples",
        "text": (
            "Documento firmado digitalmente por Wilson Patricio Heredia Escobar. Autorizado electrónicamente por "
            "Silvana Mercedes Ochoa Barrera. Para verificar la autenticidad ingrese al Portal Institucional. "
            "Ref. Código Documental 55-AB."
        ),
        "raw_entities": [
            ("PERSON", "Wilson Patricio Heredia Escobar"),
            ("PERSON", "Silvana Mercedes Ochoa Barrera"),
        ],
        "preserve": ["Portal Institucional", "Código Documental"],
    },
    {
        "id": "fp_hold_06_contrato_laboral",
        "domain": "laboral",
        "title": "Contrato con datos de nómina",
        "text": (
            "Contrato de trabajo entre la Gerencia General y el trabajador Cristian Rolando Yánez Lara, cédula "
            "1354820415. El Departamento de Talento Humano registra su cuenta de ahorros 2201938475 y un sueldo "
            "de $ 1.250,00. Teléfono de contacto: +593 99 876 5432."
        ),
        "raw_entities": [
            ("PERSON", "Cristian Rolando Yánez Lara"),
            ("ECUADOR_CEDULA", "1354820415"),
            ("BANK_ACCOUNT", "2201938475"),
            ("FINANCIAL_DATA", "$ 1.250,00"),
        ],
        "preserve": ["Gerencia General", "Talento Humano"],
        "ambiguous": ["+593 99 876 5432"],
    },
    {
        "id": "fp_hold_07_control_negativo",
        "domain": "control_negativo",
        "title": "Texto normativo e institucional sin datos personales",
        "text": (
            "La Subsecretaría Nacional de Planificación y la Secretaría General de la Presidencia presentaron el "
            "Informe Anual de Gestión. El Servicio Ecuatoriano de Normalización, el Instituto Nacional de "
            "Estadística y la Superintendencia de Bancos participaron en la Mesa Técnica de Coordinación "
            "Interinstitucional."
        ),
        "raw_entities": [],
        "preserve": [
            "Subsecretaría Nacional",
            "Secretaría General",
            "Informe Anual",
            "Servicio Ecuatoriano",
            "Instituto Nacional",
            "Mesa Técnica",
        ],
    },
    {
        "id": "fp_hold_08_acta_comparecencia",
        "domain": "notarial",
        "title": "Acta con personas y cargos",
        "text": (
            "ACTA DE ENTREGA RECEPCIÓN. Por el Ministerio de Educación firma Elena Cristina Burbano Mejía, con "
            "cédula 1100522786. Por la contraparte firma Ricardo Esteban Lalama Gómez, domicilio Calle Bolívar "
            "y Sucre S/N, sector Carolina. Atestigua la Directora Nacional de Servicios."
        ),
        "raw_entities": [
            ("PERSON", "Elena Cristina Burbano Mejía"),
            ("ECUADOR_CEDULA", "1100522786"),
            ("PERSON", "Ricardo Esteban Lalama Gómez"),
            ("ADDRESS", "Calle Bolívar y Sucre S/N, sector Carolina"),
        ],
        "preserve": ["Directora Nacional de Servicios", "Ministerio de Educación"],
    },
    {
        "id": "fp_hold_09_persona_con_cargo_pegado",
        "domain": "administrativo",
        "title": "Bloque de firma con cargo en línea contigua",
        "text": (
            "Atentamente,\n"
            "Mateo Sebastián Reinoso Cueva\n"
            "Coordinador Zonal\n"
            "Dirección Financiera\n"
            "Correo: mateo.reinoso@ministerio.gob.ec"
        ),
        "raw_entities": [
            ("PERSON", "Mateo Sebastián Reinoso Cueva"),
            ("EMAIL", "mateo.reinoso@ministerio.gob.ec"),
        ],
        "preserve": ["Coordinador Zonal", "Dirección Financiera"],
    },
    {
        "id": "fp_hold_10_identificadores",
        "domain": "identificacion",
        "title": "Identificadores tras expresiones administrativas",
        "text": (
            "Seguridad Social: afiliado con cédula 1316990009. Cédula: 0711021808. Número de matrícula vehicular "
            "placa PBA-1234. Instituto de Seguridad Social, dirección de correo notificaciones@iess.gob.ec "
            "no personal."
        ),
        "raw_entities": [
            ("ECUADOR_CEDULA", "1316990009"),
            ("ECUADOR_CEDULA", "0711021808"),
            ("VEHICLE_PLATE", "PBA-1234"),
        ],
        "preserve": ["Seguridad Social", "Instituto de Seguridad Social"],
        "ambiguous": ["notificaciones@iess.gob.ec"],
    },
]


def _find_span(text: str, substr: str, occurrence: int = 0) -> Tuple[int, int]:
    idx = -1
    for _ in range(occurrence + 1):
        idx = text.find(substr, idx + 1)
        if idx == -1:
            raise ValueError(f"Subcadena '{substr}' (ocurrencia {occurrence}) no encontrada.")
    return idx, idx + len(substr)


def _resolve_span_list(text: str, items: List[Span]) -> List[Dict[str, Any]]:
    out = []
    for item in items:
        substr, occ = (item, 0) if isinstance(item, str) else item
        start, end = _find_span(text, substr, occ)
        assert text[start:end] == substr
        out.append({"text": substr, "start_char": start, "end_char": end})
    return out


def resolve_entities(text: str, raw: List[Raw]) -> List[Dict[str, Any]]:
    resolved = []
    for item in raw:
        cat, substr = item[0], item[1]
        occ = item[2] if len(item) == 3 else 0
        start, end = _find_span(text, substr, occ)
        assert text[start:end] == substr
        resolved.append({"category": cat, "text": substr, "start_char": start, "end_char": end})
    return resolved


def build_documents(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    validated = []
    seen_ids = set()
    for doc in documents:
        if doc["id"] in seen_ids:
            raise ValueError(f"ID duplicado: {doc['id']}")
        seen_ids.add(doc["id"])
        text = doc["text"]
        entities = sorted(resolve_entities(text, doc["raw_entities"]), key=lambda e: e["start_char"])
        for a, b in zip(entities, entities[1:]):
            if a["end_char"] > b["start_char"]:
                raise ValueError(f"Colisión en {doc['id']}: {a} se solapa con {b}")
        preserve = _resolve_span_list(text, doc.get("preserve", []))
        ambiguous = _resolve_span_list(text, doc.get("ambiguous", []))
        for p in preserve:
            for e in entities:
                if max(p["start_char"], e["start_char"]) < min(p["end_char"], e["end_char"]):
                    raise ValueError(f"{doc['id']}: '{p['text']}' (preservar) solapa con PII '{e['text']}'")
        validated.append({
            "id": doc["id"],
            "domain": doc["domain"],
            "title": doc["title"],
            "text": text,
            "entities": entities,
            "preserve": preserve,
            "ambiguous": ambiguous,
        })
    return validated


def write_jsonl(path: Path, docs: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    for name, documents in (("dataset_fp_tuning.jsonl", TUNING_DOCUMENTS), ("dataset_fp_holdout.jsonl", HOLDOUT_DOCUMENTS)):
        built = build_documents(documents)
        write_jsonl(here / name, built)
        print(f"{name}: {len(built)} documentos, {sum(len(d['entities']) for d in built)} entidades GT")
