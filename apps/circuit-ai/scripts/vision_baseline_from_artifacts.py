#!/usr/bin/env python3
"""Create a no-spend baseline from existing Circuit-AI eval artifacts.

This does not call any model or backend. It summarizes the local analyzer /
current-engine artifacts already checked into eval/ so a Qwen trial can compare
against a concrete baseline.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUTS = [
    ROOT / "eval" / "capability_smoke_fixed" / "summary.json",
    ROOT / "eval" / "rerun_full_product" / "summary.json",
]
OUTPUT = ROOT / "eval" / "qwen_readiness_baseline.json"


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    rows: list[dict[str, Any]] = []
    for entry in data:
        if isinstance(entry, dict):
            rows.append({"artifact": str(path.relative_to(ROOT)), **entry})
    return rows


def numeric(rows: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def average(rows: list[dict[str, Any]], key: str) -> float | None:
    values = numeric(rows, key)
    return round(statistics.fmean(values), 4) if values else None


def weak_case(row: dict[str, Any]) -> bool:
    confidence = row.get("board_confidence")
    detections = row.get("detections")
    ocr_resolved = row.get("ocr_resolved")
    return (
        (isinstance(confidence, (int, float)) and confidence < 0.5)
        or (isinstance(detections, int) and detections <= 3)
        or (isinstance(ocr_resolved, int) and ocr_resolved <= 1)
    )


def main() -> int:
    rows = [row for path in INPUTS for row in load_rows(path)]
    image_rows = [row for row in rows if isinstance(row.get("board_type"), str)]
    weak_rows = [row for row in image_rows if weak_case(row)]
    decisions = Counter(str(row.get("decision")) for row in rows if row.get("decision"))
    readiness = Counter(str(row.get("aoi_readiness")) for row in rows if row.get("aoi_readiness"))

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "method": "existing_artifact_summary_no_model_calls_v1",
        "spend_usd": 0,
        "inputs": [str(path.relative_to(ROOT)) for path in INPUTS],
        "summary": {
            "rows": len(rows),
            "image_rows": len(image_rows),
            "weak_image_rows_for_qwen_trial": len(weak_rows),
            "average_detections": average(image_rows, "detections"),
            "average_connectors": average(image_rows, "connectors"),
            "average_ocr_resolved": average(image_rows, "ocr_resolved"),
            "average_board_confidence": average(image_rows, "board_confidence"),
            "decisions": dict(decisions),
            "aoi_readiness": dict(readiness),
        },
        "weak_cases": [
            {
                "artifact": row.get("artifact"),
                "scenario": row.get("scenario"),
                "board_type": row.get("board_type"),
                "board_confidence": row.get("board_confidence"),
                "detections": row.get("detections"),
                "connectors": row.get("connectors"),
                "ocr_resolved": row.get("ocr_resolved"),
                "aoi_readiness": row.get("aoi_readiness"),
                "why_qwen_should_help": [
                    "direct marking/package reading",
                    "region and connector localization",
                    "damage/test-point visual inspection",
                ],
            }
            for row in weak_rows
        ],
        "qwen_trial_success_bar": {
            "minimum": [
                "Return valid JSON with board_evidence.v1 on every sampled board.",
                "Improve markings/connectors/regions on weak cases without hallucinating pinouts.",
                "Stay under configured VISION_MAX_USD_PER_CALL and VISION_MONTHLY_USD_LIMIT.",
            ],
            "strong": [
                "Raise usable board confidence on weak image rows.",
                "Add salvage_candidates with required_checks grounded in visible evidence.",
                "Expose uncertainty and missing_evidence clearly enough for DeepSeek verification.",
            ],
        },
    }

    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
