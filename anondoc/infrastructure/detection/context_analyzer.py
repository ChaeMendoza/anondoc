"""
Context Analyzer to evaluate surroundings, prevent false positives, and set confidence levels.
"""
from typing import Set

class ContextAnalyzer:
    """Evaluates lexical context to suppress common false positives."""

    LEGAL_AND_INSTITUTIONAL_FALSE_POSITIVES: Set[str] = {
        "asamblea nacional", "republica del ecuador", "república del ecuador",
        "constitucion de", "constitución de", "codigo organico", "código orgánico",
        "registro oficial", "ley organica", "ley orgánica", "primer debate", "segundo debate",
        "articulo", "artículo", "disposicion", "disposición", "capitulo", "capítulo",
        "derecho a", "politica publica", "política pública", "salud publica", "salud pública",
        "defensoria del pueblo", "defensoría del pueblo", "corte constitucional",
        "tabla", "figura", "anexo", "pagina", "página", "fecha de emision", "fecha de emisión"
    }

    COMMON_MONTHS_ES: Set[str] = {
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    }

    @classmethod
    def is_common_institutional_phrase(cls, text: str) -> bool:
        norm = text.lower().strip()
        for phrase in cls.LEGAL_AND_INSTITUTIONAL_FALSE_POSITIVES:
            if phrase in norm or norm in phrase:
                return True
        # Check if words are purely months or generic calendar words
        words = norm.split()
        if all(w in cls.COMMON_MONTHS_ES or w.isdigit() for w in words):
            return True
        return False

    @staticmethod
    def extract_window(full_text: str, start: int, end: int, window_size: int = 50) -> str:
        """Extracts context window around the detection."""
        left = max(0, start - window_size)
        right = min(len(full_text), end + window_size)
        return full_text[left:right].replace("\n", " ").strip()
