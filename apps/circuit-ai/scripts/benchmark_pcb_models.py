#!/usr/bin/env python3
"""Rank local PCB component detector checkpoints on smoke images."""

from __future__ import annotations

import argparse
import json
import time
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.vision.detector import ComponentDetector
from src.vision.model_resolver import RANKING_FILE, is_model_runtime_available, resolve_pcb_model_paths


DEFAULT_IMAGE_DIRS = ("data/test_images", "assets/samples", "data/raw")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _load_image(path: Path) -> np.ndarray | None:
    try:
        with Image.open(path) as image:
            return np.asarray(image.convert("RGB"))
    except Exception:
        return None


def _iter_images(paths: list[str]) -> list[Path]:
    selected: list[Path] = []
    seen: set[str] = set()
    search_roots = paths or list(DEFAULT_IMAGE_DIRS)
    for raw in search_roots:
        root = Path(raw)
        candidates = [root] if root.is_file() else sorted(root.rglob("*")) if root.exists() else []
        for path in candidates:
            if path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            key = str(path.resolve())
            if key in seen:
                continue
            if _load_image(path) is None:
                continue
            selected.append(path)
            seen.add(key)
    return selected


def _learned_count(detections: list[dict[str, Any]]) -> int:
    count = 0
    for det in detections:
        provenance = det.get("provenance") if isinstance(det.get("provenance"), dict) else {}
        if str(provenance.get("backend", "")).startswith("yolo"):
            count += 1
    return count


def score_model(model_path: str, image_paths: list[Path], limit: int) -> dict[str, Any]:
    detector = ComponentDetector(model_path=model_path)
    per_image: list[dict[str, Any]] = []
    total_time = 0.0

    for path in image_paths[:limit]:
        image = _load_image(path)
        if image is None:
            continue
        processed, _meta = detector.preprocess_image(image, include_metadata=True)
        started = time.perf_counter()
        detections = detector.detect_components(processed, backend="yolo", enable_ocr=False)
        elapsed = time.perf_counter() - started
        total_time += elapsed
        learned = _learned_count(detections)
        classes = sorted({str(det.get("class_name", "unknown")) for det in detections})
        avg_conf = float(np.mean([float(det.get("confidence", 0.0)) for det in detections])) if detections else 0.0
        per_image.append(
            {
                "image": str(path),
                "detections": len(detections),
                "learned_detections": learned,
                "average_confidence": round(avg_conf, 4),
                "classes": classes,
                "elapsed_s": round(elapsed, 4),
            }
        )

    total_detections = sum(item["detections"] for item in per_image)
    learned_detections = sum(item["learned_detections"] for item in per_image)
    avg_confidence = (
        float(np.mean([item["average_confidence"] for item in per_image if item["detections"] > 0]))
        if any(item["detections"] > 0 for item in per_image)
        else 0.0
    )
    detected_images = sum(1 for item in per_image if item["detections"] > 0)
    class_diversity = len({cls for item in per_image for cls in item["classes"]})
    image_count = max(len(per_image), 1)
    hit_rate = detected_images / image_count
    learned_density = learned_detections / max(image_count, 1)
    runtime_penalty = min(total_time / max(image_count, 1), 2.0) / 2.0
    score = (
        0.35 * min(learned_density / 6.0, 1.0)
        + 0.25 * hit_rate
        + 0.25 * avg_confidence
        + 0.10 * min(class_diversity / 8.0, 1.0)
        - 0.05 * runtime_penalty
    )

    return {
        "model_path": model_path,
        "score": round(float(max(0.0, min(score, 1.0))), 4),
        "image_count": len(per_image),
        "detected_images": detected_images,
        "total_detections": int(total_detections),
        "learned_detections": int(learned_detections),
        "average_confidence": round(float(avg_confidence), 4),
        "class_diversity": class_diversity,
        "average_runtime_s": round(float(total_time / image_count), 4),
        "per_image": per_image,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark local PCB detector models")
    parser.add_argument("--image", action="append", default=[], help="image file or directory; repeatable")
    parser.add_argument("--model", action="append", default=[], help="model path; repeatable")
    parser.add_argument("--limit", type=int, default=12, help="max images per model")
    parser.add_argument("--output", default=str(RANKING_FILE), help="ranking JSON output")
    args = parser.parse_args()

    image_paths = _iter_images(args.image)
    if not image_paths:
        print("no readable images found")
        return 2

    requested_model_paths = args.model or resolve_pcb_model_paths(None)
    skipped_model_paths = [path for path in requested_model_paths if not is_model_runtime_available(path)]
    model_paths = [path for path in requested_model_paths if is_model_runtime_available(path)]
    if not model_paths:
        print("no local PCB models found")
        return 2

    rankings = [score_model(model, image_paths, args.limit) for model in model_paths]
    rankings.sort(key=lambda item: item["score"], reverse=True)

    payload = {
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "method": "unlabeled_smoke_rank_v1",
        "limitations": [
            "This is not mAP; use labeled validation data for production qualification.",
            "The ranking estimates practical utility on local sample photos only.",
        ],
        "skipped_models": [
            {"model_path": path, "reason": "runtime dependency unavailable"}
            for path in skipped_model_paths
        ],
        "images": [str(path) for path in image_paths[: args.limit]],
        "rankings": rankings,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {output}")
    for path in skipped_model_paths:
        print(f"skipped {path} runtime dependency unavailable")
    for idx, item in enumerate(rankings, start=1):
        print(
            f"{idx}. {item['model_path']} score={item['score']} "
            f"detections={item['learned_detections']} hit={item['detected_images']}/{item['image_count']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
