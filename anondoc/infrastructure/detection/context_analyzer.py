"""
Context Analyzer to evaluate surroundings, prevent false positives, and set confidence levels.
"""
import re
import unicodedata
from typing import FrozenSet, List, Optional, Set, Tuple


def _normalize(text: str) -> str:
    """Lowercase and strip accents so lexicon lookups ignore capitalisation and diacritics."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _with_plurals(words: str) -> FrozenSet[str]:
    out: Set[str] = set()
    for w in words.split():
        out.add(w)
        out.add(w + ("es" if w.endswith(("n", "l", "r", "d", "z")) else "s"))
    return frozenset(out)


# Generic institutional / administrative / documental vocabulary. A name candidate made ONLY of these
# tokens (plus connectors) describes an organisation, office or document, never a person.
ADMINISTRATIVE_TOKENS: FrozenSet[str] = _with_plurals(
    "hospital clinica centro unidad instituto ministerio secretaria subsecretaria direccion coordinacion "
    "departamento gerencia jefatura division area oficina agencia sucursal banco cooperativa fundacion "
    "universidad escuela colegio municipio gobierno consejo junta comision comite tribunal juzgado fiscalia "
    "corte notaria registro servicio sistema red plan programa proyecto proceso seccion superintendencia "
    "contraloria procuraduria defensoria asamblea presidencia judicatura "
    "general nacional provincial cantonal parroquial distrital zonal regional metropolitano municipal social "
    "publico publica privado privada basico basica medico medica tecnico tecnica juridico juridica "
    "administrativo administrativa financiero financiera institucional interinstitucional operativo operativa "
    "docente educativa educativo judicial civil penal laboral tributario tributaria estatal central ejecutivo "
    "legal documental digital electronico electronica integral anual hospitalaria hospitalario sanitaria "
    "sanitario ecuatoriano ecuatoriana contencioso penitenciario penitenciaria interno interna matriz rural "
    "urbano urbana autonomo autonoma descentralizado descentralizada especializado especializada "
    "resolucion oficio memorando circular acta informe certificado certificacion codigo matricula nro numero "
    "no anexo formulario solicitud tramite expediente contrato convenio reglamento ley organica decreto "
    "acuerdo disposicion articulo capitulo titulo garantia garantias contratacion talento humano humanos "
    "recursos gestion planificacion prestacion servicios seguridad salud cuidados intensivos emergencias "
    "especialidades estadistica normalizacion portal inspeccion judicatura rentas aduana aduanas "
    "dr dra sr sra ing abg lic mgs msc econ arq "
    "director directora gerente jefe jefa coordinador coordinadora secretario subsecretario subsecretaria "
    "juez jueza fiscal notario notaria alcalde alcaldesa ministro ministra presidente presidenta delegado "
    "delegada analista asistente subdirector subdirectora administrador administradora superintendente "
    "firmado firmada digitalmente electronicamente elaborado elaborada revisado revisada aprobado aprobada "
    "notificado notificada responsable constitucion constitucional constitucionales jurisdiccional "
    "jurisdiccionales control proteccion policia art arts sentencia apelacion casacion recurso tutela "
    "primero primera segunda tercero tercera cuarto cuarta quinto quinta sexto sexta septimo "
    "septima octavo octava noveno novena decimo decima vigesimo vigesima trigesimo trigesima unico unica"
)

# Role and kinship nouns: they point at a person but are not personal data themselves.
ROLE_TOKENS: FrozenSet[str] = _with_plurals(
    "conyuge esposo esposa hijo hija padre madre hermano hermana abuelo abuela tio tia sobrino sobrina "
    "solicitante beneficiario beneficiaria compareciente titular paciente ciudadano ciudadana trabajador "
    "trabajadora servidor servidora contribuyente demandante demandado demandada cliente usuario usuaria "
    "representante apoderado apoderada testigo"
)

# Heads of institution names; a capitalised name right after one of them is the proper name of that
# institution ("Hospital Pablo Arévalo", "Unidad Educativa Eugenio Espejo"), not a person.
INSTITUTION_HEADS: FrozenSet[str] = _with_plurals(
    "hospital clinica escuela colegio universidad instituto centro banco fundacion cooperativa ministerio "
    "municipio educativa dispensario subcentro estadio teatro museo biblioteca coliseo"
)

# Street / place-type words: the name after them ("Av. Simón Bolívar") names a street, not a person.
STREET_HEADS: FrozenSet[str] = _with_plurals("calle av avenida pasaje ciudadela urbanizacion barrio sector parque")

EPONYM_HEADS: FrozenSet[str] = INSTITUTION_HEADS | STREET_HEADS

CONNECTOR_TOKENS: FrozenSet[str] = frozenset({"de", "del", "la", "las", "los", "el", "y", "e", "en", "para", "al"})
_NUMBER_MARKERS: FrozenSet[str] = frozenset({"no", "nro", "n"})
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_WORD_RE = re.compile(r"\S+")
_PRECEDING_HEAD_RE = re.compile(r"([a-z0-9]+)\.?\s+(?:(?:de|del)\s+(?:la\s+|los\s+|las\s+)?)?$")


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

    _phrase_tokens: Optional[List[Tuple[str, ...]]] = None
    _phrase_vocab: Optional[FrozenSet[str]] = None

    @classmethod
    def _load_phrase_index(cls) -> Tuple[List[Tuple[str, ...]], FrozenSet[str]]:
        if cls._phrase_tokens is None:
            cls._phrase_tokens = [
                tuple(_TOKEN_RE.findall(_normalize(p))) for p in cls.LEGAL_AND_INSTITUTIONAL_FALSE_POSITIVES
            ]
            cls._phrase_vocab = frozenset(t for phrase in cls._phrase_tokens for t in phrase)
        return cls._phrase_tokens, cls._phrase_vocab

    @classmethod
    def is_common_institutional_phrase(cls, text: str) -> bool:
        """
        True when the span is only a legal/institutional expression (or month / number).
        A listed phrase must match whole words and the rest of the span may only be connectors or
        numbering, so a real name that merely contains a listed word or substring is never discarded.
        """
        # Check if words are purely months or generic calendar words
        words = _normalize(text).split()
        if all(w in cls.COMMON_MONTHS_ES or w.isdigit() for w in words):
            return True

        tokens = _TOKEN_RE.findall(_normalize(text))
        phrases, vocab = cls._load_phrase_index()
        listed = [t for t in tokens if t in vocab and t not in CONNECTOR_TOKENS]
        if listed and all(t in vocab or t in CONNECTOR_TOKENS or t.isdigit() for t in tokens):
            return True
        for phrase in phrases:
            n = len(phrase)
            for i in range(len(tokens) - n + 1):
                if tuple(tokens[i:i + n]) != phrase:
                    continue
                rest = tokens[:i] + tokens[i + n:]
                if all(t in CONNECTOR_TOKENS or t in _NUMBER_MARKERS or t.isdigit() for t in rest):
                    return True
        return False

    @classmethod
    def is_nonpersonal_semantic_span(cls, text: str, full_text: str, start: int, category_is_address: bool) -> bool:
        """
        True when a semantic (GLiNER) PERSON/ADDRESS span is really an institution, office, role or document term:
        - it is made only of administrative / role words ('Dirección Administrativa', 'cónyuge');
        - it starts with an institution head ('Banco Bolivariano', 'Hospital Pablo Arévalo');
        - (PERSON) it directly follows an institution/street head ('Hospital' + 'Pablo Arévalo').
        Whole-word matching only: a span with any other word is kept.
        """
        tokens = _TOKEN_RE.findall(_normalize(text))
        if not tokens:
            return False
        allowed = ADMINISTRATIVE_TOKENS | ROLE_TOKENS | CONNECTOR_TOKENS | _NUMBER_MARKERS
        if not category_is_address:
            allowed = allowed | EPONYM_HEADS
        if all(t in allowed or t.isdigit() for t in tokens):
            return True
        if tokens[0] in INSTITUTION_HEADS:
            return True
        return not category_is_address and cls._preceded_by_eponym_head(full_text, start)

    @classmethod
    def refine_person_span(
        cls, full_text: str, start: int, end: int, check_preceding: bool = False
    ) -> Optional[Tuple[int, int]]:
        """
        Narrows a capitalised-words person candidate to the part that can really be a name.
        Leading/trailing administrative tokens ('Departamento Jurídico', 'Dra') are trimmed off, so a name
        glued to a title or office keeps only its own words. Returns None when nothing name-like remains:
        the whole span is administrative, it is the proper name of an institution or street
        ('Hospital Pablo Arévalo', 'Av. Simón Bolívar'), or fewer than two name words are left.
        Words are only matched whole, never by substring, so real names are not discarded.
        """
        words = [(m.start() + start, m.end() + start, _normalize(m.group(0)).strip(".,;:"))
                 for m in _WORD_RE.finditer(full_text[start:end])]
        trimmable = ADMINISTRATIVE_TOKENS | ROLE_TOKENS | EPONYM_HEADS | CONNECTOR_TOKENS | _NUMBER_MARKERS
        lo, hi = 0, len(words)
        while lo < hi and words[lo][2] in trimmable:
            lo += 1
        if any(w[2] in EPONYM_HEADS for w in words[:lo]):
            return None
        while hi > lo and words[hi - 1][2] in trimmable:
            hi -= 1
        name_words = [w for w in words[lo:hi] if w[2] not in CONNECTOR_TOKENS]
        if len(name_words) < 2:
            return None
        if check_preceding and cls._preceded_by_eponym_head(full_text, words[lo][0]):
            return None
        return words[lo][0], words[hi - 1][1]

    @staticmethod
    def _preceded_by_eponym_head(full_text: str, start: int) -> bool:
        before = _normalize(full_text[max(0, start - 40):start])
        m = _PRECEDING_HEAD_RE.search(before)
        return bool(m and m.group(1) in EPONYM_HEADS)

    @staticmethod
    def extract_window(full_text: str, start: int, end: int, window_size: int = 50) -> str:
        """Extracts context window around the detection."""
        left = max(0, start - window_size)
        right = min(len(full_text), end + window_size)
        return full_text[left:right].replace("\n", " ").strip()
