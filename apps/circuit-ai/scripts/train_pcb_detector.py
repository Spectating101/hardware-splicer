#!/usr/bin/env python3
"""Fine-tune a PCB YOLO detector with provenance and dry-run support."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_yaml_summary(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    summary: dict[str, Any] = {
        "path": str(path),
        "has_train": "train:" in text,
        "has_val": "val:" in text,
        "has_test": "test:" in text,
        "has_names": "names:" in text,
    }
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("nc:"):
            value = stripped.split(":", 1)[1].split("#", 1)[0].strip()
            try:
                summary["class_count"] = int(value)
            except ValueError:
                match = re.search(r"\d+", value)
                summary["class_count"] = int(match.group(0)) if match else value
            break
    return summary


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_last_results_row(run_dir: Path) -> dict[str, Any]:
    results_path = run_dir / "results.csv"
    if not results_path.exists():
        return {}
    with results_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return {}
    latest: dict[str, Any] = {}
    for key, value in rows[-1].items():
        clean_key = key.strip()
        try:
            latest[clean_key] = float(str(value).strip())
        except (TypeError, ValueError):
            latest[clean_key] = value
    return latest


def _training_plan(args: argparse.Namespace, data_yaml: Path, base_model: str) -> dict[str, Any]:
    return {
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "mode": "pcb_detector_finetune",
        "data": _read_yaml_summary(data_yaml),
        "base_model": base_model,
        "output_dir": args.output_dir,
        "run_name": args.name,
        "train_args": {
            "epochs": args.epochs,
            "imgsz": args.imgsz,
            "batch": args.batch,
            "device": args.device,
            "freeze": args.freeze,
            "patience": args.patience,
        },
        "gates": {
            "minimum_map50": args.minimum_map50,
            "target_map50": args.target_map50,
            "notes": [
                "Smoke rankings are not production metrics.",
                "Use a held-out validation split and write model cards before promoting checkpoints.",
                "Do not redistribute source datasets or checkpoints until upstream license terms are verified.",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fine-tune a PCB YOLO detector")
    parser.add_argument("--data-yaml", required=True, help="YOLO data.yaml")
    parser.add_argument("--base-model", default="models/pcb/pcb_components_yolo11n_thawed.pt")
    parser.add_argument("--output-dir", default="pcb_runs/competitive_component_v1")
    parser.add_argument("--name", default="finetune")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--freeze", type=int, default=0)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--minimum-map50", type=float, default=0.65)
    parser.add_argument("--target-map50", type=float, default=0.80)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--plan-output", default="eval/competitive_engine/train_plan.json")
    args = parser.parse_args()

    data_yaml = Path(args.data_yaml)
    if not data_yaml.exists():
        print(f"data yaml not found: {data_yaml}")
        return 2

    base_model_path = Path(args.base_model)
    base_model = str(base_model_path if base_model_path.exists() else args.base_model)
    plan = _training_plan(args, data_yaml, base_model)
    _write_json(Path(args.plan_output), plan)
    print(f"wrote {args.plan_output}")

    if args.dry_run:
        print("dry run only; no training started")
        return 0

    try:
        from ultralytics import YOLO  # type: ignore
    except Exception as exc:
        print(f"ultralytics unavailable: {exc}")
        return 2

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model = YOLO(base_model)
    results = model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=str(output_dir),
        name=args.name,
        freeze=args.freeze,
        patience=args.patience,
    )
    run_dir = Path(getattr(results, "save_dir", output_dir / args.name))
    payload = {
        **plan,
        "result": {
            "save_dir": str(run_dir),
            "metrics": _read_last_results_row(run_dir),
            "weights": {
                "best": str(run_dir / "weights" / "best.pt"),
                "last": str(run_dir / "weights" / "last.pt"),
            },
        },
        "finished_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    _write_json(run_dir / "training_card.json", payload)
    print(f"wrote {run_dir / 'training_card.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
