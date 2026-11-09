"""
Dataset Builder and Integrity Validator for AnonDoc Benchmarks.
Calculates and strictly verifies ground-truth entity spans in realistic
Spanish administrative, judicial, medical, labor, and control documents.
"""
import json
from pathlib import Path
from typing import List, Dict, Any

DOCUMENTS: List[Dict[str, Any]] = [
    # -------------------------------------------------------------------------
    # 1. JUDICIAL / COMPARECENCIA LEGAL
    # -------------------------------------------------------------------------
    {
        "id": "doc_01_comparecencia_notarial",
        "domain": "judicial",
        "title": "Acta Notarial de Declaración Jurada",
        "text": (
            "En la ciudad de Quito, a los quince días del mes de marzo del año 2024, comparece ante mí, "
            "el Notario Vigésimo Primero, la señora María Elena Salazar Torres, domiciliada en la Av. "
            "Amazonas N24-150 y Colón, portadora de la cédula de identidad 1710034065, de estado civil soltera, "
            "con correo electrónico m.salazar@estudiojuridico.ec y teléfono celular +593998765432. "
            "La compareciente declara bajo juramento no adeudar al Servicio de Rentas Internas con RUC 1710034065001."
        ),
        "raw_entities": [
            ("ADDRESS", "Quito"),
            ("PERSON", "María Elena Salazar Torres"),
            ("ADDRESS", "Av. Amazonas N24-150 y Colón"),
            ("ECUADOR_CEDULA", "1710034065"),
            ("EMAIL", "m.salazar@estudiojuridico.ec"),
            ("PHONE", "+593998765432"),
            ("ECUADOR_RUC", "1710034065001"),
        ]
    },
    {
        "id": "doc_02_demanda_laboral",
        "domain": "judicial",
        "title": "Demanda Individual de Trabajo",
        "text": (
            "SEÑOR JUEZ DE LA UNIDAD JUDICIAL DE TRABAJO DE PICHINCHA.\n"
            "Carlos Eduardo Jaramillo Vega, con cédula número 0910034068, con dirección electrónica "
            "carlos.jaramillo@litigios.com.ec, domiciliado en Calle Los Rosales 456 y Granados, sector El Batán, "
            "por mis propios derechos, interpongo demanda laboral en contra de la empresa SERVICIOS AMBIENTALES S.A., "
            "con RUC 1790011234001, representada por el Ing. Roberto Patricio Andrade Castro."
        ),
        "raw_entities": [
            ("ADDRESS", "PICHINCHA"),
            ("PERSON", "Carlos Eduardo Jaramillo Vega"),
            ("ECUADOR_CEDULA", "0910034068"),
            ("EMAIL", "carlos.jaramillo@litigios.com.ec"),
            ("ADDRESS", "Calle Los Rosales 456 y Granados, sector El Batán"),
            ("ECUADOR_RUC", "1790011234001"),
            ("PERSON", "Roberto Patricio Andrade Castro"),
        ]
    },
    {
        "id": "doc_03_poder_especial",
        "domain": "judicial",
        "title": "Poder Especial y Procuración Judicial",
        "text": (
            "Otorgo poder especial, amplio y suficiente a favor de la Abg. Gabriela Vanessa Morales Dávila, "
            "titular de la cédula 1102345678, con domicilio profesional en Pasaje San Luis N12 y 10 de Agosto, "
            "para que represente mis derechos en el proceso arbitral. "
            "Notificaciones las recibiré al casillero judicial 1204 y al correo gaby_morales@defensoria.org."
        ),
        "raw_entities": [
            ("PERSON", "Gabriela Vanessa Morales Dávila"),
            ("ECUADOR_CEDULA", "1102345678"),
            ("ADDRESS", "Pasaje San Luis N12 y 10 de Agosto"),
            ("EMAIL", "gaby_morales@defensoria.org"),
        ]
    },

    # -------------------------------------------------------------------------
    # 2. SALUD / CLÍNICA / HISTORIA MÉDICA
    # -------------------------------------------------------------------------
    {
        "id": "doc_04_epicrisis_medica",
        "domain": "salud",
        "title": "Epicrisis y Resumen de Alta Hospitalaria",
        "text": (
            "HOSPITAL METROPOLITANO DE QUITO - SERVICIO DE CARDIOLOGÍA\n"
            "Paciente: Juan Francisco Benalcázar Ortiz, nacido el 14/05/1972, cédula 1709876543.\n"
            "Diagnóstico de ingreso: Hipertensión arterial refractaria y diabetes mellitus tipo 2.\n"
            "El paciente refiere dolor precordial de tres días de evolución. Se prescribe medicación: "
            "Enalapril 20mg cada 12 horas y Metformina 850mg. Teléfono de contacto de emergencia: 022456789."
        ),
        "raw_entities": [
            ("PERSON", "Juan Francisco Benalcázar Ortiz"),
            ("DATE_OF_BIRTH", "14/05/1972"),
            ("ECUADOR_CEDULA", "1709876543"),
            ("MEDICAL_DATA", "Hipertensión arterial refractaria y diabetes mellitus tipo 2"),
            ("PHONE", "022456789"),
        ]
    },
    {
        "id": "doc_05_certificado_oncologia",
        "domain": "salud",
        "title": "Certificado Médico de Tratamiento Especializado",
        "text": (
            "Certifico que la paciente Ana Lucía Villacís Paredes se encuentra bajo tratamiento oncológico "
            "en esta casa de salud desde enero del presente año. Su diagnóstico confirmado es adenocarcinoma "
            "gástrico estadio II. Para fines pertinentes se emite el presente a petición del Dr. Fernando Cárdenas "
            "al correo clinica_oncologica@solca.med.ec."
        ),
        "raw_entities": [
            ("PERSON", "Ana Lucía Villacís Paredes"),
            ("MEDICAL_DATA", "tratamiento oncológico"),
            ("MEDICAL_DATA", "adenocarcinoma gástrico estadio II"),
            ("PERSON", "Fernando Cárdenas"),
            ("EMAIL", "clinica_oncologica@solca.med.ec"),
        ]
    },

    # -------------------------------------------------------------------------
    # 3. LABORAL / RECURSOS HUMANOS / NÓMINA
    # -------------------------------------------------------------------------
    {
        "id": "doc_06_rol_pago",
        "domain": "laboral",
        "title": "Rol Individual de Pago de Haberes",
        "text": (
            "EMPRESA PÚBLICA METROPOLITANA DE MOVILIDAD Y OBRAS PÚBLICAS\n"
            "Rol de pagos mensual: Octubre 2024\n"
            "Empleado: Diego Fernando Castro Espinosa\n"
            "Cédula: 1712345674 | Cargo: Analista de Sistemas | Cuenta de ahorros: 220034567890\n"
            "Sueldo básico unificado: $ 1.250,00 | Aporte personal IESS 9.45%: $ 118,12 | "
            "Total neto a recibir: $ 1.131,88 en cuenta bancaria Banco Pichincha."
        ),
        "raw_entities": [
            ("PERSON", "Diego Fernando Castro Espinosa"),
            ("ECUADOR_CEDULA", "1712345674"),
            ("BANK_ACCOUNT", "220034567890"),
            ("FINANCIAL_DATA", "$ 1.250,00"),
            ("FINANCIAL_DATA", "$ 1.131,88"),
        ]
    },
    {
        "id": "doc_07_contrato_prestacion_servicios",
        "domain": "laboral",
        "title": "Contrato de Prestación de Servicios Profesionales",
        "text": (
            "Comparecen a la celebración del presente contrato: por una parte la Lic. Mónica Beatriz Zambrano Álava, "
            "con cédula de ciudadanía 1309876541, domiciliada en Manta, Barrio Los Esteros calle 103 y Av. 105; "
            "y por otra parte el Arq. Gonzalo Javier Delgado Intriago con cédula 1308765432. "
            "Los honorarios profesionales mensuales se fijan en salario de $ 2.800,00 pagaderos mediante "
            "transferencia a la cta. corriente 3456789012 del Banco de Guayaquil."
        ),
        "raw_entities": [
            ("PERSON", "Mónica Beatriz Zambrano Álava"),
            ("ECUADOR_CEDULA", "1309876541"),
            ("ADDRESS", "Manta"),
            ("ADDRESS", "Barrio Los Esteros calle 103 y Av. 105"),
            ("PERSON", "Gonzalo Javier Delgado Intriago"),
            ("ECUADOR_CEDULA", "1308765432"),
            ("FINANCIAL_DATA", "$ 2.800,00"),
            ("BANK_ACCOUNT", "3456789012"),
        ]
    },

    # -------------------------------------------------------------------------
    # 4. MUNICIPAL / TRÁNSITO / VEHICULAR
    # -------------------------------------------------------------------------
    {
        "id": "doc_08_infraccion_transito",
        "domain": "municipal",
        "title": "Citación de Infracción de Tránsito",
        "text": (
            "AGENCIA METROPOLITANA DE TRÁNSITO DE QUITO\n"
            "Se emite la presente boleta de citación al vehículo con placa PBA-2345, de propiedad del "
            "señor Luis Alfonso Guanochanga Toapanta, portador de la cédula 1714567890, "
            "por exceso de velocidad en la Av. Simón Bolívar intersección con Panamericana Norte. "
            "Consultas y apelaciones al portal institucional o al teléfono 023952300 extensión 102."
        ),
        "raw_entities": [
            ("VEHICLE_PLATE", "PBA-2345"),
            ("PERSON", "Luis Alfonso Guanochanga Toapanta"),
            ("ECUADOR_CEDULA", "1714567890"),
            ("ADDRESS", "Av. Simón Bolívar intersección con Panamericana Norte"),
            ("PHONE", "023952300"),
        ]
    },
    {
        "id": "doc_09_permiso_construccion",
        "domain": "municipal",
        "title": "Licencia Metropolitana Urbanística de Construcción",
        "text": (
            "MUNICIPIO DEL DISTRITO METROPOLITANO DE QUITO\n"
            "Se otorga la licencia de construcción No. LMU-2024-8971 al solicitante Rodrigo Esteban Paredes Cueva, "
            "identificado con cédula 1711223344 y RUC 1711223344001, para el predio ubicado en pasaje "
            "El Manantial No. 12 y Av. Mariana de Jesús, sector Bellavista. Contacto del proyectista: "
            "rodrigo_paredes@arquitectos.ec, celular 0984123456."
        ),
        "raw_entities": [
            ("PERSON", "Rodrigo Esteban Paredes Cueva"),
            ("ECUADOR_CEDULA", "1711223344"),
            ("ECUADOR_RUC", "1711223344001"),
            ("ADDRESS", "pasaje El Manantial No. 12 y Av. Mariana de Jesús"),
            ("EMAIL", "rodrigo_paredes@arquitectos.ec"),
            ("PHONE", "0984123456"),
        ]
    },

    # -------------------------------------------------------------------------
    # 5. FINANCIERO / COMERCIAL / TARJETAS
    # -------------------------------------------------------------------------
    {
        "id": "doc_10_solicitud_credito",
        "domain": "financiero",
        "title": "Solicitud de Tarjeta de Crédito y Crédito de Consumo",
        "text": (
            "BANCO GUAYAQUIL - FORMULARIO DE VINCULACIÓN DE CLIENTES\n"
            "Titular: Patricia Alexandra Moncayo Rivas, cédula 0912345678, pasaporte A1234567, "
            "nacida el 28/11/1988 en Guayaquil, correo patricia.moncayo@finanzas.com.\n"
            "Tarjeta de pago asignada: 453201511283034. Saldo disponible inicial: $ 3.500,00.\n"
            "Dirección de correspondencia: Ciudadela Kennedy Norte Mz. 12 solar 4 y Av. Francisco de Orellana."
        ),
        "raw_entities": [
            ("PERSON", "Patricia Alexandra Moncayo Rivas"),
            ("ECUADOR_CEDULA", "0912345678"),
            ("PASSPORT", "A1234567"),
            ("DATE_OF_BIRTH", "28/11/1988"),
            ("ADDRESS", "Guayaquil"),
            ("EMAIL", "patricia.moncayo@finanzas.com"),
            ("CREDIT_CARD", "453201511283034"),
            ("FINANCIAL_DATA", "$ 3.500,00"),
            ("ADDRESS", "Ciudadela Kennedy Norte Mz. 12 solar 4 y Av. Francisco de Orellana"),
        ]
    },
    {
        "id": "doc_11_seguridad_informatica",
        "domain": "tecnologia",
        "title": "Reporte de Incidente de Seguridad Telemática",
        "text": (
            "CENTRO DE RESPUESTA A INCIDENTES INFORMÁTICOS (CSIRT)\n"
            "Se detectó una intrusión originada desde la dirección IP 192.168.10.45 hacia el servidor central. "
            "El usuario comprometido fue identificado con el username admin_sec24 y alias @sec_specialist. "
            "El técnico responsable del informe es el Ing. Walter Marcelo Reinoso Pazmiño, teléfono +59322987654."
        ),
        "raw_entities": [
            ("IP_ADDRESS", "192.168.10.45"),
            ("USERNAME", "admin_sec24"),
            ("USERNAME", "sec_specialist"),
            ("PERSON", "Walter Marcelo Reinoso Pazmiño"),
            ("PHONE", "+59322987654"),
        ]
    },

    # -------------------------------------------------------------------------
    # 6. COMPRAS PÚBLICAS / INSTITUCIONAL
    # -------------------------------------------------------------------------
    {
        "id": "doc_12_acta_entrega_recepcion",
        "domain": "compras_publicas",
        "title": "Acta de Entrega Recepción Definitiva",
        "text": (
            "MINISTERIO DE EDUCACIÓN - COORDINACIÓN ZONAL 9\n"
            "En la ciudad de Quito comparecen el Ing. Cristian Andrés Viteri Morán en calidad de Administrador del Contrato, "
            "y por parte del contratista el ciudadano Byron Xavier Quishpe Llumiquinga, con cédula 1715678901. "
            "El contratista fija su domicilio fiscal en Diagonal Los Pinos 789 y Av. América. "
            "Monto final liquidado: $ 45.600,00 pagados con cheque institucional a la cuenta corriente 0012983476."
        ),
        "raw_entities": [
            ("ADDRESS", "Quito"),
            ("PERSON", "Cristian Andrés Viteri Morán"),
            ("PERSON", "Byron Xavier Quishpe Llumiquinga"),
            ("ECUADOR_CEDULA", "1715678901"),
            ("ADDRESS", "Diagonal Los Pinos 789 y Av. América"),
            ("FINANCIAL_DATA", "$ 45.600,00"),
            ("BANK_ACCOUNT", "0012983476"),
        ]
    },

    # -------------------------------------------------------------------------
    # 7. CASOS LÍMITE Y TRAMPAS DE FALSOS POSITIVOS (CONTROLES NEGATIVOS)
    # -------------------------------------------------------------------------
    {
        "id": "doc_13_control_falsos_positivos_leyes",
        "domain": "control_negativo",
        "title": "Cuerpo Normativo Legal Institucional (Trampa de Nombres y Números)",
        "text": (
            "La Asamblea Nacional de la República del Ecuador, en virtud del Código Orgánico Integral Penal "
            "y la Constitución de la República, resuelve expedir la Ley Orgánica de Transparencia. "
            "Se publica en el Registro Oficial el día 15 de Octubre de 2023. La Corte Constitucional "
            "y la Defensoría del Pueblo supervisarán su cumplimiento en todo el territorio de la República. "
            "El Art. 45 señala que no se aplicará sanción alguna sin debido proceso."
        ),
        "raw_entities": []
    },
    {
        "id": "doc_14_control_falsos_positivos_numeros",
        "domain": "control_negativo",
        "title": "Registro Técnico de Metadatos y Códigos de Barra",
        "text": (
            "Referencia de inventario código 9991234567 lote técnico 0001234567890. "
            "Resolución Administrativa número 1234-2024 emitida por el Comité Técnico. "
            "Temperatura de calibración 25.5 grados, versión del firmware 1.0.4. "
            "Código de barra EAN 7861001234567 verificado en bodega central."
        ),
        "raw_entities": []
    },
    {
        "id": "doc_15_nombres_sin_titulo_honorifico",
        "domain": "desafio_semantico",
        "title": "Acta Policial de Entrevista sin Tratamientos Honoríficos",
        "text": (
            "Al llegar al sitio del suceso se entrevistó a Mateo Sebastián Morales de la Torre, "
            "quien manifestó que vio a dos sujetos sospechosos correr hacia la quebrada. "
            "Posteriormente llegó Andrea Belén del Pozo Carrión manifestando ser la propietaria "
            "del inmueble. Ninguno de los comparecientes portaba documento de identificación en ese instante. "
            "Número telefónico proporcionado para posteriores notificaciones: 0991122334."
        ),
        "raw_entities": [
            ("PERSON", "Mateo Sebastián Morales de la Torre"),
            ("PERSON", "Andrea Belén del Pozo Carrión"),
            ("PHONE", "0991122334"),
        ]
    }
]


def resolve_entities(text: str, raw_entities: list) -> list:
    resolved = []
    for cat, substr in raw_entities:
        pos = 0
        idx = text.find(substr, pos)
        if idx == -1:
            raise ValueError(f"Substring '{substr}' no encontrada en el texto.")
        start = idx
        end = idx + len(substr)
        # Verify
        assert text[start:end] == substr, f"Desajuste: {text[start:end]} != {substr}"
        resolved.append({
            "category": cat,
            "text": substr,
            "start_char": start,
            "end_char": end
        })
    return resolved


def validate_and_build(target_path: Path):
    target_path.parent.mkdir(parents=True, exist_ok=True)
    validated_docs = []

    print(f"Construyendo y validando {len(DOCUMENTS)} documentos del dataset...")
    for doc in DOCUMENTS:
        doc_id = doc["id"]
        text = doc["text"]
        raw = doc["raw_entities"]
        entities = resolve_entities(text, raw)

        # Ensure no overlapping annotations in ground truth
        entities.sort(key=lambda e: e["start_char"])
        for i in range(len(entities) - 1):
            if entities[i]["end_char"] > entities[i + 1]["start_char"]:
                raise ValueError(
                    f"Colisión de anotación en {doc_id}: {entities[i]} se solapa con {entities[i+1]}"
                )

        validated_docs.append({
            "id": doc_id,
            "domain": doc["domain"],
            "title": doc["title"],
            "text": text,
            "entities": entities
        })

    with open(target_path, "w", encoding="utf-8") as f:
        for doc in validated_docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print(f"Dataset construido exitosamente con {len(validated_docs)} documentos en {target_path}")


if __name__ == "__main__":
    out_file = Path(__file__).resolve().parent / "dataset.jsonl"
    validate_and_build(out_file)
