from src.intelligence.board_session_store import BoardSessionStore
from src.intelligence.hardware_plan import HardwarePlanOrchestrator


def _trusted():
    return {
        "instrument_id": "bench_dmm_01",
        "instrument_type": "calibrated_dmm",
        "calibration_status": "valid",
        "recorded_at": "2026-05-26T03:00:00Z",
        "operator_id": "operator-1",
        "evidence_uri": "session://measurements/topology",
    }


def _release_manifest(resource_ids):
    return {
        "release_id": "REL-ARB-001",
        "selected_resource_ids": resource_ids,
        "released_by": "operator-1",
        "approved_by": "operator-1",
        "released_at": "2026-05-26T04:00:00Z",
        "scope_statement": "Release is limited to the measured arbitrary-board pins, rails, and terminal outcome in this session.",
        "artifact_uri": "session://release/arbitrary-board",
        "acceptance_reviewed": True,
        "repeatability_sample_count": 1,
    }


def _visual_usb_uart_board():
    return {
        "schema_version": "board_evidence.v1",
        "components": [
            {"id": "u1", "label": "CH340C USB serial bridge IC", "kind": "integrated_circuit", "confidence": 0.78},
            {"id": "j1", "label": "USB connector", "kind": "connector", "confidence": 0.74},
        ],
        "connectors": [
            {"id": "h1", "label": "UART header", "kind": "header", "confidence": 0.7},
        ],
        "damage": [],
    }


def _visual_sensor_board():
    return {
        "schema_version": "board_evidence.v1",
        "components": [
            {"id": "u1", "label": "BME280 sensor IC", "kind": "sensor", "confidence": 0.78},
            {"id": "j1", "label": "I2C header", "kind": "header", "confidence": 0.72},
        ],
        "connectors": [{"id": "j1", "label": "I2C header", "kind": "header", "confidence": 0.72}],
        "damage": [],
    }


def _visual_regulator_marking_board():
    return {
        "schema_version": "board_evidence.v1",
        "components": [
            {"id": "u1", "label": "unknown SOT-223 regulator package", "kind": "integrated_circuit", "confidence": 0.66},
            {"id": "c1", "label": "output capacitor", "kind": "capacitor", "confidence": 0.62},
        ],
        "markings": [
            {"id": "m1", "label": "AMS1117-3.3 marking on U1", "marking": "AMS1117-3.3", "confidence": 0.76},
        ],
        "connectors": [{"id": "j1", "label": "VIN GND VOUT header", "kind": "header", "confidence": 0.64}],
        "damage": [],
    }


def _visual_single_board_computer():
    return {
        "schema_version": "board_evidence.v1",
        "components": [
            {"id": "cpu", "label": "CPU / SoC", "kind": "processor", "confidence": 0.74},
            {"id": "ram", "label": "RAM package", "kind": "memory", "confidence": 0.7},
        ],
        "markings": [{"id": "m1", "label": "Raspberry Pi 4 Model B", "marking": "Raspberry Pi 4 Model B", "confidence": 0.78}],
        "connectors": [
            {"id": "usb_c", "label": "USB-C power input", "kind": "connector", "confidence": 0.74},
            {"id": "eth", "label": "Ethernet connector", "kind": "connector", "confidence": 0.72},
            {"id": "hdmi", "label": "HDMI connector", "kind": "connector", "confidence": 0.72},
            {"id": "gpio", "label": "40-pin GPIO header", "kind": "header", "confidence": 0.72},
        ],
        "damage": [],
    }


def _marked_board(marking, label, connector_label):
    return {
        "schema_version": "board_evidence.v1",
        "components": [{"id": "u1", "label": label, "kind": "integrated_circuit", "confidence": 0.68}],
        "markings": [{"id": "m1", "label": f"{marking} marking on U1", "marking": marking, "confidence": 0.76}],
        "connectors": [{"id": "j1", "label": connector_label, "kind": "header", "confidence": 0.64}],
        "damage": [],
    }


def _uart_topology(*, short=False):
    return {
        "schema_version": "topology_evidence.v1",
        **_trusted(),
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
        "current": [
            {
                "target": "current draw under current-limited supply",
                "value": "pass",
                "notes": "current draw under current-limited supply within limit",
                "status": "pass",
            }
        ],
        "thermal": [
            {
                "target": "thermal behavior after first power",
                "value": "normal",
                "notes": "temperature stable and no abnormal heat",
                "status": "pass",
            }
        ],
    }


def _motor_topology():
    return {
        "schema_version": "topology_evidence.v1",
        **_trusted(),
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
            {
                "target": "power to ground no-short",
                "value": "pass",
                "unit": "ohm",
                "notes": "unpowered resistance between VMOTOR and GND is no-short",
                "status": "pass",
            },
            {
                "target": "MOSFET/transistor short check",
                "value": "pass",
                "unit": "ohm",
                "notes": "driver output MOSFETs are not shorted drain-source",
                "status": "pass",
            },
        ],
        "current": [
            {
                "target": "current draw under current-limited dummy load",
                "value": "pass",
                "notes": "driver current draw stays within limit under dummy load",
                "status": "pass",
            }
        ],
        "thermal": [
            {
                "target": "thermal behavior after dummy-load test",
                "value": "normal",
                "notes": "temperature stable and no abnormal heat",
                "status": "pass",
            }
        ],
    }


def test_visual_board_workflow_infers_function_and_measurement_protocol_without_authority():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "reuse a photographed USB UART board",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "board_evidence": _visual_usb_uart_board(),
            "use_reference_catalog": False,
        }
    )

    analysis = plan["analysis"]
    integrated = plan["integrated_plan"]
    workflow = analysis["arbitrary_board_workflow"]
    contradictions = workflow["evidence_contradictions"]
    protocol = workflow["measurement_protocol"]
    bench = workflow["bench_protocol_pack"]

    assert workflow["board_function_inference"]["primary_function_id"] == "usb_serial_debug_bridge"
    assert contradictions["status"] == "soft_gaps"
    assert any(item["id"] == "vision_without_topology" for item in contradictions["items"])
    assert protocol["status"] == "open"
    assert any(step["lane_id"] == "measured_pinout" for step in protocol["steps"])
    assert bench["primary_function_id"] == "usb_serial_debug_bridge"
    assert "logic" in bench["required_measurement_categories"]
    assert any(step["lane_id"] == "loopback" for step in bench["steps"])
    assert analysis["fault_isolation"]["state"] == "needs_measurements"
    assert analysis["salvage_value_decision"]["decision"] == "identify_and_measure_before_value_decision"
    assert integrated["repair_brain"]["board_function"]["primary_function_id"] == "usb_serial_debug_bridge"
    assert integrated["execution_package"]["repair_brain"]["measurement_protocol"]["status"] == "open"
    assert integrated["repair_brain"]["reuse_splice_strategy"]["readiness"] == "visual_mapping_only"
    assert integrated["repair_brain"]["arbitrary_board_trust_assessment"]["level"] == "grounded_visual_candidate"
    assert integrated["repair_brain"]["bench_protocol_pack"]["title"] == "USB/UART debug bridge reuse"
    assert integrated["repair_brain"]["arbitrary_board_trust_assessment"]["production_readiness_score"] < 0.35
    assert integrated["repair_brain"]["component_salvage_map"]["preferred_reuse_class"] == "whole_board_debug_adapter_reuse"
    assert any(recipe["recipe_id"] == "debug_bridge_reuse" for recipe in integrated["execution_package"]["reuse_splice_strategy"]["recipes"])
    assert integrated["execution_package"]["arbitrary_board_trust_assessment"]["level"] == "grounded_visual_candidate"
    assert integrated["assurance"]["can_power_or_splice"] is False


def test_measured_uart_workflow_adds_repair_brain_without_blocking_controlled_splice():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "reuse measured UART header as debug bridge",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "topology_evidence": _uart_topology(),
            "use_reference_catalog": False,
        }
    )

    analysis = plan["analysis"]
    integrated = plan["integrated_plan"]
    protocol = analysis["measurement_protocol"]
    fault = analysis["fault_isolation"]
    value = analysis["salvage_value_decision"]

    assert analysis["board_function_inference"]["primary_function_id"] == "usb_serial_debug_bridge"
    assert analysis["evidence_contradictions"]["status"] == "clear"
    assert protocol["status"] == "open"
    assert any(step["lane_id"] == "terminal_outcome" for step in protocol["steps"])
    assert fault["state"] == "diagnostic_ready"
    assert fault["top_fault_id"] == "usb_serial_or_connector_fault"
    assert value["decision"] == "controlled_reuse_or_repair_trial"
    assert analysis["arbitrary_board_trust_assessment"]["level"] == "controlled_reuse_ready"
    assert analysis["arbitrary_board_trust_assessment"]["production_readiness_score"] > 0.45
    assert "Attach production_release or release_manifest." in analysis["arbitrary_board_trust_assessment"]["blocking_gaps"]
    assert integrated["repair_brain"]["fault_isolation"]["top_fault_id"] == "usb_serial_or_connector_fault"
    assert integrated["repair_brain"]["salvage_value_decision"]["decision"] == "controlled_reuse_or_repair_trial"
    assert integrated["repair_brain"]["reuse_splice_strategy"]["readiness"] == "controlled_splice_ready"
    assert integrated["execution_package"]["reuse_splice_strategy"]["best_next_checkpoint"]
    assert integrated["execution_package"]["measurement_protocol"]["next_steps"]
    assert integrated["assurance"]["can_power_or_splice"] is True


def test_workflow_routes_short_and_bad_authority_to_safety_hold_salvage_only():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "reuse measured UART header despite bad authority packet",
            "target_authority_level": "production_repair",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "topology_evidence": _uart_topology(short=True),
            "repair_authority": {"status": "authoritative_low_risk", "score": 0.96},
            "use_reference_catalog": False,
        }
    )

    analysis = plan["analysis"]

    assert analysis["authority_integrity"]["overrode_supplied_authority"] is True
    assert analysis["evidence_contradictions"]["status"] == "hard_conflict"
    assert analysis["measurement_protocol"]["status"] == "blocked"
    assert analysis["fault_isolation"]["state"] == "blocked_safety_hold"
    assert analysis["salvage_value_decision"]["decision"] == "safety_hold_or_salvage_only"
    assert analysis["reuse_splice_strategy"]["readiness"] == "blocked_safety_hold"
    assert analysis["arbitrary_board_trust_assessment"]["level"] == "blocked_safety_hold"
    assert analysis["arbitrary_board_trust_assessment"]["score"] == 0.0
    assert analysis["component_salvage_map"]["salvage_posture"] == "safety_hold"
    assert plan["integrated_plan"]["status"] == "safety_hold"


def test_sensor_board_gets_use_case_specific_reuse_recipe_without_power_release():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "reuse photographed BME280 sensor board in a logger",
            "strategy_mode": "constrained",
            "required_capabilities": ["sensor_or_adc", "connector"],
            "board_evidence": _visual_sensor_board(),
            "use_reference_catalog": False,
        }
    )

    analysis = plan["analysis"]
    strategy = analysis["reuse_splice_strategy"]

    assert analysis["board_function_inference"]["primary_function_id"] == "sensor_or_adc_module"
    assert strategy["readiness"] == "visual_mapping_only"
    assert any(recipe["recipe_id"] == "sensor_breakout_reuse" for recipe in strategy["recipes"])
    assert "first power from visual evidence" in strategy["prohibited_actions"]
    assert plan["integrated_plan"]["assurance"]["can_power_or_splice"] is False


def test_visual_marking_grounding_turns_unknown_ic_into_regulator_candidate():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "reuse unknown marked regulator board as a bench power adapter",
            "strategy_mode": "constrained",
            "required_capabilities": ["power", "connector"],
            "board_evidence": _visual_regulator_marking_board(),
            "use_reference_catalog": False,
        }
    )

    analysis = plan["analysis"]
    grounding = analysis["part_grounding"]
    strategy = analysis["reuse_splice_strategy"]
    layout = analysis["layout_reuse_boundaries"]

    assert grounding["available"] is True
    assert grounding["matched_parts"][0]["part_id"] == "ams1117_ldo"
    assert "power" in grounding["grounded_capabilities"]
    assert analysis["board_function_inference"]["primary_function_id"] == "power_distribution_or_regulator"
    assert analysis["component_salvage_map"]["preferred_reuse_class"] == "controlled_power_stage_reuse"
    assert analysis["arbitrary_board_trust_assessment"]["level"] == "grounded_visual_candidate"
    assert "Attach measured topology evidence" in " ".join(analysis["arbitrary_board_trust_assessment"]["blocking_gaps"])
    assert any(recipe["recipe_id"] == "regulated_power_stage_reuse" for recipe in strategy["recipes"])
    assert layout["section_salvage_allowed"] is False
    assert "board-section cutting from visual evidence alone" in layout["prohibited_layout_actions"]
    assert plan["integrated_plan"]["repair_brain"]["layout_reuse_boundaries"]["whole_board_reuse_preferred"] is True
    assert plan["integrated_plan"]["repair_brain"]["part_grounding"]["grounding_tasks"]
    assert plan["integrated_plan"]["assurance"]["can_power_or_splice"] is False


def test_visual_single_board_computer_gets_discovery_requirements_and_compute_function():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "inspect this photographed board for salvage and reuse options",
            "strategy_mode": "constrained",
            "board_evidence": _visual_single_board_computer(),
            "use_reference_catalog": False,
        }
    )

    analysis = plan["analysis"]
    strategy = plan["resource_strategy"]
    integrated = plan["integrated_plan"]

    assert analysis["board_function_inference"]["primary_function_id"] == "single_board_computer_module"
    assert {"controller", "power", "connector", "network_interface", "display_or_ui"}.issubset(strategy["required_capabilities"])
    assert strategy["selected_resources"]
    assert strategy["coverage"]["coverage_score"] == 1
    assert strategy["build_readiness"]["status"] == "prototype_after_evidence"
    assert integrated["assurance"]["can_power_or_splice"] is False


def test_visual_unknown_board_does_not_treat_reusable_as_ble_evidence():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "inspect this board for reusable salvage",
            "strategy_mode": "constrained",
            "board_evidence": {
                "schema_version": "board_evidence.v1",
                "components": [
                    {"id": "u1", "label": "IC Chip", "kind": "integrated_circuit", "confidence": 0.62},
                    {"id": "c1", "label": "Cap", "kind": "capacitor", "confidence": 0.62},
                    {"id": "r1", "label": "Res", "kind": "resistor", "confidence": 0.62},
                ],
                "connectors": [],
                "damage": [],
            },
            "use_reference_catalog": False,
        }
    )

    assert plan["analysis"]["board_function_inference"]["primary_function_id"] == "unknown_low_voltage_module"
    assert plan["resource_strategy"]["required_capabilities"] == ["unknown_reusable_part"]
    assert plan["integrated_plan"]["assurance"]["can_power_or_splice"] is False


def test_measured_motor_driver_gets_protected_load_splice_strategy():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "reuse measured motor driver board for a low voltage fan",
            "strategy_mode": "constrained",
            "required_capabilities": ["actuator_driver", "motor_or_load", "power"],
            "topology_evidence": _motor_topology(),
            "use_reference_catalog": False,
        }
    )

    analysis = plan["analysis"]
    strategy = analysis["reuse_splice_strategy"]
    protocols = {step["lane_id"] for step in analysis["measurement_protocol"]["steps"]}

    assert analysis["board_function_inference"]["primary_function_id"] == "load_or_motor_driver"
    assert strategy["readiness"] == "controlled_splice_ready"
    assert any(recipe["recipe_id"] == "protected_load_driver_reuse" for recipe in strategy["recipes"])
    assert any(port["interface_type"] == "actuator_or_load_output" for port in strategy["candidate_entry_points"])
    assert "load_path" in protocols
    assert plan["integrated_plan"]["assurance"]["can_power_or_splice"] is True


def test_marked_rs485_transceiver_gets_grounded_network_reuse_path():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "reuse marked RS485 board as a differential bus interface",
            "strategy_mode": "constrained",
            "required_capabilities": ["network_interface", "connector"],
            "board_evidence": _marked_board("MAX485", "unknown 8-pin interface IC", "A B VCC GND header"),
            "use_reference_catalog": False,
        }
    )

    grounding = plan["analysis"]["part_grounding"]
    strategy = plan["analysis"]["reuse_splice_strategy"]

    assert grounding["matched_parts"][0]["part_id"] == "rs485_transceiver_family"
    assert "network_interface" in grounding["grounded_capabilities"]
    assert plan["analysis"]["board_function_inference"]["primary_function_id"] == "wireless_or_rf_module"
    assert any(recipe["recipe_id"] == "rf_module_reuse" for recipe in strategy["recipes"])
    assert plan["integrated_plan"]["assurance"]["can_power_or_splice"] is False


def test_layout_boundaries_mark_battery_region_as_no_cut_zone():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "evaluate charger board with lithium battery region",
            "strategy_mode": "constrained",
            "required_capabilities": ["battery", "power"],
            "board_evidence": {
                "schema_version": "board_evidence.v1",
                "components": [
                    {"id": "bt1", "label": "Li-ion battery pack", "kind": "battery", "confidence": 0.82},
                    {"id": "u1", "label": "TP4056 charger IC", "kind": "integrated_circuit", "confidence": 0.72},
                ],
                "connectors": [{"id": "j1", "label": "BAT+ BAT- OUT+ OUT- header", "kind": "header", "confidence": 0.66}],
                "damage": [],
            },
            "use_reference_catalog": False,
        }
    )

    layout = plan["analysis"]["layout_reuse_boundaries"]

    assert layout["section_salvage_allowed"] is False
    assert layout["no_cut_zones"][0]["reason"] == "battery_or_energy_storage"
    assert "cutting, charging, loading, or desoldering through no-cut zones before clearance" in layout["prohibited_layout_actions"]


def test_completed_measured_arbitrary_board_becomes_production_release_candidate():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "release measured UART board as a reusable debug adapter",
            "target_authority_level": "production_repair",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "topology_evidence": _uart_topology(),
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
            "production_release": _release_manifest(["measured_uart_board"]),
            "use_reference_catalog": False,
        }
    )

    trust = plan["analysis"]["arbitrary_board_trust_assessment"]

    assert trust["level"] == "production_release_candidate"
    assert trust["production_readiness_score"] >= 0.85
    assert trust["functional_outcome"]["terminal_success"] is True
    assert trust["release_package"]["complete"] is True


def test_board_session_intake_gets_protocol_and_value_tasks(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")

    session = store.create_session(
        {
            "description": "photographed USB UART board",
            "route": "repair",
            "board_evidence": _visual_usb_uart_board(),
        },
        user_id="operator-1",
    )

    analysis = session["analyses"][0]["results"]
    sources = {task["source"] for task in session["evidence_tasks"]}

    assert analysis["arbitrary_board_workflow"]["available"] is True
    assert analysis["measurement_protocol"]["step_count"] > 0
    assert analysis["bench_protocol_pack"]["step_count"] > 0
    assert analysis["reuse_splice_strategy"]["readiness"] == "visual_mapping_only"
    assert "arbitrary_board_measurement_protocol" in sources
    assert "arbitrary_board_contradiction" in sources
    assert "bench_protocol_pack" in sources
