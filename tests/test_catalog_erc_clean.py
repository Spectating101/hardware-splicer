"""Catalog schematics run through the real kicad-cli ERC (never stubbed)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from hardware_splicer.build_compiler import CATALOG_BUILD_IDS, compile_catalog_build
from hardware_splicer.integrations.schematic_export import write_schematic_for_netlist
from hardware_splicer.netlist.lower import build_graph_to_netlist
from hardware_splicer.pcb.kicad_cli_erc import run_kicad_cli_erc
from hardware_splicer.plan_to_graph import splice_plan_to_build_graph

pytestmark = pytest.mark.skipif(not shutil.which("kicad-cli"), reason="kicad-cli required")

# Builds whose recipe leaves a pin that the module data says must be wired. Each entry is the exact
# remaining ERC finding; fixing the recipe (and its TypeScript mirror and footprint pads) must
# remove the entry, not loosen the test.
KNOWN_REMAINING_ERC_ERRORS = {
    "room_display_station": {("pin_not_connected", "Pin LED")},
}


def _schematic_erc(build_id: str, tmp_path: Path) -> dict:
    graph, effective_id, _notes, _warnings = splice_plan_to_build_graph(
        {"target": {"recommended_build_id": build_id}}
    )
    netlist = build_graph_to_netlist(graph)
    sch = tmp_path / f"{build_id}.kicad_sch"
    write_schematic_for_netlist(netlist, sch, title=build_id, build_id=effective_id or build_id)
    return run_kicad_cli_erc(sch, out_dir=tmp_path / "erc")


def _errors(report: dict) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for violation in report["violations"]:
        if str(violation.get("severity")).lower() != "error":
            continue
        for item in violation.get("items") or []:
            desc = str(item.get("description") or "")
            pin = desc.split(" [", 1)[0].split("Symbol ", 1)[-1]
            pin = " ".join(pin.split()[1:]) if pin.startswith("U") else pin
            found.add((str(violation.get("type")), pin))
    return found


@pytest.mark.parametrize("build_id", CATALOG_BUILD_IDS)
def test_catalog_schematic_real_erc_has_only_the_documented_errors(build_id: str, tmp_path: Path) -> None:
    report = _schematic_erc(build_id, tmp_path)
    assert report["skipped"] is False
    assert _errors(report) == KNOWN_REMAINING_ERC_ERRORS.get(build_id, set())
    assert report["pass"] is (build_id not in KNOWN_REMAINING_ERC_ERRORS)


@pytest.mark.parametrize("build_id", ["robot_drive_base", "usb_fume_extractor", "bench_power_adapter"])
def test_compiled_representative_builds_are_build_ready_under_real_erc(build_id: str, tmp_path: Path) -> None:
    result = compile_catalog_build(build_id, tmp_path, export_gerber=False)
    quality = result.design_quality
    assert quality.get("kicad_erc_pass") is True, quality.get("kicad_erc_errors")
    assert quality.get("kicad_erc_errors") == 0
    assert quality.get("build_ready") is True
    report = json.loads(
        (tmp_path / "build_compilation" / "KICAD_ERC.json").read_text(encoding="utf-8")
    )
    assert not [v for v in report.get("violations", []) if v.get("severity") == "error"]


@pytest.mark.parametrize("build_id", sorted(KNOWN_REMAINING_ERC_ERRORS))
def test_builds_with_a_real_remaining_erc_error_are_not_build_ready(build_id: str, tmp_path: Path) -> None:
    result = compile_catalog_build(build_id, tmp_path, export_gerber=False)
    assert result.design_quality.get("kicad_erc_pass") is False
    assert result.design_quality.get("build_ready") is False


def test_generic_resistors_in_a_netlist_are_connected_under_real_erc(tmp_path: Path) -> None:
    from hardware_splicer.netlist.ir import CircuitNetlist, ComponentInstance, Net, PinRef

    netlist = CircuitNetlist(
        components=[
            ComponentInstance(ref="J1", module_id="usb-power-5v"),
            ComponentInstance(ref="U1", module_id="esp32-devkit"),
            ComponentInstance(ref="U2", module_id="bme280"),
            ComponentInstance(ref="R1", module_id="resistor-4_7k"),
            ComponentInstance(ref="R2", module_id="resistor-4_7k"),
        ],
        nets=[
            Net("GND", [PinRef("J1", "GND"), PinRef("U1", "GND"), PinRef("U2", "GND")]),
            Net("+5V", [PinRef("J1", "V+"), PinRef("U1", "VIN")]),
            Net("+3V3", [PinRef("U1", "3V3"), PinRef("U2", "VCC"), PinRef("R1", "2"), PinRef("R2", "2")]),
            Net("SDA", [PinRef("U1", "GPIO21"), PinRef("U2", "SDA"), PinRef("R1", "1")]),
            Net("SCL", [PinRef("U1", "GPIO22"), PinRef("U2", "SCL"), PinRef("R2", "1")]),
        ],
    )
    sch = tmp_path / "pullups.kicad_sch"
    write_schematic_for_netlist(netlist, sch)
    report = run_kicad_cli_erc(sch, out_dir=tmp_path / "erc")
    assert _errors(report) == set(), report["violations"]
