"""
PERSON false-positive dataset (Fase 3): the twelve real false positives reported from production use,
each in realistic context together with real names, document identifiers and personal data.

Written to `dataset_person_fp.jsonl`; the Fase 0 / 1 / 2 datasets are never touched.
Note: these documents were written from the reported cases, so they measure the fix for those cases
and are NOT an independent holdout (the Fase 2 `dataset_fp_holdout.jsonl` remains the holdout).
Annotation conventions are the same as in `build_fp_datasets.py`.
"""
from pathlib import Path
from typing import Any, Dict, List

from build_fp_datasets import build_documents, write_jsonl

PERSON_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "id": "pfp_01_sentencia_constitucional",
        "domain": "juridico",
        "title": "Extracto de sentencia constitucional",
        "text": (
            "SENTENCIA DE ACCIÓN DE PROTECCIÓN. De conformidad con la Constitución Art. 88 y la Ley Orgánica de "
            "Garantías Jurisdiccionales y Control Constitucional, la Corte Constitucional conoce el caso. "
            "La Policía Nacional informó que el accionante Segundo Armando Vera Intriago, cédula 1111392252, "
            "fue notificado. Acción de Protección Nro. 17230-2026."
        ),
        "raw_entities": [
            ("PERSON", "Segundo Armando Vera Intriago"),
            ("ECUADOR_CEDULA", "1111392252"),
        ],
        "preserve": [
            "Constitución Art",
            "Garantías Jurisdiccionales",
            "Control Constitucional",
            "Corte Constitucional",
            "Policía Nacional",
            "Protección Nro",
        ],
    },
    {
        "id": "pfp_02_firma_digital_mayusculas",
        "domain": "documental",
        "title": "Pie con firma electrónica en mayúsculas",
        "text": (
            "Firmado Digitalmente por GALITO JAPÓN NÚÑEZ\n"
            "Documento emitido por el Hospital Básico de Machachi."
        ),
        "raw_entities": [("PERSON", "GALITO JAPÓN NÚÑEZ")],
        "preserve": ["Firmado Digitalmente", "Hospital Básico"],
    },
    {
        "id": "pfp_03_encabezados_apilados",
        "domain": "documental",
        "title": "Encabezados administrativos en líneas separadas",
        "text": (
            "DEL HOSPITAL BÁSICO DE MACHACHI\n"
            "Firmado Digitalmente\n"
            "Instituto Ecuatoriano de Seguridad Social\n"
            "Garantías Jurisdiccionales\n"
            "Control Constitucional\n"
            "Policía Nacional\n"
            "Corte Constitucional\n"
            "Seguridad Social\n"
            "Matrícula Nro.\n"
            "Protección Nro.\n"
        ),
        "raw_entities": [],
        "preserve": [
            "DEL HOSPITAL BÁSICO DE",
            "Firmado Digitalmente",
            "Instituto Ecuatoriano de Seguridad Social",
            "Garantías Jurisdiccionales",
            "Control Constitucional",
            "Policía Nacional",
            "Corte Constitucional",
            "Seguridad Social",
            "Matrícula Nro",
            "Protección Nro",
        ],
    },
    {
        "id": "pfp_04_atribuciones",
        "domain": "administrativo",
        "title": "Responsables y notificaciones",
        "text": (
            "Responsable: Juan Carlos Pérez. Elaborado por María Fernanda López. "
            "Notificado a Carlos Luis Tamayo Delgado en la Corte Constitucional."
        ),
        "raw_entities": [
            ("PERSON", "Juan Carlos Pérez"),
            ("PERSON", "María Fernanda López"),
            ("PERSON", "Carlos Luis Tamayo Delgado"),
        ],
        "preserve": ["Corte Constitucional"],
    },
    {
        "id": "pfp_05_identificadores_documentales",
        "domain": "administrativo",
        "title": "Identificadores documentales junto a datos personales",
        "text": (
            "Matrícula Nro. 123456 asignada a Lucía Mercedes Cevallos Toapanta, cédula 1712345678. "
            "Oficio Nro. 001-2026 y Resolución Nro. 045 emitidos por la Coordinación General."
        ),
        "raw_entities": [
            ("PERSON", "Lucía Mercedes Cevallos Toapanta"),
            ("ECUADOR_CEDULA", "1712345678"),
        ],
        "preserve": ["Matrícula Nro", "Oficio Nro", "Resolución Nro", "Coordinación General"],
        "ambiguous": ["123456", "001-2026", "045"],
    },
    {
        "id": "pfp_06_institucion_con_persona",
        "domain": "salud_institucional",
        "title": "Instituciones y personas en el mismo párrafo",
        "text": (
            "El paciente Víctor Hugo Zambrano Pilco fue atendido en el Hospital Básico de Machachi, cuya cobertura "
            "corresponde al Instituto Ecuatoriano de Seguridad Social. Firmado Digitalmente por Dra. Karla "
            "Estefanía Morales Quishpe, Policía Nacional del Ecuador."
        ),
        "raw_entities": [
            ("PERSON", "Víctor Hugo Zambrano Pilco"),
            ("PERSON", "Karla Estefanía Morales Quishpe"),
        ],
        "preserve": ["Hospital Básico", "Instituto Ecuatoriano de Seguridad Social", "Firmado Digitalmente", "Policía Nacional"],
    },
    {
        "id": "pfp_07_fragmentos_incompletos",
        "domain": "documental",
        "title": "Fragmentos truncados de oraciones",
        "text": (
            "…conforme al Control Constitucional y la Constitución Art.\n"
            "…en el marco de las Garantías Jurisdiccionales de la Corte Constitucional. Ante el Hospital Básico\n"
            "Pedro Pablo Salazar Cueva, cédula 1750193282, compareció."
        ),
        "raw_entities": [
            ("PERSON", "Pedro Pablo Salazar Cueva"),
            ("ECUADOR_CEDULA", "1750193282"),
        ],
        "preserve": ["Control Constitucional", "Constitución Art", "Garantías Jurisdiccionales", "Corte Constitucional", "Hospital Básico"],
    },
    {
        "id": "pfp_08_nombres_reales_sin_contexto",
        "domain": "control_positivo",
        "title": "Nombres reales sin disparador ni encabezado",
        "text": (
            "Intervinieron Ana Lucía Paredes Guerrero y Marco Antonio Velasteguí Ruiz. "
            "Según María Soledad Cárdenas Lema, el trámite continúa."
        ),
        "raw_entities": [
            ("PERSON", "Ana Lucía Paredes Guerrero"),
            ("PERSON", "Marco Antonio Velasteguí Ruiz"),
            ("PERSON", "María Soledad Cárdenas Lema"),
        ],
        "preserve": [],
    },
]

if __name__ == "__main__":
    out = Path(__file__).parent / "dataset_person_fp.jsonl"
    write_jsonl(out, build_documents(PERSON_DOCUMENTS))
    print(f"{out.name}: {len(PERSON_DOCUMENTS)} documentos")
