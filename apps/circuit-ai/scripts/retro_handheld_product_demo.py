#!/usr/bin/env python3
"""
Build a concrete product example:
Retro handheld console (original design, Game Boy-like function).

This generates:
- System engineering analysis (multi-board + enclosure mechanics)
- Machine manufacturing package bundle
- Human-readable report of what was built
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import api_server  # noqa: E402


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _product_payload() -> Dict[str, Any]:
    return {
        "machine": {
            "machine_name": "PocketArcade_R1",
            "lane": "generic",
            "design_intent": "professional",
            "boards": [
                {
                    "board_id": "main_logic",
                    "name": "Main Logic Board",
                    "role": "cpu_display_audio",
                    "lane": "generic",
                    "design_intent": "professional",
                    "estimated_current_a": 0.55,
                    "pcb_outline_mm": [92, 58, 1.6],
                    "capabilities": {"pwm_channels": 8, "stepper_channels": 0, "actuation_current_budget_a": 1.0},
                    "requirements": {
                        "meta": {"project_name": "PocketArcade Main Logic"},
                        "manufacturing": {"fab": {"name": "JLCPCB"}, "dnp_policy": "explicit"},
                        "board": {"layers": 4},
                        "risk_and_validation": {"what_good_looks_like": "Boots, drives display, audio output stable"},
                    },
                },
                {
                    "board_id": "controls_audio",
                    "name": "Controls + Audio Board",
                    "role": "buttons_joystick_amplifier",
                    "lane": "generic",
                    "design_intent": "professional",
                    "estimated_current_a": 0.20,
                    "pcb_outline_mm": [72, 38, 1.6],
                    "requirements": {
                        "meta": {"project_name": "PocketArcade Controls Audio"},
                        "manufacturing": {"fab": {"name": "JLCPCB"}, "dnp_policy": "explicit"},
                        "board": {"layers": 2},
                        "risk_and_validation": {"what_good_looks_like": "Buttons + speaker path low noise"},
                    },
                },
                {
                    "board_id": "power_charge",
                    "name": "Power + Charge Board",
                    "role": "battery_charge_regulation",
                    "lane": "power",
                    "design_intent": "professional",
                    "estimated_current_a": 0.95,
                    "pcb_outline_mm": [65, 36, 1.6],
                    "requirements": {
                        "meta": {"project_name": "PocketArcade Power Charge"},
                        "manufacturing": {"fab": {"name": "JLCPCB"}, "dnp_policy": "explicit"},
                        "board": {"layers": 2},
                        "power": {
                            "rails": [{"name": "5V", "voltage_v": 5.0, "max_current_a": 2.0}],
                            "sources": [{"name": "VBAT", "voltage_v": 3.7, "max_current_a": 2.0}],
                            "loads": [{"name": "MainRail", "rail": "5V", "current_a": 0.95}],
                        },
                        "risk_and_validation": {"what_good_looks_like": "No brownout under peak volume/display load"},
                    },
                },
            ],
            "interconnects": [
                {
                    "from_board": "main_logic",
                    "to_board": "controls_audio",
                    "interface": "gpio",
                    "signals": ["BTN_A", "BTN_B", "D_PAD", "START", "SELECT", "GND"],
                    "length_cm": 10,
                },
                {
                    "from_board": "main_logic",
                    "to_board": "controls_audio",
                    "interface": "i2c",
                    "signals": ["SCL", "SDA", "GND"],
                    "length_cm": 12,
                },
                {
                    "from_board": "power_charge",
                    "to_board": "main_logic",
                    "interface": "power",
                    "signals": ["V+", "GND"],
                    "length_cm": 8,
                    "wire_awg": "22",
                },
                {
                    "from_board": "power_charge",
                    "to_board": "controls_audio",
                    "interface": "power",
                    "signals": ["V+", "GND"],
                    "length_cm": 9,
                    "wire_awg": "24",
                },
            ],
            "power_tree": [
                {"source": "Battery_LiIon", "board_id": "power_charge", "rail": "VBAT", "voltage_v": 3.7, "max_current_a": 2.0},
                {"source": "power_charge", "board_id": "main_logic", "rail": "5V", "voltage_v": 5.0, "max_current_a": 1.2},
                {"source": "power_charge", "board_id": "controls_audio", "rail": "5V", "voltage_v": 5.0, "max_current_a": 0.8},
            ],
            "actuation": {"board_id": "main_logic"},
        },
        "mechanism": {
            "project_name": "pocketarcade_r1_enclosure",
            "mode": "professional",
            "process": "fdm",
            "enclosure": {
                "name": "pocketarcade_shell",
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
                    {"kind": "rect", "label": "headphone", "face": "top", "rect": {"x_mm": 10.0, "y_mm": 7.0, "w_mm": 9.0, "h_mm": 7.0}},
                ],
            },
        },
        "run_mechanism_sim": True,
        "simulation_fidelity": "high",
    }


def _render_report(*, engineer_result: Dict[str, Any], build_result: Dict[str, Any], zip_entries: List[str]) -> str:
    result = engineer_result.get("result") or {}
    analysis = result.get("analysis") or {}
    machine = result.get("machine") or {}
    placement = analysis.get("placement") or {}
    power = analysis.get("power") or {}
    inter = analysis.get("interconnects") or {}
    mecha = analysis.get("mechanism") or {}

    lines: List[str] = []
    lines.append("# Retro Handheld Product Demo")
    lines.append("")
    lines.append("- Product concept: `PocketArcade_R1` (original handheld console architecture)")
    lines.append(f"- Generated: `{_utc_now()}`")
    lines.append(f"- System verdict: `{analysis.get('verdict')}`")
    lines.append("")
    lines.append("## What Was Engineered")
    lines.append("- 3-board architecture:")
    lines.append("  - `main_logic`: CPU/display/audio control")
    lines.append("  - `controls_audio`: buttons + joystick + speaker path")
    lines.append("  - `power_charge`: battery, charging, rail distribution")
    lines.append("- 4 board-to-board links (GPIO/I2C/power)")
    lines.append("- Enclosure spec with USB-C and headphone cutouts")
    lines.append("")
    lines.append("## Engineering Results")
    lines.append(f"- Base machine readiness: `{machine.get('readiness_level')}`")
    lines.append(f"- Cable optimization: `{placement.get('before_mm')} mm -> {placement.get('after_mm')} mm` (saved `{placement.get('improvement_mm')} mm`)")
    lines.append(f"- Power simulation issues: `{len(power.get('issues') or [])}`")
    lines.append(f"- Interconnect simulation issues: `{len(inter.get('issues') or [])}`")
    lines.append(f"- Mechanism simulation run: `{mecha.get('ok')}`")
    lines.append(f"- Mechanism findings: `{len(mecha.get('simulation') or [])}` simulation, `{len(mecha.get('dfm') or [])}` DFM")
    lines.append("")
    lines.append("## Product Package Produced")
    lines.append(f"- Machine ZIP: `{build_result.get('machine_package_file')}`")
    lines.append(f"- Board package count: `{len(build_result.get('board_packages') or [])}`")
    lines.append(f"- ZIP entries: `{len(zip_entries)}`")
    lines.append("- Key bundle artifacts:")
    for name in ("MACHINE_MANIFEST.json", "MACHINE_HINTS.json", "SYSTEM_SOW.md", "HARNESS_BOM.csv"):
        lines.append(f"  - `{name}`: `{'yes' if name in zip_entries else 'no'}`")
    lines.append("")
    lines.append("## Notes")
    lines.append("- This is a digital engineering prototype package (design/simulation/manufacturing artifacts).")
    lines.append("- Not a cloned Nintendo product; original architecture with similar functional class.")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Run retro handheld product demo.")
    ap.add_argument(
        "--json-out",
        default=str(REPO_ROOT / "docs" / "status" / "generated" / "RETRO_HANDHELD_PRODUCT_DEMO.live.json"),
        help="Output JSON path.",
    )
    ap.add_argument(
        "--md-out",
        default=str(REPO_ROOT / "docs" / "status" / "generated" / "RETRO_HANDHELD_PRODUCT_DEMO.live.md"),
        help="Output markdown path.",
    )
    args = ap.parse_args()

    payload = _product_payload()
    client = api_server.app.test_client()

    engineer_resp = client.post("/api/v2/machines/engineer", data=json.dumps(payload), content_type="application/json")
    if engineer_resp.status_code != 200:
        raise SystemExit(f"machines/engineer failed: {engineer_resp.status_code} {engineer_resp.get_data(as_text=True)}")
    engineer_data = engineer_resp.get_json() or {}

    demo_dir = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo"
    pcb_a = demo_dir / "usb_esp32_sensor.kicad_pcb"
    net_a = demo_dir / "usb_esp32_sensor.net"
    pcb_b = demo_dir / "drone_fc_power.kicad_pcb"
    net_b = demo_dir / "drone_fc_power.net"
    if not pcb_a.exists() or not pcb_b.exists():
        raise SystemExit("Demo PCB files missing in circuit-ai-frontend/public/demo")

    machine_json = {
        "machine_name": "PocketArcade_R1",
        "boards": [
            {"board_id": "main_logic"},
            {"board_id": "controls_audio"},
            {"board_id": "power_charge"},
        ],
        "interconnects": payload["machine"]["interconnects"],
        "power_tree": payload["machine"]["power_tree"],
    }
    with pcb_a.open("rb") as f_main, pcb_a.open("rb") as f_ctrl, pcb_b.open("rb") as f_pow, net_a.open("rb") as n_main, net_b.open("rb") as n_pow:
        build_resp = client.post(
            "/api/v2/machines/build-package",
            data={
                "machine_json": json.dumps(machine_json),
                "pcb_file_main_logic": (f_main, "main_logic.kicad_pcb"),
                "pcb_file_controls_audio": (f_ctrl, "controls_audio.kicad_pcb"),
                "pcb_file_power_charge": (f_pow, "power_charge.kicad_pcb"),
                "netlist_file_main_logic": (n_main, "main_logic.net"),
                "netlist_file_power_charge": (n_pow, "power_charge.net"),
            },
            content_type="multipart/form-data",
        )
    if build_resp.status_code != 200:
        raise SystemExit(f"machines/build-package failed: {build_resp.status_code} {build_resp.get_data(as_text=True)}")
    build_data = build_resp.get_json() or {}

    zip_entries: List[str] = []
    zip_path = Path(str(build_data.get("machine_package_file") or ""))
    if zip_path.exists():
        with zipfile.ZipFile(zip_path, "r") as zf:
            zip_entries = sorted(zf.namelist())

    out_json = Path(args.json_out)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps({"engineer": engineer_data, "build_package": build_data, "zip_entries": zip_entries}, indent=2), encoding="utf-8")

    report = _render_report(engineer_result=engineer_data, build_result=build_data, zip_entries=zip_entries)
    out_md = Path(args.md_out)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(report, encoding="utf-8")

    summary = {
        "status": "success",
        "engineer_verdict": ((engineer_data.get("result") or {}).get("analysis") or {}).get("verdict"),
        "machine_package_file": build_data.get("machine_package_file"),
        "report_md": str(out_md),
        "report_json": str(out_json),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
