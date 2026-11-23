"""Revision B of the ESP32 servo controller: pins match the parts' own pin functions, and KiCad DRC is clean.

Revision A is kept as the record of what was wrong; its pin check is expected to fail.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REV_A = ROOT / "examples" / "main_ctrl_esp32_servo.kicad_pcb"
REV_B = ROOT / "examples" / "main_ctrl_esp32_servo_rev_b.kicad_pcb"
SYMBOLS = Path("/usr/share/kicad/symbols")

# Net each pin function must carry on this design (pin names from KiCad's symbol library).
ESP32 = {"GND": "GND", "VDD": "+3V3", "EN": "EN", "IO0": "GPIO0", "RXD0/IO3": "UART_TX", "TXD0/IO1": "UART_RX"}
# VDD is fed by the board's AMS1117, so VREGIN must sit on the same 3.3 V net (regulator not used);
# on 5 V it would put the chip's own regulator in parallel with the AMS1117.
CP2102 = {"GND": "GND", "D+": "USB_D+", "D-": "USB_D-", "VBUS": "VBUS", "VREGIN": "+3V3", "VDD": "+3V3", "TXD": "UART_TX", "RXD": "UART_RX"}


def _symbol_pins(library: str, symbol: str) -> dict[str, str]:
    text = (SYMBOLS / f"{library}.kicad_sym").read_text()
    start = text.find(f'(symbol "{symbol}"')
    block = text[start:text.find('\n\t(symbol "', start + 10)]
    return {number: name for name, number in re.findall(r'\(pin \w+ \w+.*?\(name "([^"]*)".*?\(number "(\d+)"', block, re.S)}


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


def _pad_nets(board: Path, ref: str) -> dict[str, str]:
    for node in _sexpr(board.read_text()):
        if not (isinstance(node, list) and node and node[0] == "footprint"):
            continue
        reference = next((child[2] for child in node if isinstance(child, list) and len(child) > 2
                          and child[0] in ("property", "fp_text") and child[1] in ("Reference", "reference")), None)
        if reference != ref:
            continue
        nets = {}
        for child in node:
            if isinstance(child, list) and child and child[0] == "pad":
                net = next((item for item in child if isinstance(item, list) and item and item[0] == "net"), None)
                if net is not None:
                    nets[child[1]] = net[2]
        return nets
    raise AssertionError(f"{ref} not found in {board.name}")


def _pin_errors(board: Path) -> list[str]:
    errors = []
    for ref, library, symbol, expected in (("U1", "RF_Module", "ESP32-WROOM-32", ESP32),
                                           ("U2", "Interface_USB", "CP2102N-Axx-xQFN28", CP2102)):
        pins, nets = _symbol_pins(library, symbol), _pad_nets(board, ref)
        for number, name in pins.items():
            if name in expected and number in nets and nets[number] != expected[name]:
                errors.append(f"{ref} pin {number} ({name}) on {nets[number]}, expected {expected[name]}")
            if name in expected and expected[name] != "GND" and number not in nets:
                errors.append(f"{ref} pin {number} ({name}) unconnected, expected {expected[name]}")
        for number, net in nets.items():
            if net and number in pins and pins[number] not in expected and net in set(expected.values()) - {"GND"}:
                errors.append(f"{ref} pin {number} ({pins[number]}) carries {net}")
    return errors


needs_symbols = pytest.mark.skipif(not SYMBOLS.is_dir(), reason="KiCad symbol library not installed")


@needs_symbols
def test_rev_b_pins_match_the_parts_pin_functions():
    assert _pin_errors(REV_B) == []


@needs_symbols
def test_rev_a_is_wired_to_the_wrong_pins():
    errors = _pin_errors(REV_A)
    assert any("U1 pin 1 (GND) on +3V3" in row for row in errors)
    assert any("U2 pin 26 (TXD)" in row for row in errors)


def test_rev_b_has_boot_and_reset_buttons():
    nets = {ref: _pad_nets(REV_B, ref) for ref in ("SW1", "SW2", "C3")}
    assert set(nets["SW1"].values()) == {"GPIO0", "GND"}
    assert set(nets["SW2"].values()) == {"EN", "GND"} and set(nets["C3"].values()) == {"EN", "GND"}


@pytest.mark.skipif(shutil.which("kicad-cli") is None, reason="kicad-cli not installed")
def test_rev_b_passes_kicad_drc(tmp_path):
    report = tmp_path / "drc.json"
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all", "-o", str(report), str(REV_B)],
                   capture_output=True, check=False)
    data = json.loads(report.read_text())
    errors = [row for row in data["violations"] if row["severity"] == "error"]
    assert errors == [] and data["unconnected_items"] == []
