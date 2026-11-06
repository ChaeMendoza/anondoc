"""
Domain validation rules for sensitive data types (Cédula, RUC, Luhn algorithm, IP, etc.).
"""
import re
from typing import Tuple

class PIIValidators:
    """Algorithmic and rule-based validators for high-confidence entity detection."""

    @staticmethod
    def validate_ecuador_cedula(cedula: str) -> Tuple[bool, str]:
        """
        Validates Ecuadorian identity card (Cédula de Identidad).
        Rules:
        - Exactly 10 digits.
        - First 2 digits (province) between 01 and 24, or 30.
        - 3rd digit must be < 6.
        - 10th digit must match Luhn-like modulo 10 checksum.
        """
        clean = re.sub(r"\D", "", cedula)
        if len(clean) != 10:
            return False, "Longitud no válida (debe tener 10 dígitos)"

        province = int(clean[:2])
        if not (1 <= province <= 24 or province == 30):
            return False, "Código de provincia no válido"

        third_digit = int(clean[2])
        if third_digit >= 6:
            return False, "Tercer dígito no corresponde a persona natural (< 6)"

        coefficients = [2, 1, 2, 1, 2, 1, 2, 1, 2]
        total = 0
        for i in range(9):
            val = int(clean[i]) * coefficients[i]
            if val >= 10:
                val -= 9
            total += val

        verifier = (10 - (total % 10)) % 10
        if verifier == int(clean[9]):
            return True, "Cédula ecuatoriana válida"
        return False, "Dígito verificador incorrecto"

    @classmethod
    def validate_ecuador_ruc(cls, ruc: str) -> Tuple[bool, str]:
        """
        Validates Ecuadorian Tax ID (RUC).
        Handles:
        1. Natural persons (13 digits: valid cédula + 001).
        2. Private companies (3rd digit = 9, modulo 11 algorithm).
        3. Public entities (3rd digit = 6, modulo 11 algorithm).
        """
        clean = re.sub(r"\D", "", ruc)
        if len(clean) != 13:
            return False, "El RUC debe tener 13 dígitos numéricos"

        # 1. RUC Persona Natural
        third_digit = int(clean[2])
        if third_digit < 6:
            valid_ced, _ = cls.validate_ecuador_cedula(clean[:10])
            if valid_ced and clean[10:] != "000":
                return True, "RUC Persona Natural válido"
            return False, "RUC Persona Natural inválido"

        # 2. RUC Sociedad Privada o Extranjeros sin cédula
        if third_digit == 9:
            if clean[10:] == "000":
                return False, "Establecimiento inválido en RUC privado"
            coefficients = [4, 3, 2, 7, 6, 5, 4, 3, 2]
            total = sum(int(clean[i]) * coefficients[i] for i in range(9))
            remainder = total % 11
            verifier = 0 if remainder == 0 else (11 - remainder)
            if verifier == int(clean[9]):
                return True, "RUC Sociedad Privada válido"
            return False, "Dígito verificador de RUC privado inválido"

        # 3. RUC Sociedad Pública
        if third_digit == 6:
            if clean[9:] == "0000":
                return False, "Establecimiento inválido en RUC público"
            coefficients = [3, 2, 7, 6, 5, 4, 3, 2]
            total = sum(int(clean[i]) * coefficients[i] for i in range(8))
            remainder = total % 11
            verifier = 0 if remainder == 0 else (11 - remainder)
            if verifier == int(clean[8]):
                return True, "RUC Institución Pública válido"
            return False, "Dígito verificador de RUC público inválido"

        return False, "Estructura de RUC no reconocida"

    @staticmethod
    def validate_luhn(card_number: str) -> Tuple[bool, str]:
        """Validates credit / debit cards via standard Luhn algorithm."""
        clean = re.sub(r"\D", "", card_number)
        if not (13 <= len(clean) <= 19):
            return False, "Longitud de tarjeta inválida"

        total = 0
        reverse_digits = clean[::-1]
        for i, digit_char in enumerate(reverse_digits):
            n = int(digit_char)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n

        if total % 10 == 0:
            return True, "Tarjeta válida según algoritmo de Luhn"
        return False, "Suma de verificación Luhn incorrecta"

    @staticmethod
    def validate_ipv4(ip: str) -> Tuple[bool, str]:
        parts = ip.strip().split(".")
        if len(parts) != 4:
            return False, "Formato IPv4 inválido"
        for p in parts:
            if not p.isdigit() or not (0 <= int(p) <= 255):
                return False, "Octeto IPv4 fuera de rango"
            if len(p) > 1 and p.startswith("0"):
                return False, "Octeto con cero inicial"
        return True, "Dirección IPv4 válida"
