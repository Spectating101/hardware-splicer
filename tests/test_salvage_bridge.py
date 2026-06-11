from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from hardware_splicer.module_resolver import module_overrides_for_build, resolve_parts_to_modules
from hardware_splicer.salvage_bridge import build_intake_salvage_package


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
