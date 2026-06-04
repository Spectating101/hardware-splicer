#!/usr/bin/env python3
"""Write source-backed research radar artifacts for Circuit-AI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.ml.research_radar import build_research_integration_plan, markdown_report
from src.vision.foundation_adapters import build_foundation_assist_plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate research tech radar artifacts")
    parser.add_argument("--output-dir", default="eval/competitive_engine")
    parser.add_argument("--doc", default="docs/RESEARCH_TECH_RADAR.md")
    parser.add_argument("--root", default=".")
    parser.add_argument("--device-hint", default="unknown PCB or electronic gadget")
    parser.add_argument("--goal", default="unknown_electronics_intake")
    parser.add_argument("--symptom", action="append", default=[])
    parser.add_argument("--has-video", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    plan = build_research_integration_plan(root)
    assist_plan = build_foundation_assist_plan(
        device_hint=args.device_hint,
        symptoms=tuple(args.symptom),
        has_video=args.has_video,
        goal=args.goal,
    )
    artifact = {
        "research_plan": plan,
        "foundation_assist_plan": assist_plan,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "research_tech_radar.json"
    json_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    doc_path = Path(args.doc)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(markdown_report(plan), encoding="utf-8")

    available = [
        item["backend_id"]
        for item in assist_plan["backend_statuses"]
        if item.get("available")
    ]
    print(f"wrote {json_path}")
    print(f"wrote {doc_path}")
    print(f"sources={len(plan['sources'])}")
    print(f"lanes={len(plan['lanes'])}")
    print(f"foundation_backends_available={','.join(available) if available else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
