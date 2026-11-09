"""
Phase 1 Technical Audit & Reconciliation Test Suite.
Verifies:
1. Benchmark mathematical reconciliation & invariant assertions.
2. Credit card validation (Visa 13/16, Mastercard 16, Amex 15, Luhn validation).
3. Phone vs protected categories disambiguation.
4. Protected categories preservation against semantic overrides.
5. GLiNER multi-threaded concurrency.
6. Timeout handling, fallback, and partial analysis job notification.
"""
import concurrent.futures
import time
import pytest
from unittest.mock import MagicMock

from anondoc.domain.entities import (
    DetectionConfidence,
    EntityCategory,
    PIIEntity,
    DocumentJob,
    DocumentFormat,
    JobStatus,
)
from anondoc.domain.validators import PIIValidators
from anondoc.infrastructure.detection.composite_detector import (
    CompositePIIDetector,
    HARD_DETERMINISTIC_CATEGORIES,
)
from anondoc.infrastructure.detection.gliner_detector import GLiNERDetector, GLiNERBusyError
from anondoc.infrastructure.detection.pii_detector import HybridPIIDetector
from tests.benchmark.run_benchmark import validate_benchmark_integrity


# =====================================================================
# 1. Benchmark Mathematical Integrity Tests
# =====================================================================

def test_benchmark_integrity_assertion_valid():
    """Valid benchmark results dictionary must pass integrity assertions without error."""
    valid_results = {
        "summary": {
            "documents_count": 2,
            "total_words": 100,
            "total_ground_truth": 5,
            "total_predictions": 6,
            "total_tp": 4,
            "total_fp": 2,
            "total_fn": 1,
            "precision": 0.6667,
            "recall": 0.8,
            "f1_score": 0.7273,
            "fp_per_1000_words": 20.0,
            "latency_total_ms": 10.0,
            "latency_avg_per_doc_ms": 5.0,
            "mem_rss_mb": 100.0,
            "mem_delta_mb": 0.0,
        },
        "by_category": {
            "PERSON": {
                "gt_count": 3,
                "pred_count": 4,
                "tp": 2,
                "fp": 2,
                "fn": 1,
                "precision": 0.5,
                "recall": 0.6667,
                "f1": 0.5714,
            },
            "EMAIL": {
                "gt_count": 2,
                "pred_count": 2,
                "tp": 2,
                "fp": 0,
                "fn": 0,
                "precision": 1.0,
                "recall": 1.0,
                "f1": 1.0,
            },
        },
        "false_positives": [{"dummy": 1}, {"dummy": 2}],
        "false_negatives": [{"dummy": 1}],
    }
    validate_benchmark_integrity(valid_results)


def test_benchmark_integrity_fails_on_category_sum_discrepancy():
    """Integrity check must fail if sum of category TP does not match global TP."""
    bad_results = {
        "summary": {
            "total_ground_truth": 5,
            "total_predictions": 6,
            "total_tp": 4,  # global is 4
            "total_fp": 2,
            "total_fn": 1,
            "precision": 0.6667,
            "recall": 0.8,
        },
        "by_category": {
            "PERSON": {
                "gt_count": 3,
                "pred_count": 3,
                "tp": 1,  # sum of TP is 1 + 2 = 3 != 4
                "fp": 2,
                "fn": 2,
                "precision": 0.3333,
                "recall": 0.3333,
            },
            "EMAIL": {
                "gt_count": 2,
                "pred_count": 2,
                "tp": 2,
                "fp": 0,
                "fn": 0,
                "precision": 1.0,
                "recall": 1.0,
            },
        },
        "false_positives": [{"dummy": 1}, {"dummy": 2}],
        "false_negatives": [{"dummy": 1}],
    }
    with pytest.raises(AssertionError, match="sum of category TP"):
        validate_benchmark_integrity(bad_results)


def test_benchmark_integrity_fails_on_unaccounted_ground_truth():
    """Integrity check must fail if total_ground_truth != total_tp + total_fn."""
    bad_results = {
        "summary": {
            "total_ground_truth": 10,
            "total_predictions": 4,
            "total_tp": 4,
            "total_fp": 0,
            "total_fn": 5,  # 4 + 5 = 9 != 10
            "precision": 1.0,
            "recall": 0.4444,
        },
        "by_category": {
            "EMAIL": {
                "gt_count": 10,
                "pred_count": 4,
                "tp": 4,
                "fp": 0,
                "fn": 5,
                "precision": 1.0,
                "recall": 0.4444,
            }
        },
        "false_positives": [],
        "false_negatives": [{} for _ in range(5)],
    }
    with pytest.raises(AssertionError, match="global GT"):
        validate_benchmark_integrity(bad_results)


# =====================================================================
# 2. Credit Card Validation & Luhn Algorithm Tests
# =====================================================================

def test_credit_card_valid_cards_all_brands():
    """Tests Visa 16, Visa 13, Mastercard 16, and Amex 15 with valid Luhn checksums."""
    detector = HybridPIIDetector()

    # Visa 16 digits
    v16_text = "Pago con tarjeta Visa: 4532015112830341 aprobada."
    res_v16 = detector.detect_entities([{"text": v16_text, "page_or_section": "1"}])
    cards_v16 = [e for e in res_v16 if e.category == EntityCategory.CREDIT_CARD]
    assert len(cards_v16) == 1
    assert cards_v16[0].original_text == "4532015112830341"
    assert cards_v16[0].confidence == DetectionConfidence.HIGH

    # Visa 13 digits
    v13_text = "Pago con tarjeta antigua Visa 13: 4012888888881 confirmada."
    res_v13 = detector.detect_entities([{"text": v13_text, "page_or_section": "1"}])
    cards_v13 = [e for e in res_v13 if e.category == EntityCategory.CREDIT_CARD]
    assert len(cards_v13) == 1
    assert cards_v13[0].original_text == "4012888888881"
    assert cards_v13[0].confidence == DetectionConfidence.HIGH

    # Mastercard 16 digits
    mc_text = "Mastercard débito: 5412751234123452 registrada."
    res_mc = detector.detect_entities([{"text": mc_text, "page_or_section": "1"}])
    cards_mc = [e for e in res_mc if e.category == EntityCategory.CREDIT_CARD]
    assert len(cards_mc) == 1
    assert cards_mc[0].original_text == "5412751234123452"
    assert cards_mc[0].confidence == DetectionConfidence.HIGH

    # American Express 15 digits
    amex_text = "American Express corporativa: 378282246310005 autorizada."
    res_amex = detector.detect_entities([{"text": amex_text, "page_or_section": "1"}])
    cards_amex = [e for e in res_amex if e.category == EntityCategory.CREDIT_CARD]
    assert len(cards_amex) == 1
    assert cards_amex[0].original_text == "378282246310005"
    assert cards_amex[0].confidence == DetectionConfidence.HIGH


def test_credit_card_luhn_failure_rejected():
    """Card numbers with incorrect Luhn checksum must be rejected and not labeled CREDIT_CARD."""
    detector = HybridPIIDetector()
    bad_luhn_text = "Tarjeta rechazada: 4532015112830342 por error de checksum."
    res = detector.detect_entities([{"text": bad_luhn_text, "page_or_section": "1"}])
    cards = [e for e in res if e.category == EntityCategory.CREDIT_CARD]
    assert len(cards) == 0


def test_credit_card_invalid_length_explanation():
    """
    Explains the baseline 0 detection on doc_10:
    The 15-digit number '453201511283034' starts with 4 (Visa), which requires 13 or 16 digits.
    Although it mathematically passes the generic Luhn formula, CREDIT_CARD_REGEX strictly
    enforces ISO/IEC 7812 IIN rules (4 requires 13 or 16 digits; 15 digits is Amex 34/37).
    Therefore, CREDIT_CARD_REGEX does not match it, and the detector rejects it as a CREDIT_CARD.
    """
    from anondoc.infrastructure.detection.patterns import DetectionPatterns
    # 1. Regex rejects it because 15-digit card starting with 4 is not a valid Visa length
    assert DetectionPatterns.CREDIT_CARD_REGEX.search("453201511283034") is None

    # 2. HybridPIIDetector does NOT classify it as CREDIT_CARD
    detector = HybridPIIDetector()
    doc10_snippet = "Tarjeta de pago asignada: 453201511283034."
    res = detector.detect_entities([{"text": doc10_snippet, "page_or_section": "1"}])
    cards = [e for e in res if e.category == EntityCategory.CREDIT_CARD]
    assert len(cards) == 0, "15-digit card starting with 4 is not a valid Visa card"


# =====================================================================
# 3. Disambiguation & Protected Categories
# =====================================================================

def test_phone_disambiguation_with_protected_numbers():
    """
    CompositePIIDetector Rule 2:
    Suppresses greedy phone regex matches that collide with valid credit cards,
    bank accounts, cédulas, or RUCs.
    """
    comp = CompositePIIDetector(deterministic_detector=HybridPIIDetector())
    text = (
        "Teléfono personal: 0998765432. "
        "Tarjeta: 4532015112830341. "
        "Cédula: 1710034065. "
        "Cuenta corriente: 3456789012."
    )
    entities = comp.detect_entities([{"text": text, "page_or_section": "1"}])

    phones = [e for e in entities if e.category == EntityCategory.PHONE]
    cards = [e for e in entities if e.category == EntityCategory.CREDIT_CARD]
    cedulas = [e for e in entities if e.category == EntityCategory.ECUADOR_CEDULA]
    accounts = [e for e in entities if e.category == EntityCategory.BANK_ACCOUNT]

    # Exactly one phone (the legitimate one)
    assert len(phones) == 1
    assert phones[0].original_text == "0998765432"

    # Card, cédula, and account preserved with high confidence
    assert len(cards) == 1
    assert cards[0].original_text == "4532015112830341"
    assert cards[0].confidence == DetectionConfidence.HIGH

    assert len(cedulas) == 1
    assert cedulas[0].original_text == "1710034065"
    assert cedulas[0].confidence == DetectionConfidence.HIGH

    assert len(accounts) == 1
    assert accounts[0].original_text == "3456789012"


def test_protected_categories_are_not_overwritten_by_semantic_labels():
    """
    CompositePIIDetector Rule 3 & 5:
    Authoritative hard deterministic categories (CEDULA, RUC, CARD, EMAIL, IP, PASSPORT, BANK_ACCOUNT)
    cannot be overwritten or discarded by a conflicting semantic prediction.
    """
    det_mock = MagicMock()
    # Layer 1 detects a verified Ecuadorian Cédula
    det_mock.detect_entities.return_value = [
        PIIEntity(
            id="ced-1",
            category=EntityCategory.ECUADOR_CEDULA,
            original_text="1710034065",
            start_char=10,
            end_char=20,
            confidence=DetectionConfidence.HIGH,
            context="cédula 1710034065",
            page_or_section="1",
            selected=True,
            is_manual=False,
            validation_details="Cédula ecuatoriana válida",
        )
    ]

    sem_mock = MagicMock()
    # Semantic layer mispredicts the same span as a PHONE or FINANCIAL_DATA
    sem_mock.detect_entities.return_value = [
        PIIEntity(
            id="sem-1",
            category=EntityCategory.FINANCIAL_DATA,
            original_text="1710034065",
            start_char=10,
            end_char=20,
            confidence=DetectionConfidence.HIGH,
            context="cédula 1710034065",
            page_or_section="1",
            selected=True,
            is_manual=False,
            validation_details="GLiNER bi-encoder span",
        )
    ]

    comp = CompositePIIDetector(
        deterministic_detector=det_mock,
        semantic_detector=sem_mock,
    )
    result = comp.detect_entities([{"text": "dummy text block", "page_or_section": "1"}])

    assert len(result) == 1
    assert result[0].category == EntityCategory.ECUADOR_CEDULA
    assert result[0].original_text == "1710034065"


# =====================================================================
# 4. Bounded Admission Control, Concurrency, Timeout & Fallback Tests
# =====================================================================

def test_gliner_simultaneous_requests_rejected_without_queuing():
    """
    Requirements 1 & 2:
    - Permits at most one active or pending inference per instance.
    - Rejects concurrent requests immediately with GLiNERBusyError without queuing.
    - Thread count in executor never exceeds 1.
    """
    gliner = GLiNERDetector(threshold=0.45)
    if not gliner.is_ready:
        pytest.skip("GLiNER model not available in current environment")

    # Simulate an active inference running for 0.25s
    def slow_predict(*args, **kwargs):
        time.sleep(0.25)
        return [{"label": "persona", "start": 0, "end": 14, "text": "Carlos Mendoza", "score": 0.95}]

    gliner._model.predict_entities = slow_predict

    results = []
    busy_errors = []

    def call_detector(caller_id: int):
        try:
            ents = gliner.detect_entities([{"text": "Carlos Mendoza", "page_or_section": "1"}])
            results.append((caller_id, len(ents)))
        except GLiNERBusyError:
            busy_errors.append(caller_id)

    # Launch 5 simultaneous requests from concurrent threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(call_detector, i) for i in range(5)]
        concurrent.futures.wait(futures)

    # Exactly 1 active inference admitted; the other 4 rejected without queueing
    assert len(results) == 1, f"Expected exactly 1 admitted inference, got {len(results)}"
    assert len(busy_errors) == 4, f"Expected 4 rejected requests, got {len(busy_errors)}"

    # Thread count strictly bounded to at most 1 worker
    assert len(gliner._executor._threads) <= 1
    gliner.close()


def test_gliner_timeout_during_active_inference_holds_admission():
    """
    Requirements 3 & 4:
    - When caller times out on an active inference, admission control is HELD
      until the background worker actually finishes execution.
    - An immediate subsequent request is rejected with GLiNERBusyError without queueing.
    """
    gliner = GLiNERDetector(threshold=0.45, inference_timeout_seconds=0.03)
    if not gliner.is_ready:
        pytest.skip("GLiNER model not available in current environment")

    # Background inference takes 0.25s
    def slow_predict(*args, **kwargs):
        time.sleep(0.25)
        return [{"label": "persona", "start": 0, "end": 14, "text": "Carlos Mendoza", "score": 0.95}]

    gliner._model.predict_entities = slow_predict

    # 1. First call times out after 0.03s
    t0 = time.perf_counter()
    with pytest.raises(TimeoutError, match="excedió el tiempo límite"):
        gliner.detect_entities([{"text": "Carlos Mendoza", "page_or_section": "1"}])
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.15, f"Caller must return promptly on timeout, took {elapsed:.3f}s"

    # 2. Immediate second call while background worker is still busy (t ~ 0.04s < 0.25s)
    # Must be rejected immediately with GLiNERBusyError
    with pytest.raises(GLiNERBusyError, match="ocupado"):
        gliner.detect_entities([{"text": "Carlos Mendoza", "page_or_section": "1"}])

    gliner.close()


def test_gliner_service_recovery_after_inference_completion():
    """
    Requirement 5:
    - Once the active inference finishes and the background worker releases the admission slot,
      the detector recovers cleanly and successfully admits subsequent requests.
    """
    gliner = GLiNERDetector(threshold=0.45, inference_timeout_seconds=0.03)
    if not gliner.is_ready:
        pytest.skip("GLiNER model not available in current environment")

    # Background inference takes 0.15s
    def slow_predict(*args, **kwargs):
        time.sleep(0.15)
        return [{"label": "persona", "start": 0, "end": 14, "text": "Carlos Mendoza", "score": 0.95}]

    gliner._model.predict_entities = slow_predict

    # 1. Times out on caller side
    with pytest.raises(TimeoutError):
        gliner.detect_entities([{"text": "Carlos Mendoza", "page_or_section": "1"}])

    # 2. Wait until the background task completes (0.15s total; wait 0.20s to ensure completion)
    time.sleep(0.20)

    # 3. New request after completion must succeed cleanly
    def fast_predict(*args, **kwargs):
        return [{"label": "persona", "start": 0, "end": 14, "text": "Carlos Mendoza", "score": 0.95}]

    gliner._model.predict_entities = fast_predict
    gliner.inference_timeout_seconds = 2.0

    entities = gliner.detect_entities([{"text": "Carlos Mendoza", "page_or_section": "1"}])
    assert len(entities) == 1
    assert entities[0].original_text == "Carlos Mendoza"
    assert entities[0].category == EntityCategory.PERSON

    gliner.close()


def test_gliner_bounded_concurrency_no_thread_leaks():
    """
    Verifies that multiple sequential and rejected requests do not leak threads.
    Executor threads never exceed 1.
    """
    gliner = GLiNERDetector(threshold=0.45)
    if not gliner.is_ready:
        pytest.skip("GLiNER model not available in current environment")

    for _ in range(5):
        ents = gliner.detect_entities([{"text": "Juan Pérez", "page_or_section": "1"}])
        assert isinstance(ents, list)

    assert len(gliner._executor._threads) <= 1
    gliner.close()


def test_composite_handles_gliner_busy_error_gracefully():
    """
    When GLiNER raises GLiNERBusyError (busy rejection), CompositePIIDetector must:
    1. Retain all deterministic Layer 1 entities.
    2. Set last_analysis_was_partial = True.
    3. Return safely without crashing the application.
    """
    det_mock = MagicMock()
    det_mock.detect_entities.return_value = [
        PIIEntity(
            id="det-1",
            category=EntityCategory.EMAIL,
            original_text="soporte@anondoc.org",
            start_char=0,
            end_char=20,
            confidence=DetectionConfidence.HIGH,
            context="soporte@anondoc.org",
            page_or_section="1",
            selected=True,
            is_manual=False,
        )
    ]

    sem_mock = MagicMock()
    sem_mock.is_ready = True
    sem_mock.detect_entities.side_effect = GLiNERBusyError("Detector busy test")

    comp = CompositePIIDetector(
        deterministic_detector=det_mock,
        semantic_detector=sem_mock,
    )
    result = comp.detect_entities([{"text": "soporte@anondoc.org", "page_or_section": "1"}])

    assert len(result) == 1
    assert result[0].original_text == "soporte@anondoc.org"
    assert comp.last_analysis_was_partial is True


def test_composite_graceful_degradation_on_semantic_timeout_or_failure():
    """
    When semantic detector times out or throws an error, CompositePIIDetector must:
    1. Retain all deterministic Layer 1 entities.
    2. Set last_analysis_was_partial = True.
    3. Not raise an unhandled exception to the caller.
    """
    det_mock = MagicMock()
    det_mock.detect_entities.return_value = [
        PIIEntity(
            id="det-1",
            category=EntityCategory.EMAIL,
            original_text="test@anondoc.org",
            start_char=0,
            end_char=17,
            confidence=DetectionConfidence.HIGH,
            context="test@anondoc.org",
            page_or_section="1",
            selected=True,
            is_manual=False,
        )
    ]

    sem_mock = MagicMock()
    sem_mock.is_ready = True
    sem_mock.detect_entities.side_effect = TimeoutError("Simulated GLiNER timeout")

    comp = CompositePIIDetector(
        deterministic_detector=det_mock,
        semantic_detector=sem_mock,
    )
    result = comp.detect_entities([{"text": "test@anondoc.org", "page_or_section": "1"}])

    assert len(result) == 1
    assert result[0].original_text == "test@anondoc.org"
    assert comp.last_analysis_was_partial is True


def test_composite_fallback_when_model_is_not_ready():
    """When GLiNER is not ready (load failed or disabled), composite falls back cleanly."""
    det_mock = MagicMock()
    det_mock.detect_entities.return_value = [
        PIIEntity(
            id="det-1",
            category=EntityCategory.PHONE,
            original_text="0998765432",
            start_char=0,
            end_char=10,
            confidence=DetectionConfidence.HIGH,
            context="0998765432",
            page_or_section="1",
            selected=True,
            is_manual=False,
        )
    ]

    sem_mock = MagicMock()
    sem_mock.is_ready = False

    comp = CompositePIIDetector(
        deterministic_detector=det_mock,
        semantic_detector=sem_mock,
    )
    result = comp.detect_entities([{"text": "0998765432", "page_or_section": "1"}])

    assert len(result) == 1
    assert result[0].original_text == "0998765432"
    assert comp.last_analysis_was_partial is True
