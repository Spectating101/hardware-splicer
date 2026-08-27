"""Bounded bidirectional DC motor H-bridge topology planner."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from ..electrical_contract_truth import (
    contract_snapshot,
    is_bidirectional_motor_driver_interface,
    is_level_shifter_interface,
    is_motor_or_load,
    logic_input_min_v,
    max_output_current_a,
)
from .common import (
    available_module_ids,
    blocked,
    build_path,
    dedupe,
    first_controller,
    first_float,
    first_power_source,
    has_blocker,
    module_input_range,
    module_logic_voltage,
    passed,
)
from .ir import CircuitIntent, Constraint, SynthesisCandidate, TopologyOperator


CURRENT_MARGIN_MULTIPLIER = 1.25


def plan_h_bridge(intent: CircuitIntent | Mapping[str, Any]) -> SynthesisCandidate:
    """Plan a bounded reversible DC motor drive path from structured contracts.

    Driver identity may be recognized from declared capabilities/pin roles, but current
    rating and logic-threshold compatibility must be machine-readable component truth.
    Human summaries and per-module magic tables are never electrical authority.
    """

    circuit_intent = intent if isinstance(intent, CircuitIntent) else CircuitIntent.from_dict(intent)
    available = available_module_ids(circuit_intent)
    constraints: List[Constraint] = []
    missing: List[str] = []
    topology: List[TopologyOperator] = []

    controller = first_controller(available)
    power_source = first_power_source(available)
    load_module = _single_structural_load(available)
    load = _first_load(circuit_intent)
    signal = _first_signal(circuit_intent)
    load_current_a = _load_current(circuit_intent, load)
    load_voltage_v = _load_voltage(circuit_intent, load)
    control_voltage_v = _control_voltage(circuit_intent, signal, controller)
    driver, driver_candidates = _choose_driver(
        available,
        load_voltage_v=load_voltage_v,
    )

    if not controller:
        missing.append("controller_module")
        constraints.append(
            blocked(
                "controller_module",
                "evidence_required",
                "controller",
                "Provide exactly one declared MCU/controller module.",
            )
        )
    if not load and not load_module:
        missing.append("motor_load")
        constraints.append(
            blocked(
                "motor_load",
                "measurement_required",
                "load",
                "Declare the reversible DC motor/load.",
            )
        )
    if load_current_a is None:
        missing.append("motor_stall_or_run_current")
        constraints.append(
            blocked(
                "motor_stall_or_run_current",
                "measurement_required",
                "load_current",
                "Provide measured or estimated run/stall current for driver validation.",
            )
        )
    if load_voltage_v is None:
        missing.append("motor_supply_voltage")
        constraints.append(
            blocked(
                "motor_supply_voltage",
                "voltage",
                "motor_supply",
                "Declare motor supply voltage.",
            )
        )
    if control_voltage_v is None:
        missing.append("control_logic_voltage")
        constraints.append(
            blocked(
                "control_logic_voltage",
                "logic_level",
                "control",
                "Declare or infer controller logic voltage from structured controller data.",
            )
        )

    if not driver:
        missing.append("h_bridge_driver_module")
        constraints.append(
            blocked(
                "h_bridge_driver_module",
                "architecture",
                "driver",
                (
                    "Multiple structurally compatible H-bridge drivers are declared; choose one explicitly."
                    if len(driver_candidates) > 1
                    else "Provide one declared bidirectional motor-driver interface compatible with the motor supply range."
                ),
                value={"compatible_candidates": driver_candidates},
            )
        )
    else:
        _check_driver(
            driver,
            load_current_a,
            load_voltage_v,
            control_voltage_v,
            available,
            constraints,
            missing,
        )
        topology.append(
            TopologyOperator(
                operator_id=f"{driver}_bidirectional_drive",
                operator_type="h_bridge",
                inputs=["motor_supply", "logic_supply", "direction_pwm_signals", "ground"],
                outputs=["motor_terminal_a", "motor_terminal_b"],
                required_part_types=["h_bridge_driver", "brushed_dc_motor", "controller"],
                required_ports=["motor_supply", "ground", "control_inputs", "motor_outputs"],
                notes=f"{driver} selected from declared motor-driver capabilities and pin roles.",
                metadata={
                    "module_id": driver,
                    "current_rating_a": max_output_current_a(driver),
                    "load_current_a": load_current_a,
                    "load_voltage_v": load_voltage_v,
                    "control_voltage_v": control_voltage_v,
                    "electrical_contract": contract_snapshot(driver),
                },
            )
        )

    selected_modules = dedupe([power_source, controller, driver, load_module])
    result = "blocked" if has_blocker(constraints, missing) else "ready_for_review"
    return SynthesisCandidate(
        candidate_id="h_bridge_motor_candidate",
        selected_parts=[
            {
                "id": str(load.get("name") or load.get("id") or load_module or "dc_motor"),
                "type": str(load.get("type") or "bidirectional_dc_motor"),
                "voltage_v": load_voltage_v,
                "current_a": load_current_a,
                "requires_direction_control": True,
            }
        ],
        selected_modules=dedupe([driver] if driver else []),
        generated_topology=topology,
        assumptions=[
            "H-bridge candidate is ready for human review only; direction, braking mode, current limiting, and thermal gates must close."
            if result == "ready_for_review"
            else "Planner stopped before compile/readiness approval because motor-drive evidence is missing or incompatible."
        ],
        missing_evidence=dedupe(missing),
        constraints=constraints,
        verification_gates=_verification_gates(
            load_current_a=load_current_a,
            load_voltage_v=load_voltage_v,
        ),
        recommended_build_path=build_path(
            available=available,
            selected=selected_modules,
            build_id="generic_low_voltage_build",
            notes=[
                "Compile path uses topology terminal semantics so H-bridge motor terminals remain floating, not common-ground pins.",
                "This is bounded topology planning, not certified motor-control design.",
            ],
        ),
        result=result,
        notes="Bounded reversible DC motor H-bridge topology plan.",
        metadata={
            "goal": circuit_intent.goal,
            "controller": controller,
            "power_source": power_source,
            "driver": driver,
            "driver_candidates": driver_candidates,
            "load_module": load_module,
            "electrical_truth": {
                "source": "structured_project_and_catalog_fields_only",
                "magic_rating_table_used": False,
                "magic_logic_threshold_table_used": False,
                "design_current_margin_multiplier": CURRENT_MARGIN_MULTIPLIER,
                "authority_effect": "none",
            },
        },
    )


def _first_load(intent: CircuitIntent) -> Dict[str, Any]:
    for row in intent.load_requirements:
        kind = str(row.get("type") or row.get("kind") or "").lower()
        if kind in {
            "motor",
            "dc_motor",
            "brushed_dc_motor",
            "pump",
            "fan",
            "wheel_drive",
            "actuator",
            "load",
        }:
            return dict(row)
    return dict(intent.load_requirements[0]) if intent.load_requirements else {}


def _first_signal(intent: CircuitIntent) -> Dict[str, Any]:
    for row in intent.signal_requirements:
        kind = str(row.get("type") or row.get("signal_type") or "").lower()
        if kind in {"pwm", "pwm_direction", "direction", "gpio", "logic", "control"}:
            return dict(row)
    return dict(intent.signal_requirements[0]) if intent.signal_requirements else {}


def _load_current(intent: CircuitIntent, load: Mapping[str, Any]) -> float | None:
    values: List[float] = []
    for row in [load] + list(intent.current_constraints) + list(intent.load_requirements):
        for key in (
            "stall_current_a",
            "peak_current_a",
            "run_current_a",
            "current_a",
            "load_current_a",
        ):
            value = first_float(row, (key,))
            if value is not None:
                values.append(value)
    return max(values) if values else None


def _load_voltage(intent: CircuitIntent, load: Mapping[str, Any]) -> float | None:
    for row in [load] + list(intent.supply_rails) + list(intent.voltage_constraints):
        value = first_float(
            row,
            ("motor_voltage_v", "load_voltage_v", "voltage_v", "supply_voltage_v"),
        )
        if value is not None:
            return value
    return None


def _control_voltage(
    intent: CircuitIntent,
    signal: Mapping[str, Any],
    controller: str,
) -> float | None:
    for row in [signal] + list(intent.signal_requirements):
        value = first_float(
            row,
            ("control_voltage_v", "logic_voltage_v", "voltage_v", "controller_voltage_v"),
        )
        if value is not None:
            return value
    return module_logic_voltage(controller) if controller else None


def _single_structural_load(available: set[str]) -> str:
    candidates = sorted(module_id for module_id in available if is_motor_or_load(module_id))
    return candidates[0] if len(candidates) == 1 else ""


def _choose_driver(
    available: set[str],
    *,
    load_voltage_v: float | None,
) -> tuple[str, List[str]]:
    candidates: List[str] = []
    for module_id in sorted(available):
        if not is_bidirectional_motor_driver_interface(module_id):
            continue
        min_v, max_v = module_input_range(module_id)
        if load_voltage_v is not None and min_v is not None and max_v is not None:
            if not (min_v <= load_voltage_v <= max_v):
                continue
        candidates.append(module_id)
    return (candidates[0] if len(candidates) == 1 else "", candidates)


def _check_driver(
    module_id: str,
    load_current_a: float | None,
    load_voltage_v: float | None,
    control_voltage_v: float | None,
    available: set[str],
    constraints: List[Constraint],
    missing: List[str],
) -> None:
    rating = max_output_current_a(module_id)
    if rating is None:
        missing.append("h_bridge_current_rating_contract")
        constraints.append(
            blocked(
                "h_bridge_current_margin",
                "current",
                module_id,
                "H-bridge output-current rating is absent from the structured component contract.",
                value={"driver_rating_a": None, "load_current_a": load_current_a},
            )
        )
    elif load_current_a is not None:
        required = load_current_a * CURRENT_MARGIN_MULTIPLIER
        if rating >= required:
            constraints.append(
                passed(
                    "h_bridge_current_margin",
                    "current",
                    module_id,
                    "Structured H-bridge current rating covers estimated run/stall current with design-policy margin.",
                    value={
                        "driver_rating_a": rating,
                        "load_current_a": load_current_a,
                        "required_with_margin_a": required,
                    },
                )
            )
        else:
            missing.append("h_bridge_current_margin")
            constraints.append(
                blocked(
                    "h_bridge_current_margin",
                    "current",
                    module_id,
                    "Structured H-bridge current rating is below the estimated motor current margin.",
                    value={
                        "driver_rating_a": rating,
                        "load_current_a": load_current_a,
                        "required_with_margin_a": required,
                    },
                )
            )

    min_v, max_v = module_input_range(module_id)
    if min_v is None or max_v is None:
        missing.append("h_bridge_voltage_range_contract")
        constraints.append(
            blocked(
                "h_bridge_voltage_range",
                "voltage",
                module_id,
                "H-bridge motor-supply range is absent from the structured component contract.",
            )
        )
    elif load_voltage_v is not None:
        if min_v <= load_voltage_v <= max_v:
            constraints.append(
                passed(
                    "h_bridge_voltage_range",
                    "voltage",
                    module_id,
                    "Motor supply voltage is inside the structured driver range.",
                    value={"load_voltage_v": load_voltage_v, "min_v": min_v, "max_v": max_v},
                )
            )
        else:
            missing.append("h_bridge_voltage_range")
            constraints.append(
                blocked(
                    "h_bridge_voltage_range",
                    "voltage",
                    module_id,
                    "Motor supply voltage is outside the structured driver range.",
                    value={"load_voltage_v": load_voltage_v, "min_v": min_v, "max_v": max_v},
                )
            )

    min_logic_v = logic_input_min_v(module_id)
    if control_voltage_v is not None:
        if min_logic_v is None:
            missing.append("h_bridge_logic_threshold_contract")
            constraints.append(
                blocked(
                    "h_bridge_logic_level",
                    "logic_level",
                    module_id,
                    "Guaranteed H-bridge logic-high threshold is absent from the structured component contract.",
                    value={"control_voltage_v": control_voltage_v, "required_min_v": None},
                )
            )
        elif control_voltage_v >= min_logic_v:
            constraints.append(
                passed(
                    "h_bridge_logic_level",
                    "logic_level",
                    module_id,
                    "Controller logic level meets the structured H-bridge input threshold.",
                    value={"control_voltage_v": control_voltage_v, "required_min_v": min_logic_v},
                )
            )
        else:
            shifters = sorted(
                module_id for module_id in available if is_level_shifter_interface(module_id)
            )
            if shifters:
                constraints.append(
                    passed(
                        "h_bridge_logic_level_shifted",
                        "logic_level",
                        module_id,
                        "A declared level-shifter interface is available for H-bridge control compatibility.",
                        value={
                            "control_voltage_v": control_voltage_v,
                            "required_min_v": min_logic_v,
                            "level_shifter_candidates": shifters,
                        },
                    )
                )
            else:
                missing.append("h_bridge_logic_level")
                constraints.append(
                    blocked(
                        "h_bridge_logic_level",
                        "logic_level",
                        module_id,
                        "Controller logic level is below the structured H-bridge input threshold.",
                        value={"control_voltage_v": control_voltage_v, "required_min_v": min_logic_v},
                    )
                )


def _verification_gates(
    *,
    load_current_a: float | None,
    load_voltage_v: float | None,
) -> List[Dict[str, Any]]:
    return [
        {
            "gate_id": "h_bridge_no_load_direction_test",
            "gate_type": "bench_check",
            "critical": True,
            "prompt": "With motor disconnected or current-limited, verify forward/reverse control states and brake/coast behavior.",
            "status": "open",
        },
        {
            "gate_id": "h_bridge_current_limit_ramp",
            "gate_type": "psu_ramp",
            "critical": True,
            "prompt": "Ramp motor supply with current limit; record startup and loaded current before sustained operation.",
            "expected_load_current_a": load_current_a,
            "expected_motor_voltage_v": load_voltage_v,
            "status": "open",
        },
        {
            "gate_id": "h_bridge_driver_thermal_scan",
            "gate_type": "thermal",
            "critical": True,
            "prompt": "Capture driver temperature after short forward/reverse runs.",
            "status": "open",
        },
    ]
