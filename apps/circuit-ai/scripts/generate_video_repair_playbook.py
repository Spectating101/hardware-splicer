#!/usr/bin/env python3
"""Generate a reproducible repair playbook from video metadata and optional scan evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.intelligence.repair_video_playbook import RepairVideoPlaybookBuilder


def _markdown(playbook: Dict[str, Any]) -> str:
    source = playbook.get("source_video") or {}
    pattern = playbook.get("video_pattern") or {}
    repair = playbook.get("repair_guide") or {}
    family = repair.get("device_family") or {}
    lines: List[str] = [
        "# Video Repair Playbook",
        "",
        f"Source: {source.get('title') or 'untitled'}",
        f"Channel: {source.get('channel') or 'unknown'}",
        f"URL: {source.get('url') or 'not provided'}",
        "",
        "## Pattern",
        f"- Pattern: {pattern.get('label')} (`{pattern.get('id')}`)",
        f"- Pattern confidence: {pattern.get('confidence')}",
        f"- Circuit-AI device family: {family.get('label')} (`{family.get('id')}`)",
        f"- Can-follow score: {playbook.get('can_follow_score')}",
        f"- Difficulty: {playbook.get('difficulty')}",
        "",
        "## Watch Map",
    ]
    for item in playbook.get("watch_map", []) or []:
        lines.append(f"- {item.get('moment')}: {', '.join(item.get('capture', []))}")
    lines.extend(["", "## Recreation Flow"])
    for step in playbook.get("recreation_flow", []) or []:
        lines.append(f"{step.get('order')}. {step.get('action')}")
        lines.append(f"   - Circuit-AI support: {step.get('circuit_ai_support')}")
        lines.append(f"   - Done when: {step.get('done_when')}")
    lines.extend(["", "## Quality Gates"])
    for gate in playbook.get("quality_gates", []) or []:
        lines.append(f"- {gate}")
    lines.extend(["", "## Copyright Boundary"])
    for item in playbook.get("copyright_boundary", []) or []:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a video-inspired repair playbook")
    parser.add_argument("--title", required=True)
    parser.add_argument("--channel", default="")
    parser.add_argument("--url", default="")
    parser.add_argument("--description", default="")
    parser.add_argument("--observed-action", action="append", default=[])
    parser.add_argument("--analysis", help="optional Circuit-AI analysis JSON")
    parser.add_argument("--symptom", action="append", default=[])
    parser.add_argument("--device-hint", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--markdown-output")
    args = parser.parse_args()

    analysis: Dict[str, Any] = {}
    if args.analysis:
        analysis = json.loads(Path(args.analysis).read_text(encoding="utf-8"))

    playbook = RepairVideoPlaybookBuilder().build(
        {
            "title": args.title,
            "channel": args.channel,
            "url": args.url,
            "description": args.description,
            "observed_actions": args.observed_action,
        },
        analysis=analysis,
        symptoms=args.symptom,
        device_hint=args.device_hint,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(playbook, indent=2), encoding="utf-8")
    print(f"wrote {output}")
    if args.markdown_output:
        markdown_output = Path(args.markdown_output)
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(_markdown(playbook), encoding="utf-8")
        print(f"wrote {markdown_output}")
    print(
        f"{playbook['video_pattern']['label']} | family={playbook['repair_guide']['device_family']['label']} "
        f"| score={playbook['can_follow_score']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
