"""
Hybrid PII Detector combining Regex, Context Windows, and Algorithmic Validation.
"""
import re
from typing import Any, Dict, Iterator, List, Tuple
from anondoc.domain.entities import PIIEntity, EntityCategory, DetectionConfidence
from anondoc.domain.interfaces import IPIIDetector
from anondoc.domain.validators import PIIValidators
from anondoc.infrastructure.detection.patterns import DetectionPatterns
from anondoc.infrastructure.detection.context_analyzer import ContextAnalyzer

class HybridPIIDetector(IPIIDetector):
    """Detects personal data with multi-stage verification and confidence scoring."""

    def __init__(self, active_categories: List[EntityCategory] = None):
        self.active_categories = active_categories or list(EntityCategory)

    def detect_entities(self, text_blocks: List[Dict[str, Any]]) -> List[PIIEntity]:
        all_entities: List[PIIEntity] = []

        for block in text_blocks:
            text = block.get("text", "")
            page_or_section = str(block.get("page_or_section", "1"))
            if not text.strip():
                continue

            block_entities: List[PIIEntity] = []

            # 1. Emails
            if EntityCategory.EMAIL in self.active_categories:
                for match in DetectionPatterns.EMAIL_REGEX.finditer(text):
                    block_entities.append(PIIEntity(
                        category=EntityCategory.EMAIL,
                        original_text=match.group(0),
                        start_char=match.start(),
                        end_char=match.end(),
                        confidence=DetectionConfidence.HIGH,
                        context=ContextAnalyzer.extract_window(text, match.start(), match.end()),
                        page_or_section=page_or_section,
                        validation_details="Sintaxis de correo válida"
                    ))

            # 2. Cédula Ecuatoriana (10 dígitos)
            if EntityCategory.ECUADOR_CEDULA in self.active_categories:
                for match in DetectionPatterns.CEDULA_REGEX.finditer(text):
                    val = match.group(1)
                    is_valid, reason = PIIValidators.validate_ecuador_cedula(val)
                    ctx = ContextAnalyzer.extract_window(text, match.start(), match.end())
                    if is_valid:
                        block_entities.append(PIIEntity(
                            category=EntityCategory.ECUADOR_CEDULA,
                            original_text=val,
                            start_char=match.start(),
                            end_char=match.end(),
                            confidence=DetectionConfidence.HIGH,
                            context=ctx,
                            page_or_section=page_or_section,
                            validation_details=reason
                        ))
                    elif any(k in ctx.lower() for k in ["cédula", "cedula", "identificación", "cc.", "c.i."]):
                        block_entities.append(PIIEntity(
                            category=EntityCategory.ECUADOR_CEDULA,
                            original_text=val,
                            start_char=match.start(),
                            end_char=match.end(),
                            confidence=DetectionConfidence.MEDIUM,
                            context=ctx,
                            page_or_section=page_or_section,
                            validation_details=f"Contexto de cédula con alerta: {reason}"
                        ))

            # 3. RUC Ecuatoriano (13 dígitos)
            if EntityCategory.ECUADOR_RUC in self.active_categories:
                for match in DetectionPatterns.RUC_REGEX.finditer(text):
                    val = match.group(1)
                    is_valid, reason = PIIValidators.validate_ecuador_ruc(val)
                    ctx = ContextAnalyzer.extract_window(text, match.start(), match.end())
                    if is_valid:
                        block_entities.append(PIIEntity(
                            category=EntityCategory.ECUADOR_RUC,
                            original_text=val,
                            start_char=match.start(),
                            end_char=match.end(),
                            confidence=DetectionConfidence.HIGH,
                            context=ctx,
                            page_or_section=page_or_section,
                            validation_details=reason
                        ))
                    elif "ruc" in ctx.lower():
                        block_entities.append(PIIEntity(
                            category=EntityCategory.ECUADOR_RUC,
                            original_text=val,
                            start_char=match.start(),
                            end_char=match.end(),
                            confidence=DetectionConfidence.MEDIUM,
                            context=ctx,
                            page_or_section=page_or_section,
                            validation_details=f"Contexto RUC con observación: {reason}"
                        ))

            # 4. Tarjetas de Pago / Crédito
            if EntityCategory.CREDIT_CARD in self.active_categories:
                for match in DetectionPatterns.CREDIT_CARD_REGEX.finditer(text):
                    val = match.group(0)
                    is_valid, reason = PIIValidators.validate_luhn(val)
                    if is_valid:
                        block_entities.append(PIIEntity(
                            category=EntityCategory.CREDIT_CARD,
                            original_text=val,
                            start_char=match.start(),
                            end_char=match.end(),
                            confidence=DetectionConfidence.HIGH,
                            context=ContextAnalyzer.extract_window(text, match.start(), match.end()),
                            page_or_section=page_or_section,
                            validation_details=reason
                        ))

            # 5. Teléfonos
            if EntityCategory.PHONE in self.active_categories:
                for match in DetectionPatterns.PHONE_REGEX.finditer(text):
                    val = match.group(0).strip()
                    # Filter out short sequences that are not real phones
                    digits = [c for c in val if c.isdigit()]
                    if len(digits) >= 7 and len(digits) <= 15:
                        ctx = ContextAnalyzer.extract_window(text, match.start(), match.end())
                        has_phone_context = any(k in ctx.lower() for k in ["telf", "teléfono", "telefono", "celular", "móvil", "movil", "contacto"])
                        confidence = DetectionConfidence.HIGH if (val.startswith("+593") or val.startswith("09") or has_phone_context) else DetectionConfidence.MEDIUM
                        block_entities.append(PIIEntity(
                            category=EntityCategory.PHONE,
                            original_text=val,
                            start_char=match.start(),
                            end_char=match.end(),
                            confidence=confidence,
                            context=ctx,
                            page_or_section=page_or_section,
                            validation_details="Número telefónico identificado"
                        ))

            # 6. Direcciones IPv4
            if EntityCategory.IP_ADDRESS in self.active_categories:
                for match in DetectionPatterns.IPV4_REGEX.finditer(text):
                    val = match.group(0)
                    is_valid, reason = PIIValidators.validate_ipv4(val)
                    if is_valid:
                        block_entities.append(PIIEntity(
                            category=EntityCategory.IP_ADDRESS,
                            original_text=val,
                            start_char=match.start(),
                            end_char=match.end(),
                            confidence=DetectionConfidence.HIGH,
                            context=ContextAnalyzer.extract_window(text, match.start(), match.end()),
                            page_or_section=page_or_section,
                            validation_details=reason
                        ))

            # 7. Placas vehiculares
            if EntityCategory.VEHICLE_PLATE in self.active_categories:
                for match in DetectionPatterns.VEHICLE_PLATE_REGEX.finditer(text):
                    val = match.group(0).strip()
                    ctx = ContextAnalyzer.extract_window(text, match.start(), match.end())
                    has_plate_ctx = any(k in ctx.lower() for k in ["placa", "vehículo", "vehiculo", "auto", "camioneta", "automóvil"])
                    # Fragment of a longer hyphenated reference (e.g. "MSP-DNE-2024-0456"): a document code, not a plate.
                    in_code = (match.start() > 0 and text[match.start() - 1] == "-") or re.match(
                        r"-[A-Za-z0-9]", text[match.end():match.end() + 2]
                    )
                    if in_code and not has_plate_ctx:
                        continue
                    block_entities.append(PIIEntity(
                        category=EntityCategory.VEHICLE_PLATE,
                        original_text=val,
                        start_char=match.start(),
                        end_char=match.end(),
                        confidence=DetectionConfidence.HIGH if has_plate_ctx else DetectionConfidence.MEDIUM,
                        context=ctx,
                        page_or_section=page_or_section,
                        validation_details="Formato de placa vehicular identificado"
                    ))

            # 8. Pasaportes
            if EntityCategory.PASSPORT in self.active_categories:
                for match in DetectionPatterns.PASSPORT_REGEX.finditer(text):
                    val = match.group(1).strip()
                    block_entities.append(PIIEntity(
                        category=EntityCategory.PASSPORT,
                        original_text=val,
                        start_char=match.start(1),
                        end_char=match.end(1),
                        confidence=DetectionConfidence.HIGH,
                        context=ContextAnalyzer.extract_window(text, match.start(), match.end()),
                        page_or_section=page_or_section,
                        validation_details="Número de pasaporte con contexto"
                    ))

            # 9. Fechas de Nacimiento
            if EntityCategory.DATE_OF_BIRTH in self.active_categories:
                for match in DetectionPatterns.DATE_OF_BIRTH_REGEX.finditer(text):
                    val = match.group(1).strip()
                    block_entities.append(PIIEntity(
                        category=EntityCategory.DATE_OF_BIRTH,
                        original_text=val,
                        start_char=match.start(1),
                        end_char=match.end(1),
                        confidence=DetectionConfidence.HIGH,
                        context=ContextAnalyzer.extract_window(text, match.start(), match.end()),
                        page_or_section=page_or_section,
                        validation_details="Fecha con contexto explícito de nacimiento"
                    ))

            # 10. Cuentas Bancarias
            if EntityCategory.BANK_ACCOUNT in self.active_categories:
                for match in DetectionPatterns.BANK_ACCOUNT_REGEX.finditer(text):
                    val = match.group(1).strip()
                    block_entities.append(PIIEntity(
                        category=EntityCategory.BANK_ACCOUNT,
                        original_text=val,
                        start_char=match.start(1),
                        end_char=match.end(1),
                        confidence=DetectionConfidence.HIGH,
                        context=ContextAnalyzer.extract_window(text, match.start(), match.end()),
                        page_or_section=page_or_section,
                        validation_details="Cuenta bancaria con contexto"
                    ))

            # 11. Datos Médicos
            if EntityCategory.MEDICAL_DATA in self.active_categories:
                for match in DetectionPatterns.MEDICAL_REGEX.finditer(text):
                    val = match.group(0).strip()
                    block_entities.append(PIIEntity(
                        category=EntityCategory.MEDICAL_DATA,
                        original_text=val,
                        start_char=match.start(),
                        end_char=match.end(),
                        confidence=DetectionConfidence.HIGH,
                        context=ContextAnalyzer.extract_window(text, match.start(), match.end()),
                        page_or_section=page_or_section,
                        validation_details="Información clínica / médica sensible"
                    ))

            # 12. Datos Financieros
            if EntityCategory.FINANCIAL_DATA in self.active_categories:
                for match in DetectionPatterns.FINANCIAL_REGEX.finditer(text):
                    val = match.group(0).strip()
                    block_entities.append(PIIEntity(
                        category=EntityCategory.FINANCIAL_DATA,
                        original_text=val,
                        start_char=match.start(),
                        end_char=match.end(),
                        confidence=DetectionConfidence.MEDIUM,
                        context=ContextAnalyzer.extract_window(text, match.start(), match.end()),
                        page_or_section=page_or_section,
                        validation_details="Dato financiero / salarial personal"
                    ))

            # 13. Direcciones Físicas
            if EntityCategory.ADDRESS in self.active_categories:
                for match in DetectionPatterns.ADDRESS_REGEX.finditer(text):
                    val = match.group(0).strip()
                    block_entities.append(PIIEntity(
                        category=EntityCategory.ADDRESS,
                        original_text=val,
                        start_char=match.start(),
                        end_char=match.end(),
                        confidence=DetectionConfidence.MEDIUM,
                        context=ContextAnalyzer.extract_window(text, match.start(), match.end()),
                        page_or_section=page_or_section,
                        validation_details="Dirección física con nomenclatura vial"
                    ))

            # 14. Nombres Propios (con contexto de tratamiento personal)
            if EntityCategory.PERSON in self.active_categories:
                # Primero nombres con título explícito (Alta Confianza)
                for regex, details in (
                    (DetectionPatterns.PERSON_CONTEXT_REGEX, "Nombre propio precedido de tratamiento honorífico/personal"),
                    (DetectionPatterns.PERSON_ATTRIBUTION_REGEX, "Nombre propio precedido de fórmula de atribución documental"),
                ):
                    for match in regex.finditer(text):
                        span = ContextAnalyzer.refine_person_span(text, match.start(1), match.end(1))
                        if span is None:
                            continue
                        val = text[span[0]:span[1]]
                        if not ContextAnalyzer.is_common_institutional_phrase(val):
                            block_entities.append(PIIEntity(
                                category=EntityCategory.PERSON,
                                original_text=val,
                                start_char=span[0],
                                end_char=span[1],
                                confidence=DetectionConfidence.HIGH,
                                context=ContextAnalyzer.extract_window(text, match.start(), match.end()),
                                page_or_section=page_or_section,
                                validation_details=details
                            ))

                # Nombres independientes (Media / Baja Confianza)
                for span in self._standalone_person_spans(text):
                    val = text[span[0]:span[1]]
                    if ContextAnalyzer.is_common_institutional_phrase(val):
                        continue
                    # Verificar si ya fue capturado con el patrón contextual
                    already_captured = any(e.category == EntityCategory.PERSON and val in e.original_text for e in block_entities)
                    if not already_captured:
                        ctx = ContextAnalyzer.extract_window(text, span[0], span[1])
                        # Si tiene palabras como comparece, firma, autor, ciudadano, cliente -> MEDIA
                        has_name_hint = any(k in ctx.lower() for k in ["firma", "comparece", "autor", "titular", "abogado", "cliente", "paciente"])
                        confidence = DetectionConfidence.MEDIUM if has_name_hint else DetectionConfidence.LOW
                        block_entities.append(PIIEntity(
                            category=EntityCategory.PERSON,
                            original_text=val,
                            start_char=span[0],
                            end_char=span[1],
                            confidence=confidence,
                            context=ctx,
                            page_or_section=page_or_section,
                            validation_details="Nombre propio detectado por estructura léxica"
                        ))

            # Resolver colisiones y solapamientos dentro del bloque
            deduped = self._resolve_overlaps(block_entities)
            all_entities.extend(deduped)

        return all_entities

    @staticmethod
    def _standalone_person_spans(text: str) -> Iterator[Tuple[int, int]]:
        """Capitalised-word name candidates with administrative words trimmed off (see ContextAnalyzer)."""
        regex = DetectionPatterns.PERSON_STANDALONE_REGEX
        pos = 0
        while True:
            match = regex.search(text, pos)
            if not match:
                return
            group = text[match.start(1):match.end(1)]
            lines = [m for m in re.finditer(r"[^\n]+", group)]
            if len(lines) > 1 and all(len(ln.group(0).split()) >= 2 for ln in lines):
                # Each line is a complete candidate on its own (headers stacked on separate lines).
                for ln in lines[:-1]:
                    seg = ContextAnalyzer.refine_person_span(
                        text, match.start(1) + ln.start(), match.start(1) + ln.end(), check_preceding=True
                    )
                    if seg is not None:
                        yield seg
                # The last line may have been cut by the word limit: rescan it with its full budget.
                pos = match.start(1) + lines[-1].start()
                continue
            span = ContextAnalyzer.refine_person_span(text, match.start(1), match.end(1), check_preceding=True)
            if span is not None and span[0] > match.start(1):
                # Leading office words ("Departamento Jurídico") used up part of the token budget:
                # rescan from the real name start so the name is not split in two.
                rematch = regex.match(text, span[0])
                if rematch:
                    match = rematch
                    span = ContextAnalyzer.refine_person_span(text, match.start(1), match.end(1), check_preceding=True)
            pos = match.end()
            if span is not None:
                yield span

    @staticmethod
    def _resolve_overlaps(entities: List[PIIEntity]) -> List[PIIEntity]:
        """Eliminates overlapping entities prioritizing higher confidence and longer spans."""
        if not entities:
            return []

        # Sort by start_char ascending, then confidence priority, then span length descending
        confidence_score = {
            DetectionConfidence.HIGH: 3,
            DetectionConfidence.MEDIUM: 2,
            DetectionConfidence.LOW: 1
        }
        entities.sort(key=lambda e: (e.start_char, -confidence_score[e.confidence], -(e.end_char - e.start_char)))

        resolved: List[PIIEntity] = []
        for ent in entities:
            if not resolved:
                resolved.append(ent)
                continue
            last = resolved[-1]
            # Check overlap
            if ent.start_char < last.end_char:
                # Overlap detected. Keep the one with higher confidence score
                if confidence_score[ent.confidence] > confidence_score[last.confidence]:
                    resolved[-1] = ent
                elif confidence_score[ent.confidence] == confidence_score[last.confidence]:
                    if (ent.end_char - ent.start_char) > (last.end_char - last.start_char):
                        resolved[-1] = ent
            else:
                resolved.append(ent)

        return resolved
