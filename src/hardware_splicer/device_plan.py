"""An assembly plan for a whole gadget: modules, the wires between them, and a case to hold them.

The input is a small device spec (which modules, which pin goes to which). The output is where everything sits, the wires
drawn pin to pin, wiring findings, and ordered steps a person can follow. It is built from the module library
(``data/device_modules.json``), where every figure names its source or says it is typical.

It is a proposal and a checklist. It carries no engineering authority and approves nothing: a wire that passes these checks
is not a wire that works, a case drawn here has not been printed, and every "check" is something to try, not a result.
"""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

from .text_safety import finite_number, has_hidden_characters
from typing import Any

DEVICE_PLAN_SCHEMA = "hardware_splicer.device_plan.v1"
DEVICE_SPEC_SCHEMA = "hardware_splicer.device_spec.v1"
LIBRARY_PATH = Path(__file__).resolve().parent / "data" / "device_modules.json"

MAX_MODULES = 8
MAX_CONNECTIONS = 64
MAX_NAME = 80

AUTHORITY_STATEMENT = (
    "This is a proposal and a checklist. A wire that passes these checks is not a wire that works, the case has not been "
    "printed, and every check is something to try, not a result. Nothing here approves building, powering or releasing a device."
)

# Conventional jumper-wire sizes and housings; typical, not measured. They size the case and the shopping list.
WIRE_LENGTHS_MM = (100, 150, 200, 300)
WIRE_CONNECTOR_HEIGHT_MM = 14.0
WIRE_BEND_ALLOWANCE_MM = 10.0   # room above the tallest connector for a jumper to curve
PIN_TIP_ABOVE_BOARD_MM = 3.0
PLUG_CUTOUT_MM = (14.0, 8.0)   # a Micro-USB plug's moulded body is much bigger than the socket
WINDOW_MARGIN_MM = 1.5
# Board stops: low blocks on the case floor just beyond the last header pin of each row, so a plug pushed into the board is taken by
# the pins and not by the antenna end. Sizes are typical choices, not measurements.
PIN_SQUARE_MM = 0.64
STOP_GAP_MM = 0.5
STOP_THICKNESS_MM = 2.0
STOP_HEIGHT_MM = 3.0
WIRE_COLORS = {"red", "black", "yellow", "green", "blue", "white", "orange"}
_SLUG = re.compile(r"^[a-z][a-z0-9_]{0,23}$")
_OVERRIDE_KEYS = {"pcb_mm": {"x", "y", "z"}, "above_board_mm": None}
_MODULE_KINDS = {"mcu_board", "display", "i2c_breakout"}


class DevicePlanError(ValueError):
    """The spec is not something a plan can be made from."""


# --- library --------------------------------------------------------------------------------------------------------------



def _text_field(value: Any, label: str, limit: int = 600) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or has_hidden_characters(value):
        raise RuntimeError(f"{label} must be text of 1 to {limit} characters without control or invisible characters")


def _number_field(value: Any, label: str, *, positive: bool = False) -> float:
    number = finite_number(value)
    if number is None or isinstance(value, bool) or number < 0 or (positive and number <= 0):
        raise RuntimeError(f"{label} must be a finite number{' above zero' if positive else ' of zero or more'}")
    return number


def _check_engineering(module: dict[str, Any], source_urls: list[str]) -> None:
    """The figures the engineering review reads. Each carries its locator and a source that is one of the module's own."""

    label = f"module {module['id']}"
    extra = module.get("engineering_sources", [])
    if not isinstance(extra, list) or not all(isinstance(s, dict) and isinstance(s.get("url"), str) and isinstance(s.get("label"), str) for s in extra):
        raise RuntimeError(f"{label} engineering_sources must be a list of objects with a label and a url")
    # Sources the engineering figures cite beyond those the plan shows; kept apart so that adding a figure never changes a plan.
    source_urls = list(source_urls) + [s["url"] for s in extra]
    pullups = module.get("i2c", {}).get("pullups")
    if pullups is not None:
        if not isinstance(pullups, dict) or set(pullups) != {"ohm", "rail", "quote", "source"}:
            raise RuntimeError(f"{label} i2c.pullups must have exactly ohm, rail, quote and source")
        _number_field(pullups["ohm"], f"{label} i2c.pullups.ohm", positive=True)
        if pullups["rail"] not in (None, "vin"):
            raise RuntimeError(f"{label} i2c.pullups.rail must be null or \"vin\"")
        _text_field(pullups["quote"], f"{label} i2c.pullups.quote")
        if pullups["source"] not in source_urls:
            raise RuntimeError(f"{label} i2c.pullups.source must equal one of this module's source urls")
    engineering = module.get("engineering")
    if engineering is None:
        return
    allowed = {"operating_temp_c", "supply_min_a", "loads", "antenna", "temperature_sensing", "power_stage", "gaps"}
    if not isinstance(engineering, dict) or not set(engineering) <= allowed:
        raise RuntimeError(f"{label} engineering may hold only {', '.join(sorted(allowed))}")

    def cited(row: Any, name: str, fields: set[str]) -> dict[str, Any]:
        if not isinstance(row, dict) or set(row) != fields:
            raise RuntimeError(f"{label} engineering.{name} must have exactly {', '.join(sorted(fields))}")
        _text_field(row["locator"], f"{label} engineering.{name}.locator")
        if row["source"] not in source_urls:
            raise RuntimeError(f"{label} engineering.{name}.source must equal one of this module's source urls")
        return row

    if "operating_temp_c" in engineering:
        row = cited(engineering["operating_temp_c"], "operating_temp_c", {"min", "max", "kind", "locator", "source"})
        low, high = finite_number(row["min"]), finite_number(row["max"])
        if low is None or high is None or isinstance(row["min"], bool) or isinstance(row["max"], bool) or not -273 < low < high < 1000:
            raise RuntimeError(f"{label} engineering.operating_temp_c needs a finite min below max")
        if row["kind"] not in {"recommended", "absolute_maximum"}:
            raise RuntimeError(f"{label} engineering.operating_temp_c.kind must be recommended or absolute_maximum")
    if "supply_min_a" in engineering:
        row = cited(engineering["supply_min_a"], "supply_min_a", {"value", "locator", "source"})
        _number_field(row["value"], f"{label} engineering.supply_min_a.value", positive=True)
    if "power_stage" in engineering:
        row = cited(engineering["power_stage"], "power_stage", {"kind", "note", "locator", "source"})
        if row["kind"] not in {"linear", "switching"}:
            raise RuntimeError(f"{label} engineering.power_stage.kind must be linear or switching")
        _text_field(row["note"], f"{label} engineering.power_stage.note")
    if "antenna" in engineering:
        row = cited(engineering["antenna"], "antenna", {"clearance_mm", "end", "quote", "locator", "source"})
        _number_field(row["clearance_mm"], f"{label} engineering.antenna.clearance_mm", positive=True)
        _text_field(row["quote"], f"{label} engineering.antenna.quote")
        if row["end"] not in module.get("overhang_mm", {}):
            raise RuntimeError(f"{label} engineering.antenna.end must name one of the module's overhang_mm keys")
    if "temperature_sensing" in engineering:
        row = cited(engineering["temperature_sensing"], "temperature_sensing", {"quote", "locator", "source"})
        _text_field(row["quote"], f"{label} engineering.temperature_sensing.quote")
    loads = engineering.get("loads", [])
    if not isinstance(loads, list) or len(loads) > 12:
        raise RuntimeError(f"{label} engineering.loads must be a list of at most 12 rows")
    for index, row in enumerate(loads):
        fields = {"mode", "kind", "typical_ma", "rail_v", "conditions", "locator", "source"} | ({"max_ma"} if isinstance(row, dict) and "max_ma" in row else set())
        row = cited(row, f"loads[{index}]", fields)
        _text_field(row["mode"], f"{label} engineering.loads[{index}].mode")
        _text_field(row["conditions"], f"{label} engineering.loads[{index}].conditions")
        if row["kind"] not in {"sustained", "peak"}:
            raise RuntimeError(f"{label} engineering.loads[{index}].kind must be sustained or peak")
        typical = _number_field(row["typical_ma"], f"{label} engineering.loads[{index}].typical_ma")
        _number_field(row["rail_v"], f"{label} engineering.loads[{index}].rail_v", positive=True)
        if "max_ma" in row and _number_field(row["max_ma"], f"{label} engineering.loads[{index}].max_ma") < typical:
            raise RuntimeError(f"{label} engineering.loads[{index}].max_ma may not be below typical_ma")
    gaps = engineering.get("gaps", [])
    if not isinstance(gaps, list) or not all(isinstance(g, dict) and set(g) == {"field", "reason"} for g in gaps):
        raise RuntimeError(f"{label} engineering.gaps must be a list of objects with field and reason")
    for index, gap in enumerate(gaps):
        _text_field(gap["field"], f"{label} engineering.gaps[{index}].field", 80)
        _text_field(gap["reason"], f"{label} engineering.gaps[{index}].reason")


_CONTROLLER_TEXT = (
    "short_name", "datasheet_basis", "header_types_basis", "input_high_note", "input_high_basis", "i2c_default_owner",
    "i2c_defaults_basis", "i2c_remap_note", "supply_options_note", "supply_options_basis", "supply_current_basis",
    "supply_check_step", "supply_power_step", "supply_current_note", "supply_current_source", "supply_current_practice",
)


def _check_controller(module: dict[str, Any]) -> None:
    """A microcontroller board carries the wording and sources the planner quotes, so no board's text lives in code."""

    if module.get("kind") != "mcu_board":
        return
    label = f"module {module['id']}"
    electrical = module.get("electrical", {})
    for key in _CONTROLLER_TEXT:
        _text_field(electrical.get(key), f"{label} electrical.{key}", 800)
    _text_field(module.get("pin_numbering_from"), f"{label} pin_numbering_from", 80)
    mux = electrical.get("i2c_pin_mux")
    if mux not in {"any", "fixed"}:
        raise RuntimeError(f"{label} electrical.i2c_pin_mux must be any or fixed")
    if mux == "fixed":
        _text_field(electrical.get("i2c_pin_note"), f"{label} electrical.i2c_pin_note", 800)
        for pin in module["pins"]:
            capable = {"i2c_sda_capable", "i2c_scl_capable"} & set(pin["roles"])
            if capable and not isinstance(pin.get("i2c_controller"), int):
                raise RuntimeError(f"{label} pin {pin['id']} is I2C-capable and needs an i2c_controller index")

@lru_cache(maxsize=1)
def _library() -> dict[str, Any]:
    data = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    ids = [module["id"] for module in data["modules"]]
    if len(ids) != len(set(ids)):
        raise RuntimeError("device module library has duplicate ids")
    for module in data["modules"]:
        names = [pin["id"] for pin in module["pins"]]
        if len(names) != len(set(names)):
            raise RuntimeError(f"module {module['id']} has duplicate pin ids")
        if not module.get("sources"):
            raise RuntimeError(f"module {module['id']} names no source")
        chips = module.get("chips", [])
        label = f"module {module['id']} chips"
        if not isinstance(chips, list) or len(chips) > 8:
            raise RuntimeError(f"{label} must be a list of at most 8 entries")
        sources = module["sources"]
        if not isinstance(sources, list) or not all(isinstance(s, dict) and isinstance(s.get("url"), str) for s in sources):
            raise RuntimeError(f"module {module['id']} sources must be a list of objects with a url")
        source_urls = [source["url"] for source in sources]
        orders = module.get("pin_orders", [])
        order_ids = []
        for order in orders:
            if not isinstance(order, dict) or not all(isinstance(order.get(key), str) and order[key].strip() and not has_hidden_characters(order[key]) for key in ("id", "label", "source")):
                raise RuntimeError(f"module {module['id']} pin_orders need text ids, labels and sources")
            signals = order.get("signals")
            if not isinstance(signals, list) or not all(isinstance(signal, str) for signal in signals) or len(signals) != len(names) or set(signals) != {pin["name"] for pin in module["pins"]}:
                raise RuntimeError(f"module {module['id']} pin_orders must list every pin signal once")
            if order["source"] not in source_urls:
                raise RuntimeError(f"module {module['id']} pin_order source must equal one of this module's source urls")
            order_ids.append(order["id"])
        if orders and (len(set(order_ids)) != len(order_ids) or module.get("default_pin_order") not in order_ids or len(module.get("header_positions", [])) != len(names)):
            raise RuntimeError(f"module {module['id']} needs unique pin order ids, a valid default and one header position per pin")
        for index, chip in enumerate(chips):
            if not isinstance(chip, dict):
                raise RuntimeError(f"{label}[{index}] must be an object")
            if set(chip) != {"marking", "role", "source"}:
                raise RuntimeError(f"{label}[{index}] must have exactly marking, role and source: a chip carries no pins or electrical claims here")
            for field, limit in (("marking", 40), ("role", 80), ("source", 2048)):
                value = chip.get(field)
                if not isinstance(value, str) or not value.strip() or len(value) > limit:
                    raise RuntimeError(f"{label}[{index}].{field} must be text of 1 to {limit} characters")
                if has_hidden_characters(value):
                    raise RuntimeError(f"{label}[{index}].{field} may not contain control or invisible characters")
            if chip["source"] not in source_urls:
                raise RuntimeError(f"{label}[{index}].source must equal one of this module's source urls")
        quotes = module.get("quotes", [])
        quote_label = f"module {module['id']} quotes"
        if not isinstance(quotes, list):
            raise RuntimeError(f"{quote_label} must be a list")
        for index, quote in enumerate(quotes):
            if not isinstance(quote, dict):
                raise RuntimeError(f"{quote_label}[{index}] must be an object")
            if set(quote) != {"claim", "quote", "source"}:
                raise RuntimeError(f"{quote_label}[{index}] must have exactly claim, quote and source")
            for field in ("claim", "quote", "source"):
                value = quote.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise RuntimeError(f"{quote_label}[{index}].{field} must be non-empty text")
                if has_hidden_characters(value):
                    raise RuntimeError(f"{quote_label}[{index}].{field} may not contain control or invisible characters")
            if quote["source"] not in source_urls:
                raise RuntimeError(f"{quote_label}[{index}].source must equal one of this module's source urls")
        _check_engineering(module, source_urls)
        _check_controller(module)
    return data


def module_library() -> dict[str, Any]:
    """The module library as published: sources, dimension basis, pins and optional chip roles."""

    return json.loads(json.dumps(_library()))


def _module(module_id: str) -> dict[str, Any]:
    for module in _library()["modules"]:
        if module["id"] == module_id:
            return module
    raise DevicePlanError(f"unknown module {module_id!r}; known: {', '.join(m['id'] for m in _library()['modules'])}")


# --- examples -------------------------------------------------------------------------------------------------------------

EXAMPLES: dict[str, dict[str, Any]] = {
    "esp32_oled_usb": {
        "schema_version": DEVICE_SPEC_SCHEMA,
        "name": "ESP32 with an OLED display, powered over USB",
        "power": {"source": "usb"},
        "modules": [
            {"id": "mcu", "module": "esp32-devkitc-v4"},
            {"id": "display", "module": "ssd1306-096-i2c"},
        ],
        "connections": [
            {"from": "display.VCC", "to": "mcu.3V3"},
            {"from": "display.GND", "to": "mcu.GND"},
            {"from": "display.SCL", "to": "mcu.IO22"},
            {"from": "display.SDA", "to": "mcu.IO21"},
        ],
        "case": {"wall_mm": 2.0, "clearance_mm": 1.0},
    },
    "esp32_oled_bme280_usb": {
        "schema_version": DEVICE_SPEC_SCHEMA,
        "name": "ESP32 with an OLED display and a BME280, powered over USB",
        "power": {"source": "usb"},
        "modules": [
            {"id": "mcu", "module": "esp32-devkitc-v4"},
            {"id": "display", "module": "ssd1306-096-i2c"},
            {"id": "sensor", "module": "adafruit-bme280-stemma-qt"},
        ],
        "connections": [
            {"from": "display.VCC", "to": "mcu.3V3"},
            {"from": "display.GND", "to": "mcu.GND"},
            {"from": "display.SCL", "to": "mcu.IO22"},
            {"from": "display.SDA", "to": "mcu.IO21"},
            {"from": "sensor.Vin", "to": "mcu.3V3"},
            {"from": "sensor.GND", "to": "mcu.GND"},
            {"from": "sensor.SCK", "to": "mcu.IO22"},
            {"from": "sensor.SDI", "to": "mcu.IO21"},
        ],
        "case": {"wall_mm": 2.0, "clearance_mm": 1.0},
    },
    "pico_oled_usb": {
        "schema_version": DEVICE_SPEC_SCHEMA,
        "name": "Raspberry Pi Pico with an OLED display, powered over USB",
        "power": {"source": "usb"},
        "modules": [
            {"id": "mcu", "module": "raspberry-pi-pico"},
            {"id": "display", "module": "ssd1306-096-i2c"},
        ],
        "connections": [
            {"from": "display.VCC", "to": "mcu.3V3"},
            {"from": "display.GND", "to": "mcu.GND"},
            {"from": "display.SCL", "to": "mcu.GP5"},
            {"from": "display.SDA", "to": "mcu.GP4"},
        ],
        "case": {"wall_mm": 2.0, "clearance_mm": 1.0},
    },
    "pico_oled_bme280_usb": {
        "schema_version": DEVICE_SPEC_SCHEMA,
        "name": "Raspberry Pi Pico with an OLED display and a BME280, powered over USB",
        "power": {"source": "usb"},
        "modules": [
            {"id": "mcu", "module": "raspberry-pi-pico"},
            {"id": "display", "module": "ssd1306-096-i2c"},
            {"id": "sensor", "module": "adafruit-bme280-stemma-qt"},
        ],
        "connections": [
            {"from": "display.VCC", "to": "mcu.3V3"},
            {"from": "display.GND", "to": "mcu.GND"},
            {"from": "display.SCL", "to": "mcu.GP5"},
            {"from": "display.SDA", "to": "mcu.GP4"},
            {"from": "sensor.Vin", "to": "mcu.3V3"},
            {"from": "sensor.GND", "to": "mcu.GND"},
            {"from": "sensor.SCK", "to": "mcu.GP5"},
            {"from": "sensor.SDI", "to": "mcu.GP4"},
        ],
        "case": {"wall_mm": 2.0, "clearance_mm": 1.0},
    },
}


def example_specs() -> dict[str, Any]:
    return json.loads(json.dumps(EXAMPLES))



def device_spec_json_schema() -> dict[str, Any]:
    """A JSON Schema for the device spec, built from the library so the module ids, wire colours and ranges are the ones the planner accepts.

    It is meant for a person or a model writing a spec: constrained output that satisfies it still has to pass the planner's wiring
    checks, and the planner's findings (with suggestions) say what to change.
    """

    ids = [m["id"] for m in _library()["modules"]]
    endpoint = {"type": "string", "pattern": r"^[a-z][a-z0-9_]{0,23}\.[^.\s]{1,40}$",
                "description": "module_id.PIN, for example display.SDA. A pin is named by its id or its printed name, case-insensitively."}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Hardware Splicer device spec",
        "description": "Which modules, which pin goes to which, and a case. A plan made from it is a proposal and a checklist; it approves nothing.",
        "type": "object",
        "additionalProperties": True,
        "required": ["modules"],
        "properties": {
            "schema_version": {"const": DEVICE_SPEC_SCHEMA},
            "name": {"type": "string", "minLength": 1, "maxLength": MAX_NAME},
            "power": {"type": "object", "properties": {"source": {"enum": ["usb"]}}, "additionalProperties": False},
            "modules": {
                "type": "array", "minItems": 1, "maxItems": MAX_MODULES,
                "description": "Exactly one microcontroller board and at most one display, plus any I2C breakouts.",
                "items": {
                    "type": "object", "required": ["id", "module"], "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string", "pattern": _SLUG.pattern, "description": "Your name for this module in connections, for example mcu, display, sensor."},
                        "module": {"enum": ids},
                        "pin_order": {"type": "string", "description": "For a module whose pin order varies by seller: the id of the order printed on yours (see the module's pin_orders)."},
                        "overrides": {"type": "object", "additionalProperties": False, "properties": {
                            "pcb_mm": {"type": "object", "additionalProperties": False, "properties": {k: {"type": "number", "minimum": 0.5, "maximum": 300} for k in ("x", "y", "z")}},
                            "above_board_mm": {"type": "number", "minimum": 0, "maximum": 100}}},
                    },
                },
            },
            "connections": {
                "type": "array", "maxItems": MAX_CONNECTIONS,
                "items": {"type": "object", "required": ["from", "to"], "additionalProperties": False,
                          "properties": {"from": endpoint, "to": endpoint, "wire": {"enum": sorted(WIRE_COLORS)}}},
            },
            "case": {
                "type": "object", "additionalProperties": True,
                "properties": {
                    "wall_mm": {"type": "number", "minimum": 1.2, "maximum": 5.0},
                    "clearance_mm": {"type": "number", "minimum": 0.2, "maximum": 3.0},
                    "antenna_clearance": {"type": "boolean", "description": "Lengthen the case so a board's antenna meets its sourced clearance. Default true."},
                    "board_stops": {"type": "boolean", "description": "Add stop blocks past the last header pin of each row. Default true."},
                },
            },
        },
    }


def device_catalog() -> list[dict[str, Any]]:
    """What a model needs in order to wire modules: each module's id, kind, pins with their roles, and its pin orders."""

    rows = []
    for module in _library()["modules"]:
        rows.append({
            "id": module["id"], "name": module["name"], "kind": module["kind"], "summary": module.get("summary", ""),
            "i2c_addresses": module.get("i2c", {}).get("addresses", []),
            "pin_orders": [order["id"] for order in module.get("pin_orders", [])],
            "pins": [{"id": pin["id"], "name": pin["name"], "roles": pin["roles"]} for pin in module["pins"]],
        })
    return rows

# --- spec -----------------------------------------------------------------------------------------------------------------


def _number(value: Any, label: str, low: float, high: float) -> float:
    number = finite_number(value)
    if number is None:
        raise DevicePlanError(f"{label} must be a number")
    if not low <= number <= high:
        raise DevicePlanError(f"{label} must be between {low} and {high}")
    return number


def _validate_spec(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise DevicePlanError("the spec must be an object")
    if spec.get("schema_version", DEVICE_SPEC_SCHEMA) != DEVICE_SPEC_SCHEMA:
        raise DevicePlanError(f"schema_version must be {DEVICE_SPEC_SCHEMA}")
    name = spec.get("name", "Untitled device")
    if not isinstance(name, str) or not name.strip() or len(name) > MAX_NAME:
        raise DevicePlanError(f"name must be 1 to {MAX_NAME} characters")
    if has_hidden_characters(name):
        raise DevicePlanError("name may not contain control or invisible characters")
    power = spec.get("power", {"source": "usb"})
    if not isinstance(power, dict) or not isinstance(power.get("source", "usb"), str):
        raise DevicePlanError("power must be an object with a source")
    modules = spec.get("modules")
    if not isinstance(modules, list) or not 1 <= len(modules) <= MAX_MODULES:
        raise DevicePlanError(f"modules must be a list of 1 to {MAX_MODULES}")
    seen: set[str] = set()
    clean_modules = []
    for index, row in enumerate(modules):
        if not isinstance(row, dict):
            raise DevicePlanError(f"modules[{index}] must be an object")
        mid = row.get("id")
        if not isinstance(mid, str) or not _SLUG.match(mid):
            raise DevicePlanError(f"modules[{index}].id must be lowercase letters, digits and underscores, starting with a letter")
        if mid in seen:
            raise DevicePlanError(f"module id {mid!r} is used twice")
        seen.add(mid)
        library_entry = _module(str(row.get("module")))
        order_ids = [order["id"] for order in library_entry.get("pin_orders", [])]
        if "pin_order" in row and (not isinstance(row["pin_order"], str) or row["pin_order"] not in order_ids):
            raise DevicePlanError(f"modules[{index}].pin_order must be text naming one of the valid ids: {', '.join(order_ids) or '(none for this module)'}")
        overrides = row.get("overrides", {})
        if not isinstance(overrides, dict):
            raise DevicePlanError(f"modules[{index}].overrides must be an object")
        clean: dict[str, Any] = {}
        for key, value in overrides.items():
            if key not in _OVERRIDE_KEYS:
                raise DevicePlanError(f"modules[{index}].overrides: {key!r} cannot be overridden (allowed: {', '.join(sorted(_OVERRIDE_KEYS))})")
            if key == "pcb_mm":
                if not isinstance(value, dict) or not set(value) <= _OVERRIDE_KEYS[key]:
                    raise DevicePlanError("overrides.pcb_mm may hold x, y and z")
                clean[key] = {k: _number(v, f"overrides.pcb_mm.{k}", 0.5, 300) for k, v in value.items()}
            else:
                clean[key] = _number(value, f"overrides.{key}", 0, 100)
        clean_row = {"id": mid, "module": library_entry["id"], "overrides": clean}
        if "pin_order" in row:
            clean_row["pin_order"] = row["pin_order"]
        clean_modules.append(clean_row)
    connections = spec.get("connections", [])
    if not isinstance(connections, list) or len(connections) > MAX_CONNECTIONS:
        raise DevicePlanError(f"connections must be a list of at most {MAX_CONNECTIONS}")
    clean_connections = []
    for index, row in enumerate(connections):
        if not isinstance(row, dict) or not isinstance(row.get("from"), str) or not isinstance(row.get("to"), str):
            raise DevicePlanError(f"connections[{index}] needs from and to, like \"display.SDA\"")
        wire = row.get("wire")
        if wire is not None and (not isinstance(wire, str) or wire not in WIRE_COLORS):
            raise DevicePlanError(f"connections[{index}].wire must be one of {', '.join(sorted(WIRE_COLORS))}")
        clean_connections.append({"from": row["from"], "to": row["to"], "wire": wire})
    case = spec.get("case", {})
    if not isinstance(case, dict):
        raise DevicePlanError("case must be an object")
    wall = _number(case.get("wall_mm", 2.0), "case.wall_mm", 1.2, 5.0)
    clearance = _number(case.get("clearance_mm", 1.0), "case.clearance_mm", 0.2, 3.0)
    keep_antenna_clear = case.get("antenna_clearance", True)
    if not isinstance(keep_antenna_clear, bool):
        raise DevicePlanError("case.antenna_clearance must be true or false")
    with_stops = case.get("board_stops", True)
    if not isinstance(with_stops, bool):
        raise DevicePlanError("case.board_stops must be true or false")
    return {"name": name.strip(), "power": {"source": power.get("source", "usb")}, "modules": clean_modules, "connections": clean_connections, "wall": wall, "clearance": clearance, "antenna_clearance": keep_antenna_clear, "board_stops": with_stops}


# --- geometry -------------------------------------------------------------------------------------------------------------


def _r(value: float) -> float:
    return round(float(value), 3) + 0.0


class _Placed:
    """A module in the case: library entry, effective size and a way to map its own frame into the case."""

    def __init__(self, ref: str, entry: dict[str, Any], overrides: dict[str, Any], pin_order: str | None = None) -> None:
        self.ref = ref
        self.pin_order = None
        self.pin_order_assumed = False
        if entry.get("pin_orders"):
            self.pin_order = next(order for order in entry["pin_orders"] if order["id"] == (pin_order or entry["default_pin_order"]))
            self.pin_order_assumed = pin_order is None
            by_name = {pin["name"]: pin for pin in entry["pins"]}
            # Copy the signals onto the selected pads without changing the cached library.
            entry = {**entry, "pins": [{**by_name[signal], **pad} for signal, pad in zip(self.pin_order["signals"], entry["header_positions"])]}
        self.entry = entry
        pcb = dict(entry["pcb_mm"])
        pcb.update(overrides.get("pcb_mm", {}))
        self.pcb = pcb
        self.above = float(overrides.get("above_board_mm", entry.get("above_board_mm", 0.0)))
        self.below = float(entry.get("below_board_mm", 0.0))
        self.overridden = sorted(overrides)
        self.origin = (0.0, 0.0)
        self.base_y = 0.0           # world y of the underside of the PCB
        self.turned = False         # True: the module's y axis runs along -x (the mcu board lying along the case)

    def point(self, mx: float, my: float, up: float = 0.0) -> dict[str, float]:
        """A point in the module's own top-view frame, as case coordinates (x along the case, y up, z across)."""

        if self.turned:
            return {"x": _r(self.origin[0] - my), "y": _r(self.base_y + up), "z": _r(self.origin[1] + mx)}
        return {"x": _r(self.origin[0] + mx), "y": _r(self.base_y + up), "z": _r(self.origin[1] + my)}


def _ctl(entry: dict[str, Any], key: str, default: str = "") -> str:
    """Controller-specific wording and sources come from the library entry, so a new board adds data and no code here."""

    value = entry.get("electrical", {}).get(key, default)
    return value if isinstance(value, str) else default


def _controller_of(*modules: _Placed) -> _Placed | None:
    return next((m for m in modules if m.entry["kind"] == "mcu_board"), None)


def _label(placed: _Placed, pin: dict[str, Any]) -> str:
    if "header" in pin:
        gpio = re.search(r"GPIO\d+", pin.get("function", ""))
        extra = f", also called {gpio.group(0)}" if gpio and gpio.group(0).replace("GPIO", "IO") != pin["name"] else ""
        return f"{pin['name']} (header {pin['header']}, pin {pin['number']} counting from {placed.entry.get('pin_numbering_from', 'the antenna end')}{extra})"
    if placed.entry.get("pin_order_varies"):
        return f"the pin labelled {pin['name']} (connect by the printed label, not by position in the picture)"
    return f"the pin labelled {pin['name']}"


def _resolve_pin(placed: dict[str, _Placed], endpoint: str, other: dict[str, float] | None, errors: list[str]) -> tuple[_Placed, dict[str, Any], dict[str, float], bool] | None:
    """module.PIN to (module, pin, world point, chose_among_several). A name shared by several pins (GND) takes the one nearest the other end."""

    if endpoint.count(".") != 1:
        errors.append(f"{endpoint!r} must look like module.PIN, for example display.SDA")
        return None
    mid, name = endpoint.split(".")
    if mid not in placed:
        errors.append(f"{endpoint!r}: there is no module {mid!r}")
        return None
    module = placed[mid]
    matches = [p for p in module.entry["pins"] if p["id"] == name] or [p for p in module.entry["pins"] if p["name"].lower() == name.lower()]
    if not matches:
        errors.append(f"{endpoint!r}: {module.entry['name']} has no pin named {name!r}")
        return None
    points = [(p, module.point(p["x"], p["y"], _pin_tip(module))) for p in matches]
    if len(points) > 1 and other is not None:
        points.sort(key=lambda row: (math.dist((row[1]["x"], row[1]["y"], row[1]["z"]), (other["x"], other["y"], other["z"])), row[0]["id"]))
    elif len(points) > 1:
        points.sort(key=lambda row: row[0]["id"])
    pin, point = points[0]
    return module, pin, point, len(points) > 1


def _pins_up(module: _Placed) -> bool:
    """Headers point up unless the module says they hang below the board (the OLED)."""

    face = module.entry.get("header_face")
    if face == "below":
        return False
    if face == "above":
        return True
    return module.entry["kind"] != "display"


def _pin_tip(module: _Placed) -> float:
    """How far above the module's PCB a connected wire reaches: the pin tips on a board with headers; the board's face for the rest."""

    if not _pins_up(module):
        return -0.0  # the header is on the back, so the wire meets the underside
    return module.pcb.get("z", 1.6) + PIN_TIP_ABOVE_BOARD_MM


def _end(module: _Placed, point: dict[str, float]) -> dict[str, Any]:
    """One end of a jumper: its female housing and where the wire leaves it. A board with headers has its pins pointing up, so the
    housing stands on the pin tip; a display's pins hang down from its back, so the housing hangs below it."""

    up = _pins_up(module)
    y0, y1 = (point["y"], point["y"] + WIRE_CONNECTOR_HEIGHT_MM) if up else (point["y"] - WIRE_CONNECTOR_HEIGHT_MM, point["y"])
    exit_point = {"x": point["x"], "y": _r(y1 if up else y0), "z": point["z"]}
    lead = {"x": point["x"], "y": _r(exit_point["y"] + (6.0 if up else -6.0)), "z": point["z"]}
    return {"housing": {"x": point["x"], "z": point["z"], "y0": _r(y0), "y1": _r(y1), "size_mm": 2.54}, "exit": exit_point, "lead": lead}


def _bezier(p0: dict[str, float], p1: dict[str, float], p2: dict[str, float], p3: dict[str, float]) -> list[dict[str, float]]:
    return [p0, p1, p2, p3]


def _curve_length(path: list[dict[str, float]], samples: int = 24) -> float:
    def at(t: float) -> tuple[float, float, float]:
        u = 1 - t
        return tuple(u**3 * path[0][k] + 3 * u * u * t * path[1][k] + 3 * u * t * t * path[2][k] + t**3 * path[3][k] for k in ("x", "y", "z"))  # type: ignore[return-value]

    points = [at(i / samples) for i in range(samples + 1)]
    return sum(math.dist(points[i], points[i + 1]) for i in range(samples))


def _wire_color(roles_a: set[str], roles_b: set[str], chosen: str | None) -> str:
    if chosen:
        return chosen
    roles = roles_a | roles_b
    if "ground" in roles:
        return "black"
    if roles & {"power_3v3", "power_5v", "power_in"}:
        return "red"
    if roles & {"i2c_scl", "i2c_scl_default"}:
        return "yellow"
    if roles & {"i2c_sda", "i2c_sda_default"}:
        return "green"
    return "white"


# --- findings -------------------------------------------------------------------------------------------------------------


def _finding(severity: str, rule: str, message: str, basis: str, wire: str | None = None) -> dict[str, Any]:
    return {"severity": severity, "rule": rule, "message": message, "basis": basis, "wire": wire}


def _check_connection(wire_id: str, a: tuple[_Placed, dict[str, Any]], b: tuple[_Placed, dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    (ma, pa), (mb, pb) = a, b
    ra, rb = set(pa["roles"]), set(pb["roles"])
    name = f"{ma.ref}.{pa['name']} to {mb.ref}.{pb['name']}"
    controller = _controller_of(ma, mb)
    datasheet = _ctl(controller.entry, "datasheet_basis", "the controller's datasheet") if controller else "the controller's datasheet"

    def has(roles: set[str], *wanted: str) -> bool:
        return bool(roles & set(wanted))

    for pin, owner in ((pa, ma), (pb, mb)):
        if re.search(r"\bADC2_CH\d+\b", pin.get("function", "")):
            source = next((src["url"] for src in owner.entry["sources"] if "ESP-IDF ADC docs v4.2.5" in src.get("label", "")), "")
            out.append(_finding("info", "adc2_wifi", f"{owner.ref}.{pin['name']}: analog reads on this ADC2 pin fail while Wi-Fi is running. Digital use such as I2C is not affected by that.", f"ESP-IDF ADC docs v4.2.5: adc2_get_raw() fails between esp_wifi_start() and esp_wifi_stop(); {source}", wire_id))

    # Some pins are wrong to wire to anything at all, whichever end they are on.
    for pin, owner in ((pa, ma), (pb, mb)):
        pin_roles = set(pin["roles"])
        if owner.entry["kind"] == "i2c_breakout" and not pin_roles:
            out.append(_finding("error", "unsupported_breakout_pin", f"{name} uses {owner.ref}.{pin['name']}. This pin is listed by name, but this I2C plan has no wiring checks for it. Leave it disconnected here.", "; ".join(source["url"] for source in owner.entry["sources"]) + "; this planner supports the I2C power, ground, data and clock connections", wire_id))
        elif "do_not_use" in pin_roles:
            reason = pin.get("avoid_reason") or "which belongs to the module's flash memory. Anything connected there can stop the board from running."
            out.append(_finding("error", "flash_pin", f"{name} uses {owner.ref}.{pin['name']}, {reason}" if not pin.get("avoid_reason") else f"{name} uses {owner.ref}.{pin['name']}. {reason}", datasheet, wire_id))
        elif "reset" in pin_roles:
            out.append(_finding("error", "reset_pin", f"{name} uses the reset pin ({owner.ref}.{pin['name']}). Holding it low stops the board; nothing belongs on it here.", datasheet, wire_id))
    if any(f["severity"] == "error" for f in out):
        return out

    ground_a, ground_b = has(ra, "ground"), has(rb, "ground")
    powers = {"power_3v3", "power_5v", "power_in"}
    sources = {"power_3v3", "power_5v"}
    if (has(ra, "backup_battery") and has(rb, "power_3v3", "power_5v")) or (has(rb, "backup_battery") and has(ra, "power_3v3", "power_5v")):
        backup_owner = ma if has(ra, "backup_battery") else mb
        basis = "; ".join(source["url"] for source in backup_owner.entry["sources"])
        out.append(_finding("error", "backup_to_supply", f"{name} ties the backup-battery pin to a board supply. The coin cell is backup only; do not join BAT to 3V3 or 5V.", basis + "; planner restriction: keep the coin-cell connection separate from board supplies", wire_id))
        return out
    if has(ra | rb, "backup_battery"):
        out.append(_finding("error", "backup_connection_not_supported", f"{name} uses the backup-battery pin. This plan does not describe a separate backup supply or validate this connection. Leave BAT disconnected here.", "planner supports USB power and an optional separate coin cell, without BAT wiring", wire_id))
        return out
    if has(ra, *sources) and has(rb, *sources):
        out.append(_finding("error", "supplies_joined", f"{name} joins two supply pins together.", "pin roles from the module library", wire_id))
        return out
    # DevKitC user guide, J2: "IO34 | I | GPIO34, ADC1_CH6, VDET_1"; "I: Input".
    if ground_a != ground_b and (has(ra, *powers) or has(rb, *powers) or has(ra, "gpio", "gpio_input_only", "i2c_sda", "i2c_scl") or has(rb, "gpio", "gpio_input_only", "i2c_sda", "i2c_scl")):
        kind = "a power pin" if has(ra | rb, *powers) else "a signal pin"
        detail = "A signal pin cannot provide the display's ground return." if kind == "a signal pin" else "Supply and ground must not be joined."
        out.append(_finding("error", "ground_to_other", f"{name} joins ground to {kind}. {detail}", f"pin roles from the module library; {_ctl(controller.entry, 'header_types_basis', 'the controller datasheet') if controller else 'the controller datasheet'}", wire_id))
        return out
    if ground_a and ground_b:
        return out
    if has(ra, *powers) and has(rb, *powers):
        supply, user = (pa, pb) if has(ra, "power_3v3", "power_5v") else (pb, pa)
        if has(set(supply["roles"]), "power_5v"):
            user_module = ma if user is pa else mb
            electrical = user_module.entry.get("electrical", {})
            note = " ".join(part for part in (electrical.get("supply_note"), electrical.get("pullups_note")) if part)
            sources = "; ".join(source["url"] for source in user_module.entry.get("sources", []))
            # WROOM-32E Table 15: "VIH | High-level input voltage | 0.75 × VDD | — | VDD + 0.3 | V".
            ctl = _controller_of(ma, mb)
            high_note = _ctl(ctl.entry, "input_high_note", "") if ctl else ""
            high_basis = _ctl(ctl.entry, "input_high_basis", "") if ctl else ""
            message = f"{name} runs a module from 5 V. {note} {high_note}"
            basis = f"{sources}; {high_basis}" if sources else high_basis
            if user_module.entry["id"] == "ssd1306-096-i2c":
                # Preserve the established OLED warning while new boards use
                # their own supply and pull-up evidence.
                message = f"{name} runs a module from 5 V. The SSD1306's own logic supply is 1.65 V to 3.3 V; 5 V can damage a module without a regulator. Pull-ups to VCC would also put 5 V on {_ctl(ctl.entry, 'short_name', 'the controller') if ctl else 'the controller'} SDA and SCL. Check the module's regulator and pull-up supply before connecting power."
                basis = f"SSD1306 datasheet: VDD = 1.65V to 3.3V for IC logic; {high_basis}"
            out.append(_finding("warning", "five_volts_to_a_3v3_system", " ".join(message.split()), basis, wire_id))
        return out
    if has(ra | rb, *powers) and has(ra | rb, "gpio", "i2c_sda", "i2c_scl", "gpio_input_only"):
        out.append(_finding("error", "power_to_signal", f"{name} joins a power pin to a signal pin.", "pin roles from the module library", wire_id))
        return out

    sda_a, sda_b = has(ra, "i2c_sda"), has(rb, "i2c_sda")
    scl_a, scl_b = has(ra, "i2c_scl"), has(rb, "i2c_scl")
    if (sda_a and scl_b) or (scl_a and sda_b):
        out.append(_finding("error", "sda_to_scl", f"{name} joins SDA to SCL.", "I2C signals", wire_id))
        return out
    if (sda_a and sda_b) or (scl_a and scl_b):
        return out  # Matching signals may share a bus; its controller is checked below.
    mcu_pin = pb if (sda_a or scl_a) else pa if (sda_b or scl_b) else None
    if mcu_pin is not None:
        mroles = set(mcu_pin["roles"])
        wants_sda = sda_a or sda_b
        if has(mroles, "gpio_input_only"):
            out.append(_finding("error", "input_only_pin", f"{name} uses {mcu_pin['name']}, which can only be an input. I2C needs to drive the line.", datasheet, wire_id))
        elif not has(mroles, "gpio"):
            out.append(_finding("error", "not_a_signal_pin", f"{name} uses {mcu_pin['name']}, which is not a signal pin.", datasheet, wire_id))
        elif controller is not None and _ctl(controller.entry, "i2c_pin_mux") == "fixed" and not has(mroles, "i2c_sda_capable" if wants_sda else "i2c_scl_capable"):
            wanted, other = ("SDA", "SCL") if wants_sda else ("SCL", "SDA")
            actual = f"an I2C {other} pin" if has(mroles, "i2c_scl_capable" if wants_sda else "i2c_sda_capable") else "a pin with no I2C function"
            out.append(_finding("error", "not_an_i2c_pin", f"{name} puts I2C {wanted} on {mcu_pin['name']}, which is {actual} on this board. Its I2C controllers reach only the pins marked for them: {_ctl(controller.entry, 'i2c_pin_note', 'see the pinout.')}", _ctl(controller.entry, "i2c_defaults_basis", datasheet), wire_id))
        elif "MTDI" in mcu_pin.get("function", "") and has(mroles, "strapping"):
            # WROOM-32E §4.2: "MTDI = 1, VDD_SDIO pin is powered from internal 1.8 V LDO."
            # Schematic note: "IO12 should be kept low when the module is powered on."
            out.append(_finding("error", "i2c_on_mtdi", f"{name} uses IO12 (MTDI). I2C pull-ups hold it high at reset, selecting the flash's 1.8 V supply. Keep IO12 low at power-on; move this I2C wire to another output-capable pin.", "ESP32-WROOM-32E datasheet, section 4.2 and schematic: IO12 should be kept low when the module is powered on.", wire_id))
        else:
            if has(mroles, "strapping"):
                note = ""
                basis = "ESP32-WROOM-32E datasheet, section 4 (strapping pins)"
                if mcu_pin["name"] == "IO0":
                    # ESP-IDF ADC docs v4.2.5, list of dev kits: "ESP32 DevKitC: GPIO 0 cannot be used due to external auto program circuits."
                    note = " The DevKitC also uses GPIO0 for its auto-program circuit; attached hardware can interfere with uploads."
                    basis += "; ESP-IDF ADC docs v4.2.5 (dev kit list): https://docs.espressif.com/projects/esp-idf/en/v4.2.5/esp32/api-reference/peripherals/adc.html"
                out.append(_finding("warning", "strapping_pin", f"{name} uses {mcu_pin['name']}, a pin the chip reads at start-up. Hardware on it can change how it boots.{note}", basis, wire_id))
            if has(mroles, "usb_serial"):
                out.append(_finding("warning", "serial_pin", f"{name} uses {mcu_pin['name']}, which the USB serial connection uses. It can interfere with uploading and logging.", datasheet, wire_id))
            default_sda, default_scl = has(mroles, "i2c_sda_default"), has(mroles, "i2c_scl_default")
            if (wants_sda and default_scl) or (not wants_sda and default_sda):
                out.append(_finding("warning", "swapped_default_i2c", f"{name} puts this signal on the pin that {_ctl(controller.entry, 'i2c_default_owner', 'the board support code') if controller else 'the board support code'} uses for the other one. It works if your code says so, and not otherwise.", _ctl(controller.entry, "i2c_defaults_basis", "the controller's default I2C pins") if controller else "the controller's default I2C pins", wire_id))
            elif not (default_sda or default_scl):
                out.append(_finding("info", "custom_i2c_pin", f"{name} uses {mcu_pin['name']} for I2C. {_ctl(controller.entry, 'i2c_remap_note', 'Your code must name this pin.') if controller else 'Your code must name this pin.'}", f"{_ctl(controller.entry, 'i2c_defaults_basis', 'the default pins') if controller else 'the default pins'} are the defaults", wire_id))
        return out
    return out


def _net_findings(placed: dict[str, _Placed], pairs: list[tuple[str, tuple[_Placed, dict[str, Any]], tuple[_Placed, dict[str, Any]]]]) -> list[dict[str, Any]]:
    """Wires that are each fine but together join two supplies, or a supply and ground, through the pins they share.

    A module's own ground pins are one net, and so are its 3V3 pins and its 5V pins, whether or not they are all wired. The caller
    passes only wires the per-wire rules accepted, so a wire already reported is not reported again and cannot hide another problem.
    """

    parent: dict[tuple[str, str], tuple[str, str]] = {}

    def find(node: tuple[str, str]) -> tuple[str, str]:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: tuple[str, str], b: tuple[str, str]) -> None:
        parent[find(a)] = find(b)

    roles: dict[tuple[str, str], tuple[str, set[str]]] = {}
    for module in placed.values():
        for kind in ("ground", "power_3v3", "power_5v"):
            same = [(module.ref, pin["id"]) for pin in module.entry["pins"] if kind in pin["roles"]]
            for node in same[1:]:
                union(same[0], node)
        for pin in module.entry["pins"]:
            roles[(module.ref, pin["id"])] = (f"{module.ref}.{pin['name']}", set(pin["roles"]))
    wires_in: dict[tuple[str, str], list[str]] = {}
    for wire_id, (ma, pa), (mb, pb) in pairs:
        a, b = (ma.ref, pa["id"]), (mb.ref, pb["id"])
        union(a, b)
        wires_in.setdefault(a, []).append(wire_id)
        wires_in.setdefault(b, []).append(wire_id)
    nets: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for node in list(roles):
        nets.setdefault(find(node), set()).add(node)
    out: list[dict[str, Any]] = []
    for members in nets.values():
        wires = sorted({w for node in members for w in wires_in.get(node, [])})
        if not wires:
            continue
        kinds = {role for node in members for role in roles[node][1]}
        names = sorted({roles[node][0] for node in members if roles[node][1] & {"power_3v3", "power_5v", "ground"}})
        if {"power_3v3", "power_5v"} <= kinds:
            out.append(_finding("error", "nets_bridged", f"These wires together join the 3.3 V and 5 V supplies ({', '.join(names)}).", "pin roles from the module library", wires[0]))
        elif kinds & {"power_3v3", "power_5v"} and "ground" in kinds:
            out.append(_finding("error", "nets_bridged", f"These wires together join a supply to ground ({', '.join(names)}).", "pin roles from the module library", wires[0]))
        if "backup_battery" in kinds and kinds & {"power_3v3", "power_5v", "power_in"}:
            out.append(_finding("error", "backup_to_supply", "These wires together join the backup-battery pin to a board supply. Do not join BAT to a supply while a coin cell is fitted.", "module library: backup-battery and power pin roles", wires[0]))
    return out


def _signal_nets(pairs: list[tuple[str, tuple[_Placed, dict[str, Any]], tuple[_Placed, dict[str, Any]]]]):
    """The groups of pins that the wires join into one signal, each with its pins."""

    adjacency: dict[tuple[str, str], set[tuple[str, str]]] = {}
    pins: dict[tuple[str, str], tuple[_Placed, dict[str, Any]]] = {}
    for _wire, a, b in pairs:
        ka, kb = (a[0].ref, a[1]["id"]), (b[0].ref, b[1]["id"])
        adjacency.setdefault(ka, set()).add(kb)
        adjacency.setdefault(kb, set()).add(ka)
        pins[ka], pins[kb] = a, b
    seen: set[tuple[str, str]] = set()
    for first in sorted(adjacency):
        if first in seen:
            continue
        members, pending = set(), [first]
        while pending:
            node = pending.pop()
            if node in members:
                continue
            members.add(node)
            pending.extend(adjacency[node] - members)
        seen.update(members)
        yield members, pins


def _i2c_bus_findings(placed: dict[str, _Placed], pairs: list[tuple[str, tuple[_Placed, dict[str, Any]], tuple[_Placed, dict[str, Any]]]]) -> list[dict[str, Any]]:
    """Check shared signal paths introduced by multiple breakout modules, and that one bus uses one I2C controller."""

    findings = []
    selected: dict[str, tuple[str, Any]] = {}  # signal -> (controller pin name, I2C controller index)
    check_nets = any(module.entry["kind"] == "i2c_breakout" for module in placed.values())
    for members, pins in _signal_nets(pairs):
        roles = {role for node in members for role in pins[node][1]["roles"]}
        if not roles & {"i2c_sda", "i2c_scl"}:
            continue
        names = ", ".join(sorted(f"{pins[node][0].ref}.{pins[node][1]['name']}" for node in members))
        controllers = [node for node in members if pins[node][0].entry["kind"] == "mcu_board" and "gpio" in pins[node][1]["roles"]]
        if check_nets and {"i2c_sda", "i2c_scl"} <= roles:
            findings.append(_finding("error", "i2c_signals_joined", f"These wires together join SDA to SCL ({names}).", "I2C signal roles from the module library"))
        elif check_nets and len(controllers) != 1:
            message = "has no connected microcontroller pin" if not controllers else "joins more than one microcontroller pin"
            findings.append(_finding("error", "i2c_controller_connection", f"This I2C signal {message} ({names}).", "each I2C signal needs one selected microcontroller pin in this plan"))
        elif len(controllers) == 1:
            module, pin = pins[controllers[0]]
            if module.entry.get("electrical", {}).get("i2c_pin_mux") == "fixed" and "i2c_controller" in pin:
                selected["sda" if "i2c_sda" in roles else "scl"] = (f"{module.ref}.{pin['name']}", pin["i2c_controller"])
    if len(selected) == 2 and selected["sda"][1] != selected["scl"][1]:
        finding = _finding("error", "i2c_mixed_controllers", f"SDA is on {selected['sda'][0]} (I2C{selected['sda'][1]}) and SCL on {selected['scl'][0]} (I2C{selected['scl'][1]}). One I2C bus uses both signals of the same controller.", "the controller's pinout: each I2C controller has its own SDA and SCL pins")
        mcu_ref = selected["sda"][0].split(".")[0]
        controller = placed[mcu_ref]
        finding["suggestions"] = [{"action": "move_signal", "signal": signal, "to_one_of": [f"{mcu_ref}.{p['name']}" for p in controller.entry["pins"] if f"i2c_{signal}_capable" in p["roles"] and p.get("i2c_controller") == selected[other][1]]}
                                  for signal, other in (("scl", "sda"), ("sda", "scl"))]
        findings.append(finding)
    return findings


def _candidates(mcu: _Placed, role: str, limit: int = 8) -> list[str]:
    """Controller pins that could take a wire in the given role, best first, written as ``mcu.NAME`` so a spec can use them as they are."""

    pins = mcu.entry["pins"]
    names: list[str] = []

    def add(pin: dict[str, Any]) -> None:
        name = f"{mcu.ref}.{pin['name']}"
        if name not in names:
            names.append(name)

    if role == "ground":
        for pin in pins:
            if "ground" in pin["roles"] and pin["name"].upper() == "GND":
                add(pin)
    elif role == "power":
        for pin in pins:
            if "power_3v3" in pin["roles"]:
                add(pin)
    elif role in {"i2c_sda", "i2c_scl"}:
        default, capable = f"{role}_default", f"{role}_capable"
        for pin in pins:
            if default in pin["roles"]:
                add(pin)
        for pin in pins:
            if capable in pin["roles"]:
                add(pin)
        if mcu.entry.get("electrical", {}).get("i2c_pin_mux") == "any":
            for pin in pins:
                if "gpio" in pin["roles"] and not set(pin["roles"]) & {"strapping", "usb_serial", "gpio_input_only", "do_not_use"}:
                    add(pin)
    return names[:limit] if role in {"i2c_sda", "i2c_scl"} and mcu.entry.get("electrical", {}).get("i2c_pin_mux") == "any" else names


def _attach_suggestions(findings: list[dict[str, Any]], placed: dict[str, _Placed], mcu: _Placed, wires: list[dict[str, Any]]) -> None:
    """Machine-usable ways out of the errors that have an obvious one. A suggestion is a candidate, never an applied change."""

    label_role = {"ground": "ground", "power": "power", "SDA": "i2c_sda", "SCL": "i2c_scl"}
    by_wire = {w["id"]: w for w in wires}
    for finding in findings:
        if finding["severity"] != "error":
            continue
        if finding["rule"] == "missing_connection":
            match = re.match(r"(\w+) \(.*\) has no wire on its (\w+) pin", finding["message"])
            role = label_role.get(match.group(2)) if match else None
            if match and role and match.group(1) in placed:
                module = placed[match.group(1)]
                module_role = {"ground": "ground", "power": "power_in", "i2c_sda": "i2c_sda", "i2c_scl": "i2c_scl"}[role]
                pin = next((p for p in module.entry["pins"] if module_role in p["roles"]), None)
                options = _candidates(mcu, role)
                if pin and options:
                    finding["suggestions"] = [{"action": "add_connection", "from": f"{module.ref}.{pin['name']}", "to_one_of": options}]
        elif finding["rule"] == "not_an_i2c_pin" and finding.get("wire") in by_wire:
            wire = by_wire[finding["wire"]]
            other, bad = (wire["from"], wire["to"]) if wire["to"]["module"] == mcu.ref else (wire["to"], wire["from"])
            role = "i2c_sda" if other["pin"].upper().startswith("SD") else "i2c_scl"
            finding["suggestions"] = [{"action": "replace_connection", "wire": finding["wire"], "from": f"{other['module']}.{other['pin']}", "to_one_of": _candidates(mcu, role)}]


def _required_roles(module: _Placed) -> list[tuple[str, str]]:
    if module.entry["kind"] in {"display", "i2c_breakout"}:
        return [("ground", "ground"), ("power_in", "power"), ("i2c_sda", "SDA"), ("i2c_scl", "SCL")]
    return []


# --- the plan -------------------------------------------------------------------------------------------------------------


def build_device_plan(spec: Any) -> dict[str, Any]:
    """The plan for a device spec. Pure: no I/O, deterministic for the same spec."""

    clean = _validate_spec(spec)
    placed: dict[str, _Placed] = {}
    for row in clean["modules"]:
        entry = _module(row["module"])
        if entry["kind"] not in _MODULE_KINDS:
            raise DevicePlanError(f"module kind {entry['kind']!r} cannot be placed in a case yet")
        placed[row["id"]] = _Placed(row["id"], entry, row["overrides"], row.get("pin_order"))
    boards = [m for m in placed.values() if m.entry["kind"] == "mcu_board"]
    displays = [m for m in placed.values() if m.entry["kind"] == "display"]
    if len(boards) != 1 or len(displays) > 1:
        raise DevicePlanError("a device needs exactly one microcontroller board and at most one display for now")
    mcu, display = boards[0], (displays[0] if displays else None)
    # Shared module wording names the controller with a placeholder, so a note about a 3.3 V bus says "ESP32" or "Pico" by the board in use.
    short = _ctl(mcu.entry, "short_name", "the controller")
    for module in placed.values():
        if module is not mcu:
            module.entry = {**module.entry, "electrical": {k: v.replace("{controller}", short) if isinstance(v, str) else v for k, v in module.entry.get("electrical", {}).items()}}
    wall, c = clean["wall"], clean["clearance"]

    # The board lies along the case, USB at the -x end and the antenna at +x. Positions are first worked out from the inside of the
    # -x/-z walls, then the whole layout is centred, so the case is sized from every module and not just the board.
    antenna = float(mcu.entry.get("overhang_mm", {}).get("antenna_end", 0.0))
    usb = next((k for k in mcu.entry.get("connectors", []) if k["kind"] == "micro_usb"), None)
    usb_over = float(usb["overhang_mm"]) if usb else 0.0
    mcu.turned = True
    mcu.origin = (c + usb_over + mcu.pcb["y"], c)
    board_bottom = wall + mcu.below
    mcu.base_y = board_bottom
    board_top = board_bottom + mcu.pcb["z"]
    pin_tips = board_top + PIN_TIP_ABOVE_BOARD_MM
    extent_x = c + usb_over + mcu.pcb["y"] + antenna
    # The board's source recommends a clearance around its antenna; the case is lengthened at that end to meet it, unless the spec opts out.
    antenna_rule = mcu.entry.get("engineering", {}).get("antenna")
    antenna_extra = max(0.0, antenna_rule["clearance_mm"] - c) if antenna_rule and clean["antenna_clearance"] and antenna else 0.0
    stop_reach = 0.0
    if mcu.below > 0 and clean["board_stops"]:
        # Room beyond the board's far edge for the stop blocks beyond the last header pin.
        stop_reach = min(float(pin["y"]) for pin in mcu.entry["pins"]) + PIN_SQUARE_MM / 2 + STOP_GAP_MM + STOP_THICKNESS_MM
    extent_x = c + usb_over + mcu.pcb["y"] + max(antenna + antenna_extra, stop_reach)
    extent_z = c + mcu.pcb["x"]
    mcu_top = board_top + mcu.above

    if display:
        display.base_y = pin_tips + WIRE_CONNECTOR_HEIGHT_MM + WIRE_BEND_ALLOWANCE_MM + c
        # Towards the USB end, so the display is clear of the antenna and its keep-out.
        display.origin = (c + usb_over + 4.0, c)
        extent_x = max(extent_x, display.origin[0] + display.pcb["x"])
        extent_z = max(extent_z, display.origin[1] + display.pcb["y"])
        display_top = display.base_y + display.pcb["z"] + display.above
        lid_underside = max(display_top + 0.5, mcu_top + c)
    else:
        lid_underside = mcu_top + c
    cursor_z = c + mcu.pcb["x"] + c
    for breakout in sorted((m for m in placed.values() if m.entry["kind"] == "i2c_breakout"), key=lambda m: m.ref):
        breakout.base_y = wall + breakout.below
        # USB-side of the antenna, on the case floor, beside the board so the case grows from every module.
        breakout.origin = (c + usb_over + 4.0, cursor_z)
        extent_x = max(extent_x, breakout.origin[0] + breakout.pcb["x"])
        extent_z = max(extent_z, breakout.origin[1] + breakout.pcb["y"])
        cursor_z = breakout.origin[1] + breakout.pcb["y"] + c
        housing_top = breakout.base_y + breakout.pcb.get("z", 1.6) + PIN_TIP_ABOVE_BOARD_MM + WIRE_CONNECTOR_HEIGHT_MM + WIRE_BEND_ALLOWANCE_MM
        component_top = breakout.base_y + breakout.pcb["z"] + breakout.above
        lid_underside = max(lid_underside, housing_top + c, component_top + c)
    inner_x = extent_x + c
    inner_z = extent_z + c
    inner_height = lid_underside - wall
    # Centre the layout in the case.
    for module in placed.values():
        module.origin = (module.origin[0] - inner_x / 2, module.origin[1] - inner_z / 2)
    outer = {"x": _r(inner_x + 2 * wall), "y": _r(inner_height + 2 * wall), "z": _r(inner_z + 2 * wall)}

    # Wires.
    errors: list[str] = []
    wires: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    resolved_pairs: list[tuple[str, tuple[_Placed, dict[str, Any]], tuple[_Placed, dict[str, Any]]]] = []
    for index, row in enumerate(clean["connections"], start=1):
        first = _resolve_pin(placed, row["from"], None, errors)
        if first is None:
            continue
        second = _resolve_pin(placed, row["to"], first[2], errors)
        if second is None:
            continue
        first = _resolve_pin(placed, row["from"], second[2], errors) or first
        (ma, pa, point_a, multi_a), (mb, pb, point_b, multi_b) = first, second
        if ma.ref == mb.ref:
            errors.append(f"{row['from']} to {row['to']}: both ends are on the same module")
            continue
        wire_id = f"wire-{index:02d}"
        end_a, end_b = _end(ma, point_a), _end(mb, point_b)
        path = _bezier(end_a["exit"], end_a["lead"], end_b["lead"], end_b["exit"])
        curve_mm = _curve_length(path)
        # A jumper is as long as its curve plus a little slack at each housing.
        needed = curve_mm * 1.15 + 10.0
        stock = next((size for size in WIRE_LENGTHS_MM if size >= needed), None)
        if stock is None:
            findings.append(_finding("warning", "wire_too_long", f"{row['from']} to {row['to']} needs about {needed:.0f} mm of wire; that is longer than the usual jumper sizes.", "typical jumper wire lengths", wire_id))
        wires.append(
            {
                "id": wire_id,
                "from": {"module": ma.ref, "pin_id": pa["id"], "pin": pa["name"], "label": _label(ma, pa), "point": point_a, "housing": end_a["housing"], "exit": end_a["exit"], "chosen_among_several": multi_a},
                "to": {"module": mb.ref, "pin_id": pb["id"], "pin": pb["name"], "label": _label(mb, pb), "point": point_b, "housing": end_b["housing"], "exit": end_b["exit"], "chosen_among_several": multi_b},
                "color": _wire_color(set(pa["roles"]), set(pb["roles"]), row["wire"]),
                "straight_mm": _r(math.dist((point_a["x"], point_a["y"], point_a["z"]), (point_b["x"], point_b["y"], point_b["z"]))),
                "curve_mm": _r(curve_mm),
                "stock_length_mm": stock,
                "bezier": path,
            }
        )
        resolved_pairs.append((wire_id, (ma, pa), (mb, pb)))
        findings.extend(_check_connection(wire_id, (ma, pa), (mb, pb)))
    if errors:
        raise DevicePlanError("; ".join(errors))

    # A signal pin used for two different signals. Several I2C data (or clock) wires on one bus pin are the same signal.
    users: dict[tuple[str, str], list[tuple[str, set[str]]]] = {}
    for wire_id, (ma, pa), (mb, pb) in resolved_pairs:
        for module, pin, other in ((ma, pa, (mb, pb)), (mb, pb, (ma, pa))):
            if set(pin["roles"]) & {"ground", "power_3v3", "power_5v", "power_in"}:
                continue
            users.setdefault((module.ref, pin["id"]), []).append((f"{other[0].ref}.{other[1]['name']}", set(other[1]["roles"])))
    for (ref, pin_id), others in sorted(users.items()):
        names = {name for name, _roles in others}
        if len(names) <= 1:
            continue
        other_roles = [roles for _name, roles in others]
        owner = next(pin for pin in placed[ref].entry["pins"] if pin["id"] == pin_id)
        owner_roles = set(owner["roles"])
        if any(
            signal in owner_roles and all(signal in roles or "gpio" in roles for roles in other_roles)
            or "gpio" in owner_roles and all(signal in roles for roles in other_roles)
            for signal in ("i2c_sda", "i2c_scl")
        ):
            continue
        findings.append(_finding("error", "pin_used_twice", f"{ref}.{pin_id} is wired to more than one thing: {', '.join(sorted(names))}.", "a signal pin carries one signal"))

    rejected = {f["wire"] for f in findings if f["severity"] == "error" and f["wire"]}
    findings.extend(_net_findings(placed, [pair for pair in resolved_pairs if pair[0] not in rejected]))
    findings.extend(_i2c_bus_findings(placed, [pair for pair in resolved_pairs if pair[0] not in rejected]))
    # Everything a module needs to work is wired, by a wire that the checks did not reject.
    for module in sorted(placed.values(), key=lambda m: m.ref):
        for role, label in _required_roles(module):
            connected = any(
                role in set(p["roles"]) and m.ref == module.ref
                for wire_id, a, b in resolved_pairs
                if wire_id not in rejected
                for m, p in (a, b)
            )
            if not connected:
                findings.append(_finding("error", "missing_connection", f"{module.ref} ({module.entry['name']}) has no wire on its {label} pin.", "module library: required pins"))
    # DevKitC user guide: "The power supply must be provided using one and only one of the options above".
    # power.source is a label, not a pin or a wire. The library contains no external power-source module.
    supply_note = _ctl(mcu.entry, "supply_options_note", "Use the controller's documented supply options only.")
    supply_basis = _ctl(mcu.entry, "supply_options_basis", "the controller's documentation")
    findings.append(_finding("info", "single_power_supply", supply_note, supply_basis))
    electrical = mcu.entry["electrical"]
    current_note = electrical["supply_current_note"] + " " + electrical["supply_current_practice"]
    findings.append(_finding("info", "supply_current", current_note, f"{_ctl(mcu.entry, 'supply_current_basis', 'the controller datasheet')}; {electrical['supply_current_source']}"))
    for keep_clear in mcu.entry.get("keep_clear", []):
        if keep_clear["id"] == "antenna":
            gap = _r(inner_x / 2 - (mcu.origin[0] + antenna))
            findings.append(_finding("info", "antenna_keepout", f"{keep_clear['what']} The gap from the antenna end to the inside case wall in this layout is {gap:g} mm; that is this layout's clearance, not a keepout verdict.", f"{keep_clear.get('basis', 'the controller datasheet')}; {keep_clear['source']}"))
    plug_w, plug_h = PLUG_CUTOUT_MM
    findings.append(_finding("info", "kit_fit", f"Unless you entered your own, the case uses typical values, not measurements: {WIRE_CONNECTOR_HEIGHT_MM:g} mm jumper housing height, {WIRE_BEND_ALLOWANCE_MM:g} mm wire bend allowance, {plug_w:g} x {plug_h:g} mm USB overmold, {mcu.pcb['z']:g} mm PCB thickness and {mcu.below:g} mm under-board header length. Check these against your actual kit. Female-to-female jumpers require male pins on both ends. General practice, not from the datasheet.", "typical case and jumper assumptions; general practice, not from the datasheet"))
    if clean["power"]["source"] != "usb":
        findings.append(_finding("error", "power_source_not_supported", f"Power source {clean['power']['source']!r} is not supported yet. {supply_note} This source label does not describe a supply wire or its voltage.", supply_basis))
    for module in placed.values():
        if module.pin_order:
            order = module.pin_order
            message = f"The drawing puts the pins in the order {', '.join(order['signals'])} ({order['label']}). Your module may be printed in another order: choose the order printed on your module, and connect by the printed labels, not by position in the picture."
            if module.pin_order_assumed:
                message += " This order was assumed because the spec did not choose a pin order."
            findings.append(_finding("info", "pin_order_assumed" if module.pin_order_assumed else "pin_order_drawn", message, f"{order['label']}: {order['source']}"))
        electrical = module.entry.get("electrical", {})
        source_basis = "; ".join(source["url"] for source in module.entry.get("sources", [])) or "module library"
        if module.entry["id"] == "ssd1306-096-i2c":
            source_basis = "SSD1306 datasheet (logic supply and I2C pull-ups); cited module seller listings"
        supply_rule = "oled_supply_note" if module.entry["kind"] == "display" else "module_supply_note"
        for key, rule in (("supply_note", supply_rule), ("pullups_note", "i2c_pullups_note")):
            if electrical.get(key):
                findings.append(_finding("info", rule, f"{module.ref}: {electrical[key]}", source_basis))
        if electrical.get("backup_note"):
            findings.append(_finding("info", "coin_cell_backup", f"{module.ref}: {electrical['backup_note']}", source_basis))
    i2c_modules = [module for module in placed.values() if module.entry.get("i2c", {}).get("addresses")]
    for index, left in enumerate(i2c_modules):
        left_addrs = set(left.entry["i2c"]["addresses"])
        for right in i2c_modules[index + 1:]:
            shared = left_addrs & set(right.entry["i2c"]["addresses"])
            if shared:
                findings.append(_finding(
                    "warning",
                    "i2c_address_overlap",
                    f"{left.ref} ({left.entry['name']}) and {right.ref} ({right.entry['name']}) list overlapping I2C addresses ({', '.join(sorted(shared))}). This plan does not predict which address a scan will show.",
                    f"{left.entry['name']}: {left.entry['i2c'].get('address_basis', '')}; {right.entry['name']}: {right.entry['i2c'].get('address_basis', '')}",
                ))
    pulled = [module for module in placed.values() if module.entry.get("electrical", {}).get("onboard_pullups") is True]
    if len(pulled) >= 2:
        names = ", ".join(f"{module.ref} ({module.entry['name']})" for module in sorted(pulled, key=lambda m: m.ref))
        findings.append(_finding(
            "info",
            "i2c_pullup_stack",
            f"Two or more modules state that they already have pull-up resistors ({names}). Stacked pull-ups change the bus resistance. Check each board.",
            "; ".join(source["url"] for module in pulled for source in module.entry.get("sources", [])),
        ))
    findings.sort(key=lambda f: ({"error": 0, "warning": 1, "info": 2}[f["severity"]], f["rule"], f["message"]))
    _attach_suggestions(findings, placed, mcu, wires)

    # Case.
    usb_cut = None
    if usb:
        centre = mcu.point(usb["x"], mcu.pcb["y"], board_top - board_bottom + usb["height_mm"] / 2)
        usb_cut = {"wall": "-x", "z": centre["z"], "y": centre["y"], "width_mm": PLUG_CUTOUT_MM[0], "height_mm": PLUG_CUTOUT_MM[1],
                   "basis": "wider than the socket on purpose: the plug's moulded body is much bigger. Typical; check your cable."}
    window = None
    if display:
        panel = display.entry.get("panel", {})
        active = panel.get("active_mm", {"x": 20.0, "y": 10.0})
        offset = panel.get("center_offset_mm", {"x": 0.0, "y": 0.0})
        centre = display.point(display.pcb["x"] / 2 + offset["x"], display.pcb["y"] / 2 + offset["y"], display.pcb["z"] + display.above)
        window = {"x": centre["x"], "z": centre["z"], "width_mm": _r(active["x"] + 2 * WINDOW_MARGIN_MM), "depth_mm": _r(active["y"] + 2 * WINDOW_MARGIN_MM),
                  "basis": "the active area plus a margin all round, centred where this module type usually has its glass; the offset is not published, so measure yours before printing"}

    if window is not None:
        half_x, half_z = inner_x / 2 + wall, inner_z / 2 + wall
        if abs(window["x"]) + window["width_mm"] / 2 > half_x or abs(window["z"]) + window["depth_mm"] / 2 > half_z:
            raise DevicePlanError("the display window would fall outside the lid: the measured display size is too small for its screen")

    modules_out = []
    for module in placed.values():
        pins = []
        for pin in module.entry["pins"]:
            point = module.point(pin["x"], pin["y"], _pin_tip(module))
            pins.append({"id": pin["id"], "name": pin["name"], "roles": pin["roles"], "point": point, "label": _label(module, pin)})
        corner_a, corner_b = module.point(0, 0), module.point(module.pcb["x"], module.pcb["y"])
        modules_out.append(
            {
                "id": module.ref, "module": module.entry["id"], "name": module.entry["name"], "kind": module.entry["kind"],
                "pcb_mm": module.pcb, "above_board_mm": module.above, "below_board_mm": module.below,
                "turned": module.turned, "base_y": _r(module.base_y),
                "box": {"x0": _r(min(corner_a["x"], corner_b["x"])), "x1": _r(max(corner_a["x"], corner_b["x"])), "z0": _r(min(corner_a["z"], corner_b["z"])), "z1": _r(max(corner_a["z"], corner_b["z"]))},
                "overhang_mm": module.entry.get("overhang_mm", {}),
                "overridden": module.overridden,
                "pins": pins,
                "logical_pins": pins,
                "pin_order": module.pin_order["id"] if module.pin_order else None,
                "dimension_basis": module.entry.get("dimension_basis", {}),
                "sources": module.entry["sources"],
                "notes": [*module.entry.get("notes", []),
                          *[module.entry["electrical"][key] for key in ("supply_note", "pullups_note") if module.entry.get("electrical", {}).get(key)]],
                "pin_order_varies": bool(module.entry.get("pin_order_varies")),
            }
        )

    stops = []
    if mcu.below > 0 and clean["board_stops"]:
        rows: dict[str, list[dict[str, Any]]] = {}
        for pin in mcu.entry["pins"]:
            rows.setdefault(str(pin.get("header", "")), []).append(pin)
        for header in sorted(rows):
            far = max(rows[header], key=lambda p: mcu.point(p["x"], p["y"])["x"])
            at = mcu.point(far["x"], far["y"])
            x0 = at["x"] + PIN_SQUARE_MM / 2 + STOP_GAP_MM
            stops.append({"x0": _r(x0), "x1": _r(x0 + STOP_THICKNESS_MM), "z0": _r(at["z"] - mcu.entry["pin_pitch_mm"] / 2), "z1": _r(at["z"] + mcu.entry["pin_pitch_mm"] / 2),
                          "y0": _r(wall), "y1": _r(wall + min(STOP_HEIGHT_MM, mcu.below)), "header": header or None})
        if any(stop["x1"] > inner_x / 2 or stop["z0"] < -inner_z / 2 or stop["z1"] > inner_z / 2 for stop in stops):
            stops = []
    case = {
        "style": "two_part_box",
        "wall_mm": wall, "clearance_mm": c,
        "inner_mm": {"x": _r(inner_x), "y": _r(inner_height), "z": _r(inner_z)},
        "outer_mm": outer,
        "floor_top_y": _r(wall),
        "lid_underside_y": _r(wall + inner_height),
        "usb_cutout": usb_cut, "window": window,
        **({"board_stops": {"boxes": stops, "gap_mm": STOP_GAP_MM, "basis": "A proposal: low blocks just beyond the last header pin of each row, so a plug pushed in is taken by the pins and not by the antenna end. Sizes are typical, not measured; the board is not otherwise held."}} if stops else {}),
        "basis": "A proposal sized from the modules, the clearances above and a typical jumper-wire housing height. It has not been printed or test-fitted.",
        "assumptions": {
            "board_rests_on_its_pins_mm": mcu.below,
            "wire_connector_height_mm": WIRE_CONNECTOR_HEIGHT_MM,
            "pin_tip_above_board_mm": PIN_TIP_ABOVE_BOARD_MM,
        },
    }
    steps = _steps(placed, mcu, display, wires, usb, window, findings)
    return {
        "schema_version": DEVICE_PLAN_SCHEMA,
        "authority": AUTHORITY_STATEMENT,
        "name": clean["name"],
        "power": clean["power"],
        "modules": modules_out,
        "wires": wires,
        "case": case,
        "findings": findings,
        "steps": steps,
        "shopping": _shopping(placed, wires),
        "counts": {"modules": len(modules_out), "wires": len(wires), "steps": len(steps), "errors": sum(1 for f in findings if f["severity"] == "error"), "warnings": sum(1 for f in findings if f["severity"] == "warning")},
    }


def _shopping(placed: dict[str, _Placed], wires: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [{"item": module.entry["name"], "quantity": 1, "note": "check the version: pin order and size vary between sellers" if module.entry.get("pin_order_varies") else None} for module in sorted(placed.values(), key=lambda m: m.ref)]
    by_size: dict[Any, int] = {}
    for wire in wires:
        by_size[wire["stock_length_mm"]] = by_size.get(wire["stock_length_mm"], 0) + 1
    for size, count in sorted(by_size.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)):
        rows.append({"item": f"Female-to-female jumper wire, {size / 10:g} cm" if size else "Jumper wire (longer than the usual sizes)", "quantity": count, "note": "female ends fit 2.54 mm header pins"})
    rows.append({"item": "Micro-USB data cable", "quantity": 1, "note": "a charge-only cable cannot upload code"})
    rows.append({"item": "3D-printed case, two parts", "quantity": 1, "note": "a proposal from this plan; not yet printed or test-fitted"})
    return rows


def _steps(placed: dict[str, _Placed], mcu: _Placed, display: _Placed | None, wires: list[dict[str, Any]], usb: dict[str, Any] | None, window: dict[str, Any] | None, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    antenna = bool(mcu.entry.get("overhang_mm", {}).get("antenna_end"))

    def add(kind: str, title: str, text: str, **extra: Any) -> None:
        steps.append({"step_id": f"step-{len(steps) + 1:02d}", "order": len(steps) + 1, "kind": kind, "title": title, "instruction": text, "checks": extra.pop("checks", []), **extra})

    names = ", ".join(sorted(m.entry["name"] for m in placed.values()))
    add("gather", "Gather the parts", f"You need: {names}, {len(wires)} jumper wires, a Micro-USB data cable and the printed case.", parts=sorted(placed))
    if display:
        pcb = display.pcb
        add(
            "measure", "Measure your display before anything else",
            "Follow the labels printed on your module, never the position in a drawing. Pin order varies between sellers. "
            f"The case proposal uses a display board about {pcb['x']:g} x {pcb['y']:g} mm. Measure yours with calipers and update the spec before printing. "
            "Choose the order printed on your module before following the drawing.",
            parts=[display.ref],
            checks=[{"kind": "suggested_check", "check": "measure", "from": f"{display.ref} width", "to": "your spec's dimension override", "net": None, "expect": "record what you observe; this plan supplies no reading"}],
        )
    add("place", f"Lay the {mcu.entry['name'].split(' (')[0]} in the case", f"Lower the board into the base with the USB socket at the cut-out{' and the antenna end clear of the wall' if antenna else ''}. {'It rests on its header pins.' if mcu.below else ''}", parts=[mcu.ref], motion="drop")
    for breakout in sorted((m for m in placed.values() if m.entry["kind"] == "i2c_breakout"), key=lambda m: m.ref):
        add(
            "place",
            f"Seat the {breakout.entry['name'].split(',')[0]} on the case floor",
            f"Lay {breakout.entry['name']} on the floor of the base, {'USB-side of the antenna' if antenna else 'beside the board'}, not in the lid. Connect by the printed pin names; header order was not published.",
            parts=[breakout.ref],
            motion="drop",
        )
    for wire in wires:
        a, b = wire["from"], wire["to"]
        add(
            "wire", f"Connect {a['module']}.{a['pin']} to {b['module']}.{b['pin']}",
            f"Plug one end of a {wire['color']} jumper wire onto {a['label']} on the {a['module']}, and the other end onto {b['label']} on the {b['module']}. "
            f"The wire runs about {wire['curve_mm']:.0f} mm; a {wire['stock_length_mm'] / 10:g} cm wire gives slack." if wire["stock_length_mm"] else
            f"Plug a {wire['color']} jumper wire from {a['label']} to {b['label']}.",
            wire=wire["id"], parts=[a["module"], b["module"]], color=wire["color"],
            checks=[{"kind": "suggested_check", "check": "continuity", "from": f"{a['module']}.{a['pin']}", "to": f"{b['module']}.{b['pin']}", "net": None, "expect": "record what you observe; this plan supplies no reading"}],
        )
    power_wires = [w for w in wires if w["color"] in ("red",) or w["from"]["pin"] in ("3V3", "5V", "VCC") or w["to"]["pin"] in ("3V3", "5V", "VCC")]
    ground_wires = [w for w in wires if "GND" in (w["from"]["pin"], w["to"]["pin"])]
    if power_wires and ground_wires:
        p = power_wires[0]
        pa = p["from"] if p["from"]["module"] == mcu.ref else p["to"]
        add(
            "check", "Check for a short before plugging in",
            "With all power disconnected, use a meter in continuity mode between the supply and the board's GND label. Record and investigate the reading before connecting power. These are things to try, not results.",
            checks=[{"kind": "suggested_check", "check": "isolation", "from": f"{mcu.ref}.{pa['pin']}", "to": f"{mcu.ref}.GND", "net": None, "expect": "record what you observe; this plan supplies no reading"}],
            parts=[mcu.ref],
        )
    if display and window:
        add("place", f"Fit the {display.entry['name'].split(',')[0]} into the lid", "Seat the display by its circuit-board edges, not by the glass, screen towards the window, header pins hanging inside. Never put force on the glass. Avoid straining the header or wires. General practice, not from the datasheet.", parts=[display.ref], motion="drop")
    add("close", "Close the case", "Lower the lid onto the base without trapping a wire. Fasten it the way your print is designed to (screws or snap fit).", parts=["case_lid"], motion="close")
    checks = [{"kind": "suggested_check", "check": "voltage", "from": f"{mcu.ref}.3V3", "to": f"{mcu.ref}.GND", "net": None, "expect": "record what you observe; this plan supplies no reading"}]
    if any(f["severity"] in {"warning", "error"} for f in findings):
        add("check", "Review power before connecting USB", f"Do not plug in until you have checked the warnings above and resolved the errors. Check the module supply and pull-ups. {_ctl(mcu.entry, 'supply_check_step', 'Use only the documented supply.')}", checks=checks, parts=[mcu.ref])
    else:
        add("power", "USB power and supply check", f"Review the supply and pull-up notes first. {_ctl(mcu.entry, 'supply_power_step', 'Use only the controller documented supply.')} Connect the Micro-USB data cable only after those checks. Record the supply reading; this plan gives no result. If anything gets hot or smells, unplug it.", checks=checks, parts=[mcu.ref])
    i2c_modules = [module for module in placed.values() if module.entry.get("i2c", {}).get("addresses")]
    if len(i2c_modules) == 1 and display and i2c_modules[0] is display:
        add("test", "Record an I2C scan after the wiring and power review", "After resolving the wiring and power questions, use an I2C scanner sketch that names your chosen pins. Record what it finds. The SSD1306 datasheet lists 0x3C and 0x3D as possible addresses; this plan does not predict a scan result.", parts=[display.ref], checks=[{"kind": "suggested_check", "check": "i2c_scan", "from": "I2C scanner", "to": f"{display.ref}", "net": None, "expect": "record what you observe; this plan supplies no reading"}])
    elif i2c_modules:
        listed = "; ".join(
            f"{module.entry['name']} lists {', '.join(module.entry['i2c']['addresses'])}"
            for module in sorted(i2c_modules, key=lambda m: m.ref)
        )
        add(
            "test",
            "Record an I2C scan after the wiring and power review",
            f"After resolving the wiring and power questions, use an I2C scanner sketch that names your chosen pins. Record what it finds. {listed}. This plan does not predict a scan result.",
            parts=[module.ref for module in i2c_modules],
            checks=[{"kind": "suggested_check", "check": "i2c_scan", "from": "I2C scanner", "to": ", ".join(module.ref for module in i2c_modules), "net": None, "expect": "record what you observe; this plan supplies no reading"}],
        )
    return steps
