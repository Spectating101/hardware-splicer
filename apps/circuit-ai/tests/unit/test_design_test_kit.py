from src.intelligence.design_test_kit import build_design_test_kit


def _plant_payload():
    return {
        "diy_project": "Build automatic plant watering from an ESP32, soil sensor, USB power, MOSFET driver, and 5V pump.",
        "strategy_mode": "hybrid",
        "available_resources": [
            {
                "resource_id": "esp32",
                "name": "ESP32 dev board",
                "resource_kind": "owned",
                "capabilities": ["controller", "wireless", "usb_serial", "connector"],
                "confidence": 0.9,
                "evidence_status": "verified",
            },
            {
                "resource_id": "soil_sensor",
                "name": "soil moisture sensor",
                "resource_kind": "owned",
                "capabilities": ["sensor_or_adc", "connector"],
                "confidence": 0.8,
                "evidence_status": "verified",
            },
            {
                "resource_id": "usb_power",
                "name": "USB power source",
                "resource_kind": "owned",
                "capabilities": ["power", "connector"],
                "confidence": 0.8,
                "evidence_status": "verified",
            },
            {
                "resource_id": "pump",
                "name": "5V mini pump",
                "resource_kind": "owned",
                "capabilities": ["motor_or_load", "fan_or_pump"],
                "confidence": 0.75,
                "evidence_status": "verified",
            },
            {
                "resource_id": "mosfet_driver",
                "name": "logic MOSFET pump driver",
                "resource_kind": "owned",
                "capabilities": ["actuator_driver", "protection"],
                "confidence": 0.75,
                "evidence_status": "verified",
            },
        ],
        "use_reference_catalog": False,
    }


def _passing_netlist(load_amps=0.2):
    return {
        "version": 1,
        "voltage_sources": [{"name": "VUSB", "n_plus": "VBUS", "n_minus": "0", "volts": 5.0}],
        "loads_cc": [{"name": "pump_load", "node": "VBUS", "amps": load_amps, "gnd": "0", "min_v_off": 3.0}],
        "voltage_constraints": [{"name": "pump_voltage", "node": "VBUS", "gnd": "0", "min_v": 4.5, "max_v": 5.5}],
        "resistors": [],
        "current_sources": [],
        "traces": [],
        "ldos": [],
        "loads_cp": [],
    }


def test_design_test_kit_generates_fixture_when_netlist_is_absent():
    kit = build_design_test_kit(_plant_payload())

    tests = {row["test_id"]: row for row in kit["test_suite"]["tests"]}
    modules = {row["module_id"] for row in kit["design_model"]["modules"]}

    assert kit["available"] is True
    assert kit["design_model"]["abstraction_level"] == "module_graph"
    assert {"pump_driver", "pump_load", "power"}.issubset(modules)
    assert kit["simulation"]["available"] is False
    assert tests["dc_power_tree_netlist_required"]["status"] == "pending"
    assert kit["design_model"]["simulation_fixture_required"] is True
    assert kit["release_gate"]["decision"] in {"test_fixture_required", "simulation_passed_bench_evidence_required"}
    assert kit["release_gate"]["can_production_release"] is False


def test_design_test_kit_runs_passing_power_tree_netlist():
    payload = {
        **_plant_payload(),
        "netlist": _passing_netlist(load_amps=0.2),
        "simulation_constraints": {"source_limits": [{"source_name": "VUSB", "max_current_a": 0.5}]},
    }

    kit = build_design_test_kit(payload)
    simulation_tests = [row for row in kit["test_suite"]["tests"] if row["layer"] == "power_simulation"]

    assert kit["simulation"]["available"] is True
    assert kit["simulation"]["status"] == "completed"
    assert kit["simulation"]["issues"] == []
    assert any(row["test_id"] == "dc_power_tree_no_validator_issues" and row["status"] == "pass" for row in simulation_tests)
    assert kit["simulation"]["results"]["node_v"]["VBUS"] == 5.0
    assert kit["release_gate"]["decision"] != "blocked_by_simulation_failure"


def test_design_test_kit_blocks_overcurrent_netlist():
    payload = {
        **_plant_payload(),
        "netlist": _passing_netlist(load_amps=1.2),
        "simulation_constraints": {"source_limits": [{"source_name": "VUSB", "max_current_a": 0.5}]},
    }

    kit = build_design_test_kit(payload)
    failed_sim_tests = [row for row in kit["test_suite"]["tests"] if row["layer"] == "power_simulation" and row["status"] == "fail"]

    assert kit["simulation"]["available"] is True
    assert any(issue["issue"] == "Source current exceeded" for issue in kit["simulation"]["issues"])
    assert failed_sim_tests
    assert kit["release_gate"]["decision"] == "blocked_by_simulation_failure"
    assert kit["release_gate"]["can_power_or_splice"] is False


def test_design_test_kit_preserves_hard_safety_block():
    kit = build_design_test_kit({"diy_project": "Build a wall outlet AC lamp controller from a relay."})
    safety_tests = [row for row in kit["test_suite"]["tests"] if row["layer"] == "safety"]

    assert kit["subject"]["readiness"] == "blocked_specialist_required"
    assert any(row["status"] == "blocked" for row in safety_tests)
    assert kit["release_gate"]["decision"] == "blocked_by_safety_or_specialist_authority"
    assert kit["release_gate"]["can_advance_to_controlled_bench"] is False
