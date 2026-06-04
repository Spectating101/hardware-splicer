#!/usr/bin/env python3
"""Evaluate vague DIY/project-chat intake against the deterministic planner.

This is intentionally not a model benchmark. It checks whether the product can
turn normal user language into the right hardware planning lane, expose safety
blocks, carry budget/resource constraints, and avoid known false positives.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.intelligence.diy_project_engineer import build_diy_project_engineering_plan
from src.intelligence.diy_project_session import DIYProjectSessionStore


Case = Dict[str, Any]


CASES: List[Case] = [
    {
        "id": "vague_plant_budget",
        "category": "vague_intake",
        "prompt": "I need something that waters my plants while I am away. I have random old electronics and about $10.",
        "expected_profile": "automatic_plant_watering",
        "expected_readiness": "prototype_after_evidence",
        "expected_budget_usd": 10.0,
        "expected_within_budget": False,
        "forbidden_hazards": ["safety_mains_high_voltage"],
        "min_coverage": 1.0,
    },
    {
        "id": "plant_synonym_herbs",
        "category": "vague_intake",
        "prompt": "I want an automatic irrigator for herbs using junk parts, cheap.",
        "expected_profile": "automatic_plant_watering",
        "expected_readiness": "prototype_after_evidence",
        "min_coverage": 1.0,
    },
    {
        "id": "hot_room_spare_fans",
        "category": "vague_intake",
        "prompt": "My room gets too hot and I have spare fans and old adapters. Can we make something useful?",
        "expected_profile": "fume_extractor_or_fan",
        "expected_readiness": "prototype_after_evidence",
        "min_coverage": 1.0,
    },
    {
        "id": "solder_smoke_pc_fan",
        "category": "specialty",
        "prompt": "Need solder smoke extractor from an old PC fan and USB cable.",
        "expected_profile": "fume_extractor_or_fan",
        "expected_readiness": "prototype_after_evidence",
        "min_coverage": 1.0,
    },
    {
        "id": "sensor_logger",
        "category": "specialty",
        "prompt": "I want to monitor temperature and humidity in a cabinet and log it over time.",
        "expected_profile": "sensor_logger",
        "expected_readiness": "prototype_after_evidence",
        "min_coverage": 1.0,
    },
    {
        "id": "bench_power_breakout",
        "category": "specialty",
        "prompt": "Make me a safe little bench power breakout from an old laptop adapter.",
        "expected_profile": "bench_power_adapter",
        "expected_readiness": "prototype_after_evidence",
        "min_coverage": 1.0,
    },
    {
        "id": "usb_desk_light",
        "category": "specialty",
        "prompt": "Build a USB powered desk light from LED strips and an old adapter.",
        "expected_profile": "task_light_or_indicator",
        "expected_readiness": "prototype_after_evidence",
        "forbidden_hazards": ["safety_mains_high_voltage"],
        "min_coverage": 1.0,
    },
    {
        "id": "tiny_rover",
        "category": "specialty",
        "prompt": "Can we build a tiny rover from toy motors, wheels, and random boards?",
        "expected_profile": "robot_drive_base",
        "expected_readiness": "prototype_after_evidence",
        "min_coverage": 1.0,
    },
    {
        "id": "inspection_jig_camera_mount",
        "category": "specialty",
        "prompt": "I want a board inspection jig with light and a sliding camera mount.",
        "expected_profile": "inspection_fixture",
        "expected_readiness": "prototype_after_evidence",
        "min_coverage": 1.0,
    },
    {
        "id": "solenoid_load_controller",
        "category": "specialty",
        "prompt": "Need to switch a 12V solenoid valve from a microcontroller.",
        "expected_profile": "load_controller",
        "expected_readiness": "prototype_after_evidence",
        "min_coverage": 1.0,
    },
    {
        "id": "macro_keypad",
        "category": "specialty",
        "prompt": "Can I make a USB macro keypad from spare switches and an old controller board?",
        "expected_profile": "input_panel",
        "expected_readiness": "prototype_after_evidence",
        "min_coverage": 1.0,
    },
    {
        "id": "network_status_indicator",
        "category": "specialty",
        "prompt": "I need a wifi network status indicator from spare LEDs.",
        "expected_profile": "network_status_indicator",
        "expected_readiness": "prototype_after_evidence",
        "min_coverage": 1.0,
    },
    {
        "id": "audio_alert_box",
        "category": "specialty",
        "prompt": "Make a little audio alert box from a speaker and USB power.",
        "expected_profile": "audio_alert_box",
        "expected_readiness": "prototype_after_evidence",
        "min_coverage": 1.0,
    },
    {
        "id": "camera_trigger_rig",
        "category": "specialty",
        "prompt": "Can we build a camera trigger inspection rig?",
        "expected_profile": "camera_trigger_or_capture_rig",
        "expected_readiness": "prototype_after_evidence",
        "min_coverage": 1.0,
    },
    {
        "id": "generic_garage_gadget",
        "category": "fallback",
        "prompt": "I want a useful garage gadget from random boards and wires.",
        "expected_profile": "generic_low_voltage_build",
        "expected_readiness": "prototype_after_evidence",
        "min_coverage": 1.0,
    },
    {
        "id": "ambiguous_budget_limit",
        "category": "fallback",
        "prompt": "I have junk electronics and $5, what should I make?",
        "expected_profile": "generic_low_voltage_build",
        "expected_readiness": "prototype_after_evidence",
        "expected_budget_usd": 5.0,
        "expected_within_budget": False,
        "min_coverage": 1.0,
    },
    {
        "id": "owned_plant_mostly_complete",
        "category": "resource_constraints",
        "prompt": "DIY automatic plant watering system for desk plants",
        "payload": {
            "diy_project": "DIY automatic plant watering system for desk plants",
            "strategy_mode": "hybrid",
            "constraints": {"budget_usd": 5, "safety_level": "low_voltage_only"},
            "available_resources": [
                {"resource_id": "drawer_esp32", "name": "ESP32 dev board", "resource_kind": "owned", "capabilities": ["controller", "wireless", "usb_serial", "connector"], "confidence": 0.86, "evidence_status": "verified"},
                {"resource_id": "soil_probe", "name": "capacitive soil moisture sensor module", "resource_kind": "owned", "capabilities": ["sensor_or_adc", "connector"], "confidence": 0.76, "evidence_status": "needs_evidence"},
                {"resource_id": "usb_power_bank", "name": "USB power bank and cable", "resource_kind": "owned", "capabilities": ["power", "connector"], "confidence": 0.82, "evidence_status": "verified"},
                {"resource_id": "small_pump", "name": "5V mini water pump", "resource_kind": "owned", "capabilities": ["motor_or_load", "fan_or_pump"], "confidence": 0.72, "evidence_status": "needs_evidence"},
            ],
            "procurable_catalog": [
                {"resource_id": "logic_mosfet_module", "name": "logic-level MOSFET driver module with flyback diode", "resource_kind": "procurable", "capabilities": ["actuator_driver", "protection"], "cost_usd": 1.5, "confidence": 0.86}
            ],
            "use_reference_catalog": False,
        },
        "expected_profile": "automatic_plant_watering",
        "expected_readiness": "prototype_after_evidence",
        "expected_budget_usd": 5.0,
        "expected_within_budget": True,
        "min_coverage": 1.0,
    },
    {
        "id": "constrained_junk_missing_capabilities",
        "category": "resource_constraints",
        "prompt": "Build automatic plant watering using only the jumper wires I found.",
        "payload": {
            "diy_project": "Build automatic plant watering using only the jumper wires I found.",
            "strategy_mode": "constrained",
            "available_resources": [{"resource_id": "wires", "name": "jumper wires", "resource_kind": "owned", "capabilities": ["connector"], "confidence": 0.9}],
            "use_reference_catalog": False,
        },
        "expected_profile": "automatic_plant_watering",
        "expected_readiness": "resource_gap",
        "max_coverage": 0.2,
    },
    {
        "id": "mains_lamp_controller",
        "category": "safety",
        "prompt": "Build a wall outlet AC lamp controller from a relay.",
        "expected_profile": "load_controller",
        "expected_readiness": "blocked_specialist_required",
        "expected_hazards": ["safety_mains_high_voltage"],
    },
    {
        "id": "lithium_pack",
        "category": "safety",
        "prompt": "Make a lithium 18650 battery pack for a portable project.",
        "expected_readiness": "blocked_specialist_required",
        "expected_hazards": ["safety_battery_pack_lithium"],
    },
    {
        "id": "laser_engraver",
        "category": "safety",
        "prompt": "I want to make a laser engraver from salvaged DVD parts.",
        "expected_readiness": "blocked_specialist_required",
        "expected_hazards": ["safety_laser_radiation"],
    },
    {
        "id": "negated_ac_usb_only",
        "category": "safety",
        "prompt": "I need automatic plant watering, no AC outlet, only USB power.",
        "expected_profile": "automatic_plant_watering",
        "expected_readiness": "prototype_after_evidence",
        "expected_hazards": ["safety_water_near_electronics"],
        "forbidden_hazards": ["safety_mains_high_voltage"],
    },
    {
        "id": "ac_adapter_output_not_mains_project",
        "category": "safety",
        "prompt": "Build a USB-powered desk light from an old AC adapter output and LEDs.",
        "expected_profile": "task_light_or_indicator",
        "expected_readiness": "prototype_after_evidence",
        "forbidden_hazards": ["safety_mains_high_voltage"],
        "min_coverage": 1.0,
    },
    {
        "id": "non_build_photo_discovery",
        "category": "routing_boundary",
        "prompt": "Can you identify this PCB from a photo?",
        "payload": {"description": "Can you identify this PCB from a photo?"},
        "expected_available": False,
    },
]

SEQUENCES: List[Case] = [
    {
        "id": "plant_inventory_accumulation",
        "category": "stateful_intake",
        "turns": [
            "I need something that waters my plants while I am away. I have random old electronics and about $10.",
            "I found a little 5V pump, a USB charger, jumper wires, and no ESP32 yet.",
        ],
        "expected_profile": "automatic_plant_watering",
        "expected_readiness": "prototype_after_evidence",
        "expected_budget_usd": 10.0,
        "expected_resources": ["5V mini pump", "USB power source", "hookup/jumper wire"],
        "expected_absent_resources": ["ESP32 dev board"],
    },
    {
        "id": "desk_light_ratings_accumulation",
        "category": "stateful_intake",
        "turns": [
            "Make a USB powered desk light from LEDs and a switch.",
            "The LED strip says 5V and I have a USB charger.",
        ],
        "expected_profile": "task_light_or_indicator",
        "expected_readiness": "prototype_after_evidence",
        "expected_resources": ["5V low-voltage LED/light load", "5V USB power source", "button or switch input"],
        "expected_measurements": ["5V"],
    },
    {
        "id": "pinout_label_capture",
        "category": "stateful_intake",
        "turns": [
            "Build automatic plant watering.",
            "I have a moisture sensor labeled VCC GND SIG and an ESP32.",
        ],
        "expected_profile": "automatic_plant_watering",
        "expected_readiness": "prototype_after_evidence",
        "expected_labels": ["VCC", "GND", "SIG"],
    },
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=1, help="Run each case N times for latency/scale sampling.")
    parser.add_argument("--output", default="eval/diy_project_intake/latest.json")
    parser.add_argument("--allow-failures", action="store_true")
    args = parser.parse_args()

    repeat = max(1, args.repeat)
    all_rows: List[Dict[str, Any]] = []
    latencies_ms: List[float] = []
    first_results: List[Dict[str, Any]] = []
    first_sequence_results: List[Dict[str, Any]] = []

    for case in CASES:
        first: Optional[Dict[str, Any]] = None
        for _ in range(repeat):
            started = time.perf_counter()
            row = evaluate_case(case)
            elapsed_ms = (time.perf_counter() - started) * 1000
            row["latency_ms"] = round(elapsed_ms, 3)
            latencies_ms.append(elapsed_ms)
            all_rows.append(row)
            if first is None:
                first = row
        if first is not None:
            first_results.append(first)

    sequence_latencies_ms: List[float] = []
    for sequence in SEQUENCES:
        first: Optional[Dict[str, Any]] = None
        for _ in range(repeat):
            started = time.perf_counter()
            row = evaluate_sequence(sequence)
            elapsed_ms = (time.perf_counter() - started) * 1000
            row["latency_ms"] = round(elapsed_ms, 3)
            sequence_latencies_ms.append(elapsed_ms)
            if first is None:
                first = row
        if first is not None:
            first_sequence_results.append(first)

    failed = [row for row in first_results if not row["passed"]]
    sequence_failed = [row for row in first_sequence_results if not row["passed"]]
    summary = {
        "case_count": len(CASES),
        "sequence_count": len(SEQUENCES),
        "repeat": repeat,
        "invocation_count": len(all_rows),
        "passed": len(first_results) - len(failed),
        "failed": len(failed),
        "pass_rate": round((len(first_results) - len(failed)) / max(len(first_results), 1), 4),
        "sequence_passed": len(first_sequence_results) - len(sequence_failed),
        "sequence_failed": len(sequence_failed),
        "sequence_pass_rate": round((len(first_sequence_results) - len(sequence_failed)) / max(len(first_sequence_results), 1), 4),
        "latency_ms": _latency_summary(latencies_ms),
        "sequence_latency_ms": _latency_summary(sequence_latencies_ms),
        "by_category": _category_summary(first_results),
        "profile_distribution": _distribution(row.get("profile_id") for row in first_results),
        "readiness_distribution": _distribution(row.get("readiness") for row in first_results),
    }
    report = {
        "suite": "diy_project_intake",
        "summary": summary,
        "failures": failed,
        "sequence_failures": sequence_failed,
        "cases": first_results,
        "sequences": first_sequence_results,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        f"DIY intake eval: {summary['passed']}/{summary['case_count']} passed "
        f"({summary['pass_rate'] * 100:.1f}%), "
        f"stateful={summary['sequence_passed']}/{summary['sequence_count']}, "
        f"repeat={repeat}, p95={summary['latency_ms']['p95']:.2f}ms"
    )
    for row in first_results:
        status = "PASS" if row["passed"] else "FAIL"
        print(
            f"{status} {row['id']:<34} profile={str(row.get('profile_id')):<34} "
            f"readiness={str(row.get('readiness')):<29} coverage={row.get('coverage_score')}"
        )
        if row["errors"]:
            for error in row["errors"]:
                print(f"  - {error}")
    for row in first_sequence_results:
        status = "PASS" if row["passed"] else "FAIL"
        print(
            f"{status} {row['id']:<34} profile={str(row.get('profile_id')):<34} "
            f"turns={row.get('turn_count')} resources={row.get('resource_count')}"
        )
        if row["errors"]:
            for error in row["errors"]:
                print(f"  - {error}")

    return 0 if args.allow_failures or not (failed or sequence_failed) else 1


def evaluate_case(case: Case) -> Dict[str, Any]:
    payload = dict(case.get("payload") or {"diy_project": case["prompt"], "strategy_mode": "hybrid"})
    plan = build_diy_project_engineering_plan(payload)
    available = bool(plan.get("available"))
    intent = plan.get("project_intent") if isinstance(plan.get("project_intent"), dict) else {}
    readiness = plan.get("readiness") if isinstance(plan.get("readiness"), dict) else {}
    resource_plan = plan.get("resource_plan") if isinstance(plan.get("resource_plan"), dict) else {}
    coverage = resource_plan.get("coverage") if isinstance(resource_plan.get("coverage"), dict) else {}
    procurement = resource_plan.get("procurement") if isinstance(resource_plan.get("procurement"), dict) else {}
    hazards = [
        str(gate.get("gate_id"))
        for gate in plan.get("engineering_gates", [])
        if isinstance(gate, dict) and str(gate.get("gate_id", "")).startswith("safety_")
    ]

    row = {
        "id": case["id"],
        "category": case["category"],
        "prompt": case["prompt"],
        "available": available,
        "profile_id": intent.get("profile_id"),
        "readiness": readiness.get("level"),
        "readiness_score": readiness.get("score"),
        "coverage_score": coverage.get("coverage_score"),
        "missing_capabilities": coverage.get("missing_capabilities") or [],
        "estimated_cost_usd": procurement.get("estimated_cost_usd"),
        "budget_usd": procurement.get("budget_usd"),
        "within_budget": procurement.get("within_budget"),
        "hazards": hazards,
        "selected_resource_count": len(resource_plan.get("selected_resources") or []),
        "next_evidence_task_count": len(plan.get("next_evidence_tasks") or []),
        "errors": [],
    }
    row["errors"] = check_expectations(case, row)
    row["passed"] = not row["errors"]
    return row


def evaluate_sequence(sequence: Case) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        store = DIYProjectSessionStore(Path(tmp) / "sessions.json")
        session_id = None
        result: Dict[str, Any] = {}
        for turn in sequence["turns"]:
            payload: Dict[str, Any] = {
                "user_message": turn,
                "session_id": session_id,
                "strategy_mode": "hybrid",
                "use_reference_catalog": True,
            }
            result = store.update_from_turn(payload)
            session_id = result["diy_project_session"]["session_id"]
    session = result.get("diy_project_session") if isinstance(result.get("diy_project_session"), dict) else {}
    intake = session.get("intake_state") if isinstance(session.get("intake_state"), dict) else {}
    plan = result.get("diy_project_engineering") if isinstance(result.get("diy_project_engineering"), dict) else {}
    intent = plan.get("project_intent") if isinstance(plan.get("project_intent"), dict) else {}
    readiness = plan.get("readiness") if isinstance(plan.get("readiness"), dict) else {}
    procurement = ((plan.get("resource_plan") or {}).get("procurement") if isinstance(plan.get("resource_plan"), dict) else {}) or {}
    row = {
        "id": sequence["id"],
        "category": sequence["category"],
        "profile_id": intent.get("profile_id"),
        "readiness": readiness.get("level"),
        "turn_count": ((session.get("conversation") or {}).get("turn_count") if isinstance(session.get("conversation"), dict) else None),
        "resource_count": len(intake.get("available_resources") or []),
        "resources": [resource.get("name") for resource in intake.get("available_resources") or [] if isinstance(resource, dict)],
        "absent_resources": [resource.get("name") for resource in intake.get("known_absent_resources") or [] if isinstance(resource, dict)],
        "labels": intake.get("observed_labels") or [],
        "measurements": [measurement.get("raw") for measurement in intake.get("measurements") or [] if isinstance(measurement, dict)],
        "budget_usd": procurement.get("budget_usd"),
        "errors": [],
    }
    row["errors"] = check_sequence_expectations(sequence, row)
    row["passed"] = not row["errors"]
    return row


def check_expectations(case: Case, row: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    expected_available = case.get("expected_available", True)
    if row["available"] != expected_available:
        errors.append(f"available expected {expected_available}, got {row['available']}")
    if not row["available"]:
        return errors
    if case.get("expected_profile") and row.get("profile_id") != case["expected_profile"]:
        errors.append(f"profile expected {case['expected_profile']}, got {row.get('profile_id')}")
    if case.get("expected_readiness") and row.get("readiness") != case["expected_readiness"]:
        errors.append(f"readiness expected {case['expected_readiness']}, got {row.get('readiness')}")
    for hazard in case.get("expected_hazards", []):
        if hazard not in row["hazards"]:
            errors.append(f"missing expected hazard {hazard}")
    for hazard in case.get("forbidden_hazards", []):
        if hazard in row["hazards"]:
            errors.append(f"forbidden hazard present {hazard}")
    if "expected_budget_usd" in case and not _same_money(row.get("budget_usd"), case["expected_budget_usd"]):
        errors.append(f"budget expected {case['expected_budget_usd']}, got {row.get('budget_usd')}")
    if "expected_within_budget" in case and row.get("within_budget") is not case["expected_within_budget"]:
        errors.append(f"within_budget expected {case['expected_within_budget']}, got {row.get('within_budget')}")
    if "min_coverage" in case and float(row.get("coverage_score") or 0.0) < float(case["min_coverage"]):
        errors.append(f"coverage expected >= {case['min_coverage']}, got {row.get('coverage_score')}")
    if "max_coverage" in case and float(row.get("coverage_score") or 0.0) > float(case["max_coverage"]):
        errors.append(f"coverage expected <= {case['max_coverage']}, got {row.get('coverage_score')}")
    if case.get("expected_readiness") != "blocked_specialist_required" and row["next_evidence_task_count"] <= 0:
        errors.append("expected at least one evidence task")
    return errors


def check_sequence_expectations(sequence: Case, row: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if row.get("turn_count") != len(sequence["turns"]):
        errors.append(f"turn_count expected {len(sequence['turns'])}, got {row.get('turn_count')}")
    if sequence.get("expected_profile") and row.get("profile_id") != sequence["expected_profile"]:
        errors.append(f"profile expected {sequence['expected_profile']}, got {row.get('profile_id')}")
    if sequence.get("expected_readiness") and row.get("readiness") != sequence["expected_readiness"]:
        errors.append(f"readiness expected {sequence['expected_readiness']}, got {row.get('readiness')}")
    if "expected_budget_usd" in sequence and not _same_money(row.get("budget_usd"), sequence["expected_budget_usd"]):
        errors.append(f"budget expected {sequence['expected_budget_usd']}, got {row.get('budget_usd')}")
    for resource in sequence.get("expected_resources", []):
        if resource not in row["resources"]:
            errors.append(f"missing expected captured resource {resource}")
    for resource in sequence.get("expected_absent_resources", []):
        if resource not in row["absent_resources"]:
            errors.append(f"missing expected absent resource {resource}")
    for label in sequence.get("expected_labels", []):
        if label not in row["labels"]:
            errors.append(f"missing expected label {label}")
    for measurement in sequence.get("expected_measurements", []):
        if measurement not in row["measurements"]:
            errors.append(f"missing expected measurement {measurement}")
    return errors


def _same_money(value: Any, expected: float) -> bool:
    try:
        return abs(float(value) - expected) < 0.005
    except (TypeError, ValueError):
        return False


def _latency_summary(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"mean": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    sorted_values = sorted(values)
    p95_index = min(len(sorted_values) - 1, int(round((len(sorted_values) - 1) * 0.95)))
    return {
        "mean": round(statistics.fmean(values), 3),
        "p50": round(statistics.median(values), 3),
        "p95": round(sorted_values[p95_index], 3),
        "max": round(max(values), 3),
    }


def _category_summary(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    summary: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        category = str(row.get("category") or "unknown")
        bucket = summary.setdefault(category, {"passed": 0, "failed": 0, "total": 0, "pass_rate": 0.0})
        bucket["total"] += 1
        if row.get("passed"):
            bucket["passed"] += 1
        else:
            bucket["failed"] += 1
    for bucket in summary.values():
        bucket["pass_rate"] = round(bucket["passed"] / max(bucket["total"], 1), 4)
    return summary


def _distribution(values: Iterable[Any]) -> Dict[str, int]:
    distribution: Dict[str, int] = {}
    for value in values:
        key = str(value)
        distribution[key] = distribution.get(key, 0) + 1
    return dict(sorted(distribution.items(), key=lambda item: (-item[1], item[0])))


if __name__ == "__main__":
    raise SystemExit(main())
