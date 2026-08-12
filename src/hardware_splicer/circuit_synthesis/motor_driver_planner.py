"""Bounded motor/pump driver topology planner.

Electrical ratings are read only from structured catalog/component contracts. Human-facing
module summaries, warnings and magic per-module rating tables are not engineering truth.
When a rating or threshold is absent, the candidate remains blocked on explicit evidence.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Sequence

from ..electrical_contract_truth import (
    contract_snapshot,
    exact_output_voltage_v,
    integrated_inductive_protection,
    is_h_bridge_interface,
    is_level_shifter_interface,
    is_low_side_switch_interface,
    is_mcu,
    is_motor_or_load,
    is_power_source,
    logic_input_min_v,
    max_output_current_a,
)
from ..pcb.module_registry import find_module
from .ir import CircuitIntent, Constraint, SynthesisCandidate, TopologyOperator


CURRENT_MARGIN_MULTIPLIER = 1.25
PROTECTION_EVIDENCE = {
    "flyback_or_driver_protection",
    "flyback_or_tvs",
    "protection_diode",
    "driver_integrated_clamp",
}


def plan_motor_driver(intent: CircuitIntent | Mapping[str, Any]) -> SynthesisCandidate:
    """Plan one bounded DC motor/pump driver topology from declared structured truth.

    The planner never emits a production-ready claim. It may select a uniquely declared
    interface shape, but precise current ratings, logic thresholds and protection claims
    must come from machine-readable component contracts or explicit evidence. Unknowns
    stay unknown.
    """

    circuit_intent = intent if isinstance(intent, CircuitIntent) else CircuitIntent.from_dict(intent)
    available = _available_module_ids(circuit_intent)
    evidence = set(circuit_intent.required_evidence)
    evidence.update(
        str(row.get("id") or row.get("type") or "")
        for row in circuit_intent.allowed_parts
        if row.get("evidence")
    )

    load = _first_load(circuit_intent)
    signal = _first_signal(circuit_intent)
    supply = _first_supply(circuit_intent, available)
    constraints: List[Constraint] = []
    assumptions: List[str] = []
    missing: List[str] = []
    selected_modules: List[str] = []
    selected_parts: List[Dict[str, Any]] = []
    topology: List[TopologyOperator] = []

    load_current_a = _float_or_none(
        load.get("current_a") or load.get("run_current_a") or load.get("stall_current_a")
    )
    load_voltage_v = _float_or_none(load.get("voltage_v")) or _float_or_none(supply.get("voltage_v"))
    control_voltage_v = _float_or_none(signal.get("voltage_v"))
    supply_current_a = _float_or_none(supply.get("max_current_a") or supply.get("current_limit_a"))

    if not load:
        missing.append("load_requirement")
        constraints.append(
            _blocked("load_requirement", "measurement_required", "load", "Declare the motor/pump load.")
        )
    if load and load_current_a is None:
        missing.append("load_current_estimate")
        constraints.append(
            _blocked(
                "load_current_estimate",
                "measurement_required",
                "load_current",
                "Measure or estimate motor run/stall current.",
            )
        )
    if not supply:
        missing.append("supply_rail")
        constraints.append(
            _blocked(
                "supply_rail",
                "voltage",
                "supply",
                "Declare the motor supply rail or provide one unambiguous structured power source.",
            )
        )
    if supply and _float_or_none(supply.get("voltage_v")) is None:
        missing.append("supply_voltage")
        constraints.append(
            _blocked(
                "supply_voltage",
                "voltage",
                "supply",
                "Power source output voltage is not an exact structured contract value; declare the configured rail.",
                value={"source": supply.get("name"), "provenance": supply.get("source")},
            )
        )
    if supply and supply_current_a is None:
        missing.append("supply_current_limit")
        constraints.append(
            _blocked(
                "supply_current_limit",
                "current",
                "supply",
                "Supply current limit is absent from structured evidence; declare or measure it.",
                value={"source": supply.get("name"), "provenance": supply.get("source")},
            )
        )
    if not signal:
        missing.append("control_signal")
        constraints.append(
            _blocked("control_signal", "logic_level", "control", "Declare MCU control voltage.")
        )
    if signal and control_voltage_v is None:
        missing.append("control_signal_voltage")
        constraints.append(
            _blocked("control_signal_voltage", "logic_level", "control", "Declare MCU control voltage.")
        )

    if load_current_a is not None and supply_current_a is not None:
        if supply_current_a < load_current_a:
            missing.append("supply_current_margin")
            constraints.append(
                _blocked(
                    "supply_current_margin",
                    "current",
                    "supply",
                    "Supply current limit must exceed estimated load current.",
                    value={"supply_current_a": supply_current_a, "load_current_a": load_current_a},
                )
            )
        else:
            constraints.append(
                _passed(
                    "supply_current_margin",
                    "current",
                    "supply",
                    "Supply current limit covers estimated load current.",
                    value={"supply_current_a": supply_current_a, "load_current_a": load_current_a},
                )
            )

    driver_id, switch_id, interface_ambiguity = _select_driver_interface(available)
    if interface_ambiguity:
        missing.append("driver_topology_choice")
        constraints.append(
            _blocked(
                "driver_topology_choice",
                "architecture",
                "driver",
                "Multiple declared driver interface families are available; choose the intended topology explicitly.",
                value=interface_ambiguity,
            )
        )

    selected_driver = driver_id or switch_id
    if driver_id:
        selected_modules.append(driver_id)
        rating = max_output_current_a(driver_id)
        topology.append(
            TopologyOperator(
                operator_id=f"{driver_id}_motor_driver",
                operator_type="motor_driver",
                inputs=["motor_supply", "control_signal", "ground"],
                outputs=["motor_out_a", "motor_out_b"],
                required_part_types=["motor_driver", "dc_motor_or_pump"],
                required_ports=["VCC", "GND", "IN1", "IN2", "OUT1", "OUT2"],
                notes=f"{driver_id} selected from its declared H-bridge interface shape.",
                metadata={
                    "current_rating_a": rating,
                    "module_id": driver_id,
                    "rating_source": "structured_catalog_contract" if rating is not None else "unresolved",
                },
            )
        )
        _check_current_rating(
            driver_id,
            rating,
            load_current_a,
            constraint_id="driver_current_rating",
            label="Driver",
            constraints=constraints,
            missing=missing,
        )
        _check_logic_level(
            driver_id,
            logic_input_min_v(driver_id),
            control_voltage_v,
            available,
            constraints,
            missing,
        )
    elif switch_id:
        selected_modules.append(switch_id)
        rating = max_output_current_a(switch_id)
        topology.append(
            TopologyOperator(
                operator_id=f"{switch_id}_low_side_switch",
                operator_type="low_side_switch",
                inputs=["motor_supply", "control_signal", "ground"],
                outputs=["switched_load_return"],
                required_part_types=["logic_level_mosfet", "dc_motor_or_pump"],
                required_ports=["VIN", "VIN-", "SIG", "GND", "VOUT+", "VOUT-"],
                missing_evidence_conditions=["flyback_or_driver_protection"],
                notes=f"{switch_id} selected from its declared low-side-switch interface shape.",
                metadata={
                    "current_rating_a": rating,
                    "module_id": switch_id,
                    "rating_source": "structured_catalog_contract" if rating is not None else "unresolved",
                },
            )
        )
        _check_current_rating(
            switch_id,
            rating,
            load_current_a,
            constraint_id="switch_current_rating",
            label="Switch",
            constraints=constraints,
            missing=missing,
        )
        _check_logic_level(
            switch_id,
            logic_input_min_v(switch_id),
            control_voltage_v,
            available,
            constraints,
            missing,
        )
    elif not interface_ambiguity:
        missing.append("driver_topology")
        constraints.append(
            _blocked(
                "driver_topology",
                "architecture",
                "driver",
                "Provide one declared H-bridge or low-side-switch interface; no representative driver is substituted.",
            )
        )

    if load:
        selected_parts.append(
            {
                "id": str(load.get("name") or load.get("id") or "load"),
                "type": str(load.get("type") or "dc_motor"),
                "voltage_v": load_voltage_v,
                "current_a": load_current_a,
                "inductive": _load_is_inductive(load),
            }
        )
    if signal:
        selected_parts.append(
            {
                "id": str(signal.get("name") or signal.get("id") or "control"),
                "type": str(signal.get("type") or "pwm"),
                "voltage_v": control_voltage_v,
            }
        )

    if _load_is_inductive(load):
        integrated = integrated_inductive_protection(selected_driver) if selected_driver else None
        if integrated is True:
            constraints.append(
                _passed(
                    "inductive_load_protection",
                    "protection",
                    selected_driver,
                    "Structured component contract declares integrated inductive-load protection.",
                    value={"integrated_inductive_protection": True},
                )
            )
        elif PROTECTION_EVIDENCE & evidence:
            constraints.append(
                _passed(
                    "inductive_load_protection",
                    "protection",
                    "load",
                    "Explicit external inductive-load protection evidence is present.",
                    value={"evidence": sorted(PROTECTION_EVIDENCE & evidence)},
                )
            )
            topology.append(
                TopologyOperator(
                    operator_id="evidenced_inductive_protection",
                    operator_type="protection_diode",
                    inputs=["load_positive", "switched_load_return"],
                    outputs=["clamped_inductive_spike"],
                    required_part_types=["diode_or_tvs"],
                    required_ports=["anode", "cathode"],
                    notes="Protection remains subject to physical evidence before power-on.",
                )
            )
        else:
            missing.append("flyback_or_driver_protection")
            constraints.append(
                _blocked(
                    "inductive_load_protection",
                    "protection",
                    selected_driver or "load",
                    "Integrated protection is not explicitly structured and no external protection evidence was supplied.",
                    value={"integrated_inductive_protection": integrated},
                )
            )

    gates = _verification_gates(load_current_a=load_current_a, supply_current_a=supply_current_a)
    result = "blocked" if missing or any(c.status == "blocked" for c in constraints) else "ready_for_review"
    if result == "ready_for_review":
        assumptions.append("Candidate is ready for human review only; bench gates must close before first power-on.")
    else:
        assumptions.append("Planner stopped before compile/readiness approval because required structured evidence is missing.")

    modules_for_build = _recommended_module_ids(available, selected_modules)
    contract_ids = _dedupe(list(modules_for_build) + list(selected_modules))
    return SynthesisCandidate(
        candidate_id="motor_pump_driver_candidate",
        selected_parts=selected_parts,
        selected_modules=_dedupe(selected_modules),
        generated_topology=topology,
        assumptions=assumptions,
        missing_evidence=_dedupe(missing),
        constraints=constraints,
        verification_gates=gates,
        recommended_build_path={
            "build_id": "generic_low_voltage_build",
            "compose_mode": "module_graph_candidate",
            "module_ids": modules_for_build,
            "can_compile_with_existing_auto_wire": len([m for m in modules_for_build if find_module(m)]) >= 2,
            "notes": [
                "Use compose_dispatch only after blocked constraints are resolved.",
                "This candidate is topology planning, not certified schematic synthesis.",
            ],
        },
        result=result,
        notes="Bounded DC motor/pump driver topology plan.",
        metadata={
            "goal": circuit_intent.goal,
            "supply": supply,
            "load": load,
            "signal": signal,
            "electrical_truth": {
                "source": "structured_catalog_fields_only",
                "design_current_margin_multiplier": CURRENT_MARGIN_MULTIPLIER,
                "module_contracts": [contract_snapshot(module_id) for module_id in contract_ids],
                "summary_text_used_as_rating": False,
                "magic_module_rating_table_used": False,
                "authority_effect": "none",
            },
        },
    )


def _available_module_ids(intent: CircuitIntent) -> set[str]:
    ids = set(intent.allowed_modules)
    for row in intent.allowed_parts:
        for key in ("module_id", "id"):
            mid = str(row.get(key) or "").strip()
            if mid and find_module(mid):
                ids.add(mid)
    return ids


def _first_load(intent: CircuitIntent) -> Dict[str, Any]:
    for row in intent.load_requirements:
        kind = str(row.get("type") or row.get("kind") or "").lower()
        if any(token in kind for token in ("motor", "pump", "fan", "solenoid", "load")):
            return dict(row)
    return dict(intent.load_requirements[0]) if intent.load_requirements else {}


def _first_signal(intent: CircuitIntent) -> Dict[str, Any]:
    for row in intent.signal_requirements:
        kind = str(row.get("type") or row.get("signal_type") or "").lower()
        if kind in {"pwm", "digital", "gpio", "logic"}:
            return dict(row)
    return dict(intent.signal_requirements[0]) if intent.signal_requirements else {}


def _first_supply(intent: CircuitIntent, available: set[str]) -> Dict[str, Any]:
    if intent.supply_rails:
        declared = dict(intent.supply_rails[0])
        declared.setdefault("source", "declared_supply_rail")
        return declared

    candidates = sorted(module_id for module_id in available if is_power_source(module_id))
    if len(candidates) != 1:
        return {}
    module_id = candidates[0]
    return {
        "name": module_id,
        "voltage_v": exact_output_voltage_v(module_id),
        "max_current_a": max_output_current_a(module_id),
        "source": "structured_catalog_contract",
    }


def _select_driver_interface(available: set[str]) -> tuple[str, str, Dict[str, Any]]:
    h_bridges = sorted(module_id for module_id in available if is_h_bridge_interface(module_id))
    switches = sorted(module_id for module_id in available if is_low_side_switch_interface(module_id))
    if len(h_bridges) == 1 and not switches:
        return h_bridges[0], "", {}
    if len(switches) == 1 and not h_bridges:
        return "", switches[0], {}
    if not h_bridges and not switches:
        return "", "", {}
    return "", "", {"h_bridge_candidates": h_bridges, "low_side_switch_candidates": switches}


def _check_current_rating(
    module_id: str,
    rating_a: float | None,
    load_current_a: float | None,
    *,
    constraint_id: str,
    label: str,
    constraints: List[Constraint],
    missing: List[str],
) -> None:
    if rating_a is None:
        missing.append(f"{module_id}_output_current_rating")
        constraints.append(
            _blocked(
                constraint_id,
                "current",
                module_id,
                f"{label} output/load-current rating is absent from the structured component contract.",
                value={"current_rating_a": None, "load_current_a": load_current_a},
            )
        )
        return
    if load_current_a is None:
        return
    required = load_current_a * CURRENT_MARGIN_MULTIPLIER
    if rating_a + 1e-12 >= required:
        constraints.append(
            _passed(
                constraint_id,
                "current",
                module_id,
                f"{label} structured current rating covers the explicit design-policy margin.",
                value={
                    "current_rating_a": rating_a,
                    "load_current_a": load_current_a,
                    "required_with_margin_a": required,
                    "margin_multiplier": CURRENT_MARGIN_MULTIPLIER,
                },
            )
        )
        return
    missing.append(f"{module_id}_current_margin")
    constraints.append(
        _blocked(
            constraint_id,
            "current",
            module_id,
            f"{label} structured current rating does not cover the explicit design-policy margin.",
            value={
                "current_rating_a": rating_a,
                "load_current_a": load_current_a,
                "required_with_margin_a": required,
                "margin_multiplier": CURRENT_MARGIN_MULTIPLIER,
            },
        )
    )


def _check_logic_level(
    module_id: str,
    min_voltage_v: float | None,
    control_voltage_v: float | None,
    available: set[str],
    constraints: List[Constraint],
    missing: List[str],
) -> None:
    if control_voltage_v is None:
        return
    if min_voltage_v is None:
        missing.append(f"{module_id}_logic_input_threshold")
        constraints.append(
            _blocked(
                f"{module_id}_logic_level",
                "logic_level",
                module_id,
                "Guaranteed logic-input threshold is absent from the structured component contract.",
                value={"control_voltage_v": control_voltage_v, "required_min_v": None},
            )
        )
        return
    if control_voltage_v + 1e-9 >= min_voltage_v:
        constraints.append(
            _passed(
                f"{module_id}_logic_level",
                "logic_level",
                module_id,
                "Control signal voltage meets the structured driver/switch input threshold.",
                value={"control_voltage_v": control_voltage_v, "required_min_v": min_voltage_v},
            )
        )
        return
    shifters = sorted(module_id for module_id in available if is_level_shifter_interface(module_id))
    if shifters:
        constraints.append(
            _passed(
                f"{module_id}_logic_level_shifted",
                "logic_level",
                module_id,
                "A declared level-shifter interface is available for control-signal compatibility.",
                value={
                    "control_voltage_v": control_voltage_v,
                    "required_min_v": min_voltage_v,
                    "level_shifter_candidates": shifters,
                },
            )
        )
        return
    missing.append("level_shifter_or_compatible_driver")
    constraints.append(
        _blocked(
            f"{module_id}_logic_level",
            "logic_level",
            module_id,
            "Control signal voltage is below the structured driver/switch input threshold.",
            value={"control_voltage_v": control_voltage_v, "required_min_v": min_voltage_v},
        )
    )


def _load_is_inductive(load: Mapping[str, Any]) -> bool:
    kind = str(load.get("type") or load.get("kind") or "").lower()
    if not kind:
        return True
    return any(token in kind for token in ("motor", "pump", "fan", "solenoid", "inductive"))


def _verification_gates(*, load_current_a: float | None, supply_current_a: float | None) -> List[Dict[str, Any]]:
    return [
        {
            "gate_id": "psu_current_limit_ramp",
            "gate_type": "psu_ramp",
            "critical": True,
            "prompt": "Ramp motor supply with an explicit current limit; record voltage/current at each step.",
            "expected_load_current_a": load_current_a,
            "supply_current_limit_a": supply_current_a,
            "status": "open",
        },
        {
            "gate_id": "thermal_baseline_scan",
            "gate_type": "thermal",
            "critical": True,
            "prompt": "Capture thermal baseline at idle and under brief load before enclosing or sustained operation.",
            "status": "open",
        },
        {
            "gate_id": "inductive_protection_inspection",
            "gate_type": "bench_check",
            "critical": True,
            "prompt": "Confirm flyback/TVS/integrated driver protection path for motor or pump load.",
            "status": "open",
        },
    ]


def _recommended_module_ids(available: set[str], selected: Sequence[str]) -> List[str]:
    ordered: List[str] = []
    ordered.extend(sorted(module_id for module_id in available if is_power_source(module_id)))
    ordered.extend(sorted(module_id for module_id in available if is_mcu(module_id)))
    ordered.extend(selected)
    ordered.extend(sorted(module_id for module_id in available if is_motor_or_load(module_id)))
    ordered.extend(sorted(module_id for module_id in available if is_level_shifter_interface(module_id)))
    return _dedupe(ordered)


def _passed(
    constraint_id: str,
    type: str,
    target: str,
    requirement: str,
    *,
    value: Any = None,
) -> Constraint:
    return Constraint(
        constraint_id=constraint_id,
        type=type,
        target=target,
        requirement=requirement,
        status="pass",
        value=value,
    )


def _blocked(
    constraint_id: str,
    type: str,
    target: str,
    requirement: str,
    *,
    value: Any = None,
) -> Constraint:
    return Constraint(
        constraint_id=constraint_id,
        type=type,
        target=target,
        requirement=requirement,
        status="blocked",
        value=value,
    )


def _dedupe(rows: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for row in rows:
        text = str(row or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
