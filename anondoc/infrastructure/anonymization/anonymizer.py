"""
Anonymization Strategies Engine: Redaction, Pseudonymization, and Masking.
"""
from typing import Dict
from anondoc.domain.entities import PIIEntity, EntityCategory, AnonymizationStrategy
from anondoc.config import AppConfig

class AnonymizationStrategyEngine:
    """Computes replacement strings for each entity based on selected strategy."""

    CATEGORY_PREFIX_MAP: Dict[EntityCategory, str] = {
        EntityCategory.PERSON: "PERSONA",
        EntityCategory.ECUADOR_CEDULA: "CEDULA",
        EntityCategory.ECUADOR_RUC: "RUC",
        EntityCategory.PASSPORT: "PASAPORTE",
        EntityCategory.EMAIL: "EMAIL",
        EntityCategory.PHONE: "TELEFONO",
        EntityCategory.CREDIT_CARD: "TARJETA",
        EntityCategory.BANK_ACCOUNT: "CUENTA",
        EntityCategory.DATE_OF_BIRTH: "FECHA_NAC",
        EntityCategory.IP_ADDRESS: "IP",
        EntityCategory.VEHICLE_PLATE: "PLACA",
        EntityCategory.ADDRESS: "DIRECCION",
        EntityCategory.USERNAME: "USUARIO",
        EntityCategory.MEDICAL_DATA: "DATO_MEDICO",
        EntityCategory.FINANCIAL_DATA: "DATO_FINANCIERO",
    }

    @classmethod
    def generate_replacement(
        cls,
        entity: PIIEntity,
        strategy: AnonymizationStrategy,
        pseudonym_map: Dict[str, str],
        category_counters: Dict[str, int],
        custom_placeholder: str = None
    ) -> str:
        """Calculates replacement value for an entity given the active strategy."""
        orig = entity.original_text.strip()

        # 1. Estrategia REDACTION
        if strategy == AnonymizationStrategy.REDACTION:
            if custom_placeholder:
                return custom_placeholder
            prefix = cls.CATEGORY_PREFIX_MAP.get(entity.category, "DATO")
            return f"[{prefix}_ANONIMIZADO]"

        # 2. Estrategia PSEUDONYMIZATION
        elif strategy == AnonymizationStrategy.PSEUDONYMIZATION:
            # Check if this exact text already has an assigned pseudonym in this job
            cache_key = f"{entity.category.value}:{orig.lower()}"
            if cache_key in pseudonym_map:
                return pseudonym_map[cache_key]

            prefix = cls.CATEGORY_PREFIX_MAP.get(entity.category, "ENTIDAD")
            count = category_counters.get(prefix, 1)
            pseudonym = f"{prefix}_{count:03d}"
            category_counters[prefix] = count + 1
            pseudonym_map[cache_key] = pseudonym
            return pseudonym

        # 3. Estrategia MASKING
        elif strategy == AnonymizationStrategy.MASKING:
            return cls._mask_value(entity.category, orig)

        return AppConfig.DEFAULT_REDACTION_PLACEHOLDER

    @classmethod
    def _mask_value(cls, category: EntityCategory, text: str) -> str:
        """Applies partial masking preserving format or last digits."""
        if category == EntityCategory.EMAIL:
            if "@" in text:
                user_part, domain_part = text.split("@", 1)
                if len(user_part) <= 2:
                    masked_user = user_part[0] + "*"
                else:
                    masked_user = user_part[0] + ("*" * (len(user_part) - 1))
                return f"{masked_user}@{domain_part}"
            return "*" * len(text)

        elif category in (EntityCategory.ECUADOR_CEDULA, EntityCategory.ECUADOR_RUC, EntityCategory.CREDIT_CARD, EntityCategory.BANK_ACCOUNT, EntityCategory.PHONE):
            # Conserve last 2 or 4 digits
            digits_count = 2 if len(text) <= 10 else 4
            if len(text) > digits_count:
                return ("*" * (len(text) - digits_count)) + text[-digits_count:]
            return "*" * len(text)

        elif category == EntityCategory.PERSON:
            # Mask names keeping first initial: Juan Pérez -> J*** P****
            parts = text.split()
            masked_parts = []
            for p in parts:
                if len(p) > 1:
                    masked_parts.append(p[0] + ("*" * (len(p) - 1)))
                else:
                    masked_parts.append("*")
            return " ".join(masked_parts)

        # Default masking for other categories
        if len(text) > 4:
            return text[:2] + ("*" * (len(text) - 4)) + text[-2:]
        return "*" * len(text)
