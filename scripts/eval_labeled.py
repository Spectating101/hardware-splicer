#!/usr/bin/env python3
"""
Evaluation harness for labeled images.

Usage:
  python scripts/eval_labeled.py --images path/to/images --labels labels.csv --mode retro|salvage|standard

labels.csv format:
filename,label
image1.jpg,real
image2.jpg,fake

Outputs:
  - eval_results.csv with predictions and detection quality.
"""

import argparse
import csv
import os
import sys
import base64
import asyncio
import json
from pathlib import Path
from collections import Counter
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (str(ROOT), str(SRC)):
    if path not in sys.path:
        sys.path.insert(0, path)

from circuit_agent import CircuitAgent  # noqa: E402


async def evaluate(images_dir: Path, labels: dict, mode: str, output: Path, summary_path: Path | None = None):
    agent = CircuitAgent(knowledge_path="knowledge_base")
    rows = []
    for fname, label in labels.items():
        image_path = images_dir / fname
        if not image_path.exists():
            print(f"Skipping missing file: {fname}")
            continue
        with open(image_path, "rb") as f:
            img_str = base64.b64encode(f.read()).decode()
        resp = await agent.process_request("evaluate", image_b64=img_str, mode=mode)
        det = resp.get("detection_summary", {})
        row = {
            "filename": fname,
            "label": label,
            "detection_count": det.get("count"),
            "detection_quality": det.get("quality"),
            "board_type": None,
            "retro_verdict": None,
        }
        report = resp.get("vision_report", "")
        # crude extraction
        if "Board Type:" in report:
            try:
                line = [l for l in report.splitlines() if "Board Type:" in l][0]
                row["board_type"] = line.replace("Board Type:", "").strip()
            except Exception:
                pass
        if mode == "retro":
            retro = resp.get("vision_report", "")
            if "VERDICT:" in retro:
                row["retro_verdict"] = retro
        rows.append(row)
    with output.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else ["filename", "label"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote results to {output}")

    # Lightweight summary metrics
    if rows:
        quality_counts = Counter([r.get("detection_quality", "none") for r in rows])
        det_counts = [r["detection_count"] for r in rows if r.get("detection_count") is not None]
        avg_det = mean(det_counts) if det_counts else 0
        # crude board match: label substring inside predicted board_type
        # simple normalization for both labels and predicted board types
        def norm(s: str) -> str:
            s = s.lower().replace("_", " ").replace("-", " ").strip()
            if "power distribution" in s or "power supply" in s or "psu" in s:
                return "power supply"
            if "dev board" in s or "devboard" in s:
                return "dev board"
            if "generic pcb board" in s:
                return "generic"
            return s

        matches = 0
        for r in rows:
            bt_raw = r.get("board_type") or ""
            lbl_raw = r.get("label") or ""
            bt_norm = norm(bt_raw)
            lbl_norm = norm(lbl_raw)
            if lbl_norm and bt_norm and (lbl_norm in bt_norm or bt_norm in lbl_norm):
                matches += 1
        summary = {
            "total": len(rows),
            "avg_detection_count": avg_det,
            "quality_counts": quality_counts,
            "board_match_accuracy": matches / len(rows) if rows else 0.0,
        }
        print("Summary:", summary)
        if summary_path:
            summary_path.write_text(json.dumps(summary, indent=2))
            print(f"Wrote summary to {summary_path}")


def load_labels(path: Path) -> dict:
    labels = {}
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            labels[row["filename"]] = row["label"]
    return labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True, help="Folder with images")
    ap.add_argument("--labels", required=True, help="CSV with filename,label")
    ap.add_argument("--mode", default="standard", choices=["standard", "salvage", "retro"])
    ap.add_argument("--output", default="eval_results.csv")
    ap.add_argument("--summary-out", default=None, help="Optional JSON summary output path")
    args = ap.parse_args()

    images_dir = Path(args.images)
    labels = load_labels(Path(args.labels))
    summary_path = Path(args.summary_out) if args.summary_out else None
    asyncio.run(evaluate(images_dir, labels, args.mode, Path(args.output), summary_path))


if __name__ == "__main__":
    main()
