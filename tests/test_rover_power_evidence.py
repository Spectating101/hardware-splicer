"""Outcome tests: motor power evaluation must never invent verified supplies."""
from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.project_intake import splice_and_build_from_intake
from hardware_splicer.rover_power_evidence import (
    apply_rover_power_evidence_gate,
    evaluate_rover_power,
)

ROOT = Path(__file__).resolve().parents[1]
ROVER = ROOT / "examples/intakes/splice_robot_drive_brief.json"
LOGGER = ROOT / "examples/intakes/sensor_logger_brief.json"


def _graph():
    return {"nodes": [
        {"id": "mcu", "moduleId": "esp32-devkit"},
        {"id": "driver", "moduleId": "l298n"},
        {"id": "m1", "moduleId": "dc_motor_3v_6v"},
        {"id": "m2", "moduleId": "dc_motor_3v_6v"},
    ], "wires": []}


def _real_intake():
    return json.loads(ROVER.read_text(encoding="utf-8"))


def test_declared_7v4_battery_two_6v_motors_is_not_verified_power():
    r = evaluate_rover_power(intake=_real_intake(), graph=_graph(),
                             project_build_id="robot_drive_base")
    assert r["status"] == "blocked"
    assert r["authority"] == "declared_inputs_and_catalog_topology_only"
    assert r["declared"]["battery_nominal_v"] == 7.4
    assert r["declared"]["battery_capacity_mah"] == 2200
    assert r["declared"]["motor_count"] == 2
    assert r["declared"]["motor_rated_v"] == [6, 6]
    assert r["declared"]["simultaneous_stall_current_a"] == 1.8
    assert r["power_on_authorized"] is False
    assert r["measured"]["motor_rail_v"] is None
    # Vendor limits are reference facts, NOT extrapolated 0.9A motor voltage.
    assert r["manufacturer_reference"]["logic_supply_v_range"] == [4.5, 7.0]
    assert r["manufacturer_reference"]["total_bridge_drop_at_1a_test_v"] == {"min": 1.8, "max": 3.2}
    assert "NOT a measured value" in r["manufacturer_reference"]["drop_test_conditions"]
    codes = {x["code"] for x in r["blockers"]}
    assert {
        "motor_rail_not_derived",
        "battery_discharge_limit_unknown",
        "battery_supply_unverified",
        "driver_current_thermal_unverified",
        "l298_enable_and_logic_supply_unverified",
        "physical_bench_authorization_missing",
    }.issubset(codes)


def test_capacity_never_becomes_battery_discharge_current():
    r = evaluate_rover_power(intake=_real_intake(), graph=_graph(),
                             project_build_id="robot_drive_base")
    assert "battery_discharge_limit_a" not in r["declared"]
    assert r["measured"]["battery_discharge_limit_a"] is None


def test_missing_stall_data_stays_unknown_and_never_inferred_from_nominal():
    source = _real_intake()
    source["available_parts"][1].pop("stall_current_a")
    report = evaluate_rover_power(intake=source, graph=_graph(),
                                  project_build_id="robot_drive_base")
    assert report["declared"]["simultaneous_stall_current_a"] is None
    assert "motor_stall_current_unknown" in {x["code"] for x in report["blockers"]}


def test_one_named_motor_with_explicit_quantity_two_is_counted_as_two():
    report = evaluate_rover_power(
        intake={"available_parts": [
            {"name": "6V DC motor", "type": "dc_motor", "quantity": 2,
             "voltage_v": 6, "stall_current_a": 1.1}
        ], "constraints": {"battery_voltage_v": 7.4}},
        graph=_graph(), project_build_id="robot_drive_base",
    )
    assert report["declared"]["motor_count"] == 2
    assert report["declared"]["simultaneous_stall_current_a"] == 2.2


def test_positive_declared_specs_and_even_a_fake_bench_authorization_do_not_auto_clear():
    package = {"info": {"build_id": "robot_drive_base"}, "gates": {
        "verdict": "POWER_ON_AUTHORIZED", "power_on_authorized": True,
        "build_ready": True, "fabrication_ready": True, "package_ready": True,
        "blockers": [], "next_actions": [],
    }}
    out = apply_rover_power_evidence_gate(package, intake=_real_intake(), graph=_graph())
    assert out["gates"]["power_on_authorized"] is False
    assert out["gates"]["package_ready"] is False
    assert out["gates"]["fabrication_ready"] is False
    assert out["gates"]["build_ready"] is False
    assert out["gates"]["verdict"] == "BLOCKED"
    assert len(out["gates"]["next_actions"]) >= 5
    # The caller-owned bench history is not overwritten or faked.
    assert package["gates"]["power_on_authorized"] is True


def test_sensor_logger_is_unaffected_by_rover_specific_gate():
    p = {"info": {"build_id": "sensor_logger"}, "gates": {
        "verdict": "COMPILE_READY_REVIEW_BENCH", "package_ready": True, "build_ready": True,
        "power_on_authorized": False,
    }}
    x = apply_rover_power_evidence_gate(p, intake={}, graph={"nodes": []})
    assert x["rover_power_evidence"]["status"] == "not_applicable"
    assert x["gates"] == p["gates"]


def test_real_rover_project_emits_power_tasks_but_no_unsafe_readiness(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
    intake = _real_intake()
    result = splice_and_build_from_intake(intake, out_dir=tmp_path / "rover", export_gerber=False)
    pkg = json.loads((tmp_path / "rover/PROJECT_PACKAGE.json").read_text(encoding="utf-8"))
    graph = json.loads((tmp_path / "rover/build_compilation/build_graph.json").read_text(encoding="utf-8"))
    power = pkg["rover_power_evidence"]
    assert result["ok"] is False
    assert pkg["intake_quantity_reconciliation"]["status"] == "clear"
    assert sum(n["moduleId"] == "dc_motor_3v_6v" for n in graph["nodes"]) == 2
    assert power["status"] == "blocked"
    assert power["declared"]["simultaneous_stall_current_a"] == 1.8
    assert power["compiled"]["motor_nodes"] == 2
    assert not pkg["gates"]["power_on_authorized"]
    assert not pkg["gates"]["build_ready"]
    assert not pkg["gates"]["fabrication_ready"]
    page = (tmp_path / "rover/PROJECT_PAGE.md").read_text(encoding="utf-8")
    assert "NOT AUTHORIZED TO ENERGIZE" in page
    assert "1.8" in page
    assert "physical_bench_authorization_missing" in page
    assert "not physical measurements" in page


def test_real_control_project_stays_non_rover(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
    source = json.loads(LOGGER.read_text(encoding="utf-8"))
    out = tmp_path / "logger"
    result = splice_and_build_from_intake(source, out_dir=out, export_gerber=False)
    package = json.loads((out / "PROJECT_PACKAGE.json").read_text(encoding="utf-8"))
    assert result["ok"] is True
    assert package["rover_power_evidence"]["status"] == "not_applicable"
    assert package["intake_quantity_reconciliation"]["status"] == "clear"
