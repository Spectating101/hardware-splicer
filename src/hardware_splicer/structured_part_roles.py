"""Deterministic projection of declared structured part roles.

This module is intentionally narrow. It does not interpret arbitrary prose and never
looks at human-facing ``name`` or product ``module_id`` fields. It only normalizes fields
that are already declared as structural semantics (type/category/role/class/domain or
capability tags) and maps a bounded vocabulary onto coarse engineering roles.

Unknown structured values remain ``unknown``. Legacy name/keyword compatibility belongs
outside this module behind explicit offline policy.
"""

from __future__ import annotations

import re
from typing import Any, Mapping


STRUCTURED_FIELDS = ("type", "category", "role", "class")
CAPABILITY_FIELDS = ("capability_tags", "capabilityTags", "capabilities")
DECLARED_DOMAINS = {
    "system",
    "mechanical",
    "electrical",
    "firmware",
    "software",
    "sourcing",
    "assembly",
    "verification",
}


def _token(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def declared_part_domain(row: Mapping[str, Any]) -> str | None:
    token = _token(row.get("domain"))
    return token if token in DECLARED_DOMAINS else None


def structured_part_tokens(row: Mapping[str, Any]) -> set[str]:
    tokens = {_token(row.get(key)) for key in STRUCTURED_FIELDS}
    for key in CAPABILITY_FIELDS:
        value = row.get(key)
        if isinstance(value, (list, tuple, set)):
            tokens.update(_token(item) for item in value)
        elif value:
            tokens.add(_token(value))
    tokens.discard("")
    return tokens


_ROLE_ALIASES: dict[str, set[str]] = {
    "actuator": {
        "actuator",
        "dc_motor",
        "motor",
        "stepper_motor",
        "servo",
        "pump",
        "fan",
        "motor_or_load",
        "fan_or_pump",
    },
    "sensor": {
        "sensor",
        "sensor_or_adc",
        "camera",
        "camera_or_vision",
        "imu",
        "lidar",
        "encoder",
        "radar",
        "microphone",
        "measurement_sensor",
    },
    "power": {
        "power",
        "power_source",
        "battery",
        "regulator",
        "converter",
        "power_supply",
        "bms",
    },
    "controller": {
        "controller",
        "microcontroller",
        "mcu",
        "processor",
        "compute",
    },
    "structure": {
        "structure",
        "mechanical_structure",
        "chassis",
        "frame",
        "bracket",
        "mount",
        "enclosure",
        "housing",
        "bearing",
    },
    "electrical": {
        "driver",
        "actuator_driver",
        "interface",
        "interface_board",
        "connector",
        "protection",
        "usb_serial",
        "switch_or_button",
        "display_or_ui",
        "led_or_light",
        "wireless",
        "electrical",
        "pcb",
        "board",
    },
}


def declared_part_role(row: Mapping[str, Any]) -> tuple[str, str]:
    """Return ``(role, source)`` from structured declarations only."""
    tokens = structured_part_tokens(row)
    for role in ("actuator", "sensor", "power", "controller", "structure", "electrical"):
        if tokens & _ROLE_ALIASES[role]:
            return role, "declared_structured_fields"
    return "unknown", "unresolved"


def part_has_role(row: Mapping[str, Any], role: str) -> bool:
    projected, _ = declared_part_role(row)
    return projected == role
