"""Revision B of the ESP32 servo controller, checked against its spec, KiCad's symbols and KiCad DRC.

* Every footprint and every pad net on the board equals the build script's PARTS spec.
* Every pin of the active parts carries the net its pin function needs, by KiCad's own symbol library
  (inherited symbols resolved); every ground pin is on GND and no other pin is.
* KiCad DRC: no errors and nothing unconnected; drills meet the spec's 0.3 mm minimum; the servo supply
  is at least 1.0 mm; holes and the USB connector sit where the pan/tilt spec puts them.

Revision A is kept as the record of what was wrong; its pin check is expected to fail.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REV_A = ROOT / "examples" / "main_ctrl_esp32_servo.kicad_pcb"
REV_B = ROOT / "examples" / "main_ctrl_esp32_servo_rev_b.kicad_pcb"
SPEC = ROOT / "examples" / "hardware_splicer_closed_mechatronics_demo.json"
SYMBOLS = Path("/usr/share/kicad/symbols")


def _build_script():
    spec = importlib.util.spec_from_file_location("build_esp32_servo_rev_b", ROOT / "scripts" / "build_esp32_servo_rev_b.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # pcbnew is imported lazily, so this needs no KiCad
    return module


PARTS = _build_script().PARTS

# Net each pin function must carry (KiCad symbol pin names); every other pin must be unconnected.
FUNCTIONS = {
    "U1": ("ESP32-WROOM-32", {"GND": "GND", "VDD": "+3V3", "EN": "EN", "IO0": "GPIO0", "IO25": "SERVO_PWM_PAN",
                              "IO26": "SERVO_PWM_TILT", "IO32": "SDA", "IO33": "SCL", "RXD0/IO3": "UART_TX",
                              "TXD0/IO1": "UART_RX"}),
    # Regulator not used: VDD and VREGIN on the board's 3.3 V; VBUS sensed through the divider.
    "U2": ("CP2102N-Axx-xQFN28", {"GND": "GND", "D+": "USB_D+", "D-": "USB_D-", "VDD": "+3V3", "VREGIN": "+3V3",
                                  "VBUS": "VBUS_SENSE", "~{RST}": "CP_RST", "~{RTS}": "RTS", "~{DTR}": "DTR",
                                  "RXD": "UART_RX", "TXD": "UART_TX"}),
    "U3": ("AMS1117-3.3", {"GND": "GND", "VO": "+3V3", "VI": "VBUS"}),
    "U4": ("USBLC6-2SC6", {"GND": "GND", "I/O1": "USB_D+", "I/O2": "USB_D-", "VBUS": "VBUS"}),
    "Q1": ("MMBT3904", {"B": "Q1_B", "E": "RTS", "C": "EN"}),
    "Q2": ("MMBT3904", {"B": "Q2_B", "E": "DTR", "C": "GPIO0"}),
}


# ---- KiCad file parsing ------------------------------------------------------------------------

def _sexpr(text: str) -> list:
    """Parse a KiCad s-expression file into nested lists of strings."""
    tokens = re.findall(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+', text)
    stack: list[list] = [[]]
    for token in tokens:
        if token == "(":
            stack.append([])
        elif token == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(token[1:-1] if token.startswith('"') else token)
    return stack[0][0]


def _child(node: list, name: str):
    return next((item for item in node if isinstance(item, list) and item and item[0] == name), None)


def _children(node: list, name: str) -> list:
    return [item for item in node if isinstance(item, list) and item and item[0] == name]


def _symbol(name: str) -> dict[str, str]:
    """Pin number -> pin name for a KiCad symbol, following `extends`. Fails loudly if not found."""
    for library in sorted(SYMBOLS.glob("*.kicad_sym")):
        tree = _sexpr(library.read_text())
        for symbol in _children(tree, "symbol"):
            if symbol[1] != name:
                continue
            parent = _child(symbol, "extends")
            if parent is not None:
                return _symbol(parent[1])
            pins = {}
            for unit in [symbol] + _children(symbol, "symbol"):
                for pin in _children(unit, "pin"):
                    pins[_child(pin, "number")[1]] = _child(pin, "name")[1]
            assert pins, f"symbol {name} has no pins"
            return pins
    raise AssertionError(f"symbol {name} not found in {SYMBOLS}")


def _board(path: Path) -> dict:
    """ref -> {"at": (x, y, rot), "pads": {number: [net, ...]}, "drills": [mm]} plus tracks and vias."""
    tree = _sexpr(path.read_text())
    net_names = {item[1]: item[2] for item in _children(tree, "net") if len(item) > 2}
    footprints = {}
    for node in _children(tree, "footprint"):
        reference = next((child[2] for child in node if isinstance(child, list) and len(child) > 2
                          and child[0] in ("property", "fp_text") and child[1] in ("Reference", "reference")), None)
        at = _child(node, "at")
        pads, drills = {}, []
        for pad in _children(node, "pad"):
            net = _child(pad, "net")
            pads.setdefault(pad[1], []).append(net[2] if net is not None and len(net) > 2 else "")
            drill = _child(pad, "drill")
            if drill is not None and len(drill) > 1 and drill[1] not in ("oval",):
                drills.append(float(drill[1]))
        footprints[reference] = {"at": tuple(float(value) for value in at[1:4]) if len(at) > 3 else (float(at[1]), float(at[2]), 0.0),
                                 "pads": pads, "drills": drills}
    segments = [{"net": net_names.get(_child(seg, "net")[1], _child(seg, "net")[1]), "width": float(_child(seg, "width")[1])}
                for seg in _children(tree, "segment")]
    vias = [float(_child(via, "drill")[1]) for via in _children(tree, "via")]
    return {"footprints": footprints, "segments": segments, "via_drills": vias}


def _pin_errors(board: dict, refs=None) -> list[str]:
    errors = []
    for ref, (symbol, functions) in FUNCTIONS.items():
        if refs is not None and ref not in refs:
            continue
        footprint = board["footprints"].get(ref)
        if footprint is None:
            errors.append(f"{ref} missing")
            continue
        for number, name in _symbol(symbol).items():
            expected = functions.get(name, "")
            for net in footprint["pads"].get(number, [None]):
                if net is None:
                    if expected:
                        errors.append(f"{ref} pin {number} ({name}) has no pad, expected {expected}")
                elif net != expected:
                    errors.append(f"{ref} pin {number} ({name}) carries {net or 'nothing'}, expected {expected or 'nothing'}")
    return errors


needs_symbols = pytest.mark.skipif(not SYMBOLS.is_dir(), reason="KiCad symbol library not installed")


# ---- Tests -------------------------------------------------------------------------------------

def test_every_footprint_and_pad_net_matches_the_spec():
    board = _board(REV_B)["footprints"]
    assert set(board) == set(PARTS)
    for ref, (_, _, _, (x, y), rotation, nets) in PARTS.items():
        assert board[ref]["at"][:2] == pytest.approx((x, y), abs=1e-3), ref
        for number, assigned in board[ref]["pads"].items():
            assert set(assigned) == {nets.get(number, "")}, f"{ref} pad {number}: {assigned}"
        assert set(nets) <= set(board[ref]["pads"]), f"{ref} spec names pads the footprint lacks"


@needs_symbols
def test_symbol_lookup_fails_loudly():
    with pytest.raises(AssertionError):
        _symbol("NO-SUCH-PART-XYZ")
    assert _symbol("USBLC6-2SC6")["5"] == "VBUS"  # inherited from USBLC6-2P6


@needs_symbols
def test_rev_b_pins_match_the_parts_pin_functions():
    assert _pin_errors(_board(REV_B)) == []


@needs_symbols
def test_rev_a_is_wired_to_the_wrong_pins():
    errors = _pin_errors(_board(REV_A), refs={"U1"})
    assert any("U1 pin 1 (GND) carries +3V3" in row for row in errors)
    assert any("U1 pin 2 (VDD) carries EN" in row for row in errors)


def test_rev_b_has_boot_reset_and_auto_reset():
    pads = {ref: _board(REV_B)["footprints"][ref]["pads"] for ref in ("SW1", "SW2", "C3", "R8", "R9")}
    assert {net for nets in pads["SW1"].values() for net in nets} == {"GPIO0", "GND"}
    assert {net for nets in pads["SW2"].values() for net in nets} == {"EN", "GND"}
    assert {net for nets in pads["R8"].values() for net in nets} == {"DTR", "Q1_B"}
    assert {net for nets in pads["R9"].values() for net in nets} == {"RTS", "Q2_B"}


def test_rev_b_meets_the_pan_tilt_board_spec():
    board = _board(REV_B)
    spec = json.loads(SPEC.read_text())
    text = json.dumps(spec)
    mounts = [(mount["x_mm"], mount["y_mm"]) for mount in _find(spec, "mounts")]
    holes = sorted(board["footprints"][ref]["at"][:2] for ref in ("MH1", "MH2"))
    assert holes == sorted(mounts)
    port = next(row for row in _find(spec, "ports") if row["label"] == "usb_access")["rect"]
    usb_x, usb_y, _ = board["footprints"]["J1"]["at"]
    assert port["x_mm"] <= usb_x <= port["x_mm"] + port["w_mm"]
    # The footprint's "PCB Edge" marker is 2.688 mm in front of its origin; rotated 180 it meets y = 0.
    assert usb_y == pytest.approx(2.688, abs=0.01)
    minimum = float(re.search(r'"via_min_drill_mm":\s*([\d.]+)', text).group(1))
    drills = board["via_drills"] + [d for fp in board["footprints"].values() for d in fp["drills"]]
    assert min(drills) >= minimum - 1e-9
    servo = [seg["width"] for seg in board["segments"] if seg["net"] == "SERVO_5V"]
    assert servo and min(servo) >= 1.0


def _find(node, key):
    if isinstance(node, dict):
        if key in node:
            return node[key]
        for value in node.values():
            found = _find(value, key)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find(value, key)
            if found is not None:
                return found
    return None


@pytest.mark.skipif(shutil.which("kicad-cli") is None, reason="kicad-cli not installed")
def test_rev_b_passes_kicad_drc(tmp_path):
    report = tmp_path / "drc.json"
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all", "-o", str(report), str(REV_B)],
                   capture_output=True, check=False)
    data = json.loads(report.read_text())
    errors = [row for row in data["violations"] if row["severity"] == "error"]
    assert errors == [] and data["unconnected_items"] == []


@pytest.mark.skipif(shutil.which("kicad-cli") is None, reason="kicad-cli not installed")
def test_rev_b_clears_the_board_drc_release_gate_and_rev_a_does_not():
    from hardware_splicer import mechatronics_authority
    from hardware_splicer.mechatronics_authority import _electrical_status

    def status(board):
        mechatronics_authority._DRC_CACHE.clear()
        return _electrical_status({
            "machine": {"boards": [{"board_id": "main_ctrl", "requirements": {}}]},
            "board_design_files": {"main_ctrl": {"kind": "pcb", "path": str(board)}},
            "circuit_authority": {"production_authorized": True},
        }, {})

    assert status(REV_B)["release_ready"] is True
    assert status(REV_A)["release_ready"] is False
