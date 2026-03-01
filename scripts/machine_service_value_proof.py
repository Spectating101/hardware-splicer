#!/usr/bin/env python3
"""
Run an end-to-end multi-board machine proof and emit a monetization-focused report.

This script uses Flask's in-process test client:
1) Compile a machine spec (boards + interconnects + power tree)
2) Build a machine package from multiple PCB uploads
3) Inspect produced ZIP artifacts
4) Write a report that translates technical outputs into service SKU value
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import api_server  # noqa: E402


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scenario_payload() -> Dict[str, Any]:
    return {
        "machine_name": "BenchBot_Controller_Stack",
        "lane": "generic",
        "design_intent": "professional",
        "boards": [
            {
                "board_id": "main_ctrl",
                "name": "Main Control Board",
                "role": "compute_and_control",
                "lane": "generic",
                "design_intent": "professional",
                "requirements": {
                    "meta": {"project_name": "BenchBot Main Control"},
                    "manufacturing": {"fab": {"name": "JLCPCB"}},
                    "risk_and_validation": {"what_good_looks_like": "System boots + controls peripherals"},
                },
                "pcb_outline_mm": [85, 55, 1.6],
            },
            {
                "board_id": "sensor_io",
                "name": "Sensor and IO Board",
                "role": "sensor_frontend",
                "lane": "power",
                "design_intent": "professional",
                "requirements": {
                    "meta": {"project_name": "BenchBot Sensor IO"},
                    "manufacturing": {"fab": {"name": "JLCPCB"}},
                    "board": {"layers": 2},
                    "risk_and_validation": {"what_good_looks_like": "Stable sensor reads at target sample rate"},
                },
                "pcb_outline_mm": [60, 40, 1.6],
            },
            {
                "board_id": "power_stage",
                "name": "Power Stage Board",
                "role": "power_distribution",
                "lane": "power",
                "design_intent": "professional",
                "requirements": {
                    "meta": {"project_name": "BenchBot Power Stage"},
                    "manufacturing": {"fab": {"name": "JLCPCB"}},
                    "board": {"layers": 2},
                    "power": {
                        "rails": [{"name": "12V", "voltage_v": 12.0, "max_current_a": 3.0}],
                        "sources": [{"name": "VIN", "voltage_v": 24.0, "max_current_a": 3.0}],
                        "loads": [{"name": "MotorDriver", "rail": "12V", "current_a": 1.2}],
                    },
                    "risk_and_validation": {"what_good_looks_like": "No brownout at nominal load"},
                },
                "pcb_outline_mm": [70, 45, 1.6],
            },
        ],
        "interconnects": [
            {
                "from_board": "main_ctrl",
                "to_board": "sensor_io",
                "interface": "i2c",
                "signals": ["SCL", "SDA", "GND"],
                "connector": "JST-XH-4",
                "length_cm": 20,
            },
            {
                "from_board": "main_ctrl",
                "to_board": "power_stage",
                "interface": "uart",
                "signals": ["TX", "RX", "GND"],
                "connector": "JST-XH-4",
                "length_cm": 25,
            },
            {
                "from_board": "power_stage",
                "to_board": "sensor_io",
                "interface": "power",
                "signals": ["V+", "GND"],
                "connector": "JST-VH-2",
                "length_cm": 15,
                "from_voltage_v": 12.0,
                "to_voltage_v": 12.0,
            },
        ],
        "power_tree": [
            {"source": "Battery_24V", "board_id": "power_stage", "rail": "VIN", "voltage_v": 24.0, "max_current_a": 3.0},
            {"source": "power_stage:12V", "board_id": "main_ctrl", "rail": "VIN", "voltage_v": 12.0, "max_current_a": 1.0},
            {"source": "power_stage:12V", "board_id": "sensor_io", "rail": "VIN", "voltage_v": 12.0, "max_current_a": 0.8},
        ],
    }


def _hardened_payload() -> Dict[str, Any]:
    payload = _scenario_payload()
    boards = payload.get("boards") or []
    by_id: Dict[str, Dict[str, Any]] = {}
    for b in boards:
        if isinstance(b, dict):
            bid = str(b.get("board_id") or "").strip()
            if bid:
                by_id[bid] = b

    main_req = (((by_id.get("main_ctrl") or {}).get("requirements")) or {})
    if isinstance(main_req, dict):
        main_req.setdefault("board", {})["layers"] = 2
        main_req.setdefault("manufacturing", {})["dnp_policy"] = "explicit"

    sensor_req = (((by_id.get("sensor_io") or {}).get("requirements")) or {})
    if isinstance(sensor_req, dict):
        sensor_req.setdefault("manufacturing", {})["dnp_policy"] = "explicit"
        sensor_req["power"] = {
            "rails": [{"name": "12V", "voltage_v": 12.0, "max_current_a": 0.8}],
            "sources": [{"name": "VIN", "voltage_v": 12.0, "max_current_a": 1.0}],
            "loads": [{"name": "SensorArray", "rail": "12V", "current_a": 0.35}],
        }

    power_req = (((by_id.get("power_stage") or {}).get("requirements")) or {})
    if isinstance(power_req, dict):
        power_req.setdefault("manufacturing", {})["dnp_policy"] = "explicit"

    return payload


def _machine_pricing_snapshot(board_count: int, interconnect_count: int) -> Dict[str, Any]:
    starter = 120 + (90 * board_count) + (25 * interconnect_count)
    standard = 250 + (140 * board_count) + (40 * interconnect_count)
    premium = 480 + (220 * board_count) + (70 * interconnect_count)
    return {
        "starter_usd": starter,
        "standard_usd": standard,
        "premium_usd": premium,
        "notes": [
            "Starter: architecture + compile artifacts + open questions",
            "Standard: includes full machine package + board-level manifests",
            "Premium: includes integration risk memo + revision-ready handoff",
        ],
    }


def _render_report(
    *,
    compile_baseline_result: Dict[str, Any],
    compile_hardened_result: Dict[str, Any],
    package_result: Dict[str, Any],
    zip_entries: List[str],
    pricing: Dict[str, Any],
) -> str:
    machine = compile_hardened_result.get("machine") or {}
    system = compile_hardened_result.get("system") or {}
    boards = compile_hardened_result.get("boards") or []
    readiness = machine.get("readiness_level")
    board_count = machine.get("board_count")
    interconnect_count = machine.get("interconnect_count")
    blockers = machine.get("blockers") or []
    risks = system.get("risks") or []
    questions = system.get("questions") or []
    baseline_machine = compile_baseline_result.get("machine") or {}
    baseline_boards = compile_baseline_result.get("boards") or []
    hardened_boards = boards

    lines: List[str] = []
    lines.append("# Multi-Board Service Value Proof")
    lines.append("")
    lines.append(f"- Generated (UTC): `{_utc_now()}`")
    lines.append(f"- Machine: `{machine.get('machine_name')}`")
    lines.append(f"- Readiness: `{readiness}`")
    lines.append(f"- Board count: `{board_count}`")
    lines.append(f"- Interconnect count: `{interconnect_count}`")
    lines.append("")
    lines.append("## Technical Proof")
    lines.append(f"- `/api/v2/machines/compile` baseline: success")
    lines.append(f"- `/api/v2/machines/compile` hardened: success")
    lines.append(f"- `/api/v2/machines/build-package`: success")
    lines.append(f"- Machine package path: `{package_result.get('machine_package_file')}`")
    lines.append(f"- Board packages generated: `{len(package_result.get('board_packages') or [])}`")
    lines.append(f"- ZIP entries: `{len(zip_entries)}`")
    lines.append("")
    lines.append("## Integration Artifacts Found")
    for k in ("MACHINE_MANIFEST.json", "MACHINE_HINTS.json", "SYSTEM_SOW.md", "HARNESS_BOM.csv"):
        present = "yes" if k in zip_entries else "no"
        lines.append(f"- `{k}` present: `{present}`")
    lines.append("")
    lines.append("## Iteration Uplift")
    lines.append(f"- Baseline readiness: `{baseline_machine.get('readiness_level')}`")
    lines.append(f"- Hardened readiness: `{machine.get('readiness_level')}`")
    for b0 in baseline_boards:
        bid = b0.get("board_id")
        b1 = next((x for x in hardened_boards if x.get("board_id") == bid), {})
        q0 = b0.get("quality") or {}
        q1 = b1.get("quality") or {}
        lines.append(
            f"- `{bid}` quality: `{q0.get('grade')}:{q0.get('score')}` -> `{q1.get('grade')}:{q1.get('score')}`"
        )
    lines.append("")
    lines.append("## Board-Level Snapshot")
    for b in boards:
        q = b.get("quality") or {}
        lines.append(
            f"- `{b.get('board_id')}` lane=`{b.get('lane')}` intent=`{b.get('design_intent')}` readiness=`{b.get('readiness_level')}` quality=`{q.get('grade')}:{q.get('score')}`"
        )
    lines.append("")
    lines.append("## Unresolved Items")
    if blockers:
        for item in blockers[:20]:
            lines.append(f"- blocker: {item}")
    else:
        lines.append("- blocker: none")
    if risks:
        for item in risks[:20]:
            lines.append(f"- risk: {item}")
    else:
        lines.append("- risk: none")
    if questions:
        for item in questions[:20]:
            lines.append(f"- question: {item}")
    else:
        lines.append("- question: none")
    lines.append("")
    lines.append("## Service Monetization Snapshot")
    lines.append(f"- Starter package: `${pricing['starter_usd']}/project`")
    lines.append(f"- Standard package: `${pricing['standard_usd']}/project`")
    lines.append(f"- Premium package: `${pricing['premium_usd']}/project`")
    lines.append("- Revision upsell angle: baseline compile exposes blockers; paid revision closes them and increases machine readiness.")
    lines.append("- Why this is higher-value than single PCB:")
    lines.append("  - one system scope with multiple boards and explicit interconnect contracts")
    lines.append("  - one bundled machine deliverable with per-board manufacturing artifacts")
    lines.append("  - direct EE->ME bridge fields for enclosure/mechanics handoff")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate multi-board machine value proof report.")
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "docs" / "status" / "generated" / "MULTIBOARD_SERVICE_VALUE_PROOF.live.md"),
        help="Output markdown report path.",
    )
    args = parser.parse_args()

    demo_dir = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo"
    main_pcb = demo_dir / "usb_esp32_sensor.kicad_pcb"
    main_net = demo_dir / "usb_esp32_sensor.net"
    power_pcb = demo_dir / "drone_fc_power.kicad_pcb"
    power_net = demo_dir / "drone_fc_power.net"
    if not main_pcb.exists() or not power_pcb.exists():
        raise SystemExit("Required demo PCB files not found under circuit-ai-frontend/public/demo")

    baseline_payload = _scenario_payload()
    hardened_payload = _hardened_payload()
    client = api_server.app.test_client()

    compile_baseline_resp = client.post("/api/v2/machines/compile", json=baseline_payload)
    if compile_baseline_resp.status_code != 200:
        raise SystemExit(f"baseline compile failed: {compile_baseline_resp.status_code} {compile_baseline_resp.get_data(as_text=True)}")
    compile_baseline = (compile_baseline_resp.get_json() or {}).get("result") or {}

    compile_hardened_resp = client.post("/api/v2/machines/compile", json=hardened_payload)
    if compile_hardened_resp.status_code != 200:
        raise SystemExit(f"hardened compile failed: {compile_hardened_resp.status_code} {compile_hardened_resp.get_data(as_text=True)}")
    compile_hardened = (compile_hardened_resp.get_json() or {}).get("result") or {}

    machine_json = {
        "machine_name": hardened_payload["machine_name"],
        "boards": [
            {"board_id": "main_ctrl"},
            {"board_id": "sensor_io"},
            {"board_id": "power_stage"},
        ],
        "interconnects": hardened_payload["interconnects"],
        "power_tree": hardened_payload["power_tree"],
    }
    with (
        main_pcb.open("rb") as f_main_ctrl,
        main_pcb.open("rb") as f_sensor,
        power_pcb.open("rb") as f_power,
        main_net.open("rb") as n_main,
        power_net.open("rb") as n_power,
    ):
        build_resp = client.post(
            "/api/v2/machines/build-package",
            data={
                "machine_json": json.dumps(machine_json),
                "pcb_file_main_ctrl": (f_main_ctrl, "main_ctrl.kicad_pcb"),
                "pcb_file_sensor_io": (f_sensor, "sensor_io.kicad_pcb"),
                "pcb_file_power_stage": (f_power, "power_stage.kicad_pcb"),
                "netlist_file_main_ctrl": (n_main, "main_ctrl.net"),
                "netlist_file_power_stage": (n_power, "power_stage.net"),
            },
            content_type="multipart/form-data",
        )

    if build_resp.status_code != 200:
        raise SystemExit(f"build-package failed: {build_resp.status_code} {build_resp.get_data(as_text=True)}")

    build_body = build_resp.get_json() or {}
    machine_zip = Path(str(build_body.get("machine_package_file") or ""))
    if not machine_zip.exists():
        raise SystemExit(f"machine package missing: {machine_zip}")

    zip_entries: List[str] = []
    with zipfile.ZipFile(machine_zip, "r") as zf:
        zip_entries = sorted(zf.namelist())

    machine = compile_hardened.get("machine") or {}
    pricing = _machine_pricing_snapshot(
        int(machine.get("board_count") or 0),
        int(machine.get("interconnect_count") or 0),
    )
    report_md = _render_report(
        compile_baseline_result=compile_baseline,
        compile_hardened_result=compile_hardened,
        package_result=build_body,
        zip_entries=zip_entries,
        pricing=pricing,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_md, encoding="utf-8")

    print(json.dumps({"status": "success", "report": str(out_path), "machine_package_file": str(machine_zip)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
