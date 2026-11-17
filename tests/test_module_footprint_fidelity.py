"""Module footprints match the real parts they stand for.

Ground truth, in order of preference: KiCad's own footprint and symbol libraries (read from the
installed copy, so those checks are skipped where KiCad is not installed), then a layout the
maker documents. A module whose board varies by vendor is not asserted here: it carries
``fit.status == "unverified_variant"`` and fabrication stays withheld (tests/test_module_fit_gate.py).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

from hardware_splicer.pcb import module_registry as registry

KICAD_FOOTPRINTS = Path("/usr/share/kicad/footprints")
KICAD_SYMBOLS = Path("/usr/share/kicad/symbols")

needs_kicad_library = pytest.mark.skipif(
    not (KICAD_FOOTPRINTS / "Module.pretty").is_dir() or not KICAD_SYMBOLS.is_dir(),
    reason="KiCad footprint and symbol libraries are not installed",
)

PAD_RE = re.compile(
    r'\(pad\s+"?([^\s")]+)"?\s+(thru_hole|smd|np_thru_hole)\s+\w+\s+\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+[-\d.]+)?\)'
)


def kicad_pads(relative: str) -> List[Tuple[int, float, float]]:
    """(pad number, x, y) of every through-hole pad, ordered by pad number."""
    text = (KICAD_FOOTPRINTS / relative).read_text(encoding="utf-8")
    found = [(int(n), float(x), float(y)) for n, kind, x, y in PAD_RE.findall(text) if kind == "thru_hole"]
    return sorted(found)


def kicad_pin_names(library: str, symbol: str) -> Dict[int, str]:
    """Pin number -> name of a KiCad library symbol (parents followed through ``extends``)."""
    text = (KICAD_SYMBOLS / library).read_text(encoding="utf-8")
    start = text.index(f'\n\t(symbol "{symbol}"')
    end = text.find('\n\t(symbol "', start + 5)
    block = text[start : end if end > 0 else None]
    extends = re.search(r'\(extends "([^"]+)"\)', block)
    if extends:
        return kicad_pin_names(library, extends.group(1))
    names: Dict[int, str] = {}
    for piece in block.split("(pin ")[1:]:
        found = re.search(r'\(name "([^"]*)".*?\(number "(\d+)"', piece, re.S)
        if found:
            names[int(found.group(2))] = found.group(1)
    return names


def table(module_id: str) -> List[dict]:
    return registry.resolve_module_pads(module_id, registry.find_module(module_id)) or []


def relative_to_kicad(module_id: str, relative: str) -> List[Tuple[float, float]]:
    """Offsets between our pads and KiCad's: constant when the two layouts are the same."""
    ours = table(module_id)
    theirs = kicad_pads(relative)
    assert len(ours) == len(theirs), (module_id, len(ours), len(theirs))
    return [(round(p["x"] - x, 3), round(p["y"] - y, 3)) for p, (_n, x, y) in zip(ours, theirs)]


def spec_pin_ids(module_id: str) -> set:
    return {p["id"] for p in registry.find_module(module_id)["pins"]}


def fit(module_id: str) -> dict:
    return registry.resolve_module_fit(module_id)


# ---- Arduino Nano -----------------------------------------------------------------------------


@needs_kicad_library
def test_arduino_nano_has_all_thirty_pads_in_kicad_geometry_and_order() -> None:
    pads = table("arduino-nano")
    assert len(pads) == 30
    assert len({p["pinId"] for p in pads}) == 30
    # Same coordinates as KiCad's Module:Arduino_Nano, pad for pad (a single constant offset).
    assert len(set(relative_to_kicad("arduino-nano", "Module.pretty/Arduino_Nano.kicad_mod"))) == 1
    xs = sorted({p["x"] for p in pads})
    assert round(xs[1] - xs[0], 3) == 15.24, "rows must be 15.24 mm apart"
    for column in xs:
        ys = sorted(p["y"] for p in pads if p["x"] == column)
        assert len(ys) == 15
        assert {round(b - a, 3) for a, b in zip(ys, ys[1:])} == {2.54}


@needs_kicad_library
def test_arduino_nano_pad_names_are_the_kicad_symbol_names() -> None:
    pads = table("arduino-nano")
    names = kicad_pin_names("MCU_Module.kicad_sym", "Arduino_Nano_v3.x")
    assert len(names) == 30
    for number, pad in enumerate(pads, start=1):
        kicad = names[number].split("/")[0].lstrip("+").replace("~{RESET}", "RST")
        ours = re.sub(r"_?2$", "", pad["pinId"]) if pad["pinId"] in ("GND_2", "RST2") else pad["pinId"]
        assert ours == kicad, (number, pad["pinId"], names[number])


def test_arduino_nano_declares_every_pad_as_a_pin_and_is_verified() -> None:
    assert {p["pinId"] for p in table("arduino-nano")} <= spec_pin_ids("arduino-nano")
    assert fit("arduino-nano")["status"] == "verified_against"
    assert "Arduino_Nano" in fit("arduino-nano")["verified_against"]
