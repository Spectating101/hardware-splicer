"""Check that firmware names every microcontroller pin the design wires to a signal.

A composed design can have two servos wired to GPIO15 and GPIO16 while its firmware only
blinks the built-in LED, and nothing in the board checks would notice. This reads the
wiring and the firmware source. It does not compile the firmware or run it.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping

from .pcb.module_registry import find_module

SCHEMA_VERSION = "hardware_splicer.firmware_coverage.v1"
CLAIM_BOUNDARY = (
    "Checks only that the firmware names each microcontroller pin the design wires to a signal. "
    "It does not compile the firmware, and does not show the firmware will behave as intended. "
    "Bus pins (I2C, UART) are not expected in the source because the default bus hides them."
)
# Pins the firmware must mention by number. Bus and power roles are excluded on purpose.
_SIGNAL_ROLES = frozenset({"digital_io", "digital_in", "digital_out", "pwm", "analog_in"})
_COMMENTS = re.compile(r"/\*.*?\*/|//[^\n]*|#[^\n]*", re.DOTALL)


def assess_firmware_coverage(
    build_graph: Mapping[str, Any] | None,
    firmware_source: str | None,
) -> Dict[str, Any]:
    required = _required_pins(build_graph) if build_graph is not None else []
    if build_graph is None or firmware_source is None or not required:
        status = "not_assessable"
        uncovered: List[Dict[str, str]] = []
    else:
        code = _COMMENTS.sub("", firmware_source)
        uncovered = [row for row in required if not _names_pin(code, row["pin"])]
        status = "gaps" if uncovered else "covers"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "required_pins": required,
        "uncovered_pins": uncovered,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _required_pins(graph: Mapping[str, Any]) -> List[Dict[str, str]]:
    module_of = {str(n.get("id")): str(n.get("moduleId") or "") for n in graph.get("nodes") or []}
    specs = {node_id: (find_module(module_id) if module_id else None) for node_id, module_id in module_of.items()}
    pin_roles = {
        node_id: {str(p.get("id")): str(p.get("role") or "") for p in (spec or {}).get("pins") or []}
        for node_id, spec in specs.items()
    }
    mcus = {node_id for node_id, spec in specs.items() if spec and spec.get("category") == "mcu"}
    required: Dict[str, Dict[str, str]] = {}
    for wire in graph.get("wires") or []:
        ends = (wire.get("from") or {}, wire.get("to") or {})
        for here, there in (ends, ends[::-1]):
            node, other = str(here.get("nodeId")), str(there.get("nodeId"))
            if node not in mcus or other in mcus:
                continue
            pin = str(here.get("pinId"))
            if _carries_signal(
                pin_roles[node].get(pin, ""), pin_roles.get(other, {}).get(str(there.get("pinId")), "")
            ):
                required.setdefault(
                    pin, {"pin": pin, "drives": f"{module_of.get(other, other)}.{there.get('pinId')}"}
                )
    return list(required.values())


def _carries_signal(mcu_role: str, partner_role: str) -> bool:
    """A pin needs naming in the source unless it is a bus pin talking to a bus pin."""
    if mcu_role in _SIGNAL_ROLES:
        return True
    for bus in ("i2c", "uart"):
        if mcu_role.startswith(bus):
            return not partner_role.startswith(bus)
    return False


def _names_pin(code: str, pin_id: str) -> bool:
    if re.search(rf"(?<![\w.]){re.escape(pin_id)}(?![\w.])", code):
        return True
    digits = "".join(ch for ch in pin_id if ch.isdigit())
    return bool(digits) and re.search(rf"(?<![\w.]){digits}(?![\w.])", code) is not None
