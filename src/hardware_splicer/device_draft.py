"""A device spec drafted from a controller and a list of parts.

A draft is a starting point for a person or an agent. It wires every part the plain way (power, ground and the controller's
default I2C bus) and then runs the planner, so the findings that come back are the planner's, not this module's. Drafting
does not approve anything: the same checks, the same ``UNPROVEN`` status and the same closed authorizations apply to it
as to a spec written by hand.
"""

from __future__ import annotations

import re
from typing import Any

from .device_plan import DEVICE_SPEC_SCHEMA, DevicePlanError, _module, build_device_plan, module_library
from .text_safety import has_hidden_characters

MAX_PARTS = 8
MAX_TEXT = 2000
MAX_FRAGMENTS = 40
_WIRED_KINDS = {"display", "i2c_breakout"}

# Explicit typed names only. A variant (ESP32-S3) is not the listed board; a generic word is labelled as one.
TYPED_NAMES: dict[str, tuple[tuple[str, str], ...]] = {
    "esp32-devkitc-v4": (("esp32", "name"), ("esp32 devkitc", "name"), ("devkitc", "name"), ("esp32 wroom 32e", "chip")),
    "raspberry-pi-pico": (("raspberry pi pico", "name"), ("pico", "name"), ("rp2040", "chip")),
    "ssd1306-096-i2c": (("ssd1306", "chip"), ("oled", "generic_word")),
    "adafruit-bme280-stemma-qt": (("bme280", "chip"),),
    "adafruit-bh1750-stemma-qt": (("bh1750fvi", "chip"), ("bh1750", "chip")),
    "adafruit-ds3231-stemma-qt": (("ds3231", "chip"),),
    "adafruit-ina219-stemma-qt": (("ina219", "chip"),),
    "adafruit-mpu-6050-stemma-qt": (("mpu 6050", "chip"),),
    "adafruit-ads1115-stemma-qt": (("ads1115", "chip"),),
}

# Known different boards. A space-separated variant is still that other board, not the library entry.
NOT_THE_LISTED_BOARD: dict[str, tuple[str, ...]] = {
    "esp32-devkitc-v4": (r"\besp32[\s\-]*(?:s2|s3|c2|c3|c5|c6|h2|p4)\b",),
    "raspberry-pi-pico": (r"\bpico[\s\-]*(?:2|w)\b", r"\brp2350\b"),
}

_SPLIT = re.compile(r"(?:\n|,|;|\+|&|\s+and\s+|\s+with\s+|\s+plus\s+)", re.IGNORECASE)
_QTY_PREFIX = re.compile(r"^\s*([1-8])\s*[x×]\s+")
_QTY_SUFFIX = re.compile(r"\s[x×]\s*([1-8])\s*$")
_VARIANT_TAIL = r"(?![A-Za-z0-9])(?!-?[A-Za-z]{0,2}\d)"


def _pin(entry: dict[str, Any], role: str) -> dict[str, Any] | None:
    return next((p for p in entry["pins"] if role in p["roles"]), None)


def _controller_pin(entry: dict[str, Any], *roles: str, name: str | None = None) -> str:
    for role in roles:
        for pin in entry["pins"]:
            if role in pin["roles"] and (name is None or pin["name"].upper() == name):
                return pin["name"]
    raise DevicePlanError(f"{entry['id']} declares no pin for {' or '.join(roles)}, so its parts cannot be wired automatically")


def draft_device_spec(request: Any) -> dict[str, Any]:
    """``{"controller": id, "parts": [id, ...], "power": "usb", "name": text}`` -> the spec, what was assumed, and the planner's findings."""

    if not isinstance(request, dict):
        raise DevicePlanError("the request must be an object")
    controller_id, parts = request.get("controller"), request.get("parts")
    if not isinstance(controller_id, str):
        raise DevicePlanError("controller must be a module id from the library")
    if not isinstance(parts, list) or not 1 <= len(parts) <= MAX_PARTS or not all(isinstance(p, str) for p in parts):
        raise DevicePlanError(f"parts must be a list of 1 to {MAX_PARTS} module ids from the library")
    controller = _module(controller_id)
    if controller["kind"] != "mcu_board":
        raise DevicePlanError(f"{controller_id} is not a controller board")

    sda = _controller_pin(controller, "i2c_sda_default")
    scl = _controller_pin(controller, "i2c_scl_default")
    supply = _controller_pin(controller, "power_3v3")
    ground = _controller_pin(controller, "ground", name="GND")

    modules = [{"id": "mcu", "module": controller["id"]}]
    connections: list[dict[str, str]] = []
    counts: dict[str, int] = {}
    for part_id in parts:
        entry = _module(part_id)
        if entry["kind"] not in _WIRED_KINDS:
            raise DevicePlanError(f"{part_id} is a {entry['kind']}; only displays and I2C breakouts can be wired automatically")
        base = "display" if entry["kind"] == "display" else "sensor"
        counts[base] = counts.get(base, 0) + 1
        ref = base if counts[base] == 1 else f"{base}_{counts[base]}"
        modules.append({"id": ref, "module": entry["id"]})
        for role, target in (("power_in", supply), ("ground", ground), ("i2c_scl", scl), ("i2c_sda", sda)):
            pin = _pin(entry, role)
            if pin is None:
                raise DevicePlanError(f"{part_id} declares no {role} pin, so it cannot be wired automatically")
            connections.append({"from": f"{ref}.{pin['name']}", "to": f"mcu.{target}"})

    name = request.get("name")
    if name is None:
        name = f"{controller['name']} with {len(parts)} part{'s' if len(parts) != 1 else ''}"
    spec = {"schema_version": DEVICE_SPEC_SCHEMA, "name": name, "power": {"source": request.get("power", "usb")}, "modules": modules, "connections": connections, "case": {"wall_mm": 2.0, "clearance_mm": 1.0}}
    plan = build_device_plan(spec)
    return {
        "spec": spec,
        "assumptions": [
            f"Every part is powered from {controller_id} {supply} and grounded to {ground}.",
            f"All parts share the controller's default I2C bus ({sda} for SDA, {scl} for SCL).",
            "Power is taken from the part's main supply pin, whatever its rated voltage; the planner's findings say whether that suits it.",
            "Nothing is chosen for you beyond that: addresses, pull-ups, supply current and fit are for the planner and the engineering review to report.",
        ],
        "findings": plan["findings"],
        "next": "POST the spec to /v1/devices/plan, then /v1/devices/engineering, to see the complete plan and review.",
    }


def _alias_body(alias: str) -> str:
    chunks: list[str] = []
    i = 0
    while i < len(alias):
        if alias[i] in " -":
            while i < len(alias) and alias[i] in " -":
                i += 1
            chunks.append(r"[\s\-]*" if chunks and i < len(alias) else r"[\s\-]+")
        else:
            j = i
            while j < len(alias) and alias[j] not in " -":
                j += 1
            chunks.append(re.escape(alias[i:j]))
            i = j
    return "".join(chunks)


def _compile_aliases() -> tuple[tuple[re.Pattern[str], str, str, str, str], ...]:
    rows = []
    for module_id, aliases in TYPED_NAMES.items():
        name = _module(module_id)["name"]
        for alias, basis in aliases:
            pattern = re.compile(rf"\b{_alias_body(alias)}{_VARIANT_TAIL}", re.IGNORECASE)
            rows.append((pattern, module_id, name, alias, basis))
    return tuple(rows)


_ALIAS_INDEX = _compile_aliases()
_VARIANT_INDEX = tuple(
    (module_id, _module(module_id)["name"], tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns))
    for module_id, patterns in NOT_THE_LISTED_BOARD.items()
)


def _fragment_quantity(text: str) -> int:
    prefix = _QTY_PREFIX.match(text)
    if prefix:
        return int(prefix.group(1))
    suffix = _QTY_SUFFIX.search(text)
    return int(suffix.group(1)) if suffix else 1


def _other_board(text: str) -> tuple[set[str], str | None]:
    dropped: set[str] = set()
    note: str | None = None
    for module_id, name, patterns in _VARIANT_INDEX:
        for pattern in patterns:
            hit = pattern.search(text)
            if hit:
                dropped.add(module_id)
                if note is None:
                    note = f"{hit.group(0)} is a different board from the library's {name}; it was not used."
    return dropped, note


def _match_fragment(text: str) -> list[dict[str, Any]]:
    found: list[tuple[int, int, dict[str, Any]]] = []
    for pattern, module_id, name, alias, basis in _ALIAS_INDEX:
        for hit in pattern.finditer(text):
            found.append((hit.start(), hit.end(), {"module": module_id, "name": name, "matched_on": alias, "basis": basis}))
    found.sort(key=lambda row: (row[0], row[0] - row[1], -len(row[2]["matched_on"])))
    matches: list[dict[str, Any]] = []
    cursor = 0
    for start, end, match in found:
        if start < cursor:
            continue
        matches.append(match)
        cursor = end
    quantity = _fragment_quantity(text)
    for index, match in enumerate(matches):
        match["quantity"] = quantity if index == 0 else 1
    return matches


def parse_parts_text(text: str) -> dict[str, Any]:
    """Split a typed list into fragments and name the library modules each one matches, or that nothing matched."""

    if not isinstance(text, str) or not text.strip():
        raise DevicePlanError("text must be a non-empty string")
    text = text.strip()
    if len(text) > MAX_TEXT:
        raise DevicePlanError(f"text may be at most {MAX_TEXT} characters")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    if has_hidden_characters(text.replace("\n", "")):
        raise DevicePlanError("the text may not contain invisible characters")
    pieces = [piece.strip() for piece in _SPLIT.split(text) if piece.strip()]
    if len(pieces) > MAX_FRAGMENTS:
        raise DevicePlanError(f"the list may name at most {MAX_FRAGMENTS} fragments")

    fragments: list[dict[str, Any]] = []
    parts: list[str] = []
    controllers: list[str] = []
    for piece in pieces:
        matches = _match_fragment(piece)
        dropped, note = _other_board(piece)
        if dropped:
            matches = [match for match in matches if match["module"] not in dropped]
        fragment: dict[str, Any] = {"text": piece, "matches": matches}
        if note:
            fragment["note"] = note
        fragments.append(fragment)
        for match in matches:
            if _module(match["module"])["kind"] == "mcu_board":
                controllers.append(match["module"])
            else:
                parts.extend([match["module"]] * match["quantity"])
    return {
        "fragments": fragments,
        "controller": controllers[0] if len(controllers) == 1 else None,
        "parts": parts,
        "left_out": [fragment["text"] for fragment in fragments if not fragment["matches"]],
    }


def draft_from_parts_text(body: dict[str, Any]) -> dict[str, Any]:
    """Parse a typed parts list and hand the named controller and parts to the existing drafter. Approves nothing."""

    if not isinstance(body, dict) or "text" not in body:
        raise DevicePlanError("text is required")
    parsed = parse_parts_text(body["text"])
    named = [match["module"] for fragment in parsed["fragments"] for match in fragment["matches"] if _module(match["module"])["kind"] == "mcu_board"]
    if not named:
        names = ", ".join(entry["name"] for entry in module_library()["modules"] if entry["kind"] == "mcu_board")
        raise DevicePlanError(f"name a controller from the library: {names}")
    if len(named) > 1:
        raise DevicePlanError("name one controller")
    if not parsed["parts"]:
        raise DevicePlanError("name a display or I2C breakout part from the library")
    if len(parsed["parts"]) > MAX_PARTS:
        raise DevicePlanError(f"parts may be at most {MAX_PARTS}")
    return {"parsed": parsed, **draft_device_spec({"controller": parsed["controller"], "parts": parsed["parts"], "power": body.get("power", "usb")})}
