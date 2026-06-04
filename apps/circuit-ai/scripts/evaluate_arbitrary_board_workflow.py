#!/usr/bin/env python3
"""Evaluate arbitrary-board workflow behavior across representative scenarios."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.intelligence.hardware_plan import HardwarePlanOrchestrator  # noqa: E402


def trusted() -> Dict[str, Any]:
    return {
        "instrument_id": "bench_dmm_01",
        "instrument_type": "calibrated_dmm",
        "calibration_status": "valid",
        "recorded_at": "2026-05-26T03:00:00Z",
        "operator_id": "operator-1",
        "evidence_uri": "session://arbitrary-board-workflow",
    }


def release_manifest(resource_ids: List[str]) -> Dict[str, Any]:
    return {
        "release_id": "REL-ARB-EVAL-001",
        "selected_resource_ids": resource_ids,
        "released_by": "operator-1",
        "approved_by": "operator-1",
        "released_at": "2026-05-26T04:00:00Z",
        "scope_statement": "Release is limited to the measured arbitrary-board pins, rails, and terminal outcome in this eval.",
        "artifact_uri": "session://release/arbitrary-eval",
        "acceptance_reviewed": True,
        "repeatability_sample_count": 1,
    }


def board_evidence() -> Dict[str, Any]:
    return {
        "schema_version": "board_evidence.v1",
        "components": [
            {"id": "u1", "label": "CH340C USB serial bridge IC", "kind": "integrated_circuit", "confidence": 0.78},
            {"id": "j1", "label": "USB connector", "kind": "connector", "confidence": 0.74},
        ],
        "connectors": [{"id": "h1", "label": "UART header", "kind": "header", "confidence": 0.7}],
        "damage": [],
    }


def sensor_board_evidence() -> Dict[str, Any]:
    return {
        "schema_version": "board_evidence.v1",
        "components": [
            {"id": "u1", "label": "BME280 sensor IC", "kind": "sensor", "confidence": 0.78},
            {"id": "j1", "label": "I2C header", "kind": "header", "confidence": 0.72},
        ],
        "connectors": [{"id": "j1", "label": "I2C header", "kind": "header", "confidence": 0.72}],
        "damage": [],
    }


def regulator_marking_board_evidence() -> Dict[str, Any]:
    return {
        "schema_version": "board_evidence.v1",
        "components": [
            {"id": "u1", "label": "unknown SOT-223 regulator package", "kind": "integrated_circuit", "confidence": 0.66},
            {"id": "c1", "label": "output capacitor", "kind": "capacitor", "confidence": 0.62},
        ],
        "markings": [{"id": "m1", "label": "AMS1117-3.3 marking on U1", "marking": "AMS1117-3.3", "confidence": 0.76}],
        "connectors": [{"id": "j1", "label": "VIN GND VOUT header", "kind": "header", "confidence": 0.64}],
        "damage": [],
    }


def marked_board_evidence(marking: str, label: str, connector_label: str = "header") -> Dict[str, Any]:
    return {
        "schema_version": "board_evidence.v1",
        "components": [{"id": "u1", "label": label, "kind": "integrated_circuit", "confidence": 0.68}],
        "markings": [{"id": "m1", "label": f"{marking} marking on U1", "marking": marking, "confidence": 0.76}],
        "connectors": [{"id": "j1", "label": connector_label, "kind": "header", "confidence": 0.64}],
        "damage": [],
    }


def topology(*, short: bool = False) -> Dict[str, Any]:
    return {
        "schema_version": "topology_evidence.v1",
        **trusted(),
        "connectors": [
            {
                "ref": "J1",
                "label": "measured UART header",
                "status": "verified",
                "pins": [
                    {"pin": "1", "net": "GND", "role": "ground", "status": "verified"},
                    {"pin": "2", "net": "3V3", "role": "power", "voltage": 3.31, "status": "verified"},
                    {"pin": "3", "net": "UART_TX", "role": "uart_tx", "logic_voltage": 3.29, "status": "verified"},
                    {"pin": "4", "net": "UART_RX", "role": "uart_rx", "logic_voltage": 3.3, "status": "verified"},
                ],
            }
        ],
        "resistance": [
            {
                "target": "power to ground no-short",
                "value": "fail" if short else "pass",
                "unit": "ohm",
                "notes": "short detected between 3V3 and GND" if short else "unpowered resistance between power and ground is no-short",
                "status": "failed" if short else "pass",
            }
        ],
        "current": [{"target": "current draw under current-limited supply", "value": "pass", "status": "pass", "notes": "within limit"}],
        "thermal": [{"target": "thermal behavior after first power", "value": "normal", "status": "pass", "notes": "stable"}],
    }


def motor_topology() -> Dict[str, Any]:
    return {
        "schema_version": "topology_evidence.v1",
        **trusted(),
        "connectors": [
            {
                "ref": "J2",
                "label": "measured motor driver terminal",
                "status": "verified",
                "pins": [
                    {"pin": "1", "net": "GND", "role": "ground", "status": "verified"},
                    {"pin": "2", "net": "VMOTOR", "role": "power", "voltage": 5.02, "status": "verified"},
                    {"pin": "3", "net": "MOTOR_A", "role": "motor", "status": "verified"},
                    {"pin": "4", "net": "MOTOR_B", "role": "motor", "status": "verified"},
                ],
            }
        ],
        "resistance": [
            {"target": "power to ground no-short", "value": "pass", "unit": "ohm", "notes": "VMOTOR and GND are no-short", "status": "pass"},
            {
                "target": "MOSFET/transistor short check",
                "value": "pass",
                "unit": "ohm",
                "notes": "driver output MOSFETs are not shorted drain-source",
                "status": "pass",
            },
        ],
        "current": [{"target": "current draw under current-limited dummy load", "value": "pass", "status": "pass", "notes": "within limit"}],
        "thermal": [{"target": "thermal behavior after dummy-load test", "value": "normal", "status": "pass", "notes": "stable"}],
    }


CASES: List[Dict[str, Any]] = [
    {
        "case_id": "vision_only_uart_candidate",
        "payload": {
            "goal": "reuse photographed USB UART board",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "board_evidence": board_evidence(),
            "use_reference_catalog": False,
        },
        "expected": {
            "function": "usb_serial_debug_bridge",
            "contradictions": "soft_gaps",
            "fault_state": "needs_measurements",
            "value_decision": "identify_and_measure_before_value_decision",
            "reuse_readiness": "visual_mapping_only",
            "trust_level": "grounded_visual_candidate",
            "can_power_or_splice": False,
        },
    },
    {
        "case_id": "measured_uart_controlled_reuse",
        "payload": {
            "goal": "reuse measured UART header as debug bridge",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "topology_evidence": topology(),
            "use_reference_catalog": False,
        },
        "expected": {
            "function": "usb_serial_debug_bridge",
            "contradictions": "clear",
            "fault_state": "diagnostic_ready",
            "value_decision": "controlled_reuse_or_repair_trial",
            "reuse_readiness": "controlled_splice_ready",
            "trust_level": "controlled_reuse_ready",
            "can_power_or_splice": True,
        },
    },
    {
        "case_id": "completed_uart_production_release_candidate",
        "payload": {
            "goal": "release measured UART board as a reusable debug adapter",
            "target_authority_level": "production_repair",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "topology_evidence": topology(),
            "outcome_history": [
                {
                    "decision": "reused",
                    "selected_resource_ids_used": ["measured_uart_board"],
                    "measurements_recorded": True,
                    "cash_spent_usd": 0,
                    "value_recovered_usd": 8,
                    "time_spent_minutes": 18,
                    "deviations_from_plan": [],
                    "failure_or_stop_reason": "",
                    "output_function_verified": True,
                    "first_power_result": "pass",
                    "thermal_result": "normal",
                    "current_limit_used": True,
                    "operator_id": "operator-1",
                    "recorded_at": "2026-05-26T03:30:00Z",
                    "evidence_uri": "session://outcomes/uart-loopback",
                }
            ],
            "production_release": release_manifest(["measured_uart_board"]),
            "use_reference_catalog": False,
        },
        "expected": {
            "function": "usb_serial_debug_bridge",
            "contradictions": "clear",
            "fault_state": "diagnostic_ready",
            "value_decision": "controlled_reuse_or_repair_trial",
            "reuse_readiness": "controlled_splice_ready",
            "trust_level": "production_release_candidate",
            "can_power_or_splice": True,
        },
    },
    {
        "case_id": "shorted_uart_blocks_bad_authority",
        "payload": {
            "goal": "reuse measured UART header despite bad authority packet",
            "target_authority_level": "production_repair",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "topology_evidence": topology(short=True),
            "repair_authority": {"status": "authoritative_low_risk", "score": 0.96},
            "use_reference_catalog": False,
        },
        "expected": {
            "function": "usb_serial_debug_bridge",
            "contradictions": "hard_conflict",
            "fault_state": "blocked_safety_hold",
            "value_decision": "safety_hold_or_salvage_only",
            "reuse_readiness": "blocked_safety_hold",
            "trust_level": "blocked_safety_hold",
            "can_power_or_splice": False,
        },
    },
    {
        "case_id": "vision_only_i2c_sensor_candidate",
        "payload": {
            "goal": "reuse photographed BME280 sensor board in a logger",
            "strategy_mode": "constrained",
            "required_capabilities": ["sensor_or_adc", "connector"],
            "board_evidence": sensor_board_evidence(),
            "use_reference_catalog": False,
        },
        "expected": {
            "function": "sensor_or_adc_module",
            "contradictions": "soft_gaps",
            "fault_state": "needs_measurements",
            "value_decision": "identify_and_measure_before_value_decision",
            "reuse_readiness": "visual_mapping_only",
            "trust_level": "grounded_visual_candidate",
            "can_power_or_splice": False,
        },
    },
    {
        "case_id": "measured_motor_driver_controlled_load_reuse",
        "payload": {
            "goal": "reuse measured motor driver board for a low voltage fan",
            "strategy_mode": "constrained",
            "required_capabilities": ["actuator_driver", "motor_or_load", "power"],
            "topology_evidence": motor_topology(),
            "use_reference_catalog": False,
        },
        "expected": {
            "function": "load_or_motor_driver",
            "contradictions": "clear",
            "fault_state": "diagnostic_ready",
            "value_decision": "controlled_reuse_or_repair_trial",
            "reuse_readiness": "controlled_splice_ready",
            "trust_level": "controlled_reuse_ready",
            "can_power_or_splice": True,
        },
    },
    {
        "case_id": "vision_marked_ams1117_power_stage_candidate",
        "payload": {
            "goal": "reuse unknown marked regulator board as a bench power adapter",
            "strategy_mode": "constrained",
            "required_capabilities": ["power", "connector"],
            "board_evidence": regulator_marking_board_evidence(),
            "use_reference_catalog": False,
        },
        "expected": {
            "function": "power_distribution_or_regulator",
            "contradictions": "soft_gaps",
            "fault_state": "needs_measurements",
            "value_decision": "identify_and_measure_before_value_decision",
            "reuse_readiness": "visual_mapping_only",
            "grounded_parts": 1,
            "trust_level": "grounded_visual_candidate",
            "can_power_or_splice": False,
        },
    },
    {
        "case_id": "vision_marked_tp4056_charger_requires_specialist_path",
        "payload": {
            "goal": "evaluate a marked charger board for reuse",
            "strategy_mode": "constrained",
            "required_capabilities": ["battery", "power"],
            "board_evidence": marked_board_evidence("TP4056", "unknown charger IC", "battery and power header"),
            "use_reference_catalog": False,
        },
        "expected": {
            "function": "battery_or_charger",
            "contradictions": "soft_gaps",
            "fault_state": "needs_measurements",
            "value_decision": "identify_and_measure_before_value_decision",
            "reuse_readiness": "visual_mapping_only",
            "grounded_parts": 1,
            "trust_level": "grounded_visual_candidate",
            "can_power_or_splice": False,
        },
    },
    {
        "case_id": "vision_marked_esp32_controller_candidate",
        "payload": {
            "goal": "reuse an ESP32 board as a controller module",
            "strategy_mode": "constrained",
            "required_capabilities": ["controller", "wireless", "connector"],
            "board_evidence": marked_board_evidence("ESP32", "unknown shielded controller module", "GPIO header"),
            "use_reference_catalog": False,
        },
        "expected": {
            "function": "controller_module",
            "contradictions": "soft_gaps",
            "fault_state": "needs_measurements",
            "value_decision": "identify_and_measure_before_value_decision",
            "reuse_readiness": "visual_mapping_only",
            "grounded_parts": 1,
            "trust_level": "grounded_visual_candidate",
            "can_power_or_splice": False,
        },
    },
    {
        "case_id": "vision_marked_ssd1306_ui_candidate",
        "payload": {
            "goal": "reuse a small OLED display board as a status UI",
            "strategy_mode": "constrained",
            "required_capabilities": ["display_or_ui", "connector"],
            "board_evidence": marked_board_evidence("SSD1306", "small OLED display controller", "I2C header"),
            "use_reference_catalog": False,
        },
        "expected": {
            "function": "display_or_ui_module",
            "contradictions": "soft_gaps",
            "fault_state": "needs_measurements",
            "value_decision": "identify_and_measure_before_value_decision",
            "reuse_readiness": "visual_mapping_only",
            "grounded_parts": 1,
            "trust_level": "grounded_visual_candidate",
            "can_power_or_splice": False,
        },
    },
    {
        "case_id": "vision_marked_pam8403_audio_candidate",
        "payload": {
            "goal": "reuse a small amplifier board as an alert output",
            "strategy_mode": "constrained",
            "required_capabilities": ["speaker_or_audio", "connector"],
            "board_evidence": marked_board_evidence("PAM8403", "small audio amplifier IC", "speaker and input header"),
            "use_reference_catalog": False,
        },
        "expected": {
            "function": "audio_or_alert_module",
            "contradictions": "soft_gaps",
            "fault_state": "needs_measurements",
            "value_decision": "identify_and_measure_before_value_decision",
            "reuse_readiness": "visual_mapping_only",
            "grounded_parts": 1,
            "trust_level": "grounded_visual_candidate",
            "can_power_or_splice": False,
        },
    },
    {
        "case_id": "vision_marked_max485_network_interface_candidate",
        "payload": {
            "goal": "reuse an RS485 board as a differential bus interface",
            "strategy_mode": "constrained",
            "required_capabilities": ["network_interface", "connector"],
            "board_evidence": marked_board_evidence("MAX485", "unknown 8-pin interface IC", "A B VCC GND header"),
            "use_reference_catalog": False,
        },
        "expected": {
            "function": "wireless_or_rf_module",
            "contradictions": "soft_gaps",
            "fault_state": "needs_measurements",
            "value_decision": "identify_and_measure_before_value_decision",
            "reuse_readiness": "visual_mapping_only",
            "grounded_parts": 1,
            "trust_level": "grounded_visual_candidate",
            "can_power_or_splice": False,
        },
    },
]


def evaluate_case(planner: HardwarePlanOrchestrator, case: Dict[str, Any]) -> Dict[str, Any]:
    plan = planner.plan(case["payload"])
    analysis = plan["analysis"]
    integrated = plan["integrated_plan"]
    trust = analysis.get("arbitrary_board_trust_assessment") or {}
    actual = {
        "function": (analysis.get("board_function_inference") or {}).get("primary_function_id"),
        "contradictions": (analysis.get("evidence_contradictions") or {}).get("status"),
        "fault_state": (analysis.get("fault_isolation") or {}).get("state"),
        "value_decision": (analysis.get("salvage_value_decision") or {}).get("decision"),
        "reuse_readiness": (analysis.get("reuse_splice_strategy") or {}).get("readiness"),
        "trust_level": trust.get("level"),
        "trust_score": trust.get("score"),
        "production_readiness_score": trust.get("production_readiness_score"),
        "grounded_parts": len((analysis.get("part_grounding") or {}).get("matched_parts") or []),
        "can_power_or_splice": (integrated.get("assurance") or {}).get("can_power_or_splice"),
        "status": integrated.get("status"),
        "repair_authority": (analysis.get("repair_authority") or {}).get("status"),
    }
    expected = case["expected"]
    checks = {
        key: actual.get(key) == value
        for key, value in expected.items()
    }
    return {
        "case_id": case["case_id"],
        "passed": all(checks.values()),
        "checks": checks,
        "actual": actual,
        "expected": expected,
    }


def main() -> int:
    planner = HardwarePlanOrchestrator()
    rows = [evaluate_case(planner, case) for case in CASES]
    out_dir = ROOT / "eval" / "arbitrary_board_workflow"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(rows, indent=2, sort_keys=True))
    passed = sum(1 for row in rows if row["passed"])
    print(f"cases={len(rows)} passed={passed} pass_rate={passed / max(len(rows), 1):.3f}")
    for row in rows:
        print(f"{row['case_id']}: passed={row['passed']} actual={row['actual']}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
