"""Regression: source inventory must not silently lose selected donor motors."""
from __future__ import annotations

from hardware_splicer.manufacturing_reconciliation import (
    apply_manufacturing_reconciliation,
    reconcile_intake_quantities_to_build_graph,
)


def _two_motor_intake():
    return {
        "salvage_mode": True,
        "available_parts": [
            {"name": "left 6V DC gear motor", "type": "dc_motor"},
            {"name": "right 6V DC gear motor", "type": "dc_motor"},
            {"name": "ESP32 development board", "type": "microcontroller"},
        ],
    }


def _graph(motor_count: int):
    nodes = [{"id": f"motor-{i}", "moduleId": "dc_motor_3v_6v"} for i in range(motor_count)]
    nodes += [{"id": "controller", "moduleId": "esp32-devkit"}]
    return {"nodes": nodes, "wires": []}


def test_detects_selected_second_motor_lost_from_graph():
    report = reconcile_intake_quantities_to_build_graph(_two_motor_intake(), _graph(1))
    assert report["status"] == "blocked"
    assert report["source_counts"]["dc_motor_3v_6v"] == 2
    assert report["graph_counts"]["dc_motor_3v_6v"] == 1
    assert report["blockers"][0]["code"] == "intake_graph_quantity_underrepresented"
    assert report["blockers"][0]["missing_instances"] == 1


def test_two_graph_motors_preserve_complete_inventory():
    report = reconcile_intake_quantities_to_build_graph(_two_motor_intake(), _graph(2))
    assert report["status"] == "clear"
    assert not report["blockers"]


def test_extra_unused_motor_inventory_is_warning_not_an_automatic_wiring_repair():
    report = reconcile_intake_quantities_to_build_graph(
        {"available_parts": [{"name": "unused 6V DC motor", "type": "dc_motor"}]},
        {"nodes": [{"id": "controller", "moduleId": "esp32-devkit"}]},
    )
    assert report["status"] == "clear"
    assert report["warnings"][0]["code"] == "inventory_module_not_selected"


def test_selected_graph_quantity_is_a_package_blocker_even_if_bom_matches_graph():
    graph = _graph(1)
    package = {
        "bom": {"lines": [
            {"module_id": "dc_motor_3v_6v", "qty": 1},
            {"module_id": "esp32-devkit", "qty": 1},
        ]},
        "gates": {"verdict": "REVIEW", "build_ready": True, "fabrication_ready": True},
    }
    result = apply_manufacturing_reconciliation(package, build_graph=graph, intake=_two_motor_intake())
    assert result["manufacturing_reconciliation"]["status"] == "clear"
    assert result["intake_quantity_reconciliation"]["status"] == "blocked"
    assert result["gates"]["verdict"] == "BLOCKED"
    assert result["gates"]["package_ready"] is False
    assert result["gates"]["build_ready"] is False
    assert result["gates"]["fabrication_ready"] is False
    assert any("Source inventory includes 2" in x for x in result["gates"]["blockers"])


def test_non_evaluable_source_is_not_automatically_declared_verified():
    result = reconcile_intake_quantities_to_build_graph({}, _graph(1))
    assert result["status"] == "not_evaluable"


def test_explicit_quantity_kept_when_inventory_has_one_line_with_two_motors():
    intake = {"available_parts": [{"name": "6V DC gear motor", "type": "dc_motor", "qty": 2}]}
    result = reconcile_intake_quantities_to_build_graph(intake, _graph(1))
    assert result["source_counts"]["dc_motor_3v_6v"] == 2
    assert result["status"] == "blocked"
