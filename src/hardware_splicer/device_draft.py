"""A device spec drafted from a controller and a list of parts.

A draft is a starting point for a person or an agent. It wires every part the plain way (power, ground and the controller's
default I2C bus) and then runs the planner, so the findings that come back are the planner's, not this module's. Drafting
does not approve anything: the same checks, the same ``UNPROVEN`` status and the same closed authorizations apply to it
as to a spec written by hand.
"""

from __future__ import annotations

from typing import Any

from .device_plan import DEVICE_SPEC_SCHEMA, DevicePlanError, _module, build_device_plan

MAX_PARTS = 8
_WIRED_KINDS = {"display", "i2c_breakout"}


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
