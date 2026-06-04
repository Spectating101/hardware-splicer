from src.engines.netlist_io import netlist_from_dict
from src.intelligence.design_test_kit import build_design_test_kit
from src.intelligence.topology_netlist_compiler import compile_topology_to_netlist


def _trusted():
    return {
        "instrument_id": "bench_dmm_01",
        "instrument_type": "calibrated_dmm",
        "calibration_status": "valid",
        "recorded_at": "2026-06-02T03:00:00Z",
        "operator_id": "operator-1",
        "evidence_uri": "session://measurements/topology-netlist",
    }


def _measured_power_topology(current_value=120, current_unit="mA"):
    return {
        "schema_version": "topology_evidence.v1",
        **_trusted(),
        "connectors": [
            {
                "ref": "J1",
                "label": "measured USB power breakout",
                "status": "verified",
                "pins": [
                    {"pin": "1", "net": "VBUS", "role": "power", "voltage": 5.02, "status": "verified"},
                    {"pin": "2", "net": "GND", "role": "ground", "status": "verified"},
                ],
            }
        ],
        "resistance": [
            {
                "target": "power to ground no-short",
                "value": "pass",
                "unit": "ohm",
                "status": "pass",
            }
        ],
        "current": [
            {
                "target": "current draw under current-limited supply",
                "value": current_value,
                "unit": current_unit,
                "status": "pass",
            }
        ],
    }


def test_topology_netlist_compiler_turns_measured_power_topology_into_simulatable_netlist():
    compiled = compile_topology_to_netlist(
        {
            "topology_evidence": _measured_power_topology(),
            "constraints": {"current_limit_a": 0.5},
        }
    )

    netlist_from_dict(compiled["netlist"])

    assert compiled["available"] is True
    assert compiled["coverage"]["simulation_ready"] is True
    assert compiled["netlist"]["voltage_sources"][0]["n_plus"] == "VBUS"
    assert compiled["netlist"]["voltage_sources"][0]["volts"] == 5.02
    assert compiled["netlist"]["loads_cc"][0]["amps"] == 0.12
    assert compiled["constraints"]["source_limits"][0]["max_current_a"] == 0.5
    assert compiled["issues"] == []


def test_design_test_kit_auto_uses_compiled_topology_netlist():
    kit = build_design_test_kit(
        {
            "diy_project": "Build a low-voltage USB power breakout from a measured connector.",
            "topology_evidence": _measured_power_topology(current_value=180, current_unit="mA"),
            "constraints": {"current_limit_a": 0.5},
        }
    )

    tests = {row["test_id"]: row for row in kit["test_suite"]["tests"]}

    assert kit["design_model"]["simulation_model_source"] == "compiled_topology"
    assert kit["design_model"]["compiled_topology_netlist"]["available"] is True
    assert kit["simulation"]["available"] is True
    assert kit["simulation"]["status"] == "completed"
    assert kit["simulation"]["issues"] == []
    assert tests["topology_netlist_selected_for_simulation"]["status"] == "pass"
    assert "dc_power_tree_netlist_required" not in tests


def test_topology_netlist_compiler_warns_when_load_current_is_missing():
    topology = _measured_power_topology(current_value="pass", current_unit="")
    compiled = compile_topology_to_netlist({"topology_evidence": topology})

    issue_ids = {row["issue_id"] for row in compiled["issues"]}

    assert compiled["available"] is True
    assert compiled["coverage"]["simulation_ready"] is False
    assert compiled["netlist"]["voltage_sources"]
    assert compiled["netlist"]["loads_cc"] == []
    assert "load_model_missing" in issue_ids
    assert compiled["load_envelope"]["available"] is False


def test_design_test_kit_builds_bounded_load_envelope_for_missing_load_with_source_limit():
    topology = _measured_power_topology(current_value="pass", current_unit="")
    kit = build_design_test_kit(
        {
            "diy_project": "Build a low-voltage USB power breakout from measured power pins, but current is not measured yet.",
            "topology_evidence": topology,
            "constraints": {"current_limit_a": 0.5},
        }
    )
    compiled = kit["design_model"]["compiled_topology_netlist"]
    envelope = kit["simulation"]["load_envelope"]
    tests = {row["test_id"]: row for row in kit["test_suite"]["tests"]}

    assert compiled["coverage"]["simulation_ready"] is False
    assert compiled["coverage"]["bounded_envelope_ready"] is True
    assert compiled["load_envelope"]["recommended_max_load_a"] == 0.4
    assert envelope["available"] is True
    assert envelope["status"] == "pass"
    assert envelope["scenario_count"] == 5
    assert tests["bounded_load_envelope_available"]["status"] == "pass"
    assert kit["release_gate"]["decision"] == "bounded_load_envelope_measurement_required"
    assert kit["release_gate"]["can_power_or_splice"] is False


def test_topology_netlist_compiler_blocks_power_ground_short():
    topology = _measured_power_topology()
    topology["resistance"] = [
        {
            "target": "power to ground no-short",
            "value": "fail",
            "notes": "short detected between VBUS and GND",
            "status": "failed",
        }
    ]

    compiled = compile_topology_to_netlist({"topology_evidence": topology})
    kit = build_design_test_kit(
        {
            "diy_project": "Build a low-voltage USB power breakout from this measured connector.",
            "topology_evidence": topology,
        }
    )

    assert compiled["available"] is False
    assert compiled["source"] == "blocked_topology_hazard"
    assert any(row["severity"] == "critical" for row in compiled["issues"])
    assert kit["release_gate"]["decision"] == "blocked_by_safety_or_specialist_authority"
    assert any(
        row["test_id"].startswith("topology_compile_") and row["status"] == "blocked"
        for row in kit["test_suite"]["tests"]
    )


def test_topology_netlist_compiler_accepts_bench_capture_input():
    capture = {
        "schema_version": "bench_topology_capture.v1",
        "capture_id": "bench-power-001",
        "operator_id": "operator-1",
        "recorded_at": "2026-06-02T03:00:00Z",
        "instruments": [{"instrument_id": "bench_dmm_01", "instrument_type": "calibrated_dmm", "calibration_status": "valid"}],
        "artifacts": [{"kind": "measurement_log", "uri": "session://bench/power-log"}],
        "connectors": [
            {
                "ref": "J1",
                "label": "bench verified power header",
                "pins": [
                    {"pin": "1", "net": "VCC", "role": "vcc", "voltage": 3.3, "status": "verified"},
                    {"pin": "2", "net": "GND", "role": "gnd", "status": "verified"},
                ],
            }
        ],
        "measurements": [
            {"kind": "resistance", "target": "power to ground no-short", "value": "pass", "status": "pass"},
            {"kind": "current", "target": "current draw under current-limited supply", "value": 75, "unit": "mA", "status": "pass"},
        ],
    }

    compiled = compile_topology_to_netlist({"bench_topology_capture": capture, "constraints": {"current_limit_a": 0.25}})

    assert compiled["available"] is True
    assert compiled["netlist"]["voltage_sources"][0]["n_plus"] == "VCC"
    assert compiled["netlist"]["loads_cc"][0]["amps"] == 0.075
    assert compiled["constraints"]["source_limits"][0]["max_current_a"] == 0.25
