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
    quality = result.design_quality
    # Real ERC must have executed and passed; a skipped or crashed run is not a clean one.
    assert quality.get("kicad_erc_skipped") is False, quality.get("kicad_erc_reason")
    assert quality.get("kicad_erc_pass") is True and quality.get("kicad_erc_errors") == 0
    return result, netlist, pcb


# ---- engine data: the footprint table is one shared data file --------------------------------


def test_footprint_geometry_comes_from_the_shared_data_file_for_modules_this_work_touches() -> None:
    # Python and TypeScript read one file (tests/test_module_footprint_parity.py proves both
    # resolve identical pads), so the modules this work touches are checked against that file.
    shared = json.loads((DATA / "module_footprints.json").read_text(encoding="utf-8"))["modules"]
    touched = {"a4988-stepper", "terminal-block-2p", "terminal-block-2p-dc", "terminal-block-4p", "resistor-10r"}
    for module_id in touched:
        pads = resolve_module_pads(module_id, find_module(module_id))
        assert [(p["pinId"], round(p["x"], 4), round(p["y"], 4)) for p in pads] == [
            (p["pinId"], round(p["x"], 4), round(p["y"], 4)) for p in shared[module_id]["pads"]
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
    # Pads are numbered by position in the module pad table, so look the GND pad numbers up.
    def gnd_pad(module_id: str) -> int:
        pads = resolve_module_pads(module_id, find_module(module_id))
        return next(i for i, p in enumerate(pads) if p["pinId"] == "GND") + 1

    good = (
        '\n  (footprint "Connector:USB-MICRO-POWER" (layer "F.Cu")\n'
        f'    (pad "{gnd_pad("usb-power-5v")}" thru_hole circle (at 0 0) (size 1 1) (net 1 "GND"))\n  )'
        '\n  (footprint "Module:ESP32-WROOM-32" (layer "F.Cu")\n'
        f'    (pad "{gnd_pad("esp32-devkit")}" thru_hole circle (at 0 0) (size 1 1) (net 1 "GND"))\n  )'
    )
    assert netlist_pcb_parity(netlist, good)["pass"] is True
    broken = good.replace('(net 1 "GND"))\n  )\n  (footprint', '(net 0 ""))\n  )\n  (footprint', 1)
    result = netlist_pcb_parity(netlist, broken)
    assert result["pass"] is False and result["missing_on_pcb"]


# ---- plotter_motion_stage -----------------------------------------------------------------------


def test_plotter_a4988_reset_is_tied_to_sleep_and_enable_to_ground() -> None:
    assert _has_wire("plotter_motion_stage", ("a4988-stepper", "RST"), ("a4988-stepper", "SLP"))
    # EN stays tied to GND (the stage is not driven through ENABLE). That decision used to rest on the
    # registry listing only nine Nano pins, all taken; the registry now carries all 30 real pads, so
    # free GPIOs exist, and the recipe is deliberately unchanged: ENABLE is not needed to move the stage.
    assert _has_wire("plotter_motion_stage", ("a4988-stepper", "EN"), ("arduino-nano", "GND"))
    used = {w[1] for w in _wires("plotter_motion_stage") if w[0] == "arduino-nano"} | {
        w[3] for w in _wires("plotter_motion_stage") if w[2] == "arduino-nano"
    }
    assert used <= {p["id"] for p in find_module("arduino-nano")["pins"]}


def test_plotter_stepper_coils_land_on_a_real_four_pin_terminal() -> None:
    for coil, terminal_pin in (("1A", "COIL1_A"), ("1B", "COIL1_B"), ("2A", "COIL2_A"), ("2B", "COIL2_B")):
        assert _has_wire("plotter_motion_stage", ("a4988-stepper", coil), ("terminal-block-4p", terminal_pin))
    assert len(find_module("terminal-block-4p")["pins"]) == 4


def test_new_connector_and_resistor_footprints_exist_in_the_shared_footprint_file() -> None:
    exported = json.loads((DATA / "module_footprints.json").read_text(encoding="utf-8"))["modules"]
    assert "terminal-block-4p" in exported and "a4988-stepper" in exported


def test_a4988_footprint_has_a_pad_for_every_pin_including_reset_sleep_and_coils() -> None:
    spec = find_module("a4988-stepper")
    pad_ids = {p["pinId"] for p in resolve_module_pads("a4988-stepper", spec)}
    assert {p["id"] for p in spec["pins"]} <= pad_ids


def _pads(module_id: str) -> list:
    return resolve_module_pads(module_id, find_module(module_id))


def test_a4988_footprint_is_the_real_two_by_eight_stepstick() -> None:
    """Pololu A4988 carrier: 2x8 header, 2.54 mm pitch, rows 12.7 mm apart, ~15.2 x 20.3 mm."""
    pads = _pads("a4988-stepper")
    assert len(pads) == 16
    columns: dict = {}
    for pad in pads:
        columns.setdefault(round(pad["x"], 3), []).append(pad)
    assert len(columns) == 2
    left, right = (sorted(col, key=lambda p: p["y"]) for _, col in sorted(columns.items()))
    assert round(sorted(columns)[1] - sorted(columns)[0], 3) == 12.7
    for col in (left, right):
        assert len(col) == 8
        assert [round(b["y"] - a["y"], 3) for a, b in zip(col, col[1:])] == [2.54] * 7
    # Pololu pin order: one row ENABLE..DIR, the other VMOT, GND, 2B, 2A, 1A, 1B, VDD, GND.
    assert [p["pinId"] for p in left] == ["EN", "MS1", "MS2", "MS3", "RST", "SLP", "STEP", "DIR"]
    assert [p["pinId"] for p in right] == ["VMOT", "GND_MOTOR", "2B", "2A", "1A", "1B", "VDD", "GND_LOGIC"]
    body = json.loads((DATA / "module_footprints.json").read_text(encoding="utf-8"))["modules"][
        "a4988-stepper"
    ]["bodyMm"]
    assert (body["w"], body["h"]) == (15.2, 20.3)


def test_added_connector_and_resistor_footprints_match_the_real_parts() -> None:
    def pitch(module_id: str) -> set:
        xs = sorted(p["x"] for p in _pads(module_id))
        return {round(b - a, 3) for a, b in zip(xs, xs[1:])}

    # 5.08 mm screw terminals (KF301) with 4, 2 and 2 positions; 10.16 mm axial 1/4 W resistor.
    assert (len(_pads("terminal-block-4p")), pitch("terminal-block-4p")) == (4, {5.08})
    assert (len(_pads("terminal-block-2p")), pitch("terminal-block-2p")) == (2, {5.08})
    assert (len(_pads("terminal-block-2p-dc")), pitch("terminal-block-2p-dc")) == (2, {5.08})
    assert (len(_pads("resistor-10r")), pitch("resistor-10r")) == (2, {10.16})


@pytest.mark.skipif(not shutil.which("node"), reason="node required")
def test_plotter_reports_its_real_kicad_drc_errors_and_is_not_build_ready(tmp_path: Path) -> None:
    # With the true 2x8 footprint the engine's router leaves kicad-cli clearance errors (parallel
    # via lanes 0.64 mm apart). The build must say so rather than pass on a false footprint.
    result, netlist, pcb = _compile("plotter_motion_stage", tmp_path)
    quality = result.design_quality
    assert quality.get("drc_pass") is True  # the engine's own DRC
    assert quality.get("kicad_drc_pass") is False
    assert quality.get("kicad_drc_errors", 0) > 0
    assert quality.get("build_ready") is False
    report = json.loads((tmp_path / "build_compilation" / "KICAD_DRC.json").read_text(encoding="utf-8"))
    assert {v["type"] for v in report["violations"] if v["severity"] == "error"} == {"clearance"}
    # Connectivity itself is intact: the board still matches the netlist.
    assert netlist_pcb_parity(netlist, pcb)["pass"] is True


# ---- indicator_or_task_light --------------------------------------------------------------------


def test_indicator_light_has_a_microcontroller_that_drives_the_mosfet_from_a_pwm_pin() -> None:
    recipe = _recipe("indicator_or_task_light")
    assert "arduino-nano" in {m["moduleId"] for m in recipe["modules"]}
    # The Nano's PWM-capable pins are D3, D5, D6, D9, D10 and D11; the recipe drives the MOSFET from D3.
    pwm_pins = {p["id"] for p in find_module("arduino-nano")["pins"] if p["role"] == "pwm"}
    assert pwm_pins == {"D3", "D5", "D6", "D9", "D10", "D11"}
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


# ---- bench_power_adapter ------------------------------------------------------------------------


def test_bench_adapter_3v3_output_lands_on_a_two_pin_terminal() -> None:
    # The AMS1117 breakout's VIN, GND and VOUT are all pads on the carrier PCB, so the consumers'
    # wires need a terminal on the carrier; V+ is 3V3 and GND is ground. (A ground wire may only meet a gnd-role pin, so this is
    # a separate part from the signal-style speaker terminal.)
    assert _has_wire("bench_power_adapter", ("ldo-ams1117-3v3", "VOUT"), ("terminal-block-2p-dc", "V+"))
    assert _has_wire("bench_power_adapter", ("ldo-ams1117-3v3", "GND"), ("terminal-block-2p-dc", "GND"))
    assert "terminal" in " ".join(_recipe("bench_power_adapter")["notes"]).lower()


@pytest.mark.skipif(not shutil.which("node"), reason="node required")
def test_bench_adapter_compiles_with_the_output_terminal_on_the_board(tmp_path: Path) -> None:
    result, netlist, pcb = _compile("bench_power_adapter", tmp_path)
    assert result.ok is True, result.error
    assert result.design_quality.get("kicad_drc_pass") is True
    assert netlist_pcb_parity(netlist, pcb)["pass"] is True
