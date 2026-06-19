"""Adapt catalog recipes to salvage inventory (power topology + owned modules).

Python port of apps/circuit-ai/circuit-ai-frontend/lib/salvage/inventory-topology.ts
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Set, Tuple

from .pcb.module_registry import find_module, resolve_module_pads

Wire = Dict[str, Dict[str, str]]
Recipe = Dict[str, Any]

BUCK_ROLES = frozenset({"buck", "psu", "mot_psu"})
BARREL_ID = "dc-barrel-12v"
USB_ID = "usb-power-5v"
SUPPORT_MODULE_IDS = frozenset(
    {
        BARREL_ID,
        USB_ID,
        "buck-mp1584",
        "buck-lm2596",
        "ldo-ams1117-3v3",
        "ldo-ams1117-5v",
        "tp4056",
    }
)


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


def _module_pin_ids(module_id: str) -> Set[str]:
    spec = find_module(module_id) or {}
    ids = {str(pin.get("id") or "") for pin in spec.get("pins") or [] if pin.get("id")}
    pads = resolve_module_pads(module_id, spec) or []
    ids.update(str(pad.get("pinId") or "") for pad in pads if pad.get("pinId"))
    return {pin_id for pin_id in ids if pin_id}


def _module_supports_i2c(module_id: str) -> bool:
    pins = _module_pin_ids(module_id)
    return "SDA" in pins and "SCL" in pins


def _i2c_pins_for_mcu(module_id: str) -> Optional[Tuple[str, str]]:
    pins = _module_pin_ids(module_id)
    if {"GPIO21", "GPIO22"}.issubset(pins):
        return ("GPIO21", "GPIO22")
    if {"A4", "A5"}.issubset(pins):
        return ("A4", "A5")
    if {"GP0", "GP1"}.issubset(pins):
        return ("GP0", "GP1")
    return None


def _support_roles_needed_by_owned_modules(
    recipe: Recipe,
    *,
    owned_roles: Set[str],
    kept_roles: Set[str],
    topology: str,
) -> Set[str]:
    """Keep power/support modules that make a pruned salvage recipe electrically valid."""
    if topology == "usb_5v":
        return set()

    modules = list(recipe.get("modules") or [])
    module_by_role = {str(m.get("role") or ""): str(m.get("moduleId") or "") for m in modules}
    support_roles = {
        role
        for role, module_id in module_by_role.items()
        if module_id in SUPPORT_MODULE_IDS or role in {"pwr", "usb", "buck", "psu", "mot_psu"}
    }
    functional_owned_roles = owned_roles - support_roles
    needed: Set[str] = set()

    # MCU catalog recipes often use USB/5V input for logic even when a higher-voltage
    # barrel supply is present for motors.
    if "mcu" in owned_roles and "usb" in support_roles:
        needed.add("usb")

    for wire in recipe.get("wires") or []:
        from_role = str(wire.get("from", {}).get("role") or "")
        to_role = str(wire.get("to", {}).get("role") or "")
        pair = {from_role, to_role}
        if not pair & functional_owned_roles:
            continue
        needed.update(pair & support_roles)

    # If a buck/regulator is directly needed, keep its upstream source too.
    expanded = True
    while expanded:
        expanded = False
        for wire in recipe.get("wires") or []:
            from_role = str(wire.get("from", {}).get("role") or "")
            to_role = str(wire.get("to", {}).get("role") or "")
            if from_role in support_roles and to_role in needed and from_role not in kept_roles | needed:
                needed.add(from_role)
                expanded = True

    return needed


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
    owned_roles = {str(role) for role in kept_roles if role}
    support_roles = _support_roles_needed_by_owned_modules(
        recipe,
        owned_roles=owned_roles,
        kept_roles={str(role) for role in kept_roles if role},
        topology=str(plan.get("power_topology") or ""),
    )
    if support_roles:
        support_modules = [
            dict(m)
            for m in recipe.get("modules") or []
            if str(m.get("role") or "") in support_roles
            and str(m.get("role") or "") not in {str(role) for role in kept_roles if role}
        ]
        modules = [*support_modules, *modules]
        kept_roles.update(m.get("role") for m in support_modules)

    wires = [
        w
        for w in recipe.get("wires") or []
        if w.get("from", {}).get("role") in kept_roles and w.get("to", {}).get("role") in kept_roles
    ]
    notes = list(recipe.get("notes") or [])
    notes.append(f"Inventory prune: {len(modules)}/{len(recipe.get('modules') or [])} modules from owned parts.")
    if support_roles:
        notes.append("Inventory prune: kept required power/support roles for electrical validity.")
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
    adapted = _append_inventory_sensors(adapted, overrides)
    adapted = _prune_to_inventory(adapted, plan)
    return adapted, notes


def _append_inventory_sensors(recipe: Recipe, overrides: Mapping[str, str]) -> Recipe:
    """Add salvaged I2C sensor module when catalog recipe lacks that sensor."""
    sns_id = str(overrides.get("sns") or "").strip()
    modules = list(recipe.get("modules") or [])
    if not sns_id or _has_role(modules, "sns"):
        return recipe
    if any(str(m.get("moduleId") or "") == sns_id for m in modules):
        return recipe
    if not _module_supports_i2c(sns_id):
        return recipe

    new_modules = [dict(m) for m in modules]
    new_modules.append({"role": "sns", "moduleId": sns_id})
    wires = [dict(w) for w in recipe.get("wires") or []]
    mcu_id = _module_id_for(new_modules, "mcu")
    i2c_pins = _i2c_pins_for_mcu(mcu_id) if mcu_id else None
    if _has_role(new_modules, "mcu") and i2c_pins:
        sda_pin, scl_pin = i2c_pins
        wires.extend(
            [
                {"from": {"role": "mcu", "pin": sda_pin}, "to": {"role": "sns", "pin": "SDA"}},
                {"from": {"role": "mcu", "pin": scl_pin}, "to": {"role": "sns", "pin": "SCL"}},
                {"from": {"role": "mcu", "pin": "3V3"}, "to": {"role": "sns", "pin": "VCC"}},
                {"from": {"role": "mcu", "pin": "GND"}, "to": {"role": "sns", "pin": "GND"}},
            ]
        )
    elif _has_role(new_modules, "mcu"):
        notes = list(recipe.get("notes") or [])
        notes.append(f"Inventory: skipped I2C sensor wiring; MCU has no known I2C pads ({mcu_id}).")
        return {"modules": new_modules, "wires": wires, "notes": notes}
    notes = list(recipe.get("notes") or [])
    notes.append(f"Inventory: salvaged sensor wired on I2C ({sns_id}).")
    return {"modules": new_modules, "wires": wires, "notes": notes}
