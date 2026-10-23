"""Outcome regression: correct rover hardware representation without invented power.

This checks actual generated artifacts, not just graph-shape helpers. Neither
successful execution nor count parity implies safe physical motor operation.
"""
from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.project_intake import splice_and_build_from_intake

ROOT = Path(__file__).resolve().parents[1]
ROVER = ROOT / "examples/intakes/splice_robot_drive_brief.json"
LOGGER = ROOT / "examples/intakes/sensor_logger_brief.json"


def _run(intake_path: Path, out: Path) -> tuple[dict, dict, dict, dict]:
    intake = json.loads(intake_path.read_text(encoding="utf-8"))
    result = splice_and_build_from_intake(intake, out_dir=out, export_gerber=False)
    package = json.loads((out / "PROJECT_PACKAGE.json").read_text(encoding="utf-8"))
    graph = json.loads((out / "build_compilation/build_graph.json").read_text(encoding="utf-8"))
    plan = json.loads((out / "SPLICE_PLAN.json").read_text(encoding="utf-8"))
    return result, package, graph, plan


def test_real_donor_rover_preserves_both_motors_and_refuses_unverified_power(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
    result, package, graph, plan = _run(ROVER, tmp_path / "rover")

    resolved = [
        row for row in plan["resolved_modules"] if row.get("module_id") == "dc_motor_3v_6v"
    ]
    assert len(resolved) == 2
    assert len({row.get("instance_id") for row in resolved}) == 2

    modules = {node["id"]: node["moduleId"] for node in graph["nodes"]}
    motors = {nid for nid, mid in modules.items() if mid == "dc_motor_3v_6v"}
    drivers = {nid for nid, mid in modules.items() if mid == "l298n"}
    assert len(motors) == 2
    assert len(drivers) == 1
    motor_qty = sum(
        int(line.get("qty") or 0)
        for line in package["bom"]["lines"]
        if line.get("module_id") == "dc_motor_3v_6v"
    )
    assert motor_qty == 2

    output_pairs = [
        (wire["from"]["pinId"], wire["to"]["nodeId"])
        for wire in graph["wires"]
        if wire["from"]["nodeId"] in drivers
        and wire["from"]["pinId"] in {"OUT1", "OUT2", "OUT3", "OUT4"}
    ]
    assert {pin for pin, _ in output_pairs} == {"OUT1", "OUT2", "OUT3", "OUT4"}
    assert {dest for _, dest in output_pairs} == motors

    # A goal or recipe is NOT evidence of a donor's physical power source.
    assert not {"dc-barrel-12v", "usb-power-5v", "buck-mp1584"}.intersection(modules.values())
    integrity = package["intake_quantity_reconciliation"]
    assert integrity["source_counts"]["dc_motor_3v_6v"] == 2
    assert integrity["graph_counts"]["dc_motor_3v_6v"] == 2
    assert integrity["bom_counts"]["dc_motor_3v_6v"] == 2
    assert integrity["status"] == "clear"
    assert package["manufacturing_reconciliation"]["status"] == "clear"

    # Count fidelity improves, but absent independent power keeps review blocked.
    assert not package["gates"]["build_ready"]
    assert not result["ok"]
    assert "12V barrel feeds" not in package["wiring"]["narrative_markdown"]
    assert "common ground" not in "\n".join(
        line for line in package["wiring"]["narrative_markdown"].splitlines()
        if "motor driver (OUT" in line
    )


def test_nonrover_sensor_logger_does_not_inherit_rover_motor_or_power_modifications(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
    result, package, graph, _plan = _run(LOGGER, tmp_path / "logger")
    assert result["ok"]
    assert package["intake_quantity_reconciliation"]["status"] == "clear"
    assert not any(node.get("moduleId") == "dc_motor_3v_6v" for node in graph.get("nodes", []))
