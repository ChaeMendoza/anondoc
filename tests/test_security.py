"""
Security regression tests. Each test exercises the real application code path
(API -> storage -> isolated worker -> engines) using synthetic, fictitious data.
"""
import io
import logging
import os
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import docx
import pymupdf
import pytest

from anondoc.application.job_manager import job_manager
from anondoc.config import AppConfig
from anondoc.infrastructure.detection.pii_detector import HybridPIIDetector
from anondoc.infrastructure.sandbox import runner
from anondoc.infrastructure.sandbox.runner import ServerBusy, WorkerError, run_worker
from anondoc.infrastructure.storage.temp_storage import SecureStorageService
from anondoc.presentation.api.routes import use_cases

from conftest import FAKE_EMAIL, FAKE_ID, auth, make_docx, make_pdf, rewrite_zip, upload, upload_ok

W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def code_of(res):
    return res.json().get("code")


# ------------------------------------------------------------------ 4.1 format validation
def test_wrong_magic_with_pdf_extension_rejected(client):
    res = upload(client, "x.pdf", b"#!/bin/bash\necho hacked", "application/pdf")
    assert res.status_code == 400 and code_of(res) == "unsupported_format"


def test_extension_mismatch_rejected(client):
    res = upload(client, "x.docx", make_pdf(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert res.status_code == 400 and code_of(res) == "extension_mismatch"


def test_client_mime_type_is_ignored(client):
    res = upload(client, "x.docx", make_docx(), "text/html")
    assert res.status_code == 201


@pytest.mark.parametrize("name", ["x.docm", "x.doc", "x.html", "x.svg", "x.zip", "x.exe", "x"])
def test_disallowed_extensions_rejected(client, name):
    assert upload(client, name, make_docx()).status_code == 400


def test_empty_file_rejected(client):
    assert code_of(upload(client, "x.pdf", b"")) == "empty_file"


def test_corrupt_pdf_and_docx_rejected(client):
    assert upload(client, "x.pdf", b"%PDF-1.7\n garbage garbage").status_code in (400, 422)
    assert upload(client, "x.docx", b"PK\x03\x04" + b"\x00" * 50).status_code in (400, 422)


def test_job_dir_removed_when_upload_rejected(client):
    before = set(p.name for p in use_cases.storage.base_dir.iterdir())
    upload(client, "x.pdf", b"%PDF-1.7\n garbage")
    after = set(p.name for p in use_cases.storage.base_dir.iterdir())
    assert before == after


# ------------------------------------------------------------------ 4.2 limits
def test_oversized_file_rejected(client, monkeypatch):
    monkeypatch.setattr(AppConfig, "MAX_FILE_SIZE_BYTES", 100)
    res = upload(client, "x.pdf", make_pdf())
    assert res.status_code == 413


def test_oversized_request_body_rejected_before_parsing(client, monkeypatch):
    monkeypatch.setattr(AppConfig, "MAX_FILE_SIZE_BYTES", 1000)
    res = client.post("/api/v1/documents", content=b"x" * (2 * 1024 * 1024),
                      headers={"Content-Type": "multipart/form-data; boundary=x"})
    assert res.status_code == 413


def test_too_many_pages_rejected(client, monkeypatch):
    monkeypatch.setenv("ANONDOC_MAX_PAGES", "2")
    res = upload(client, "x.pdf", make_pdf(pages=3))
    assert res.status_code == 400 and code_of(res) == "too_many_pages"


def test_too_many_zip_entries_rejected(client, monkeypatch):
    monkeypatch.setenv("ANONDOC_MAX_ZIP_ENTRIES", "5")
    data = rewrite_zip(make_docx(), extra={f"word/media/f{i}.txt": b"a" for i in range(10)})
    assert code_of(upload(client, "x.docx", data)) == "zip_too_many_entries"


# ------------------------------------------------------------------ 5 DOCX / ZIP
def test_zip_bomb_rejected(client):
    bomb = rewrite_zip(make_docx(), extra={"word/media/bomb.bin.txt": b"\x00" * (30 * 1024 * 1024)})
    res = upload(client, "x.docx", bomb)
    assert res.status_code == 400 and code_of(res) == "zip_ratio"


def test_oversized_zip_entry_rejected(client, monkeypatch):
    monkeypatch.setenv("ANONDOC_MAX_ZIP_ENTRY_BYTES", "1024")
    data = rewrite_zip(make_docx(), extra={"word/media/big.txt": b"A" * 4096})
    assert code_of(upload(client, "x.docx", data)) in ("zip_entry_too_large", "zip_ratio")


@pytest.mark.parametrize("name", ["../evil.xml", "word/../../evil.xml", "/etc/passwd", "C:/evil.xml", "word\\evil.xml"])
def test_zip_slip_names_rejected(client, name):
    data = rewrite_zip(make_docx(), extra={name: b"x"})
    assert code_of(upload(client, "x.docx", data)) == "zip_bad_path"


def test_duplicate_zip_entries_rejected(client):
    data = rewrite_zip(make_docx())
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as zin, zipfile.ZipFile(out, "w") as zout:
        for info in zin.infolist():
            zout.writestr(info.filename, zin.read(info))
        with pytest.warns(UserWarning):
            zout.writestr("word/document.xml", b"<w:document/>")
    assert code_of(upload(client, "x.docx", out.getvalue())) == "zip_duplicate_entry"


def test_docx_malformed_xml_rejected(client):
    data = rewrite_zip(make_docx(), replace={"word/document.xml": b"<w:document><unclosed>"})
    assert code_of(upload(client, "x.docx", data)) == "xml_malformed"


def test_docx_xxe_and_dtd_rejected(client):
    xxe = (b'<?xml version="1.0"?><!DOCTYPE d [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
           b'<w:document ' + W_NS.encode() + b'><w:body><w:p><w:r><w:t>&x;</w:t></w:r></w:p></w:body></w:document>')
    res = upload(client, "x.docx", rewrite_zip(make_docx(), replace={"word/document.xml": xxe}))
    assert res.status_code == 400 and code_of(res) == "xml_forbidden"
    assert "root:" not in res.text


def test_docx_billion_laughs_rejected(client):
    bomb = (b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]>'
            b'<w:document ' + W_NS.encode() + b'>&b;</w:document>')
    assert code_of(upload(client, "x.docx", rewrite_zip(make_docx(), replace={"word/document.xml": bomb}))) == "xml_forbidden"


def test_docx_macros_ole_and_external_refs_rejected(client):
    base = make_docx()
    assert code_of(upload(client, "x.docx", rewrite_zip(base, extra={"word/vbaProject.bin": b"x"}))) == "docx_active_content"
    assert code_of(upload(client, "x.docx", rewrite_zip(base, extra={"word/embeddings/oleObject1.bin": b"x"}))) == "docx_active_content"
    docm = zipfile.ZipFile(io.BytesIO(base)).read("[Content_Types].xml").replace(
        b"document.main+xml", b"document.macroEnabled.main+xml")
    assert code_of(upload(client, "x.docx", rewrite_zip(base, replace={"[Content_Types].xml": docm}))) in (
        "docx_active_content", "docx_structure")

    rels = (b'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            b'<Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/attachedTemplate" '
            b'Target="http://127.0.0.1:9/t.dotm" TargetMode="External"/></Relationships>')
    data = rewrite_zip(base, extra={"word/_rels/settings.xml.rels": rels})
    assert code_of(upload(client, "x.docx", data)) == "docx_external_ref"


def test_docx_altchunk_and_objects_rejected(client):
    base = make_docx()
    body = (b'<w:document ' + W_NS.encode() + b'><w:body><w:altChunk r:id="x" '
            b'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></w:body></w:document>')
    assert code_of(upload(client, "x.docx", rewrite_zip(base, replace={"word/document.xml": body}))) == "docx_active_content"


# ------------------------------------------------------------------ 6 PDF
def _pdf_with_catalog_entry(key, value) -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    doc.xref_set_key(doc.pdf_catalog(), key, value)
    data = doc.tobytes()
    doc.close()
    return data


def test_pdf_javascript_rejected(client):
    data = _pdf_with_catalog_entry("OpenAction", "<</S/JavaScript/JS (app.alert\\(1\\))>>")
    res = upload(client, "x.pdf", data)
    assert res.status_code == 400 and code_of(res) == "pdf_active_content"


def test_pdf_obfuscated_javascript_name_rejected(client):
    data = _pdf_with_catalog_entry("OpenAction", "<</S/J#61vaScript/J#53 (app.alert\\(1\\))>>")
    assert code_of(upload(client, "x.pdf", data)) == "pdf_active_content"


def test_pdf_launch_and_xfa_rejected(client):
    assert code_of(upload(client, "x.pdf", _pdf_with_catalog_entry("OpenAction", "<</S/Launch/F (cmd.exe)>>"))) == "pdf_active_content"
    assert code_of(upload(client, "x.pdf", _pdf_with_catalog_entry("AcroForm", "<</XFA [(a) (b)]>>"))) == "pdf_active_content"


def test_encrypted_pdf_rejected(client):
    doc = pymupdf.open()
    doc.new_page()
    data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")
    assert code_of(upload(client, "x.pdf", data)) == "pdf_encrypted"


def test_pdf_attachment_and_metadata_removed_from_output(client):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 100), f"Cédula {FAKE_ID}")
    page.add_text_annot((60, 60), f"nota privada {FAKE_EMAIL}")
    doc.embfile_add("secreto.txt", f"adjunto con {FAKE_EMAIL}".encode())
    doc.set_metadata({"author": FAKE_EMAIL, "title": "Informe de " + FAKE_EMAIL})
    data = doc.tobytes()
    doc.close()

    job_id, h = upload_ok(client, "x.pdf", data)
    analysis = client.post(f"/api/v1/documents/{job_id}/analyze", headers=h).json()
    assert any("adjuntos" in m for m in analysis["limitations"])
    res = client.post(f"/api/v1/documents/{job_id}/anonymize", headers=h, json={"strategy": "REDACTION"})
    assert res.status_code == 200, res.text
    out = client.get(f"/api/v1/documents/{job_id}/download", headers=h).content

    result = pymupdf.open(stream=out, filetype="pdf")
    assert result.embfile_count() == 0
    assert FAKE_EMAIL not in " ".join(str(v) for v in result.metadata.values())
    assert not list(result[0].annots() or [])
    assert FAKE_ID not in result[0].get_text()
    raw = out
    assert FAKE_EMAIL.encode() not in raw and FAKE_ID.encode() not in raw
    result.close()


def test_pdf_value_redacted_on_every_page(client):
    data = make_pdf(pages=3)
    job_id, h = upload_ok(client, "x.pdf", data)
    ents = client.post(f"/api/v1/documents/{job_id}/analyze", headers=h).json()["entities"]
    # Only page-1 detections are submitted, as a user deselecting others would; other pages must still be redacted
    page1 = [e for e in ents if e["page_or_section"] == "1"]
    client.patch(f"/api/v1/documents/{job_id}/detections", headers=h, json={"entities": page1})
    assert client.post(f"/api/v1/documents/{job_id}/anonymize", headers=h, json={}).status_code == 200
    out = pymupdf.open(stream=client.get(f"/api/v1/documents/{job_id}/download", headers=h).content, filetype="pdf")
    assert all(FAKE_ID not in p.get_text() for p in out)


# ------------------------------------------------------------------ 9 API authorization (IDOR/BOLA)
ENDPOINTS = [
    ("post", "/analyze"), ("get", "/analysis"), ("patch", "/detections"),
    ("post", "/anonymize"), ("get", "/download"), ("delete", ""),
]


def _call(client, method, job_id, suffix, headers=None):
    kwargs = {"headers": headers or {}}
    if method == "patch":
        kwargs["json"] = {"entities": []}
    if method == "post" and suffix == "/anonymize":
        kwargs["json"] = {}
    return getattr(client, method)(f"/api/v1/documents/{job_id}{suffix}", **kwargs)


@pytest.mark.parametrize("method,suffix", ENDPOINTS)
def test_job_endpoints_require_the_owners_token(client, method, suffix):
    a_id, a_h = upload_ok(client)
    _, b_h = upload_ok(client)
    assert _call(client, method, a_id, suffix).status_code == 404                      # no token
    assert _call(client, method, a_id, suffix, b_h).status_code == 404                 # another job's token
    assert _call(client, method, a_id, suffix, {"Authorization": "Bearer nope"}).status_code == 404
    assert _call(client, method, a_id, suffix, {"Authorization": "Basic abc"}).status_code == 404
    assert job_manager.get_authorized_job(a_id, a_h["Authorization"][7:]) is not None  # still intact


def test_token_in_query_string_is_not_accepted(client):
    job_id, h = upload_ok(client)
    token = h["Authorization"][7:]
    assert client.get(f"/api/v1/documents/{job_id}/analysis?token={token}").status_code == 404


@pytest.mark.parametrize("bad_id", ["../../etc/passwd", "..%2F..%2Fetc", "a" * 22 + "/..", "%00", "x", "A" * 200])
def test_manipulated_job_ids_are_rejected(client, bad_id):
    for method, suffix in ENDPOINTS:
        assert _call(client, method, bad_id, suffix, {"Authorization": "Bearer x"}).status_code in (404, 405)


def test_unknown_and_unauthorized_are_indistinguishable(client):
    job_id, _ = upload_ok(client)
    unknown = client.get("/api/v1/documents/" + "A" * 22 + "/analysis", headers=auth("x"))
    forbidden = client.get(f"/api/v1/documents/{job_id}/analysis", headers=auth("x"))
    assert unknown.status_code == forbidden.status_code == 404
    assert unknown.json() == forbidden.json()


def test_only_hash_of_token_is_stored(client):
    job_id, h = upload_ok(client)
    token = h["Authorization"][7:]
    job = job_manager.get_authorized_job(job_id, token)
    assert token not in repr(job.__dict__)


def test_job_ids_are_random_and_unique(client):
    ids = {upload_ok(client)[0] for _ in range(3)}
    assert len(ids) == 3 and all(re.fullmatch(r"[A-Za-z0-9_-]{22}", i) for i in ids)


# ------------------------------------------------------------------ 4.3 paths
def test_storage_rejects_traversal_and_foreign_ids(tmp_path):
    storage = SecureStorageService(base_dir=tmp_path)
    for bad in ["../../etc/cron.d", "..", ".", "/etc", "a/b", "short", "A" * 22 + "/../x"]:
        with pytest.raises(ValueError):
            storage.get_job_dir(bad)


def test_malicious_filename_never_reaches_filesystem_or_response(client):
    name = "../../../etc/cron.d/<script>alert(1)</script>.docx"
    res = upload(client, name, make_docx())
    assert res.status_code == 201
    job_id, h = res.json()["job_id"], auth(res.json()["access_token"])
    assert "/" not in res.json()["filename"] and "\\" not in res.json()["filename"]
    files = [p.name for p in use_cases.storage.get_job_dir(job_id).iterdir()]
    assert files == ["original.docx"]
    client.post(f"/api/v1/documents/{job_id}/analyze", headers=h)
    assert client.post(f"/api/v1/documents/{job_id}/anonymize", headers=h, json={}).status_code == 200
    cd = client.get(f"/api/v1/documents/{job_id}/download", headers=h).headers["content-disposition"]
    assert "cron" not in cd and "script" not in cd


def test_download_name_does_not_leak_original_filename(client):
    job_id, h = upload_ok(client, "Juan Perez cedula 1710034065.docx")
    client.post(f"/api/v1/documents/{job_id}/analyze", headers=h)
    client.post(f"/api/v1/documents/{job_id}/anonymize", headers=h, json={})
    cd = client.get(f"/api/v1/documents/{job_id}/download", headers=h).headers["content-disposition"]
    assert "Juan" not in cd and FAKE_ID not in cd


def test_storage_permissions_are_private(client):
    job_id, _ = upload_ok(client)
    d = use_cases.storage.get_job_dir(job_id)
    assert (d.stat().st_mode & 0o077) == 0
    assert ((d / "original.docx").stat().st_mode & 0o077) == 0


def test_api_never_exposes_server_paths(client):
    job_id, h = upload_ok(client)
    texts = [
        client.get("/api/v1/health").text,
        client.post(f"/api/v1/documents/{job_id}/analyze", headers=h).text,
        client.get(f"/api/v1/documents/{job_id}/download", headers=h).text,
        upload(client, "x.pdf", b"%PDF-1.7 junk").text,
    ]
    for t in texts:
        assert str(AppConfig.BASE_TEMP_DIR) not in t and "/home/" not in t and "Traceback" not in t


# ------------------------------------------------------------------ 9 headers / CORS / docs / errors
def test_security_headers_present(client):
    r = client.get("/")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp and "unsafe-eval" not in csp
    assert client.get("/api/v1/health").headers["cache-control"] == "no-store"


def test_cors_is_not_open_by_default(client):
    r = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers
    pre = client.options("/api/v1/documents", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in pre.headers


def test_openapi_and_docs_disabled_by_default(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_validation_errors_do_not_echo_input(client):
    job_id, h = upload_ok(client)
    client.post(f"/api/v1/documents/{job_id}/analyze", headers=h)
    secret = "SECRETO-" + FAKE_ID
    r = client.patch(f"/api/v1/documents/{job_id}/detections", headers=h,
                     json={"entities": [{"category": "NOPE", "original_text": secret}]})
    assert r.status_code == 422 and secret not in r.text


def test_request_limits_on_entities_and_placeholder(client):
    job_id, h = upload_ok(client)
    client.post(f"/api/v1/documents/{job_id}/analyze", headers=h)
    big = {"entities": [{"category": "PERSON", "original_text": "x" * 501}]}
    assert client.patch(f"/api/v1/documents/{job_id}/detections", headers=h, json=big).status_code == 422
    assert client.post(f"/api/v1/documents/{job_id}/anonymize", headers=h,
                       json={"custom_placeholder": "x" * 65}).status_code == 422


def test_upload_rate_limit(client, monkeypatch):
    monkeypatch.setattr(AppConfig, "UPLOAD_RATE_LIMIT", 2)
    codes = [upload(client, "x.pdf", b"nope").status_code for _ in range(4)]
    assert codes[:2] == [400, 400] and codes[2:] == [429, 429]


def test_global_rate_limit(client, monkeypatch):
    monkeypatch.setattr(AppConfig, "RATE_LIMIT_REQUESTS", 3)
    codes = [client.get("/api/v1/health").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]


def test_state_machine_blocks_anonymize_before_analysis_and_download_before_completion(client):
    job_id, h = upload_ok(client)
    assert client.post(f"/api/v1/documents/{job_id}/anonymize", headers=h, json={}).status_code == 409
    assert client.get(f"/api/v1/documents/{job_id}/download", headers=h).status_code == 404


def test_concurrent_operation_on_same_job_is_refused(client):
    job_id, h = upload_ok(client)
    job = job_manager.get_authorized_job(job_id, h["Authorization"][7:])
    assert job_manager.begin_operation(job)
    try:
        assert client.post(f"/api/v1/documents/{job_id}/analyze", headers=h).status_code == 409
    finally:
        job_manager.end_operation(job)


# ------------------------------------------------------------------ 10/11 privacy & result verification
def test_logs_contain_no_document_content_or_tokens(client, caplog):
    caplog.set_level(logging.DEBUG)
    res = upload(client, "Persona Ficticia.docx", make_docx())
    token = res.json()["access_token"]
    job_id, h = res.json()["job_id"], auth(token)
    client.post(f"/api/v1/documents/{job_id}/analyze", headers=h)
    client.post(f"/api/v1/documents/{job_id}/anonymize", headers=h, json={})
    upload(client, "x.pdf", b"%PDF-1.7 junk " + FAKE_EMAIL.encode())
    for secret in (FAKE_ID, FAKE_EMAIL, token, "Persona Ficticia"):
        assert secret not in caplog.text


def _all_zip_text(data: bytes) -> str:
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for n in z.namelist():
            out.append(n)
            out.append(z.read(n).decode("utf-8", "ignore"))
    return "\n".join(out)


def test_docx_no_residual_pii_in_any_part(client):
    d = docx.Document()
    d.core_properties.author = FAKE_EMAIL
    d.core_properties.comments = f"nota {FAKE_ID}"
    d.add_paragraph(f"Cuerpo con {FAKE_ID} y {FAKE_EMAIL}.")
    d.sections[0].header.paragraphs[0].text = f"Encabezado {FAKE_EMAIL}"
    d.sections[0].footer.paragraphs[0].text = f"Pie {FAKE_ID}"
    d.add_comment(d.paragraphs[0].runs, text=f"Comentario {FAKE_EMAIL}", author="Autora Ficticia")
    bio = io.BytesIO()
    d.save(bio)
    data = bio.getvalue()
    # Text box and alt text, which python-docx does not expose as paragraphs
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        doc_xml = z.read("word/document.xml").decode()
    box = (f'<w:p><w:r><mc:AlternateContent xmlns:mc="x"><w:txbxContent><w:p><w:r><w:t>Caja {FAKE_EMAIL}</w:t></w:r></w:p>'
           f'</w:txbxContent></mc:AlternateContent></w:r></w:p><w:p><w:r><w:t descr="alt {FAKE_ID}">x</w:t></w:r></w:p>')
    doc_xml = doc_xml.replace("<w:sectPr", box + "<w:sectPr", 1)
    data = rewrite_zip(data, replace={"word/document.xml": doc_xml.encode()})

    job_id, h = upload_ok(client, "x.docx", data)
    client.post(f"/api/v1/documents/{job_id}/analyze", headers=h)
    r = client.post(f"/api/v1/documents/{job_id}/anonymize", headers=h, json={})
    assert r.status_code == 200, r.text
    out = client.get(f"/api/v1/documents/{job_id}/download", headers=h).content
    text = _all_zip_text(out)
    assert FAKE_ID not in text and FAKE_EMAIL not in text and "Autora Ficticia" not in text
    assert "thumbnail" not in text


def test_failed_verification_is_fail_closed(client, monkeypatch):
    job_id, h = upload_ok(client)
    client.post(f"/api/v1/documents/{job_id}/analyze", headers=h)
    import anondoc.application.use_cases as uc
    original = uc.run_worker

    def leaky(request, cwd):
        resp = original(request, cwd)
        if request["op"] == "anonymize":
            resp["verification_passed"] = False
        return resp

    monkeypatch.setattr(uc, "run_worker", leaky)
    r = client.post(f"/api/v1/documents/{job_id}/anonymize", headers=h, json={})
    assert r.status_code == 422 and r.json()["code"] == "verification_failed"
    assert client.get(f"/api/v1/documents/{job_id}/download", headers=h).status_code == 404
    assert not (use_cases.storage.get_job_dir(job_id) / "anonymized.docx").exists()


def test_verifiers_detect_residual_data(tmp_path):
    from anondoc.domain.entities import EntityCategory, PIIEntity
    from anondoc.infrastructure.engines.docx_engine import DOCXEngine
    from anondoc.infrastructure.engines.pdf_engine import PDFEngine

    p = tmp_path / "a.pdf"
    p.write_bytes(make_pdf())
    ok, warns = PDFEngine.verify_redacted_pdf(str(p), [PIIEntity(category=EntityCategory.ECUADOR_CEDULA, original_text=FAKE_ID)])
    assert ok is False and FAKE_ID not in " ".join(warns)
    d = tmp_path / "a.docx"
    d.write_bytes(make_docx())
    ok, warns = DOCXEngine.verify_redacted_docx(str(d), [FAKE_ID])
    assert ok is False and FAKE_ID not in " ".join(warns)


def test_original_and_entities_removed_after_success(client):
    job_id, h = upload_ok(client)
    client.post(f"/api/v1/documents/{job_id}/analyze", headers=h)
    client.post(f"/api/v1/documents/{job_id}/anonymize", headers=h, json={"strategy": "PSEUDONYMIZATION"})
    files = sorted(p.name for p in use_cases.storage.get_job_dir(job_id).iterdir())
    assert files == ["anonymized.docx"]
    job = job_manager.get_authorized_job(job_id, h["Authorization"][7:])
    assert job.entities == [] and job.pseudonym_map == {}


# ------------------------------------------------------------------ lifecycle / cleanup
def test_delete_removes_files_and_job(client):
    job_id, h = upload_ok(client)
    assert client.delete(f"/api/v1/documents/{job_id}", headers=h).status_code == 204
    assert not use_cases.storage.get_job_dir(job_id).exists()
    assert client.get(f"/api/v1/documents/{job_id}/analysis", headers=h).status_code == 404


def test_expired_jobs_are_purged_from_memory_and_disk(client, monkeypatch):
    job_id, h = upload_ok(client)
    monkeypatch.setattr(AppConfig, "JOB_TTL_SECONDS", -1)
    job_manager.get_authorized_job(job_id, h["Authorization"][7:]).expires_at = None
    from datetime import datetime, timedelta, timezone
    job_manager.get_authorized_job(job_id, h["Authorization"][7:]).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    use_cases.purge_expired()
    assert not use_cases.storage.get_job_dir(job_id).exists()
    assert client.get(f"/api/v1/documents/{job_id}/analysis", headers=h).status_code == 404


def test_startup_purges_orphaned_job_dirs(tmp_path):
    storage = SecureStorageService(base_dir=tmp_path)
    orphan = storage.create_job_dir("A" * 22)
    (orphan / "original.pdf").write_bytes(b"x")
    assert storage.purge_expired_jobs(0) == 1 and not orphan.exists()


def test_job_capacity_limit(client, monkeypatch):
    monkeypatch.setattr(AppConfig, "MAX_ACTIVE_JOBS", job_manager.count_active())
    res = upload(client, "x.docx", make_docx())
    assert res.status_code == 503
    assert [p for p in use_cases.storage.base_dir.iterdir() if p.is_dir()] == [
        p for p in use_cases.storage.base_dir.iterdir() if p.is_dir() and job_manager.get_authorized_job(p.name, "x") is None
    ]


# ------------------------------------------------------------------ 7/8 worker isolation and resource limits
def test_worker_environment_is_scrubbed(monkeypatch, tmp_path):
    monkeypatch.setenv("ANONDOC_SECRET_TEST", "should-not-leak")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "should-not-leak")
    env = runner.build_env(str(tmp_path))
    assert "should-not-leak" not in " ".join(env.values())
    assert set(env) == {"PATH", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "LANG", "HOME", "TMPDIR"}


def test_worker_runs_in_separate_session_with_restricted_cwd_and_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ANONDOC_SECRET_TEST", "should-not-leak")
    code = ("import os,sys,json;print(json.dumps({'cwd':os.getcwd(),'env':dict(os.environ),"
            "'sid':os.getsid(0),'pid':os.getpid(),'ppid_sid':os.getsid(os.getppid())}))")
    proc = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=runner.build_env(str(tmp_path)),
                          preexec_fn=runner._limits(), capture_output=True, text=True)
    import json
    info = json.loads(proc.stdout)
    assert info["cwd"] == str(tmp_path) and "ANONDOC_SECRET_TEST" not in info["env"]
    assert info["sid"] == info["pid"] != info["ppid_sid"]


def test_worker_memory_limit_enforced(monkeypatch, tmp_path):
    monkeypatch.setattr(AppConfig, "WORKER_MEMORY_BYTES", 300 * 1024 * 1024)
    proc = subprocess.run([sys.executable, "-c", "x = bytearray(1024*1024*1024)"], cwd=tmp_path,
                          env=runner.build_env(str(tmp_path)), preexec_fn=runner._limits(), capture_output=True)
    assert proc.returncode != 0 and b"MemoryError" in proc.stderr


def test_worker_cpu_limit_enforced(monkeypatch, tmp_path):
    monkeypatch.setattr(AppConfig, "WORKER_CPU_SECONDS", 1)
    start = time.monotonic()
    proc = subprocess.run([sys.executable, "-c", "while True: pass"], cwd=tmp_path, env=runner.build_env(str(tmp_path)),
                          preexec_fn=runner._limits(), capture_output=True, timeout=20)
    assert proc.returncode != 0 and time.monotonic() - start < 15


def test_worker_timeout_kills_process_group(monkeypatch, tmp_path):
    monkeypatch.setattr(AppConfig, "WORKER_TIMEOUT_SECONDS", 0.05)
    p = tmp_path / "t.pdf"
    p.write_bytes(make_pdf())
    pids = []
    real_popen = subprocess.Popen

    def spy(*a, **k):
        proc = real_popen(*a, **k)
        pids.append(proc.pid)
        return proc

    monkeypatch.setattr(runner.subprocess, "Popen", spy)
    with pytest.raises(WorkerError) as e:
        run_worker({"op": "inspect", "fmt": "pdf", "path": str(p), "size": p.stat().st_size}, cwd=str(tmp_path))
    assert e.value.code == "timeout"
    with pytest.raises(ProcessLookupError):
        os.killpg(pids[0], 0)


def test_concurrency_limit_returns_busy(monkeypatch, tmp_path, client):
    monkeypatch.setattr(runner, "ACQUIRE_TIMEOUT_SECONDS", 0.05)
    slots = [runner._slots.acquire() for _ in range(AppConfig.MAX_CONCURRENT_JOBS)]
    try:
        with pytest.raises(ServerBusy):
            run_worker({"op": "inspect"}, cwd=str(tmp_path))
        assert upload(client, "x.docx", make_docx()).status_code == 503
    finally:
        for _ in slots:
            runner._slots.release()


def test_worker_errors_do_not_leak_document_content(tmp_path):
    p = tmp_path / "x.docx"
    p.write_bytes(rewrite_zip(make_docx(), replace={"word/document.xml": f"<w:document>{FAKE_EMAIL}<".encode()}))
    with pytest.raises(WorkerError) as e:
        run_worker({"op": "inspect", "fmt": "docx", "path": str(p), "size": p.stat().st_size}, cwd=str(tmp_path))
    assert FAKE_EMAIL not in e.value.message


# ------------------------------------------------------------------ detection robustness / frontend
@pytest.mark.parametrize("payload", [
    "a" * 200_000, "1" * 200_000, "a@" * 50_000, ("cuenta " * 30_000), ("fecha de nacimiento " * 10_000),
    ("0" * 12 + ".") * 20_000, "Dr. " + "Ab " * 60_000, " " * 200_000 + "x",
])
def test_detector_is_not_vulnerable_to_regex_dos(payload):
    start = time.monotonic()
    HybridPIIDetector().detect_entities([{"text": payload[: AppConfig.MAX_TEXT_BLOCK_CHARS], "page_or_section": "1"}])
    assert time.monotonic() - start < 10


def test_frontend_has_no_inline_handlers_external_hosts_or_unescaped_attrs():
    web = Path(__file__).resolve().parents[1] / "anondoc/presentation/web"
    html = (web / "templates/index.html").read_text()
    js = (web / "static/app.js").read_text()
    assert "onclick=" not in js and "onclick=" not in html
    assert not re.search(r"<script(?![^>]*src=)[^>]*>", html)
    assert "googleapis" not in html and not re.search(r'(?:src|href)="https?://', html)
    assert '.replace(/"/g, "&quot;")' in js
    assert "Authorization" in js
