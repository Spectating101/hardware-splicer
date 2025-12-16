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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from circuit_agent import CircuitAgent  # noqa: E402


async def evaluate(images_dir: Path, labels: dict, mode: str, output: Path):
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
    args = ap.parse_args()

    images_dir = Path(args.images)
    labels = load_labels(Path(args.labels))
    asyncio.run(evaluate(images_dir, labels, args.mode, Path(args.output)))


if __name__ == "__main__":
    main()
