"""
Fase 2 benchmark: false-positive reduction on institutional / administrative documents.

Reuses `evaluate_detector` (same overlap-based matching and integrity checks as Fase 0/1) and adds:
- provenance of every prediction (deterministic / semantic / dual) taken from `validation_details`;
- preservation violations: predictions overlapping expressions that must be kept;
- ambiguous spans reported separately (never counted in TP/FP/FN);
- a before/after comparison listing corrected cases and regressions.

Usage:
    PYTHONPATH=. python tests/benchmark/run_fp_benchmark.py run --label after [--gliner] [--out FILE]
    PYTHONPATH=. python tests/benchmark/run_fp_benchmark.py compare BEFORE.json AFTER.json

`run --out` refuses to overwrite an existing file, so saved reference results stay immutable.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from anondoc.domain.entities import PIIEntity
from anondoc.domain.interfaces import IPIIDetector
from tests.benchmark.run_benchmark import evaluate_detector, spans_overlap

BENCH_DIR = Path(__file__).resolve().parent
DATASETS = {
    "fp_tuning": BENCH_DIR / "dataset_fp_tuning.jsonl",
    "fp_holdout": BENCH_DIR / "dataset_fp_holdout.jsonl",
    "person_fp": BENCH_DIR / "dataset_person_fp.jsonl",
    "phase0": BENCH_DIR / "dataset.jsonl",
    "phase1_holdout": BENCH_DIR / "dataset_eval_holdout.jsonl",
}


def entity_layer(entity: PIIEntity) -> str:
    """Layer that produced an entity, derived from the existing `validation_details` markers."""
    details = entity.validation_details or ""
    if details.startswith("GLiNER"):
        return "semantic"
    if details.startswith("Confirmación dual"):
        return "dual"
    return "deterministic"


class _RecordingDetector(IPIIDetector):
    """Transparent wrapper that keeps the predictions made for each document, in call order."""

    def __init__(self, inner: IPIIDetector):
        self.inner = inner
        self.calls: List[List[PIIEntity]] = []

    def detect_entities(self, text_blocks):
        entities = self.inner.detect_entities(text_blocks)
        self.calls.append(list(entities))
        return entities


def _overlaps(entity: PIIEntity, span: Dict[str, Any]) -> bool:
    return spans_overlap(entity.start_char, entity.end_char, span["start_char"], span["end_char"])


def evaluate_dataset(detector: IPIIDetector, path: Path) -> Dict[str, Any]:
    recorder = _RecordingDetector(detector)
    result = evaluate_detector(recorder, path)
    docs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    index_by_id = {doc["id"]: i for i, doc in enumerate(docs)}

    for fp in result["false_positives"]:
        doc_idx = index_by_id[fp["doc_id"]]
        match = next(
            (e for e in recorder.calls[doc_idx]
             if (e.start_char, e.end_char) == tuple(fp["span"]) and e.category.value == fp["category"]),
            None,
        )
        fp["layer"] = entity_layer(match) if match else "unknown"
        fp["rule"] = (match.validation_details or "")[:60] if match else ""

    violations, ambiguous_hits = [], []
    for doc, predictions in zip(docs, recorder.calls):
        for span in doc.get("preserve", []):
            for e in predictions:
                if _overlaps(e, span):
                    violations.append({
                        "doc_id": doc["id"], "preserved": span["text"], "category": e.category.value,
                        "text": e.original_text, "layer": entity_layer(e),
                    })
        for span in doc.get("ambiguous", []):
            hits = [e for e in predictions if _overlaps(e, span)]
            ambiguous_hits.append({
                "doc_id": doc["id"], "text": span["text"],
                "detected_as": [f"{e.category.value}:{e.original_text}" for e in hits],
            })

    result["preservation_violations"] = violations
    result["ambiguous"] = ambiguous_hits
    result["person"] = result["by_category"].get("PERSON", {})
    return result


def build_detector(use_gliner: bool) -> IPIIDetector:
    from anondoc.infrastructure.detection.pii_detector import HybridPIIDetector
    if not use_gliner:
        return HybridPIIDetector()
    from anondoc.infrastructure.detection.composite_detector import CompositePIIDetector
    from anondoc.infrastructure.detection.gliner_detector import GLiNERDetector
    gliner = GLiNERDetector()
    if not gliner.is_ready:
        raise SystemExit("GLiNER no está disponible en este entorno.")
    return CompositePIIDetector(semantic_detector=gliner)


def cmd_run(args: argparse.Namespace) -> None:
    detector = build_detector(args.gliner)
    report = {"label": args.label, "detector": "composite_gliner" if args.gliner else "deterministic", "datasets": {}}
    for name, path in DATASETS.items():
        res = evaluate_dataset(detector, path)
        report["datasets"][name] = res
        s = res["summary"]
        print(
            f"[{name}] P={s['precision']:.4f} R={s['recall']:.4f} F1={s['f1_score']:.4f} "
            f"TP={s['total_tp']} FP={s['total_fp']} FN={s['total_fn']} FP/1000w={s['fp_per_1000_words']} "
            f"PERSON(fp={res['person'].get('fp', 0)}, fn={res['person'].get('fn', 0)}) "
            f"preservation_violations={len(res['preservation_violations'])}"
        )
    if args.out:
        out = Path(args.out)
        if out.exists():
            raise SystemExit(f"{out} ya existe: los resultados de referencia son inmutables.")
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Guardado en {out}")


def _keys(items: List[Dict[str, Any]], fields: Tuple[str, ...]) -> set:
    return {tuple(item[f] for f in fields) for item in items}


def cmd_compare(args: argparse.Namespace) -> None:
    before = json.loads(Path(args.before).read_text(encoding="utf-8"))
    after = json.loads(Path(args.after).read_text(encoding="utf-8"))
    print(f"Comparación {before['label']} -> {after['label']} (detector {after['detector']})")
    for name, b in before["datasets"].items():
        a = after["datasets"][name]
        bs, as_ = b["summary"], a["summary"]
        print(f"\n== {name} ==")
        for key in ("precision", "recall", "f1_score", "total_tp", "total_fp", "total_fn", "fp_per_1000_words"):
            print(f"  {key:<18} {bs[key]:>8} -> {as_[key]:>8}")
        print(f"  PERSON fp/fn       {b['person'].get('fp', 0)}/{b['person'].get('fn', 0)} -> "
              f"{a['person'].get('fp', 0)}/{a['person'].get('fn', 0)}")
        print(f"  preservation viol. {len(b['preservation_violations'])} -> {len(a['preservation_violations'])}")
        fp_f = ("doc_id", "category", "text")
        fixed = _keys(b["false_positives"], fp_f) - _keys(a["false_positives"], fp_f)
        new_fp = _keys(a["false_positives"], fp_f) - _keys(b["false_positives"], fp_f)
        new_fn = _keys(a["false_negatives"], fp_f) - _keys(b["false_negatives"], fp_f)
        fixed_fn = _keys(b["false_negatives"], fp_f) - _keys(a["false_negatives"], fp_f)
        print(f"  FP corregidos: {len(fixed)} | FP nuevos: {len(new_fp)} | FN nuevos (regresiones): {len(new_fn)} | FN corregidos: {len(fixed_fn)}")
        if args.verbose:
            for label, items in (("FP corregido", fixed), ("FP nuevo", new_fp), ("FN NUEVO", new_fn), ("FN corregido", fixed_fn)):
                for item in sorted(items):
                    print(f"    {label}: {item}")


def main(argv: List[str]) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--label", required=True)
    run.add_argument("--gliner", action="store_true")
    run.add_argument("--out")
    run.set_defaults(func=cmd_run)
    cmp_ = sub.add_parser("compare")
    cmp_.add_argument("before")
    cmp_.add_argument("after")
    cmp_.add_argument("-v", "--verbose", action="store_true")
    cmp_.set_defaults(func=cmd_compare)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
