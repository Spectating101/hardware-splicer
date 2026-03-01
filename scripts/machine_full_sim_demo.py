#!/usr/bin/env python3
"""
Run full-simulation gates for a concrete multi-board machine.

Produces:
- strict=false result (operational without ngspice hard gate)
- strict=true result (requires ngspice + mecha gate pass)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import api_server  # noqa: E402


def _base_machine() -> Dict[str, Any]:
    return {
        "machine_name": "PocketArcade_FullSim",
        "lane": "generic",
        "design_intent": "professional",
        "boards": [
            {
                "board_id": "main_logic",
                "lane": "generic",
                "requirements": {
                    "meta": {"project_name": "Main Logic"},
                    "manufacturing": {"fab": {"name": "JLCPCB"}, "dnp_policy": "explicit"},
                    "board": {"layers": 2},
                    "risk_and_validation": {"what_good_looks_like": "Display + controls responsive"},
                },
            },
            {
                "board_id": "power_stage",
                "lane": "power",
                "requirements": {
                    "meta": {"project_name": "Power Stage"},
                    "manufacturing": {"fab": {"name": "JLCPCB"}, "dnp_policy": "explicit"},
                    "board": {"layers": 2},
                    "power": {
                        "rails": [{"name": "5V", "voltage_v": 5.0, "max_current_a": 1.4}],
                        "sources": [{"name": "VBAT", "voltage_v": 3.7, "max_current_a": 2.0}],
                        "loads": [{"name": "MainRail", "rail": "5V", "current_a": 0.8}],
                    },
                    "risk_and_validation": {"what_good_looks_like": "No brownout"},
                },
            },
        ],
        "interconnects": [
            {"from_board": "power_stage", "to_board": "main_logic", "interface": "power", "length_cm": 8, "wire_awg": "22"},
            {"from_board": "main_logic", "to_board": "power_stage", "interface": "i2c", "length_cm": 10},
        ],
        "power_tree": [
            {"source": "battery", "board_id": "power_stage", "rail": "VBAT", "voltage_v": 3.7, "max_current_a": 2.0},
            {"source": "power_stage", "board_id": "main_logic", "rail": "5V", "voltage_v": 5.0, "max_current_a": 1.4},
        ],
    }


def _mechanism() -> Dict[str, Any]:
    return {
        "project_name": "pocketarcade_fullsim_enclosure",
        "mode": "professional",
        "process": "fdm",
        "enclosure": {
            "name": "pocketarcade_box",
            "inner_w_mm": 140.0,
            "inner_d_mm": 82.0,
            "inner_h_mm": 24.0,
            "wall_mm": 2.6,
            "floor_mm": 2.0,
            "lid_mm": 2.0,
            "clearance_mm": 0.6,
            "lid_style": "screw",
            "fastener": "m3",
            "cutouts": [
                {"kind": "rect", "label": "usb_c", "face": "front", "rect": {"x_mm": 66.0, "y_mm": 7.0, "w_mm": 12.0, "h_mm": 7.0}},
            ],
        },
    }


def _run_once(client: Any, *, strict: bool) -> Dict[str, Any]:
    demo_dir = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo"
    net_main = demo_dir / "usb_esp32_sensor.net"
    net_power = demo_dir / "drone_fc_power.net"
    if not net_main.exists() or not net_power.exists():
        raise SystemExit("Required demo netlists not found in circuit-ai-frontend/public/demo")

    payload = {
        "machine": _base_machine(),
        "mechanism": _mechanism(),
        "board_design_files": {
            "main_logic": {"path": str(net_main), "kind": "netlist"},
            "power_stage": {"path": str(net_power), "kind": "netlist"},
        },
        "strict": bool(strict),
        "simulation_fidelity": "high",
    }
    r = client.post("/api/v2/machines/full-simulate", data=json.dumps(payload), content_type="application/json")
    if r.status_code != 200:
        raise SystemExit(f"full-simulate failed: {r.status_code} {r.get_data(as_text=True)}")
    return r.get_json() or {}


def main() -> int:
    ap = argparse.ArgumentParser(description="Run machine full simulation demo.")
    ap.add_argument(
        "--out",
        default=str(REPO_ROOT / "docs" / "status" / "generated" / "MACHINE_FULL_SIM_DEMO.live.json"),
        help="Output JSON path.",
    )
    args = ap.parse_args()

    client = api_server.app.test_client()
    soft = _run_once(client, strict=False)
    strict = _run_once(client, strict=True)

    out = {
        "soft": soft,
        "strict": strict,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    sres = (soft.get("result") or {})
    tres = (strict.get("result") or {})
    summary = {
        "status": "success",
        "soft_verdict": sres.get("verdict"),
        "strict_verdict": tres.get("verdict"),
        "soft_gates": [{"gate": g.get("gate"), "required": g.get("required"), "passed": g.get("passed")} for g in (sres.get("gates") or [])],
        "strict_gates": [{"gate": g.get("gate"), "required": g.get("required"), "passed": g.get("passed")} for g in (tres.get("gates") or [])],
        "out": str(out_path),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

