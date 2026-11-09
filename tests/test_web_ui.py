"""
Web UI support tests: published limits, partial-analysis signalling end to end,
detector wiring, log hygiene and static frontend safety. Synthetic data only.
"""
import logging
import re
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from anondoc.config import AppConfig
from anondoc.domain.entities import EntityCategory
from anondoc.infrastructure.detection import factory
from anondoc.infrastructure.detection.composite_detector import CompositePIIDetector
from anondoc.infrastructure.detection.gliner_detector import GLiNERBusyError
from anondoc.infrastructure.detection.pii_detector import HybridPIIDetector
from anondoc.presentation.api.routes import use_cases

from conftest import FAKE_EMAIL, FAKE_ID, upload_ok

WEB_DIR = Path(__file__).resolve().parent.parent / "anondoc" / "presentation" / "web"
BLOCKS = [{"text": f"Correo {FAKE_EMAIL}", "page_or_section": "1"}]


def _semantic(side_effect=None, ready=True):
    sem = MagicMock()
    sem.is_ready = ready
    sem.detect_entities.side_effect = side_effect
    if side_effect is None:
        sem.detect_entities.return_value = []
    return sem


@pytest.fixture
def swap_detector():
    original = use_cases.detector

    def _swap(detector):
        use_cases.detector = detector

    yield _swap
    use_cases.detector = original


# ---------------------------------------------------------------- health / limits
def test_health_publishes_upload_limits(client):
    body = client.get("/api/v1/health").json()
    assert body["max_file_size_bytes"] == AppConfig.MAX_FILE_SIZE_BYTES
    assert body["allowed_extensions"] == sorted(AppConfig.ALLOWED_EXTENSIONS)
    assert body["semantic_engine_enabled"] is AppConfig.ENABLE_GLINER


# ---------------------------------------------------------------- partial reasons
@pytest.mark.parametrize(
    "semantic,reason",
    [
        (None, "unavailable"),
        (_semantic(ready=False), "unavailable"),
        (_semantic(GLiNERBusyError("busy")), "busy"),
        (_semantic(TimeoutError("slow")), "failed"),
        (_semantic(RuntimeError("boom")), "failed"),
    ],
)
def test_composite_reports_partial_reason(semantic, reason):
    comp = CompositePIIDetector(semantic_detector=semantic)
    ents = comp.detect_entities(BLOCKS)
    assert any(e.category == EntityCategory.EMAIL for e in ents)  # deterministic layer kept
    assert comp.last_analysis_was_partial is True
    assert comp.last_partial_reason == reason


def test_composite_complete_analysis_has_no_reason():
    comp = CompositePIIDetector(semantic_detector=_semantic())
    comp.detect_entities(BLOCKS)
    assert comp.last_analysis_was_partial is False
    assert comp.last_partial_reason is None


def test_composite_partial_state_is_per_thread():
    comp = CompositePIIDetector(semantic_detector=_semantic(GLiNERBusyError("busy")))
    seen = {}

    def worker():
        seen["before"] = comp.last_analysis_was_partial
        comp.detect_entities(BLOCKS)
        seen["after"] = comp.last_analysis_was_partial

    comp.detect_entities(BLOCKS)
    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert seen == {"before": False, "after": True}
    assert comp.last_analysis_was_partial is True


# ---------------------------------------------------------------- end to end
def test_default_flow_is_not_partial(client):
    job_id, h = upload_ok(client)
    analysis = client.post(f"/api/v1/documents/{job_id}/analyze", headers=h).json()
    assert analysis["analysis_partial"] is False
    assert analysis["partial_reason"] is None
    res = client.post(f"/api/v1/documents/{job_id}/anonymize", headers=h, json={"strategy": "REDACTION"})
    assert res.status_code == 200
    assert res.json()["analysis_partial"] is False


@pytest.mark.parametrize("exc,reason", [(GLiNERBusyError("busy"), "busy"), (TimeoutError("slow"), "failed")])
def test_partial_analysis_is_flagged_through_api(client, swap_detector, exc, reason):
    swap_detector(CompositePIIDetector(semantic_detector=_semantic(exc)))
    job_id, h = upload_ok(client)

    analysis = client.post(f"/api/v1/documents/{job_id}/analyze", headers=h).json()
    assert analysis["analysis_partial"] is True
    assert analysis["partial_reason"] == reason
    assert any(l.startswith("ANÁLISIS PARCIAL") for l in analysis["limitations"])
    assert analysis["total_entities"] > 0  # deterministic findings are still delivered

    again = client.get(f"/api/v1/documents/{job_id}/analysis", headers=h).json()
    assert again["analysis_partial"] is True

    res = client.post(f"/api/v1/documents/{job_id}/anonymize", headers=h, json={"strategy": "REDACTION"}).json()
    assert res["analysis_partial"] is True
    assert res["partial_reason"] == reason
    assert client.get(res["download_url"], headers=h).status_code == 200


def test_reanalysis_clears_partial_flag(client, swap_detector):
    comp = CompositePIIDetector(semantic_detector=_semantic(GLiNERBusyError("busy")))
    swap_detector(comp)
    job_id, h = upload_ok(client)
    assert client.post(f"/api/v1/documents/{job_id}/analyze", headers=h).json()["analysis_partial"] is True

    comp.semantic_detector.detect_entities.side_effect = None
    comp.semantic_detector.detect_entities.return_value = []
    retry = client.post(f"/api/v1/documents/{job_id}/analyze", headers=h).json()
    assert retry["analysis_partial"] is False
    assert not any(l.startswith("ANÁLISIS PARCIAL") for l in retry["limitations"])


def test_download_unavailable_before_completion(client):
    job_id, h = upload_ok(client)
    client.post(f"/api/v1/documents/{job_id}/analyze", headers=h)
    assert client.get(f"/api/v1/documents/{job_id}/download", headers=h).status_code == 404


def test_validation_errors_are_user_readable(client):
    files = {"file": ("nota.txt", b"hola", "text/plain")}
    r = client.post("/api/v1/documents", files=files)
    assert r.status_code == 400
    body = r.json()
    assert isinstance(body["detail"], str) and "/" not in body["detail"] and "Traceback" not in r.text
    empty = client.post("/api/v1/documents", files={"file": ("a.pdf", b"", "application/pdf")})
    assert empty.status_code == 400


def test_document_content_never_reaches_logs(client, caplog, swap_detector):
    swap_detector(CompositePIIDetector(semantic_detector=_semantic(GLiNERBusyError("busy"))))
    caplog.set_level(logging.DEBUG)
    job_id, h = upload_ok(client)
    client.post(f"/api/v1/documents/{job_id}/analyze", headers=h)
    client.post(f"/api/v1/documents/{job_id}/anonymize", headers=h, json={"strategy": "REDACTION"})
    assert FAKE_ID not in caplog.text and FAKE_EMAIL not in caplog.text


# ---------------------------------------------------------------- detector wiring
def test_factory_defaults_to_deterministic(monkeypatch):
    monkeypatch.setattr(AppConfig, "ENABLE_GLINER", False)
    assert isinstance(factory.build_detector(), HybridPIIDetector)


def test_factory_builds_hybrid_when_enabled(monkeypatch):
    monkeypatch.setattr(AppConfig, "ENABLE_GLINER", True)
    stub = _semantic()
    monkeypatch.setattr(factory, "GLiNERDetector", lambda: stub)
    det = factory.build_detector()
    assert isinstance(det, CompositePIIDetector)
    assert det.semantic_detector is stub


# ---------------------------------------------------------------- static frontend
def test_frontend_renders_document_text_safely():
    js = (WEB_DIR / "static" / "app.js").read_text(encoding="utf-8")
    assert "escapeHtml" not in js and "alert(" not in js
    # innerHTML may only receive constant strings, never interpolated data.
    for line in js.splitlines():
        if "innerHTML" in line:
            assert "${" not in line and "+" not in line


def test_frontend_states_real_limitations():
    html = (WEB_DIR / "templates" / "index.html").read_text(encoding="utf-8")
    assert "OCR" in html and "falsos positivos" in html and "parcial" in html
    assert not re.search(r"https?://(?!localhost)", html)  # no external resources
