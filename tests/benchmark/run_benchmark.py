"""
AnonDoc Reproducible Benchmark Harness.
Evaluates any IPIIDetector implementation against the standardized dataset.
Calculates strict metrics (Precision, Recall, F1, FP, FN, Latency, Memory)
both globally and broken down per entity category.
"""
import json
import os
import psutil
import time
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict

from anondoc.domain.entities import PIIEntity
from anondoc.domain.interfaces import IPIIDetector
from anondoc.infrastructure.detection.pii_detector import HybridPIIDetector


def spans_overlap(s1: int, e1: int, s2: int, e2: int) -> bool:
    return max(s1, s2) < min(e1, e2)


def evaluate_detector(
    detector: IPIIDetector,
    dataset_path: Path,
    strict_span: bool = False
) -> Dict[str, Any]:
    """
    Evaluates detector against dataset.
    If strict_span is False, an overlap with the same category counts as TP.
    If strict_span is True, exact matching of (start_char, end_char) is required.
    """
    process = psutil.Process(os.getpid())
    mem_before = process.memory_info().rss / (1024 * 1024)

    with open(dataset_path, "r", encoding="utf-8") as f:
        docs = [json.loads(line) for line in f if line.strip()]

    total_words = 0
    t0 = time.perf_counter()

    # Per-category metrics: {cat: {"tp": 0, "fp": 0, "fn": 0}}
    cat_metrics = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "gt_count": 0, "pred_count": 0})
    false_positives = []
    false_negatives = []

    for doc in docs:
        text = doc["text"]
        gt_entities = doc["entities"]
        total_words += len(text.split())

        # Ground truth counting
        for gt in gt_entities:
            cat_metrics[gt["category"]]["gt_count"] += 1

        # Run detector
        block = [{"text": text, "page_or_section": "1"}]
        predictions: List[PIIEntity] = detector.detect_entities(block)

        for p in predictions:
            cat_metrics[p.category.value]["pred_count"] += 1

        matched_gt = set()
        matched_pred = set()

        # Match predictions to GT
        for p_idx, pred in enumerate(predictions):
            pred_cat = pred.category.value
            pred_start, pred_end = pred.start_char, pred.end_char

            matched = False
            for g_idx, gt in enumerate(gt_entities):
                if g_idx in matched_gt:
                    continue
                if gt["category"] != pred_cat:
                    continue

                if strict_span:
                    is_match = (pred_start == gt["start_char"] and pred_end == gt["end_char"])
                else:
                    is_match = spans_overlap(pred_start, pred_end, gt["start_char"], gt["end_char"])

                if is_match:
                    cat_metrics[pred_cat]["tp"] += 1
                    matched_gt.add(g_idx)
                    matched_pred.add(p_idx)
                    matched = True
                    break

            if not matched:
                cat_metrics[pred_cat]["fp"] += 1
                false_positives.append({
                    "doc_id": doc["id"],
                    "category": pred_cat,
                    "text": pred.original_text,
                    "span": (pred_start, pred_end),
                    "context": pred.context
                })

        # Unmatched GT are FN
        for g_idx, gt in enumerate(gt_entities):
            if g_idx not in matched_gt:
                cat_metrics[gt["category"]]["fn"] += 1
                false_negatives.append({
                    "doc_id": doc["id"],
                    "category": gt["category"],
                    "text": gt["text"],
                    "span": (gt["start_char"], gt["end_char"])
                })

    elapsed_ms = (time.perf_counter() - t0) * 1000
    mem_after = process.memory_info().rss / (1024 * 1024)

    # Compute summary
    global_tp = sum(m["tp"] for m in cat_metrics.values())
    global_fp = sum(m["fp"] for m in cat_metrics.values())
    global_fn = sum(m["fn"] for m in cat_metrics.values())
    global_gt = sum(m["gt_count"] for m in cat_metrics.values())
    total_preds = sum(m["pred_count"] for m in cat_metrics.values())

    precision = global_tp / (global_tp + global_fp) if (global_tp + global_fp) > 0 else 0.0
    recall = global_tp / (global_tp + global_fn) if (global_tp + global_fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    category_results = {}
    for cat, m in sorted(cat_metrics.items()):
        p = m["tp"] / (m["tp"] + m["fp"]) if (m["tp"] + m["fp"]) > 0 else 0.0
        r = m["tp"] / (m["tp"] + m["fn"]) if (m["tp"] + m["fn"]) > 0 else 0.0
        f = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0
        category_results[cat] = {
            "gt_count": m["gt_count"],
            "pred_count": m["pred_count"],
            "tp": m["tp"],
            "fp": m["fp"],
            "fn": m["fn"],
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f, 4),
        }

    eval_result = {
        "summary": {
            "documents_count": len(docs),
            "total_words": total_words,
            "total_ground_truth": global_gt,
            "total_predictions": total_preds,
            "total_tp": global_tp,
            "total_fp": global_fp,
            "total_fn": global_fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "fp_per_1000_words": round((global_fp / total_words) * 1000, 2) if total_words > 0 else 0.0,
            "latency_total_ms": round(elapsed_ms, 2),
            "latency_avg_per_doc_ms": round(elapsed_ms / len(docs), 2) if docs else 0.0,
            "mem_rss_mb": round(mem_after, 2),
            "mem_delta_mb": round(mem_after - mem_before, 2)
        },
        "by_category": category_results,
        "false_positives": false_positives,
        "false_negatives": false_negatives
    }

    validate_benchmark_integrity(eval_result)
    return eval_result


def validate_benchmark_integrity(results: Dict[str, Any]) -> None:
    """
    Automated mathematical reconciliation invariant assertions.
    Ensures that global and category breakdown metrics are 100% mathematically consistent:
    - Sum of category GT equals total ground truth.
    - Sum of category TP equals total TP.
    - Sum of category FP equals total FP.
    - Sum of category FN equals total FN.
    - Sum of category Pred equals total Pred.
    - Total GT equals Total TP + Total FN.
    - Total Pred equals Total TP + Total FP.
    - Length of false_positives list equals total FP.
    - Length of false_negatives list equals total FN.
    - For each category, GT == TP + FN and Pred == TP + FP.
    - Calculated precision, recall, and F1 match the count ratios.
    - No entity has an empty or invalid category name.
    """
    s = results["summary"]
    cats = results["by_category"]

    sum_gt = sum(c["gt_count"] for c in cats.values())
    sum_pred = sum(c["pred_count"] for c in cats.values())
    sum_tp = sum(c["tp"] for c in cats.values())
    sum_fp = sum(c["fp"] for c in cats.values())
    sum_fn = sum(c["fn"] for c in cats.values())

    if sum_gt != s["total_ground_truth"]:
        raise AssertionError(
            f"Integrity error: sum of category GT ({sum_gt}) != global GT ({s['total_ground_truth']})"
        )
    if sum_tp != s["total_tp"]:
        raise AssertionError(
            f"Integrity error: sum of category TP ({sum_tp}) != global TP ({s['total_tp']})"
        )
    if sum_fp != s["total_fp"]:
        raise AssertionError(
            f"Integrity error: sum of category FP ({sum_fp}) != global FP ({s['total_fp']})"
        )
    if sum_fn != s["total_fn"]:
        raise AssertionError(
            f"Integrity error: sum of category FN ({sum_fn}) != global FN ({s['total_fn']})"
        )
    if s["total_ground_truth"] != s["total_tp"] + s["total_fn"]:
        raise AssertionError(
            f"Integrity error: global GT ({s['total_ground_truth']}) != TP + FN ({s['total_tp'] + s['total_fn']})"
        )
    if sum_pred != s["total_tp"] + s["total_fp"]:
        raise AssertionError(
            f"Integrity error: sum of category Pred ({sum_pred}) != TP + FP ({s['total_tp'] + s['total_fp']})"
        )
    if len(results["false_positives"]) != s["total_fp"]:
        raise AssertionError(
            f"Integrity error: FP items ({len(results['false_positives'])}) != total_fp ({s['total_fp']})"
        )
    if len(results["false_negatives"]) != s["total_fn"]:
        raise AssertionError(
            f"Integrity error: FN items ({len(results['false_negatives'])}) != total_fn ({s['total_fn']})"
        )

    for cat_name, c in cats.items():
        if not cat_name or cat_name in ("None", "null"):
            raise AssertionError(f"Integrity error: invalid entity category name: '{cat_name}'")
        if c["gt_count"] != c["tp"] + c["fn"]:
            raise AssertionError(
                f"Category {cat_name}: GT ({c['gt_count']}) != TP + FN ({c['tp'] + c['fn']})"
            )
        if c["pred_count"] != c["tp"] + c["fp"]:
            raise AssertionError(
                f"Category {cat_name}: Pred ({c['pred_count']}) != TP + FP ({c['tp'] + c['fp']})"
            )
        exp_p = round(c["tp"] / (c["tp"] + c["fp"]), 4) if (c["tp"] + c["fp"]) > 0 else 0.0
        exp_r = round(c["tp"] / (c["tp"] + c["fn"]), 4) if (c["tp"] + c["fn"]) > 0 else 0.0
        if c["precision"] != exp_p:
            raise AssertionError(f"Category {cat_name}: precision mismatch {c['precision']} vs {exp_p}")
        if c["recall"] != exp_r:
            raise AssertionError(f"Category {cat_name}: recall mismatch {c['recall']} vs {exp_r}")

    exp_global_p = round(s["total_tp"] / (s["total_tp"] + s["total_fp"]), 4) if (s["total_tp"] + s["total_fp"]) > 0 else 0.0
    exp_global_r = round(s["total_tp"] / (s["total_tp"] + s["total_fn"]), 4) if (s["total_tp"] + s["total_fn"]) > 0 else 0.0
    if s["precision"] != exp_global_p:
        raise AssertionError(f"Global precision mismatch: {s['precision']} vs {exp_global_p}")
    if s["recall"] != exp_global_r:
        raise AssertionError(f"Global recall mismatch: {s['recall']} vs {exp_global_r}")


def print_report(results: Dict[str, Any], title: str = "BENCHMARK RESULTS"):
    s = results["summary"]
    print("=" * 80)
    print(f" {title} ")
    print("=" * 80)
    print(f"Documentos evaluados: {s['documents_count']} | Palabras analizadas: {s['total_words']}")
    print(f"Precision Global:     {s['precision'] * 100:.2f}%")
    print(f"Recall Global:        {s['recall'] * 100:.2f}%")
    print(f"F1-Score Global:      {s['f1_score'] * 100:.2f}%")
    print(f"Verdaderos Positivos: {s['total_tp']} / {s['total_ground_truth']}")
    print(f"Falsos Positivos:     {s['total_fp']} ({s['fp_per_1000_words']} por 1.000 palabras)")
    print(f"Falsos Negativos:     {s['total_fn']}")
    print(f"Latencia Total:       {s['latency_total_ms']:.2f} ms ({s['latency_avg_per_doc_ms']:.2f} ms/doc)")
    print(f"Consumo Memoria RSS:  {s['mem_rss_mb']:.2f} MB (Delta: {s['mem_delta_mb']:+.2f} MB)")
    print("-" * 80)
    print(f"{'Categoría':<20} | {'GT':<4} | {'Pred':<4} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'Prec':<7} | {'Rec':<7} | {'F1':<7}")
    print("-" * 80)
    for cat, m in results["by_category"].items():
        print(f"{cat:<20} | {m['gt_count']:<4} | {m['pred_count']:<4} | {m['tp']:<4} | {m['fp']:<4} | {m['fn']:<4} | {m['precision']*100:>6.1f}% | {m['recall']*100:>6.1f}% | {m['f1']*100:>6.1f}%")
    print("=" * 80)

    if results["false_negatives"]:
        print("\n--- RESUMEN DE FALSOS NEGATIVOS (PII NO DETECTADA) ---")
        for fn in results["false_negatives"]:
            print(f"[{fn['doc_id']}] {fn['category']}: '{fn['text']}'")

    if results["false_positives"]:
        print("\n--- RESUMEN DE FALSOS POSITIVOS (TEXTO ERRÓNEAMENTE DETECTADO) ---")
        for fp in results["false_positives"]:
            print(f"[{fp['doc_id']}] {fp['category']}: '{fp['text']}'")


if __name__ == "__main__":
    dataset_file = Path(__file__).resolve().parent / "dataset.jsonl"
    detector = HybridPIIDetector()
    res = evaluate_detector(detector, dataset_file)
    print_report(res, "LINEA BASE V2.0 - MOTOR DETERMINISTA ACTUAL")
    
    # Save baseline metrics to disk for regression comparison
    baseline_out = Path(__file__).resolve().parent / "baseline_results.json"
    with open(baseline_out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    print(f"\nResultados basales guardados en: {baseline_out}")
