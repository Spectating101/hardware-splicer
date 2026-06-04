#!/usr/bin/env python3
"""
Run a realistic system-engineering demo:
- multi-board machine topology
- mechanism coupling (pan/tilt)
- optimization + simulation outputs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import api_server  # noqa: E402


def build_payload() -> dict:
    return {
        "machine": {
            "machine_name": "PanTilt_Inspector_System",
            "lane": "generic",
            "design_intent": "professional",
            "boards": [
                {
                    "board_id": "main_ctrl",
                    "name": "Main Controller",
                    "lane": "generic",
                    "design_intent": "professional",
                    "estimated_current_a": 0.45,
                    "pcb_outline_mm": [80, 55, 1.6],
                    "capabilities": {"pwm_channels": 8, "stepper_channels": 2, "actuation_current_budget_a": 1.2},
                    "requirements": {
                        "meta": {"project_name": "Main Ctrl"},
                        "manufacturing": {"fab": {"name": "JLCPCB"}, "dnp_policy": "explicit"},
                        "board": {"layers": 2},
                        "risk_and_validation": {"what_good_looks_like": "Controls pan/tilt and streams sensor data"},
                    },
                },
                {
                    "board_id": "sensor_io",
                    "name": "Sensor IO",
                    "lane": "power",
                    "design_intent": "professional",
                    "estimated_current_a": 0.22,
                    "pcb_outline_mm": [50, 35, 1.6],
                    "requirements": {
                        "meta": {"project_name": "Sensor IO"},
                        "manufacturing": {"fab": {"name": "JLCPCB"}, "dnp_policy": "explicit"},
                        "board": {"layers": 2},
                        "power": {
                            "rails": [{"name": "12V", "voltage_v": 12.0, "max_current_a": 0.8}],
                            "sources": [{"name": "VIN", "voltage_v": 12.0, "max_current_a": 1.0}],
                            "loads": [{"name": "SensorArray", "rail": "12V", "current_a": 0.22}],
                        },
                        "risk_and_validation": {"what_good_looks_like": "Stable measurements under movement"},
                    },
                },
                {
                    "board_id": "power_stage",
                    "name": "Power Stage",
                    "lane": "power",
                    "design_intent": "professional",
                    "estimated_current_a": 0.9,
                    "pcb_outline_mm": [70, 45, 1.6],
                    "requirements": {
                        "meta": {"project_name": "Power Stage"},
                        "manufacturing": {"fab": {"name": "JLCPCB"}, "dnp_policy": "explicit"},
                        "board": {"layers": 2},
                        "power": {
                            "rails": [{"name": "12V", "voltage_v": 12.0, "max_current_a": 2.0}],
                            "sources": [{"name": "VIN", "voltage_v": 24.0, "max_current_a": 3.0}],
                            "loads": [{"name": "ActuationRail", "rail": "12V", "current_a": 0.9}],
                        },
                        "risk_and_validation": {"what_good_looks_like": "No brownout during motion spikes"},
                    },
                },
            ],
            "interconnects": [
                {"from_board": "main_ctrl", "to_board": "sensor_io", "interface": "i2c", "length_cm": 25},
                {"from_board": "main_ctrl", "to_board": "power_stage", "interface": "uart", "length_cm": 30},
                {"from_board": "power_stage", "to_board": "main_ctrl", "interface": "power", "length_cm": 22, "wire_awg": "22"},
                {"from_board": "power_stage", "to_board": "sensor_io", "interface": "power", "length_cm": 18, "wire_awg": "24"},
            ],
            "power_tree": [
                {"source": "Battery_24V", "board_id": "power_stage", "rail": "VIN", "voltage_v": 24.0, "max_current_a": 3.0},
                {"source": "power_stage", "board_id": "main_ctrl", "rail": "12V", "voltage_v": 12.0, "max_current_a": 1.2},
                {"source": "power_stage", "board_id": "sensor_io", "rail": "12V", "voltage_v": 12.0, "max_current_a": 0.8},
            ],
            "actuation": {"board_id": "main_ctrl"},
        },
        "mechanism": {
            "project_name": "pan_tilt_inspector_mecha",
            "mode": "professional",
            "process": "fdm",
            "simulation_fidelity": "high",
            "pan_tilt": {
                "name": "pt_inspector",
                "pan_servo": "sg90",
                "tilt_servo": "sg90",
                "base_w_mm": 120.0,
                "base_h_mm": 80.0,
                "base_t_mm": 6.0,
                "bracket_w_mm": 80.0,
                "bracket_h_mm": 70.0,
                "bracket_t_mm": 6.0,
                "platform_w_mm": 60.0,
                "platform_h_mm": 40.0,
                "platform_t_mm": 4.0,
                "max_payload_n": 5.5,
                "payload_offset_mm": 45.0,
            },
        },
        "run_mechanism_sim": True,
        "simulation_fidelity": "high",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Run machine engineering demo.")
    ap.add_argument(
        "--out",
        default=str(REPO_ROOT / "docs" / "status" / "generated" / "MACHINE_ENGINEERING_DEMO.live.json"),
        help="Output JSON report path.",
    )
    args = ap.parse_args()

    client = api_server.app.test_client()
    payload = build_payload()
    r = client.post("/api/v2/machines/engineer", data=json.dumps(payload), content_type="application/json")
    if r.status_code != 200:
        raise SystemExit(f"machines/engineer failed: {r.status_code} {r.get_data(as_text=True)}")

    data = r.get_json() or {}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")

    result = data.get("result") or {}
    analysis = result.get("analysis") or {}
    summary = {
        "status": data.get("status"),
        "verdict": analysis.get("verdict"),
        "placement_improvement_mm": ((analysis.get("placement") or {}).get("improvement_mm")),
        "power_issues": len((analysis.get("power") or {}).get("issues") or []),
        "interconnect_issues": len((analysis.get("interconnects") or {}).get("issues") or []),
        "control_coupling_issues": len((analysis.get("control_coupling") or {}).get("issues") or []),
        "mecha_ok": (analysis.get("mechanism") or {}).get("ok"),
        "mecha_out_dir": (analysis.get("mechanism") or {}).get("out_dir"),
        "report_md_preview": (result.get("report_md") or "")[:800],
        "saved": result.get("saved_artifacts"),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

