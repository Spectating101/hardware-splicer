"""Module registry: loads engine_pcb_data.json and exposes lookup helpers
that mirror the TypeScript module-library + module-footprints functions."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).parent.parent / "data" / "engine_pcb_data.json"

# ---------------------------------------------------------------------------
# Types (plain dicts, matching TS ModuleSpec / ModulePadDef shapes)
# ---------------------------------------------------------------------------
# ModuleSpec  -> {"id", "label", "category", "pins": [{"id","label","role","voltage",...}], ...}
# ModulePadDef -> {"pinId", "x", "y"}

_P = 2.54  # standard pitch mm

# ---------------------------------------------------------------------------
# Hard-coded footprint table (mirrors module-footprints.ts MODULE_FOOTPRINTS)
# ---------------------------------------------------------------------------

def _dual_col(
    left: list[str], right: list[str], x_span: float = _P * 4
) -> list[dict]:
    rows = max(len(left), len(right))
    y0 = -((rows - 1) * _P) / 2
    x_l = -x_span / 2
    x_r = x_span / 2
    pads: list[dict] = []
    for i, pin_id in enumerate(left):
        pads.append({"pinId": pin_id, "x": x_l, "y": y0 + i * _P})
    for i, pin_id in enumerate(right):
        pads.append({"pinId": pin_id, "x": x_r, "y": y0 + i * _P})
    return pads


def _row(
    pin_ids: list[str], y: float = 0, x0: float = 0, pitch: float = _P
) -> list[dict]:
    span = (len(pin_ids) - 1) * pitch
    start = x0 - span / 2
    return [{"pinId": pid, "x": start + i * pitch, "y": y} for i, pid in enumerate(pin_ids)]


def _quad(
    in_pos: tuple[str, str],
    out_pos: tuple[str, str],
    hw: float = 5,
    hh: float = 3,
) -> list[dict]:
    return [
        {"pinId": in_pos[0],  "x": -hw, "y": -hh},
        {"pinId": in_pos[1],  "x": -hw, "y":  hh},
        {"pinId": out_pos[0], "x":  hw, "y": -hh},
        {"pinId": out_pos[1], "x":  hw, "y":  hh},
    ]


_MODULE_FOOTPRINTS: dict[str, dict] = {
    "dc-barrel-12v": {
        "kicadFootprint": "Connector:BarrelJack_CUI_PJ-002A",
        "bodyMm": {"w": 10, "h": 10},
        "pads": _row(["V+", "GND"], 0, 0, 3.5),
    },
    "usb-power-5v": {
        "kicadFootprint": "Connector:USB-MICRO-POWER",
        "bodyMm": {"w": 8, "h": 7},
        "pads": _row(["V+", "GND"], -2, 0, 2.5),
    },
    "esp32-devkit": {
        "kicadFootprint": "Module:ESP32-WROOM-32",
        "bodyMm": {"w": 26, "h": 50},
        "pads": _dual_col(
            ["VIN", "GND", "GPIO4", "GPIO16", "GPIO17"],
            ["3V3", "GPIO2", "GPIO21", "GPIO22", "GPIO34"],
            _P * 5,
        ),
    },
    "arduino-nano": {
        "kicadFootprint": "Module:Arduino_Nano",
        "bodyMm": {"w": 18, "h": 45},
        "pads": _dual_col(
            ["VIN", "GND", "D2", "D3", "A0"],
            ["5V", "3V3", "A4", "A5"],
            _P * 7,
        ),
    },
    "rpi-pico": {
        "kicadFootprint": "Module:RPi_Pico",
        "bodyMm": {"w": 21, "h": 51},
        "pads": _dual_col(
            ["VSYS", "GND", "GP0", "GP4", "GP26"],
            ["VBUS", "3V3", "GP1", "GP5"],
            _P * 10,
        ),
    },
    "soil_moisture": {
        "kicadFootprint": "Sensor:SOIL-MOISTURE-3PIN",
        "bodyMm": {"w": 20, "h": 12},
        "pads": _row(["VCC", "GND", "A0", "D0"], 4, 0, _P),
    },
    "bme280": {
        "kicadFootprint": "Sensor:BME280-BREAKOUT",
        "bodyMm": {"w": 12, "h": 10},
        "pads": _row(["VCC", "GND", "SCL", "SDA"], 0, 0, _P),
    },
    "dht22": {
        "kicadFootprint": "Sensor:DHT22-4PIN",
        "bodyMm": {"w": 15, "h": 12},
        "pads": _row(["VCC", "DATA", "NC", "GND"], 0, 0, _P),
    },
    "hc-sr04": {
        "kicadFootprint": "Sensor:HC-SR04",
        "bodyMm": {"w": 45, "h": 20},
        "pads": _row(["VCC", "TRIG", "ECHO", "GND"], 0, 0, _P * 2),
    },
    "buck-mp1584": {
        "kicadFootprint": "Power:BUCK-MP1584-MODULE",
        "bodyMm": {"w": 17, "h": 11},
        "pads": _quad(("IN+", "IN-"), ("OUT+", "OUT-"), 6, 3.5),
    },
    "buck-lm2596": {
        "kicadFootprint": "Power:BUCK-LM2596-MODULE",
        "bodyMm": {"w": 43, "h": 21},
        "pads": _quad(("IN+", "IN-"), ("OUT+", "OUT-"), 14, 6),
    },
    "ldo-ams1117-3v3": {
        "kicadFootprint": "Power:AMS1117-3V3-MODULE",
        "bodyMm": {"w": 12, "h": 10},
        "pads": _row(["VIN", "GND", "VOUT"], 0, 0, _P),
    },
    "ldo-ams1117-5v": {
        "kicadFootprint": "Power:AMS1117-5V-MODULE",
        "bodyMm": {"w": 12, "h": 10},
        "pads": _row(["VIN", "GND", "VOUT"], 0, 0, _P),
    },
    "tp4056": {
        "kicadFootprint": "Power:TP4056-CHARGER",
        "bodyMm": {"w": 27, "h": 17},
        "pads": (
            _row(["IN+", "IN-"], -5, -6, _P * 2)
            + _row(["BAT+", "BAT-"], 5, -6, _P * 2)
            + _row(["OUT+", "OUT-"], 0, 6, _P * 2)
        ),
    },
    "mosfet-irlz44n": {
        "kicadFootprint": "Driver:MOSFET-LOGIC-MODULE",
        "bodyMm": {"w": 33, "h": 24},
        "pads": [
            {"pinId": "VIN",   "x": -11, "y": -7},
            {"pinId": "VIN-",  "x": -11, "y":  7},
            {"pinId": "SIG",   "x":  -2, "y":  7},
            {"pinId": "GND",   "x":  -2, "y": -7},
            {"pinId": "VOUT+", "x":  11, "y": -7},
            {"pinId": "VOUT-", "x":  11, "y":  7},
        ],
    },
    "mosfet-irf520": {
        "kicadFootprint": "Driver:MOSFET-IRF520-MODULE",
        "bodyMm": {"w": 33, "h": 24},
        "pads": [
            {"pinId": "VIN",   "x": -11, "y": -7},
            {"pinId": "VIN-",  "x": -11, "y":  7},
            {"pinId": "SIG",   "x":  -2, "y":  7},
            {"pinId": "GND",   "x":  -2, "y": -7},
            {"pinId": "VOUT+", "x":  11, "y": -7},
            {"pinId": "VOUT-", "x":  11, "y":  7},
        ],
    },
    "relay-1ch-5v": {
        "kicadFootprint": "Driver:RELAY-1CH-5V",
        "bodyMm": {"w": 50, "h": 26},
        "pads": (
            _row(["VCC", "GND", "IN"], -6, -8, _P)
            + _row(["COM", "NO", "NC"], 6, 8, _P)
        ),
    },
    "l298n": {
        "kicadFootprint": "Driver:L298N-HBRIDGE",
        "bodyMm": {"w": 43, "h": 37},
        "pads": [
            {"pinId": "VCC",  "x": -14, "y": -10},
            {"pinId": "GND",  "x": -14, "y":  10},
            {"pinId": "5V",   "x":  -5, "y": -10},
            {"pinId": "IN1",  "x":  -5, "y":   0},
            {"pinId": "IN2",  "x":  -5, "y":  10},
            {"pinId": "OUT1", "x":  14, "y":  -6},
            {"pinId": "OUT2", "x":  14, "y":   6},
        ],
    },
    "sg90": {
        "kicadFootprint": "Actuator:SG90-SERVO",
        "bodyMm": {"w": 23, "h": 12},
        "pads": _row(["VCC", "GND", "SIG"], -8, 0, _P),
    },
    "ssd1306-128x64": {
        "kicadFootprint": "Display:SSD1306-OLED",
        "bodyMm": {"w": 27, "h": 27},
        "pads": _row(["VCC", "GND", "SCL", "SDA"], 10, 0, _P),
    },
    "ch340-usb-ttl": {
        "kicadFootprint": "Interface:USB-TTL-CH340",
        "bodyMm": {"w": 17, "h": 32},
        "pads": _row(["VCC", "GND", "TX", "RX"], 0, 0, _P),
    },
    "mini-pump-5v": {
        "kicadFootprint": "Actuator:PUMP-5V-MINI",
        "bodyMm": {"w": 24, "h": 18},
        "pads": _row(["V+", "GND"], 0, 0, _P * 2),
    },
    "level-shifter-4ch": {
        "kicadFootprint": "Interface:LEVEL-SHIFTER-4CH",
        "bodyMm": {"w": 15, "h": 12},
        "pads": _row(["LV", "HV", "GND", "LV1", "HV1", "LV2", "HV2"], 0, 0, _P),
    },
    "a4988-stepper": {
        "kicadFootprint": "Driver:A4988-STEPSTICK",
        "bodyMm": {"w": 20, "h": 15},
        "pads": _row(
            ["VDD", "GND_LOGIC", "STEP", "DIR", "EN", "VMOT", "GND_MOTOR"],
            0, 0, _P * 1.4,
        ),
    },
    "max98357a-i2s-amp": {
        "kicadFootprint": "Driver:MAX98357A-I2S",
        "bodyMm": {"w": 18, "h": 12},
        "pads": _row(
            ["VIN", "GND", "BCLK", "LRC", "DIN", "SD", "SPK+", "SPK-"],
            0, 0, _P,
        ),
    },
    "limit-switch-3pin": {
        "kicadFootprint": "Sensor:LIMIT-SWITCH-3PIN",
        "bodyMm": {"w": 20, "h": 10},
        "pads": _row(["VCC", "GND", "SIG"], 0, 0, _P),
    },
    "esp32-cam-module": {
        "kicadFootprint": "Module:ESP32-CAM",
        "bodyMm": {"w": 27, "h": 40},
        "pads": _row(["5V", "GND", "U0T", "U0R", "GPIO4"], -6, 0, _P),
    },
}

# ---------------------------------------------------------------------------
# Module library cache (loaded from engine_pcb_data.json)
# ---------------------------------------------------------------------------

_MODULE_LIBRARY: Optional[dict[str, dict]] = None


def _load_library() -> dict[str, dict]:
    global _MODULE_LIBRARY
    if _MODULE_LIBRARY is not None:
        return _MODULE_LIBRARY
    with open(_DATA_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    _MODULE_LIBRARY = {m["id"]: m for m in data.get("module_library", [])}
    return _MODULE_LIBRARY


# ---------------------------------------------------------------------------
# Public API (mirrors TS helpers)
# ---------------------------------------------------------------------------

def find_module(module_id: str) -> Optional[dict]:
    """Return ModuleSpec dict for module_id, or None."""
    return _load_library().get(module_id)


def find_modules_by_capabilities(requires_any: list[list[str]]) -> list[dict]:
    """Return modules whose capabilityTags satisfy every OR-group in requires_any."""
    out: list[dict] = []
    for module in _load_library().values():
        tags = set(module.get("capabilityTags") or [])
        if all(any(cap in tags for cap in alt) for alt in requires_any):
            out.append(module)
    return out


def find_pin(module: dict, pin_id: str) -> Optional[dict]:
    """Return pin dict for pin_id on module, or None."""
    for pin in module.get("pins") or []:
        if pin.get("id") == pin_id:
            return pin
    return None


def resolve_module_footprint(module_id: str) -> str:
    """Return KiCad footprint string."""
    meta = _MODULE_FOOTPRINTS.get(module_id)
    if meta:
        return meta["kicadFootprint"]
    return f"Circuit.AI:{module_id}"


def resolve_module_body_mm(module_id: str) -> Optional[dict]:
    """Return {w, h} body envelope in mm, or None."""
    meta = _MODULE_FOOTPRINTS.get(module_id)
    if meta:
        return meta.get("bodyMm")
    return None


def resolve_module_pads(module_id: str, spec: Optional[dict] = None) -> Optional[list[dict]]:
    """Return list of {pinId, x, y} pad defs (local mm from center), or None.

    Mirrors resolveModulePads from module-footprints.ts: custom table first,
    then synthetic dual-column fallback when spec.pins is available.
    """
    meta = _MODULE_FOOTPRINTS.get(module_id)
    if meta:
        custom = meta.get("pads")
        if custom:
            return list(custom)
    if not spec or not spec.get("pins"):
        return None
    pins = spec["pins"]
    half = math.ceil(len(pins) / 2)
    return _dual_col(
        [p["id"] for p in pins[:half]],
        [p["id"] for p in pins[half:]],
    )


def bounds_from_pads(pads: list[dict], margin: float = 3) -> dict:
    """Return {w, h} bounding box of pad positions plus margin."""
    if not pads:
        return {"w": 10, "h": 10}
    xs = [p["x"] for p in pads]
    ys = [p["y"] for p in pads]
    w = max(max(xs) - min(xs) + margin * 2, 8)
    h = max(max(ys) - min(ys) + margin * 2, 8)
    return {"w": w, "h": h}
