#!/usr/bin/env python3
"""Emit live photo → donor-board-vision intake (golden RC board photo)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_payload(*, live: bool = True) -> dict:
    photo = ROOT / "tests" / "data" / "golden" / "rc_toy_motor_board.jpg"
    if not photo.is_file():
        raise SystemExit(f"missing golden photo: {photo}")
    return {
        "project_name": "quickstart_live_photo_salvage",
        "goal": "Salvage motor driver from RC toy board photo for robot drive base",
        "salvage_mode": True,
        "donor_board_vision": {
            "enabled": True,
            "live": bool(live),
            "device_hint": "Playmobil RC motor controller PCB",
        },
        "available_parts": [
            {"name": "RC donor board", "type": "donor_board", "condition": "salvaged"},
            {"name": "ESP32", "type": "microcontroller", "condition": "salvaged"},
        ],
        "circuit": {
            "mode": "circuit_board_system",
            "boards": [
                {
                    "board_id": "donor_rc_live",
                    "board_name": "RC toy motor controller (live photo)",
                    "vision_source": {
                        "path": str(photo.resolve()),
                        "live": bool(live),
                        "device_hint": "Playmobil RC motor controller PCB",
                        "symptoms": ["motors do not spin", "board silent on battery"],
                    },
                }
            ],
        },
    }


def main() -> int:
    live = "--offline" not in sys.argv
    print(json.dumps(build_payload(live=live)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
