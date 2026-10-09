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
WIRE_COLORS = {"red", "black", "yellow", "green", "blue", "white", "orange"}
_SLUG = re.compile(r"^[a-z][a-z0-9_]{0,23}$")
_OVERRIDE_KEYS = {"pcb_mm": {"x", "y", "z"}, "above_board_mm": None}
_MODULE_KINDS = {"mcu_board", "display"}


class DevicePlanError(ValueError):
    """The spec is not something a plan can be made from."""


# --- library --------------------------------------------------------------------------------------------------------------


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
    return data


def module_library() -> dict[str, Any]:
    """The module library as published: every module with its sources, dimension basis and pins."""

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
    }
}


def example_specs() -> dict[str, Any]:
    return json.loads(json.dumps(EXAMPLES))


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
        clean_modules.append({"id": mid, "module": library_entry["id"], "overrides": clean})
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
    return {"name": name.strip(), "power": {"source": power.get("source", "usb")}, "modules": clean_modules, "connections": clean_connections, "wall": wall, "clearance": clearance}


# --- geometry -------------------------------------------------------------------------------------------------------------


def _r(value: float) -> float:
    return round(float(value), 3) + 0.0


class _Placed:
    """A module in the case: library entry, effective size and a way to map its own frame into the case."""

    def __init__(self, ref: str, entry: dict[str, Any], overrides: dict[str, Any]) -> None:
        self.ref = ref
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


def _label(placed: _Placed, pin: dict[str, Any]) -> str:
    if "header" in pin:
        gpio = re.search(r"GPIO\d+", pin.get("function", ""))
        extra = f", also called {gpio.group(0)}" if gpio and gpio.group(0).replace("GPIO", "IO") != pin["name"] else ""
        return f"{pin['name']} (header {pin['header']}, pin {pin['number']} counting from the antenna end{extra})"
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


def _pin_tip(module: _Placed) -> float:
    """How far above the module's PCB a connected wire reaches: the pin tips on a board with headers; the board's face for the rest."""

    if module.entry["kind"] == "display":
        return -0.0  # the header is on the back, so the wire meets the underside
    return module.pcb.get("z", 1.6) + PIN_TIP_ABOVE_BOARD_MM


def _end(module: _Placed, point: dict[str, float]) -> dict[str, Any]:
    """One end of a jumper: its female housing and where the wire leaves it. A board with headers has its pins pointing up, so the
    housing stands on the pin tip; a display's pins hang down from its back, so the housing hangs below it."""

    up = module.entry["kind"] != "display"
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
    datasheet = "ESP32-WROOM-32E datasheet; ESP32-DevKitC V4 user guide"

    def has(roles: set[str], *wanted: str) -> bool:
        return bool(roles & set(wanted))

    # Some pins are wrong to wire to anything at all, whichever end they are on.
    for pin, owner in ((pa, ma), (pb, mb)):
        pin_roles = set(pin["roles"])
        if "do_not_use" in pin_roles:
            out.append(_finding("error", "flash_pin", f"{name} uses {owner.ref}.{pin['name']}, which belongs to the module's flash memory. Anything connected there can stop the board from running.", datasheet, wire_id))
        elif "reset" in pin_roles:
            out.append(_finding("error", "reset_pin", f"{name} uses the reset pin ({owner.ref}.{pin['name']}). Holding it low stops the board; nothing belongs on it here.", datasheet, wire_id))
    if out:
        return out

    ground_a, ground_b = has(ra, "ground"), has(rb, "ground")
    powers = {"power_3v3", "power_5v", "power_in"}
    sources = {"power_3v3", "power_5v"}
    if has(ra, *sources) and has(rb, *sources):
        out.append(_finding("error", "supplies_joined", f"{name} joins two supply pins together.", "pin roles from the module library", wire_id))
        return out
    if ground_a != ground_b and (has(ra, *powers) or has(rb, *powers) or has(ra, "gpio", "i2c_sda", "i2c_scl") or has(rb, "gpio", "i2c_sda", "i2c_scl")):
        kind = "a power pin" if has(ra | rb, *powers) else "a signal pin"
        out.append(_finding("error", "ground_to_other", f"{name} joins ground to {kind}. That is a short or a stuck signal.", "pin roles from the module library", wire_id))
        return out
    if ground_a and ground_b:
        return out
    if has(ra, *powers) and has(rb, *powers):
        supply, user = (pa, pb) if has(ra, "power_3v3", "power_5v") else (pb, pa)
        if has(set(supply["roles"]), "power_5v"):
            out.append(_finding("warning", "five_volts_to_a_3v3_system", f"{name} runs a module from 5 V. Many modules pull SDA and SCL up to their supply, which would put 5 V on ESP32 pins that are rated for 3.3 V.", "ESP32-WROOM-32E datasheet: VIH max is VDD + 0.3 V; the module note says pull-ups usually go to VCC", wire_id))
        return out
    if has(ra | rb, *powers) and has(ra | rb, "gpio", "i2c_sda", "i2c_scl", "gpio_input_only"):
        out.append(_finding("error", "power_to_signal", f"{name} joins a power pin to a signal pin.", "pin roles from the module library", wire_id))
        return out

    sda_a, sda_b = has(ra, "i2c_sda"), has(rb, "i2c_sda")
    scl_a, scl_b = has(ra, "i2c_scl"), has(rb, "i2c_scl")
    if (sda_a and scl_b) or (scl_a and sda_b):
        out.append(_finding("error", "sda_to_scl", f"{name} joins SDA to SCL.", "I2C signals", wire_id))
        return out
    mcu_pin = pb if (sda_a or scl_a) else pa if (sda_b or scl_b) else None
    if mcu_pin is not None:
        mroles = set(mcu_pin["roles"])
        wants_sda = sda_a or sda_b
        if has(mroles, "gpio_input_only"):
            out.append(_finding("error", "input_only_pin", f"{name} uses {mcu_pin['name']}, which can only be an input. I2C needs to drive the line.", datasheet, wire_id))
        elif not has(mroles, "gpio"):
            out.append(_finding("error", "not_a_signal_pin", f"{name} uses {mcu_pin['name']}, which is not a signal pin.", datasheet, wire_id))
        else:
            if has(mroles, "strapping"):
                out.append(_finding("warning", "strapping_pin", f"{name} uses {mcu_pin['name']}, a pin the chip reads at start-up. Hardware on it can change how it boots.", "ESP32-WROOM-32E datasheet, Table 4 (strapping pins)", wire_id))
            if has(mroles, "usb_serial"):
                out.append(_finding("warning", "serial_pin", f"{name} uses {mcu_pin['name']}, which the USB serial connection uses. It can interfere with uploading and logging.", datasheet, wire_id))
            default_sda, default_scl = has(mroles, "i2c_sda_default"), has(mroles, "i2c_scl_default")
            if (wants_sda and default_scl) or (not wants_sda and default_sda):
                out.append(_finding("warning", "swapped_default_i2c", f"{name} puts this signal on the pin that Arduino uses for the other one. It works if your code says so, and not otherwise.", "arduino-esp32 pins_arduino.h: SDA = 21, SCL = 22", wire_id))
            elif not (default_sda or default_scl):
                out.append(_finding("info", "custom_i2c_pin", f"{name} uses {mcu_pin['name']} for I2C. The ESP32 can route I2C to most pins, but your code must name it.", "arduino-esp32 pins_arduino.h: SDA = 21, SCL = 22 are the defaults", wire_id))
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
    return out


def _required_roles(module: _Placed) -> list[tuple[str, str]]:
    if module.entry["kind"] == "display":
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
        placed[row["id"]] = _Placed(row["id"], entry, row["overrides"])
    boards = [m for m in placed.values() if m.entry["kind"] == "mcu_board"]
    displays = [m for m in placed.values() if m.entry["kind"] == "display"]
    if len(boards) != 1 or len(displays) > 1:
        raise DevicePlanError("a device needs exactly one microcontroller board and at most one display for now")
    mcu, display = boards[0], (displays[0] if displays else None)
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

    # A signal pin used for two different signals.
    users: dict[tuple[str, str], list[str]] = {}
    for wire_id, (ma, pa), (mb, pb) in resolved_pairs:
        for module, pin, other in ((ma, pa, (mb, pb)), (mb, pb, (ma, pa))):
            if set(pin["roles"]) & {"ground", "power_3v3", "power_5v", "power_in"}:
                continue
            users.setdefault((module.ref, pin["id"]), []).append(f"{other[0].ref}.{other[1]['name']}")
    for (ref, pin_id), others in sorted(users.items()):
        if len(set(others)) > 1:
            findings.append(_finding("error", "pin_used_twice", f"{ref}.{pin_id} is wired to more than one thing: {', '.join(sorted(set(others)))}.", "a signal pin carries one signal"))

    rejected = {f["wire"] for f in findings if f["severity"] == "error" and f["wire"]}
    findings.extend(_net_findings(placed, [pair for pair in resolved_pairs if pair[0] not in rejected]))
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
    if clean["power"]["source"] != "usb":
        findings.append(_finding("error", "power_source_not_supported", f"Power source {clean['power']['source']!r} is not supported yet. A battery needs a charger and a regulator between it and the board; wiring one straight to the 3V3 pin exceeds the 3.6 V the module allows.", "ESP32-WROOM-32E datasheet: VDD33 abs. max 3.6 V"))
    findings.sort(key=lambda f: ({"error": 0, "warning": 1, "info": 2}[f["severity"]], f["rule"], f["message"]))

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
                "dimension_basis": module.entry.get("dimension_basis", {}),
                "sources": module.entry["sources"],
                "notes": module.entry.get("notes", []),
                "pin_order_varies": bool(module.entry.get("pin_order_varies")),
            }
        )

    case = {
        "style": "two_part_box",
        "wall_mm": wall, "clearance_mm": c,
        "inner_mm": {"x": _r(inner_x), "y": _r(inner_height), "z": _r(inner_z)},
        "outer_mm": outer,
        "floor_top_y": _r(wall),
        "lid_underside_y": _r(wall + inner_height),
        "usb_cutout": usb_cut, "window": window,
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

    def add(kind: str, title: str, text: str, **extra: Any) -> None:
        steps.append({"step_id": f"step-{len(steps) + 1:02d}", "order": len(steps) + 1, "kind": kind, "title": title, "instruction": text, "checks": extra.pop("checks", []), **extra})

    names = ", ".join(sorted(m.entry["name"] for m in placed.values()))
    add("gather", "Gather the parts", f"You need: {names}, {len(wires)} jumper wires, a Micro-USB data cable and the printed case.", parts=sorted(placed))
    if display:
        pcb = display.pcb
        add(
            "measure", "Measure your display before anything else",
            f"The plan assumes the display board is about {pcb['x']:g} x {pcb['y']:g} mm and that its pins are labelled GND, VCC, SCL and SDA. Sellers differ. "
            "Measure yours with calipers. If it is more than 1 mm off, or the pins are in another order, change the numbers in the spec before printing. "
            "Always connect by the printed label, never by position.",
            parts=[display.ref],
            checks=[{"kind": "suggested_check", "check": "measure", "from": f"{display.ref} width", "to": f"about {pcb['x']:g} mm", "net": None, "expect": "within 1 mm"}],
        )
    add("place", f"Lay the {mcu.entry['name'].split(' (')[0]} in the case", f"Lower the board into the base with the USB socket at the cut-out and the antenna end clear of the wall. {'It rests on its header pins.' if mcu.below else ''}", parts=[mcu.ref], motion="drop")
    for wire in wires:
        a, b = wire["from"], wire["to"]
        add(
            "wire", f"Connect {a['module']}.{a['pin']} to {b['module']}.{b['pin']}",
            f"Plug one end of a {wire['color']} jumper wire onto {a['label']} on the {a['module']}, and the other end onto {b['label']} on the {b['module']}. "
            f"The wire runs about {wire['curve_mm']:.0f} mm; a {wire['stock_length_mm'] / 10:g} cm wire gives slack." if wire["stock_length_mm"] else
            f"Plug a {wire['color']} jumper wire from {a['label']} to {b['label']}.",
            wire=wire["id"], parts=[a["module"], b["module"]], color=wire["color"],
            checks=[{"kind": "suggested_check", "check": "continuity", "from": f"{a['module']}.{a['pin']}", "to": f"{b['module']}.{b['pin']}", "net": None, "expect": "the two points are connected (beep)"}],
        )
    power_wires = [w for w in wires if w["color"] in ("red",) or w["from"]["pin"] in ("3V3", "5V", "VCC") or w["to"]["pin"] in ("3V3", "5V", "VCC")]
    ground_wires = [w for w in wires if "GND" in (w["from"]["pin"], w["to"]["pin"])]
    if power_wires and ground_wires:
        p, g = power_wires[0], ground_wires[0]
        pa = p["from"] if p["from"]["module"] == mcu.ref else p["to"]
        ga = g["from"] if g["from"]["module"] == mcu.ref else g["to"]
        add(
            "check", "Check for a short before plugging in",
            "With nothing connected to USB, use a meter in continuity mode between the supply and ground. They must not be connected. These are things to try, not results.",
            checks=[{"kind": "suggested_check", "check": "isolation", "from": f"{mcu.ref}.{pa['pin']}", "to": f"{mcu.ref}.{ga['pin']}", "net": None, "expect": "NOT connected"}],
            parts=[mcu.ref],
        )
    if display and window:
        add("place", f"Fit the {display.entry['name'].split(',')[0]} into the lid", "Press the display into the lid from below, screen towards the window, header pins hanging inside. Wires stay attached.", parts=[display.ref], motion="drop")
    add("close", "Close the case", "Lower the lid onto the base without trapping a wire. Fasten it the way your print is designed to (screws or snap fit).", parts=["case_lid"], motion="close")
    checks = [{"kind": "suggested_check", "check": "voltage", "from": f"{mcu.ref}.3V3", "to": f"{mcu.ref}.GND", "net": None, "expect": "between 3.0 V and 3.6 V (the module's supply range in its datasheet)"}]
    add("power", "Plug in USB and check the supply", "Connect the Micro-USB data cable. Nothing will show on the display yet: it needs code. If anything gets hot or smells, unplug it.", checks=checks, parts=[mcu.ref])
    if display:
        add("test", "Look for the display on the I2C bus", "Upload any I2C scanner sketch with the Arduino IDE. It should report one device, at 0x3C or 0x3D (the SSD1306 datasheet gives those two addresses).", parts=[display.ref], checks=[{"kind": "suggested_check", "check": "i2c_scan", "from": "I2C scanner", "to": f"{display.ref}", "net": None, "expect": "a device at 0x3C or 0x3D"}])
    return steps
