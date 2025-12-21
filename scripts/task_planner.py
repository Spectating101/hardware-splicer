#!/usr/bin/env python3
"""
Task planner: generates pick/place/probe JSON tasks from detection summary + checklist.
Intended as a stepping stone toward robot/bench integration.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
for path in (ROOT, SRC):
    if path not in sys.path:
        sys.path.insert(0, path)

from circuit_agent import CircuitAgent  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True, help="Path to image for analysis")
    ap.add_argument("--out", default="task_plan.json", help="Output JSON path")
    ap.add_argument("--mode", default="standard", choices=["standard", "salvage", "retro"])
    args = ap.parse_args()

    if not os.path.exists(args.image):
        raise SystemExit(f"Image not found: {args.image}")

    with open(args.image, "rb") as f:
        import base64
        img_b64 = base64.b64encode(f.read()).decode()

    agent = CircuitAgent(knowledge_path="knowledge_base")
    resp = agent.loop.run_until_complete(agent.process_request("Generate task plan", image_b64=img_b64, mode=args.mode))

    checklist = resp.get("inspection_checklist", {}).get("steps", [])
    det_summary = resp.get("detection_summary", {})
    board_type = resp.get("inspection_checklist", {}).get("board_type", "")

    tasks = []
    for step in checklist:
        tasks.append({
            "type": "inspect",
            "title": step["title"],
            "risk": step["risk"],
            "reason": step["reason"],
            "target": board_type,
        })
    plan = {
        "board_type": board_type,
        "detection_summary": det_summary,
        "tasks": tasks,
        "notes": "Pixel→world mapping and specific coordinates require calibration; this is a logical task plan.",
    }

    Path(args.out).write_text(json.dumps(plan, indent=2))
    print(f"Wrote task plan -> {args.out}")


if __name__ == "__main__":
    main()
