from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.engines.mechatronic_context import build_mechatronic_context


DEMO_PCB = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo" / "usb_esp32_sensor.kicad_pcb"
DEMO_NET = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo" / "usb_esp32_sensor.net"


def test_build_mechatronic_context_generates_anchor_bundle_and_topology():
    machine = {
        "machine_name": "BenchRig",
        "boards": [
            {"board_id": "main_ctrl", "name": "Main Control"},
            {"board_id": "sensor_io", "name": "Sensor IO", "pcb_outline_mm": [60, 40, 1.6]},
        ],
    }
    board_design_files = {
        "main_ctrl": {"path": str(DEMO_NET), "kind": "netlist"},
        "sensor_io": {"path": str(DEMO_PCB), "kind": "pcb"},
    }

    context = build_mechatronic_context(machine, board_design_files=board_design_files)

    assert context["board_count"] == 2
    assert len(context["electronics_bundle"]) == 2
    assert context["primary_board_id"] in {"main_ctrl", "sensor_io"}

    board_rows = {row["board_id"]: row for row in context["boards"]}
    assert (board_rows["sensor_io"]["prototype3d"] or {}).get("scad")
    assert (board_rows["sensor_io"]["electronics_anchor"] or {}).get("ports")
    assert (board_rows["main_ctrl"]["controller_runtime"] or {}).get("controllers")
    assert "machine_bring_up_sequence" in context
