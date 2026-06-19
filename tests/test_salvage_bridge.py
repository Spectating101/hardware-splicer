from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from hardware_splicer.module_resolver import (
    fill_salvage_gaps,
    infer_power_topology,
    module_overrides_for_build,
    resolve_parts_to_modules,
    salvage_plan_input_from_intake,
)
from hardware_splicer.salvage_bridge import build_intake_salvage_package
from hardware_splicer.project_intake import load_project_intake


ROOT = Path(__file__).resolve().parents[1]


def test_resolve_parts_maps_esp32_and_mosfet() -> None:
    parts = [
        {"name": "ESP32 DevKit", "type": "microcontroller"},
        {"name": "IRLZ44N module", "type": "driver"},
    ]
    resolved = resolve_parts_to_modules(parts)
    by_module = {row["module_id"]: row for row in resolved if row.get("module_id")}
    assert by_module["esp32-devkit"]["role"] == "mcu"
    assert by_module["mosfet-irlz44n"]["role"] == "drv"


def test_module_overrides_substitutes_irf520_on_3v3() -> None:
    resolved = resolve_parts_to_modules([{"name": "IRF520 MOSFET", "type": "driver"}])
    overrides = module_overrides_for_build(build_id="automatic_plant_watering", resolved_modules=resolved)
    assert overrides.get("drv") == "mosfet-irlz44n"


def test_compose_from_inventory_when_constrained() -> None:
    body = salvage_plan_input_from_intake(
        {"target": {"recommended_build_id": "generic_low_voltage_build"}},
        resolved_modules=[
            {"module_id": "usb-power-5v", "role": "pwr"},
            {"module_id": "esp32-devkit", "role": "mcu"},
            {"module_id": "mosfet-irlz44n", "role": "drv"},
        ],
        strategy_mode="constrained",
        power_topology="usb_5v",
    )
    assert body.get("compose_from_inventory") is True


def test_compose_from_inventory_builds_wired_graph(tmp_path: Path) -> None:
    from hardware_splicer.build_compiler import compile_catalog_build

    graph_input = salvage_plan_input_from_intake(
        {"target": {"recommended_build_id": "generic_low_voltage_build"}},
        resolved_modules=[
            {"module_id": "usb-power-5v"},
            {"module_id": "esp32-devkit"},
            {"module_id": "soil_moisture"},
        ],
        strategy_mode="constrained",
        power_topology="usb_5v",
    )
    result = compile_catalog_build(
        "generic_low_voltage_build",
        tmp_path,
        export_gerber=False,
        splice_plan=graph_input,
    )
    assert result.ok is True, result.error
    import json

    graph = json.loads(Path(result.build_graph_file).read_text(encoding="utf-8"))
    assert len(graph.get("nodes") or []) >= 3
    assert len(graph.get("wires") or []) >= 2


def test_infer_power_topology_usb_bank_only() -> None:
    parts = [
        {"name": "USB power bank", "type": "power_source"},
        {"name": "ESP32", "type": "microcontroller"},
    ]
    resolved = resolve_parts_to_modules(parts)
    assert infer_power_topology(parts, resolved) == "usb_5v"


def test_printer_motion_salvage_resolves_power_stepper_and_limits_offline() -> None:
    parts = [
        {"name": "dead inkjet printer donor motion board", "type": "donor_board"},
        {"name": "stepper motor X axis", "type": "stepper_motor"},
        {"name": "X axis limit switch", "type": "limit_switch"},
        {"name": "24V power supply", "type": "power_source", "voltage_v": 24.0},
        {"name": "Arduino Nano from parts bin", "type": "microcontroller"},
    ]
    resolved = fill_salvage_gaps(resolve_parts_to_modules(parts), parts=parts)
    module_ids = {row.get("module_id") for row in resolved if row.get("module_id")}
    assert infer_power_topology(parts, resolved) == "barrel_12v"
    assert "dc-barrel-12v" in module_ids
    assert "a4988-stepper" in module_ids
    assert "limit-switch-3pin" in module_ids
    assert "l298n" not in module_ids


def test_printer_motion_salvage_graph_keeps_required_power_support() -> None:
    from hardware_splicer.plan_to_graph import splice_plan_to_build_graph

    intake = load_project_intake(ROOT / "examples" / "intakes" / "splice_printer_motion_brief.json")
    package = build_intake_salvage_package(
        goal=str(intake.get("goal") or ""),
        parts=list(intake.get("available_parts") or []),
        constraints=dict(intake.get("constraints") or {}),
        project_name=str(intake.get("project_name") or "printer_motion"),
    )
    graph, build_id, _notes, warnings = splice_plan_to_build_graph(package.get("graph_input"))
    module_ids = [node.get("moduleId") for node in graph.get("nodes") or []]
    pins = {
        str(end.get("pinId") or "")
        for wire in graph.get("wires") or []
        for end in (wire.get("from") or {}, wire.get("to") or {})
    }
    assert build_id == "plotter_motion_stage"
    assert warnings == []
    assert module_ids == [
        "usb-power-5v",
        "buck-mp1584",
        "dc-barrel-12v",
        "arduino-nano",
        "a4988-stepper",
        "limit-switch-3pin",
        "limit-switch-3pin",
    ]
    assert "GPIO21" not in pins
    assert "GPIO22" not in pins
    assert {"A0", "A4", "VMOT", "VDD"}.issubset(pins)


def test_wifi_salvage_intake_resolves_usb_wall_wart_without_barrel() -> None:
    intake = load_project_intake(ROOT / "examples" / "intakes" / "salvage_wifi_logger_brief.json")
    package = build_intake_salvage_package(
        goal=str(intake.get("goal") or ""),
        parts=list(intake.get("available_parts") or []),
        constraints=dict(intake.get("constraints") or {}),
        project_name=str(intake.get("project_name") or "wifi_logger"),
    )
    module_ids = [row.get("module_id") for row in package.get("resolved_modules") or []]
    assert package.get("power_topology") == "usb_5v"
    assert "dc-barrel-12v" not in module_ids
    assert module_ids == ["esp32-devkit", "dht22", "usb-power-5v"]
    assert package.get("compose_module_ids") == module_ids


def test_plant_watering_brief_uses_usb_topology_not_barrel() -> None:
    intake = load_project_intake(ROOT / "examples" / "intakes" / "plant_watering_brief.json")
    package = build_intake_salvage_package(
        goal=str(intake.get("goal") or ""),
        parts=list(intake.get("available_parts") or []),
        constraints=dict(intake.get("constraints") or {}),
        project_name=str(intake.get("project_name") or "plant"),
    )
    assert package.get("power_topology") == "usb_5v"
    assert package.get("module_overrides", {}).get("pwr") == "usb-power-5v"
    graph_input = package.get("graph_input") or {}
    assert graph_input.get("power_topology") == "usb_5v"


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_plant_usb_salvage_graph_omits_barrel_module(tmp_path: Path) -> None:
    from hardware_splicer.build_compiler import compile_catalog_build

    intake = load_project_intake(ROOT / "examples" / "intakes" / "plant_watering_brief.json")
    package = build_intake_salvage_package(
        goal=str(intake.get("goal") or ""),
        parts=list(intake.get("available_parts") or []),
        constraints=dict(intake.get("constraints") or {}),
        project_name="plant_usb",
    )
    result = compile_catalog_build(
        "automatic_plant_watering",
        tmp_path,
        export_gerber=False,
        splice_plan=package.get("graph_input"),
        resolved_modules=package.get("resolved_modules"),
    )
    assert result.ok is True, result.error
    import json

    graph_path = result.build_graph_file
    assert graph_path and Path(graph_path).is_file()
    graph = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    module_ids = [n.get("moduleId") for n in graph.get("nodes") or []]
    assert "dc-barrel-12v" not in module_ids
    assert "usb-power-5v" in module_ids
    assert "buck-mp1584" not in module_ids
    assert result.design_quality.get("drc_pass") is True


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_fume_extractor_usb_inventory_drops_barrel_and_buck(tmp_path: Path) -> None:
    from hardware_splicer.build_compiler import compile_catalog_build

    package = build_intake_salvage_package(
        goal="USB powered solder fume extractor fan",
        parts=[
            {"name": "USB power bank", "type": "power_source"},
            {"name": "MOSFET driver", "type": "driver"},
        ],
        project_name="fume_usb",
    )
    assert package.get("power_topology") == "usb_5v"
    result = compile_catalog_build(
        "usb_fume_extractor",
        tmp_path,
        export_gerber=False,
        splice_plan=package.get("graph_input"),
        resolved_modules=package.get("resolved_modules"),
    )
    assert result.ok is True, result.error
    import json

    graph = json.loads(Path(result.build_graph_file).read_text(encoding="utf-8"))
    module_ids = [n.get("moduleId") for n in graph.get("nodes") or []]
    assert module_ids == ["usb-power-5v", "mosfet-irlz44n"]
    assert result.design_quality.get("drc_pass") is True


def test_salvage_package_for_plant_watering_goal() -> None:
    package = build_intake_salvage_package(
        goal="automatic plant waterer with ESP32 soil sensor and mini pump",
        parts=[
            {"name": "ESP32", "type": "microcontroller"},
            {"name": "soil moisture sensor", "type": "sensor"},
            {"name": "mini pump", "type": "pump"},
        ],
        project_name="plant_test",
    )
    assert package.get("recommended_build_id") == "automatic_plant_watering"
    assert package.get("graph_input", {}).get("target", {}).get("recommended_build_id") == "automatic_plant_watering"
    assert package.get("verdict") in {"ready_after_measurements", "reuse_ready", "planning_ready"}


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_plant_watering_compiles_with_salvage_graph_input(tmp_path: Path) -> None:
    from hardware_splicer.build_compiler import compile_catalog_build

    package = build_intake_salvage_package(
        goal="automatic plant waterer",
        parts=[
            {"name": "ESP32", "type": "microcontroller"},
            {"name": "soil sensor", "type": "sensor"},
            {"name": "IRLZ44N", "type": "driver"},
            {"name": "12V barrel supply", "type": "power_source"},
            {"name": "MP1584 buck", "type": "power_regulator"},
        ],
        project_name="plant_compile",
    )
    result = compile_catalog_build(
        "automatic_plant_watering",
        tmp_path,
        export_gerber=False,
        splice_plan=package.get("graph_input"),
        resolved_modules=package.get("resolved_modules"),
    )
    assert result.ok is True, result.error
    quality = result.design_quality
    assert quality.get("electrical_warnings", 99) == 0
    assert quality.get("drc_pass") is True
    assert (tmp_path / "build_compilation" / "BOM.json").is_file()
