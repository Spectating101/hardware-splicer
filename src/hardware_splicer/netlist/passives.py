"""Suggest missing passives on netlist IR (rule-based, GNN-ready hook)."""

from __future__ import annotations

from typing import Any, Dict, List, Set

from .ir import CircuitNetlist


def suggest_passives(netlist: CircuitNetlist) -> List[Dict[str, Any]]:
    """Return non-blocking suggestions (pull-ups, decoupling)."""
    suggestions: List[Dict[str, Any]] = []
    comp_by_ref = netlist.component_map()

    i2c_nets: Set[str] = set()
    for net in netlist.nets:
        name = net.name.upper()
        if name in {"SDA", "SCL", "I2C_SDA", "I2C_SCL"} or "I2C" in name:
            i2c_nets.add(net.name)
    if any(
        (c.module_id or "").lower() in {"bme280", "ssd1306-128x64", "mpu6050", "bh1750"}
        or "i2c" in (c.module_id or c.value or "").lower()
        for c in netlist.components
    ):
        suggestions.append(
            {
                "kind": "i2c_pullups",
                "severity": "info",
                "message": "I2C-class sensor detected — confirm 4.7k pull-ups to VCC on SDA/SCL.",
                "nets": sorted(i2c_nets) if i2c_nets else [],
            }
        )
    elif i2c_nets:
        suggestions.append(
            {
                "kind": "i2c_pullups",
                "severity": "info",
                "message": "I2C nets detected — confirm 4.7k pull-ups to VCC on SDA/SCL (often on breakout boards).",
                "nets": sorted(i2c_nets),
            }
        )

    mcu_refs = [
        ref
        for ref, comp in comp_by_ref.items()
        if any(tok in (comp.module_id or comp.value or "").lower() for tok in ("esp32", "pico", "arduino", "mcu"))
    ]
    power_nets = {n.name for n in netlist.nets if any(x in n.name.upper() for x in ("3V3", "3.3", "VCC", "VDD"))}
    if mcu_refs and power_nets:
        has_cap = any(
            "cap" in (c.module_id or c.value or "").lower() or (c.ref or "").upper().startswith("C")
            for c in netlist.components
        )
        if not has_cap:
            suggestions.append(
                {
                    "kind": "decoupling",
                    "severity": "warning",
                    "message": "MCU without explicit decoupling capacitor in netlist — add 100nF near each IC power pin.",
                    "mcu_refs": mcu_refs,
                    "power_nets": sorted(power_nets),
                }
            )

    for net in netlist.nets:
        if net.name.upper() in {"EN", "RESET", "NRST", "GPIO0"}:
            refs = {p.component_ref for p in net.pins}
            if len(refs) == 1:
                suggestions.append(
                    {
                        "kind": "pullup",
                        "severity": "info",
                        "message": f"Net {net.name} has single connection — consider pull-up/pull-down resistor.",
                        "net": net.name,
                        "ref": next(iter(refs)),
                    }
                )

    return suggestions
