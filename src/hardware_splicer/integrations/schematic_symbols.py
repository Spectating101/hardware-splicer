"""Embedded + module-aware schematic symbol selection."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..pcb.module_registry import find_module, resolve_module_footprint

# module_id → (embedded lib_id, ref prefix)
MODULE_SYMBOLS: Dict[str, Tuple[str, str]] = {
    "usb-power-5v": ("HS:PowerIn", "J"),
    "dc-barrel-12v": ("HS:PowerIn", "J"),
    "esp32-devkit": ("HS:MCU", "U"),
    "arduino-nano": ("HS:MCU", "U"),
    "rpi-pico": ("HS:MCU", "U"),
    "dht22": ("HS:Sensor", "U"),
    "bme280": ("HS:Sensor", "U"),
    "soil_moisture": ("HS:Sensor", "U"),
    "hc-sr04": ("HS:Sensor", "U"),
    "relay-1ch-5v": ("HS:Actuator", "K"),
    "level-shifter-4ch": ("HS:Support", "U"),
    "ldo-ams1117-3v3": ("HS:Support", "U"),
    "ldo-ams1117-5v": ("HS:Support", "U"),
    "buck-mp1584": ("HS:Support", "U"),
    "buck-lm2596": ("HS:Support", "U"),
    "mosfet-irlz44n": ("HS:Transistor", "Q"),
    "mosfet-irf520": ("HS:Transistor", "Q"),
    "l298n": ("HS:Driver", "U"),
    "sg90": ("HS:Actuator", "M"),
    "ssd1306-128x64": ("HS:Display", "U"),
    "ch340-usb-ttl": ("HS:Support", "U"),
    "mini-pump-5v": ("HS:Actuator", "M"),
    "a4988-stepper": ("HS:Driver", "U"),
    "max98357a-i2s-amp": ("HS:Driver", "U"),
    "limit-switch-3pin": ("HS:Sensor", "SW"),
    "esp32-cam-module": ("HS:MCU", "U"),
    "tp4056": ("HS:Support", "U"),
    "resistor-10k": ("Device:R", "R"),
}

EMBEDDED_LIB_IDS = {
    "Connector:Conn_01x01",
    "Device:R",
    "Device:C",
    "HS:ModuleBlock",
    "HS:MCU",
    "HS:Sensor",
    "HS:PowerIn",
    "HS:Support",
    "HS:Actuator",
    "HS:Driver",
    "HS:Display",
    "HS:Transistor",
}


def schematic_symbol_for_module(module_id: Optional[str], *, ref: str, value: str = "") -> Tuple[str, str, str]:
    """Return (embedded lib_id, ref_prefix, footprint)."""
    mid = str(module_id or "").strip()
    spec = find_module(mid) if mid else None
    label = value or (spec.get("label") if spec else "") or mid or ref

    if mid in MODULE_SYMBOLS:
        lib_id, prefix = MODULE_SYMBOLS[mid]
        return lib_id, prefix, resolve_module_footprint(mid) or ""

    if ref.upper().startswith("R"):
        return "Device:R", "R", resolve_module_footprint(mid) or ""
    if ref.upper().startswith("C"):
        return "Device:C", "C", resolve_module_footprint(mid) or ""
    if ref.upper().startswith("J"):
        return "HS:PowerIn", "J", resolve_module_footprint(mid) or ""
    if ref.upper().startswith("K"):
        return "HS:Actuator", "K", resolve_module_footprint(mid) or ""
    if ref.upper().startswith("Q"):
        return "HS:Transistor", "Q", resolve_module_footprint(mid) or ""
    if ref.upper().startswith("M"):
        return "HS:Actuator", "M", resolve_module_footprint(mid) or ""
    return "HS:ModuleBlock", "U", resolve_module_footprint(mid) or mid


def embedded_schematic_lib_symbols() -> List[str]:
    """Lib symbol bodies embedded in exported .kicad_sch (no external libs required)."""
    return [
        '    (symbol "Connector:Conn_01x01" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)',
        '      (property "Reference" "J" (at 0 2.54 0) (effects (font (size 1.27 1.27))))',
        '      (property "Value" "Conn_01x01" (at 0 -2.54 0) (effects (font (size 1.27 1.27))))',
        '      (symbol "Conn_01x01_0_1"',
        '        (pin passive line (at 0 0 0) (length 2.54) (name "Pin_1" (effects (font (size 1.27 1.27)))) (number "1"))',
        "      )",
        "    )",
        '    (symbol "Device:R" (pin_names (offset 0)) (in_bom yes) (on_board yes)',
        '      (property "Reference" "R" (at 0 2.54 0) (effects (font (size 1.27 1.27))))',
        '      (property "Value" "R" (at 0 -2.54 0) (effects (font (size 1.27 1.27))))',
        '      (symbol "R_0_1"',
        '        (pin passive line (at 0 2.54 0) (length 2.54) (name "~" (effects (font (size 1.27 1.27)))) (number "1"))',
        '        (pin passive line (at 0 -2.54 0) (length 2.54) (name "~" (effects (font (size 1.27 1.27)))) (number "2"))',
        "      )",
        "    )",
        '    (symbol "Device:C" (pin_names (offset 0)) (in_bom yes) (on_board yes)',
        '      (property "Reference" "C" (at 0 2.54 0) (effects (font (size 1.27 1.27))))',
        '      (property "Value" "C" (at 0 -2.54 0) (effects (font (size 1.27 1.27))))',
        '      (symbol "C_0_1"',
        '        (pin passive line (at 0 2.54 0) (length 2.54) (name "~" (effects (font (size 1.27 1.27)))) (number "1"))',
        '        (pin passive line (at 0 -2.54 0) (length 2.54) (name "~" (effects (font (size 1.27 1.27)))) (number "2"))',
        "      )",
        "    )",
        *_hs_block_symbol("HS:ModuleBlock", "MOD"),
        *_hs_block_symbol("HS:MCU", "MCU"),
        *_hs_block_symbol("HS:Sensor", "SNS"),
        *_hs_block_symbol("HS:PowerIn", "PWR"),
        *_hs_block_symbol("HS:Support", "SUP"),
        *_hs_block_symbol("HS:Actuator", "ACT"),
        *_hs_block_symbol("HS:Driver", "DRV"),
        *_hs_block_symbol("HS:Display", "DSP"),
        *_hs_block_symbol("HS:Transistor", "FET"),
    ]


def _hs_block_symbol(lib_id: str, default_value: str) -> List[str]:
    name = lib_id.split(":", 1)[1]
    return [
        f'    (symbol "{lib_id}" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)',
        f'      (property "Reference" "U" (at 0 5.08 0) (effects (font (size 1.27 1.27))))',
        f'      (property "Value" "{default_value}" (at 0 -5.08 0) (effects (font (size 1.27 1.27))))',
        f'      (symbol "{name}_0_1"',
        '        (rectangle (start -5.08 3.81) (end 5.08 -3.81) (stroke (width 0.254) (type default)) (fill (type background)))',
        '        (pin passive line (at -7.62 2.54 0) (length 2.54) (name "A" (effects (font (size 1.27 1.27)))) (number "1"))',
        '        (pin passive line (at -7.62 -2.54 0) (length 2.54) (name "B" (effects (font (size 1.27 1.27)))) (number "2"))',
        "      )",
        "    )",
    ]
