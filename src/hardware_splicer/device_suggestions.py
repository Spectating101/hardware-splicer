"""Apply the first planner suggestions to a device spec.

A suggestion is a candidate repair, not an approval. This module copies the spec
and never mutates its arguments. A suggestion it cannot apply cleanly (no
candidate, a pin it cannot find, a wire it cannot match) is skipped and changes
nothing.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping


def _pin_of(plan: Mapping[str, Any], endpoint: str):
    """module.PIN as the spec writes it (a pin id or a printed name, any case) -> (module id, pin dict), or None."""
    module_id, _, name = endpoint.partition(".")
    module = next((m for m in plan["modules"] if m["id"] == module_id), None)
    if module is None:
        return None
    pin = next((p for p in module["pins"] if p["id"] == name), None) or next(
        (p for p in module["pins"] if p["name"].lower() == name.lower()), None)
    return (module_id, pin) if pin else None


def _same_pin(plan: Mapping[str, Any], endpoint: str, key: tuple[str, str]) -> bool:
    found = _pin_of(plan, endpoint)
    return found is not None and (found[0], found[1]["id"]) == key


def apply_first_suggestions(spec: Mapping[str, Any], plan: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    """Take the first candidate of each planner suggestion. Returns (new spec, whether anything changed)."""

    new_spec = copy.deepcopy(dict(spec))
    changed = False
    wires_by_id = {w["id"]: w for w in plan["wires"]}
    for finding in plan["findings"]:
        for suggestion in finding.get("suggestions", []):
            options = suggestion.get("to_one_of") or []
            if not options:
                continue
            if suggestion["action"] == "add_connection":
                pin = _pin_of(plan, suggestion["from"])
                if pin is None or any(_same_pin(plan, row[end], (pin[0], pin[1]["id"]))
                                      for row in new_spec["connections"] for end in ("from", "to")):
                    continue  # already wired (a wire the planner rejected as it stands): a replacement is the repair
                new_spec["connections"].append({"from": suggestion["from"], "to": options[0]})
                changed = True
            elif suggestion["action"] == "replace_connection":
                wire = wires_by_id.get(suggestion["wire"])
                keep = _pin_of(plan, suggestion["from"])
                if wire is None or keep is None:
                    continue
                keep_key = (keep[0], keep[1]["id"])
                ends = {(wire[end]["module"], wire[end]["pin_id"]) for end in ("from", "to")}
                for row in new_spec["connections"]:
                    keys = [_pin_of(plan, row[end]) for end in ("from", "to")]
                    if None in keys or {(k[0], k[1]["id"]) for k in keys} != ends:
                        continue
                    # the end that is not the module's own pin is the one to replace, whichever way the wire is written
                    replace = "to" if _same_pin(plan, row["from"], keep_key) else "from"
                    row[replace] = options[0]
                    changed = True
                    break
            elif suggestion["action"] == "move_signal":
                role = "i2c_scl" if suggestion["signal"] == "scl" else "i2c_sda"
                mcu_ref = options[0].split(".")[0]
                moved = False
                for row in new_spec["connections"]:
                    ends = {end: _pin_of(plan, row[end]) for end in ("from", "to")}
                    if any(found is None for found in ends.values()):
                        continue
                    for end, other in (("from", "to"), ("to", "from")):
                        if ends[end][0] == mcu_ref and role in ends[other][1]["roles"] and ends[other][0] != mcu_ref:
                            row[end] = options[0]  # every wire of this signal moves, so the bus is not split
                            moved = True
                if moved:
                    return new_spec, True  # one signal at a time, then re-plan
    return new_spec, changed
