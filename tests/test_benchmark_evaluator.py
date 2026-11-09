"""
Unit tests for the Benchmark Evaluator Integrity and Matching Engine.
Covers:
1. Category match requirement (category mismatch on overlapping span -> 1 FP + 1 FN, 0 TP).
2. Offset matching and span tolerance (strict_span=True vs strict_span=False).
3. Expanded spans (subsumed and extended spans).
4. One-to-one strict bijection (1 GT cannot be consumed by 2 predictions; 1 pred cannot consume 2 GTs).
5. Duplicate predictions prevention.
6. Conservation of totals (GT == TP + FN, Pred == TP + FP).
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from anondoc.domain.entities import DetectionConfidence, EntityCategory, PIIEntity
from tests.benchmark.run_benchmark import evaluate_detector, spans_overlap, validate_benchmark_integrity


def test_spans_overlap_logic():
    """Verifies interval overlap boundary conditions."""
    # Disjoint intervals
    assert not spans_overlap(0, 5, 5, 10)  # adjacent boundary: [0, 5) and [5, 10) do not overlap
    assert not spans_overlap(10, 15, 0, 5)

    # Overlapping intervals
    assert spans_overlap(0, 6, 5, 10)  # 1 char overlap at 5
    assert spans_overlap(5, 10, 0, 6)
    assert spans_overlap(0, 10, 2, 8)  # contained
    assert spans_overlap(2, 8, 0, 10)  # containing
    assert spans_overlap(0, 10, 0, 10) # identical


def test_evaluator_category_mismatch_counts_as_fp_and_fn(tmp_path):
    """
    If a prediction overlaps an entity but has a DIFFERENT category,
    it must NOT count as a TP. It must be 1 FP for the predicted category
    and 1 FN for the ground truth category.
    """
    dataset_file = tmp_path / "test_cat_mismatch.jsonl"
    dataset_file.write_text(
        '{"id": "doc_1", "text": "Cédula: 1710034065.", "entities": [{"category": "ECUADOR_CEDULA", "text": "1710034065", "start_char": 8, "end_char": 18}]}\n',
        encoding="utf-8",
    )

    mock_detector = MagicMock()
    # Detector predicts PHONE over the cédula span
    mock_detector.detect_entities.return_value = [
        PIIEntity(
            id="p-1",
            category=EntityCategory.PHONE,
            original_text="1710034065",
            start_char=8,
            end_char=18,
            confidence=DetectionConfidence.HIGH,
            context="Cédula: 1710034065",
            page_or_section="1",
            selected=True,
            is_manual=False,
        )
    ]

    res = evaluate_detector(mock_detector, dataset_file, strict_span=False)
    s = res["summary"]

    assert s["total_ground_truth"] == 1
    assert s["total_predictions"] == 1
    assert s["total_tp"] == 0
    assert s["total_fp"] == 1
    assert s["total_fn"] == 1

    assert res["by_category"]["ECUADOR_CEDULA"]["fn"] == 1
    assert res["by_category"]["ECUADOR_CEDULA"]["tp"] == 0
    assert res["by_category"]["PHONE"]["fp"] == 1
    assert res["by_category"]["PHONE"]["tp"] == 0


def test_evaluator_strict_span_vs_overlap_tolerance(tmp_path):
    """
    Demonstrates the difference between strict_span=True and strict_span=False:
    When prediction has an expanded span (e.g. including title or punctuation):
    - strict_span=False: counted as TP (span overlap accepted).
    - strict_span=True: counted as 1 FP and 1 FN (exact offsets required).
    """
    dataset_file = tmp_path / "test_span.jsonl"
    dataset_file.write_text(
        '{"id": "doc_2", "text": "El Dr. Carlos Mendoza asistió.", "entities": [{"category": "PERSON", "text": "Carlos Mendoza", "start_char": 7, "end_char": 21}]}\n',
        encoding="utf-8",
    )

    mock_detector = MagicMock()
    # Detector predicts expanded span including title "Dr. Carlos Mendoza" (start 3, end 21)
    mock_detector.detect_entities.return_value = [
        PIIEntity(
            id="p-exp",
            category=EntityCategory.PERSON,
            original_text="Dr. Carlos Mendoza",
            start_char=3,
            end_char=21,
            confidence=DetectionConfidence.HIGH,
            context="El Dr. Carlos Mendoza asistió",
            page_or_section="1",
            selected=True,
            is_manual=False,
        )
    ]

    # 1. Overlap mode (default): TP = 1, FP = 0, FN = 0
    res_overlap = evaluate_detector(mock_detector, dataset_file, strict_span=False)
    assert res_overlap["summary"]["total_tp"] == 1
    assert res_overlap["summary"]["total_fp"] == 0
    assert res_overlap["summary"]["total_fn"] == 0

    # 2. Strict mode: start_char differs (3 != 7), so TP = 0, FP = 1, FN = 1
    res_strict = evaluate_detector(mock_detector, dataset_file, strict_span=True)
    assert res_strict["summary"]["total_tp"] == 0
    assert res_strict["summary"]["total_fp"] == 1
    assert res_strict["summary"]["total_fn"] == 1


def test_evaluator_one_to_one_bijective_mapping_prevents_duplicate_tp(tmp_path):
    """
    A single Ground Truth entity CANNOT be counted as a True Positive more than once.
    If a detector outputs duplicate or multiple overlapping predictions for 1 GT:
    - 1st prediction: TP = 1.
    - 2nd prediction: FP = 1.
    """
    dataset_file = tmp_path / "test_duplicates.jsonl"
    dataset_file.write_text(
        '{"id": "doc_3", "text": "Correo: test@anondoc.org.", "entities": [{"category": "EMAIL", "text": "test@anondoc.org", "start_char": 8, "end_char": 24}]}\n',
        encoding="utf-8",
    )

    mock_detector = MagicMock()
    # Detector returns two predictions for the same email
    mock_detector.detect_entities.return_value = [
        PIIEntity(
            id="e-1",
            category=EntityCategory.EMAIL,
            original_text="test@anondoc.org",
            start_char=8,
            end_char=24,
            confidence=DetectionConfidence.HIGH,
            context="test@anondoc.org",
            page_or_section="1",
            selected=True,
            is_manual=False,
        ),
        PIIEntity(
            id="e-2",
            category=EntityCategory.EMAIL,
            original_text="test@anondoc.org",
            start_char=8,
            end_char=24,
            confidence=DetectionConfidence.HIGH,
            context="test@anondoc.org",
            page_or_section="1",
            selected=True,
            is_manual=False,
        ),
    ]

    res = evaluate_detector(mock_detector, dataset_file, strict_span=False)
    s = res["summary"]

    assert s["total_ground_truth"] == 1
    assert s["total_predictions"] == 2
    assert s["total_tp"] == 1
    assert s["total_fp"] == 1
    assert s["total_fn"] == 0


def test_evaluator_single_prediction_overlapping_two_gts(tmp_path):
    """
    If one oversized prediction overlaps two separate GT entities of the same category,
    it can only match ONE of them as TP; the other GT remains unmatched and becomes FN.
    """
    dataset_file = tmp_path / "test_two_gts.jsonl"
    # Text with two adjacent addresses
    dataset_file.write_text(
        '{"id": "doc_4", "text": "Sedes: Quito y Guayaquil.", "entities": [{"category": "ADDRESS", "text": "Quito", "start_char": 7, "end_char": 12}, {"category": "ADDRESS", "text": "Guayaquil", "start_char": 15, "end_char": 24}]}\n',
        encoding="utf-8",
    )

    mock_detector = MagicMock()
    # Oversized prediction covering "Quito y Guayaquil" (7 to 24)
    mock_detector.detect_entities.return_value = [
        PIIEntity(
            id="p-combo",
            category=EntityCategory.ADDRESS,
            original_text="Quito y Guayaquil",
            start_char=7,
            end_char=24,
            confidence=DetectionConfidence.HIGH,
            context="Quito y Guayaquil",
            page_or_section="1",
            selected=True,
            is_manual=False,
        )
    ]

    res = evaluate_detector(mock_detector, dataset_file, strict_span=False)
    s = res["summary"]

    assert s["total_ground_truth"] == 2
    assert s["total_predictions"] == 1
    assert s["total_tp"] == 1
    assert s["total_fp"] == 0
    assert s["total_fn"] == 1
    assert s["total_ground_truth"] == s["total_tp"] + s["total_fn"]
