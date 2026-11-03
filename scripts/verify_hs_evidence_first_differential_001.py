#!/usr/bin/env python3
"""Synthetic post-holdout differential / abstention integration checks.

These are DEVELOPMENT tests motivated by the frozen November 3 evaluation.
They are not new blind validation and must never be reported as generalization.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "circuit-ai"))

from src.intelligence.board_session_store import BoardSessionStore
from src.intelligence.repair_case_evaluator import RepairCaseEvaluator

TESTS = (
    (
        "retained_aa_power_differential",
        "Original Game Boy DMG-01",
        ["Original handheld does not turn on", "Visible AA contact corrosion and discharged cells"],
        None,
        "aa_battery_contact_or_power_switch_fault",
        False,
    ),
    (
        "speaker_not_battery_power",
        "Game Boy Color handheld",
        ["Built-in speaker is silent and has no sound",
         "Headphones work and gameplay, controls and LCD display still operate"],
        "retro_handheld_console",
        "speaker_jack_switch_or_audio_path_unverified",
        True,
    ),
    (
        "laptop_no_external_voltage",
        "Samsung series notebook laptop with barrel input",
        ["Laptop won't turn on or charge",
         "Owner reports measured no voltage at external charger output lead"],
        "laptop_or_macbook",
        "external_adapter_or_lead_output_unverified",
        True,
    ),
    (
        "laptop_no_measurement_not_invented",
        "Windows laptop with DC-in",
        ["Laptop won't turn on or charge", "Unknown charger output; no measurement yet"],
        "laptop_or_macbook",
        None,
        False,
    ),
    (
        "quadcopter_propeller_swap",
        "Toy quadcopter drone",
        ["After replacing propellers, motors spin but drone won't lift",
         "Changed blades without checking clockwise / counterclockwise orientation"],
        None,
        "propeller_orientation_or_thrust_path_unverified",
        True,
    ),
    (
        "postimpact_drone_not_motor_driver",
        "Small quadcopter drone",
        ["After a crash all motors spin but drone doesn't lift",
         "Damage to gear train and propellers is unverified"],
        None,
        "postimpact_propulsion_path_unverified",
        True,
    ),
    (
        "jammed_printer_not_electrical_driver",
        "Home inkjet printer",
        ["Carriage stuck at maintenance station and won't move",
         "Mechanical jam after changing ink cartridge"],
        None,
        "printer_carriage_or_service_station_mechanical_unverified",
        True,
    ),
    (
        "reassembly_dependence_not_replace_part_again",
        "iPhone smartphone Lightning flex assembly",
        ["New charging port flex appeared to work before reassembly",
         "After final reassembly the phone won't boot with flex connected; disconnecting it restores boot"],
        "phone_or_tablet",
        "assembly_interference_or_charge_flex_short_unverified",
        True,
    ),
    (
        "existing_console_identity",
        "Nintendo Switch OLED",
        ["No docked HDMI image and intermittent USB-C charging"],
        "modern_game_console",
        "modern_console_usb_c_port_or_video_filter_fault",
        False,
    ),
)

def main() -> None:
    failures = []
    results = []
    with tempfile.TemporaryDirectory() as temp:
        evaluator = RepairCaseEvaluator(
            session_store=BoardSessionStore(Path(temp) / "test_sessions.json")
        )
        for name, hint, symptoms, market, fault, needs_measurement in TESTS:
            guide = evaluator.encyclopedia.generate(
                analysis={}, device_hint=hint, symptoms=symptoms
            )
            result = evaluator.evaluate_case({
                "case_id": name,
                "title": "Synthetic diagnostic fixture",
                "device_hint": hint,
                "symptoms": symptoms,
                "source_url": "https://example.invalid/synthetic-fixture",
                "notes": "",
                "observed_actions": [],
            }, commit_session=False)
            top = (guide.get("fault_candidates") or [{}])[0].get("fault_id")
            triage = guide.get("triage_state") or {}
            measured = bool(triage.get("requires_measurement"))
            if market and result["coverage"]["top_item"] != market:
                failures.append(name + ": device classification " + str(result["coverage"]["top_item"]))
            if fault is not None and (top != fault or result["repair_guide"]["top_fault"] != fault):
                failures.append(name + ": expected " + fault + ", got " + str(top))
            if measured != needs_measurement:
                failures.append(name + ": measurement gate mismatch")
            if needs_measurement:
                if result["verdict"] == "solvable_now":
                    failures.append(name + ": unsafe repair-ready outcome")
                if not triage.get("repair_ready") is False or triage.get("hypothesis_verified") is not False:
                    failures.append(name + ": false confidence or authority")
                if not any("differential hypothesis unverified" in b for b in result["blockers"]):
                    failures.append(name + ": missing hard stop / assistive cap")
                if guide["repair_playbooks"][0]["title"] != "Diagnostic evidence collection only; no repair approved":
                    failures.append(name + ": stale replacement playbook")
                if guide["parts_and_tools"]["likely_parts"]:
                    failures.append(name + ": premature part shopping suggestions")
            if "drone" in hint or "printer" in hint:
                if guide["safety_profile"]["risk_level"] != "high":
                    failures.append(name + ": powered-motion hazard not blocked")
                if any("power with current limit" in str(step).lower() for step in guide["diagnostic_flow"]):
                    failures.append(name + ": generic powered test leaked")
            results.append({
                "case": name,
                "market_item": result["coverage"]["top_item"],
                "family": result["repair_guide"]["family"],
                "top_fault": top,
                "verdict": result["verdict"],
                "triage_requires_measurement": measured,
            })

    report = {
        "dataset": "synthetic_development_regressions_not_a_new_blind_holdout",
        "cases": len(results),
        "errors": failures,
        "results": results,
        "real_physical_repairs": 0,
        "flight_or_live_power_authorized": False,
    }
    print(json.dumps(report, indent=2))
    if failures:
        raise SystemExit("post-holdout differential integration tests failed")

if __name__ == "__main__":
    main()
