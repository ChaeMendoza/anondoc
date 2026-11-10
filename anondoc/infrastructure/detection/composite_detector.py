"""
Composite PII Detector orchestrating Layer 1 (Deterministic) and Layer 2 (Semantic).
Applies explicit, transparent fusion rules:
1. Exact matches: consolidated with HIGH confidence.
2. Partial matches / span extension: subsumed to union span with HIGH confidence.
3. Category conflicts: hard deterministic validation prevails; soft conflicts keep highest confidence.
4. Unconfirmed detections: NEVER silently dropped. Preserved with their original confidence
   and marked as unconfirmed so human review is not deprived of candidate alerts.
5. Phone false-positive suppression: phone regex matches overlapping verified cards/accounts/cedulas are purged.
"""
import logging
import threading
from typing import Any, Dict, List, Optional, Set

from anondoc.domain.entities import DetectionConfidence, EntityCategory, PIIEntity
from anondoc.domain.interfaces import IPIIDetector
from anondoc.infrastructure.detection.context_analyzer import ContextAnalyzer
from anondoc.infrastructure.detection.gliner_detector import GLiNERBusyError
from anondoc.infrastructure.detection.pii_detector import HybridPIIDetector

ops_log = logging.getLogger("anondoc.ops")
security_log = logging.getLogger("anondoc.security")

# Categories where algorithmic validation (Luhn, Modulo 10/11) or syntax (RFC 5322) is mathematically authoritative
HARD_DETERMINISTIC_CATEGORIES: Set[EntityCategory] = {
    EntityCategory.ECUADOR_CEDULA,
    EntityCategory.ECUADOR_RUC,
    EntityCategory.CREDIT_CARD,
    EntityCategory.EMAIL,
    EntityCategory.IP_ADDRESS,
    EntityCategory.PASSPORT,
    EntityCategory.BANK_ACCOUNT,
}


def _spans_overlap(s1: int, e1: int, s2: int, e2: int) -> bool:
    return max(s1, s2) < min(e1, e2)


class CompositePIIDetector(IPIIDetector):
    """
    Two-layer hybrid detector combining deterministic rules (Layer 1)
    with local zero-shot semantic span extraction (Layer 2 - GLiNER).
    """

    def __init__(
        self,
        deterministic_detector: Optional[IPIIDetector] = None,
        semantic_detector: Optional[IPIIDetector] = None,
    ):
        self.deterministic_detector = deterministic_detector or HybridPIIDetector()
        self.semantic_detector = semantic_detector
        # Per-thread: analyses run concurrently in the API threadpool and must not share the flag.
        self._state = threading.local()

    @property
    def is_semantic_available(self) -> bool:
        if self.semantic_detector is None:
            return False
        if hasattr(self.semantic_detector, "is_ready"):
            return bool(self.semantic_detector.is_ready)
        return True

    @property
    def last_analysis_was_partial(self) -> bool:
        return getattr(self._state, "partial", False)

    @property
    def last_partial_reason(self) -> Optional[str]:
        """'unavailable', 'busy' or 'failed' when the last analysis on this thread was partial."""
        return getattr(self._state, "reason", None)

    def _mark(self, partial: bool, reason: Optional[str] = None) -> None:
        self._state.partial = partial
        self._state.reason = reason

    def detect_entities(self, text_blocks: List[Dict[str, Any]]) -> List[PIIEntity]:
        det_entities = self.deterministic_detector.detect_entities(text_blocks)

        if not self.is_semantic_available:
            self._mark(True, "unavailable")
            return det_entities

        self._mark(False)
        try:
            sem_entities = self.semantic_detector.detect_entities(text_blocks)
        except Exception as exc:
            security_log.warning("event=semantic_inference_failed error=%s", str(exc))
            self._mark(True, "busy" if isinstance(exc, GLiNERBusyError) else "failed")
            return det_entities

        if not sem_entities:
            return det_entities

        # Group by page/section to ensure spatial coordinate integrity
        blocks_map: Dict[str, List[PIIEntity]] = {}
        for ent in det_entities:
            blocks_map.setdefault(ent.page_or_section, []).append(ent)

        sem_map: Dict[str, List[PIIEntity]] = {}
        for ent in sem_entities:
            sem_map.setdefault(ent.page_or_section, []).append(ent)

        all_merged: List[PIIEntity] = []
        all_pages = set(blocks_map.keys()) | set(sem_map.keys())

        for page in all_pages:
            det_list = blocks_map.get(page, [])
            sem_list = sem_map.get(page, [])
            merged_page = self._merge_page_entities(det_list, sem_list)
            all_merged.extend(merged_page)

        return all_merged

    def _merge_page_entities(
        self,
        det_entities: List[PIIEntity],
        sem_entities: List[PIIEntity],
    ) -> List[PIIEntity]:
        """
        Applies explicit fusion rules:
        - Rule 1: High-confidence hard deterministic entities are authoritative.
        - Rule 2: Suppress greedy PHONE regex matches that overlap with valid cards, cédulas, or accounts.
        - Rule 3: Suppress semantic entities that overlap with valid hard deterministic entities.
        - Rule 4: Match and subsume overlapping entities of the same category (union span, HIGH confidence).
        - Rule 5: Resolve category conflicts (hard deterministic > soft semantic; higher confidence wins).
        - Rule 6: Unconfirmed detections from BOTH layers are RETAINED (no silent data loss).
        """
        # 1. Authoritative hard deterministic entities
        hard_entities = [
            e for e in det_entities
            if e.category in HARD_DETERMINISTIC_CATEGORIES and e.confidence == DetectionConfidence.HIGH
        ]

        # Also consider valid bank accounts as authoritative against phone regex
        account_entities = [
            e for e in det_entities
            if e.category == EntityCategory.BANK_ACCOUNT
        ]
        authoritative_numbers = hard_entities + account_entities

        # 2. Filter out deterministic PHONE false positives that overlap with verified numbers
        sanitized_det: List[PIIEntity] = []
        for det in det_entities:
            if det.category == EntityCategory.PHONE:
                overlaps_auth = any(
                    _spans_overlap(det.start_char, det.end_char, a.start_char, a.end_char)
                    for a in authoritative_numbers
                )
                if overlaps_auth:
                    continue
            sanitized_det.append(det)

        # 3. Discard semantic predictions that collide with hard deterministic entities
        valid_sem: List[PIIEntity] = []
        for sem in sem_entities:
            overlaps_hard = any(
                _spans_overlap(sem.start_char, sem.end_char, h.start_char, h.end_char)
                for h in hard_entities
            )
            if overlaps_hard:
                continue
            valid_sem.append(sem)

        final_entities: List[PIIEntity] = []
        matched_sem_ids = set()

        # 4 & 5. Process deterministic entities and pair with semantic predictions
        for det in sanitized_det:
            # Check for overlapping semantic entities
            overlapping_sems = [
                s for s in valid_sem
                if _spans_overlap(det.start_char, det.end_char, s.start_char, s.end_char)
            ]

            if not overlapping_sems:
                # Rule 6A: Unconfirmed deterministic detection. NEVER drop it.
                # Retain with original confidence and inform the reviewer.
                if det not in hard_entities:
                    det.validation_details = (
                        f"{det.validation_details or 'Detección determinista'} (sin confirmación semántica)"
                    )
                final_entities.append(det)
                continue

            # Found one or more overlapping semantic entities
            # Handle primary overlap
            best_sem = overlapping_sems[0]
            matched_sem_ids.add(best_sem.id)

            if det.category == best_sem.category:
                # Rule 4: Same category -> Subsume to union span and elevate to HIGH confidence
                sem_start, sem_end = best_sem.start_char, best_sem.end_char
                if det.category == EntityCategory.PERSON:
                    # Never absorb an administrative header ("Firmado Digitalmente por") into a person span.
                    inner = ContextAnalyzer.refine_person_span(best_sem.original_text, 0, len(best_sem.original_text))
                    if inner is None:
                        sem_start, sem_end = det.start_char, det.end_char
                    else:
                        sem_start = best_sem.start_char + inner[0]
                        sem_end = best_sem.start_char + inner[1]
                new_start = min(det.start_char, sem_start)
                new_end = max(det.end_char, sem_end)
                det.start_char = new_start
                det.end_char = new_end
                det.confidence = DetectionConfidence.HIGH
                det.validation_details = (
                    f"Confirmación dual y span ampliado: Reglas deterministas + {best_sem.validation_details}"
                )
                final_entities.append(det)
            else:
                # Rule 5: Category conflict on overlapping span
                if det.category in HARD_DETERMINISTIC_CATEGORIES and det.confidence == DetectionConfidence.HIGH:
                    # Hard deterministic takes precedence
                    final_entities.append(det)
                else:
                    # Soft category conflict (e.g. PERSON vs ADDRESS)
                    # Compare confidence levels
                    conf_scores = {
                        DetectionConfidence.HIGH: 3,
                        DetectionConfidence.MEDIUM: 2,
                        DetectionConfidence.LOW: 1
                    }
                    if conf_scores[best_sem.confidence] > conf_scores[det.confidence]:
                        final_entities.append(best_sem)
                    else:
                        # Deterministic has equal or higher confidence; retain deterministic
                        det.validation_details = (
                            f"{det.validation_details or 'Detección determinista'} "
                            f"(solapa con {best_sem.category.value} semántico)"
                        )
                        final_entities.append(det)

        # Rule 6B: Unconfirmed semantic entities (detected by GLiNER but missed by regex)
        for sem in valid_sem:
            if sem.id not in matched_sem_ids:
                # Check it doesn't collide with any already accepted entity
                collides = any(
                    _spans_overlap(sem.start_char, sem.end_char, f.start_char, f.end_char)
                    for f in final_entities
                )
                if not collides:
                    final_entities.append(sem)

        # 6. Final deduplication and overlap cleanup
        return HybridPIIDetector._resolve_overlaps(final_entities)
