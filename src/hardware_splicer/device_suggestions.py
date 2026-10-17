"""Apply the first planner suggestions to a device spec.

A suggestion is a candidate repair, not an approval. This module copies the spec
and never mutates its arguments.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping


def apply_first_suggestions(spec: Mapping[str, Any], plan: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    """Take the first candidate of each planner suggestion. Returns (new spec, whether anything changed)."""

    new_spec = copy.deepcopy(dict(spec))
    changed = False
    wires_by_id = {w["id"]: w for w in plan["wires"]}
    for finding in plan["findings"]:
        for suggestion in finding.get("suggestions", []):
            if suggestion["action"] == "strap_address":
                endpoint = f"{suggestion['module']}.{suggestion['pin']}"
                if not suggestion["to_one_of"] or any(endpoint in (row["from"], row["to"]) for row in new_spec["connections"]):
                    continue
                new_spec["connections"].append({"from": endpoint, "to": suggestion["to_one_of"][0]})
                return new_spec, True  # one strap at a time, then re-plan
            elif suggestion["action"] == "add_connection":
                new_spec["connections"].append({"from": suggestion["from"], "to": suggestion["to_one_of"][0]})
                changed = True
            elif suggestion["action"] == "replace_connection":
                wire = wires_by_id[suggestion["wire"]]
                for row in new_spec["connections"]:
                    if suggestion["from"] in (row["from"], row["to"]) and f"{wire['to']['module']}.{wire['to']['pin']}" in (row["from"], row["to"]):
                        key = "to" if row["from"] == suggestion["from"] else "from"
                        row[key] = suggestion["to_one_of"][0]
                        changed = True
            elif suggestion["action"] == "move_signal":
                signal = "SCL" if suggestion["signal"] == "scl" else "SDA"
                if not suggestion["to_one_of"]:
                    continue
                if suggestion.get("from"):
                    for row in new_spec["connections"]:
                        for end in ("from", "to"):
                            if row[end] == suggestion["from"]:
                                row[end] = suggestion["to_one_of"][0]
                                changed = True
                    return new_spec, changed
                for row in new_spec["connections"]:
                    if row["from"].upper().endswith("." + signal):
                        row["to"] = suggestion["to_one_of"][0]
                        changed = True
                        break
                else:
                    continue
                return new_spec, changed  # one move at a time, then re-plan
    return new_spec, changed
