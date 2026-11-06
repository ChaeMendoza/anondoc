"""
Structural inspection of untrusted PDF and DOCX files.

Nothing here trusts the extension, the declared MIME type or the file name:
the format is decided from the content. Every violation raises
DocumentRejected with a stable error code and a message that never contains
document content.
"""
import re
import zipfile
from typing import Any, Dict, List

import defusedxml.ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from anondoc.config import AppConfig

DOCX_MAIN_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

# Relationship types that are inert and allowed to point outside the package.
ALLOWED_EXTERNAL_REL_SUFFIXES = ("/hyperlink",)

FORBIDDEN_DOCX_PREFIXES = (
    "word/vbaproject", "word/vbadata", "word/embeddings/", "word/activex/",
    "word/macrosheets/", "customui/", "word/oleobject",
)
FORBIDDEN_DOCX_MARKERS = (b"<w:altChunk", b"<w:control ", b"<w:object", b"<o:OLEObject", b"<w:ocx")

# Dangerous PDF keys, matched on MuPDF's normalized object rendering (so /J#53 obfuscation is resolved).
PDF_REJECT_KEYS = (
    "JavaScript", "JS", "Launch", "XFA", "RichMedia", "SubmitForm",
    "ImportData", "GoToR", "GoToE", "Movie", "Sound", "Rendition",
)
PDF_REJECT_RE = re.compile(r"/(?:" + "|".join(PDF_REJECT_KEYS) + r")(?![A-Za-z0-9])")
MAX_IMAGE_PIXELS = 100_000_000


class DocumentRejected(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def detect_format(head: bytes) -> str:
    """Returns 'pdf' or 'docx' from magic bytes, else raises."""
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        return "docx"
    raise DocumentRejected("unsupported_format", "Formato no reconocido. Solo se admiten PDF y DOCX.")


def _safe_member_name(name: str) -> bool:
    if not name or "\x00" in name or "\\" in name or name.startswith("/"):
        return False
    if re.match(r"^[A-Za-z]:", name):
        return False
    return ".." not in name.split("/")


def inspect_zip_container(zf: zipfile.ZipFile, compressed_size: int) -> List[zipfile.ZipInfo]:
    """Metadata-level checks of a ZIP central directory (no decompression)."""
    infos = zf.infolist()
    if len(infos) > AppConfig.MAX_ZIP_ENTRIES:
        raise DocumentRejected("zip_too_many_entries", "El paquete contiene demasiadas entradas.")

    seen = set()
    total = 0
    for info in infos:
        if not _safe_member_name(info.filename):
            raise DocumentRejected("zip_bad_path", "El paquete contiene rutas no permitidas.")
        key = info.filename.lower()
        if key in seen:
            raise DocumentRejected("zip_duplicate_entry", "El paquete contiene entradas duplicadas.")
        seen.add(key)
        if info.flag_bits & 0x1:
            raise DocumentRejected("zip_encrypted", "El paquete está cifrado.")
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise DocumentRejected("zip_bad_compression", "Método de compresión no permitido.")
        if info.file_size > AppConfig.MAX_ZIP_ENTRY_BYTES:
            raise DocumentRejected("zip_entry_too_large", "Una entrada del paquete excede el tamaño permitido.")
        total += info.file_size

    if total > AppConfig.MAX_DOCX_UNCOMPRESSED_BYTES:
        raise DocumentRejected("zip_too_large", "El contenido descomprimido excede el límite permitido.")
    if compressed_size > 0 and total / compressed_size > AppConfig.MAX_DECOMPRESSED_RATIO and total > 5 * 1024 * 1024:
        raise DocumentRejected("zip_ratio", "Relación de compresión sospechosa (posible ZIP bomb).")
    return infos


def read_bounded(zf: zipfile.ZipFile, info: zipfile.ZipInfo, budget: List[int]) -> bytes:
    """Reads an entry enforcing real (not declared) sizes against a shared budget."""
    limit = min(AppConfig.MAX_ZIP_ENTRY_BYTES, budget[0])
    with zf.open(info) as fh:
        data = fh.read(limit + 1)
    if len(data) > limit:
        raise DocumentRejected("zip_too_large", "El contenido descomprimido excede el límite permitido.")
    budget[0] -= len(data)
    return data


def parse_xml_safely(data: bytes):
    try:
        return SafeET.fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except DefusedXmlException:
        raise DocumentRejected("xml_forbidden", "El documento contiene construcciones XML no permitidas (DTD/entidades).")
    except SafeET.ParseError:
        raise DocumentRejected("xml_malformed", "El documento contiene XML malformado.")


def inspect_docx(path: str, compressed_size: int) -> Dict[str, Any]:
    """Validates a DOCX package. Returns limitations to report to the user."""
    limitations: List[str] = []
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise DocumentRejected("corrupt", "El archivo DOCX está dañado o no es un ZIP válido.")

    with zf:
        infos = inspect_zip_container(zf, compressed_size)
        names = {i.filename for i in infos}
        if "[Content_Types].xml" not in names or "word/document.xml" not in names:
            raise DocumentRejected("docx_structure", "Estructura de documento Word inválida.")

        budget = [AppConfig.MAX_DOCX_UNCOMPRESSED_BYTES]
        nodes = 0
        images = 0
        try:
            for info in infos:
                lname = info.filename.lower()
                if lname.startswith(FORBIDDEN_DOCX_PREFIXES) or lname.endswith((".bin", ".exe", ".dll", ".js", ".vbs")):
                    raise DocumentRejected("docx_active_content", "El documento contiene macros, objetos incrustados o contenido activo.")
                if info.is_dir():
                    continue
                data = read_bounded(zf, info, budget)
                if lname.startswith("word/media/"):
                    images += 1
                if not lname.endswith((".xml", ".rels")):
                    continue
                root = parse_xml_safely(data)
                for _ in root.iter():
                    nodes += 1
                    if nodes > AppConfig.MAX_XML_NODES:
                        raise DocumentRejected("xml_too_complex", "El documento excede la complejidad XML permitida.")
                if lname == "[content_types].xml":
                    if b"macroEnabled" in data or b"vbaProject" in data:
                        raise DocumentRejected("docx_active_content", "El documento habilita macros (DOCM).")
                    if DOCX_MAIN_CT.encode() not in data:
                        raise DocumentRejected("docx_structure", "Tipo de contenido principal inválido.")
                if lname.endswith(".rels"):
                    for rel in root.iter(f"{REL_NS}Relationship"):
                        if rel.get("TargetMode") == "External" and not (rel.get("Type") or "").endswith(ALLOWED_EXTERNAL_REL_SUFFIXES):
                            raise DocumentRejected("docx_external_ref", "El documento contiene referencias externas no permitidas.")
                if lname.startswith("word/") and any(m in data for m in FORBIDDEN_DOCX_MARKERS):
                    raise DocumentRejected("docx_active_content", "El documento contiene objetos OLE, controles o contenido incrustado.")
        except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, EOFError):
            raise DocumentRejected("corrupt", "El archivo DOCX está dañado.")

        if images:
            limitations.append(f"El documento contiene {images} imagen(es) que no se analizan ni modifican (firmas, fotos u otro contenido visual).")
    return {"limitations": limitations}


def inspect_pdf(path: str) -> Dict[str, Any]:
    """Validates a PDF: encryption, complexity, active content and oversized images."""
    import pymupdf

    limitations: List[str] = []
    try:
        doc = pymupdf.open(path)
    except Exception:
        raise DocumentRejected("corrupt", "El archivo PDF está dañado o no es válido.")

    try:
        if not doc.is_pdf:
            raise DocumentRejected("unsupported_format", "El archivo no es un PDF válido.")
        if doc.needs_pass or doc.is_encrypted:
            raise DocumentRejected("pdf_encrypted", "El PDF está cifrado o protegido con contraseña.")
        if doc.page_count > AppConfig.MAX_PAGES_LIMIT:
            raise DocumentRejected("too_many_pages", f"El PDF excede el máximo de {AppConfig.MAX_PAGES_LIMIT} páginas.")
        xref_len = doc.xref_length()
        if xref_len > AppConfig.MAX_PDF_OBJECTS:
            raise DocumentRejected("pdf_too_complex", "El PDF excede la cantidad de objetos permitida.")

        for xref in range(1, xref_len):
            try:
                obj = doc.xref_object(xref, compressed=False)
            except Exception:
                raise DocumentRejected("corrupt", "El PDF contiene objetos malformados.")
            if PDF_REJECT_RE.search(obj):
                raise DocumentRejected("pdf_active_content", "El PDF contiene contenido activo (JavaScript, acciones, XFA o multimedia).")

        pixels = 0
        image_count = 0
        for page in doc:
            for img in page.get_images(full=False):
                image_count += 1
                pixels += int(img[2]) * int(img[3])
                if pixels > MAX_IMAGE_PIXELS:
                    raise DocumentRejected("pdf_images_too_large", "El PDF contiene imágenes de dimensiones excesivas.")

        if doc.embfile_count() > 0:
            limitations.append("El PDF contiene archivos adjuntos; serán eliminados del resultado.")
        if doc.is_form_pdf:
            limitations.append("El PDF contiene formularios; sus campos serán eliminados del resultado.")
        if image_count:
            limitations.append(f"El PDF contiene {image_count} imagen(es) cuyo contenido no se analiza (texto en imágenes, firmas, fotos).")
        return {"limitations": limitations, "pages": doc.page_count}
    finally:
        doc.close()


def inspect_document(path: str, fmt: str, compressed_size: int) -> Dict[str, Any]:
    if fmt == "pdf":
        return inspect_pdf(path)
    if fmt == "docx":
        return inspect_docx(path, compressed_size)
    raise DocumentRejected("unsupported_format", "Formato no admitido.")
