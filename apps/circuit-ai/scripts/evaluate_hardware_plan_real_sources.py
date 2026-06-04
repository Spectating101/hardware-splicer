#!/usr/bin/env python3
"""Evaluate hardware planning against public-source grounded maker examples."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.intelligence.hardware_plan import HardwarePlanOrchestrator  # noqa: E402


def trusted_measurement(measurement_type: str, target: str, value: Any, notes: str, *, unit: str = "") -> Dict[str, Any]:
    return {
        "type": measurement_type,
        "target": target,
        "value": value,
        "unit": unit,
        "notes": notes,
        "instrument_id": "bench_dmm_01" if measurement_type != "thermal" else "thermal_probe_01",
        "instrument_type": "calibrated_dmm" if measurement_type != "thermal" else "thermal_probe",
        "calibration_status": "valid",
        "recorded_at": "2026-05-26T02:00:00Z",
        "operator_id": "operator-1",
        "evidence_uri": f"session://hardware-plan-real-source/{measurement_type}/{target}",
    }


def release_manifest(resource_ids: Sequence[str], *, release_id: str) -> Dict[str, Any]:
    return {
        "release_id": release_id,
        "selected_resource_ids": list(resource_ids),
        "released_by": "operator-1",
        "released_at": "2026-05-26T03:00:00Z",
        "scope_statement": "Production release is limited to the measured resources, low-voltage evidence, and recorded terminal outcome in this eval case.",
        "artifact_uris": ["session://hardware-plan-real-source/release/test-report", "session://hardware-plan-real-source/release/photos"],
        "acceptance_reviewed": True,
        "repeatability_count": 1,
    }


PASS_UART_MEASUREMENTS = [
    trusted_measurement("resistance", "power to ground no-short", "pass", "unpowered resistance between power and ground is no-short"),
    trusted_measurement("continuity", "connector ground to exposed ground", "pass", "connector ground continuity ok"),
    trusted_measurement("voltage", "UART logic high voltage", 3.31, "UART TX/RX idle high at 3.3V", unit="V"),
    trusted_measurement("continuity", "shared ground continuity", "pass", "shared ground continuity pass"),
    trusted_measurement("logic_level", "serial UART idle state", "pass", "serial idle high and stable before connecting target board"),
    trusted_measurement("current", "current draw under current-limited supply", "pass", "current draw under current-limited supply within limit"),
    trusted_measurement("thermal", "thermal behavior after first power", "normal", "temperature stable and no abnormal heat"),
]


REAL_SOURCE_CASES: List[Dict[str, Any]] = [
    {
        "case_id": "sparkfun_ch340c_uart_complete",
        "title": "SparkFun CH340C USB-C serial adapter completes after bench proof",
        "source": {
            "name": "SparkFun Serial Basic Breakout - CH340C and USB-C",
            "url": "https://www.sparkfun.com/sparkfun-serial-basic-breakout-ch340c-and-usb-c.html",
            "grounding": [
                "CH340C USB-to-Serial adapter.",
                "Works with 5V and 3.3V systems.",
                "Breaks out DTR/RXI/TXO/VCC/CTS/GND style serial pins.",
            ],
        },
        "allowed_selected_ids": ["sparkfun_ch340c"],
        "payload": {
            "goal": "use a SparkFun CH340C USB-C serial adapter to program and debug a 3.3V low-voltage target",
            "target_authority_level": "production_repair",
            "strategy_mode": "hybrid",
            "required_capabilities": ["usb_serial", "connector"],
            "available_resources": [
                {
                    "resource_id": "sparkfun_ch340c",
                    "name": "SparkFun Serial Basic Breakout CH340C USB-C",
                    "resource_kind": "owned",
                    "capabilities": ["usb_serial", "connector"],
                    "confidence": 0.9,
                    "evidence_status": "verified",
                }
            ],
            "measurements": PASS_UART_MEASUREMENTS,
            "outcome_history": [
                {
                    "decision": "built",
                    "selected_resource_ids_used": ["sparkfun_ch340c"],
                    "measurements_recorded": True,
                    "cash_spent_usd": 0,
                    "value_recovered_usd": 10.5,
                    "time_spent_minutes": 15,
                    "deviations_from_plan": [],
                    "failure_or_stop_reason": "",
                    "output_function_verified": True,
                    "first_power_result": "pass",
                    "thermal_result": "normal",
                    "current_limit_used": True,
                    "evidence_uri": "session://outcomes/sparkfun-ch340c-loopback",
                }
            ],
            "production_release": release_manifest(["sparkfun_ch340c"], release_id="REAL-SRC-CH340C-001"),
            "repair_authority": {
                "status": "authoritative_low_risk",
                "score": 0.91,
                "required_measurements": [],
                "blocked_decisions": [],
            },
            "use_reference_catalog": False,
        },
        "expected": {
            "status": "ready_for_build_plan",
            "completion_state": "workflow_complete",
            "execution_stage": "complete",
            "can_power_or_splice": True,
            "selected_exact": ["sparkfun_ch340c"],
            "missing_equals": [],
            "open_gate_count": 0,
            "next_actions_empty": True,
            "production_authorized": True,
        },
    },
    {
        "case_id": "sparkfun_ch340c_public_reference_pinout",
        "title": "SparkFun CH340C official pinout seeds topology but still requires bench confirmation",
        "source": {
            "name": "SparkFun Serial Basic Breakout - CH340C and USB-C",
            "url": "https://www.sparkfun.com/sparkfun-serial-basic-breakout-ch340c-and-usb-c.html",
            "grounding": [
                "Official pinout is DTR/RXI/TXO/VCC/CTS/GND.",
                "Default VCC and logic level are 3.3V unless the rear jumper is changed.",
                "Public pinout is reference topology, not a bench measurement of a salvaged board.",
            ],
        },
        "allowed_selected_ids": ["topology_j1", "uart_serial"],
        "payload": {
            "goal": "reuse a SparkFun CH340C serial board from public pinout reference",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "topology_evidence": {
                "schema_version": "topology_evidence.v1",
                "source_type": "public_reference_topology",
                "reference_uri": "https://www.sparkfun.com/sparkfun-serial-basic-breakout-ch340c-and-usb-c.html",
                "connectors": [
                    {
                        "ref": "J1",
                        "label": "SparkFun CH340C FTDI-style header",
                        "pins": [
                            {"pin": "1", "net": "DTR", "role": "dtr"},
                            {"pin": "2", "net": "RXI", "role": "rxi", "logic_voltage": 3.3},
                            {"pin": "3", "net": "TXO", "role": "txo", "logic_voltage": 3.3},
                            {"pin": "4", "net": "VCC", "role": "vcc", "voltage": 3.3},
                            {"pin": "5", "net": "CTS", "role": "cts"},
                            {"pin": "6", "net": "GND", "role": "gnd"},
                        ],
                    }
                ],
            },
            "use_reference_catalog": False,
        },
        "expected": {
            "status": "prototype_after_evidence",
            "completion_state": "evidence_required",
            "can_power_or_splice": False,
            "selected_contains": ["uart_serial"],
            "missing_equals": [],
            "next_actions_contain": ["unpowered resistance"],
            "production_authorized": False,
        },
    },
    {
        "case_id": "adafruit_bme280_public_reference_pinout",
        "title": "Adafruit BME280 official pinout gives I2C/SPI topology but remains evidence-gated",
        "source": {
            "name": "Adafruit BME280 Humidity + Barometric Pressure + Temperature Sensor Breakout",
            "url": "https://learn.adafruit.com/adafruit-bme280-humidity-barometric-pressure-temperature-sensor-breakout/pinouts",
            "grounding": [
                "Vin accepts 3-5V and GND is common ground.",
                "SCK/SDI can be used as I2C SCL/SDA for the breakout wiring path.",
                "SPI pins SCK/SDO/SDI/CS are also exposed.",
            ],
        },
        "allowed_selected_ids": ["topology_j1"],
        "payload": {
            "goal": "reuse an Adafruit BME280 breakout as an I2C environmental sensor",
            "strategy_mode": "constrained",
            "required_capabilities": ["sensor_or_adc", "power", "connector"],
            "topology_evidence": {
                "schema_version": "topology_evidence.v1",
                "source_type": "public_reference_topology",
                "reference_uri": "https://learn.adafruit.com/adafruit-bme280-humidity-barometric-pressure-temperature-sensor-breakout/pinouts",
                "connectors": [
                    {
                        "ref": "J1",
                        "label": "Adafruit BME280 breakout header",
                        "pins": [
                            {"pin": "1", "net": "VIN", "role": "vin"},
                            {"pin": "2", "net": "3VO", "role": "3v3"},
                            {"pin": "3", "net": "GND", "role": "gnd"},
                            {"pin": "4", "net": "SCK/SCL", "role": "i2c_scl", "logic_voltage": 3.3},
                            {"pin": "5", "net": "SDI/SDA", "role": "i2c_sda", "logic_voltage": 3.3},
                            {"pin": "6", "net": "SDO", "role": "spi_miso", "logic_voltage": 3.3},
                            {"pin": "7", "net": "CS", "role": "spi_cs", "logic_voltage": 3.3},
                        ],
                    }
                ],
            },
            "use_reference_catalog": False,
        },
        "expected": {
            "status": "prototype_after_evidence",
            "completion_state": "evidence_required",
            "can_power_or_splice": False,
            "selected_contains": ["topology_j1"],
            "missing_equals": [],
            "next_actions_contain": ["unpowered resistance"],
            "production_authorized": False,
        },
    },
    {
        "case_id": "adafruit_drv8833_public_reference_pinout",
        "title": "Adafruit DRV8833 official pinout maps motor/control pins but blocks load use",
        "source": {
            "name": "Adafruit DRV8833 DC/Stepper Motor Driver Breakout Board",
            "url": "https://learn.adafruit.com/adafruit-drv8833-dc-stepper-motor-driver-breakout-board/pinouts",
            "grounding": [
                "Vmotor is motor voltage and GND is shared logic/motor ground.",
                "AIN1/AIN2/BIN1/BIN2 are logic inputs.",
                "Motor A and Motor B outputs are motor power outputs.",
            ],
        },
        "allowed_selected_ids": ["topology_j1"],
        "payload": {
            "goal": "reuse an Adafruit DRV8833 breakout as a dual motor driver",
            "strategy_mode": "constrained",
            "required_capabilities": ["actuator_driver", "motor_or_load", "power", "connector"],
            "topology_evidence": {
                "schema_version": "topology_evidence.v1",
                "source_type": "public_reference_topology",
                "reference_uri": "https://learn.adafruit.com/adafruit-drv8833-dc-stepper-motor-driver-breakout-board/pinouts",
                "connectors": [
                    {
                        "ref": "J1",
                        "label": "Adafruit DRV8833 breakout pins",
                        "pins": [
                            {"pin": "VMOTOR", "net": "VMOTOR", "role": "vin"},
                            {"pin": "GND", "net": "GND", "role": "gnd"},
                            {"pin": "AIN1", "net": "AIN1", "role": "ain1", "logic_voltage": 3.3},
                            {"pin": "AIN2", "net": "AIN2", "role": "ain2", "logic_voltage": 3.3},
                            {"pin": "BIN1", "net": "BIN1", "role": "bin1", "logic_voltage": 3.3},
                            {"pin": "BIN2", "net": "BIN2", "role": "bin2", "logic_voltage": 3.3},
                            {"pin": "SLP", "net": "SLP", "role": "slp", "logic_voltage": 3.3},
                            {"pin": "FLT", "net": "FLT", "role": "flt", "logic_voltage": 3.3},
                            {"pin": "AOUT1", "net": "AOUT1", "role": "aout1"},
                            {"pin": "AOUT2", "net": "AOUT2", "role": "aout2"},
                            {"pin": "BOUT1", "net": "BOUT1", "role": "bout1"},
                            {"pin": "BOUT2", "net": "BOUT2", "role": "bout2"},
                        ],
                    }
                ],
            },
            "use_reference_catalog": False,
        },
        "expected": {
            "status": "prototype_after_evidence",
            "completion_state": "evidence_required",
            "can_power_or_splice": False,
            "selected_contains": ["topology_j1"],
            "missing_equals": [],
            "next_actions_contain": ["startup current"],
            "production_authorized": False,
        },
    },
    {
        "case_id": "adafruit_bme280_esp32_hybrid",
        "title": "ESP32 plus BME280 logger buys only the missing sensor and remains evidence-gated",
        "source": {
            "name": "Adafruit BME280 Humidity + Barometric Pressure + Temperature Sensor Breakout",
            "url": "https://learn.adafruit.com/adafruit-bme280-humidity-barometric-pressure-temperature-sensor-breakout?view=all",
            "grounding": [
                "BME280 is a temperature, pressure, and humidity environmental sensor.",
                "The breakout supports I2C or SPI.",
                "Vin accepts 3-5V and GND is common power/data ground.",
                "I2C wiring uses SCK as clock and SDI as data.",
            ],
        },
        "allowed_selected_ids": ["owned_esp32", "usb_power_bank", "adafruit_bme280"],
        "payload": {
            "goal": "build an ESP32 BME280 environmental sensor logger using I2C",
            "strategy_mode": "hybrid",
            "constraints": {"budget_usd": 20},
            "required_capabilities": ["controller", "sensor_or_adc", "power", "connector"],
            "available_resources": [
                {
                    "resource_id": "owned_esp32",
                    "name": "ESP32 dev board",
                    "resource_kind": "owned",
                    "capabilities": ["controller", "wireless", "usb_serial", "connector"],
                    "confidence": 0.84,
                    "evidence_status": "verified",
                },
                {
                    "resource_id": "usb_power_bank",
                    "name": "USB power bank and cable",
                    "resource_kind": "owned",
                    "capabilities": ["power", "connector"],
                    "confidence": 0.78,
                    "evidence_status": "verified",
                },
            ],
            "procurable_catalog": [
                {
                    "resource_id": "adafruit_bme280",
                    "name": "Adafruit BME280 I2C or SPI sensor breakout",
                    "resource_kind": "procurable",
                    "capabilities": ["sensor_or_adc", "connector"],
                    "cost_usd": 14.95,
                    "confidence": 0.9,
                }
            ],
            "use_reference_catalog": False,
        },
        "expected": {
            "status": "prototype_after_evidence",
            "completion_state": "evidence_required",
            "execution_stage": "procurement_gap_fill",
            "can_power_or_splice": False,
            "selected_contains": ["owned_esp32", "usb_power_bank", "adafruit_bme280"],
            "missing_equals": [],
            "procurement_within_budget": True,
            "next_actions_contain": ["Confirm datasheet", "unpowered resistance"],
            "production_authorized": False,
        },
    },
    {
        "case_id": "adafruit_bme280_constrained_no_sensor",
        "title": "Constrained ESP32 logger refuses to invent the missing BME280 sensor",
        "source": {
            "name": "Adafruit BME280 Humidity + Barometric Pressure + Temperature Sensor Breakout",
            "url": "https://learn.adafruit.com/adafruit-bme280-humidity-barometric-pressure-temperature-sensor-breakout?view=all",
            "grounding": [
                "The public example requires a real BME280 sensor breakout for environmental readings.",
                "The logger goal alone is not evidence that the sensor exists in inventory.",
            ],
        },
        "allowed_selected_ids": ["owned_esp32", "usb_power_bank"],
        "payload": {
            "goal": "build an ESP32 BME280 environmental sensor logger using I2C",
            "strategy_mode": "constrained",
            "required_capabilities": ["controller", "sensor_or_adc", "power", "connector"],
            "available_resources": [
                {
                    "resource_id": "owned_esp32",
                    "name": "ESP32 dev board",
                    "resource_kind": "owned",
                    "capabilities": ["controller", "wireless", "usb_serial", "connector"],
                    "confidence": 0.84,
                    "evidence_status": "verified",
                },
                {
                    "resource_id": "usb_power_bank",
                    "name": "USB power bank and cable",
                    "resource_kind": "owned",
                    "capabilities": ["power", "connector"],
                    "confidence": 0.78,
                    "evidence_status": "verified",
                },
            ],
            "use_reference_catalog": False,
        },
        "expected": {
            "status": "blocked_missing_resources",
            "completion_state": "blocked",
            "can_power_or_splice": False,
            "selected_exact": ["owned_esp32", "usb_power_bank"],
            "selected_excludes": ["sensor", "bme280", "adafruit_bme280"],
            "missing_equals": ["sensor_or_adc"],
            "next_actions_contain": ["missing capability: sensor_or_adc"],
            "production_authorized": False,
        },
    },
    {
        "case_id": "adafruit_drv8833_motor_hybrid",
        "title": "DRV8833 motor stage selects driver, motor, controller, and power but blocks first power",
        "source": {
            "name": "Adafruit DRV8833 DC/Stepper Motor Driver Breakout Board",
            "url": "https://learn.adafruit.com/adafruit-drv8833-dc-stepper-motor-driver-breakout-board?view=all",
            "grounding": [
                "DRV8833 is a motor driver breakout for DC/stepper motors.",
                "Motor supply must stay in the specified low-voltage range.",
                "Motors require external power, shared ground, and output coil/load wiring.",
            ],
        },
        "allowed_selected_ids": ["owned_feather", "small_dc_motors", "nine_volt_supply", "adafruit_drv8833"],
        "payload": {
            "goal": "build a low-voltage two-motor driver stage with a DRV8833 breakout",
            "strategy_mode": "hybrid",
            "required_capabilities": ["controller", "actuator_driver", "motor_or_load", "power", "connector"],
            "available_resources": [
                {
                    "resource_id": "owned_feather",
                    "name": "Feather or ESP32 controller",
                    "resource_kind": "owned",
                    "capabilities": ["controller", "connector"],
                    "confidence": 0.84,
                    "evidence_status": "verified",
                },
                {
                    "resource_id": "small_dc_motors",
                    "name": "two small DC motors",
                    "resource_kind": "owned",
                    "capabilities": ["motor_or_load"],
                    "confidence": 0.7,
                    "evidence_status": "needs_evidence",
                },
                {
                    "resource_id": "nine_volt_supply",
                    "name": "9V current-limited bench supply",
                    "resource_kind": "owned",
                    "capabilities": ["power"],
                    "confidence": 0.82,
                    "evidence_status": "verified",
                },
            ],
            "procurable_catalog": [
                {
                    "resource_id": "adafruit_drv8833",
                    "name": "Adafruit DRV8833 DC/Stepper Motor Driver Breakout",
                    "resource_kind": "procurable",
                    "capabilities": ["actuator_driver", "connector"],
                    "cost_usd": 4.95,
                    "confidence": 0.9,
                }
            ],
            "use_reference_catalog": False,
        },
        "expected": {
            "status": "prototype_after_evidence",
            "completion_state": "evidence_required",
            "execution_stage": "procurement_gap_fill",
            "can_power_or_splice": False,
            "selected_contains": ["owned_feather", "small_dc_motors", "nine_volt_supply", "adafruit_drv8833"],
            "missing_equals": [],
            "next_actions_contain": ["Confirm datasheet", "startup current"],
            "production_authorized": False,
        },
    },
    {
        "case_id": "adafruit_lipo_swollen_pack_safety",
        "title": "Swollen LiPoly pack is blocked as unsafe power",
        "source": {
            "name": "Adafruit Li-Ion & LiPoly Batteries",
            "url": "https://learn.adafruit.com/li-ion-and-lipoly-batteries?view=all",
            "grounding": [
                "Li-Ion/LiPoly batteries are power dense and require care during use and charging.",
                "Datasheets and safety guidance matter for safe voltage, current, and temperature limits.",
                "A swollen pack is treated as unsafe project power.",
            ],
        },
        "allowed_selected_ids": ["swollen_lipo"],
        "payload": {
            "goal": "reuse a swollen LiPoly battery as project power",
            "strategy_mode": "constrained",
            "required_capabilities": ["power"],
            "available_resources": [
                {
                    "resource_id": "swollen_lipo",
                    "name": "swollen LiPoly pouch battery",
                    "resource_kind": "salvaged",
                    "capabilities": ["power", "battery"],
                    "confidence": 0.8,
                }
            ],
            "use_reference_catalog": False,
        },
        "expected": {
            "status": "safety_hold",
            "completion_state": "blocked",
            "can_power_or_splice": False,
            "selected_exact": [],
            "selected_excludes": ["swollen_lipo"],
            "missing_equals": ["power"],
            "next_actions_contain": ["do not power"],
            "production_authorized": False,
        },
    },
]


def selected_ids(plan: Dict[str, Any]) -> List[str]:
    strategy = plan.get("resource_strategy") if isinstance(plan.get("resource_strategy"), dict) else {}
    return [str(resource.get("resource_id")) for resource in strategy.get("selected_resources") or []]


def missing_capabilities(plan: Dict[str, Any]) -> List[str]:
    strategy = plan.get("resource_strategy") if isinstance(plan.get("resource_strategy"), dict) else {}
    coverage = strategy.get("coverage") if isinstance(strategy.get("coverage"), dict) else {}
    return sorted(str(item) for item in coverage.get("missing_capabilities") or [])


def next_action_text(plan: Dict[str, Any]) -> str:
    integrated = plan.get("integrated_plan") if isinstance(plan.get("integrated_plan"), dict) else {}
    return " | ".join(str(item) for item in integrated.get("next_actions") or []).lower()


def selected_resource_hallucinations(plan: Dict[str, Any], allowed: Sequence[str]) -> List[str]:
    allowed_ids = set(str(item) for item in allowed)
    return sorted(resource_id for resource_id in selected_ids(plan) if resource_id not in allowed_ids)


def check_case(case: Dict[str, Any], plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    expected = case.get("expected") if isinstance(case.get("expected"), dict) else {}
    integrated = plan.get("integrated_plan") if isinstance(plan.get("integrated_plan"), dict) else {}
    assurance = integrated.get("assurance") if isinstance(integrated.get("assurance"), dict) else {}
    completion = integrated.get("completion_contract") if isinstance(integrated.get("completion_contract"), dict) else {}
    execution = integrated.get("execution_package") if isinstance(integrated.get("execution_package"), dict) else {}
    strategy = plan.get("resource_strategy") if isinstance(plan.get("resource_strategy"), dict) else {}
    procurement = strategy.get("procurement_plan") if isinstance(strategy.get("procurement_plan"), dict) else {}
    production = integrated.get("production_repair_authority") if isinstance(integrated.get("production_repair_authority"), dict) else {}

    checks: List[Dict[str, Any]] = []

    def add(name: str, passed: bool, actual: Any = None, expected_value: Any = None) -> None:
        checks.append(
            {
                "name": name,
                "passed": bool(passed),
                "actual": actual,
                "expected": expected_value,
            }
        )

    if "status" in expected:
        add("status", integrated.get("status") == expected["status"], integrated.get("status"), expected["status"])
    if "completion_state" in expected:
        add(
            "completion_state",
            completion.get("state") == expected["completion_state"],
            completion.get("state"),
            expected["completion_state"],
        )
    if "execution_stage" in expected:
        add(
            "execution_stage",
            execution.get("current_stage") == expected["execution_stage"],
            execution.get("current_stage"),
            expected["execution_stage"],
        )
    if "can_power_or_splice" in expected:
        add(
            "can_power_or_splice",
            assurance.get("can_power_or_splice") is expected["can_power_or_splice"],
            assurance.get("can_power_or_splice"),
            expected["can_power_or_splice"],
        )
    if "open_gate_count" in expected:
        add("open_gate_count", assurance.get("open_gate_count") == expected["open_gate_count"], assurance.get("open_gate_count"), expected["open_gate_count"])
    if "selected_exact" in expected:
        add("selected_exact", sorted(selected_ids(plan)) == sorted(expected["selected_exact"]), selected_ids(plan), expected["selected_exact"])
    if "selected_contains" in expected:
        selected = set(selected_ids(plan))
        wanted = set(str(item) for item in expected["selected_contains"])
        add("selected_contains", wanted.issubset(selected), sorted(selected), sorted(wanted))
    if "selected_excludes" in expected:
        selected = set(selected_ids(plan))
        forbidden = set(str(item) for item in expected["selected_excludes"])
        add("selected_excludes", selected.isdisjoint(forbidden), sorted(selected), sorted(forbidden))
    if "missing_equals" in expected:
        add("missing_equals", missing_capabilities(plan) == sorted(expected["missing_equals"]), missing_capabilities(plan), sorted(expected["missing_equals"]))
    if "procurement_within_budget" in expected:
        add(
            "procurement_within_budget",
            procurement.get("within_budget") is expected["procurement_within_budget"],
            procurement.get("within_budget"),
            expected["procurement_within_budget"],
        )
    if expected.get("next_actions_empty") is True:
        add("next_actions_empty", integrated.get("next_actions") == [], integrated.get("next_actions"), [])
    for phrase in expected.get("next_actions_contain") or []:
        add(f"next_actions_contain:{phrase}", str(phrase).lower() in next_action_text(plan), integrated.get("next_actions"), phrase)
    if "production_authorized" in expected:
        add(
            "production_authorized",
            production.get("authorized") is expected["production_authorized"],
            production.get("authorized"),
            expected["production_authorized"],
        )

    hallucinated = selected_resource_hallucinations(plan, case.get("allowed_selected_ids") or [])
    add("no_unallowed_selected_resources", hallucinated == [], hallucinated, [])
    return checks


def evaluate_cases(cases: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    planner = HardwarePlanOrchestrator()
    rows = []
    for case in cases:
        plan = planner.plan(case["payload"])
        checks = check_case(case, plan)
        passed = len([check for check in checks if check["passed"]])
        score = round(passed / max(len(checks), 1), 3)
        integrated = plan.get("integrated_plan") if isinstance(plan.get("integrated_plan"), dict) else {}
        assurance = integrated.get("assurance") if isinstance(integrated.get("assurance"), dict) else {}
        completion = integrated.get("completion_contract") if isinstance(integrated.get("completion_contract"), dict) else {}
        production = integrated.get("production_repair_authority") if isinstance(integrated.get("production_repair_authority"), dict) else {}
        rows.append(
            {
                "case_id": case["case_id"],
                "title": case["title"],
                "source": case["source"],
                "score": score,
                "passed_assertions": passed,
                "total_assertions": len(checks),
                "all_passed": passed == len(checks),
                "status": integrated.get("status"),
                "assurance": assurance.get("level"),
                "can_power_or_splice": assurance.get("can_power_or_splice"),
                "completion_state": completion.get("state"),
                "production_authorized": bool(production.get("authorized")),
                "production_decision": production.get("decision"),
                "selected_resources": selected_ids(plan),
                "missing_capabilities": missing_capabilities(plan),
                "hallucinated_selected_resources": selected_resource_hallucinations(plan, case.get("allowed_selected_ids") or []),
                "next_actions": integrated.get("next_actions") or [],
                "checks": checks,
            }
        )

    all_passed = [row for row in rows if row["all_passed"]]
    hallucination_rows = [row for row in rows if row["hallucinated_selected_resources"]]
    safety_rows = [row for row in rows if row["case_id"].endswith("_safety")]
    evidence_gated_rows = [
        row for row in rows if row["completion_state"] == "evidence_required" and row["can_power_or_splice"] is False
    ]
    production_authorized_rows = [row for row in rows if row["production_authorized"]]
    summary = {
        "case_count": len(rows),
        "all_passed_count": len(all_passed),
        "pass_rate": round(len(all_passed) / max(len(rows), 1), 3),
        "average_assertion_score": round(sum(row["score"] for row in rows) / max(len(rows), 1), 3),
        "hallucinated_resource_case_count": len(hallucination_rows),
        "production_authorized_count": len(production_authorized_rows),
        "production_authorized_cases": [row["case_id"] for row in production_authorized_rows],
        "safety_hold_case_count": len([row for row in safety_rows if row["status"] == "safety_hold"]),
        "evidence_gated_case_count": len(evidence_gated_rows),
        "weak_cases": [row["case_id"] for row in rows if not row["all_passed"]],
    }
    return {
        "mode": "hardware_plan_real_source_eval",
        "schema_version": "hardware_plan_real_source_eval.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "cases": rows,
        "trust_bar": {
            "portfolio_demo_engine": "pass" if summary["pass_rate"] == 1.0 and summary["hallucinated_resource_case_count"] == 0 else "review",
            "serious_development_foundation": "pass" if summary["average_assertion_score"] >= 0.95 and summary["hallucinated_resource_case_count"] == 0 else "review",
            "production_repair_authority": (
                "narrow_low_voltage_pass"
                if summary["production_authorized_count"] >= 1
                and summary["hallucinated_resource_case_count"] == 0
                and summary["pass_rate"] == 1.0
                else "not_yet"
            ),
            "reason": "Production authority is only for measured low-voltage workflows with terminal outcome proof; broad repair authority still needs calibrated image/measurement capture and field validation.",
        },
    }


def render_markdown(report: Dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Hardware Plan Real-Source Eval",
        "",
        "Grounded eval using public maker hardware examples. The sources are used to shape realistic scenarios; the engine is still scored on deterministic behavior.",
        "",
        "## Summary",
        "",
        f"- Cases: {summary['case_count']}",
        f"- Full pass rate: {summary['pass_rate']}",
        f"- Average assertion score: {summary['average_assertion_score']}",
        f"- Hallucinated selected-resource cases: {summary['hallucinated_resource_case_count']}",
        f"- Production-authorized cases: {summary['production_authorized_count']}",
        f"- Safety holds passed: {summary['safety_hold_case_count']}",
        f"- Evidence-gated cases: {summary['evidence_gated_case_count']}",
        f"- Portfolio demo engine: {report['trust_bar']['portfolio_demo_engine']}",
        f"- Serious development foundation: {report['trust_bar']['serious_development_foundation']}",
        f"- Production repair authority: {report['trust_bar']['production_repair_authority']}",
        "",
        "## Cases",
        "",
        "| Case | Score | Status | Completion | Production | Can power/splice | Selected | Missing | Source |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["cases"]:
        source = row["source"]
        lines.append(
            "| `{case}` | {score:.3f} | `{status}` | `{completion}` | `{production}` | `{can}` | {selected} | {missing} | [{source_name}]({source_url}) |".format(
                case=row["case_id"],
                score=row["score"],
                status=row["status"],
                completion=row["completion_state"],
                production=row["production_decision"],
                can=row["can_power_or_splice"],
                selected=", ".join(f"`{item}`" for item in row["selected_resources"]) or "-",
                missing=", ".join(f"`{item}`" for item in row["missing_capabilities"]) or "-",
                source_name=source["name"],
                source_url=source["url"],
            )
        )

    lines.extend(["", "## Failed Assertions", ""])
    failures = 0
    for row in report["cases"]:
        failed = [check for check in row["checks"] if not check["passed"]]
        if not failed:
            continue
        failures += len(failed)
        lines.append(f"### {row['case_id']}")
        for check in failed:
            lines.append(f"- `{check['name']}` actual={check['actual']!r} expected={check['expected']!r}")
        lines.append("")
    if failures == 0:
        lines.append("No failed assertions.")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("eval/hardware_plan_real_sources"))
    args = parser.parse_args()

    report = evaluate_cases(REAL_SOURCE_CASES)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (args.output_dir / "cases.json").write_text(json.dumps(REAL_SOURCE_CASES, indent=2), encoding="utf-8")
    (args.output_dir / "README.md").write_text(render_markdown(report), encoding="utf-8")

    summary = report["summary"]
    print(f"wrote {args.output_dir}")
    print(
        "cases={case_count} pass_rate={pass_rate} avg={average_assertion_score} "
        "hallucinated={hallucinated_resource_case_count} production_authorized={production_authorized_count} weak={weak_cases}".format(**summary)
    )
    for row in report["cases"]:
        print(
            f"{row['case_id']}: score={row['score']} status={row['status']} "
            f"completion={row['completion_state']} production={row['production_decision']} "
            f"selected={row['selected_resources']} missing={row['missing_capabilities']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
