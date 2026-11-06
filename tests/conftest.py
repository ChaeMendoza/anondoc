"""Shared fixtures and synthetic-document builders. All content is fictitious test data."""
import io
import zipfile

import docx
import pymupdf
import pytest
from fastapi.testclient import TestClient

from anondoc.main import app
from anondoc.presentation.api.middleware import limiter

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
FAKE_ID = "1710034065"          # valid-checksum test cédula
FAKE_EMAIL = "persona.ficticia@ejemplo.test"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._hits.clear()
    yield
    limiter._hits.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def make_docx(text: str = f"Cédula {FAKE_ID} correo {FAKE_EMAIL}") -> bytes:
    d = docx.Document()
    d.core_properties.author = "Autor Ficticio"
    d.add_paragraph(text)
    bio = io.BytesIO()
    d.save(bio)
    return bio.getvalue()


def make_pdf(text: str = f"Cédula {FAKE_ID} correo {FAKE_EMAIL}", pages: int = 1) -> bytes:
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page().insert_text((50, 100), text)
    data = doc.tobytes()
    doc.close()
    return data


def rewrite_zip(data: bytes, extra=None, replace=None, drop=()) -> bytes:
    """Returns a copy of a zip with entries added/replaced/removed (for building hostile fixtures)."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            if info.filename in drop:
                continue
            payload = (replace or {}).get(info.filename, zin.read(info))
            zout.writestr(info.filename, payload)
        for name, payload in (extra or {}).items():
            zout.writestr(name, payload)
    return out.getvalue()


def upload(client, name, data, mime="application/octet-stream"):
    return client.post("/api/v1/documents", files={"file": (name, data, mime)})


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def upload_ok(client, name="doc.docx", data=None):
    data = data if data is not None else make_docx()
    res = upload(client, name, data)
    assert res.status_code == 201, res.text
    body = res.json()
    return body["job_id"], auth(body["access_token"])
