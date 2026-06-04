#!/usr/bin/env python3
"""Evaluate golden-reference localization on a DeepPCB subset manifest."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.vision.golden_reference import GoldenReferenceInspector


def _load(path: str):
    image = cv2.imread(path, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"could not read image: {path}")
    return image


def _iou(box_a: list[int], box_b: list[int]) -> float:
    ax1, ay1, ax2, ay2 = [float(value) for value in box_a]
    bx1, by1, bx2, by2 = [float(value) for value in box_b]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def evaluate(manifest_path: Path, output_path: Path, iou_threshold: float, diff_threshold: int) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    inspector = GoldenReferenceInspector(diff_threshold=diff_threshold)
    rows: list[dict[str, Any]] = []
    tp = fp = fn = 0

    for sample in manifest.get("samples", []):
        template = _load(sample["template"])
        image = _load(sample["image"])
        result = inspector.compare(template, image)
        predictions = result.get("defects", []) or []
        annotations = sample.get("annotations", []) or []
        matched_predictions: set[int] = set()
        matched_annotations: set[int] = set()

        for ann_idx, annotation in enumerate(annotations):
            ann_box = annotation["bbox"]
            best_idx = None
            best_iou = 0.0
            for pred_idx, pred in enumerate(predictions):
                if pred_idx in matched_predictions:
                    continue
                pred_iou = _iou(ann_box, pred.get("bbox", [0, 0, 0, 0]))
                if pred_iou > best_iou:
                    best_iou = pred_iou
                    best_idx = pred_idx
            if best_idx is not None and best_iou >= iou_threshold:
                matched_annotations.add(ann_idx)
                matched_predictions.add(best_idx)

        sample_tp = len(matched_annotations)
        sample_fn = max(0, len(annotations) - sample_tp)
        sample_fp = max(0, len(predictions) - len(matched_predictions))
        tp += sample_tp
        fn += sample_fn
        fp += sample_fp
        rows.append(
            {
                "sample_id": sample.get("sample_id"),
                "annotation_count": len(annotations),
                "prediction_count": len(predictions),
                "true_positive": sample_tp,
                "false_positive": sample_fp,
                "false_negative": sample_fn,
                "golden_status": result.get("status"),
                "change_area_ratio": result.get("change_area_ratio"),
            }
        )

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    payload = {
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "iou_threshold": iou_threshold,
        "diff_threshold": diff_threshold,
        "metrics": {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "precision": round(float(precision), 4),
            "recall": round(float(recall), 4),
            "sample_count": len(rows),
        },
        "samples": rows,
        "limitations": [
            "Golden diff is a change localizer, not a class-specific trained DeepPCB detector.",
            "Use this to qualify alignment/defect-region sensitivity before training a defect model.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate DeepPCB golden diff localization")
    parser.add_argument("--manifest", default="datasets/deeppcb_subset/manifest.json")
    parser.add_argument("--output", default="eval/deeppcb_golden_eval.json")
    parser.add_argument("--iou-threshold", type=float, default=0.1)
    parser.add_argument("--diff-threshold", type=int, default=48)
    args = parser.parse_args()

    payload = evaluate(Path(args.manifest), Path(args.output), args.iou_threshold, args.diff_threshold)
    metrics = payload["metrics"]
    print(f"wrote {args.output}")
    print(
        "precision={precision:.3f} recall={recall:.3f} tp={true_positive} fp={false_positive} fn={false_negative}".format(
            **metrics
        )
    )
    return 0 if metrics["recall"] >= 0.70 else 1


if __name__ == "__main__":
    raise SystemExit(main())
