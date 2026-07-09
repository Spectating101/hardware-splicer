#!/usr/bin/env python3
"""Emit POST /v1/donor-board-vision intake for offline photo→salvage quickstart."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.project_intake import load_project_intake


def build_payload() -> dict:
    intake_path = ROOT / "examples" / "intakes" / "splice_robot_drive_vision_brief.json"
    intake = load_project_intake(intake_path)
    # Ensure offline board_evidence path (no live Qwen required)
    intake.setdefault("donor_board_vision", {})
    intake["donor_board_vision"]["enabled"] = True
    intake["donor_board_vision"]["live"] = False
    return intake


def main() -> int:
    print(json.dumps(build_payload()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
