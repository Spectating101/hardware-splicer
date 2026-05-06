#!/usr/bin/env python3
"""Evaluate golden-image AOI and defect candidates on a labeled sample set."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.vision.defect_detector import DefectDetector
from src.vision.golden_reference import GoldenReferenceInspector


def _load_image(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"could not read image: {path}")
    return image


def _read_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not isinstance(payload.get("samples"), list):
        raise ValueError("manifest must contain samples[]")
    return payload


def _matches_expected(detected_types: set[str], expected: list[str]) -> bool:
    if not expected:
        return not detected_types
    return bool(detected_types.intersection(expected))


def evaluate(manifest_path: Path, output_path: Path, confidence_threshold: float) -> dict[str, Any]:
    manifest = _read_manifest(manifest_path)
    root = manifest_path.parent
    golden_path = root / str(manifest["golden_image"])
    golden = _load_image(golden_path)
    golden_inspector = GoldenReferenceInspector()
    defect_detector = DefectDetector(use_classical_fallback=True)

    rows: list[dict[str, Any]] = []
    tp = fp = fn = tn = 0
    golden_failures = 0

    for sample in manifest["samples"]:
        image_path = root / str(sample["image"])
        expected = [str(item) for item in sample.get("expected_defects", [])]
        image = _load_image(image_path)

        golden_result = golden_inspector.compare(golden, image)
        golden_types = {str(item.get("defect_type")) for item in golden_result.get("defects", [])}
        if golden_result.get("status") == "FAIL":
            golden_types.add("golden_mismatch")
        classical_defects = defect_detector.detect_defects(image, confidence_threshold=confidence_threshold)
        classical_types = {str(item.defect_type) for item in classical_defects}

        detected_positive = bool(golden_types) or bool(classical_types)
        expected_positive = bool(expected)
        class_match = _matches_expected(golden_types | classical_types, expected)
        if expected_positive and detected_positive and class_match:
            tp += 1
        elif expected_positive and not class_match:
            fn += 1
        elif not expected_positive and detected_positive:
            fp += 1
        else:
            tn += 1

        if golden_result.get("status") == "FAIL":
            golden_failures += 1

        rows.append(
            {
                "image": str(image_path),
                "expected_defects": expected,
                "golden_status": golden_result.get("status"),
                "golden_defect_types": sorted(golden_types),
                "golden_defect_count": golden_result.get("defect_count", 0),
                "classical_defect_types": sorted(classical_types),
                "classical_defect_count": len(classical_defects),
                "class_match": bool(class_match),
            }
        )

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    false_positive_rate = fp / max(fp + tn, 1)
    payload = {
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "golden_image": str(golden_path),
        "confidence_threshold": confidence_threshold,
        "metrics": {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "true_negative": tn,
            "precision": round(float(precision), 4),
            "recall": round(float(recall), 4),
            "false_positive_rate": round(float(false_positive_rate), 4),
            "golden_failures": golden_failures,
            "sample_count": len(rows),
        },
        "samples": rows,
        "limitations": [
            "Synthetic image set verifies pipeline mechanics, not real factory accuracy.",
            "Use line-specific labeled photos for final production thresholds.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate golden-image defect AOI")
    parser.add_argument(
        "--manifest",
        default="tests/data/defect_samples/manifest.json",
        help="defect sample manifest JSON",
    )
    parser.add_argument(
        "--output",
        default="eval/golden_defect_eval.json",
        help="output metrics JSON",
    )
    parser.add_argument("--confidence-threshold", type=float, default=0.65)
    args = parser.parse_args()

    payload = evaluate(Path(args.manifest), Path(args.output), args.confidence_threshold)
    metrics = payload["metrics"]
    print(f"wrote {args.output}")
    print(
        "precision={precision:.3f} recall={recall:.3f} fpr={false_positive_rate:.3f} "
        "tp={true_positive} fp={false_positive} fn={false_negative} tn={true_negative}".format(**metrics)
    )
    return 0 if metrics["recall"] >= 0.75 and metrics["false_positive_rate"] <= 0.25 else 1


if __name__ == "__main__":
    raise SystemExit(main())
