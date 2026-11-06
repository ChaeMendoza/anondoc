"""
DOCX Engine: extraction, style-preserving replacement, package sanitization and
residual verification over every XML part of the output.

Runs inside the isolated worker process, never in the API process.
"""
import io
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

import docx
from docx.text.paragraph import Paragraph
from lxml import etree

from anondoc.config import AppConfig
from anondoc.domain.entities import AnonymizationStrategy, PIIEntity
from anondoc.domain.interfaces import IDocumentAnonymizer, IDocumentExtractor
from anondoc.infrastructure.anonymization.anonymizer import AnonymizationStrategyEngine
from anondoc.infrastructure.security.inspector import DocumentRejected, parse_xml_safely, read_bounded

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W15 = "http://schemas.microsoft.com/office/word/2012/wordml"
TEXT_TAGS = (f"{{{W}}}t", f"{{{W}}}delText")
AUTHOR_ATTRS = (f"{{{W}}}author", f"{{{W}}}initials", f"{{{W15}}}author")
XML_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _para_text(p) -> str:
    return "".join(t.text or "" for t in p.iter() if t.tag in TEXT_TAGS)


class DOCXEngine(IDocumentExtractor, IDocumentAnonymizer):
    """Handles extraction and style-preserving anonymization for Word (.docx) files."""

    # ------------------------------------------------------------------ extraction
    def extract_text_and_blocks(self, file_path: str) -> List[Dict[str, Any]]:
        doc = docx.Document(file_path)
        blocks: List[Dict[str, Any]] = []
        limit = AppConfig.MAX_TEXT_BLOCK_CHARS

        def add(text: str, label: str, meta: Dict[str, Any]):
            text = text.strip()[:limit]
            if text:
                blocks.append({"text": text, "page_or_section": label, "metadata": meta})

        for s_idx, section in enumerate(doc.sections):
            add(" ".join(p.text.strip() for p in section.header.paragraphs if p.text.strip()),
                f"Encabezado Sección {s_idx + 1}", {"type": "header", "section": s_idx})
            add(" ".join(p.text.strip() for p in section.footer.paragraphs if p.text.strip()),
                f"Pie de Página Sección {s_idx + 1}", {"type": "footer", "section": s_idx})

        for p_idx, p in enumerate(doc.paragraphs):
            add(p.text, f"Párrafo {p_idx + 1}", {"type": "paragraph", "index": p_idx})

        for t_idx, table in enumerate(doc.tables):
            for r_idx, row in enumerate(table.rows):
                for c_idx, cell in enumerate(row.cells):
                    for cp in cell.paragraphs:
                        add(cp.text, f"Tabla {t_idx + 1} (Fila {r_idx + 1}, Col {c_idx + 1})",
                            {"type": "table_cell", "table_index": t_idx, "row": r_idx, "col": c_idx})

        # Footnotes, endnotes, comments and text boxes
        extra_idx = 0
        for label, text in self._extra_texts(file_path):
            extra_idx += 1
            add(text, f"{label} {extra_idx}", {"type": "extra"})
        return blocks

    @staticmethod
    def _extra_texts(file_path: str) -> Iterator[Tuple[str, str]]:
        budget = [AppConfig.MAX_DOCX_UNCOMPRESSED_BYTES]
        with zipfile.ZipFile(file_path) as zf:
            for info in zf.infolist():
                name = info.filename
                if name == "word/document.xml":
                    root = parse_xml_safely(read_bounded(zf, info, budget))
                    for tx in root.iter(f"{{{W}}}txbxContent"):
                        for p in tx.iter(f"{{{W}}}p"):
                            yield "Cuadro de texto", _para_text(p)
                elif re.match(r"^word/(footnotes|endnotes|comments)\.xml$", name):
                    root = parse_xml_safely(read_bounded(zf, info, budget))
                    label = {"footnotes": "Nota al pie", "endnotes": "Nota final", "comments": "Comentario"}[
                        name.split("/")[1].split(".")[0]]
                    for p in root.iter(f"{{{W}}}p"):
                        yield label, _para_text(p)

    # ------------------------------------------------------------------ anonymization
    def anonymize(
        self,
        input_path: str,
        output_path: str,
        entities: List[PIIEntity],
        strategy: AnonymizationStrategy,
        pseudonym_map: Dict[str, str],
        custom_placeholder: str = None,
    ) -> Tuple[bool, List[str]]:
        warnings: List[str] = []
        doc = docx.Document(input_path)
        category_counters: Dict[str, int] = {}
        selected = [e for e in entities if e.selected and e.original_text.strip()]

        rep_map: Dict[str, str] = {}
        for entity in selected:
            orig = entity.original_text.strip()
            if orig not in rep_map:
                rep_map[orig] = AnonymizationStrategyEngine.generate_replacement(
                    entity=entity,
                    strategy=strategy,
                    pseudonym_map=pseudonym_map,
                    category_counters=category_counters,
                    custom_placeholder=custom_placeholder,
                )

        # Longest first to avoid partial-prefix replacements
        sorted_targets = sorted(rep_map.keys(), key=len, reverse=True)

        def replace_in_paragraph(p: Paragraph):
            for target in sorted_targets:
                if target in p.text:
                    self._replace_text_in_runs(p, target, rep_map[target])

        for section in doc.sections:
            for p in section.header.paragraphs:
                replace_in_paragraph(p)
            for p in section.footer.paragraphs:
                replace_in_paragraph(p)
        for p in doc.paragraphs:
            replace_in_paragraph(p)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        replace_in_paragraph(p)

        core = doc.core_properties
        core.author = "AnonDoc Privacy Engine"
        core.last_modified_by = "AnonDoc Privacy Engine"
        core.comments = ""
        core.category = ""
        core.keywords = ""
        core.title = "Documento Anonimizado"
        core.subject = ""

        buf = io.BytesIO()
        doc.save(buf)

        out_file = Path(output_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)
        self._sanitize_package(buf.getvalue(), str(out_file), rep_map, sorted_targets)

        passed, residual = self.verify_redacted_docx(str(out_file), sorted_targets)
        warnings.extend(residual)
        return passed, warnings

    @staticmethod
    def _replace_text_in_runs(p: Paragraph, target: str, replacement: str):
        """Replaces in a single run when possible; otherwise rewrites the paragraph keeping the first style."""
        for run in p.runs:
            if target in run.text:
                run.text = run.text.replace(target, replacement)
                return

        if target in p.text:
            font_name = font_size = is_bold = is_italic = color = None
            for run in p.runs:
                if run.font.name:
                    font_name = run.font.name
                if run.font.size:
                    font_size = run.font.size
                if run.bold is not None:
                    is_bold = run.bold
                if run.italic is not None:
                    is_italic = run.italic
                if run.font.color and run.font.color.rgb:
                    color = run.font.color.rgb
                if font_name:
                    break

            new_full_text = p.text.replace(target, replacement)
            p.text = ""
            new_run = p.add_run(new_full_text)
            if font_name:
                new_run.font.name = font_name
            if font_size:
                new_run.font.size = font_size
            if is_bold is not None:
                new_run.bold = is_bold
            if is_italic is not None:
                new_run.italic = is_italic
            if color:
                new_run.font.color.rgb = color

    @staticmethod
    def _sanitize_package(data: bytes, out_path: str, rep_map: Dict[str, str], sorted_targets: List[str]) -> None:
        """
        Second pass over every XML part: replaces residual occurrences (text boxes, notes,
        deleted text, alt text), anonymizes comment/revision authors and drops thumbnails,
        custom properties and company/manager fields.
        """
        def replace_str(s: str) -> str:
            for t in sorted_targets:
                if t in s:
                    s = s.replace(t, rep_map[t])
            return s

        with zipfile.ZipFile(io.BytesIO(data)) as zin, zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                name = info.filename
                lname = name.lower()
                if lname.startswith("docproperties/thumbnail") or lname.startswith("docprops/thumbnail"):
                    continue
                payload = zin.read(info)

                if lname.endswith((".xml", ".rels")) and lname != "[content_types].xml":
                    root = etree.fromstring(payload, XML_PARSER)

                    if lname == "_rels/.rels":
                        for rel in list(root):
                            if (rel.get("Type") or "").endswith("/thumbnail"):
                                root.remove(rel)
                    elif lname == "docprops/custom.xml":
                        for child in list(root):
                            root.remove(child)
                    elif lname == "docprops/app.xml":
                        for el in root.iter():
                            if isinstance(el.tag, str) and etree.QName(el).localname in ("Company", "Manager"):
                                el.text = ""

                    for el in root.iter():
                        if not isinstance(el.tag, str):
                            continue
                        for attr, val in list(el.attrib.items()):
                            if attr in AUTHOR_ATTRS:
                                el.set(attr, "Anon")
                            elif any(t in val for t in sorted_targets):
                                el.set(attr, replace_str(val))
                        if el.tag in TEXT_TAGS and el.text and any(t in el.text for t in sorted_targets):
                            el.text = replace_str(el.text)

                    if lname.startswith("word/"):
                        for p in root.iter(f"{{{W}}}p"):
                            runs = list(p.iter(f"{{{W}}}t"))
                            joined = "".join(t.text or "" for t in runs)
                            if runs and any(t in joined for t in sorted_targets):
                                new = replace_str(joined)
                                runs[0].text = new
                                runs[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                                for t in runs[1:]:
                                    t.text = ""
                    payload = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)

                zout.writestr(name, payload)

    # ------------------------------------------------------------------ verification
    @staticmethod
    def _output_fragments(docx_path: str) -> Iterator[str]:
        budget = [AppConfig.MAX_DOCX_UNCOMPRESSED_BYTES]
        with zipfile.ZipFile(docx_path) as zf:
            for info in zf.infolist():
                lname = info.filename.lower()
                if info.is_dir():
                    continue
                if lname.startswith("docprops/thumbnail"):
                    yield "<thumbnail-present>"
                    continue
                if not lname.endswith((".xml", ".rels")):
                    continue
                root = parse_xml_safely(read_bounded(zf, info, budget))
                for p in root.iter(f"{{{W}}}p"):
                    yield _para_text(p)
                for el in root.iter():
                    if not isinstance(el.tag, str):
                        continue
                    yield from el.attrib.values()
                    if el.text and el.tag not in TEXT_TAGS:
                        yield el.text

    @staticmethod
    def verify_redacted_docx(docx_path: str, targets: List[str]) -> Tuple[bool, List[str]]:
        """Scans every XML part (body, headers, notes, comments, props, alt text, attributes) for leftovers."""
        warnings: List[str] = []
        passed = True
        try:
            haystack = _norm(" | ".join(DOCXEngine._output_fragments(docx_path)))
        except DocumentRejected:
            return False, ["Falla de verificación: no se pudo inspeccionar el documento resultante."]

        if "<thumbnail-present>" in haystack:
            passed = False
            warnings.append("Falla de verificación: el resultado contiene una miniatura del documento original.")

        leaked = 0
        for target in targets:
            clean = _norm(target)
            if clean and clean in haystack:
                leaked += 1
        if leaked:
            passed = False
            warnings.append(f"Falla de verificación: {leaked} valor(es) seleccionado(s) aún están presentes en el documento.")
        return passed, warnings
