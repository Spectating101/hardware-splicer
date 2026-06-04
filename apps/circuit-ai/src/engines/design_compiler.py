"""Compile a high-level design description into a solvable `CircuitNetlist`.

High ROI goal: let LLM/UI produce a simple parts list (using known component IDs)
while the physics engine turns it into deterministic node/rail/load modeling.

Input schema (dict / JSON):
{
  "microcontroller": "esp32",
  "components": ["bme280", "oled_ssd1306"],
  "power_source": {"type": "usb", "voltage_v": 5.0, "current_limit_a": 0.5},
  "scenario": "max",  # or "typical"
  "pcb": {
    "vin_trace": {"length_m": 0.20, "width_m": 0.20e-3, "copper_oz": 1.0},
    "vout_trace": {"length_m": 0.10, "width_m": 0.20e-3, "copper_oz": 1.0}
  }
}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Tuple

from src.engines.circuit_physics import CircuitPhysicsEngine, ComponentType, PhysicalComponent
from src.engines.netlist import (
    CircuitNetlist,
    ConstantCurrentLoad,
    LDO,
    TraceResistor,
    TraceSpec,
    VoltageConstraint,
    VoltageSource,
)
from src.engines.power_tree_validator import PowerTreeConstraints, SourceCurrentLimit


Scenario = Literal["typical", "max"]


@dataclass(frozen=True)
class CompiledDesign:
    netlist: CircuitNetlist
    constraints: PowerTreeConstraints
    mcu: PhysicalComponent
    components: List[PhysicalComponent]
    rails: Dict[str, float]


def _get_current(comp: PhysicalComponent, scenario: Scenario) -> float:
    return comp.electrical.max_current if scenario == "max" else comp.electrical.typical_current


def compile_design(design: Dict) -> CompiledDesign:
    """Compile a design dict into a netlist + validation constraints."""

    engine = CircuitPhysicsEngine()

    mcu_id = design.get("microcontroller")
    if not mcu_id or mcu_id not in engine.component_specs:
        raise ValueError(f"Unknown microcontroller: {mcu_id}")

    component_ids = list(design.get("components") or [])
    for cid in component_ids:
        if cid not in engine.component_specs:
            raise ValueError(f"Unknown component: {cid}")

    mcu = engine.component_specs[mcu_id]
    components = [engine.component_specs[cid] for cid in component_ids]

    scenario: Scenario = design.get("scenario") or "max"
    if scenario not in ("typical", "max"):
        raise ValueError("scenario must be 'typical' or 'max'")

    power_source = design.get("power_source") or {"type": "usb"}
    ps_type = power_source.get("type", "usb")

    if ps_type == "usb":
        vbus_v = float(power_source.get("voltage_v", 5.0))
        current_limit_a = float(power_source.get("current_limit_a", 0.5))
    elif ps_type == "external":
        vbus_v = float(power_source.get("voltage_v", 5.0))
        current_limit_a = float(power_source.get("current_limit_a", 1.0))
    else:
        raise ValueError(f"Unsupported power_source.type: {ps_type}")

    # Rails
    rails: Dict[str, float] = {"VBUS": vbus_v}

    # Determine if we need a regulated 3V3 rail.
    needs_3v3 = any(abs(c.electrical.operating_voltage - 3.3) < 1e-6 for c in [mcu, *components])
    needs_regulated_3v3 = needs_3v3 and vbus_v >= 4.0

    net = CircuitNetlist()

    # Upstream source
    net.voltage_sources.append(VoltageSource(name="VUSB", n_plus="VBUS", n_minus="0", volts=vbus_v))

    # PCB traces (optional)
    pcb = design.get("pcb") or {}
    vin_trace = pcb.get("vin_trace")
    vout_trace = pcb.get("vout_trace")

    ldo_in_node = "LDO_IN"
    ldo_out_node = "V3V3"

    if needs_regulated_3v3:
        rails["V3V3"] = 3.3

        # Model upstream copper to the regulator input.
        if vin_trace:
            net.traces.append(
                TraceResistor(
                    name="VBUS_TO_LDOIN",
                    n1="VBUS",
                    n2=ldo_in_node,
                    spec=TraceSpec(
                        length_m=float(vin_trace.get("length_m", 0.05)),
                        width_m=float(vin_trace.get("width_m", 0.2e-3)),
                        copper_oz=float(vin_trace.get("copper_oz", 1.0)),
                    ),
                )
            )
        else:
            # Default: minimal drop (short/wide)
            net.traces.append(
                TraceResistor(
                    name="VBUS_TO_LDOIN",
                    n1="VBUS",
                    n2=ldo_in_node,
                    spec=TraceSpec(length_m=0.01, width_m=1.0e-3, copper_oz=1.0),
                )
            )

        # LDO itself
        net.ldos.append(
            LDO(
                name="U_LDO_3V3",
                vin=ldo_in_node,
                vout=ldo_out_node,
                gnd="0",
                vout_nom_v=3.3,
                dropout_v=float(pcb.get("ldo_dropout_v", 0.3)),
                max_current_a=float(pcb.get("ldo_max_current_a", 1.0)),
                quiescent_current_a=float(pcb.get("ldo_quiescent_current_a", 0.002)),
                r_theta_ja_c_per_w=float(pcb.get("ldo_r_theta_ja", 60.0)),
                tj_max_c=float(pcb.get("ldo_tj_max_c", 125.0)),
                ambient_c=float(pcb.get("ambient_c", 25.0)),
            )
        )

        # Optional copper drop from regulator output to the 3V3 rail load point.
        if vout_trace:
            net.traces.append(
                TraceResistor(
                    name="LDOOUT_TO_V3V3",
                    n1=ldo_out_node,
                    n2="V3V3_LOAD",
                    spec=TraceSpec(
                        length_m=float(vout_trace.get("length_m", 0.05)),
                        width_m=float(vout_trace.get("width_m", 0.2e-3)),
                        copper_oz=float(vout_trace.get("copper_oz", 1.0)),
                    ),
                )
            )
            v3v3_node = "V3V3_LOAD"
        else:
            v3v3_node = ldo_out_node

    else:
        # If the input supply is already ~3.3V, treat VBUS as the 3V3 rail (no LDO).
        if needs_3v3 and vbus_v < 4.0:
            rails["V3V3"] = vbus_v
            v3v3_node = "VBUS"
        else:
            v3v3_node = "V3V3"  # unused

    def rail_for_voltage(v: float) -> str:
        if abs(v - 5.0) < 1e-3:
            return "VBUS"
        if abs(v - 3.3) < 1e-3:
            return v3v3_node
        # If unknown, place on VBUS for now (will surface via voltage constraints)
        return "VBUS"

    # Add loads for MCU + components
    all_parts = [mcu, *components]
    for part in all_parts:
        node = rail_for_voltage(part.electrical.operating_voltage)
        amps = _get_current(part, scenario)
        net.loads_cc.append(
            ConstantCurrentLoad(
                name=part.id,
                node=node,
                amps=amps,
                gnd="0",
                min_v_off=None,
            )
        )

    # Aggregate rail constraints from component specs
    rail_limits: Dict[str, Tuple[Optional[float], Optional[float]]] = {}
    for part in all_parts:
        rail = rail_for_voltage(part.electrical.operating_voltage)
        min_v = part.electrical.min_voltage
        max_v = part.electrical.max_voltage

        cur_min, cur_max = rail_limits.get(rail, (None, None))
        new_min = min_v if cur_min is None else max(cur_min, min_v)
        new_max = max_v if cur_max is None else min(cur_max, max_v)
        rail_limits[rail] = (new_min, new_max)

    for rail, (min_v, max_v) in rail_limits.items():
        net.voltage_constraints.append(
            VoltageConstraint(
                name=f"RAIL::{rail}",
                node=rail,
                gnd="0",
                min_v=min_v,
                max_v=max_v,
                severity="error",
            )
        )

    # Power source constraints
    constraints = PowerTreeConstraints(
        source_limits=[SourceCurrentLimit(source_name="VUSB", max_current_a=current_limit_a)],
        max_trace_drop_v=float(power_source.get("max_trace_drop_v", 0.25)),
    )

    return CompiledDesign(netlist=net, constraints=constraints, mcu=mcu, components=components, rails=rails)


def spec_level_issues(design: Dict) -> List[dict]:
    """High-ROI non-netlist checks derived from component specs.

    Returns JSON-ish dicts (compatible with `SimulationIssue.__dict__`).
    """

    engine = CircuitPhysicsEngine()
    mcu_id = design.get("microcontroller")
    if not mcu_id or mcu_id not in engine.component_specs:
        return []

    mcu = engine.component_specs[mcu_id]
    component_ids = list(design.get("components") or [])
    issues: List[dict] = []

    for cid in component_ids:
        comp = engine.component_specs.get(cid)
        if comp is None:
            continue

        # Logic-level mismatch (high ROI warning)
        if comp.electrical.logic_level and mcu.electrical.logic_level:
            if comp.electrical.logic_level > mcu.electrical.logic_level + 1e-6:
                issues.append(
                    {
                        "severity": "warning",
                        "component": cid,
                        "issue": "Logic level mismatch",
                        "explanation": (
                            f"{comp.name} expects {comp.electrical.logic_level:.1f}V logic but {mcu.name} is {mcu.electrical.logic_level:.1f}V; signals may be unreliable."
                        ),
                        "physics_data": {
                            "component_logic_v": comp.electrical.logic_level,
                            "mcu_logic_v": mcu.electrical.logic_level,
                        },
                        "solution": "Add a level shifter or use a compatible component",
                    }
                )

        # Actuator external power reminder
        if comp.component_type == ComponentType.ACTUATOR and comp.electrical.max_current > 0.1:
            issues.append(
                {
                    "severity": "error",
                    "component": cid,
                    "issue": "High-current actuator needs external power",
                    "explanation": f"{comp.name} can draw up to {comp.electrical.max_current*1000:.0f}mA; do not power from MCU pins or weak rails.",
                    "physics_data": {"max_current_a": comp.electrical.max_current},
                    "solution": "Use a dedicated supply for the actuator; share GND; drive via proper driver circuitry",
                }
            )

    return issues