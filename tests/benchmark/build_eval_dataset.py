"""
Independent Hold-Out Evaluation Dataset Builder for AnonDoc (Phase 1+).
Strictly separated from the baseline/calibration set.
Enforces refined taxonomy:
- Generic city names (e.g., 'Quito', 'Manta') are NOT categorized as personal ADDRESS.
- Event or issuance dates are NOT categorized as DATE_OF_BIRTH.
- Diverse structures: formal letters, minutes, customs declarations, clinical notes, negative controls.
- All ground-truth annotations are strictly verified character-by-character.
"""
import json
from pathlib import Path
from typing import List, Dict, Any

HOLDOUT_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "id": "holdout_01_notificacion_tributaria",
        "domain": "tributario",
        "title": "Notificación de Determinación Tributaria Coactiva",
        "text": (
            "SERVICIO DE RENTAS INTERNAS - DIRECCIÓN ZONAL 8\n"
            "Por medio del presente acto administrativo se notifica al contribuyente Esteban Andrés "
            "Guerrero Vinueza, portador de la cédula de identidad 1716543210 y RUC 1716543210001, "
            "con domicilio tributario ubicado en Calle Junín 456 y Córdova, piso 3, oficina 302, "
            "correo de contacto tributario esteban_guerrero@inmobiliaria.ec y teléfono fijo 042345678. "
            "Se determina una obligación tributaria pendiente correspondiente al ejercicio fiscal 2023."
        ),
        "raw_entities": [
            ("PERSON", "Esteban Andrés Guerrero Vinueza"),
            ("ECUADOR_CEDULA", "1716543210"),
            ("ECUADOR_RUC", "1716543210001"),
            ("ADDRESS", "Calle Junín 456 y Córdova, piso 3, oficina 302"),
            ("EMAIL", "esteban_guerrero@inmobiliaria.ec"),
            ("PHONE", "042345678"),
        ]
    },
    {
        "id": "holdout_02_contrato_arrendamiento",
        "domain": "inmobiliario",
        "title": "Contrato de Arrendamiento de Bien Inmueble Residencial",
        "text": (
            "En el Distrito Metropolitano, convienen en celebrar el contrato de arrendamiento: "
            "como arrendadora la Dra. Cecilia Margarita Romero Cevallos con cédula 1103456789; "
            "y como arrendatario el ciudadano Luis Fernando Espinoza Carvajal con cédula 0918765432. "
            "El inmueble arrendado se ubica en Urbanización Los Helechos Mz. B villa 14 y Av. Las Lomas. "
            "El canon mensual pactado asciende a sueldo o renta de $ 650,00 que se acreditará a la "
            "cuenta corriente 1029384756 del Banco Bolivariano. Teléfono de contacto: +593984567890."
        ),
        "raw_entities": [
            ("PERSON", "Cecilia Margarita Romero Cevallos"),
            ("ECUADOR_CEDULA", "1103456789"),
            ("PERSON", "Luis Fernando Espinoza Carvajal"),
            ("ECUADOR_CEDULA", "0918765432"),
            ("ADDRESS", "Urbanización Los Helechos Mz. B villa 14 y Av. Las Lomas"),
            ("FINANCIAL_DATA", "$ 650,00"),
            ("BANK_ACCOUNT", "1029384756"),
            ("PHONE", "+593984567890"),
        ]
    },
    {
        "id": "holdout_03_historia_clinica_cirugia",
        "domain": "salud",
        "title": "Protocolo Quirúrgico y Registro Postoperatorio",
        "text": (
            "CLÍNICA SANTA INÉS - SERVICIO DE CIRUGÍA GENERAL\n"
            "Paciente: Valeria Sofía Narváez Enríquez, fecha de nacimiento 03/12/1995, cédula 0102938475.\n"
            "Diagnóstico preoperatorio: Colelitiasis aguda sintomática y colecistitis crónica litiásica.\n"
            "Cirujano tratante: Dr. Marcelo Hernán Córdova Pazmiño. Se prescribe medicación:\n"
            "Ketorolaco 30mg intravenoso y Ciprofloxacino 500mg vía oral. Contacto: 072834567."
        ),
        "raw_entities": [
            ("PERSON", "Valeria Sofía Narváez Enríquez"),
            ("DATE_OF_BIRTH", "03/12/1995"),
            ("ECUADOR_CEDULA", "0102938475"),
            ("MEDICAL_DATA", "Colelitiasis aguda sintomática y colecistitis crónica litiásica"),
            ("PERSON", "Marcelo Hernán Córdova Pazmiño"),
            ("PHONE", "072834567"),
        ]
    },
    {
        "id": "holdout_04_acta_finiquito",
        "domain": "laboral",
        "title": "Acta de Finiquito y Liquidación de Relación Laboral",
        "text": (
            "MINISTERIO DEL TRABAJO - INSPECCIÓN PROVINCIAL DEL TRABAJO\n"
            "Empleador: LOGÍSTICA DEL ECUADOR S.A., con RUC 1791234567001.\n"
            "Trabajador: Kevin Alexander Guamán Pillajo, con cédula de ciudadanía 1723456789, "
            "con residencia en Pasaje Santa Rosa N3-45 y Pasaje Las Flores, sector Caupicho. "
            "Monto de la liquidación total percibida: $ 3.420,50 mediante cheque entregado en audiencia. "
            "Correo institucional del ex-empleado: kevin_guaman@logistica.com.ec."
        ),
        "raw_entities": [
            ("ECUADOR_RUC", "1791234567001"),
            ("PERSON", "Kevin Alexander Guamán Pillajo"),
            ("ECUADOR_CEDULA", "1723456789"),
            ("ADDRESS", "Pasaje Santa Rosa N3-45 y Pasaje Las Flores, sector Caupicho"),
            ("FINANCIAL_DATA", "$ 3.420,50"),
            ("EMAIL", "kevin_guaman@logistica.com.ec"),
        ]
    },
    {
        "id": "holdout_05_investigacion_forense",
        "domain": "tecnologia",
        "title": "Informe Técnico de Análisis Pericial Informático",
        "text": (
            "UNIDAD DE CIBERCRIMEN - POLICÍA JUDICIAL\n"
            "El perito informático Ing. Álvaro Paul Montalvo Suárez con cédula 1801234567 analizó "
            "los logs de acceso del cortafuegos institucional. Se evidenciaron conexiones anómalas "
            "provenientes de la dirección IP 10.14.22.105 asociadas al usuario con alias @dark_operator "
            "y username sysaudit_root. Vehículo de traslado del perito placa PCH-9876."
        ),
        "raw_entities": [
            ("PERSON", "Álvaro Paul Montalvo Suárez"),
            ("ECUADOR_CEDULA", "1801234567"),
            ("IP_ADDRESS", "10.14.22.105"),
            ("USERNAME", "dark_operator"),
            ("USERNAME", "sysaudit_root"),
            ("VEHICLE_PLATE", "PCH-9876"),
        ]
    },
    {
        "id": "holdout_06_control_negativo_resolucion",
        "domain": "control_negativo",
        "title": "Resolución de Régimen Interno de la Función Judicial",
        "text": (
            "El Consejo de la Judicatura, en uso de las atribuciones conferidas por el Código Orgánico "
            "de la Función Judicial y la Constitución de la República del Ecuador, resuelve convocar a "
            "sesión extraordinaria el 20 de Noviembre de 2024. Los Juzgados de Garantías Penitenciarias "
            "y los Tribunales Distritales de lo Contencioso Administrativo adoptarán las medidas "
            "correspondientes conforme al Memorando Circular No. CJ-DG-2024-0099. No se admitirá recurso alguno."
        ),
        "raw_entities": []
    },
    {
        "id": "holdout_07_carta_solicitud_informacion",
        "domain": "administrativo",
        "title": "Carta de Petición Ciudadana de Acceso a la Información",
        "text": (
            "Señor Director General del Registro Civil.\n"
            "Yo, Tatiana Jimena Alarcón Morales, portadora de la cédula 1719876543, "
            "con correo electrónico tatiana_alarcon@derechoshumanos.org, domiciliada en "
            "Avenida 12 de Octubre N16-114 y Pasaje Foch, solicito copias certificadas de mi partida. "
            "Cualquier notificación telefónica podrá realizarse al número 0995544332."
        ),
        "raw_entities": [
            ("PERSON", "Tatiana Jimena Alarcón Morales"),
            ("ECUADOR_CEDULA", "1719876543"),
            ("EMAIL", "tatiana_alarcon@derechoshumanos.org"),
            ("ADDRESS", "Avenida 12 de Octubre N16-114 y Pasaje Foch"),
            ("PHONE", "0995544332"),
        ]
    },
    {
        "id": "holdout_08_acta_asamblea_copropietarios",
        "domain": "comunitario",
        "title": "Acta de Asamblea General Ordinaria de Copropietarios",
        "text": (
            "CONDOMINIO TORRES DEL RÍO - ACTA No. 04-2024\n"
            "Preside la asamblea el Ing. Fausto Vinicio Barahona Caicedo en calidad de Administrador. "
            "Se constata la deuda de alícuotas del departamento 402 perteneciente al Sr. Nelson "
            "Rodrigo Tapia Cárdenas, cédula 0601234567, con saldo disponible adeudado de $ 840,00. "
            "Se acuerda notificar al casillero electrónico nelson.tapia@inmuebles.ec y cuenta bancaria 4001239876."
        ),
        "raw_entities": [
            ("PERSON", "Fausto Vinicio Barahona Caicedo"),
            ("PERSON", "Nelson Rodrigo Tapia Cárdenas"),
            ("ECUADOR_CEDULA", "0601234567"),
            ("FINANCIAL_DATA", "$ 840,00"),
            ("EMAIL", "nelson.tapia@inmuebles.ec"),
            ("BANK_ACCOUNT", "4001239876"),
        ]
    },
    {
        "id": "holdout_09_declaracion_aduanera_courier",
        "domain": "comercial",
        "title": "Declaración Aduanera Simplificada Courier Internacional",
        "text": (
            "SERVICIO NACIONAL DE ADUANA DEL ECUADOR - DISTRITO AÉREO QUITO\n"
            "Consignatario: Boris Alejandro Vaca Samaniego, pasaporte B9876543, "
            "nacido el 19/08/1982, con dirección de entrega en Manzana 4 Villa 8 y Calle Las Acacias, "
            "teléfono de contacto +59322446688. Valor FOB declarado de la mercadería: $ 1.450,00."
        ),
        "raw_entities": [
            ("PERSON", "Boris Alejandro Vaca Samaniego"),
            ("PASSPORT", "B9876543"),
            ("DATE_OF_BIRTH", "19/08/1982"),
            ("ADDRESS", "Manzana 4 Villa 8 y Calle Las Acacias"),
            ("PHONE", "+59322446688"),
            ("FINANCIAL_DATA", "$ 1.450,00"),
        ]
    },
    {
        "id": "holdout_10_minuta_donacion_inmueble",
        "domain": "notarial",
        "title": "Minuta de Donación Gratuita de Lote de Terreno",
        "text": (
            "SEÑOR NOTARIO: En el protocolo a su cargo sírvase insertar la escritura de donación que otorga "
            "la ciudadana Clara Inés Bustamante Aguirre con cédula 1102983746 a favor de su hijo "
            "el Abg. Camilo Andrés Solórzano Bustamante con cédula 1720987654. "
            "El inmueble se encuentra ubicado en Pasaje San Francisco No. 88 y Av. Maldonado. "
            "Avalúo pericial del predio fijado en el sueldo o valor de $ 58.000,00."
        ),
        "raw_entities": [
            ("PERSON", "Clara Inés Bustamante Aguirre"),
            ("ECUADOR_CEDULA", "1102983746"),
            ("PERSON", "Camilo Andrés Solórzano Bustamante"),
            ("ECUADOR_CEDULA", "1720987654"),
            ("ADDRESS", "Pasaje San Francisco No. 88 y Av. Maldonado"),
            ("FINANCIAL_DATA", "$ 58.000,00"),
        ]
    },
    {
        "id": "holdout_11_certificado_laboral_experiencia",
        "domain": "laboral",
        "title": "Certificado de Experiencia y Desempeño Laboral",
        "text": (
            "A QUIEN CORRESPONDA: Certifico que el Ing. Oswaldo Xavier Benítez Ludeña laboró en nuestra institución "
            "desde el año 2018 hasta agosto de 2024, desempeñando las funciones de Jefe de Telecomunicaciones. "
            "Durante su gestión registró la IP asignada 192.168.100.25 y correo oswaldo_benitez@telecom.ec. "
            "Para constancia firma la Directora de Talento Humano Dra. Lorena Patricia Carrión Vintimilla, teléfono 022987654."
        ),
        "raw_entities": [
            ("PERSON", "Oswaldo Xavier Benítez Ludeña"),
            ("IP_ADDRESS", "192.168.100.25"),
            ("EMAIL", "oswaldo_benitez@telecom.ec"),
            ("PERSON", "Lorena Patricia Carrión Vintimilla"),
            ("PHONE", "022987654"),
        ]
    },
    {
        "id": "holdout_12_control_negativo_compras_publicas",
        "domain": "control_negativo",
        "title": "Extracto de Pliego Técnico del Sistema Nacional de Contratación Pública",
        "text": (
            "El Servicio Nacional de Contratación Pública (SERCOP) publica los pliegos del proceso de subasta inversa "
            "institucional No. SIE-GADM-2024-0012. El presupuesto referencial asignado por el Estado corresponde a "
            "la partida presupuestaria 530804 del clasificador central. La Comisión Técnica y la Gerencia de Compras "
            "sesionarán en el auditorio institucional. Este procedimiento se rige por la Ley Orgánica del Sistema Nacional "
            "de Contratación Pública y su Reglamento General."
        ),
        "raw_entities": []
    }
]


def resolve_holdout_entities(text: str, raw_entities: list) -> list:
    resolved = []
    for cat, substr in raw_entities:
        idx = text.find(substr)
        if idx == -1:
            raise ValueError(f"Substring '{substr}' no encontrada en el texto.")
        start = idx
        end = idx + len(substr)
        assert text[start:end] == substr
        resolved.append({
            "category": cat,
            "text": substr,
            "start_char": start,
            "end_char": end
        })
    return resolved


def build_holdout(target_path: Path):
    target_path.parent.mkdir(parents=True, exist_ok=True)
    validated = []
    print(f"Construyendo y validando {len(HOLDOUT_DOCUMENTS)} documentos del dataset hold-out...")
    for doc in HOLDOUT_DOCUMENTS:
        doc_id = doc["id"]
        text = doc["text"]
        raw = doc["raw_entities"]
        entities = resolve_holdout_entities(text, raw)

        entities.sort(key=lambda e: e["start_char"])
        for i in range(len(entities) - 1):
            if entities[i]["end_char"] > entities[i + 1]["start_char"]:
                raise ValueError(f"Colisión en {doc_id}: {entities[i]} se solapa con {entities[i+1]}")

        validated.append({
            "id": doc_id,
            "domain": doc["domain"],
            "title": doc["title"],
            "text": text,
            "entities": entities
        })

    with open(target_path, "w", encoding="utf-8") as f:
        for doc in validated:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print(f"Dataset de evaluación independiente construido exitosamente ({len(validated)} docs) en {target_path}")


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "dataset_eval_holdout.jsonl"
    build_holdout(out)
