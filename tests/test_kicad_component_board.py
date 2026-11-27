"""Component-level KiCad generation: library symbols, pin coverage, and KiCad's read-back of the written schematic."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from hardware_splicer import kicad_component_board as kb

needs_libs = pytest.mark.skipif(not (kb.symbol_dir() / "Device.kicad_sym").is_file(), reason="KiCad symbol libraries not installed")
needs_cli = pytest.mark.skipif(shutil.which("kicad-cli") is None, reason="kicad-cli not on PATH")


def _divider() -> kb.Design:
    parts = [kb.Part("R1", "Device:R", "10k", "Resistor_SMD:R_0603_1608Metric", sch_xy=(50.8, 50.8)),
             kb.Part("R2", "Device:R", "10k", "Resistor_SMD:R_0603_1608Metric", sch_xy=(76.2, 50.8)),
             kb.Part("J1", "Connector_Generic:Conn_01x03", "IN", "Connector_JST:JST_EH_B3B-EH-A_1x03_P2.50mm_Vertical",
                     sch_xy=(25.4, 50.8))]
    nets = {"VIN": ["J1.1", "R1.1"], "MID": ["R1.2", "R2.1", "J1.2"], "GND": ["R2.2", "J1.3"]}
    return kb.Design(name="divider", title="divider", parts=parts, nets=nets, paper="A4")


def test_sexpr_round_trip_keeps_quoting() -> None:
    tree = kb.parse_sexpr('(a "b c" (d 1.27 "e\\"f") g)')
    assert tree == ["a", "b c", ["d", "1.27", 'e"f'], "g"]
    assert kb.parse_sexpr(kb.dump_sexpr(tree)) == tree


@needs_libs
def test_derived_symbols_are_flattened_with_their_own_name() -> None:
    sym = kb.library_symbol("74xGxx:74AHCT1G125")  # the library entry extends 74LVC1G125
    assert sym[1] == "74xGxx:74AHCT1G125"
    assert not any(isinstance(n, list) and n and n[0] == "extends" for n in sym)
    subs = [str(n[1]) for n in sym if isinstance(n, list) and n and n[0] == "symbol"]
    assert subs and all(s.startswith("74AHCT1G125_") for s in subs)
    assert sorted(p.number for p in kb.symbol_pins(sym)) == ["1", "2", "3", "4", "5"]
    assert kb.symbol_property(sym, "Value") == "74AHCT1G125"


@needs_libs
def test_pin_coverage_names_missing_unknown_and_doubled_pins() -> None:
    design = _divider()
    assert kb.pin_coverage(design)["pass"]
    design.nets["GND"] = ["R2.2", "J1.9"]
    design.nets["MID"].append("R1.1")
    report = kb.pin_coverage(design)
    assert not report["pass"]
    assert report["unknown_endpoints"] == ["GND: J1.9"]
    assert "J1.3" in report["pins_neither_connected_nor_declared_unused"]
    assert set(report["on_several_nets"]["R1.1"]) == {"VIN", "MID"}


@needs_libs
@needs_cli
def test_kicad_reads_back_the_written_nets_and_catches_a_mismatch(tmp_path: Path) -> None:
    design = _divider()
    sch = tmp_path / "divider.kicad_sch"
    kb.write_schematic(design, sch)
    readback = kb.schematic_netlist(sch)
    assert kb.netlist_parity(design, readback)["pass"]
    assert kb.run_erc(sch, tmp_path)["errors"] == 0
    design.nets["MID"] = ["R1.2", "R2.1"]
    design.nets["GND"] = ["R2.2", "J1.3", "J1.2"]
    report = kb.netlist_parity(design, readback)
    assert not report["pass"] and set(report["mismatched"]) == {"MID", "GND"}


@needs_libs
def test_two_nets_on_one_point_are_refused(tmp_path: Path) -> None:
    design = _divider()
    design.part("R2").sch_xy = design.part("R1").sch_xy  # stacked: R2's pins land on R1's
    with pytest.raises(ValueError, match="already used by net"):
        kb.write_schematic(design, tmp_path / "x.kicad_sch")
