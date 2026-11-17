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


# ---- Raspberry Pi Pico --------------------------------------------------------------------------


@needs_kicad_library
def test_rpi_pico_has_all_forty_pads_in_kicad_geometry_and_order() -> None:
    pads = table("rpi-pico")
    assert len(pads) == 40
    assert len({p["pinId"] for p in pads}) == 40
    assert len(set(relative_to_kicad("rpi-pico", "Module.pretty/RaspberryPi_Pico_Common_THT.kicad_mod"))) == 1
    xs = sorted({p["x"] for p in pads})
    assert round(xs[1] - xs[0], 3) == 17.78, "rows must be 17.78 mm apart"
    for column in xs:
        ys = sorted(p["y"] for p in pads if p["x"] == column)
        assert len(ys) == 20
        assert {round(b - a, 3) for a, b in zip(ys, ys[1:])} == {2.54}


@needs_kicad_library
def test_rpi_pico_pad_names_are_the_kicad_symbol_names() -> None:
    names = kicad_pin_names("MCU_Module.kicad_sym", "RaspberryPi_Pico")
    assert len(names) == 40
    for number, pad in enumerate(table("rpi-pico"), start=1):
        kicad = names[number]
        if kicad.startswith("GPIO"):
            kicad = "GP" + re.match(r"GPIO(\d+)", kicad).group(1)
        ours = pad["pinId"]
        if re.fullmatch(r"GND_\d", ours):
            ours = "GND"
        assert ours == kicad, (number, pad["pinId"], names[number])


def test_rpi_pico_declares_every_pad_as_a_pin_and_is_verified() -> None:
    assert {p["pinId"] for p in table("rpi-pico")} <= spec_pin_ids("rpi-pico")
    assert fit("rpi-pico")["status"] == "verified_against"
    assert "RaspberryPi_Pico_Common_THT" in fit("rpi-pico")["verified_against"]


# ---- ESP32 DevKit (Espressif ESP32-DevKitC V4, 38 pins) -------------------------------------------

# Header J2 then J3, top to bottom, as in the Espressif ESP32-DevKitC user guide pin tables. The
# registry calls the board's 5V pad VIN; GND appears once on J2 and twice on J3.
DEVKITC_V4_J2 = ["3V3", "EN", "GPIO36", "GPIO39", "GPIO34", "GPIO35", "GPIO32", "GPIO33", "GPIO25", "GPIO26",
                 "GPIO27", "GPIO14", "GPIO12", "GND", "GPIO13", "GPIO9", "GPIO10", "GPIO11", "VIN"]
DEVKITC_V4_J3 = ["GND_2", "GPIO23", "GPIO22", "GPIO1", "GPIO3", "GPIO21", "GND_3", "GPIO19", "GPIO18", "GPIO5",
                 "GPIO17", "GPIO16", "GPIO4", "GPIO0", "GPIO2", "GPIO15", "GPIO8", "GPIO7", "GPIO6"]


def test_esp32_devkit_is_the_38_pin_devkitc_v4_with_rows_25_4_mm_apart() -> None:
    pads = table("esp32-devkit")
    assert len(pads) == 38 and len({p["pinId"] for p in pads}) == 38
    left = [p for p in pads if p["x"] < 0]
    right = [p for p in pads if p["x"] > 0]
    assert [p["pinId"] for p in left] == DEVKITC_V4_J2
    assert [p["pinId"] for p in right] == DEVKITC_V4_J3
    assert round(right[0]["x"] - left[0]["x"], 3) == 25.4
    for column in (left, right):
        assert len(column) == 19
        assert {round(b["y"] - a["y"], 3) for a, b in zip(column, column[1:])} == {2.54}
    # Pads sit on the board: the envelope holds the 25.4 mm row spacing plus the pad copper.
    body = registry.resolve_module_body_mm("esp32-devkit")
    assert body["w"] >= 25.4 + 1.8 and body["h"] >= 18 * 2.54 + 1.8


def test_esp32_devkit_declares_every_pad_as_a_pin_and_keeps_the_recipe_pins() -> None:
    pad_ids = {p["pinId"] for p in table("esp32-devkit")}
    assert pad_ids <= spec_pin_ids("esp32-devkit")
    assert {"VIN", "3V3", "GND", "GPIO2", "GPIO4", "GPIO5", "GPIO15", "GPIO16", "GPIO17", "GPIO18",
            "GPIO21", "GPIO22", "GPIO23", "GPIO34"} <= pad_ids


def test_esp32_devkit_names_its_variant_and_the_flash_pins_are_not_offered_as_gpio() -> None:
    fit_record = fit("esp32-devkit")
    assert fit_record["status"] == "verified_against"
    assert "DevKitC V4" in fit_record["verified_against"] and "30-pin" in fit_record["verified_against"]
    spec = registry.find_module("esp32-devkit")
    flash = [p for p in spec["pins"] if p["id"] in {"GPIO6", "GPIO7", "GPIO8", "GPIO9", "GPIO10", "GPIO11"}]
    assert len(flash) == 6 and all(p["role"] == "other" and "flash" in p["notes"] for p in flash)


# ---- ESP32-CAM (AI-Thinker) ---------------------------------------------------------------------


def test_esp32_cam_has_both_eight_pin_rows_in_the_ai_thinker_order() -> None:
    pads = table("esp32-cam-module")
    left = [p for p in pads if p["x"] < 0]
    right = [p for p in pads if p["x"] > 0]
    assert [p["pinId"] for p in left] == ["5V", "GND", "GPIO12", "GPIO13", "GPIO15", "GPIO14", "GPIO2", "GPIO4"]
    assert [p["pinId"] for p in right] == ["3V3", "GPIO16", "GPIO0", "GND_2", "VCC", "U0R", "U0T", "GND_3"]
    for column in (left, right):
        assert {round(b["y"] - a["y"], 3) for a, b in zip(column, column[1:])} == {2.54}
    assert {p["pinId"] for p in pads} <= spec_pin_ids("esp32-cam-module")


def test_esp32_cam_is_unverified_because_the_row_spacing_is_not_published() -> None:
    record = fit("esp32-cam-module")
    assert record["status"] == "unverified_variant"
    assert "row" in record["reason"] and "assumed" in record["reason"]


# ---- DC barrel jack -----------------------------------------------------------------------------


@needs_kicad_library
def test_barrel_jack_has_all_three_terminals_at_kicad_geometry() -> None:
    pads = table("dc-barrel-12v")
    assert [p["pinId"] for p in pads] == ["V+", "GND", "SW"]
    offsets = relative_to_kicad("dc-barrel-12v", "Connector_BarrelJack.pretty/BarrelJack_Horizontal.kicad_mod")
    assert len(set(offsets)) == 1
    assert {"V+", "GND", "SW"} <= spec_pin_ids("dc-barrel-12v")


def test_barrel_jack_is_not_claimed_verified_for_the_named_part() -> None:
    record = fit("dc-barrel-12v")
    assert record["status"] == "unverified_variant"
    assert "PJ-002A" in record["reason"] and "slot" in record["reason"]


# ---- 4-channel level shifter --------------------------------------------------------------------


def test_level_shifter_is_a_two_by_six_header_with_every_channel() -> None:
    pads = table("level-shifter-4ch")
    left = [p for p in pads if p["x"] < 0]
    right = [p for p in pads if p["x"] > 0]
    assert [p["pinId"] for p in left] == ["LV1", "LV2", "LV", "GND", "LV3", "LV4"]
    assert [p["pinId"] for p in right] == ["HV1", "HV2", "HV", "GND_2", "HV3", "HV4"]
    for column in (left, right):
        assert {round(b["y"] - a["y"], 3) for a, b in zip(column, column[1:])} == {2.54}
    assert len(pads) == 12 and {p["pinId"] for p in pads} <= spec_pin_ids("level-shifter-4ch")


def test_level_shifter_is_unverified_because_row_spacing_varies_by_vendor() -> None:
    record = fit("level-shifter-4ch")
    assert record["status"] == "unverified_variant"
    assert "differs by vendor" in record["reason"]


# ---- HC-SR04, SG90, DHT22 (maker-documented layouts) ---------------------------------------------


def _single_row(module_id: str) -> List[Tuple[str, float]]:
    pads = table(module_id)
    assert len({p["y"] for p in pads}) == 1, "one in-line header"
    return [(p["pinId"], p["x"]) for p in sorted(pads, key=lambda p: p["x"])]


def test_hc_sr04_is_a_four_pin_header_at_2_54_mm() -> None:
    row = _single_row("hc-sr04")
    assert [name for name, _x in row] == ["VCC", "TRIG", "ECHO", "GND"]
    assert {round(b[1] - a[1], 3) for a, b in zip(row, row[1:])} == {2.54}
    assert fit("hc-sr04")["status"] == "verified_against"
def test_sg90_lead_is_gnd_vcc_sig_with_vcc_in_the_middle() -> None:
    row = _single_row("sg90")
    assert [name for name, _x in row] == ["GND", "VCC", "SIG"]
    assert {round(b[1] - a[1], 3) for a, b in zip(row, row[1:])} == {2.54}
    assert fit("sg90")["status"] == "verified_against"



def test_dht22_bare_part_has_four_pins_with_the_nc_pad_between_data_and_ground() -> None:
    row = _single_row("dht22")
    assert [name for name, _x in row] == ["VCC", "DATA", "NC", "GND"]
    assert {round(b[1] - a[1], 3) for a, b in zip(row, row[1:])} == {2.54}
    assert {"VCC", "DATA", "NC", "GND"} <= spec_pin_ids("dht22")
    assert fit("dht22")["status"] == "verified_against"


# ---- MAX98357A I2S amplifier breakout -----------------------------------------------------------


def test_max98357a_has_the_seven_pin_header_and_a_separate_speaker_pair() -> None:
    pads = table("max98357a-i2s-amp")
    header = sorted((p for p in pads if p["pinId"] not in ("SPK+", "SPK-")), key=lambda p: p["x"])
    assert [p["pinId"] for p in header] == ["LRC", "BCLK", "DIN", "GAIN", "SD", "GND", "VIN"]
    assert len({p["y"] for p in header}) == 1
    assert {round(b["x"] - a["x"], 3) for a, b in zip(header, header[1:])} == {2.54}
    speaker = [p for p in pads if p["pinId"] in ("SPK+", "SPK-")]
    assert len(speaker) == 2 and speaker[0]["y"] != header[0]["y"], "speaker terminal is not on the header row"
    assert {p["pinId"] for p in pads} == spec_pin_ids("max98357a-i2s-amp")


def test_max98357a_stays_unverified_because_the_speaker_terminal_is_assumed() -> None:
    record = fit("max98357a-i2s-amp")
    assert record["status"] == "unverified_variant" and "speaker terminal" in record["reason"]


# ---- A4988 stepper carrier, resistor, terminal blocks -----------------------------------------------


@needs_kicad_library
def test_a4988_footprint_is_the_pololu_carrier_turned_through_180_degrees() -> None:
    kicad = kicad_pads("Module.pretty/Pololu_Breakout-16_15.2x20.3mm.kicad_mod")
    names = kicad_pin_names("Driver_Motor.kicad_sym", "Pololu_Breakout_A4988")
    assert len(kicad) == len(names) == 16
    # Registry ids for KiCad's names; pad 1 is the ground beside VDD, pad 7 the one beside VMOT.
    alias = {"~{ENABLE}": "EN", "~{RESET}": "RST", "~{SLEEP}": "SLP"}
    kicad_cx = (min(x for _n, x, _y in kicad) + max(x for _n, x, _y in kicad)) / 2
    kicad_cy = (min(y for _n, _x, y in kicad) + max(y for _n, _x, y in kicad)) / 2
    ours = {p["pinId"]: (p["x"], p["y"]) for p in table("a4988-stepper")}
    assert len(ours) == 16
    for number, x, y in kicad:
        name = names[number]
        pin = {1: "GND_LOGIC", 7: "GND_MOTOR"}.get(number) or alias.get(name, name)
        # Rotating the board 180 degrees about its centre maps KiCad's pad onto ours.
        expected = (round(-(x - kicad_cx), 3), round(-(y - kicad_cy), 3))
        assert (round(ours[pin][0], 3), round(ours[pin][1], 3)) == expected, (number, name, pin)
    assert fit("a4988-stepper")["status"] == "verified_against"


@needs_kicad_library
def test_resistor_and_terminal_block_pads_match_kicad() -> None:
    for module_id, relative in (
        ("resistor-10r", "Resistor_THT.pretty/R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal.kicad_mod"),
        ("terminal-block-2p", "TerminalBlock.pretty/TerminalBlock_bornier-2_P5.08mm.kicad_mod"),
        ("terminal-block-2p-dc", "TerminalBlock.pretty/TerminalBlock_bornier-2_P5.08mm.kicad_mod"),
        ("terminal-block-4p", "TerminalBlock.pretty/TerminalBlock_bornier-4_P5.08mm.kicad_mod"),
    ):
        assert len(set(relative_to_kicad(module_id, relative))) == 1, module_id


def test_terminal_blocks_are_not_verified_because_kicads_hole_is_larger_than_the_generators() -> None:
    assert fit("resistor-10r")["status"] == "verified_against"
    for module_id in ("terminal-block-2p", "terminal-block-2p-dc", "terminal-block-4p"):
        record = fit(module_id)
        assert record["status"] == "unverified_variant", module_id
        assert "1.52" in record["reason"] and "1.0" in record["reason"]


def test_dht11_uses_the_same_four_pin_layout_as_the_dht22() -> None:
    assert [p["pinId"] for p in table("dht11")] == ["VCC", "DATA", "NC", "GND"]
    assert fit("dht11")["status"] == "verified_against"


# ---- single-row breakouts: no 0.11 inch pitch ---------------------------------------------------


def test_in_line_breakout_headers_use_the_standard_2_54_mm_pitch() -> None:
    """2.794 mm (0.11 in) is not a header pitch; those rows were a scaling slip, not a variant."""
    for module_id in ("st7735_tft", "ds3231_rtc", "sd_card_module"):
        row = _single_row(module_id)
        assert {round(b[1] - a[1], 3) for a, b in zip(row, row[1:])} == {2.54}, module_id
        assert fit(module_id)["status"] == "unverified_variant", "row order and variant remain unchecked"
