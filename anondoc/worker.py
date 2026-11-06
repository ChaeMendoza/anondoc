"""
Isolated document worker. Executed as a separate, resource-limited process:

    python -s -P -m anondoc.worker

Reads one JSON request from stdin and writes one JSON response to stdout.
It never receives the API's environment, and error responses never contain
document content.
"""
import json
import sys
from typing import Any, Dict

from anondoc.domain.entities import AnonymizationStrategy, EntityCategory, PIIEntity
from anondoc.infrastructure.security.inspector import DocumentRejected, inspect_document


def _engine(fmt: str):
    if fmt == "pdf":
        from anondoc.infrastructure.engines.pdf_engine import PDFEngine
        return PDFEngine()
    from anondoc.infrastructure.engines.docx_engine import DOCXEngine
    return DOCXEngine()


def handle(req: Dict[str, Any]) -> Dict[str, Any]:
    op, fmt, path = req["op"], req["fmt"], req["path"]
    info = inspect_document(path, fmt, int(req["size"]))

    if op == "inspect":
        return {"ok": True, **info}
    if op == "extract":
        return {"ok": True, "blocks": _engine(fmt).extract_text_and_blocks(path), **info}
    if op == "anonymize":
        entities = [
            PIIEntity(
                id=e["id"],
                category=EntityCategory(e["category"]),
                original_text=e["original_text"],
                selected=bool(e["selected"]),
            )
            for e in req["entities"]
        ]
        passed, warnings = _engine(fmt).anonymize(
            input_path=path,
            output_path=req["output"],
            entities=entities,
            strategy=AnonymizationStrategy(req["strategy"]),
            pseudonym_map={},
            custom_placeholder=req.get("placeholder"),
        )
        return {"ok": True, "verification_passed": passed, "warnings": info["limitations"] + warnings}
    raise ValueError("unknown operation")


def main() -> int:
    try:
        req = json.loads(sys.stdin.read())
        resp = handle(req)
    except DocumentRejected as exc:
        resp = {"ok": False, "code": exc.code, "message": exc.message}
    except MemoryError:
        resp = {"ok": False, "code": "resource_limit", "message": "El documento excede los recursos permitidos."}
    except Exception:  # noqa: BLE001 - never leak document-derived details
        resp = {"ok": False, "code": "processing_error", "message": "No se pudo procesar el documento."}
    sys.stdout.write(json.dumps(resp))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
