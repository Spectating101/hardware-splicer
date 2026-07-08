#!/usr/bin/env python3
"""Emit POST /v1/compose/agent-loop JSON for robot-drive salvage quickstart."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.project_intake import _donor_context_from_intake, load_project_intake

INTAKE_PATH = ROOT / "examples" / "intakes" / "splice_robot_drive_brief.json"


def build_payload(*, project_name: str = "quickstart_salvage") -> dict:
    intake = load_project_intake(INTAKE_PATH)
    return {
        "goal": intake["goal"],
        "parts": intake["available_parts"],
        "constraints": intake.get("constraints") or {},
        "donor_context": _donor_context_from_intake(intake),
        "salvage_mode": True,
        "allow_llm_first": False,
        "max_manual_retries": 1,
        "finalize_package": True,
        "project_name": project_name,
        "export_gerber": False,
    }


def main() -> None:
    json.dump(build_payload(), sys.stdout)


if __name__ == "__main__":
    main()
