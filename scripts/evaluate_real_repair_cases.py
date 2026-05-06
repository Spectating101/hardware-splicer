#!/usr/bin/env python3
"""Evaluate Circuit-AI against sourced real-world repair case patterns."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.intelligence.board_session_store import BoardSessionStore
from src.intelligence.repair_case_evaluator import RepairCase, RepairCaseEvaluator


DEFAULT_CASES = [
    RepairCase(
        case_id="xbox_thumbstick_drift",
        title="Xbox One wireless controller has malfunctioning thumbstick",
        device_hint="Xbox game controller",
        symptoms=["stick drift", "thumbstick axis is unreliable", "controller input is intermittent"],
        source_url="https://www.ifixit.com/Troubleshooting/Xbox_One_Controller/Xbox%2BOne%2BWireless%2BController%2BHas%2BMalfunctioning%2BThumbstick/444889",
        observed_actions=["open controller", "inspect joystick module", "clean contacts", "replace analog stick if drift remains"],
        expected_lane="game_controller_input",
    ),
    RepairCase(
        case_id="laptop_no_power",
        title="Laptop will not turn on",
        device_hint="PC laptop no power",
        symptoms=["laptop won't turn on", "no power", "not charging"],
        source_url="https://www.ifixit.com/Troubleshooting/PC_Laptop/Laptop%2BWill%2BNot%2BTurn%2BOn/505262",
        observed_actions=["try known-good charger", "inspect charge port", "isolate battery", "check board input path"],
        expected_lane="laptop_power_path",
    ),
    RepairCase(
        case_id="coffee_not_hot",
        title="Coffee maker not hot enough",
        device_hint="coffee maker heater appliance",
        symptoms=["coffee maker not heating", "not hot enough", "brew output is cold"],
        source_url="https://www.ifixit.com/Troubleshooting/Coffee_Maker/Not%2BHot%2BEnough/483047",
        observed_actions=["unplug appliance", "check thermal fuse", "check thermostat", "measure heating element"],
        expected_lane="mains_heater_appliance",
    ),
    RepairCase(
        case_id="electric_toothbrush_not_charging",
        title="Electric toothbrush not charging",
        device_hint="electric toothbrush charging dock",
        symptoms=["not charging", "battery does not hold charge", "charging dock suspected"],
        source_url="https://www.ifixit.com/Troubleshooting/Electric_Toothbrush/Not%2BCharging/564390",
        observed_actions=["inspect charging contacts", "verify charger output", "measure battery voltage", "replace battery if safe"],
        expected_lane="battery_charging_gadget",
    ),
    RepairCase(
        case_id="dewalt_battery_not_charge",
        title="DeWalt DC970 battery will not charge",
        device_hint="cordless drill battery and charger",
        symptoms=["cordless drill battery will not charge", "charger or battery pack fault", "tool has no power"],
        source_url="https://www.ifixit.com/Wiki/DeWalt_DC970_Troubleshooting",
        observed_actions=["check battery contacts", "verify charger", "measure pack voltage", "inspect battery terminals"],
        expected_lane="battery_charging_gadget",
    ),
    RepairCase(
        case_id="tv_sound_no_picture",
        title="TV has sound but no picture",
        device_hint="LED TV backlight power board",
        symptoms=["sound but no picture", "screen dark", "backlight suspected"],
        source_url="https://www.ifixit.com/Troubleshooting/Television/TV%2BHas%2BSound%2BBut%2BNo%2BPicture/493422",
        observed_actions=["flashlight test", "inspect power board", "test backlight strips", "check backlight driver"],
        expected_lane="tv_backlight_power",
    ),
    RepairCase(
        case_id="usb_fan_no_spin",
        title="USB fan warms but motor will not spin",
        device_hint="USB fan controller board",
        symptoms=["warm board", "motor will not spin", "no spin unless wire is wiggled", "intermittent harness"],
        source_url="local sample assets/samples/test_pcb.png",
        observed_actions=["scan PCB", "inspect connector", "measure continuity", "test motor/load under current limit"],
        expected_lane="small_dc_motor_gadget",
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate real repair cases")
    parser.add_argument("--output-dir", default="eval/real_repair_cases", help="directory for report artifacts")
    parser.add_argument("--commit-sessions", action="store_true", help="persist eval sessions to the output store")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    store = BoardSessionStore(out / "board_sessions.json")
    evaluator = RepairCaseEvaluator(session_store=store)
    report = evaluator.evaluate_cases(DEFAULT_CASES, commit_sessions=args.commit_sessions)
    (out / "real_repair_case_eval.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "README.md").write_text(evaluator.render_markdown(report), encoding="utf-8")
    (out / "cases.json").write_text(json.dumps(evaluator.serialize_cases(DEFAULT_CASES), indent=2), encoding="utf-8")

    summary = report["summary"]
    print(f"wrote {out}")
    print(
        "cases={case_count} solvable={solvable_now} assistive={assistive_only} "
        "not_ready={not_ready} avg_score={average_workflow_score}".format(**summary)
    )
    for row in report["cases"]:
        print(
            f"{row['case_id']}: {row['verdict']} score={row['workflow_score']} "
            f"lane={row['repair_guide']['family']} top_fault={row['repair_guide']['top_fault']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
