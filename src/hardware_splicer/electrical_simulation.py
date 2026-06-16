"""Power-domain simulation for module-netlist compiles (ngspice + analytical budget)."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Mapping, Optional

from .netlist.ir import CircuitNetlist
from .spice_runner import ngspice_available, run_ngspice

SCHEMA_VERSION = "hardware_splicer.electrical_simulation.v1"

_SOURCE_MODULES = {
    "usb-power-5v": ("USB_5V", 5.0, 0.9),
    "dc-barrel-12v": ("BARREL_12V", 12.0, 1.5),
    "buck-mp1584": ("BUCK", 5.0, 2.0),
    "ldo-ams1117-3v3": ("LDO_3V3", 3.3, 0.8),
}

_DEFAULT_LOAD_A: Dict[str, float] = {
    "esp32-devkit": 0.25,
    "arduino-nano": 0.08,
    "rpi-pico": 0.12,
    "dht22": 0.0025,
    "bme280": 0.001,
    "soil_moisture": 0.01,
    "relay-1ch-5v": 0.08,
    "l298n": 0.05,
    "mini-pump": 0.55,
    "mosfet-irlz44n": 0.001,
    "servo-sg90": 0.35,
    "oled-128x64": 0.02,
    "neopixel-8": 0.24,
    "esp32-cam-module": 0.4,
}

_POWER_NET_RE = re.compile(r"gnd|ground|\+?5v|v\+|vbus|3v3|3\.3", re.I)


def simulate_enabled() -> bool:
    return os.environ.get("HARDWARE_SPLICER_SIMULATE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def simulate_strict() -> bool:
    return os.environ.get("HARDWARE_SPLICER_SIM_STRICT", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _default_load_amps(module_id: Optional[str]) -> float:
    if not module_id:
        return 0.05
    return float(_DEFAULT_LOAD_A.get(str(module_id), 0.05))


def _power_nets(netlist: CircuitNetlist) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for net in netlist.nets:
        name = str(net.name or "")
        upper = name.upper()
        if upper in {"GND", "GROUND", "0"}:
            out[name] = "gnd"
        elif "+5V" in upper or upper in {"5V", "V+", "VBUS"}:
            out[name] = "+5v"
        elif "3V3" in upper or "3.3" in upper:
            out[name] = "+3v3"
    return out


def _estimate_loads(netlist: CircuitNetlist) -> List[Dict[str, Any]]:
    loads: List[Dict[str, Any]] = []
    power_nets = _power_nets(netlist)
    for comp in netlist.components:
        mid = str(comp.module_id or "")
        if mid in _SOURCE_MODULES:
            continue
        amps = _default_load_amps(mid or None)
        rail = "+5v"
        if mid in {"ldo-ams1117-3v3"}:
            rail = "+3v3"
        loads.append(
            {
                "component_ref": comp.ref,
                "module_id": mid,
                "estimated_current_a": round(amps, 4),
                "rail": rail,
            }
        )
    if not loads and netlist.components:
        loads.append(
            {
                "component_ref": "LOAD_EST",
                "module_id": "",
                "estimated_current_a": 0.1,
                "rail": "+5v",
            }
        )
    return loads


def _detect_source(netlist: CircuitNetlist) -> Dict[str, Any]:
    for comp in netlist.components:
        mid = str(comp.module_id or "")
        if mid in _SOURCE_MODULES:
            name, volts, max_a = _SOURCE_MODULES[mid]
            return {
                "module_id": mid,
                "source_name": name,
                "voltage_nominal_v": volts,
                "max_current_a": max_a,
            }
    return {
        "module_id": "implicit_usb_5v",
        "source_name": "USB_5V",
        "voltage_nominal_v": 5.0,
        "max_current_a": 0.9,
    }


def _rails_from_netlist(netlist: CircuitNetlist) -> List[Dict[str, Any]]:
    source = _detect_source(netlist)
    loads = _estimate_loads(netlist)
    total_a = sum(float(row.get("estimated_current_a") or 0.0) for row in loads)
    return [
        {
            "source": source["source_name"],
            "voltage_nominal_v": source["voltage_nominal_v"],
            "max_current_a": source["max_current_a"],
            "board_current_a": max(total_a, 1e-6),
            "voltage_drop_v": 0.05,
            "loads": loads,
        }
    ]


def _power_spice_netlist(rails: List[Dict[str, Any]]) -> str:
    if not rails:
        return "* empty\n.end\n"
    lines = ["* hardware-splicer power distribution (DC operating point)"]
    source_nodes: Dict[str, str] = {}
    for i, rail in enumerate(rails):
        src = str(rail.get("source") or f"S{i}")
        if src not in source_nodes:
            source_nodes[src] = f"NSRC{i + 1}"
            volts = float(rail.get("voltage_nominal_v") or 5.0)
            lines.append(f"V_{i + 1} {source_nodes[src]} 0 DC {volts:.6f}")
    for i, rail in enumerate(rails):
        src = str(rail.get("source") or "")
        nload = f"NLOAD{i + 1}"
        volts = max(float(rail.get("voltage_nominal_v") or 5.0), 1e-6)
        amps = max(float(rail.get("board_current_a") or 0.0), 1e-6)
        rpath = max(float(rail.get("voltage_drop_v") or 0.0) / amps, 1e-5)
        rload = max(volts / amps, 1.0)
        lines.append(f"RPATH_{i + 1} {source_nodes.get(src, '0')} {nload} {rpath:.6f}")
        lines.append(f"RLOAD_{i + 1} {nload} 0 {rload:.6f}")
    lines.extend([".op", ".end"])
    return "\n".join(lines) + "\n"


def run_electrical_simulation(
    netlist: CircuitNetlist | Mapping[str, Any],
    *,
    enabled: Optional[bool] = None,
    strict: Optional[bool] = None,
) -> Dict[str, Any]:
    """Run analytical power budget + optional ngspice .op cross-check."""
    if enabled is None:
        enabled = simulate_enabled()
    if strict is None:
        strict = simulate_strict()

    circuit = netlist if isinstance(netlist, CircuitNetlist) else CircuitNetlist.from_dict(netlist)
    rails = _rails_from_netlist(circuit)
    source = _detect_source(circuit)
    total_load_a = round(sum(float(r.get("board_current_a") or 0.0) for r in rails), 4)
    max_a = float(source.get("max_current_a") or 0.9)
    margin_a = round(max_a - total_load_a, 4)
    budget_issues: List[Dict[str, Any]] = []
    if total_load_a > max_a:
        budget_issues.append(
            {
                "severity": "error",
                "code": "power_budget_exceeded",
                "message": (
                    f"Estimated load {total_load_a:.3f}A exceeds "
                    f"{source['source_name']} budget {max_a:.3f}A."
                ),
            }
        )
    elif total_load_a > max_a * 0.85:
        budget_issues.append(
            {
                "severity": "warn",
                "code": "power_budget_tight",
                "message": (
                    f"Estimated load {total_load_a:.3f}A is tight against "
                    f"{source['source_name']} budget {max_a:.3f}A."
                ),
            }
        )

    if not enabled:
        return {
            "schema_version": SCHEMA_VERSION,
            "enabled": False,
            "skipped": True,
            "simulation_pass": None,
            "power_budget": {
                "source": source,
                "estimated_load_a": total_load_a,
                "max_current_a": max_a,
                "margin_a": margin_a,
                "issues": budget_issues,
            },
            "spice": {"ok": False, "skipped": True, "export_method": "none"},
        }

    spice_text = _power_spice_netlist(rails)
    spice = run_ngspice(netlist_text=spice_text, timeout_s=20)
    spice["netlist_preview"] = spice_text.splitlines()[:12]

    budget_ok = not any(str(i.get("severity")).lower() == "error" for i in budget_issues)
    spice_ok = bool(spice.get("ok"))
    if spice.get("error") == "ngspice_not_available":
        simulation_pass = budget_ok
        spice_skipped = True
    else:
        spice_skipped = False
        simulation_pass = budget_ok and spice_ok

    if strict and not spice_skipped and not spice_ok:
        simulation_pass = False

    return {
        "schema_version": SCHEMA_VERSION,
        "enabled": True,
        "skipped": False,
        "strict": strict,
        "ngspice_available": ngspice_available(),
        "simulation_pass": simulation_pass,
        "power_budget": {
            "source": source,
            "estimated_load_a": total_load_a,
            "max_current_a": max_a,
            "margin_a": margin_a,
            "rails": rails,
            "issues": budget_issues,
        },
        "spice": spice,
    }
