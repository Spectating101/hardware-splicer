#!/usr/bin/env python3
"""Analyze one board image and write board/function/AOI understanding JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.ingest import CircuitAnalyzer


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    return value


def _load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, nargs="+", help="Board image(s) to analyze; pass front/back/crops for fusion")
    parser.add_argument("--reference-image", type=Path, default=None, help="Optional golden/reference board image")
    parser.add_argument("--backend", default="hybrid", choices=["auto", "hybrid", "yolo", "classical"], help="Detector backend")
    parser.add_argument("--ocr", action="store_true", help="Enable OCR if available")
    parser.add_argument("--output", type=Path, default=None, help="Output JSON path")
    args = parser.parse_args()

    analyzer = CircuitAnalyzer()
    images = [_load_rgb(path) for path in args.image]
    reference_image = _load_rgb(args.reference_image) if args.reference_image else None
    backend = None if args.backend == "auto" else args.backend
    if len(images) == 1:
        result = analyzer.analyze_pcb(
            images[0],
            backend=backend,
            enable_ocr=args.ocr,
            reference_image=reference_image,
        )
        payload = {
            "images": [str(args.image[0])],
            "summary": analyzer.get_analysis_summary(result),
            "detection_summary": result.get("detection_summary", {}),
            "marking_analysis": result.get("marking_analysis", {}),
            "board_understanding": result.get("board_understanding", {}),
            "machine_connection_map": result.get("machine_connection_map", {}),
            "visual_topology": result.get("visual_topology", {}),
            "defect_inspection": result.get("defect_inspection", {}),
            "golden_aoi": result.get("golden_aoi", {}),
            "aoi_inspection": result.get("aoi_inspection", {}),
            "analysis_metadata": result.get("analysis_metadata", {}),
        }
        default_name = f"{args.image[0].stem}_board_understanding.json"
        summary_text = payload["summary"].get("summary_text", "")
    else:
        result = analyzer.analyze_board_set(
            images,
            backend=backend,
            enable_ocr=args.ocr,
            reference_image=reference_image,
        )
        payload = {
            "images": [str(path) for path in args.image],
            "summary": result.get("summary", ""),
            "fused_board_understanding": result.get("fused_board_understanding", {}),
            "views": [
                {
                    "view_id": view.get("view_id"),
                    "summary": analyzer.get_analysis_summary(view),
                    "detection_summary": view.get("detection_summary", {}),
                    "marking_analysis": view.get("marking_analysis", {}),
                    "board_understanding": view.get("board_understanding", {}),
                    "machine_connection_map": view.get("machine_connection_map", {}),
                    "analysis_metadata": view.get("analysis_metadata", {}),
                }
                for view in result.get("views", [])
            ],
        }
        default_name = f"{args.image[0].stem}_fused_board_understanding.json"
        summary_text = str(payload["summary"])
    output = args.output or Path("eval") / default_name
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(_json_safe(payload), indent=2), encoding="utf-8")
    print(f"Wrote {output}")
    print(summary_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
