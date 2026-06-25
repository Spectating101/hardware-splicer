"""Lower bounded topology operators into graph terminal semantics.

This is intentionally narrow. It does not replace the existing auto-wire or
netlist compiler. It adds the first bridge from `TopologyOperator` meaning into
the strict graph path so safety checks do not rely only on pin names.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Mapping

from ..pcb.module_registry import find_module
from .ir import SynthesisCandidate


SCHEMA_VERSION = "hardware_splicer.circuit_operator_lowering.v1"

MOTOR_LOAD_MODULES = {
    "dc_motor_3v_6v",
    "dc_geared_motor_12v",
    "water_pump_5v",
    "mini-pump-5v",
    "cooling_fan_5v",
    "vibration_motor",
}


@dataclass(frozen=True)
class OperatorLoweringResult:
    graph: Dict[str, Any]
    report: Dict[str, Any] = field(default_factory=dict)


def apply_operator_lowering(
    candidate: SynthesisCandidate | Mapping[str, Any],
    graph: Mapping[str, Any],
) -> OperatorLoweringResult:
    """Apply bounded operator semantics to a compiled module graph.

    The first useful semantic is H-bridge floating load terminals. Catalog motor
    modules often name one terminal `GND`, but behind an H-bridge that terminal
    is not common ground. It is a floating motor terminal. The safety checker
    must see that explicitly.
    """

    synthesis_candidate = candidate if isinstance(candidate, SynthesisCandidate) else SynthesisCandidate.from_dict(candidate)
    lowered = {
        "nodes": [dict(row) for row in graph.get("nodes") or []],
        "wires": [dict(row) for row in graph.get("wires") or []],
    }
    for key, value in graph.items():
        if key not in {"nodes", "wires"}:
            lowered[key] = value

    semantics: Dict[str, Dict[str, Any]] = {
        str(key): dict(value)
        for key, value in dict(graph.get("terminal_semantics") or {}).items()
        if isinstance(value, Mapping)
    }
    support_components: List[Dict[str, Any]] = [
        dict(row) for row in graph.get("support_components") or [] if isinstance(row, Mapping)
    ]
    topology_nets: List[Dict[str, Any]] = [
        dict(row) for row in graph.get("topology_nets") or [] if isinstance(row, Mapping)
    ]
    actions: List[Dict[str, Any]] = []

    for operator in synthesis_candidate.generated_topology:
        if operator.operator_type == "h_bridge":
            actions.extend(_lower_h_bridge(operator.to_dict(), lowered, semantics))
        elif operator.operator_type == "relay_driver":
            actions.extend(_lower_relay_driver(operator.to_dict(), lowered, semantics))
        elif operator.operator_type == "voltage_divider":
            actions.extend(_lower_voltage_divider(operator.to_dict(), support_components, topology_nets))
        elif operator.operator_type == "rc_filter":
            actions.extend(_lower_rc_filter(operator.to_dict(), support_components, topology_nets))
        elif operator.operator_type in {"pull_up", "pull_down"}:
            actions.extend(_lower_pull_resistor_network(operator.to_dict(), support_components, topology_nets))
        elif operator.operator_type == "protection_diode":
            actions.extend(_lower_protection_operator(operator.to_dict(), support_components, topology_nets))
        elif operator.operator_type in {"battery_charger", "boost_regulator", "ldo_regulator", "buck_regulator"}:
            actions.extend(_lower_power_path_operator(operator.to_dict(), support_components, topology_nets))
        elif operator.operator_type in {"adc_interface", "sensor_interface", "level_shifter", "motor_driver", "low_side_switch"}:
            actions.extend(_record_operator_only(operator.to_dict()))

    actions.extend(_apply_physical_support_lowering(synthesis_candidate, lowered, support_components))

    lowered["terminal_semantics"] = semantics
    lowered["support_components"] = support_components
    lowered["topology_nets"] = topology_nets
    lowered["topology_lowering"] = {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": synthesis_candidate.candidate_id,
        "operator_count": len(synthesis_candidate.generated_topology),
        "actions": actions,
    }
    return OperatorLoweringResult(graph=lowered, report=dict(lowered["topology_lowering"]))


def _apply_physical_support_lowering(
    candidate: SynthesisCandidate,
    graph: Dict[str, Any],
    support_components: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    operators = [operator.to_dict() for operator in candidate.generated_topology]
    operator_types = {str(operator.get("operator_type") or "") for operator in operators}
    if "voltage_divider" in operator_types or "rc_filter" in operator_types:
        actions.extend(_insert_analog_support_passives(graph, support_components))
    if "pull_up" in operator_types or "pull_down" in operator_types:
        actions.extend(_insert_pull_resistor_passives(graph, support_components))
    physical_nodes = [
        {
            "node_id": row.get("id"),
            "module_id": row.get("moduleId"),
            "support_component_id": row.get("supportComponentId"),
            "operator_id": row.get("operatorId"),
            "ref": row.get("ref"),
            "value": row.get("value"),
            "footprint": row.get("footprint"),
        }
        for row in graph.get("nodes") or []
        if row.get("supportComponentId")
    ]
    if physical_nodes:
        graph["physical_support_lowering"] = {
            "schema_version": "hardware_splicer.physical_support_lowering.v1",
            "node_count": len(physical_nodes),
            "nodes": physical_nodes,
            "boundary": "Synthetic passives are placed as review-required footprints; values and topology still require human review.",
        }
    return actions


def _insert_analog_support_passives(
    graph: Dict[str, Any],
    support_components: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    source = _find_analog_source_endpoint(graph)
    adc = _find_controller_endpoint(graph, "analog_in")
    ground = _find_controller_endpoint(graph, "gnd") or _find_any_endpoint(graph, "gnd")
    if not source or not adc or not ground:
        return []

    r_top = _support_by_role(support_components, "divider_upper_leg")
    r_bottom = _support_by_role(support_components, "divider_lower_leg")
    r_filter = _support_by_role(support_components, "rc_series_resistor")
    c_filter = _support_by_role(support_components, "rc_shunt_capacitor")
    if not r_top and not r_filter:
        return []

    _remove_wire_between(graph, source, adc)
    actions: List[Dict[str, Any]] = []

    r_top_node = _add_physical_support_node(graph, r_top, ref_prefix="R") if r_top else None
    r_bottom_node = _add_physical_support_node(graph, r_bottom, ref_prefix="R") if r_bottom else None
    r_filter_node = _add_physical_support_node(graph, r_filter, ref_prefix="R") if r_filter else None
    c_filter_node = _add_physical_support_node(graph, c_filter, ref_prefix="C") if c_filter else None

    if r_top_node and r_bottom_node:
        _wire_next(graph, source, _endpoint(r_top_node, "1"))
        _wire_next(graph, _endpoint(r_top_node, "2"), _endpoint(r_bottom_node, "1"))
        _wire_next(graph, _endpoint(r_bottom_node, "2"), ground)
        actions.extend(_physical_actions(r_top_node, r_bottom_node))
        divider_node = _endpoint(r_top_node, "2")
    else:
        divider_node = source

    if r_filter_node:
        _wire_next(graph, divider_node, _endpoint(r_filter_node, "1"))
        _wire_next(graph, _endpoint(r_filter_node, "2"), adc)
        actions.extend(_physical_actions(r_filter_node))
        filtered_node = _endpoint(r_filter_node, "2")
    elif r_top_node:
        _wire_next(graph, divider_node, adc)
        filtered_node = adc
    else:
        filtered_node = source

    if c_filter_node:
        _wire_next(graph, filtered_node, _endpoint(c_filter_node, "1"))
        _wire_next(graph, _endpoint(c_filter_node, "2"), ground)
        actions.extend(_physical_actions(c_filter_node))

    return actions


def _insert_pull_resistor_passives(
    graph: Dict[str, Any],
    support_components: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rail = _find_controller_power_out(graph) or _find_any_endpoint(graph, "power_out")
    if not rail:
        return []
    actions: List[Dict[str, Any]] = []
    for support in [row for row in support_components if row.get("role") in {"pull_up_resistor", "pull_down_resistor"}]:
        connects = [str(row).upper() for row in support.get("connects") or []]
        signal_role = "i2c_sda" if "SDA" in connects else "i2c_scl" if "SCL" in connects else "digital_io"
        signal = _find_controller_endpoint(graph, signal_role)
        target = rail if support.get("role") == "pull_up_resistor" else (_find_controller_endpoint(graph, "gnd") or _find_any_endpoint(graph, "gnd"))
        if not signal or not target:
            continue
        node = _add_physical_support_node(graph, support, ref_prefix="R")
        _wire_next(graph, signal, _endpoint(node, "1"))
        _wire_next(graph, _endpoint(node, "2"), target)
        actions.extend(_physical_actions(node))
    return actions


def _lower_h_bridge(
    operator: Mapping[str, Any],
    graph: Dict[str, Any],
    semantics: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    module_id = str((operator.get("metadata") or {}).get("module_id") or "")
    driver_nodes = _nodes_by_module(graph, module_id) if module_id else []
    load_nodes = [node for node in graph.get("nodes") or [] if str(node.get("moduleId") or "") in MOTOR_LOAD_MODULES]
    actions: List[Dict[str, Any]] = []

    for node in driver_nodes:
        spec = find_module(str(node.get("moduleId") or "")) or {}
        for pin in spec.get("pins") or []:
            if _is_h_bridge_output_pin(str(pin.get("id") or "")):
                _mark(
                    semantics,
                    node_id=str(node.get("id")),
                    pin_id=str(pin.get("id")),
                    role="floating_motor_terminal",
                    operator=operator,
                    reason="H-bridge driver output is a switched floating motor terminal.",
                )
                actions.append(
                    {
                        "action": "mark_terminal",
                        "node_id": node.get("id"),
                        "module_id": node.get("moduleId"),
                        "pin_id": pin.get("id"),
                        "role": "floating_motor_terminal",
                    }
                )

    for node in load_nodes:
        spec = find_module(str(node.get("moduleId") or "")) or {}
        for pin in spec.get("pins") or []:
            if pin.get("role") in {"power_in", "gnd"}:
                _mark(
                    semantics,
                    node_id=str(node.get("id")),
                    pin_id=str(pin.get("id")),
                    role="floating_motor_terminal",
                    operator=operator,
                    reason="Motor load terminal is floating behind H-bridge, even if catalog pin is named GND.",
                )
                actions.append(
                    {
                        "action": "mark_terminal",
                        "node_id": node.get("id"),
                        "module_id": node.get("moduleId"),
                        "pin_id": pin.get("id"),
                        "role": "floating_motor_terminal",
                    }
                )
    return actions


def _lower_voltage_divider(
    operator: Mapping[str, Any],
    support_components: List[Dict[str, Any]],
    topology_nets: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    metadata = dict(operator.get("metadata") or {})
    r_top = _positive_number(metadata.get("r_top_ohm")) or 10_000.0
    r_bottom = _positive_number(metadata.get("r_bottom_ohm")) or 10_000.0
    operator_id = str(operator.get("operator_id") or "voltage_divider")
    ratio = r_bottom / max(r_top + r_bottom, 1.0)
    source_max_v = _positive_number(metadata.get("source_max_v"))
    output_max_v = source_max_v * ratio if source_max_v is not None else None
    parts = [
        _support_component(
            operator=operator,
            ref=f"{_ref_prefix(operator_id)}_Rtop",
            component_type="resistor",
            role="divider_upper_leg",
            value={"resistance_ohm": int(r_top)},
            connects=["analog_source", "adc_safe_signal"],
            notes="Upper divider leg generated from ADC voltage constraint.",
        ),
        _support_component(
            operator=operator,
            ref=f"{_ref_prefix(operator_id)}_Rbottom",
            component_type="resistor",
            role="divider_lower_leg",
            value={"resistance_ohm": int(r_bottom)},
            connects=["adc_safe_signal", "ground"],
            notes="Lower divider leg generated from ADC voltage constraint.",
        ),
    ]
    for part in parts:
        _append_unique(support_components, part)
    _append_unique(
        topology_nets,
        _topology_net(
            operator=operator,
            name=f"{operator_id}.adc_safe_signal",
            role="scaled_analog_signal",
            connects=["divider_upper_leg", "divider_lower_leg", "controller_adc"],
            metadata={"divider_ratio": round(ratio, 5), "estimated_output_max_v": output_max_v},
        ),
    )
    return [
        {"action": "add_support_component", "operator_id": operator_id, "component_id": part["id"], "component_type": part["type"]}
        for part in parts
    ] + [
        {
            "action": "add_topology_net",
            "operator_id": operator_id,
            "net": f"{operator_id}.adc_safe_signal",
            "role": "scaled_analog_signal",
        }
    ]


def _lower_rc_filter(
    operator: Mapping[str, Any],
    support_components: List[Dict[str, Any]],
    topology_nets: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    metadata = dict(operator.get("metadata") or {})
    operator_id = str(operator.get("operator_id") or "rc_filter")
    cutoff_hz = _positive_number(metadata.get("suggested_cutoff_hz") or metadata.get("cutoff_hz"))
    r_ohm = _positive_number(metadata.get("series_r_ohm")) or 10_000.0
    c_f = _positive_number(metadata.get("shunt_c_f"))
    if c_f is None and cutoff_hz is not None:
        c_f = 1.0 / (2.0 * math.pi * r_ohm * cutoff_hz)
    c_f = c_f or 100e-9
    parts = [
        _support_component(
            operator=operator,
            ref=f"{_ref_prefix(operator_id)}_R",
            component_type="resistor",
            role="rc_series_resistor",
            value={"resistance_ohm": int(r_ohm)},
            connects=["adc_safe_signal", "filtered_adc_signal"],
            notes="Series resistor for first-order ADC noise filter.",
        ),
        _support_component(
            operator=operator,
            ref=f"{_ref_prefix(operator_id)}_C",
            component_type="capacitor",
            role="rc_shunt_capacitor",
            value={"capacitance_f": c_f, "capacitance_nf": round(c_f * 1e9, 2)},
            connects=["filtered_adc_signal", "ground"],
            notes="Shunt capacitor for first-order ADC noise filter.",
        ),
    ]
    for part in parts:
        _append_unique(support_components, part)
    _append_unique(
        topology_nets,
        _topology_net(
            operator=operator,
            name=f"{operator_id}.filtered_adc_signal",
            role="filtered_analog_signal",
            connects=["rc_series_resistor", "rc_shunt_capacitor", "controller_adc"],
            metadata={"cutoff_hz": cutoff_hz, "series_r_ohm": r_ohm, "shunt_c_f": c_f},
        ),
    )
    return [
        {"action": "add_support_component", "operator_id": operator_id, "component_id": part["id"], "component_type": part["type"]}
        for part in parts
    ] + [
        {
            "action": "add_topology_net",
            "operator_id": operator_id,
            "net": f"{operator_id}.filtered_adc_signal",
            "role": "filtered_analog_signal",
        }
    ]


def _lower_pull_resistor_network(
    operator: Mapping[str, Any],
    support_components: List[Dict[str, Any]],
    topology_nets: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    operator_id = str(operator.get("operator_id") or operator.get("operator_type") or "pull_resistor")
    op_type = str(operator.get("operator_type") or "pull_up")
    bus_count = 2 if "i2c" in operator_id.lower() else 1
    rail = "logic_rail" if op_type == "pull_up" else "ground"
    default_resistance = 4_700 if bus_count == 2 else 10_000
    actions: List[Dict[str, Any]] = []
    for index in range(bus_count):
        signal = ("SDA" if index == 0 else "SCL") if bus_count == 2 else "signal"
        part = _support_component(
            operator=operator,
            ref=f"{_ref_prefix(operator_id)}_R{index + 1}",
            component_type="resistor",
            role=f"{op_type}_resistor",
            value={"resistance_ohm": default_resistance},
            connects=[signal, rail],
            notes=f"{op_type.replace('_', '-')} resistor required unless a breakout provides it.",
        )
        _append_unique(support_components, part)
        actions.append(
            {
                "action": "add_support_component",
                "operator_id": operator_id,
                "component_id": part["id"],
                "component_type": part["type"],
            }
        )
    _append_unique(
        topology_nets,
        _topology_net(
            operator=operator,
            name=f"{operator_id}.defined_idle_level",
            role="defined_bus_idle_level",
            connects=["signal_bus", rail],
            metadata={"resistance_ohm": default_resistance, "line_count": bus_count},
        ),
    )
    actions.append(
        {
            "action": "add_topology_net",
            "operator_id": operator_id,
            "net": f"{operator_id}.defined_idle_level",
            "role": "defined_bus_idle_level",
        }
    )
    return actions


def _lower_protection_operator(
    operator: Mapping[str, Any],
    support_components: List[Dict[str, Any]],
    topology_nets: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    operator_id = str(operator.get("operator_id") or "protection")
    kind = "flyback_or_tvs_or_snubber" if _operator_text(operator).find("relay") >= 0 else "diode_or_tvs_or_clamp"
    if "adc" in _operator_text(operator):
        kind = "adc_series_resistor_or_clamp"
    part = _support_component(
        operator=operator,
        ref=f"{_ref_prefix(operator_id)}_D",
        component_type=kind,
        role="transient_or_reverse_energy_protection",
        value={"selection": "review_required"},
        connects=list(operator.get("inputs") or []) or ["protected_node", "return_or_rail"],
        notes=str(operator.get("notes") or "Protection part must be selected and polarity reviewed before power-on."),
    )
    _append_unique(support_components, part)
    _append_unique(
        topology_nets,
        _topology_net(
            operator=operator,
            name=f"{operator_id}.protected_node",
            role="protected_transient_path",
            connects=list(operator.get("inputs") or []) + list(operator.get("outputs") or []),
            metadata={"selection": kind},
        ),
    )
    return [
        {
            "action": "add_support_component",
            "operator_id": operator_id,
            "component_id": part["id"],
            "component_type": part["type"],
        },
        {
            "action": "add_topology_net",
            "operator_id": operator_id,
            "net": f"{operator_id}.protected_node",
            "role": "protected_transient_path",
        },
    ]


def _lower_power_path_operator(
    operator: Mapping[str, Any],
    support_components: List[Dict[str, Any]],
    topology_nets: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    operator_id = str(operator.get("operator_id") or operator.get("operator_type") or "power_path")
    op_type = str(operator.get("operator_type") or "power_path")
    metadata = dict(operator.get("metadata") or {})
    net = _topology_net(
        operator=operator,
        name=f"{operator_id}.power_path",
        role=op_type,
        connects=list(operator.get("inputs") or []) + list(operator.get("outputs") or []),
        metadata={key: value for key, value in metadata.items() if key in {"target_output_v", "load_current_a", "module_id"}},
    )
    _append_unique(topology_nets, net)
    actions = [
        {
            "action": "add_topology_net",
            "operator_id": operator_id,
            "net": net["name"],
            "role": op_type,
        }
    ]
    if op_type == "battery_charger":
        part = _support_component(
            operator=operator,
            ref=f"{_ref_prefix(operator_id)}_CELL",
            component_type="protected_single_cell_battery_or_protection_board",
            role="battery_safety_evidence_item",
            value={"selection": "evidence_required"},
            connects=["BAT+", "BAT-"],
            notes="Battery cell/protection is not a generic PCB module; evidence must confirm protection, polarity, and charger variant.",
        )
        _append_unique(support_components, part)
        actions.append(
            {
                "action": "add_support_component",
                "operator_id": operator_id,
                "component_id": part["id"],
                "component_type": part["type"],
            }
        )
    return actions


def _is_h_bridge_output_pin(pin_id: str) -> bool:
    text = pin_id.upper()
    return (
        text.startswith("OUT")
        or text.startswith("AOUT")
        or text.startswith("BOUT")
        or text.startswith("MOTOR")
        or text in {"M+", "M-", "AO1", "AO2", "BO1", "BO2"}
    )


def _lower_relay_driver(
    operator: Mapping[str, Any],
    graph: Dict[str, Any],
    semantics: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    module_id = str((operator.get("metadata") or {}).get("module_id") or "")
    actions: List[Dict[str, Any]] = []
    for node in _nodes_by_module(graph, module_id):
        spec = find_module(str(node.get("moduleId") or "")) or {}
        for pin in spec.get("pins") or []:
            if str(pin.get("id") or "") in {"COM", "NO", "NC", "COM1", "NO1", "NC1"}:
                _mark(
                    semantics,
                    node_id=str(node.get("id")),
                    pin_id=str(pin.get("id")),
                    role="isolated_relay_contact",
                    operator=operator,
                    reason="Relay contact terminal is isolated switched load wiring, not logic-side power.",
                )
                actions.append(
                    {
                        "action": "mark_terminal",
                        "node_id": node.get("id"),
                        "module_id": node.get("moduleId"),
                        "pin_id": pin.get("id"),
                        "role": "isolated_relay_contact",
                    }
                )
    return actions


def _record_operator_only(
    operator: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    return [
        {
            "action": "record_operator",
            "operator_id": operator.get("operator_id"),
            "operator_type": operator.get("operator_type"),
            "reason": "Operator is represented as topology/check metadata; no graph terminal rewrite was required.",
        }
    ]


def _nodes_by_module(graph: Mapping[str, Any], module_id: str) -> List[Dict[str, Any]]:
    if not module_id:
        return []
    return [dict(node) for node in graph.get("nodes") or [] if str(node.get("moduleId") or "") == module_id]


def _mark(
    semantics: Dict[str, Dict[str, Any]],
    *,
    node_id: str,
    pin_id: str,
    role: str,
    operator: Mapping[str, Any],
    reason: str,
) -> None:
    if not node_id or not pin_id:
        return
    semantics[f"{node_id}:{pin_id}"] = {
        "role": role,
        "operator_id": operator.get("operator_id"),
        "operator_type": operator.get("operator_type"),
        "reason": reason,
    }


def _support_component(
    *,
    operator: Mapping[str, Any],
    ref: str,
    component_type: str,
    role: str,
    value: Mapping[str, Any],
    connects: List[str],
    notes: str,
) -> Dict[str, Any]:
    return {
        "id": ref,
        "ref": ref,
        "type": component_type,
        "role": role,
        "operator_id": operator.get("operator_id"),
        "operator_type": operator.get("operator_type"),
        "value": dict(value),
        "connects": [str(row) for row in connects if str(row).strip()],
        "status": "review_required",
        "placement": "virtual_support_component",
        "notes": notes,
    }


def _add_physical_support_node(
    graph: Dict[str, Any],
    support: Dict[str, Any] | None,
    *,
    ref_prefix: str,
) -> Dict[str, Any] | None:
    if not support:
        return None
    existing_id = support.get("physical_node_id")
    if existing_id:
        existing = next((row for row in graph.get("nodes") or [] if row.get("id") == existing_id), None)
        return dict(existing) if isinstance(existing, Mapping) else None
    ref = _next_ref(graph, ref_prefix)
    node_id = _next_node_id(graph, "ps")
    component_type = str(support.get("type") or "")
    module_id = _physical_module_id(support)
    footprint = _physical_footprint(component_type, ref_prefix)
    value = _physical_value(support)
    node = {
        "id": node_id,
        "moduleId": module_id,
        "ref": ref,
        "value": value,
        "footprint": footprint,
        "pinIds": ["1", "2"],
        "supportComponentId": support.get("id"),
        "operatorId": support.get("operator_id"),
        "synthetic": True,
    }
    graph.setdefault("nodes", []).append(node)
    support["placement"] = "physical_synthetic_footprint"
    support["physical_node_id"] = node_id
    support["physical_ref"] = ref
    support["footprint"] = footprint
    support["physical_value"] = value
    return node


def _physical_actions(*nodes: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for node in nodes:
        if not node:
            continue
        actions.append(
            {
                "action": "add_physical_support_node",
                "node_id": node.get("id"),
                "module_id": node.get("moduleId"),
                "support_component_id": node.get("supportComponentId"),
                "ref": node.get("ref"),
                "footprint": node.get("footprint"),
            }
        )
    return actions


def _find_analog_source_endpoint(graph: Mapping[str, Any]) -> Dict[str, str] | None:
    for node in graph.get("nodes") or []:
        spec = find_module(str(node.get("moduleId") or "")) or {}
        if spec.get("category") == "mcu":
            continue
        pin = _pin_with_role(spec, "analog_in")
        if pin:
            return {"nodeId": str(node.get("id")), "pinId": pin}
    return None


def _find_controller_endpoint(graph: Mapping[str, Any], role: str) -> Dict[str, str] | None:
    for node in graph.get("nodes") or []:
        spec = find_module(str(node.get("moduleId") or "")) or {}
        if spec.get("category") != "mcu":
            continue
        pin = _pin_with_role(spec, role)
        if pin:
            return {"nodeId": str(node.get("id")), "pinId": pin}
    return None


def _find_controller_power_out(graph: Mapping[str, Any]) -> Dict[str, str] | None:
    for node in graph.get("nodes") or []:
        spec = find_module(str(node.get("moduleId") or "")) or {}
        if spec.get("category") != "mcu":
            continue
        for preferred in ("3V3", "5V"):
            if any(str(pin.get("id") or "") == preferred for pin in spec.get("pins") or []):
                return {"nodeId": str(node.get("id")), "pinId": preferred}
        pin = _pin_with_role(spec, "power_out")
        if pin:
            return {"nodeId": str(node.get("id")), "pinId": pin}
    return None


def _find_any_endpoint(graph: Mapping[str, Any], role: str) -> Dict[str, str] | None:
    for node in graph.get("nodes") or []:
        spec = find_module(str(node.get("moduleId") or "")) or {}
        pin = _pin_with_role(spec, role)
        if pin:
            return {"nodeId": str(node.get("id")), "pinId": pin}
    return None


def _pin_with_role(spec: Mapping[str, Any], role: str) -> str:
    for pin in spec.get("pins") or []:
        if pin.get("role") == role:
            return str(pin.get("id") or "")
    return ""


def _support_by_role(support_components: List[Dict[str, Any]], role: str) -> Dict[str, Any] | None:
    return next((row for row in support_components if row.get("role") == role), None)


def _remove_wire_between(graph: Dict[str, Any], a: Mapping[str, str], b: Mapping[str, str]) -> None:
    def same(endpoint: Mapping[str, Any], target: Mapping[str, str]) -> bool:
        return endpoint.get("nodeId") == target.get("nodeId") and endpoint.get("pinId") == target.get("pinId")

    graph["wires"] = [
        wire
        for wire in graph.get("wires") or []
        if not (
            (same(wire.get("from") or {}, a) and same(wire.get("to") or {}, b))
            or (same(wire.get("from") or {}, b) and same(wire.get("to") or {}, a))
        )
    ]


def _wire_next(graph: Dict[str, Any], a: Mapping[str, str], b: Mapping[str, str]) -> None:
    if not a or not b:
        return
    wire = {
        "id": _next_wire_id(graph),
        "from": {"nodeId": a.get("nodeId"), "pinId": a.get("pinId")},
        "to": {"nodeId": b.get("nodeId"), "pinId": b.get("pinId")},
    }
    graph.setdefault("wires", []).append(wire)


def _endpoint(node: Mapping[str, Any] | None, pin_id: str) -> Dict[str, str]:
    return {"nodeId": str((node or {}).get("id") or ""), "pinId": pin_id}


def _next_node_id(graph: Mapping[str, Any], prefix: str) -> str:
    used = {str(node.get("id") or "") for node in graph.get("nodes") or []}
    index = 1
    while f"{prefix}{index}" in used:
        index += 1
    return f"{prefix}{index}"


def _next_wire_id(graph: Mapping[str, Any]) -> str:
    used = {str(wire.get("id") or "") for wire in graph.get("wires") or []}
    index = 1
    while f"ws{index}" in used or f"w{index}" in used:
        index += 1
    return f"ws{index}"


def _next_ref(graph: Mapping[str, Any], prefix: str) -> str:
    used = {str(node.get("ref") or "") for node in graph.get("nodes") or []}
    index = 1
    while f"{prefix}{index}" in used:
        index += 1
    return f"{prefix}{index}"


def _physical_module_id(support: Mapping[str, Any]) -> str:
    component_type = str(support.get("type") or "")
    value = dict(support.get("value") or {})
    if component_type == "resistor":
        return f"resistor-{_format_resistance_for_id(_positive_number(value.get('resistance_ohm')) or 0)}"
    if component_type == "capacitor":
        return f"capacitor-{_format_capacitance_for_id(_positive_number(value.get('capacitance_f')) or 0)}"
    if "diode" in component_type or "clamp" in component_type:
        return "diode-review"
    return f"support-{component_type or 'component'}"


def _physical_footprint(component_type: str, ref_prefix: str) -> str:
    if component_type == "resistor" or ref_prefix == "R":
        return "Resistor_SMD:R_0603_1608Metric"
    if component_type == "capacitor" or ref_prefix == "C":
        return "Capacitor_SMD:C_0603_1608Metric"
    if "diode" in component_type or ref_prefix == "D":
        return "Diode_SMD:D_SOD-123"
    return "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"


def _physical_value(support: Mapping[str, Any]) -> str:
    value = dict(support.get("value") or {})
    if "resistance_ohm" in value:
        return _format_resistance(_positive_number(value.get("resistance_ohm")) or 0)
    if "capacitance_f" in value:
        return _format_capacitance(_positive_number(value.get("capacitance_f")) or 0)
    return str(value.get("selection") or support.get("type") or support.get("id") or "")


def _format_resistance(ohm: float) -> str:
    if ohm >= 1_000_000:
        return f"{ohm / 1_000_000:g}M"
    if ohm >= 1_000:
        return f"{ohm / 1_000:g}k"
    return f"{ohm:g}R"


def _format_resistance_for_id(ohm: float) -> str:
    return _format_resistance(ohm).replace(".", "_")


def _format_capacitance(farad: float) -> str:
    if farad >= 1e-6:
        return f"{farad * 1e6:.3g}uF"
    if farad >= 1e-9:
        return f"{farad * 1e9:.3g}nF"
    return f"{farad * 1e12:.3g}pF"


def _format_capacitance_for_id(farad: float) -> str:
    return _format_capacitance(farad).replace(".", "_")


def _topology_net(
    *,
    operator: Mapping[str, Any],
    name: str,
    role: str,
    connects: List[str],
    metadata: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "name": name,
        "role": role,
        "operator_id": operator.get("operator_id"),
        "operator_type": operator.get("operator_type"),
        "connects": [str(row) for row in connects if str(row).strip()],
        "metadata": dict(metadata or {}),
    }


def _append_unique(rows: List[Dict[str, Any]], item: Mapping[str, Any]) -> None:
    key_name = "id" if item.get("id") else "name"
    key = str(item.get(key_name) or "")
    if key and any(str(row.get(key_name) or "") == key for row in rows):
        return
    rows.append(dict(item))


def _positive_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _ref_prefix(operator_id: str) -> str:
    text = "".join(ch if ch.isalnum() else "_" for ch in operator_id.upper()).strip("_")
    return text or "TOPOLOGY"


def _operator_text(operator: Mapping[str, Any]) -> str:
    return " ".join(
        [
            str(operator.get("operator_id") or ""),
            str(operator.get("operator_type") or ""),
            str(operator.get("notes") or ""),
            " ".join(str(row) for row in operator.get("inputs") or []),
            " ".join(str(row) for row in operator.get("outputs") or []),
        ]
    ).lower()
