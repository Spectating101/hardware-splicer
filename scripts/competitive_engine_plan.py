#!/usr/bin/env python3
"""Write Circuit-AI competitive catch-up plan artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.ml.competitive_engine import build_catchup_plan, markdown_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate competitive engine catch-up plan")
    parser.add_argument("--output-dir", default="eval/competitive_engine")
    parser.add_argument("--doc", default="docs/COMPETITIVE_ENGINE_CATCHUP.md")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    plan = build_catchup_plan(Path(args.root))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "catchup_plan.json"
    json_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    doc_path = Path(args.doc)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(markdown_report(plan), encoding="utf-8")

    print(f"wrote {json_path}")
    print(f"wrote {doc_path}")
    print(f"sources={len(plan['sources'])}")
    print(f"local_training_datasets={len(plan['local_training_datasets'])}")
    print(f"immediate_actions={len(plan['immediate_actions'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
