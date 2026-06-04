#!/usr/bin/env python3
"""Evaluate salvage/reuse/splice planning coverage across common junk cases."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.intelligence.salvage_splice_planner import SalvageSplicePlanner


BUILTIN_CASES: List[Dict[str, Any]] = [
    {
        "case_id": "usb_fan",
        "category": "low_voltage_air_mover",
        "title": "USB fan with broken switch",
        "goal": "reuse as fume extractor or bench cooling fan",
        "available_parts": ["5V USB cable", "small DC motor and fan blade", "on/off switch", "wire harness connector", "plastic enclosure"],
        "expected": "reuse",
        "expected_build_ids": ["usb_fume_extractor", "low_voltage_motor_test_jig"],
    },
    {
        "case_id": "pc_fan",
        "category": "low_voltage_air_mover",
        "title": "old PC fan and adapter",
        "goal": "reuse as bench cooling fan",
        "available_parts": ["12V PC fan", "3 pin connector", "fan grill", "old 12V adapter"],
        "expected": "reuse",
        "expected_build_ids": ["usb_fume_extractor", "low_voltage_motor_test_jig"],
    },
    {
        "case_id": "toy_rc_car",
        "category": "motors_mechanics",
        "title": "broken RC toy car",
        "goal": "reuse motors and gearbox for a small robot",
        "available_parts": ["DC motors", "gearbox", "wheels", "battery holder", "switch", "wire harness"],
        "expected": "reuse",
        "expected_build_ids": ["robot_drive_base", "low_voltage_motor_test_jig"],
    },
    {
        "case_id": "inkjet_printer_motion",
        "category": "motors_mechanics",
        "title": "dead inkjet printer",
        "goal": "reuse printer parts for CNC or plotter motion test jig",
        "available_parts": ["stepper motors", "limit switches", "optical sensor", "24V power supply", "belts and rails", "wire harness connectors"],
        "expected": "reuse",
        "expected_build_ids": ["plotter_motion_stage", "low_voltage_motor_test_jig"],
    },
    {
        "case_id": "flatbed_scanner",
        "category": "motors_sensors_lighting",
        "title": "flatbed scanner",
        "goal": "reuse light bar, stepper, and rails for an inspection fixture",
        "available_parts": ["stepper motor", "LED light bar", "linear rail", "optical sensor", "12V adapter", "limit switch"],
        "expected": "reuse",
        "expected_build_ids": ["inspection_motion_fixture", "plotter_motion_stage", "camera_ir_light_or_sensor_mount", "indicator_or_task_light"],
    },
    {
        "case_id": "document_camera_slider",
        "category": "inspection_fixture",
        "title": "scrap scanner rail with webcam",
        "goal": "build a repeatable document inspection camera slider",
        "available_parts": ["linear rail", "stepper motor", "limit switch", "USB webcam camera module", "LED light strip", "12V adapter", "wire harness"],
        "expected": "reuse",
        "expected_build_ids": ["inspection_motion_fixture", "camera_ir_light_or_sensor_mount", "plotter_motion_stage"],
    },
    {
        "case_id": "dvd_drive_motion",
        "category": "small_motion_stage",
        "title": "old DVD drive tray and sled",
        "goal": "reuse the tray motor and sled as a small positioning stage",
        "available_parts": ["DC tray motor", "linear sled rail", "limit switch", "5V connector", "plastic frame"],
        "expected": "reuse",
        "expected_build_ids": ["plotter_motion_stage", "low_voltage_motor_test_jig"],
    },
    {
        "case_id": "laser_printer_mains",
        "category": "mains_laser_printer",
        "title": "laser printer fuser and motor assembly",
        "goal": "reuse motors and rollers",
        "available_parts": ["mains laser printer", "fuser heater", "high voltage corona board", "DC motor", "rollers", "optical sensors"],
        "expected": "safety",
        "expected_build_ids": [],
    },
    {
        "case_id": "wifi_router",
        "category": "network_modules",
        "title": "old WiFi router",
        "goal": "reuse router parts for network or status gadget",
        "available_parts": ["12V power adapter", "WiFi antennas", "LED indicators", "Ethernet connectors", "plastic case"],
        "expected": "reuse",
        "expected_build_ids": ["network_status_indicator", "bench_power_adapter"],
    },
    {
        "case_id": "bluetooth_speaker",
        "category": "audio_modules",
        "title": "broken Bluetooth speaker",
        "goal": "reuse speaker and amplifier as a small amp box",
        "available_parts": ["speaker driver", "amplifier board", "USB charging board", "buttons", "battery pack", "enclosure"],
        "expected": "reuse",
        "expected_build_ids": ["small_audio_amp_box"],
    },
    {
        "case_id": "car_radio_speaker",
        "category": "audio_modules",
        "title": "old car speaker and 12V amp board",
        "goal": "reuse as a bench audio monitor",
        "available_parts": ["speaker", "12V amplifier board", "volume knob", "power connector", "metal enclosure"],
        "expected": "reuse",
        "expected_build_ids": ["small_audio_amp_box"],
    },
    {
        "case_id": "led_desk_lamp",
        "category": "lighting",
        "title": "broken USB LED desk lamp",
        "goal": "reuse as small task light",
        "available_parts": ["LED board", "5V USB cable", "switch", "gooseneck enclosure"],
        "expected": "reuse",
        "expected_build_ids": ["indicator_or_task_light"],
    },
    {
        "case_id": "led_strip_controller",
        "category": "lighting_control",
        "title": "LED strip controller",
        "goal": "reuse MOSFET board as low voltage light controller",
        "available_parts": ["12V adapter", "MOSFET driver board", "IR remote", "LED strip scraps", "wire connectors", "plastic case"],
        "expected": "reuse",
        "expected_build_ids": ["smart_relay_box", "indicator_or_task_light", "network_status_indicator"],
    },
    {
        "case_id": "power_bank_normal",
        "category": "battery_power",
        "title": "normal power bank board",
        "goal": "reuse USB boost/charging board as protected power breakout",
        "available_parts": ["USB boost charging board", "18650 battery pack", "case", "USB connector"],
        "expected": "reuse",
        "expected_build_ids": ["bench_power_adapter"],
    },
    {
        "case_id": "electric_toothbrush",
        "category": "battery_motor_gadget",
        "title": "dead electric toothbrush",
        "goal": "reuse motor, switch, and charging coil if safe",
        "available_parts": ["small vibration motor", "battery pack", "charging coil", "switch button", "plastic waterproof case"],
        "expected": "reuse",
        "expected_build_ids": ["low_voltage_motor_test_jig", "bench_power_adapter"],
    },
    {
        "case_id": "game_controller",
        "category": "input_devices",
        "title": "broken game controller",
        "goal": "reuse buttons and joysticks as control panel",
        "available_parts": ["USB cable", "button board", "joystick modules", "vibration motors", "plastic shell"],
        "expected": "reuse",
        "expected_build_ids": ["salvaged_input_panel", "low_voltage_motor_test_jig"],
    },
    {
        "case_id": "keyboard",
        "category": "input_devices",
        "title": "old USB keyboard",
        "goal": "reuse keys as macro pad or input panel",
        "available_parts": ["USB cable", "keyboard matrix", "keys", "controller board", "plastic case"],
        "expected": "reuse",
        "expected_build_ids": ["salvaged_input_panel"],
    },
    {
        "case_id": "mouse",
        "category": "input_devices",
        "title": "old optical mouse",
        "goal": "reuse mouse sensor and buttons",
        "available_parts": ["USB cable", "optical sensor", "buttons", "scroll wheel", "plastic case"],
        "expected": "reuse",
        "expected_build_ids": ["salvaged_input_panel", "camera_ir_light_or_sensor_mount"],
    },
    {
        "case_id": "security_camera",
        "category": "camera_sensor",
        "title": "dead WiFi security camera",
        "goal": "reuse camera LEDs and enclosure as inspection fixture",
        "available_parts": ["WiFi camera board", "IR LED board", "5V USB cable", "speaker", "plastic enclosure"],
        "expected": "reuse",
        "expected_build_ids": ["camera_ir_light_or_sensor_mount", "network_status_indicator"],
    },
    {
        "case_id": "hard_drive",
        "category": "motors_mechanics",
        "title": "old hard drive",
        "goal": "reuse hard drive motor, magnets, and connector",
        "available_parts": ["spindle motor", "voice coil magnets", "SATA connector", "aluminum enclosure", "12V 5V power connector"],
        "expected": "reuse",
        "expected_build_ids": ["low_voltage_motor_test_jig", "bench_power_adapter"],
    },
    {
        "case_id": "laptop_parts",
        "category": "mixed_modules",
        "title": "scrap laptop parts",
        "goal": "reuse low-voltage peripherals only",
        "available_parts": ["USB webcam camera module", "speaker pair", "WiFi antenna", "keyboard", "cooling fan", "plastic frame"],
        "expected": "reuse",
        "expected_build_ids": ["camera_ir_light_or_sensor_mount", "small_audio_amp_box", "salvaged_input_panel", "usb_fume_extractor"],
    },
    {
        "case_id": "phone_parts",
        "category": "mixed_modules",
        "title": "scrap smartphone parts",
        "goal": "reuse camera, vibration motor, speaker, and enclosure if practical",
        "available_parts": ["camera module", "vibration motor", "speaker", "battery pack", "screen", "USB connector"],
        "expected": "reuse",
        "expected_build_ids": ["camera_ir_light_or_sensor_mount", "small_audio_amp_box", "low_voltage_motor_test_jig"],
    },
    {
        "case_id": "power_bank_swollen",
        "category": "battery_hazard",
        "title": "swollen lithium power bank",
        "goal": "reuse cells",
        "available_parts": ["swollen lithium battery pack", "USB charging board", "plastic case"],
        "expected": "safety",
        "expected_build_ids": [],
    },
    {
        "case_id": "coffee_maker_mains",
        "category": "mains_appliance",
        "title": "mains AC coffee maker",
        "goal": "reuse pump or heater parts",
        "available_parts": ["mains AC coffee maker", "heater plate", "thermal fuse", "pump", "switches"],
        "expected": "safety",
        "expected_build_ids": [],
    },
    {
        "case_id": "microwave_hv",
        "category": "high_voltage_appliance",
        "title": "microwave oven",
        "goal": "reuse turntable motor",
        "available_parts": ["microwave oven", "high voltage capacitor", "magnetron", "turntable motor", "mains transformer"],
        "expected": "safety",
        "expected_build_ids": [],
    },
    {
        "case_id": "smart_bulb_mains",
        "category": "mains_lighting",
        "title": "mains smart bulb",
        "goal": "reuse LED board",
        "available_parts": ["mains smart bulb", "LED board", "WiFi controller", "AC line driver"],
        "expected": "safety",
        "expected_build_ids": [],
    },
    {
        "case_id": "pc_power_supply",
        "category": "mains_power",
        "title": "desktop ATX PC power supply",
        "goal": "reuse as bench power supply",
        "available_parts": ["mains ATX power supply", "AC line input", "large capacitors", "12V rails", "fan", "wiring harness"],
        "expected": "safety",
        "expected_build_ids": [],
    },
    {
        "case_id": "ebike_battery",
        "category": "high_energy_battery",
        "title": "e-bike battery pack",
        "goal": "reuse pack for a machine",
        "available_parts": ["high voltage e-bike battery pack", "BMS board", "charger connector", "case"],
        "expected": "safety",
        "expected_build_ids": [],
    },
    {
        "case_id": "crt_tv",
        "category": "high_voltage_display",
        "title": "CRT television",
        "goal": "reuse speaker or enclosure",
        "available_parts": ["CRT tube", "high voltage flyback", "mains power board", "speaker", "plastic case"],
        "expected": "safety",
        "expected_build_ids": [],
    },
]


def score_case(case: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    verdict = str(plan.get("verdict") or "")
    target_id = str((plan.get("target") or {}).get("recommended_build_id") or "")
    expected = str(case.get("expected") or "reuse")
    expected_build_ids = set(case.get("expected_build_ids") or [])
    measurement_count = len(((plan.get("splice_plan") or {}).get("required_measurements") or []))
    adapter_count = len(((plan.get("splice_plan") or {}).get("adapter_circuits") or []))
    block_count = len(plan.get("reusable_blocks") or [])
    target_match = not expected_build_ids or target_id in expected_build_ids

    if expected == "safety":
        score = 1.0 if verdict == "unsafe_hold" else 0.25 if (plan.get("stop_conditions") or []) else 0.0
    else:
        score = (
            0.35 * (verdict in {"reuse_ready", "ready_after_measurements"})
            + 0.25 * target_match
            + 0.15 * (measurement_count >= 3)
            + 0.15 * (block_count >= 3)
            + 0.10 * (adapter_count >= 1)
        )
        if verdict == "unsafe_hold":
            score *= 0.25
    score = round(float(score), 3)
    if score >= 0.8:
        level = "strong"
    elif score >= 0.55:
        level = "partial"
    else:
        level = "weak"
    return {
        "score": score,
        "coverage_level": level,
        "target_match": target_match,
        "measurement_count": measurement_count,
        "adapter_count": adapter_count,
        "block_count": block_count,
    }


def render_markdown(report: Dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Salvage Splice Coverage Evaluation",
        "",
        f"- Cases: {summary['case_count']}",
        f"- Strong: {summary['strong_count']}",
        f"- Partial: {summary['partial_count']}",
        f"- Weak: {summary['weak_count']}",
        f"- Safety holds caught: {summary['safety_hold_count']}/{summary['safety_case_count']}",
        f"- Reuse-ready or ready-after-measurements: {summary['reuse_routable_count']}/{summary['reuse_case_count']}",
        f"- Average score: {summary['average_score']}",
        "",
        "## Cases",
    ]
    for row in report["cases"]:
        lines.extend(
            [
                "",
                f"### {row['case_id']}",
                "",
                f"- Category: `{row['category']}`",
                f"- Verdict: `{row['verdict']}`",
                f"- Coverage: `{row['coverage_level']}` score `{row['score']}`",
                f"- Target: `{row['target_build_id']}` / {row['target_build']}",
                f"- Blocks: `{row['block_count']}`, measurements: `{row['measurement_count']}`, adapters: `{row['adapter_count']}`",
                f"- Top measurements: {', '.join(row['top_measurements'][:4]) or 'none'}",
            ]
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Strong means the planner identified useful blocks, routed to a plausible build or safety hold, and produced measurement/adapter gates.",
            "- Partial means it found reusable material but the target or proof path still needs sharper domain knowledge.",
            "- Weak means the item needs more evidence, new capability vocabulary, or a dedicated safety/reuse pack.",
            "",
        ]
    )
    return "\n".join(lines)


def load_cases(path: Path | None) -> List[Dict[str, Any]]:
    if path is None:
        return BUILTIN_CASES
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("case file must be a JSON list")
    return [item for item in payload if isinstance(item, dict)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-file", type=Path, help="Optional JSON list of cases")
    parser.add_argument("--output-dir", type=Path, default=Path("eval/salvage_splice_coverage"))
    args = parser.parse_args()

    planner = SalvageSplicePlanner()
    rows = []
    for case in load_cases(args.case_file):
        plan = planner.plan(case)
        score = score_case(case, plan)
        target = plan.get("target") or {}
        splice = plan.get("splice_plan") or {}
        rows.append(
            {
                "case_id": case.get("case_id"),
                "category": case.get("category"),
                "title": case.get("title"),
                "expected": case.get("expected"),
                "verdict": plan.get("verdict"),
                "confidence": plan.get("confidence"),
                "coverage_level": score["coverage_level"],
                "score": score["score"],
                "target_match": score["target_match"],
                "target_build_id": target.get("recommended_build_id"),
                "target_build": target.get("recommended_build"),
                "block_count": score["block_count"],
                "measurement_count": score["measurement_count"],
                "adapter_count": score["adapter_count"],
                "top_measurements": (splice.get("required_measurements") or [])[:6],
                "top_adapters": [item.get("name") for item in (splice.get("adapter_circuits") or [])[:4]],
                "stop_conditions": plan.get("stop_conditions") or [],
                "plan": plan,
            }
        )

    strong = [row for row in rows if row["coverage_level"] == "strong"]
    partial = [row for row in rows if row["coverage_level"] == "partial"]
    weak = [row for row in rows if row["coverage_level"] == "weak"]
    safety_rows = [row for row in rows if row["expected"] == "safety"]
    reuse_rows = [row for row in rows if row["expected"] == "reuse"]
    summary = {
        "case_count": len(rows),
        "strong_count": len(strong),
        "partial_count": len(partial),
        "weak_count": len(weak),
        "strong_or_partial_rate": round((len(strong) + len(partial)) / max(len(rows), 1), 3),
        "average_score": round(sum(row["score"] for row in rows) / max(len(rows), 1), 3),
        "safety_case_count": len(safety_rows),
        "safety_hold_count": len([row for row in safety_rows if row["verdict"] == "unsafe_hold"]),
        "reuse_case_count": len(reuse_rows),
        "reuse_routable_count": len([row for row in reuse_rows if row["verdict"] in {"reuse_ready", "ready_after_measurements"}]),
        "weak_cases": [row["case_id"] for row in weak],
        "partial_cases": [row["case_id"] for row in partial],
    }
    report = {
        "mode": "salvage_splice_coverage_eval",
        "summary": summary,
        "cases": rows,
        "next_builds": [
            "add real photo/measurement capture for these reuse cases",
            "split battery packs into stricter chemistry-specific safety lanes",
            "add domain packs for cameras/displays, motors/mechanisms, and audio modules",
            "convert successful reuse builds into value trials with recovered value and training exports",
        ],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "salvage_splice_coverage.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (args.output_dir / "cases.json").write_text(json.dumps(BUILTIN_CASES, indent=2), encoding="utf-8")
    (args.output_dir / "README.md").write_text(render_markdown(report), encoding="utf-8")

    print(f"wrote {args.output_dir}")
    print(
        "cases={case_count} strong={strong_count} partial={partial_count} weak={weak_count} "
        "avg={average_score} safety={safety_hold_count}/{safety_case_count} reuse={reuse_routable_count}/{reuse_case_count}".format(**summary)
    )
    for row in rows:
        print(f"{row['case_id']}: {row['coverage_level']} {row['verdict']} -> {row['target_build_id']} score={row['score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
