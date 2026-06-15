"""Adapt catalog recipes to salvage inventory (power topology + owned modules).

Python port of apps/circuit-ai/circuit-ai-frontend/lib/salvage/inventory-topology.ts
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Set, Tuple

Wire = Dict[str, Dict[str, str]]
Recipe = Dict[str, Any]

BUCK_ROLES = frozenset({"buck", "psu", "mot_psu"})
BARREL_ID = "dc-barrel-12v"
USB_ID = "usb-power-5v"


def _has_role(modules: List[Mapping[str, str]], role: str) -> bool:
    return any(m.get("role") == role for m in modules)


def _module_id_for(modules: List[Mapping[str, str]], role: str) -> Optional[str]:
    for m in modules:
        if m.get("role") == role:
            return str(m.get("moduleId") or "")
    return None


def _drop_roles(modules: List[Dict[str, str]], roles: Set[str]) -> List[Dict[str, str]]:
    return [dict(m) for m in modules if m.get("role") not in roles]


def _drop_wires_touching_roles(wires: List[Wire], roles: Set[str]) -> List[Wire]:
    return [
        w
        for w in wires
        if w.get("from", {}).get("role") not in roles and w.get("to", {}).get("role") not in roles
    ]


def _usb_bench_load_topology(recipe: Recipe) -> Optional[Recipe]:
    modules = list(recipe.get("modules") or [])
    if _module_id_for(modules, "pwr") != BARREL_ID:
        return None
    if _has_role(modules, "mcu") or _has_role(modules, "usb"):
        return None
    buck_role = next((m.get("role") for m in modules if m.get("role") in BUCK_ROLES), None)
    if not buck_role or not _has_role(modules, "drv"):
        return None

    drop = {"pwr", str(buck_role)}
    new_modules = [{"role": "pwr", "moduleId": USB_ID}, *_drop_roles(modules, drop)]
    wires = [
        {"from": {"role": "pwr", "pin": "V+"}, "to": {"role": "drv", "pin": "VIN"}},
        {"from": {"role": "pwr", "pin": "GND"}, "to": {"role": "drv", "pin": "VIN-"}},
        {"from": {"role": "pwr", "pin": "GND"}, "to": {"role": "drv", "pin": "GND"}},
    ]
    notes = list(recipe.get("notes") or [])
    notes.append("Inventory: USB 5V salvage path — barrel and buck omitted.")
    return {"modules": new_modules, "wires": wires, "notes": notes}


def _usb_drop_high_voltage_rail(recipe: Recipe) -> Optional[Recipe]:
    modules = list(recipe.get("modules") or [])
    if _module_id_for(modules, "pwr") != BARREL_ID:
        return None
    if not _has_role(modules, "usb"):
        return None

    hv_roles = {"pwr", "svo_psu", "mot_psu"}
    new_modules = _drop_roles(modules, hv_roles)
    wires = _drop_wires_touching_roles(list(recipe.get("wires") or []), hv_roles)
    extra: List[Wire] = []
    if _has_role(new_modules, "svo"):
        extra.extend(
            [
                {"from": {"role": "usb", "pin": "V+"}, "to": {"role": "svo", "pin": "VCC"}},
                {"from": {"role": "usb", "pin": "GND"}, "to": {"role": "svo", "pin": "GND"}},
            ]
        )
        sig = next(
            (
                w
                for w in recipe.get("wires") or []
                if w.get("to", {}).get("role") == "svo" and w.get("to", {}).get("pin") == "SIG"
            ),
            None,
        )
        if sig:
            extra.append(sig)

    notes = list(recipe.get("notes") or [])
    notes.append("Inventory: USB-only — 12V barrel and HV PSU omitted.")
    return {"modules": new_modules, "wires": [*wires, *extra], "notes": notes}


def _usb_robot_topology(recipe: Recipe) -> Optional[Recipe]:
    modules = list(recipe.get("modules") or [])
    if _module_id_for(modules, "pwr") != BARREL_ID:
        return None
    if not _has_role(modules, "mot_psu") or not _has_role(modules, "usb"):
        return None

    drop = {"pwr", "mot_psu"}
    new_modules = _drop_roles(modules, drop)
    wires = _drop_wires_touching_roles(list(recipe.get("wires") or []), drop)
    extra = [
        {"from": {"role": "usb", "pin": "V+"}, "to": {"role": "drv", "pin": "VCC"}},
        {"from": {"role": "usb", "pin": "GND"}, "to": {"role": "drv", "pin": "GND"}},
    ]
    ctrl = [
        w
        for w in recipe.get("wires") or []
        if w.get("from", {}).get("role") == "mcu" and w.get("to", {}).get("role") == "drv"
    ]
    notes = list(recipe.get("notes") or [])
    notes.append("Inventory: USB-only — motor buck omitted; driver on 5V USB (small motors only).")
    return {"modules": new_modules, "wires": [*wires, *extra, *ctrl], "notes": notes}


def _prune_to_inventory(recipe: Recipe, plan: Mapping[str, Any]) -> Recipe:
    if plan.get("strategy_mode") != "constrained":
        return recipe
    resolved = plan.get("resolved_modules") or []
    owned_ids = {
        str(r.get("module_id"))
        for r in resolved
        if r.get("module_id") and r.get("source") != "unresolved"
    }
    if len(owned_ids) < 2:
        return recipe

    modules = [dict(m) for m in recipe.get("modules") or [] if m.get("moduleId") in owned_ids]
    if len(modules) < 2 or len(modules) == len(recipe.get("modules") or []):
        return recipe

    kept_roles = {m.get("role") for m in modules}
    wires = [
        w
        for w in recipe.get("wires") or []
        if w.get("from", {}).get("role") in kept_roles and w.get("to", {}).get("role") in kept_roles
    ]
    notes = list(recipe.get("notes") or [])
    notes.append(f"Inventory prune: {len(modules)}/{len(recipe.get('modules') or [])} modules from owned parts.")
    return {"modules": modules, "wires": wires, "notes": notes}


def _apply_module_overrides(recipe: Recipe, overrides: Mapping[str, str]) -> Recipe:
    if not overrides:
        return recipe
    modules = []
    for m in recipe.get("modules") or []:
        row = dict(m)
        role = str(row.get("role") or "")
        if role in overrides:
            row["moduleId"] = overrides[role]
        modules.append(row)
    return {**recipe, "modules": modules}


def adapt_recipe_to_inventory(recipe: Recipe, plan: Mapping[str, Any]) -> Tuple[Recipe, List[str]]:
    """Return recipe adapted to salvage inventory constraints."""
    notes: List[str] = []
    overrides = dict(plan.get("module_overrides") or {})

    adapted: Recipe = {
        "modules": [dict(m) for m in recipe.get("modules") or []],
        "wires": [dict(w) for w in recipe.get("wires") or []],
        "notes": list(recipe.get("notes") or []),
    }

    if plan.get("power_topology") == "usb_5v":
        for fn in (_usb_robot_topology, _usb_drop_high_voltage_rail, _usb_bench_load_topology):
            nxt = fn(adapted)
            if nxt:
                adapted = nxt
                notes.append("Applied USB 5V inventory power topology.")
                break

    adapted = _apply_module_overrides(adapted, overrides)
    adapted = _prune_to_inventory(adapted, plan)
    return adapted, notes
