"""Bounded native projection: measured top-header passive switch donors only.

This receives HS's frozen reading, not an agent's spec or embedded contract.
No catalog analogy, active driver, supply or firmware behavior is inherited.
"""
from __future__ import annotations

import copy
import math
import re
from typing import Any, Mapping

from .device_plan import DevicePlanError


def _number(value, label, low, high):
    if type(value) not in (int, float) or not low <= value <= high or not math.isfinite(value):
        raise DevicePlanError(f"donor {label} must be finite and between {low} and {high}")
    return float(value)


def _measured(fact, label):
    if not isinstance(fact, Mapping) or fact.get("grade") != "person_measurement":
        raise DevicePlanError(f"donor {label} requires an accepted matching measurement")
    return fact.get("value")


def project_donor_module(donor: Mapping[str, Any]) -> dict:
    ident = donor["donor_id"]
    if donor.get("contract_state") != "verified":
        raise DevicePlanError(f"donor {ident} contract is not verified")
    if donor.get("has_power_domains"):
        raise DevicePlanError(f"donor {ident}: powered domains are outside the passive switch scope")
    geometry_fact = donor.get("planner_geometry")
    geo = _measured(geometry_fact, f"{ident} planner_geometry")
    if geometry_fact.get("unit") not in (None, "mm"):
        raise DevicePlanError("donor planner_geometry must use millimetres")
    if not isinstance(geo, Mapping) or set(geo) != {"pcb_mm", "above_board_mm", "below_board_mm", "contacts", "connector"}:
        raise DevicePlanError("donor planner_geometry needs pcb_mm, above_board_mm, below_board_mm, contacts, connector")
    if geo["connector"] != "male_header_2_54":
        raise DevicePlanError("donor planner supports only measured top-facing male_header_2_54 contacts")
    if not isinstance(geo["pcb_mm"], Mapping) or set(geo["pcb_mm"]) != {"x", "y", "z"}:
        raise DevicePlanError("donor pcb_mm needs x, y and z")
    pcb = {k: _number(v, f"pcb_mm.{k}", 0.5, 300) for k, v in geo["pcb_mm"].items()}
    above = _number(geo["above_board_mm"], "above_board_mm", 0, 100)
    below = _number(geo["below_board_mm"], "below_board_mm", 0, 0)
    contacts = geo["contacts"]
    if not isinstance(contacts, list) or not 2 <= len(contacts) <= 5:
        raise DevicePlanError("donor geometry supports two to five measured contacts")
    pads = {}
    for contact in contacts:
        if not isinstance(contact, Mapping) or set(contact) != {"contact_id", "x_mm", "y_mm", "z_mm"}:
            raise DevicePlanError("donor contact geometry needs contact_id, x_mm, y_mm, z_mm")
        key = contact["contact_id"]
        if not isinstance(key, str) or not key or key in pads:
            raise DevicePlanError("donor geometry contact identities must be unique")
        pads[key] = {"x": _number(contact["x_mm"], "contact.x_mm", 1.27, pcb["x"] - 1.27),
                     "y": _number(contact["y_mm"], "contact.y_mm", 1.27, pcb["y"] - 1.27),
                     "tip_mm": _number(contact["z_mm"], "contact.z_mm", pcb["z"], pcb["z"] + above)}
    if len({(p["x"], p["y"]) for p in pads.values()}) != len(pads):
        raise DevicePlanError("donor contacts must not occupy the same position")
    points = list(pads.values())
    if any(max(abs(a["x"]-b["x"]), abs(a["y"]-b["y"])) < 2.54 - 1e-6
           for i, a in enumerate(points) for b in points[i+1:]):
        raise DevicePlanError("donor contact housings overlap in the supported 2.54 mm connector geometry")
    pins, switches, grounds = [], 0, 0
    for signal in donor.get("signals", []):
        name = signal["name"]
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,39}", name):
            raise DevicePlanError("donor signal names must be unambiguous endpoint identifiers")
        protocol = _measured(signal.get("protocol"), f"{name}.protocol")
        if signal.get("voltage_max_v", {}).get("unit") not in (None, "V"):
            raise DevicePlanError("donor voltage_max_v must use volts")
        vmax = _number(_measured(signal.get("voltage_max_v"), f"{name}.voltage_max_v"), "voltage_max_v", 0, 60)
        if protocol == "ground_reference" and signal["direction"] == "passive" and vmax == 0:
            role, grounds = "ground", grounds + 1
            extra = {}
        elif protocol == "switch_to_ground" and signal["direction"] == "output":
            if _measured(signal.get("active_level"), f"{name}.active_level") != "low" or vmax < 3.3:
                raise DevicePlanError("donor switch must be active-low and rated for the proposed 3.3 V logic topology")
            controller_pin = _measured(signal.get("controller_pin"), f"{name}.controller_pin")
            if not isinstance(controller_pin, str) or not controller_pin:
                raise DevicePlanError("donor controller_pin must identify a pin")
            role, switches = "donor_switch", switches + 1
            extra = {"controller_pin": controller_pin}
        else:
            raise DevicePlanError(f"donor {name}: only measured switch_to_ground/ground_reference protocols are supported")
        contact = signal.get("contact_id")
        if contact not in pads:
            raise DevicePlanError(f"donor {name} has no measured contact geometry")
        pins.append({"id": name, "name": name, "number": contact, "roles": [role], **pads[contact], **extra})
    if grounds != 1 or not 1 <= switches <= 4 or len(pins) != len(pads):
        raise DevicePlanError("donor scope requires exactly one ground and one to four distinct switch contacts")
    if len({s.get("contact_id") for s in donor["signals"]}) != len(pins):
        raise DevicePlanError("donor signals must not alias one physical contact")
    return {"id": ident, "name": donor["label"], "kind": "donor_passive", "pcb_mm": pcb,
            "above_board_mm": above, "below_board_mm": below, "header_face": "above", "pins": pins,
            "pin_pitch_mm": 2.54, "pin_numbering_from": "the measured donor contact identity",
            "sources": [{"label": "Frozen project donor contract", "url": "donor-contract:" + ident}],
            "dimension_basis": {"source": "project dimensional evidence", "evidence_ids": geometry_fact["evidence_ids"]},
            "donor_evidence": copy.deepcopy(donor),
            "engineering": {"gaps": ["Donor contact ratings, actuation life, debounce and MCU input configuration are not modeled."]},
            "notes": ["Passive contact topology proposal only; no donor firmware, actuation or power-on authority is generated."]}


def mission_donor_modules(view: Mapping, spec: Mapping) -> dict:
    """Build context only for explicitly placed donor modules from this mission's frozen reading."""
    modules = spec.get("modules")
    ids = [m.get("module") for m in (modules if isinstance(modules, list) else []) if isinstance(m, Mapping)
           and isinstance(m.get("module"), str) and m["module"].startswith("donor:")]
    if len(set(ids)) != len(ids):
        raise DevicePlanError("a physical donor block may not be placed more than once")
    used = set(spec.get("donors_used") or [])
    if ids and set(ids) != used:
        raise DevicePlanError("wired donor modules must cover exactly donors_used; tracking references are not implementation")
    by_id = {d["donor_id"]: d for d in view.get("donors", [])}
    result = {}
    for ident in ids:
        if ident not in by_id:
            raise DevicePlanError(f"donor {ident} has no frozen HS donor_read")
        result[ident] = project_donor_module(by_id[ident])
    return result
