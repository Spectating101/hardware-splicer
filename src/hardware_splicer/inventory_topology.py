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
    # ESP32-CAM has no dedicated I2C pads in the catalog — soft-I2C on free GPIOs.
    if module_id == "esp32-cam-module" and {"GPIO14", "GPIO15"}.issubset(pins):
        return ("GPIO14", "GPIO15")
    return None


def _mcu_power_in_pin(module_id: str) -> str:
    pins = _module_pin_ids(module_id)
    for candidate in ("VIN", "VBUS", "5V", "VSYS"):
        if candidate in pins:
            return candidate
    return "VIN"


def _mcu_pin_aliases(module_id: str) -> Dict[str, str]:
    """Map recipe Arduino-style pins onto the overridden MCU's real pads."""
    pins = _module_pin_ids(module_id)
    aliases: Dict[str, str] = {}
    power = _mcu_power_in_pin(module_id)
    if "VIN" not in pins and power != "VIN":
        aliases["VIN"] = power
    if "VBUS" not in pins and power != "VBUS":
        aliases["VBUS"] = power
    if "D2" not in pins:
        gpio_pool = [p for p in ("GPIO12", "GPIO13", "GPIO14", "GPIO15", "GPIO4", "GPIO2") if p in pins]
        for src, dst in zip(("D2", "D3", "D4", "D5", "D6", "D7"), gpio_pool):
            aliases[src] = dst
    return aliases


def _remap_recipe_pins_for_modules(recipe: Recipe) -> Recipe:
    """Rewrite recipe wire pin ids after module_overrides (e.g. Nano → ESP32-CAM)."""
    modules = list(recipe.get("modules") or [])
    mcu_id = _module_id_for(modules, "mcu")
    if not mcu_id:
        return recipe
    aliases = _mcu_pin_aliases(mcu_id)
    if not aliases and mcu_id != "esp32-cam-module":
        return recipe

    wires: List[Wire] = []
    for wire in recipe.get("wires") or []:
        row = {
            "from": dict(wire.get("from") or {}),
            "to": dict(wire.get("to") or {}),
        }
        for end in ("from", "to"):
            if row[end].get("role") != "mcu":
                continue
            pin = str(row[end].get("pin") or "")
            if pin in aliases:
                row[end]["pin"] = aliases[pin]
        wires.append(row)

    drv_id = _module_id_for(modules, "drv")
    drv_pins = _module_pin_ids(drv_id) if drv_id else set()
    mcu_pins = _module_pin_ids(mcu_id)
    to_drv = {
        str(w.get("to", {}).get("pin") or "")
        for w in wires
        if w.get("from", {}).get("role") == "mcu" and w.get("to", {}).get("role") == "drv"
    }
    notes = list(recipe.get("notes") or [])
    if {"IN3", "IN4"}.issubset(drv_pins) and "IN3" not in to_drv:
        used = {
            str(w.get("from", {}).get("pin") or "")
            for w in wires
            if w.get("from", {}).get("role") == "mcu"
        }
        candidates = [
            p for p in ("GPIO14", "GPIO15", "GPIO4", "GPIO2", "D4", "D5") if p in mcu_pins and p not in used
        ]
        # Prefer aliased names already remapped.
        candidates = [aliases.get(p, p) for p in candidates]
        candidates = [p for p in candidates if p in mcu_pins and p not in used]
        if len(candidates) >= 2:
            wires.append({"from": {"role": "mcu", "pin": candidates[0]}, "to": {"role": "drv", "pin": "IN3"}})
            wires.append({"from": {"role": "mcu", "pin": candidates[1]}, "to": {"role": "drv", "pin": "IN4"}})
            notes.append("Inventory: dual H-bridge channel B wired (IN3/IN4).")

    if aliases:
        notes.append(f"Inventory: remapped MCU pins for {mcu_id}: {aliases}")
    return {**recipe, "wires": wires, "notes": notes}


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


def _alias_overrides_for_recipe(recipe: Recipe, overrides: Mapping[str, str]) -> Dict[str, str]:
    """Map inventory roles onto catalog recipe roles (pwr→usb, relay→rly, act→svo)."""
    out = dict(overrides)
    recipe_roles = {str(m.get("role") or "") for m in (recipe.get("modules") or [])}
    if "usb" in recipe_roles:
        if out.get("usb") == "usb-uart" and out.get("pwr") == USB_ID:
            out["usb"] = USB_ID
        if "usb" not in out and out.get("pwr") == USB_ID:
            out["usb"] = USB_ID
    if "rly" in recipe_roles and "rly" not in out:
        for key in ("relay", "drv"):
            mid = str(out.get(key) or "")
            if mid.startswith("relay"):
                out["rly"] = mid
                break
    if "svo" in recipe_roles and "svo" not in out and out.get("act") in {"sg90", "mg996r"}:
        out["svo"] = str(out["act"])
    return out


def _rewrite_mcu_5v_loads_to_usb(recipe: Recipe) -> Recipe:
    """ESP32 has no 5V out pin — feed relay/sensor 5V loads from USB rail instead."""
    modules = list(recipe.get("modules") or [])
    mcu_id = _module_id_for(modules, "mcu")
    if not mcu_id or "5V" in _module_pin_ids(mcu_id):
        return recipe
    if not _has_role(modules, "usb"):
        return recipe
    wires = []
    changed = False
    for wire in recipe.get("wires") or []:
        fr = dict(wire.get("from") or {})
        if fr.get("role") == "mcu" and fr.get("pin") == "5V":
            wires.append({"from": {"role": "usb", "pin": "V+"}, "to": dict(wire.get("to") or {})})
            changed = True
        else:
            wires.append({"from": fr, "to": dict(wire.get("to") or {})})
    if not changed:
        return recipe
    notes = list(recipe.get("notes") or [])
    notes.append("Inventory: MCU has no 5V pin — loads fed from USB V+.")
    return {**recipe, "wires": wires, "notes": notes}


def _usb_pan_tilt_topology(recipe: Recipe, plan: Mapping[str, Any]) -> Recipe | None:
    """USB-only pan-tilt: drop 12V barrel/LDO/OLED; power servos from USB; keep dual SG90."""
    if _module_id_for(list(recipe.get("modules") or []), "pwr") != BARREL_ID:
        return None
    if not _has_role(list(recipe.get("modules") or []), "svo"):
        return None
    overrides = dict(plan.get("module_overrides") or {})
    if overrides.get("mcu") not in {"esp32-devkit", "esp32-cam-module", "arduino-nano"} and not any(
        str(r.get("module_id") or "") in {"esp32-devkit", "esp32-cam-module", "arduino-nano"}
        for r in (plan.get("resolved_modules") or [])
    ):
        # Still OK for pico-on-USB; only require USB present in inventory.
        pass
    has_usb_inv = any(
        str(r.get("module_id") or "") == USB_ID for r in (plan.get("resolved_modules") or [])
    ) or overrides.get("usb") == USB_ID or overrides.get("pwr") == USB_ID
    if not has_usb_inv and plan.get("power_topology") not in {"usb_5v", "hybrid"}:
        return None

    drop = {"pwr", "svo_psu", "ui"}
    modules = [dict(m) for m in recipe.get("modules") or [] if str(m.get("role") or "") not in drop]
    if not _has_role(modules, "usb"):
        modules.insert(0, {"role": "usb", "moduleId": USB_ID})
    # Prefer inventory MCU (ESP32) over catalog Pico when present.
    inv_mcu = overrides.get("mcu") or next(
        (
            str(r.get("module_id") or "")
            for r in (plan.get("resolved_modules") or [])
            if str(r.get("role") or "") == "mcu" and r.get("module_id")
        ),
        "",
    )
    if inv_mcu:
        if _has_role(modules, "mcu"):
            for mod in modules:
                if str(mod.get("role") or "") == "mcu":
                    mod["moduleId"] = inv_mcu
                    break
        else:
            modules.append({"role": "mcu", "moduleId": inv_mcu})
    # Ensure at least one servo; add second from inventory if present.
    servo_count = sum(
        1
        for r in (plan.get("resolved_modules") or [])
        if str(r.get("module_id") or "") in {"sg90", "mg996r"}
    )
    if servo_count >= 2 and not _has_role(modules, "svo2"):
        modules.append({"role": "svo2", "moduleId": overrides.get("svo") or overrides.get("act") or "sg90"})

    mcu_id = _module_id_for(modules, "mcu") or inv_mcu or "esp32-devkit"
    power_pin = _mcu_power_in_pin(mcu_id)
    pin_ids = _module_pin_ids(mcu_id)
    gpio_candidates = [
        p
        for p in ("GPIO18", "GPIO19", "GPIO16", "GPIO17", "GPIO25", "GPIO26", "GPIO12", "GPIO13", "GPIO14", "GPIO15")
        if p in pin_ids
    ]
    if len(gpio_candidates) >= 2:
        sig_pins = gpio_candidates[:2]
    elif "GP0" in pin_ids and "GP1" in pin_ids:
        sig_pins = ["GP0", "GP1"]
    elif "D2" in pin_ids and "D3" in pin_ids:
        sig_pins = ["D2", "D3"]
    else:
        sig_pins = gpio_candidates + ["GPIO18", "GPIO19"]
    wires: List[Wire] = [
        {"from": {"role": "usb", "pin": "V+"}, "to": {"role": "mcu", "pin": power_pin}},
        {"from": {"role": "usb", "pin": "GND"}, "to": {"role": "mcu", "pin": "GND"}},
        {"from": {"role": "usb", "pin": "V+"}, "to": {"role": "svo", "pin": "VCC"}},
        {"from": {"role": "usb", "pin": "GND"}, "to": {"role": "svo", "pin": "GND"}},
        {"from": {"role": "mcu", "pin": sig_pins[0]}, "to": {"role": "svo", "pin": "SIG"}},
    ]
    if _has_role(modules, "svo2"):
        wires.extend(
            [
                {"from": {"role": "usb", "pin": "V+"}, "to": {"role": "svo2", "pin": "VCC"}},
                {"from": {"role": "usb", "pin": "GND"}, "to": {"role": "svo2", "pin": "GND"}},
                {"from": {"role": "mcu", "pin": sig_pins[1]}, "to": {"role": "svo2", "pin": "SIG"}},
            ]
        )
    notes = list(recipe.get("notes") or [])
    notes.append("Inventory: USB-only pan-tilt — barrel/LDO/OLED omitted; servos on USB 5V.")
    return {"modules": modules, "wires": wires, "notes": notes}


def adapt_recipe_to_inventory(recipe: Recipe, plan: Mapping[str, Any]) -> Tuple[Recipe, List[str]]:
    """Return recipe adapted to salvage inventory constraints."""
    notes: List[str] = []
    overrides = dict(plan.get("module_overrides") or {})

    adapted: Recipe = {
        "modules": [dict(m) for m in recipe.get("modules") or []],
        "wires": [dict(w) for w in recipe.get("wires") or []],
        "notes": list(recipe.get("notes") or []),
    }

    # USB pan-tilt before USB HV-drop — catalog recipe is 12V+Pico+OLED heavy.
    pan = _usb_pan_tilt_topology(adapted, {**dict(plan), "module_overrides": overrides})
    if pan:
        adapted = pan
        notes.append("Applied USB pan-tilt inventory topology.")
    elif plan.get("power_topology") == "usb_5v":
        for fn in (_usb_robot_topology, _usb_drop_high_voltage_rail, _usb_bench_load_topology):
            nxt = fn(adapted)
            if nxt:
                adapted = nxt
                notes.append("Applied USB 5V inventory power topology.")
                break

    overrides = _alias_overrides_for_recipe(adapted, overrides)
    adapted = _apply_module_overrides(adapted, overrides)
    adapted = _remap_recipe_pins_for_modules(adapted)
    adapted = _rewrite_mcu_5v_loads_to_usb(adapted)
    adapted = _rewrite_i2c_sensor_to_dht(adapted, overrides)
    adapted = _append_inventory_sensors(adapted, overrides)
    adapted = _prune_to_inventory(adapted, plan)
    return adapted, notes


def _rewrite_i2c_sensor_to_dht(recipe: Recipe, overrides: Mapping[str, str]) -> Recipe:
    """sensor_logger recipe is BME280/I2C — retarget wires when inventory is DHT22."""
    sns_id = str(overrides.get("sns") or _module_id_for(list(recipe.get("modules") or []), "sns") or "")
    if sns_id not in {"dht22", "dht11"}:
        return recipe
    mcu_id = _module_id_for(list(recipe.get("modules") or []), "mcu") or ""
    data_pin = "GPIO4"
    if "GPIO16" in _module_pin_ids(mcu_id):
        data_pin = "GPIO16"
    elif "D2" in _module_pin_ids(mcu_id):
        data_pin = "D2"
    wires: List[Wire] = []
    for wire in recipe.get("wires") or []:
        to_role = str((wire.get("to") or {}).get("role") or "")
        from_role = str((wire.get("from") or {}).get("role") or "")
        if to_role == "sns" or from_role == "sns":
            continue
        wires.append({"from": dict(wire.get("from") or {}), "to": dict(wire.get("to") or {})})
    if _has_role(list(recipe.get("modules") or []), "sns") and _has_role(
        list(recipe.get("modules") or []), "mcu"
    ):
        vcc_from = {"role": "mcu", "pin": "3V3"} if "3V3" in _module_pin_ids(mcu_id) else {"role": "usb", "pin": "V+"}
        wires.extend(
            [
                {"from": vcc_from, "to": {"role": "sns", "pin": "VCC"}},
                {"from": {"role": "mcu", "pin": "GND"}, "to": {"role": "sns", "pin": "GND"}},
                {"from": {"role": "mcu", "pin": data_pin}, "to": {"role": "sns", "pin": "DATA"}},
            ]
        )
    notes = list(recipe.get("notes") or [])
    notes.append(f"Inventory: retargeted sensor wiring for {sns_id} on {data_pin}.")
    return {**recipe, "wires": wires, "notes": notes}


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

    mcu_id = _module_id_for(modules, "mcu")
    i2c_pins = _i2c_pins_for_mcu(mcu_id) if mcu_id else None
    mcu_pins = _module_pin_ids(mcu_id) if mcu_id else set()
    notes = list(recipe.get("notes") or [])
    used_mcu_pins = {
        str(w.get("from", {}).get("pin") or "")
        for w in (recipe.get("wires") or [])
        if w.get("from", {}).get("role") == "mcu"
    }
    used_mcu_pins |= {
        str(w.get("to", {}).get("pin") or "")
        for w in (recipe.get("wires") or [])
        if w.get("to", {}).get("role") == "mcu"
    }

    if not (_has_role(modules, "mcu") and i2c_pins):
        notes.append(f"Inventory: skipped I2C sensor wiring; MCU has no known I2C pads ({mcu_id}).")
        return {**recipe, "notes": notes}

    sda_pin, scl_pin = i2c_pins
    if sda_pin in used_mcu_pins or scl_pin in used_mcu_pins:
        notes.append(
            f"Inventory: kept {sns_id} in salvage inventory; MCU GPIOs already claimed by drive wiring."
        )
        return {**recipe, "notes": notes}

    new_modules = [dict(m) for m in modules]
    new_modules.append({"role": "sns", "moduleId": sns_id})
    wires = [dict(w) for w in recipe.get("wires") or []]
    wires.extend(
        [
            {"from": {"role": "mcu", "pin": sda_pin}, "to": {"role": "sns", "pin": "SDA"}},
            {"from": {"role": "mcu", "pin": scl_pin}, "to": {"role": "sns", "pin": "SCL"}},
            {"from": {"role": "mcu", "pin": "GND"}, "to": {"role": "sns", "pin": "GND"}},
        ]
    )
    if "3V3" in mcu_pins:
        wires.append({"from": {"role": "mcu", "pin": "3V3"}, "to": {"role": "sns", "pin": "VCC"}})
    elif _has_role(new_modules, "usb"):
        wires.append({"from": {"role": "usb", "pin": "V+"}, "to": {"role": "sns", "pin": "VCC"}})
        notes.append("Inventory: sensor VCC from USB 5V (MCU has no 3V3 pad).")
    else:
        notes.append(f"Inventory: sensor {sns_id} lacks a VCC source on this MCU topology.")
        return {**recipe, "notes": notes}
    if mcu_id == "esp32-cam-module":
        notes.append("Inventory: ESP32-CAM soft-I2C on GPIO14/GPIO15 for salvaged sensor.")
    notes.append(f"Inventory: salvaged sensor wired on I2C ({sns_id}).")
    return {"modules": new_modules, "wires": wires, "notes": notes}
