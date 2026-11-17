"""Design decisions that replaced no-connects with real wiring in catalog recipes.

Each test states one decision and the data it rests on; the real-ERC consequences live in
test_catalog_erc_clean.py. Recipes are exported from plan-to-graph.ts, so these tests read the
exported JSON that the Python engine actually compiles.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from hardware_splicer.build_compiler import compile_catalog_build
from hardware_splicer.netlist.ir import CircuitNetlist
from hardware_splicer.pcb.module_registry import find_module, resolve_module_pads
from hardware_splicer.pcb.netlist_pcb_parity import netlist_pcb_parity

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "hardware_splicer" / "data"


def _recipe(build_id: str) -> Dict[str, Any]:
    return json.loads((DATA / "catalog_recipes.json").read_text(encoding="utf-8"))["recipes"][build_id]


def _wires(build_id: str) -> List[Tuple[str, str, str, str]]:
    """Wires as (from_module, from_pin, to_module, to_pin), resolved through the role table."""
    recipe = _recipe(build_id)
    roles = {m["role"]: m["moduleId"] for m in recipe["modules"]}
    return [
        (roles[w["from"]["role"]], w["from"]["pin"], roles[w["to"]["role"]], w["to"]["pin"])
        for w in recipe["wires"]
    ]


def _has_wire(build_id: str, a: Tuple[str, str], b: Tuple[str, str]) -> bool:
    return any(
        {(w[0], w[1]), (w[2], w[3])} == {a, b} for w in _wires(build_id)
    )


def _compile(build_id: str, tmp_path: Path):
    result = compile_catalog_build(build_id, tmp_path, export_gerber=False)
    build = tmp_path / "build_compilation"
    netlist = CircuitNetlist.from_dict(json.loads((build / "circuit_netlist.json").read_text(encoding="utf-8")))
    pcb = (build / "main_ctrl_build.kicad_pcb").read_text(encoding="utf-8")
    return result, netlist, pcb


# ---- engine data: Python pad tables must equal the TypeScript-exported ones --------------------


def test_exported_footprint_pads_match_the_python_pad_tables_for_modules_this_work_touches() -> None:
    # esp32-devkit already differs between the TypeScript and Python tables (Python carries every
    # declared pin, TypeScript does not); that drift predates this work, so it is not asserted here.
    exported = json.loads((DATA / "engine_pcb_data.json").read_text(encoding="utf-8"))["module_footprints"]
    touched = {"a4988-stepper", "terminal-block-2p", "terminal-block-4p", "resistor-10r", "ili9341_tft"}
    for module_id, meta in exported.items():
        if module_id not in touched:
            continue
        pads = resolve_module_pads(module_id, find_module(module_id))
        assert [(p["pinId"], round(p["x"], 4), round(p["y"], 4)) for p in pads] == [
            (p["pinId"], round(p["x"], 4), round(p["y"], 4)) for p in meta["pads"]
        ], module_id


def test_netlist_pcb_parity_notices_a_pad_that_leaves_its_net() -> None:
    netlist = CircuitNetlist.from_dict(
        {
            "components": [
                {"ref": "U1", "module_id": "usb-power-5v"},
                {"ref": "U2", "module_id": "esp32-devkit"},
            ],
            "nets": [{"name": "GND", "pins": [{"component_ref": "U1", "pin": "GND"}, {"component_ref": "U2", "pin": "GND"}]}],
        }
    )
    good = (
        '\n  (footprint "Connector:USB-MICRO-POWER" (layer "F.Cu")\n'
        '    (pad "2" thru_hole circle (at 0 0) (size 1 1) (net 1 "GND"))\n  )'
        '\n  (footprint "Module:ESP32-WROOM-32" (layer "F.Cu")\n'
        '    (pad "2" thru_hole circle (at 0 0) (size 1 1) (net 1 "GND"))\n  )'
    )
    assert netlist_pcb_parity(netlist, good)["pass"] is True
    broken = good.replace('(net 1 "GND"))\n  )\n  (footprint', '(net 0 ""))\n  )\n  (footprint', 1)
    result = netlist_pcb_parity(netlist, broken)
    assert result["pass"] is False and result["missing_on_pcb"]


# ---- plotter_motion_stage -----------------------------------------------------------------------


def test_plotter_a4988_reset_is_tied_to_sleep_and_enable_to_ground() -> None:
    assert _has_wire("plotter_motion_stage", ("a4988-stepper", "RST"), ("a4988-stepper", "SLP"))
    # Every Arduino Nano pin in the module data is already used (D2 STEP, D3 DIR, A0/A4 limit
    # switches, A5 servo), so there is no free GPIO and EN is tied to GND, not driven.
    assert _has_wire("plotter_motion_stage", ("a4988-stepper", "EN"), ("arduino-nano", "GND"))
    nano_signal_pins = {p["id"] for p in find_module("arduino-nano")["pins"] if p["role"] not in {"power_in", "power_out", "gnd"}}
    used = {w[1] for w in _wires("plotter_motion_stage") if w[0] == "arduino-nano"} | {
        w[3] for w in _wires("plotter_motion_stage") if w[2] == "arduino-nano"
    }
    assert nano_signal_pins <= used


def test_plotter_stepper_coils_land_on_a_real_four_pin_terminal() -> None:
    for coil, terminal_pin in (("1A", "COIL1_A"), ("1B", "COIL1_B"), ("2A", "COIL2_A"), ("2B", "COIL2_B")):
        assert _has_wire("plotter_motion_stage", ("a4988-stepper", coil), ("terminal-block-4p", terminal_pin))
    assert len(find_module("terminal-block-4p")["pins"]) == 4


def test_new_connector_and_resistor_footprints_exist_in_the_exported_tables() -> None:
    exported = json.loads((DATA / "engine_pcb_data.json").read_text(encoding="utf-8"))["module_footprints"]
    assert "terminal-block-4p" in exported and "a4988-stepper" in exported


def test_a4988_footprint_has_a_pad_for_every_pin_including_reset_sleep_and_coils() -> None:
    spec = find_module("a4988-stepper")
    pad_ids = {p["pinId"] for p in resolve_module_pads("a4988-stepper", spec)}
    assert {p["id"] for p in spec["pins"]} <= pad_ids


@pytest.mark.skipif(not shutil.which("node"), reason="node required")
def test_plotter_compiles_with_pcb_connectivity_matching_the_netlist(tmp_path: Path) -> None:
    result, netlist, pcb = _compile("plotter_motion_stage", tmp_path)
    assert result.design_quality.get("drc_pass") is True, result.design_quality.get("drc_violations")
    assert result.design_quality.get("kicad_drc_pass") is True
    parity = netlist_pcb_parity(netlist, pcb)
    assert parity["pass"] is True, parity
    # The RST-SLP strap and the coil terminal are physical nets on the board, not schematic-only.
    assert any(
        {"RST", "SLP"} <= {p.pin for p in net.pins}
        for net in netlist.nets
    )


# ---- indicator_or_task_light --------------------------------------------------------------------


def test_indicator_light_has_a_microcontroller_that_drives_the_mosfet_from_a_pwm_pin() -> None:
    recipe = _recipe("indicator_or_task_light")
    assert "arduino-nano" in {m["moduleId"] for m in recipe["modules"]}
    # Arduino Nano D3 is the pin the module data marks PWM-capable (role "pwm").
    pwm_pins = {p["id"] for p in find_module("arduino-nano")["pins"] if p["role"] == "pwm"}
    assert pwm_pins == {"D3"}
    assert _has_wire("indicator_or_task_light", ("arduino-nano", "D3"), ("mosfet-irlz44n", "SIG"))
    # The Nano is powered from the same buck output as the MOSFET rail and shares its ground.
    assert _has_wire("indicator_or_task_light", ("buck-mp1584", "OUT+"), ("arduino-nano", "VIN"))
    assert _has_wire("indicator_or_task_light", ("buck-mp1584", "OUT-"), ("arduino-nano", "GND"))
    note = " ".join(recipe["notes"])
    assert "D3" in note and "PWM" in note


@pytest.mark.skipif(not shutil.which("node"), reason="node required")
def test_indicator_light_compiles_with_the_nano_and_pcb_matches_the_netlist(tmp_path: Path) -> None:
    result, netlist, pcb = _compile("indicator_or_task_light", tmp_path)
    assert result.ok is True, result.error
    assert result.design_quality.get("kicad_drc_pass") is True
    assert any({"D3", "SIG"} <= {p.pin for p in net.pins} for net in netlist.nets)
    assert netlist_pcb_parity(netlist, pcb)["pass"] is True


# ---- room_display_station -----------------------------------------------------------------------


def test_display_backlight_is_fed_from_3v3_through_a_stated_series_resistor() -> None:
    spec = find_module("ili9341_tft")
    led = next(p for p in spec["pins"] if p["id"] == "LED")
    # The module data only says "Backlight": no onboard resistor or transistor is documented,
    # so the recipe adds its own current limiter.
    assert led["notes"] == "Backlight"
    assert "resistor" not in json.dumps(spec).lower() and "transistor" not in json.dumps(spec).lower()
    assert _has_wire("room_display_station", ("esp32-devkit", "3V3"), ("resistor-10r", "1"))
    assert _has_wire("room_display_station", ("resistor-10r", "2"), ("ili9341_tft", "LED"))
    assert "10" in find_module("resistor-10r")["label"]
    note = " ".join(_recipe("room_display_station")["notes"])
    assert "10 ohm" in note and "backlight" in note.lower()


@pytest.mark.skipif(not shutil.which("node"), reason="node required")
def test_room_display_compiles_with_the_backlight_resistor_on_the_board(tmp_path: Path) -> None:
    result, netlist, pcb = _compile("room_display_station", tmp_path)
    assert result.ok is True, result.error
    assert result.design_quality.get("kicad_drc_pass") is True
    assert netlist_pcb_parity(netlist, pcb)["pass"] is True


# ---- small_audio_amp_box ------------------------------------------------------------------------


def test_speaker_outputs_land_on_a_two_pin_terminal_on_the_carrier() -> None:
    # The MAX98357A footprint carries SPK+ and SPK- as pads on the carrier PCB, so the speaker
    # wires cannot land on the breakout itself; they get a real terminal.
    pads = {p["pinId"] for p in resolve_module_pads("max98357a-i2s-amp", find_module("max98357a-i2s-amp"))}
    assert {"SPK+", "SPK-"} <= pads
    assert _has_wire("small_audio_amp_box", ("max98357a-i2s-amp", "SPK+"), ("terminal-block-2p", "1"))
    assert _has_wire("small_audio_amp_box", ("max98357a-i2s-amp", "SPK-"), ("terminal-block-2p", "2"))
    assert "SPK-" in " ".join(_recipe("small_audio_amp_box")["notes"])


@pytest.mark.skipif(not shutil.which("node"), reason="node required")
def test_audio_box_compiles_with_the_speaker_terminal_on_the_board(tmp_path: Path) -> None:
    result, netlist, pcb = _compile("small_audio_amp_box", tmp_path)
    assert result.ok is True, result.error
    assert result.design_quality.get("kicad_drc_pass") is True
    assert netlist_pcb_parity(netlist, pcb)["pass"] is True
