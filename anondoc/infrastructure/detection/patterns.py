"""
Regex and Lexical Patterns for PII Detection with Contextual Windows.
"""
import re

class DetectionPatterns:
    # 1. Correos Electrónicos
    EMAIL_REGEX = re.compile(
        r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]{1,64}@(?:[A-Za-z0-9-]{1,63}\.){1,8}[A-Za-z]{2,24}\b",
        re.IGNORECASE
    )

    # 2. Cédulas Ecuatorianas (candidatos de 10 dígitos)
    CEDULA_REGEX = re.compile(r"\b(?<!\d)(\d{10})(?!\d)\b")

    # 3. RUC Ecuatoriano (candidatos de 13 dígitos)
    RUC_REGEX = re.compile(r"\b(?<!\d)(\d{13})(?!\d)\b")

    # 4. Tarjetas de Pago / Crédito / Débito (13 a 19 dígitos, con o sin guiones/espacios)
    CREDIT_CARD_REGEX = re.compile(
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}|(?:2131|1800|35\d{3})\d{11}|(?:[0-9]{4}[-\s]){3}[0-9]{4})\b"
    )

    # 5. Teléfonos (Móviles y Fijos Ecuador y formatos internacionales)
    PHONE_REGEX = re.compile(
        r"(?:(?:\+?593\s?|0)(?:9\d{8}|[2-7]\d{7})|\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b)"
    )

    # 6. Direcciones IPv4
    IPV4_REGEX = re.compile(
        r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    )

    # 7. Placas vehiculares (Ecuador: 3 letras - 3 o 4 dígitos)
    VEHICLE_PLATE_REGEX = re.compile(
        r"\b[A-Z]{3}[-\s]?[0-9]{3,4}\b"
    )

    # 8. Pasaportes con contexto
    PASSPORT_REGEX = re.compile(
        r"(?i)(?:pasaporte|passport|nro\.?\s*pasaporte)[\s\:\#]*([A-Z0-9]{6,10})\b"
    )

    # 9. Nombres de usuario
    USERNAME_REGEX = re.compile(
        r"(?i)(?:username|usuario|user|alias)[\s\:\=]+([A-Za-z0-9_.]{3,30})\b|(?<=\s)@([A-Za-z0-9_.]{3,30})\b"
    )

    # 10. Cuentas bancarias con contexto
    BANK_ACCOUNT_REGEX = re.compile(
        r"(?i)(?:cuenta|cta\.?|nro\.?\s*cuenta|iban)[\s\:\#]*(?:ahorros?|corriente)?[\s\:\#]*([0-9]{8,24})\b"
    )

    # 11. Fechas de nacimiento con contexto
    DATE_OF_BIRTH_REGEX = re.compile(
        r"(?i)(?:fecha\s+de\s+nacimiento|f\.?\s*nacimiento|nacido\s+el|naci[oó]\s+el)[\s\:\#]*([0-3]?[0-9][\/\-\.][0-1]?[0-9][\/\-\.][1-2][0-9]{3})\b"
    )

    # 12. Direcciones Físicas con contexto de calle/av
    ADDRESS_REGEX = re.compile(
        r"(?i)\b(?:calle|av\.?|avenida|pasaje|barrio|sector|ciudadela|mz\.?|manzana|intersecci[oó]n|diagonal)\s+[A-Za-z0-9\s\#\-\.,N°º]{6,60}(?=[,\.\n]|$)"
    )

    # 13. Datos Médicos sensibles
    MEDICAL_REGEX = re.compile(
        r"(?i)\b(?:diagn[oó]stico|historia\s+cl[ií]nica|patolog[ií]a|enfermedad|medicaci[oó]n|prescripci[oó]n|cie-10|hipertensi[oó]n|diabetes|c[aá]ncer|tratamiento\s+oncol[oó]gico|vih|seropositivo)\b[\s\:\-]*([A-Za-z0-9\s,]{4,50})(?=[,\.\n]|$)"
    )

    # 14. Datos Financieros personales
    FINANCIAL_REGEX = re.compile(
        r"(?i)(?:sueldo|salario|remuneraci[oó]n|ingreso\s+mensual|endeudamiento|deuda|saldo\s+disponible)[\s\:\$]*(\$?\s*[0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]{2})?)\b"
    )

    # 15. Nombres propios con contexto de tratamiento personal.
    # Solo las palabras de tratamiento ignoran mayúsculas; el nombre debe estar capitalizado (o en MAYÚSCULAS),
    # de modo que verbos o preposiciones ("paciente refiere dolor", "titular de la cédula") no se capturen.
    PERSON_CONTEXT_REGEX = re.compile(
        r"\b(?i:sr\.|sra\.|dr\.|dra\.|ing\.|abg\.|lic\.|don|do[ñn]a|se[ñn]or|se[ñn]ora|ciudadano|ciudadana|paciente|titular|compareciente)"
        r"\s+((?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+|[A-ZÁÉÍÓÚÑ]{2,})"
        r"(?:\s+(?:(?i:de|del|la|las|los)\s+){0,2}(?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+|[A-ZÁÉÍÓÚÑ]{2,})){1,3})\b"
    )

    # Nombre tras una fórmula de atribución documental ("Firmado digitalmente por GALITO JAPÓN NÚÑEZ").
    # Sólo el disparador es insensible a mayúsculas; el nombre debe ir en Capitalizada o MAYÚSCULAS.
    PERSON_ATTRIBUTION_REGEX = re.compile(
        r"\b(?i:firmad[oa]\s+(?:digital|electr[oó]nic[oa]?)mente\s+por|firmad[oa]\s+por|elaborad[oa]\s+por|"
        r"revisad[oa]\s+por|aprobad[oa]\s+por|notificad[oa]\s+a|responsable)\s*:?\s*"
        r"((?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+|[A-ZÁÉÍÓÚÑ]{2,})"
        r"(?:[ \t]+(?:(?i:de|del|la|las|los)[ \t]+){0,2}(?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+|[A-ZÁÉÍÓÚÑ]{2,})){1,4})\b"
    )

    # Nombres sin título explícito pero estructura de Nombre Apellido con mayúscula inicial
    PERSON_STANDALONE_REGEX = re.compile(
        r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,15}\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,15}(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,15}){0,2})\b"
    )
