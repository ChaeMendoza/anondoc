"""
GLiNER Local Semantic Detector Adapter.
Implements IPIIDetector using local GLiNER transformer models.
Performs zero-shot span extraction on CPU with strict textual groundedness verification.
"""
import concurrent.futures
import logging
import threading
import uuid
from typing import Any, Dict, List, Optional

from anondoc.domain.entities import DetectionConfidence, EntityCategory, PIIEntity
from anondoc.domain.interfaces import IPIIDetector
from anondoc.infrastructure.detection.context_analyzer import ContextAnalyzer

ops_log = logging.getLogger("anondoc.ops")
security_log = logging.getLogger("anondoc.security")


class GLiNERBusyError(RuntimeError):
    """Raised when GLiNER is already executing an inference and cannot admit new requests."""
    pass

DEFAULT_SPAN_MAP: Dict[str, EntityCategory] = {
    "persona": EntityCategory.PERSON,
    "nombre completo": EntityCategory.PERSON,
    "dirección residencial": EntityCategory.ADDRESS,
    "dirección física": EntityCategory.ADDRESS,
    "diagnóstico médico": EntityCategory.MEDICAL_DATA,
    "enfermedad o patología": EntityCategory.MEDICAL_DATA,
    "monto financiero": EntityCategory.FINANCIAL_DATA,
    "nombre de usuario": EntityCategory.USERNAME,
}


class GLiNERDetector(IPIIDetector):
    """Local semantic PII detector powered by GLiNER bi-encoder models on CPU."""

    def __init__(
        self,
        model_name: str = "urchade/gliner_multi-v2.1",
        threshold: float = 0.50,
        labels_map: Optional[Dict[str, EntityCategory]] = None,
        device: str = "cpu",
        inference_timeout_seconds: Optional[float] = 10.0,
    ):
        self.model_name = model_name
        self.threshold = threshold
        self.labels_map = labels_map or DEFAULT_SPAN_MAP
        self.labels = list(self.labels_map.keys())
        self.device = device
        self.inference_timeout_seconds = inference_timeout_seconds
        self._model = None
        self._load_model()
        # Bounded admission: at most 1 active/pending inference per instance.
        self._admission_slot = threading.Semaphore(1)
        # Persistent bounded executor to prevent thread churn, enforce concurrency limit = 1,
        # and eliminate caller-blocking on ThreadPoolExecutor.__exit__ during timeouts.
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="gliner_inference",
        )

    def close(self) -> None:
        """Closes the background inference executor cleanly, cancelling pending tasks."""
        if hasattr(self, "_executor") and self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

    def __del__(self) -> None:
        self.close()

    def _load_model(self) -> None:
        try:
            from gliner import GLiNER
            ops_log.info("op=load_model model=%s device=%s", self.model_name, self.device)
            self._model = GLiNER.from_pretrained(self.model_name)
            if hasattr(self._model, "to"):
                self._model.to(self.device)
        except Exception as exc:
            security_log.warning("event=gliner_load_failed error=%s", str(exc))
            self._model = None

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    def detect_entities(self, text_blocks: List[Dict[str, Any]]) -> List[PIIEntity]:
        if not self._model or not text_blocks:
            return []

        # 1. Bounded admission: reject new requests immediately when busy without enqueuing
        if not self._admission_slot.acquire(blocking=False):
            security_log.warning("event=gliner_detector_busy action=reject_without_queue")
            raise GLiNERBusyError(
                "El detector semántico local (GLiNER) está ocupado procesando otra solicitud. "
                "Solicitud rechazada sin encolar para proteger recursos de CPU y memoria."
            )

        # 2. Worker routine running within the bounded single-worker executor
        def _execute_inference():
            try:
                results = []
                for block in text_blocks:
                    text = block.get("text", "")
                    if not text.strip():
                        continue
                    preds = self._model.predict_entities(
                        text,
                        self.labels,
                        threshold=self.threshold,
                        flat_ner=True,
                    )
                    results.append((block, preds))
                return results
            finally:
                # 4. Maintain admission control until the inference actually finishes
                self._admission_slot.release()

        future = self._executor.submit(_execute_inference)

        try:
            raw_results = future.result(timeout=self.inference_timeout_seconds)
        except concurrent.futures.TimeoutError:
            # 3. On timeout, attempt cancellation ONLY if task hasn't started yet
            if not future.running() and future.cancel():
                # Task cancelled before running; release the admission slot
                self._admission_slot.release()
            security_log.warning(
                "event=gliner_inference_timeout limit=%.2fs",
                self.inference_timeout_seconds,
            )
            raise TimeoutError(
                f"Inferencia GLiNER excedió el tiempo límite de {self.inference_timeout_seconds}s"
            )
        except Exception as exc:
            security_log.warning("event=gliner_inference_error error=%s", str(exc))
            return []

        # 5. Transform raw predictions into domain PIIEntity objects
        all_entities: List[PIIEntity] = []
        for block, raw_predictions in raw_results:
            text = block.get("text", "")
            page_or_section = str(block.get("page_or_section", "1"))
            for pred in raw_predictions:
                label = pred.get("label")
                start = pred.get("start")
                end = pred.get("end")
                matched_text = pred.get("text", "")
                score = float(pred.get("score", 0.0))

                category = self.labels_map.get(label)
                if not category:
                    continue

                # Strict span groundedness verification: the substring must match character-by-character
                if text[start:end] != matched_text:
                    security_log.warning(
                        "event=gliner_span_mismatch expected='%s' found='%s'",
                        matched_text,
                        text[start:end],
                    )
                    continue

                # Exclude obvious false positive phrases like institutional names
                if ContextAnalyzer.is_common_institutional_phrase(matched_text):
                    continue

                # Calibrate confidence score
                if score >= 0.85:
                    confidence = DetectionConfidence.HIGH
                elif score >= 0.65:
                    confidence = DetectionConfidence.MEDIUM
                else:
                    confidence = DetectionConfidence.LOW

                ctx = ContextAnalyzer.extract_window(text, start, end)

                all_entities.append(
                    PIIEntity(
                        id=str(uuid.uuid4()),
                        category=category,
                        original_text=matched_text,
                        start_char=start,
                        end_char=end,
                        confidence=confidence,
                        context=ctx,
                        page_or_section=page_or_section,
                        selected=True,
                        is_manual=False,
                        validation_details=f"GLiNER bi-encoder span (score: {score:.2f})",
                    )
                )

        return all_entities
