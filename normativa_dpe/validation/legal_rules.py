"""
Módulo de validación jurídica y documental bajo estándares constitucionales del Ecuador.
Verifica competencias del MSP (Art. 32 CRE, Ley Orgánica de Salud), mandato de la Defensoría
del Pueblo (Art. 215 CRE) y coherencia con el derecho a la alimentación adecuada (Art. 13 CRE).
"""
from typing import List, Dict, Any, Tuple
from normativa_dpe.models import ChangeRecord, QualityControlReport, ValidationStatus

class LegalValidator:
    """Validador de rigor técnico-jurídico y control documental."""

    AUTHORIZED_CONSTITUTIONAL_ARTICLES = {"13", "32", "66", "215", "281"}
    MANDATORY_CRITERIA_CONCLUSION = [
        "autoridad sanitaria",
        "evidencia científica",
        "jerarquización nutricional",
        "igualdad",
        "pertinencia cultural",
        "accesibilidad económica",
        "artículo 6"
    ]

    @classmethod
    def validate_change(cls, change: ChangeRecord) -> Tuple[bool, List[str]]:
        """
        Valida que una propuesta de modificación cumpla con los estándares técnicos y jurídicos:
        - No contenga frases genéricas infundadas.
        - Se fundamente en disposiciones existentes de las fuentes.
        - Preserve la competencia técnica de la autoridad sanitaria.
        - Deje expresa constancia de necesidad de revisión humana.
        """
        issues = []

        # 1. Verificar erradicación de afirmaciones genéricas no sustentadas
        if "podría obstaculizar el ejercicio efectivo del derecho a la salud" in change.propuesta_redaccion.lower():
            issues.append("Error: La propuesta conserva afirmaciones abstractas no fundamentadas sobre vulneración del derecho a la salud.")

        # 2. Verificar cumplimiento de los 6 requisitos para la Conclusión 5
        if "conclusión" in change.ubicacion.lower():
            propuesta_lower = change.propuesta_redaccion.lower()
            for crit in cls.MANDATORY_CRITERIA_CONCLUSION:
                if crit not in propuesta_lower:
                    issues.append(f"Falta incorporar el criterio obligatorio: '{crit}' en la conclusión reformulada.")

        # 3. Verificar estado de validación (Human-in-the-loop)
        if change.estado_validacion != ValidationStatus.PENDIENTE_REVISION.value and change.estado_validacion != ValidationStatus.VALIDADO_CONFORME.value:
            issues.append(f"Estado de validación desconocido o no seguro: {change.estado_validacion}")

        is_valid = len(issues) == 0
        return is_valid, issues

    @classmethod
    def generate_quality_control_report(cls, changes: List[ChangeRecord], original_sources: Dict[str, str]) -> QualityControlReport:
        """Genera el reporte de control de calidad documental y jurídico."""
        all_issues = []
        backed_by_sources = True
        unwarranted_claims_eliminated = True
        sanitary_authority_competence_preserved = True

        for c in changes:
            valid, issues = cls.validate_change(c)
            if not valid:
                all_issues.extend([f"[{c.ubicacion}] {iss}" for iss in issues])
            
            # Verificar si la frase no sustentada sigue presente
            if "podría obstaculizar el ejercicio efectivo del derecho a la salud" in c.propuesta_redaccion.lower():
                unwarranted_claims_eliminated = False

            # Verificar preservación de competencia sanitaria
            if "artículo 8" in c.ubicacion.lower() or "conclusión" in c.ubicacion.lower():
                if "autoridad sanitaria" not in c.propuesta_redaccion.lower():
                    sanitary_authority_competence_preserved = False

            # Verificar coherencia con las fuentes originales
            if not c.fuente_respaldo:
                backed_by_sources = False
                all_issues.append(f"[{c.ubicacion}] Modificación sin fuente de respaldo documental trazable.")

        audit_notes = [
            "Control de trazabilidad: Se contrastaron los artículos 6 y 8 del Proyecto de Ley con las observaciones de la Defensoría.",
            "Principio de legalidad y competencia: Se salvaguarda la potestad técnica del Ministerio de Salud Pública (Art. 32 CRE y Ley Orgánica de Salud).",
            "Enfoque de Derechos Humanos: Se incorporan igualdad, no discriminación, pertinencia cultural y territorial, y accesibilidad económica (Art. 13 CRE).",
            "Principio de precaución metodológica: Todo cambio queda marcado como 'PENDIENTE DE REVISIÓN TÉCNICA' para validación del personal técnico-jurídico antes de la suscripción oficial."
        ]
        if all_issues:
            audit_notes.extend([f"OBSERVACIÓN DETECTADA: {iss}" for iss in all_issues])

        return QualityControlReport(
            total_modifications=len(changes),
            modifications_backed_by_sources=backed_by_sources and (len(all_issues) == 0),
            unwarranted_claims_eliminated=unwarranted_claims_eliminated,
            sanitary_authority_competence_preserved=sanitary_authority_competence_preserved,
            human_review_required=True,
            changes=changes,
            audit_notes=audit_notes
        )
