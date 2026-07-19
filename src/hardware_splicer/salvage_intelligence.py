"""Salvage-facing intelligence: gap analysis, shopping list, bench bring-up card."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Set

from .auto_wire import auto_wire_picked_modules
from .material_modes import allowed_purchases, resolve_material_mode
from .module_picker import pick_modules_for_goal
from .module_resolver import infer_power_topology
from .pcb.module_registry import find_module

SCHEMA_GAP = "hardware_splicer.salvage_gap_analysis.v1"
SCHEMA_BRINGUP = "hardware_splicer.bringup_card.v1"

_ROLE_LABELS = {
    "mcu": "Microcontroller",
    "sns": "Sensor",
    "drv": "Driver / switch",
    "pwr": "Power input",
    "buck": "DC-DC converter",
    "load": "Load (pump, fan, …)",
    "mot": "Motor",
    "act": "Actuator",
    "ui": "Display",
    "usb": "USB / charger",
}


def _module_ids(resolved_modules: List[Mapping[str, Any]]) -> Set[str]:
    return {str(row.get("module_id") or "").strip() for row in resolved_modules if row.get("module_id")}


def _roles_present(resolved_modules: List[Mapping[str, Any]]) -> Set[str]:
    return {str(row.get("role") or "").strip() for row in resolved_modules if row.get("role")}


def _goal_needs_power(goal: str, parts: List[Mapping[str, Any]]) -> bool:
    text = f"{goal} {' '.join(str(p.get('name') or p.get('type') or '') for p in parts)}".lower()
    return bool(re.search(r"pump|motor|fan|relay|solenoid|led strip|12v|5v|power|usb", text))


def _inventory_covers_battery_power(
    parts: List[Mapping[str, Any]],
    constraints: Mapping[str, Any] | None,
    power_topology: str | None,
) -> bool:
    """Junk-bin packs (LiPo / declared battery_voltage_v) already cover the power role."""
    constraints_map = dict(constraints or {})
    if constraints_map.get("battery_voltage_v") is not None and str(power_topology or "") in {
        "hybrid",
        "barrel_12v",
    }:
        return True
    text = " ".join(str(p.get("name") or p.get("type") or "") for p in parts).lower()
    return bool(re.search(r"\bbattery\b|lipo|li-?ion|2s\b|7\.4\s*v", text))


def _goal_needs_sensor(goal: str) -> bool:
    return bool(
        re.search(
            r"sensor|moist|temp|humid|distance|light|pressure|soil|water level|detect",
            goal,
            re.I,
        )
    )


def _goal_needs_driver(
    goal: str,
    parts: List[Mapping[str, Any]],
    module_ids: Set[str],
    resolved_modules: List[Mapping[str, Any]] | None = None,
) -> bool:
    # Donor-bound actuator_driver already covers the motor path — do not shop L298N.
    for row in resolved_modules or []:
        if str(row.get("source") or "") in {"donor_functional_salvage", "circuit_functional_salvage"}:
            if str(row.get("role") or "") == "drv" and row.get("module_id"):
                return False
    text = f"{goal} {' '.join(str(p.get('name') or p.get('type') or '') for p in parts)}".lower()
    if re.search(r"pump|motor|fan|solenoid|relay|load", text):
        driver_ids = {
            "l298n",
            "mosfet-irlz44n",
            "mosfet-irf520",
            "relay-1ch",
            "relay-1ch-5v",
            "a4988-stepper",
        }
        if module_ids & driver_ids:
            return False
        if re.search(r"mosfet|driver|relay|transistor", text):
            return False
        return True
    return False


def _module_label(module_id: str) -> str:
    spec = find_module(module_id)
    if spec:
        return str(spec.get("label") or module_id)
    return module_id


def _shopping_entry(
    module_id: str,
    *,
    reason: str,
    priority: str,
    source: str,
    in_inventory: bool,
    auto_filled: bool = False,
) -> Dict[str, Any]:
    return {
        "module_id": module_id,
        "label": _module_label(module_id),
        "reason": reason,
        "priority": priority,
        "source": source,
        "in_inventory": in_inventory,
        "auto_filled": auto_filled,
    }


def analyze_salvage_gaps(
    *,
    goal: str,
    parts: List[Mapping[str, Any]],
    resolved_modules: List[Mapping[str, Any]],
    constraints: Mapping[str, Any] | None = None,
    power_topology: str | None = None,
) -> Dict[str, Any]:
    """Compare goal + inventory vs what the design still needs."""
    constraints_map = dict(constraints or {})
    material_mode = resolve_material_mode(constraints=constraints_map, salvage_mode=True)
    inventory_ids = _module_ids(resolved_modules)
    goal_pick = pick_modules_for_goal(goal)
    goal_ids = list(goal_pick.module_ids)
    roles = _roles_present(resolved_modules)

    covered: List[Dict[str, Any]] = []
    auto_filled: List[Dict[str, Any]] = []
    shopping: List[Dict[str, Any]] = []
    still_missing: List[Dict[str, Any]] = []

    for row in resolved_modules:
        module_id = str(row.get("module_id") or "").strip()
        if not module_id:
            continue
        entry = {
            "module_id": module_id,
            "label": _module_label(module_id),
            "part_name": row.get("part_name"),
            "role": row.get("role"),
            "source": row.get("source"),
            "confidence": row.get("confidence"),
        }
        if str(row.get("source") or "") == "gap_fill":
            auto_filled.append(entry)
        else:
            covered.append(entry)

    for module_id in goal_ids:
        if module_id in inventory_ids:
            continue
        spec = find_module(module_id)
        category = str(spec.get("category") or "") if spec else ""
        role_filled = (
            (category == "mcu" and "mcu" in roles)
            or (category == "sensor" and "sns" in roles)
            or (category == "power" and roles & {"pwr", "usb", "buck"})
            or (category == "actuator" and roles & {"act", "load", "mot"})
            or (category == "driver" and "drv" in roles)
        )
        if role_filled:
            continue
        purchasable = module_id in allowed_purchases(constraints_map) or material_mode == "scratch"
        entry = _shopping_entry(
            module_id,
            reason=f"Goal picker suggests: {dict(zip(goal_pick.module_ids, goal_pick.labels)).get(module_id, module_id)}",
            priority="recommended",
            source="goal_picker",
            in_inventory=False,
        )
        if purchasable:
            shopping.append(entry)
        else:
            still_missing.append({**entry, "priority": "required", "note": "Not in inventory or allowed_purchases"})

    if "mcu" not in roles and not any(find_module(mid) and find_module(mid).get("category") == "mcu" for mid in inventory_ids):
        entry = _shopping_entry(
            "esp32-devkit",
            reason="No microcontroller resolved from declared parts",
            priority="required",
            source="role_gap",
            in_inventory=False,
        )
        if "esp32-devkit" not in inventory_ids:
            still_missing.append(entry)

    if _goal_needs_sensor(goal) and "sns" not in roles:
        mid = goal_ids[0] if goal_ids else "soil_moisture"
        for candidate in goal_ids + ["soil_moisture", "dht22"]:
            spec = find_module(candidate)
            if spec and spec.get("category") == "sensor":
                mid = candidate
                break
        if mid not in inventory_ids:
            shopping.append(
                _shopping_entry(
                    mid,
                    reason="Goal implies sensing but no sensor module is mapped",
                    priority="required",
                    source="role_gap",
                    in_inventory=False,
                )
            )

    topo_preview = power_topology or infer_power_topology(parts, resolved_modules, constraints=constraints_map)
    if (
        _goal_needs_power(goal, parts)
        and not (roles & {"pwr", "usb", "buck"})
        and not _inventory_covers_battery_power(parts, constraints_map, topo_preview)
    ):
        if "usb-power-5v" not in inventory_ids:
            shopping.append(
                _shopping_entry(
                    "usb-power-5v",
                    reason="Loads need a defined power source (USB 5V is the usual salvage default)",
                    priority="required",
                    source="power_gap",
                    in_inventory=False,
                )
            )

    if _goal_needs_driver(goal, parts, inventory_ids, resolved_modules):
        driver = "mosfet-irlz44n" if "mosfet-irlz44n" in allowed_purchases(constraints_map) else "l298n"
        if driver not in inventory_ids:
            row = _shopping_entry(
                driver,
                reason="Pump/motor/load needs a switch or driver between MCU and load",
                priority="required",
                source="driver_gap",
                in_inventory=False,
            )
            if driver in allowed_purchases(constraints_map) or material_mode == "scratch":
                shopping.append(row)
            else:
                still_missing.append(row)

    topo = power_topology or infer_power_topology(parts, resolved_modules, constraints=constraints_map)
    power_summary = _power_summary(topo, parts, constraints_map)

    # De-dupe shopping by module_id
    seen: Set[str] = set()
    deduped_shopping: List[Dict[str, Any]] = []
    for row in shopping:
        mid = str(row.get("module_id") or "")
        if mid and mid not in seen and mid not in inventory_ids:
            seen.add(mid)
            deduped_shopping.append(row)

    has_mcu = "mcu" in roles
    if not has_mcu:
        for mid in inventory_ids:
            spec = find_module(mid)
            if spec and spec.get("category") == "mcu":
                has_mcu = True
                break
    blocking = [row for row in still_missing if str(row.get("source") or "") != "goal_picker"]

    return {
        "schema_version": SCHEMA_GAP,
        "goal": goal,
        "material_mode": material_mode,
        "power_topology": topo,
        "power_summary": power_summary,
        "inventory_module_ids": sorted(inventory_ids),
        "goal_module_ids": goal_ids,
        "covered": covered,
        "auto_filled": auto_filled,
        "shopping_list": deduped_shopping,
        "still_missing": still_missing,
        "ready_to_compile": len(blocking) == 0 and has_mcu and bool(inventory_ids),
        "summary": _gap_summary(covered, auto_filled, deduped_shopping, still_missing),
    }


def _power_summary(topology: str, parts: List[Mapping[str, Any]], constraints: Mapping[str, Any]) -> str:
    budget_v = constraints.get("battery_voltage_v")
    if topology == "usb_5v":
        base = "Power from USB 5V (phone charger or power bank)."
    elif topology == "barrel_12v":
        base = "Power from barrel jack / 12V adapter."
    elif topology == "hybrid":
        base = "Mixed USB + higher-voltage path — check buck/LDO routing."
    else:
        base = f"Power topology: {topology}."
    if budget_v is not None:
        base += f" Declared rail ~{budget_v}V."
    if parts:
        names = ", ".join(str(p.get("name") or p.get("type") or "part") for p in parts[:4])
        if len(parts) > 4:
            names += ", …"
        base += f" Inventory mentions: {names}."
    return base


def _gap_summary(
    covered: List[Dict[str, Any]],
    auto_filled: List[Dict[str, Any]],
    shopping: List[Dict[str, Any]],
    missing: List[Dict[str, Any]],
) -> str:
    if missing:
        labels = ", ".join(str(r.get("label") or r.get("module_id")) for r in missing[:3])
        return f"Blocked: still need {labels}."
    if shopping:
        labels = ", ".join(str(r.get("label") or r.get("module_id")) for r in shopping[:3])
        return f"Mostly covered — consider buying: {labels}."
    if auto_filled:
        return f"Inventory covers the goal; {len(auto_filled)} part(s) were auto-added (driver, etc.)."
    return f"Inventory covers {len(covered)} mapped module(s) for this goal."


_GPIO_PIN_RE = re.compile(r"gpio|gp\d+|d\d+|a\d+", re.I)


def _module_ids_for_bringup(
    resolved_modules: List[Mapping[str, Any]],
    module_overrides: Mapping[str, str] | None,
) -> List[str]:
    overrides = dict(module_overrides or {})
    module_ids: List[str] = []
    seen: Set[str] = set()
    for row in resolved_modules:
        mid = str(row.get("module_id") or "").strip()
        if mid and mid not in seen:
            seen.add(mid)
            module_ids.append(mid)
    for mid in overrides.values():
        if mid and mid not in seen:
            seen.add(mid)
            module_ids.append(str(mid))
    return module_ids


def _connections_from_compiled_graph(build_graph: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Human hookup lines from compiled build_graph wires (authoritative after compile)."""
    nodes_by_id: Dict[str, Mapping[str, Any]] = {
        str(n.get("id")): n
        for n in (build_graph.get("nodes") or [])
        if isinstance(n, Mapping) and n.get("id") is not None
    }
    connections: List[Dict[str, Any]] = []
    for wire in build_graph.get("wires") or []:
        if not isinstance(wire, Mapping):
            continue
        src = wire.get("from") if isinstance(wire.get("from"), Mapping) else {}
        dst = wire.get("to") if isinstance(wire.get("to"), Mapping) else {}
        if not src or not dst:
            continue
        fn = nodes_by_id.get(str(src.get("nodeId"))) or {}
        tn = nodes_by_id.get(str(dst.get("nodeId"))) or {}
        fmid = str(fn.get("moduleId") or src.get("nodeId") or "")
        tmid = str(tn.get("moduleId") or dst.get("nodeId") or "")
        fp = str(src.get("pinId") or src.get("pin") or "")
        tp = str(dst.get("pinId") or dst.get("pin") or "")
        if not fp or not tp:
            continue
        connections.append(
            {
                "from": f"{_module_label(fmid)} ({fp})",
                "to": f"{_module_label(tmid)} ({tp})",
                "from_role": str(fn.get("role") or src.get("nodeId") or ""),
                "to_role": str(tn.get("role") or dst.get("nodeId") or ""),
                "from_pin": fp,
                "to_pin": tp,
                "purpose": _wire_purpose(fmid, fp, tmid, tp),
                "sourced_from_graph": True,
            }
        )
    return connections


def build_bringup_card(
    *,
    goal: str,
    resolved_modules: List[Mapping[str, Any]],
    module_overrides: Mapping[str, str] | None = None,
    power_topology: str | None = None,
    graph_input: Mapping[str, Any] | None = None,
    build_graph: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Human bench hookup sheet from resolved modules (or compiled build_graph when provided)."""
    module_ids = _module_ids_for_bringup(resolved_modules, module_overrides)
    warnings: List[str] = []
    connections: List[Dict[str, Any]] = []
    sourced_from_graph = bool(
        build_graph
        and (build_graph.get("wires") or build_graph.get("nodes"))
    )

    if sourced_from_graph:
        connections = _connections_from_compiled_graph(build_graph or {})
        if not connections:
            warnings.append("Compiled graph had no usable wires — fell back to auto-wire heuristics.")
            sourced_from_graph = False

    if not sourced_from_graph:
        specs = [find_module(mid) for mid in module_ids]
        specs = [spec for spec in specs if spec]
        recipe_modules: List[Dict[str, Any]] = []
        wires: List[Dict[str, Any]] = []
        if len(specs) >= 2:
            recipe = auto_wire_picked_modules(specs)
            recipe_modules = list(recipe.get("modules") or [])
            wires = list(recipe.get("wires") or [])
        else:
            warnings.append("Need at least two known modules for hookup lines.")

        role_labels: Dict[str, str] = {}
        role_module_ids: Dict[str, str] = {}
        for index, mod in enumerate(recipe_modules):
            role = str(mod.get("role") or f"m{index + 1}")
            module_id = str(mod.get("moduleId") or mod.get("module_id") or "")
            role_labels[role] = _module_label(module_id) if module_id else role
            role_module_ids[role] = module_id

        for wire in wires:
            src = dict(wire.get("from") or {})
            dst = dict(wire.get("to") or {})
            fr = str(src.get("role") or "")
            tr = str(dst.get("role") or "")
            fp = str(src.get("pin") or "")
            tp = str(dst.get("pin") or "")
            connections.append(
                {
                    "from": f"{role_labels.get(fr, fr)} ({fp})",
                    "to": f"{role_labels.get(tr, tr)} ({tp})",
                    "from_role": fr,
                    "to_role": tr,
                    "from_pin": fp,
                    "to_pin": tp,
                    "purpose": _wire_purpose(
                        role_module_ids.get(fr, ""), fp, role_module_ids.get(tr, ""), tp
                    ),
                }
            )

    # Donor harness reuse — keep junk connector labels in the human sheet.
    donor_harness = _donor_harness_connections(resolved_modules, graph_input)
    for row in donor_harness:
        connections.append(row)

    gpio_rows = [
        row
        for row in connections
        if _GPIO_PIN_RE.search(str(row.get("from_pin") or ""))
        or _GPIO_PIN_RE.search(str(row.get("to_pin") or ""))
    ]
    bench_checks = _bench_checks(goal, power_topology, module_ids, connections)
    if sourced_from_graph:
        bench_checks.insert(0, "Hookup lines match compiled build_graph (same pins as firmware scaffold).")
    for row in donor_harness:
        refs = row.get("connector_refs") or []
        if refs:
            bench_checks.insert(
                0 if not sourced_from_graph else 1,
                f"Keep donor harness connectors intact: {', '.join(str(r) for r in refs)} — measure before cutting.",
            )
            break

    markdown = _bringup_markdown(goal, power_topology, connections, bench_checks)

    return {
        "schema_version": SCHEMA_BRINGUP,
        "goal": goal,
        "power_topology": power_topology,
        "module_ids": module_ids,
        "connections": connections,
        "gpio_assignments": gpio_rows,
        "bench_checks": bench_checks,
        "warnings": warnings,
        "markdown": markdown,
        "donor_harness": donor_harness,
        "sourced_from_graph": sourced_from_graph,
    }


def _donor_harness_connections(
    resolved_modules: List[Mapping[str, Any]],
    graph_input: Mapping[str, Any] | None,
) -> List[Dict[str, Any]]:
    """Emit bringup lines that keep donor connector_refs (J_MOTOR_*, J_LOGIC, …)."""
    rows: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    def _add(block_name: str, refs: List[str], purpose: str) -> None:
        key = f"{block_name}|{','.join(refs)}"
        if not refs or key in seen:
            return
        seen.add(key)
        rows.append(
            {
                "from": f"Donor {block_name}",
                "to": f"Harness {', '.join(refs)}",
                "from_role": "donor",
                "to_role": "harness",
                "from_pin": refs[0],
                "to_pin": refs[-1] if len(refs) > 1 else refs[0],
                "purpose": purpose,
                "connector_refs": refs,
            }
        )

    for row in resolved_modules:
        if str(row.get("source") or "") not in {"donor_functional_salvage", "circuit_functional_salvage"}:
            continue
        refs = [str(c) for c in (row.get("connector_refs") or []) if str(c).strip()]
        name = str(row.get("donor_block_name") or row.get("part_name") or "donor block")
        _add(name, refs, "reuse donor connector — do not cut until pinout/voltage gates close")

    for block in (graph_input or {}).get("reusable_blocks") or []:
        if not isinstance(block, Mapping):
            continue
        if str(block.get("source") or "") not in {
            "circuit_functional_salvage",
            "donor_functional_salvage",
            "",
        } and str(block.get("function_type") or "") not in {
            "actuator_driver",
            "power_regulation",
            "sensor_io",
            "mechanical_motion",
        }:
            # Still take FS-shaped blocks with connector_refs.
            if not block.get("connector_refs"):
                continue
        refs = [str(c) for c in (block.get("connector_refs") or []) if str(c).strip()]
        name = str(block.get("name") or block.get("block_id") or "donor block")
        _add(name, refs, "reuse donor connector — do not cut until pinout/voltage gates close")

    return rows


def _wire_purpose(from_mod: str, from_pin: str, to_mod: str, to_pin: str) -> str:
    text = f"{from_mod} {from_pin} {to_mod} {to_pin}".lower()
    if "gnd" in text:
        return "common ground"
    if re.search(r"v\+|5v|vin|vbus|power", text):
        return "power rail"
    if re.search(r"sig|gate|in\d|pwm", text):
        return "control signal"
    if re.search(r"sda|scl|i2c", text):
        return "I2C bus"
    if re.search(r"trig|echo", text):
        return "sensor timing"
    return "signal"


def _bench_checks(
    goal: str,
    power_topology: str | None,
    module_ids: List[str],
    connections: List[Dict[str, Any]],
) -> List[str]:
    checks = [
        "Confirm common ground between MCU, driver, and load before energizing.",
        "Measure supply voltage at the load before attaching pump/motor.",
    ]
    if power_topology == "usb_5v":
        checks.append("USB source should deliver ≥1A for small pumps; use a powered hub if the host port sags.")
    if any("pump" in mid or "motor" in mid for mid in module_ids):
        checks.append("Dry-run: GPIO high → driver output ON → load sees supply (no MCU on same rail without driver).")
    if _goal_needs_sensor(goal):
        checks.append("Sensor sanity: read raw value at dry and wet (or hot/cold) before closing the control loop.")
    if not connections:
        checks.append("No auto-wires generated — verify schematic nets before bench power.")
    return checks


def _bringup_markdown(
    goal: str,
    power_topology: str | None,
    connections: List[Dict[str, Any]],
    bench_checks: List[str],
) -> str:
    lines = [
        "# Bench bring-up",
        "",
        f"**Goal:** {goal}",
        f"**Power:** {power_topology or 'unknown'}",
        "",
        "## Hookup",
        "",
    ]
    if connections:
        for row in connections:
            lines.append(f"- **{row['from']}** → **{row['to']}** — {row.get('purpose') or 'connect'}")
    else:
        lines.append("- No automatic hookup lines — open KiCad/schematic nets.")
    lines.extend(["", "## Before you power on", ""])
    for check in bench_checks:
        lines.append(f"- {check}")
    lines.append("")
    return "\n".join(lines)
