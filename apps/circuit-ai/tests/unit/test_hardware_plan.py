from pathlib import Path

from src.api.v1 import main as main_module
from src.intelligence.board_session_store import BoardSessionStore
from src.intelligence.hardware_plan import HardwarePlanOrchestrator
from src.intelligence.salvage_splice_planner import SalvageSplicePlanner


ROOT = Path(__file__).resolve().parents[4]
DEMO_NETLIST = ROOT / "examples" / "main_ctrl_esp32_servo.net"


def _trusted_measurement(measurement_type, target, value, notes, *, unit=""):
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
        "evidence_uri": f"session://measurements/{measurement_type}/{target}",
    }


def _release_manifest(resource_ids, *, release_id="REL-LOW-001"):
    return {
        "release_id": release_id,
        "selected_resource_ids": resource_ids,
        "released_by": "operator-1",
        "released_at": "2026-05-26T03:00:00Z",
        "scope_statement": "Production release is limited to the measured resources, low-voltage evidence, and recorded terminal outcome in this plan.",
        "artifact_uris": ["session://release/test-report", "session://release/photos"],
        "acceptance_reviewed": True,
        "repeatability_count": 1,
    }


def test_hardware_plan_chains_resource_strategy_into_selected_splice_plan():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "build a sensor logger from one owned ESP32 and buy only the gaps",
            "strategy_mode": "hybrid",
            "constraints": {"budget_usd": 5},
            "required_capabilities": ["controller", "sensor_or_adc", "power"],
            "available_resources": [
                {
                    "resource_id": "drawer_esp32",
                    "name": "ESP32 board from drawer",
                    "resource_kind": "owned",
                    "capabilities": ["controller", "wireless", "usb_serial"],
                    "confidence": 0.84,
                    "evidence_status": "verified",
                }
            ],
            "procurable_catalog": [
                {
                    "resource_id": "sensor_breakout",
                    "name": "I2C sensor breakout",
                    "resource_kind": "procurable",
                    "capabilities": ["sensor_or_adc"],
                    "cost_usd": 2.5,
                    "confidence": 0.86,
                },
                {
                    "resource_id": "buck",
                    "name": "buck converter",
                    "resource_kind": "procurable",
                    "capabilities": ["power"],
                    "cost_usd": 2.0,
                    "confidence": 0.86,
                },
            ],
            "use_reference_catalog": False,
        }
    )

    integrated = plan["integrated_plan"]
    selected_ids = set(plan["build_splice_plan"]["resource_strategy_link"]["selected_resource_ids"])

    assert plan["mode"] == "hardware_plan"
    assert plan["resource_strategy"]["coverage"]["coverage_score"] == 1
    assert {"drawer_esp32", "sensor_breakout", "buck"}.issubset(selected_ids)
    assert plan["build_splice_plan"]["target"]["recommended_build_id"] == "sensor_logger"
    assert integrated["status"] == "prototype_after_evidence"
    assert integrated["assurance"]["level"] == "prototype_gated"
    assert integrated["assurance"]["can_build_now"] is False
    assert integrated["assurance"]["measurement_gate_count"] > 0
    assert integrated["execution_package"]["current_stage"] in {"procurement_gap_fill", "evidence_closure", "bench_validation"}
    assert integrated["execution_package"]["outcome_contract"]["required_fields"]
    assert any(stage["stage_id"] == "first_power_or_splice" and stage["status"] == "blocked_until_authority" for stage in integrated["execution_package"]["stages"])
    assert integrated["procurement"]["estimated_cost_usd"] == 4.5
    assert integrated["first_measurements"]
    assert plan["analysis"]["machine_connection_map"]["splice_plan"]["required_measurements"]


def test_hardware_plan_constrained_mode_does_not_invent_goal_text_resources():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "build a sensor logger from an ESP32",
            "strategy_mode": "constrained",
            "required_capabilities": ["controller", "sensor_or_adc", "power"],
            "available_resources": [
                {
                    "resource_id": "drawer_esp32",
                    "name": "ESP32 board from drawer",
                    "resource_kind": "owned",
                    "capabilities": ["controller", "wireless", "usb_serial"],
                    "confidence": 0.84,
                    "evidence_status": "verified",
                }
            ],
            "use_reference_catalog": False,
        }
    )

    selected_ids = {resource["resource_id"] for resource in plan["resource_strategy"]["selected_resources"]}

    assert selected_ids == {"drawer_esp32"}
    assert plan["resource_strategy"]["coverage"]["missing_capabilities"] == ["power", "sensor_or_adc"]
    assert plan["integrated_plan"]["status"] == "blocked_missing_resources"
    assert plan["integrated_plan"]["execution_package"]["completion_state"] == "blocked"


def test_hardware_plan_repair_authority_downgrades_ready_build_until_measurements_close():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "build a UART debug adapter from a known CH340 module",
            "strategy_mode": "hybrid",
            "required_capabilities": ["usb_serial", "connector"],
            "available_resources": [
                {
                    "resource_id": "known_ch340",
                    "name": "known CH340 adapter",
                    "resource_kind": "owned",
                    "capabilities": ["usb_serial", "connector"],
                    "confidence": 0.9,
                    "evidence_status": "verified",
                }
            ],
            "repair_authority": {
                "status": "measurement_backed",
                "score": 0.72,
                "required_measurements": ["Confirm UART idle high voltage before connecting target board."],
                "blocked_decisions": ["production repair release"],
                "measurement_summary": {"count": 1},
            },
            "use_reference_catalog": False,
        }
    )

    integrated = plan["integrated_plan"]
    prompts = [gate["prompt"] for gate in integrated["evidence_gates"]]

    assert integrated["status"] == "prototype_after_evidence"
    assert integrated["assurance"]["level"] == "prototype_gated"
    assert integrated["assurance"]["review_gate_count"] >= 1
    assert integrated["assurance"]["can_power_or_splice"] is False
    assert integrated["authority"]["repair_authority_status"] == "measurement_backed"
    assert any("UART idle high voltage" in prompt for prompt in prompts)
    assert any("production repair release" in prompt for prompt in prompts)
    assert "authority" in plan["analysis"]["hardware_plan_summary"]
    assert "assurance" in plan["analysis"]["hardware_plan_summary"]


def test_hardware_plan_closes_matching_measurement_gates_and_authorizes_power():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "build a UART debug adapter from a known CH340 module",
            "strategy_mode": "hybrid",
            "required_capabilities": ["usb_serial", "connector"],
            "available_resources": [
                {
                    "resource_id": "known_ch340",
                    "name": "known CH340 adapter",
                    "resource_kind": "owned",
                    "capabilities": ["usb_serial", "connector"],
                    "confidence": 0.92,
                    "evidence_status": "verified",
                }
            ],
            "measurements": [
                {
                    "type": "resistance",
                    "target": "power to ground no-short",
                    "value": "pass",
                    "notes": "unpowered resistance between power and ground is no-short",
                },
                {
                    "type": "continuity",
                    "target": "connector ground to exposed ground",
                    "value": "pass",
                    "notes": "connector ground continuity ok",
                },
                {
                    "type": "voltage",
                    "target": "UART logic high voltage",
                    "value": 3.31,
                    "unit": "V",
                    "notes": "UART TX/RX idle high at 3.3V",
                },
                {
                    "type": "continuity",
                    "target": "shared ground continuity",
                    "value": "pass",
                    "notes": "shared ground continuity pass",
                },
                {
                    "type": "logic_level",
                    "target": "serial UART idle state",
                    "value": "pass",
                    "notes": "serial idle high and stable before connecting target board",
                },
            ],
            "repair_authority": {
                "status": "authoritative_low_risk",
                "score": 0.91,
                "required_measurements": [],
                "blocked_decisions": [],
            },
            "use_reference_catalog": False,
        }
    )

    integrated = plan["integrated_plan"]
    assurance = integrated["assurance"]

    assert integrated["status"] == "ready_for_build_plan"
    assert assurance["level"] == "authority_ready"
    assert assurance["can_build_now"] is True
    assert assurance["can_power_or_splice"] is True
    assert assurance["open_gate_count"] == 0
    assert integrated["measurement_evidence"]["closed_gate_count"] >= 5
    assert integrated["first_measurements"] == []
    assert integrated["execution_package"]["current_stage"] == "outcome_capture"
    assert integrated["completion_contract"]["state"] == "plan_complete_awaiting_outcome"
    assert integrated["completion_contract"]["plan_done"] is True
    assert integrated["completion_contract"]["workflow_done"] is False
    assert all(gate["status"] == "closed" for gate in integrated["evidence_gates"] if gate["type"] == "measurement")


def test_hardware_plan_with_terminal_outcome_is_workflow_complete():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "build a UART debug adapter from a known CH340 module",
            "strategy_mode": "hybrid",
            "required_capabilities": ["usb_serial", "connector"],
            "available_resources": [
                {
                    "resource_id": "known_ch340",
                    "name": "known CH340 adapter",
                    "resource_kind": "owned",
                    "capabilities": ["usb_serial", "connector"],
                    "confidence": 0.92,
                    "evidence_status": "verified",
                }
            ],
            "measurements": [
                {"type": "resistance", "target": "power to ground no-short", "value": "pass", "notes": "unpowered resistance between power and ground is no-short"},
                {"type": "continuity", "target": "connector ground to exposed ground", "value": "pass", "notes": "connector ground continuity ok"},
                {"type": "voltage", "target": "UART logic high voltage", "value": 3.31, "unit": "V", "notes": "UART TX/RX idle high at 3.3V"},
                {"type": "continuity", "target": "shared ground continuity", "value": "pass", "notes": "shared ground continuity pass"},
                {"type": "logic_level", "target": "serial UART idle state", "value": "pass", "notes": "serial idle high and stable before connecting target board"},
            ],
            "outcome_history": [
                {
                    "decision": "built",
                    "selected_resource_ids_used": ["known_ch340"],
                    "measurements_recorded": True,
                    "cash_spent_usd": 0,
                    "value_recovered_usd": 9,
                    "time_spent_minutes": 20,
                    "deviations_from_plan": [],
                    "failure_or_stop_reason": "",
                    "output_function_verified": True,
                    "evidence_uri": "session://outcomes/known-ch340-built",
                }
            ],
            "repair_authority": {
                "status": "authoritative_low_risk",
                "score": 0.91,
                "required_measurements": [],
                "blocked_decisions": [],
            },
            "use_reference_catalog": False,
        }
    )

    integrated = plan["integrated_plan"]

    assert integrated["execution_package"]["current_stage"] == "complete"
    assert integrated["execution_package"]["completion_state"] == "complete"
    assert integrated["execution_package"]["outcome_contract"]["recorded"] is True
    assert integrated["completion_contract"]["state"] == "workflow_complete"
    assert integrated["completion_contract"]["workflow_done"] is True
    assert integrated["next_actions"] == []


def test_hardware_plan_production_authority_authorizes_low_voltage_completed_workflow():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "release a measured low-voltage UART debug adapter repair",
            "target_authority_level": "production_repair",
            "strategy_mode": "hybrid",
            "required_capabilities": ["usb_serial", "connector"],
            "available_resources": [
                {
                    "resource_id": "known_ch340",
                    "name": "known CH340 adapter",
                    "resource_kind": "owned",
                    "capabilities": ["usb_serial", "connector"],
                    "confidence": 0.92,
                    "evidence_status": "verified",
                }
            ],
            "measurements": [
                _trusted_measurement("resistance", "power to ground no-short", "pass", "unpowered resistance between power and ground is no-short"),
                _trusted_measurement("continuity", "connector ground to exposed ground", "pass", "connector ground continuity ok"),
                _trusted_measurement("voltage", "UART logic high voltage", 3.31, "UART TX/RX idle high at 3.3V", unit="V"),
                _trusted_measurement("continuity", "shared ground continuity", "pass", "shared ground continuity pass"),
                _trusted_measurement("logic_level", "serial UART idle state", "pass", "serial idle high and stable before connecting target board"),
                _trusted_measurement("current", "current draw under current-limited supply", "pass", "current draw under current-limited supply within limit"),
                _trusted_measurement("thermal", "thermal behavior after first power", "normal", "temperature stable and no abnormal heat"),
            ],
            "outcome_history": [
                {
                    "decision": "built",
                    "selected_resource_ids_used": ["known_ch340"],
                    "measurements_recorded": True,
                    "cash_spent_usd": 0,
                    "value_recovered_usd": 9,
                    "time_spent_minutes": 20,
                    "deviations_from_plan": [],
                    "failure_or_stop_reason": "",
                    "output_function_verified": True,
                    "first_power_result": "pass",
                    "thermal_result": "normal",
                    "current_limit_used": True,
                    "evidence_uri": "session://outcomes/known-ch340-release",
                }
            ],
            "production_release": _release_manifest(["known_ch340"]),
            "repair_authority": {
                "status": "authoritative_low_risk",
                "score": 0.94,
                "required_measurements": [],
                "blocked_decisions": [],
            },
            "use_reference_catalog": False,
        }
    )

    production = plan["integrated_plan"]["production_repair_authority"]

    assert plan["integrated_plan"]["completion_contract"]["workflow_done"] is True
    assert production["authorized"] is True
    assert production["decision"] == "authorized_low_voltage_repair_release"
    assert production["hazard_profile"]["source_policy"]["raw_text_release_logic"] is False
    assert production["measurement_requirements"]["missing_categories"] == []
    assert production["measurement_provenance"]["missing_trusted_categories"] == []
    assert production["measurement_provenance"]["missing_artifact_categories"] == []
    assert production["release_manifest"]["complete"] is True
    assert production["authority_casefile"]["status"] == "release_ready"
    assert production["authority_casefile"]["blocked_claim_count"] == 0
    claims = {claim["claim_id"]: claim for claim in production["authority_casefile"]["claims"]}
    assert claims["measurement_provenance_auditable"]["status"] == "pass"
    assert claims["terminal_outcome_verified"]["status"] == "pass"
    assert claims["release_manifest_complete"]["status"] == "pass"
    assert plan["integrated_plan"]["next_actions"] == []


def test_hardware_plan_production_authority_blocks_missing_release_manifest():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "release a measured low-voltage UART debug adapter repair",
            "target_authority_level": "production_repair",
            "strategy_mode": "hybrid",
            "required_capabilities": ["usb_serial", "connector"],
            "available_resources": [
                {
                    "resource_id": "known_ch340",
                    "name": "known CH340 adapter",
                    "resource_kind": "owned",
                    "capabilities": ["usb_serial", "connector"],
                    "confidence": 0.92,
                    "evidence_status": "verified",
                }
            ],
            "measurements": [
                _trusted_measurement("resistance", "power to ground no-short", "pass", "unpowered resistance between power and ground is no-short"),
                _trusted_measurement("continuity", "connector ground to exposed ground", "pass", "connector ground continuity ok"),
                _trusted_measurement("voltage", "UART logic high voltage", 3.31, "UART TX/RX idle high at 3.3V", unit="V"),
                _trusted_measurement("continuity", "shared ground continuity", "pass", "shared ground continuity pass"),
                _trusted_measurement("logic_level", "serial UART idle state", "pass", "serial idle high and stable before connecting target board"),
                _trusted_measurement("current", "current draw under current-limited supply", "pass", "current draw under current-limited supply within limit"),
                _trusted_measurement("thermal", "thermal behavior after first power", "normal", "temperature stable and no abnormal heat"),
            ],
            "outcome_history": [
                {
                    "decision": "built",
                    "selected_resource_ids_used": ["known_ch340"],
                    "measurements_recorded": True,
                    "cash_spent_usd": 0,
                    "value_recovered_usd": 9,
                    "time_spent_minutes": 20,
                    "deviations_from_plan": [],
                    "failure_or_stop_reason": "",
                    "output_function_verified": True,
                    "first_power_result": "pass",
                    "thermal_result": "normal",
                    "current_limit_used": True,
                    "evidence_uri": "session://outcomes/known-ch340-release",
                }
            ],
            "repair_authority": {"status": "authoritative_low_risk", "score": 0.94},
            "use_reference_catalog": False,
        }
    )

    production = plan["integrated_plan"]["production_repair_authority"]

    assert production["authorized"] is False
    assert "Production release manifest is incomplete." in production["blockers"]
    assert "Attach production_release or release_manifest." in production["release_manifest"]["missing_requirements"]
    claims = {claim["claim_id"]: claim for claim in production["authority_casefile"]["claims"]}
    assert production["authority_casefile"]["status"] == "evidence_required"
    assert claims["release_manifest_complete"]["status"] == "blocked"


def test_hardware_plan_production_authority_blocks_unprovenanced_measurements():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "release a measured low-voltage UART debug adapter repair",
            "target_authority_level": "production_repair",
            "strategy_mode": "hybrid",
            "required_capabilities": ["usb_serial", "connector"],
            "available_resources": [
                {
                    "resource_id": "known_ch340",
                    "name": "known CH340 adapter",
                    "resource_kind": "owned",
                    "capabilities": ["usb_serial", "connector"],
                    "confidence": 0.92,
                    "evidence_status": "verified",
                }
            ],
            "measurements": [
                {"type": "resistance", "target": "power to ground no-short", "value": "pass", "notes": "unpowered resistance between power and ground is no-short"},
                {"type": "continuity", "target": "connector ground to exposed ground", "value": "pass", "notes": "connector ground continuity ok"},
                {"type": "voltage", "target": "UART logic high voltage", "value": 3.31, "unit": "V", "notes": "UART TX/RX idle high at 3.3V"},
                {"type": "continuity", "target": "shared ground continuity", "value": "pass", "notes": "shared ground continuity pass"},
                {"type": "logic_level", "target": "serial UART idle state", "value": "pass", "notes": "serial idle high and stable before connecting target board"},
                {"type": "current", "target": "current draw under current-limited supply", "value": "pass", "notes": "current draw under current-limited supply within limit"},
                {"type": "thermal", "target": "thermal behavior after first power", "value": "normal", "notes": "temperature stable and no abnormal heat"},
            ],
            "outcome_history": [
                {
                    "decision": "built",
                    "selected_resource_ids_used": ["known_ch340"],
                    "measurements_recorded": True,
                    "cash_spent_usd": 0,
                    "value_recovered_usd": 9,
                    "time_spent_minutes": 20,
                    "deviations_from_plan": [],
                    "failure_or_stop_reason": "",
                    "output_function_verified": True,
                    "first_power_result": "pass",
                    "thermal_result": "normal",
                    "evidence_uri": "session://outcomes/known-ch340-unprovenanced",
                }
            ],
            "repair_authority": {"status": "authoritative_low_risk", "score": 0.94},
            "use_reference_catalog": False,
        }
    )

    production = plan["integrated_plan"]["production_repair_authority"]

    assert plan["integrated_plan"]["completion_contract"]["workflow_done"] is True
    assert production["authorized"] is False
    assert "Required production measurements lack trusted provenance." in production["blockers"]
    assert production["measurement_provenance"]["missing_trusted_categories"]


def test_hardware_plan_production_authority_uses_structured_hazard_profile_not_text_release():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "release a measured low-voltage looking adapter with structured hazard flag",
            "target_authority_level": "production_repair",
            "strategy_mode": "hybrid",
            "required_capabilities": ["usb_serial", "connector"],
            "available_resources": [
                {
                    "resource_id": "known_ch340",
                    "name": "known CH340 adapter",
                    "resource_kind": "owned",
                    "capabilities": ["usb_serial", "connector"],
                    "confidence": 0.92,
                    "evidence_status": "verified",
                }
            ],
            "hazard_profile": {
                "energy_domain": "mains_input_present",
                "hazards": [
                    {
                        "hazard_id": "mains_input",
                        "severity": "critical",
                        "unsupported_for_production_authority": True,
                        "clearance_requires": ["isolate mains section in specialist workflow"],
                    }
                ],
            },
            "measurements": [
                _trusted_measurement("resistance", "power to ground no-short", "pass", "unpowered resistance between power and ground is no-short"),
                _trusted_measurement("continuity", "connector ground to exposed ground", "pass", "connector ground continuity ok"),
                _trusted_measurement("voltage", "UART logic high voltage", 3.31, "UART TX/RX idle high at 3.3V", unit="V"),
                _trusted_measurement("continuity", "shared ground continuity", "pass", "shared ground continuity pass"),
                _trusted_measurement("logic_level", "serial UART idle state", "pass", "serial idle high and stable before connecting target board"),
                _trusted_measurement("current", "current draw under current-limited supply", "pass", "current draw under current-limited supply within limit"),
                _trusted_measurement("thermal", "thermal behavior after first power", "normal", "temperature stable and no abnormal heat"),
            ],
            "outcome_history": [
                {
                    "decision": "built",
                    "selected_resource_ids_used": ["known_ch340"],
                    "measurements_recorded": True,
                    "cash_spent_usd": 0,
                    "value_recovered_usd": 9,
                    "time_spent_minutes": 20,
                    "deviations_from_plan": [],
                    "failure_or_stop_reason": "",
                    "output_function_verified": True,
                    "first_power_result": "pass",
                    "thermal_result": "normal",
                    "evidence_uri": "session://outcomes/known-ch340-hazard",
                }
            ],
            "repair_authority": {"status": "authoritative_low_risk", "score": 0.94},
            "use_reference_catalog": False,
        }
    )

    production = plan["integrated_plan"]["production_repair_authority"]

    assert production["authorized"] is False
    assert production["decision"] == "blocked_by_hazard_scope"
    assert production["hazard_profile"]["unsupported_for_production_authority"] is True
    assert "The hazard profile is outside production repair authority scope." in production["blockers"]
    assert any("specialist workflow" in requirement for requirement in production["requirements"])


def test_hardware_plan_broad_production_matrix_routes_motor_lane():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "production release a low-voltage motor driver repair",
            "target_authority_level": "production_repair",
            "strategy_mode": "hybrid",
            "required_capabilities": ["controller", "actuator_driver", "motor_or_load", "power", "connector"],
            "available_resources": [
                {
                    "resource_id": "owned_controller",
                    "name": "known controller board",
                    "resource_kind": "owned",
                    "capabilities": ["controller", "connector"],
                    "confidence": 0.88,
                    "evidence_status": "verified",
                },
                {
                    "resource_id": "motor_driver",
                    "name": "known motor driver",
                    "resource_kind": "owned",
                    "capabilities": ["actuator_driver", "connector"],
                    "confidence": 0.88,
                    "evidence_status": "verified",
                },
                {
                    "resource_id": "small_motor",
                    "name": "small DC motor",
                    "resource_kind": "owned",
                    "capabilities": ["motor_or_load"],
                    "confidence": 0.76,
                    "evidence_status": "verified",
                },
                {
                    "resource_id": "bench_supply",
                    "name": "current-limited bench supply",
                    "resource_kind": "owned",
                    "capabilities": ["power"],
                    "confidence": 0.86,
                    "evidence_status": "verified",
                },
            ],
            "measurements": [
                _trusted_measurement("resistance", "power to ground no-short", "pass", "unpowered resistance between power and ground is no-short"),
                _trusted_measurement("resistance", "MOSFET/transistor short check", "pass", "MOSFET/transistor short check passed"),
                _trusted_measurement("continuity", "connector ground to exposed ground", "pass", "connector ground continuity ok"),
                _trusted_measurement("voltage", "motor supply voltage", 5.0, "motor supply voltage verified", unit="V"),
                _trusted_measurement("voltage", "logic high voltage", 3.3, "logic high voltage verified", unit="V"),
                _trusted_measurement("current", "motor run current under current limit", "pass", "run current within limit"),
                _trusted_measurement("thermal", "motor driver thermal behavior", "normal", "temperature stable and no abnormal heat"),
            ],
            "outcome_history": [
                {
                    "decision": "built",
                    "selected_resource_ids_used": ["owned_controller", "motor_driver", "small_motor", "bench_supply"],
                    "measurements_recorded": True,
                    "cash_spent_usd": 0,
                    "value_recovered_usd": 12,
                    "time_spent_minutes": 35,
                    "deviations_from_plan": [],
                    "failure_or_stop_reason": "",
                    "output_function_verified": True,
                    "first_power_result": "pass",
                    "thermal_result": "normal",
                    "evidence_uri": "session://outcomes/motor-missing-special-evidence",
                }
            ],
            "production_release": _release_manifest(
                ["owned_controller", "motor_driver", "small_motor", "bench_supply"],
                release_id="REL-MOTOR-001",
            ),
            "repair_authority": {"status": "authoritative_low_risk", "score": 0.92},
            "use_reference_catalog": False,
        }
    )

    production = plan["integrated_plan"]["production_repair_authority"]
    motor_lane = [
        lane for lane in production["domain_authority"]["lanes"]
        if lane["lane_id"] == "motor_mechanical_load"
    ][0]

    assert production["authorized"] is False
    assert production["domain_authority"]["primary_lane"] == "motor_mechanical_load"
    assert motor_lane["relevant"] is True
    assert motor_lane["authorized"] is False
    assert "Record stall_current_result=pass or equivalent." in motor_lane["requirements"]


def test_hardware_plan_motor_lane_authorizes_with_motor_specific_outcome():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "production release a low-voltage motor driver repair",
            "target_authority_level": "production_repair",
            "strategy_mode": "hybrid",
            "required_capabilities": ["controller", "actuator_driver", "motor_or_load", "power", "connector"],
            "available_resources": [
                {
                    "resource_id": "owned_controller",
                    "name": "known controller board",
                    "resource_kind": "owned",
                    "capabilities": ["controller", "connector"],
                    "confidence": 0.88,
                    "evidence_status": "verified",
                },
                {
                    "resource_id": "motor_driver",
                    "name": "known motor driver",
                    "resource_kind": "owned",
                    "capabilities": ["actuator_driver", "connector"],
                    "confidence": 0.88,
                    "evidence_status": "verified",
                },
                {
                    "resource_id": "small_motor",
                    "name": "small DC motor",
                    "resource_kind": "owned",
                    "capabilities": ["motor_or_load"],
                    "confidence": 0.76,
                    "evidence_status": "verified",
                },
                {
                    "resource_id": "bench_supply",
                    "name": "current-limited bench supply",
                    "resource_kind": "owned",
                    "capabilities": ["power"],
                    "confidence": 0.86,
                    "evidence_status": "verified",
                },
            ],
            "measurements": [
                _trusted_measurement("resistance", "power to ground no-short", "pass", "unpowered resistance between power and ground is no-short"),
                _trusted_measurement("resistance", "MOSFET/transistor short check", "pass", "MOSFET/transistor short check passed"),
                _trusted_measurement("continuity", "connector ground to exposed ground", "pass", "connector ground continuity ok"),
                _trusted_measurement("voltage", "motor supply voltage", 5.0, "motor supply voltage verified", unit="V"),
                _trusted_measurement("voltage", "logic high voltage", 3.3, "logic high voltage verified", unit="V"),
                _trusted_measurement("current", "motor run current under current limit", "pass", "run current within limit"),
                _trusted_measurement("thermal", "motor driver thermal behavior", "normal", "temperature stable and no abnormal heat"),
            ],
            "outcome_history": [
                {
                    "decision": "built",
                    "selected_resource_ids_used": ["owned_controller", "motor_driver", "small_motor", "bench_supply"],
                    "measurements_recorded": True,
                    "cash_spent_usd": 0,
                    "value_recovered_usd": 12,
                    "time_spent_minutes": 35,
                    "deviations_from_plan": [],
                    "failure_or_stop_reason": "",
                    "output_function_verified": True,
                    "first_power_result": "pass",
                    "thermal_result": "normal",
                    "stall_current_result": "pass",
                    "mechanical_guarding_verified": True,
                    "abnormal_current_stop_verified": True,
                    "evidence_uri": "session://outcomes/motor-authorized",
                }
            ],
            "production_release": _release_manifest(
                ["owned_controller", "motor_driver", "small_motor", "bench_supply"],
                release_id="REL-MOTOR-002",
            ),
            "repair_authority": {"status": "authoritative_low_risk", "score": 0.92},
            "use_reference_catalog": False,
        }
    )

    production = plan["integrated_plan"]["production_repair_authority"]
    motor_lane = [
        lane for lane in production["domain_authority"]["lanes"]
        if lane["lane_id"] == "motor_mechanical_load"
    ][0]

    assert production["authorized"] is True
    assert production["decision"] == "authorized_motor_mechanical_load_release"
    assert production["domain_authority"]["primary_lane"] == "motor_mechanical_load"
    assert motor_lane["authorized"] is True
    assert production["release_manifest"]["complete"] is True
    assert production["blockers"] == []


def test_hardware_plan_battery_lane_authorizes_only_with_specialist_packet():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "production release a protected battery module repair",
            "target_authority_level": "production_repair",
            "strategy_mode": "hybrid",
            "required_capabilities": ["battery_pack", "connector"],
            "available_resources": [
                {
                    "resource_id": "protected_lfp_pack",
                    "name": "protected LiFePO4 battery module",
                    "resource_kind": "owned",
                    "capabilities": ["battery_pack", "connector"],
                    "confidence": 0.9,
                    "evidence_status": "verified",
                }
            ],
            "measurements": [
                _trusted_measurement("resistance", "pack output no-short", "pass", "pack output no-short verified"),
                _trusted_measurement("continuity", "pack connector polarity", "pass", "connector polarity and ground continuity verified"),
                _trusted_measurement("voltage", "pack output voltage", 12.8, "pack output voltage within expected LiFePO4 range", unit="V"),
                _trusted_measurement("current", "protected load current", "pass", "load current within protected limit"),
                _trusted_measurement("thermal", "pack thermal behavior", "normal", "temperature stable under validation load"),
            ],
            "outcome_history": [
                {
                    "decision": "reused",
                    "selected_resource_ids_used": ["protected_lfp_pack"],
                    "measurements_recorded": True,
                    "cash_spent_usd": 0,
                    "value_recovered_usd": 18,
                    "time_spent_minutes": 45,
                    "deviations_from_plan": [],
                    "failure_or_stop_reason": "",
                    "output_function_verified": True,
                    "first_power_result": "pass",
                    "thermal_result": "normal",
                    "current_limit_used": True,
                    "evidence_uri": "session://outcomes/battery-authorized",
                }
            ],
            "production_release": _release_manifest(["protected_lfp_pack"], release_id="REL-BAT-001"),
            "repair_authority": {"status": "authoritative_low_risk", "score": 0.93},
            "specialist_authority": {
                "battery_pack_lithium": {
                    "status": "certified_release",
                    "signed_by": "battery-specialist-1",
                    "certificate_id": "BAT-REL-001",
                    "issued_at": "2026-05-26T02:30:00Z",
                    "evidence": {
                        "chemistry_verified": True,
                        "cell_count_verified": True,
                        "bms_protection_verified": True,
                        "cell_balance_result": "pass",
                        "charge_discharge_result": "pass",
                        "thermal_containment_verified": True,
                        "enclosure_verified": True,
                    },
                }
            },
            "use_reference_catalog": False,
        }
    )

    production = plan["integrated_plan"]["production_repair_authority"]
    battery_lane = [
        lane for lane in production["domain_authority"]["lanes"]
        if lane["lane_id"] == "battery_pack_lithium"
    ][0]

    assert production["authorized"] is True
    assert production["decision"] == "authorized_battery_pack_lithium_specialist_release"
    assert production["hazard_profile"]["unsupported_for_production_authority"] is True
    assert production["domain_authority"]["primary_lane"] == "battery_pack_lithium"
    assert battery_lane["authorized"] is True
    assert battery_lane["evidence"]["specialist_authority"]["authorized"] is True
    assert production["release_manifest"]["complete"] is True
    assert production["blockers"] == []


def test_hardware_plan_battery_lane_blocks_missing_specialist_packet():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "production release a protected battery module repair",
            "target_authority_level": "production_repair",
            "strategy_mode": "hybrid",
            "required_capabilities": ["battery_pack", "connector"],
            "available_resources": [
                {
                    "resource_id": "protected_lfp_pack",
                    "name": "protected LiFePO4 battery module",
                    "resource_kind": "owned",
                    "capabilities": ["battery_pack", "connector"],
                    "confidence": 0.9,
                    "evidence_status": "verified",
                }
            ],
            "measurements": [
                _trusted_measurement("resistance", "pack output no-short", "pass", "pack output no-short verified"),
                _trusted_measurement("continuity", "pack connector polarity", "pass", "connector polarity and ground continuity verified"),
                _trusted_measurement("voltage", "pack output voltage", 12.8, "pack output voltage within expected LiFePO4 range", unit="V"),
                _trusted_measurement("current", "protected load current", "pass", "load current within protected limit"),
                _trusted_measurement("thermal", "pack thermal behavior", "normal", "temperature stable under validation load"),
            ],
            "outcome_history": [
                {
                    "decision": "reused",
                    "selected_resource_ids_used": ["protected_lfp_pack"],
                    "measurements_recorded": True,
                    "cash_spent_usd": 0,
                    "value_recovered_usd": 18,
                    "time_spent_minutes": 45,
                    "deviations_from_plan": [],
                    "failure_or_stop_reason": "",
                    "output_function_verified": True,
                    "first_power_result": "pass",
                    "thermal_result": "normal",
                    "current_limit_used": True,
                    "evidence_uri": "session://outcomes/battery-missing-specialist",
                }
            ],
            "repair_authority": {"status": "authoritative_low_risk", "score": 0.93},
            "use_reference_catalog": False,
        }
    )

    production = plan["integrated_plan"]["production_repair_authority"]
    battery_lane = [
        lane for lane in production["domain_authority"]["lanes"]
        if lane["lane_id"] == "battery_pack_lithium"
    ][0]

    assert production["authorized"] is False
    assert production["decision"] == "blocked_by_hazard_scope"
    assert production["domain_authority"]["primary_lane"] == "battery_pack_lithium"
    assert battery_lane["relevant"] is True
    assert battery_lane["authorized"] is False
    assert battery_lane["decision"] == "specialist_authority_required"
    assert "The hazard profile is outside production repair authority scope." in production["blockers"]


def test_hardware_plan_failed_measurement_blocks_power_and_build():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "build a UART debug adapter from a known CH340 module",
            "strategy_mode": "hybrid",
            "required_capabilities": ["usb_serial", "connector"],
            "available_resources": [
                {
                    "resource_id": "known_ch340",
                    "name": "known CH340 adapter",
                    "resource_kind": "owned",
                    "capabilities": ["usb_serial", "connector"],
                    "confidence": 0.92,
                    "evidence_status": "verified",
                }
            ],
            "measurements": [
                {
                    "type": "resistance",
                    "target": "power to ground no-short",
                    "value": "fail",
                    "notes": "short detected between power and ground",
                }
            ],
            "repair_authority": {"status": "authoritative_low_risk", "score": 0.91},
            "use_reference_catalog": False,
        }
    )

    integrated = plan["integrated_plan"]

    assert integrated["status"] == "safety_hold"
    assert integrated["assurance"]["level"] == "blocked"
    assert integrated["assurance"]["failed_gate_count"] >= 1
    assert integrated["assurance"]["can_build_now"] is False
    assert integrated["assurance"]["can_power_or_splice"] is False
    assert integrated["measurement_evidence"]["failed_gate_count"] >= 1
    assert integrated["execution_package"]["current_stage"] == "safety_authority"
    assert any(gate["status"] == "failed" for gate in integrated["evidence_gates"])


def test_hardware_plan_api_uses_existing_session_measurements_to_close_gates(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    session = store.create_session(
        {
            "title": "UART adapter evidence",
            "description": "Session-backed UART adapter measurements",
            "route": "hardware_plan",
        },
        user_id="operator-1",
        commit=True,
    )
    for measurement in [
        {
            "type": "resistance",
            "target": "power to ground no-short",
            "value": "pass",
            "notes": "unpowered resistance between power and ground is no-short",
        },
        {
            "type": "continuity",
            "target": "connector ground to exposed ground",
            "value": "pass",
            "notes": "connector ground continuity ok",
        },
        {
            "type": "voltage",
            "target": "UART logic high voltage",
            "value": 3.31,
            "unit": "V",
            "notes": "UART TX/RX idle high at 3.3V",
        },
        {
            "type": "continuity",
            "target": "shared ground continuity",
            "value": "pass",
            "notes": "shared ground continuity pass",
        },
        {
            "type": "logic_level",
            "target": "serial UART idle state",
            "value": "pass",
            "notes": "serial idle high and stable before connecting target board",
        },
    ]:
        store.add_measurement(session["session_id"], measurement)

    response = main_module.hardware_plan(
        {
            "session_id": session["session_id"],
            "goal": "build a UART debug adapter from a known CH340 module",
            "strategy_mode": "hybrid",
            "required_capabilities": ["usb_serial", "connector"],
            "available_resources": [
                {
                    "resource_id": "known_ch340",
                    "name": "known CH340 adapter",
                    "resource_kind": "owned",
                    "capabilities": ["usb_serial", "connector"],
                    "confidence": 0.92,
                    "evidence_status": "verified",
                }
            ],
            "repair_authority": {
                "status": "authoritative_low_risk",
                "score": 0.91,
                "required_measurements": [],
                "blocked_decisions": [],
            },
            "use_reference_catalog": False,
        },
        commit_session=True,
        current_user={"user_id": "operator-1"},
        planner=SalvageSplicePlanner(),
        store=store,
    )

    integrated = response["hardware_plan"]["integrated_plan"]
    saved_session = store.get_session(session["session_id"])

    assert response["metadata"]["source_session_id"] == session["session_id"]
    assert response["metadata"]["committed"] is True
    assert response["saved"]["new_task_count"] == 0
    assert integrated["status"] == "ready_for_build_plan"
    assert integrated["assurance"]["can_power_or_splice"] is True
    assert integrated["measurement_evidence"]["closed_gate_count"] >= 5
    assert saved_session["analyses"][-1]["results"]["hardware_plan_summary"]["measurement_evidence"]["closed_gate_count"] >= 5


def test_hardware_plan_safety_hold_for_unsafe_selected_only_case():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "reuse a swollen lithium pack as power",
            "strategy_mode": "constrained",
            "required_capabilities": ["power"],
            "available_resources": [
                {
                    "resource_id": "swollen_pack",
                    "name": "swollen lithium pack",
                    "resource_kind": "salvaged",
                    "capabilities": ["power"],
                    "confidence": 0.8,
                }
            ],
            "use_reference_catalog": False,
        }
    )

    integrated = plan["integrated_plan"]

    assert integrated["status"] == "safety_hold"
    assert integrated["assurance"]["level"] == "blocked"
    assert integrated["assurance"]["can_build_now"] is False
    assert integrated["assurance"]["blockers"]
    assert integrated["execution_package"]["current_stage"] == "safety_authority"
    assert integrated["execution_package"]["completion_state"] == "blocked"


def test_hardware_plan_prior_unsafe_outcome_blocks_matching_resource():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "reuse the same power module in a bench adapter",
            "strategy_mode": "hybrid",
            "required_capabilities": ["power"],
            "available_resources": [
                {
                    "resource_id": "mystery_power_module",
                    "name": "mystery power module",
                    "resource_kind": "owned",
                    "capabilities": ["power"],
                    "confidence": 0.82,
                    "evidence_status": "verified",
                }
            ],
            "outcome_history": [
                {
                    "decision": "unsafe_hold",
                    "selected_resource_ids": ["mystery_power_module"],
                    "failure_or_stop_reason": "overheated during first power",
                }
            ],
            "use_reference_catalog": False,
        }
    )

    integrated = plan["integrated_plan"]

    assert integrated["status"] == "safety_hold"
    assert integrated["outcome_memory"]["negative_count"] == 1
    assert integrated["assurance"]["level"] == "blocked"
    assert any("Prior unsafe outcome" in gate["prompt"] for gate in integrated["evidence_gates"])


def test_hardware_plan_api_advances_existing_circuit_session_and_appends_plan(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    created = main_module.circuit_boards_analyze_design(
        {
            "description": "Controller board hardware plan source",
            "board": {
                "board_id": "main_ctrl",
                "path": str(DEMO_NETLIST),
                "kind": "netlist",
            },
        },
        commit_session=True,
        current_user={"user_id": "operator-1"},
        store=store,
    )
    session_id = created["session"]["session_id"]

    response = main_module.hardware_plan(
        {
            "session_id": session_id,
            "goal": "reuse the controller, sensor connector, and power section for a low-voltage sensor logger",
            "strategy_mode": "hybrid",
            "required_capabilities": ["controller", "sensor_or_adc", "power"],
            "constraints": {"budget_usd": 5},
            "use_reference_catalog": False,
        },
        commit_session=True,
        current_user={"user_id": "operator-1"},
        planner=SalvageSplicePlanner(),
        store=store,
    )

    hardware_plan = response["hardware_plan"]
    session = store.get_session(session_id)

    assert response["metadata"]["committed"] is True
    assert response["metadata"]["source_session_id"] == session_id
    assert response["saved"]["analysis"]["source"] == "hardware_plan"
    assert hardware_plan["context"]["analysis_source"] == "session_circuit_advance"
    assert hardware_plan["initial_salvage_plan"]["functional_reuse_plan"]["circuit_backed"] is True
    assert hardware_plan["resource_strategy"]["selected_resources"]
    assert session["analyses"][-1]["results"]["mode"] == "hardware_plan"


def test_hardware_plan_api_can_create_new_planning_session(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    response = main_module.hardware_plan(
        {
            "title": "Constrained fan build",
            "goal": "build a USB fume extractor from a verified fan, switch, and cable",
            "strategy_mode": "constrained",
            "required_capabilities": ["power", "motor_or_load", "fan_or_pump", "switch_or_button", "connector"],
            "available_resources": [
                {
                    "name": "verified USB fan assembly",
                    "resource_kind": "salvaged",
                    "capabilities": ["power", "motor_or_load", "fan_or_pump"],
                    "confidence": 0.82,
                    "evidence_status": "verified",
                },
                {
                    "name": "toggle switch",
                    "resource_kind": "owned",
                    "capabilities": ["switch_or_button"],
                    "confidence": 0.8,
                    "evidence_status": "verified",
                },
                {
                    "name": "USB cable harness",
                    "resource_kind": "owned",
                    "capabilities": ["connector"],
                    "confidence": 0.8,
                    "evidence_status": "verified",
                },
            ],
            "use_reference_catalog": False,
        },
        commit_session=True,
        current_user={"user_id": "operator-1"},
        planner=SalvageSplicePlanner(),
        store=store,
    )

    assert response["metadata"]["committed"] is True
    assert response["session"]["route"] == "hardware_plan"
    assert response["hardware_plan"]["integrated_plan"]["recommended_path"] == "reuse_first"
    assert len(store.sessions) == 1
