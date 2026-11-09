"""
Rigorous, Reproducible A/B Benchmark Comparison for Phase 1.
Features:
- Warm-up execution to eliminate JIT/caching noise.
- Multi-iteration latency measurement (mean ± std dev).
- Exact distinction between base interpreter RSS, model loading footprint, and inference delta.
- Evaluation on both Baseline Dataset (15 docs) and Independent Hold-Out Dataset (12 docs).
- Detailed breakdown per category with TP, FP, FN, Precision, Recall, F1 and concrete examples.
"""
import json
import os
import psutil
import statistics
import time
from pathlib import Path
from typing import Dict, Any

from anondoc.infrastructure.detection.composite_detector import CompositePIIDetector
from anondoc.infrastructure.detection.gliner_detector import GLiNERDetector
from anondoc.infrastructure.detection.pii_detector import HybridPIIDetector
from tests.benchmark.run_benchmark import evaluate_detector, print_report


def measure_detector_performance(
    detector,
    dataset_path: Path,
    warmup_runs: int = 1,
    test_runs: int = 5
) -> Dict[str, Any]:
    process = psutil.Process(os.getpid())
    mem_start = process.memory_info().rss / (1024 * 1024)

    # 1. Warm-up
    for _ in range(warmup_runs):
        _ = evaluate_detector(detector, dataset_path)

    # 2. Timed iterations
    run_times_ms = []
    last_eval = None
    for _ in range(test_runs):
        t0 = time.perf_counter()
        last_eval = evaluate_detector(detector, dataset_path)
        elapsed = (time.perf_counter() - t0) * 1000
        run_times_ms.append(elapsed)

    mem_end = process.memory_info().rss / (1024 * 1024)

    mean_time_ms = statistics.mean(run_times_ms)
    std_time_ms = statistics.stdev(run_times_ms) if len(run_times_ms) > 1 else 0.0
    doc_count = last_eval["summary"]["documents_count"]

    last_eval["summary"]["latency_mean_total_ms"] = round(mean_time_ms, 2)
    last_eval["summary"]["latency_std_total_ms"] = round(std_time_ms, 2)
    last_eval["summary"]["latency_mean_per_doc_ms"] = round(mean_time_ms / doc_count, 2) if doc_count else 0.0
    last_eval["summary"]["mem_rss_process_mb"] = round(mem_end, 2)
    last_eval["summary"]["mem_delta_mb"] = round(mem_end - mem_start, 2)

    return last_eval


def run_full_ab_audit():
    base_dataset = Path(__file__).resolve().parent / "dataset.jsonl"
    holdout_dataset = Path(__file__).resolve().parent / "dataset_eval_holdout.jsonl"

    process = psutil.Process(os.getpid())
    base_rss_mb = process.memory_info().rss / (1024 * 1024)

    print("=" * 80)
    print(" FASE 1: AUDITORÍA TÉCNICA Y BENCHMARK A/B REPRODUCIBLE")
    print("=" * 80)
    print(f"Memoria base del intérprete Python: {base_rss_mb:.2f} MB RSS")

    # 1. Evaluate Engine A (Deterministic Baseline) on both datasets BEFORE loading GLiNER
    print("\n[1/4] Evaluando Motor A (Determinista Basal v2.0) en Dataset Base...")
    det_a = HybridPIIDetector()
    res_a_base = measure_detector_performance(det_a, base_dataset)

    print("\n[2/4] Evaluando Motor A (Determinista Basal v2.0) en Dataset Hold-Out...")
    res_a_holdout = measure_detector_performance(det_a, holdout_dataset)
    mem_after_a = process.memory_info().rss / (1024 * 1024)

    # 2. Load GLiNER and evaluate Model Memory Footprint
    print("\n[3/4] Cargando modelo GLiNER en CPU...")
    t_load_start = time.perf_counter()
    gliner_b = GLiNERDetector(threshold=0.45)
    t_load_end = (time.perf_counter() - t_load_start) * 1000
    mem_after_model = process.memory_info().rss / (1024 * 1024)
    model_footprint_mb = mem_after_model - mem_after_a

    print(f"Modelo GLiNER cargado en {t_load_end:.2f} ms.")
    print(f"Huella en memoria del modelo (pesos + tensores): {model_footprint_mb:.2f} MB RSS")

    det_b = CompositePIIDetector(
        deterministic_detector=det_a,
        semantic_detector=gliner_b,
    )

    # 3. Evaluate Engine B on Base Dataset
    print("\n[4/4] Evaluando Motor B (Híbrido) en Base y Hold-Out...")
    res_b_base = measure_detector_performance(det_b, base_dataset)
    res_b_holdout = measure_detector_performance(det_b, holdout_dataset)

    # Print reports
    print("\n" + "#" * 80)
    print(" REPORTE DETALLADO: DATASET BASE (15 DOCUMENTOS)")
    print("#" * 80)
    print_report(res_a_base, "CONFIGURACIÓN A: MOTOR DETERMINISTA BASAL (V2.0)")
    print_report(res_b_base, "CONFIGURACIÓN B: MOTOR HÍBRIDO (V2.0 + GLiNER)")

    print("\n" + "#" * 80)
    print(" REPORTE DETALLADO: DATASET INDEPENDIENTE DE HOLDOUT (12 DOCUMENTOS)")
    print("#" * 80)
    print_report(res_a_holdout, "HOLDOUT - CONFIGURACIÓN A: DETERMINISTA")
    print_report(res_b_holdout, "HOLDOUT - CONFIGURACIÓN B: HÍBRIDO CON GLiNER")

    # Save complete audit report
    audit_data = {
        "environment": {
            "base_rss_mb": round(base_rss_mb, 2),
            "model_footprint_rss_mb": round(model_footprint_mb, 2),
            "total_rss_with_model_mb": round(mem_after_model, 2),
            "model_load_time_ms": round(t_load_end, 2)
        },
        "dataset_base": {
            "engine_a_baseline": res_a_base,
            "engine_b_hybrid": res_b_base
        },
        "dataset_holdout": {
            "engine_a_baseline": res_a_holdout,
            "engine_b_hybrid": res_b_holdout
        }
    }

    out_file = Path(__file__).resolve().parent / "ab_comparison_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2, ensure_ascii=False)
    print(f"\nResultados completos de auditoría guardados en: {out_file}")


if __name__ == "__main__":
    run_full_ab_audit()
