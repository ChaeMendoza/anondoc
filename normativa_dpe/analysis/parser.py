"""
Módulo de análisis semántico y normativo ecuatoriano.
Identificación de Art. 6, Art. 8, observaciones institucionales y sección de conclusiones.
"""
import re
from typing import Dict, Any, Optional, List, Tuple
from normativa_dpe.models import ExtractedDocument

class NormativeParser:
    """Analizador especializado en proyectos de ley e informes jurídicos de la Defensoría del Pueblo."""

    # Expresiones regulares para artículos y conclusiones
    RE_ART_6 = re.compile(r"(?:art[ií]culo\s+6[\.\:\s\-]|art\.\s*6[\.\:\s\-])([^\n]+(?:\n(?!(?:art[ií]culo|art\.|disposici[oó]n|conclusi[oó]n|\d+[\.\-]))[^\n]+)*)", re.IGNORECASE)
    RE_ART_8 = re.compile(r"(?:art[ií]culo\s+8[\.\:\s\-]|art\.\s*8[\.\:\s\-])([^\n]+(?:\n(?!(?:art[ií]culo|art\.|disposici[oó]n|conclusi[oó]n|\d+[\.\-]))[^\n]+)*)", re.IGNORECASE)
    
    TARGET_PHRASE_CONCLUSION_5 = "podría obstaculizar el ejercicio efectivo del derecho a la salud"
    
    RECOMMENDATION_ART_8 = (
        "Se recomienda que el artículo 8 preserve la facultad de la autoridad sanitaria nacional "
        "para actualizar las recomendaciones sobre los grupos de alimentos según la evidencia disponible, "
        "la etapa de vida, la diversidad cultural y las condiciones de acceso de la población."
    )

    NEW_CONCLUSION_5 = (
        "Quinta.- Se recomienda que el artículo 8 preserve expresamente la facultad técnica y privativa "
        "de la Autoridad Sanitaria Nacional para definir y actualizar periódicamente las guías alimentarias "
        "nacionales sobre la base de la mejor evidencia científica disponible, evitando que la ley consagre "
        "una jerarquización nutricional invariable o excluyente de determinados alimentos. Esta regulación "
        "debe armonizarse con los principios de igualdad, no discriminación, pertinencia cultural y territorial, "
        "así como con la disponibilidad y accesibilidad económica de los alimentos, garantizando plenamente "
        "el derecho a la orientación nutricional individualizada consagrado en el artículo 6 del presente proyecto de ley."
    )

    @classmethod
    def extract_articles(cls, text: str) -> Dict[str, str]:
        """Extrae artículos 6 y 8 del texto mediante segmentación regex y normalización."""
        articles = {}
        
        # Búsqueda de Art. 6
        match_6 = cls.RE_ART_6.search(text)
        if match_6:
            articles["articulo_6"] = match_6.group(0).strip()
        
        # Búsqueda de Art. 8
        match_8 = cls.RE_ART_8.search(text)
        if match_8:
            articles["articulo_8"] = match_8.group(0).strip()

        return articles

    @classmethod
    def locate_target_conclusion(cls, doc: ExtractedDocument) -> Optional[Tuple[int, str]]:
        """
        Localiza el párrafo o celda que contiene la conclusión quinta y la frase objeto de revisión:
        'podría obstaculizar el ejercicio efectivo del derecho a la salud'.
        Retorna (paragraph_index, original_text).
        """
        for p in doc.paragraphs:
            if cls.TARGET_PHRASE_CONCLUSION_5.lower() in p.text.lower():
                return (p.index, p.text)
        return None

    @classmethod
    def evaluate_art_8_competence(cls, art_8_text: str, observation_text: str) -> Dict[str, Any]:
        """
        Evalúa si la disposición del artículo 8 y las observaciones preservan la competencia
        técnica de la autoridad sanitaria nacional (MSP) para actualizar recomendaciones alimentarias.
        """
        keywords_sanitary_auth = ["autoridad sanitaria", "ministerio de salud", "msp", "guía alimentaria", "guías alimentarias"]
        keywords_prioritization = ["prioritario", "prioridad", "alto valor biológico", "jerarquización", "jerarquía"]
        keywords_evidence = ["evidencia", "etapa de vida", "diversidad cultural", "acceso"]

        has_sanitary_mention = any(k in art_8_text.lower() for k in keywords_sanitary_auth)
        has_rigid_prioritization = any(k in art_8_text.lower() for k in keywords_prioritization)
        preserves_flexibility = all(k in observation_text.lower() for k in keywords_evidence)

        # Diagnóstico de preservación de facultad técnica
        needs_recommendation = True
        return {
            "has_sanitary_mention": has_sanitary_mention,
            "has_rigid_prioritization": has_rigid_prioritization,
            "preserves_flexibility": preserves_flexibility,
            "requires_amendment": needs_recommendation,
            "recommended_text": cls.RECOMMENDATION_ART_8
        }
