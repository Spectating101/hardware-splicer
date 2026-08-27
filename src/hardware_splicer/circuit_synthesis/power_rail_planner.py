"""Bounded power-rail conversion planner using structured electrical contracts."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from ..electrical_contract_truth import (
    contract_snapshot,
    max_output_current_a,
    output_voltage_range_v,
    power_conversion_kind,
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
    passed,
    warned,
)
from .ir import CircuitIntent, Constraint, SynthesisCandidate, TopologyOperator


STEP_DOWN_KINDS = {"buck", "ldo"}
CURRENT_MARGIN_MULTIPLIER = 1.25
STEP_DOWN_HEADROOM_POLICY_V = 0.25
LDO_REVIEW_DISSIPATION_W = 0.5
LDO_BLOCK_DISSIPATION_W = 1.0


def plan_power_rail(intent: CircuitIntent | Mapping[str, Any]) -> SynthesisCandidate:
    circuit_intent = intent if isinstance(intent, CircuitIntent) else CircuitIntent.from_dict(intent)
    available = available_module_ids(circuit_intent)
    constraints: List[Constraint] = []
    missing: List[str] = []
    topology: List[TopologyOperator] = []
    selected_modules: List[str] = []

    input_v = _input_voltage(circuit_intent)
    output_v = _output_voltage(circuit_intent)
    load_current_a = _load_current(circuit_intent)
    source_module = first_power_source(available, input_v)
    regulator, regulator_candidates = _choose_regulator(
        available,
        input_v=input_v,
        output_v=output_v,
    )
    regulator_kind = power_conversion_kind(regulator) if regulator else None

    if input_v is None:
        missing.append("input_voltage")
        constraints.append(
            blocked("input_voltage", "voltage", "input_rail", "Declare source/input rail voltage.")
        )
    if output_v is None:
        missing.append("target_output_voltage")
        constraints.append(
            blocked(
                "target_output_voltage",
                "voltage",
                "output_rail",
                "Declare required regulated output voltage in structured project state.",
            )
        )
    if load_current_a is None:
        missing.append("load_current_estimate")
        constraints.append(
            blocked(
                "load_current_estimate",
                "measurement_required",
                "load",
                "Declare expected rail load current.",
            )
        )

    if input_v is not None and output_v is not None:
        if input_v <= output_v + STEP_DOWN_HEADROOM_POLICY_V:
            missing.append("step_down_headroom")
            constraints.append(
                blocked(
                    "step_down_headroom",
                    "voltage",
                    "regulator",
                    "Step-down regulator needs input voltage above output voltage by the explicit planner-policy headroom.",
                    value={
                        "input_v": input_v,
                        "output_v": output_v,
                        "policy_headroom_v": STEP_DOWN_HEADROOM_POLICY_V,
                    },
                )
            )
        else:
            constraints.append(
                passed(
                    "step_down_headroom",
                    "voltage",
                    "regulator",
                    "Input voltage is above target output rail by the explicit planner-policy headroom.",
                    value={
                        "input_v": input_v,
                        "output_v": output_v,
                        "policy_headroom_v": STEP_DOWN_HEADROOM_POLICY_V,
                    },
                )
            )

    if regulator:
        selected_modules.append(regulator)
        if source_module:
            selected_modules.insert(0, source_module)
        _check_regulator(regulator, input_v, output_v, load_current_a, constraints, missing)
        topology.append(
            TopologyOperator(
                operator_id=f"{regulator}_rail_conversion",
                operator_type="ldo_regulator" if regulator_kind == "ldo" else "buck_regulator",
                inputs=["input_rail", "ground"],
                outputs=["regulated_output_rail", "ground"],
                required_part_types=["regulator_module", "load"],
                required_ports=["VIN", "GND", "VOUT"],
                notes=f"{regulator} selected because it is the sole declared regulator compatible with structured constraints.",
                metadata={
                    "module_id": regulator,
                    "power_conversion_kind": regulator_kind,
                    "input_v": input_v,
                    "output_v": output_v,
                    "load_current_a": load_current_a,
                    "electrical_contract": contract_snapshot(regulator),
                },
            )
        )
    else:
        missing.append("regulator_module")
        constraints.append(
            blocked(
                "regulator_module",
                "evidence_required",
                "regulator",
                (
                    "Multiple compatible regulator modules are declared; choose one explicitly."
                    if len(regulator_candidates) > 1
                    else "Provide one regulator with an explicit step-down topology contract plus structured input/output/current contracts compatible with the target rail."
                ),
                value={"compatible_candidates": regulator_candidates},
            )
        )

    result = "blocked" if has_blocker(constraints, missing) else "ready_for_review"
    assumptions = [
        "Power-rail candidate is ready for human review only; output voltage must be measured before connecting loads."
        if result == "ready_for_review"
        else "Planner stopped before compile/readiness approval because rail evidence is missing or incompatible."
    ]
    if regulator_kind == "ldo" and input_v is not None and output_v is not None and load_current_a is not None:
        assumptions.append(
            "LDO dissipation thresholds are explicit design policy; bench thermal capture still controls sustained-load confidence."
        )

    modules_for_build = _recommended_modules(available, selected_modules)
    return SynthesisCandidate(
        candidate_id="power_rail_candidate",
        selected_parts=[
            {
                "id": "regulated_rail",
                "type": "power_rail",
                "input_v": input_v,
                "output_v": output_v,
                "load_current_a": load_current_a,
            }
        ],
        selected_modules=dedupe(selected_modules),
        generated_topology=topology,
        assumptions=assumptions,
        missing_evidence=dedupe(missing),
        constraints=constraints,
        verification_gates=_verification_gates(
            input_v=input_v,
            output_v=output_v,
            load_current_a=load_current_a,
        ),
        recommended_build_path=build_path(available=available, selected=modules_for_build),
        result=result,
        notes="Bounded regulated power-rail topology plan.",
        metadata={
            "goal": circuit_intent.goal,
            "input_voltage_v": input_v,
            "output_voltage_v": output_v,
            "load_current_a": load_current_a,
            "regulator_candidates": regulator_candidates,
            "regulator_kind": regulator_kind,
            "electrical_truth": {
                "source": "structured_project_and_component_contracts_only",
                "goal_prose_voltage_inference_used": False,
                "current_default_used": False,
                "module_id_family_table_used": False,
                "design_policy": {
                    "current_margin_multiplier": CURRENT_MARGIN_MULTIPLIER,
                    "step_down_headroom_v": STEP_DOWN_HEADROOM_POLICY_V,
                    "ldo_review_dissipation_w": LDO_REVIEW_DISSIPATION_W,
                    "ldo_block_dissipation_w": LDO_BLOCK_DISSIPATION_W,
                },
                "authority_effect": "none",
            },
        },
    )


def _input_voltage(intent: CircuitIntent) -> float | None:
    for row in intent.supply_rails:
        role = str(row.get("role") or row.get("kind") or "").lower()
        if role in {"input", "source", "vin", "adapter", "battery"}:
            return first_float(row, ("voltage_v", "input_voltage_v", "source_voltage_v"))
    if intent.supply_rails:
        return first_float(
            intent.supply_rails[0],
            ("voltage_v", "input_voltage_v", "source_voltage_v"),
        )
    return None


def _output_voltage(intent: CircuitIntent) -> float | None:
    for row in intent.voltage_constraints:
        value = first_float(
            row,
            ("output_voltage_v", "target_voltage_v", "voltage_v", "required_voltage_v"),
        )
        if value is not None:
            return value
    for row in intent.supply_rails[1:]:
        value = first_float(
            row,
            ("output_voltage_v", "target_voltage_v", "voltage_v", "required_voltage_v"),
        )
        if value is not None:
            return value
    return None


def _load_current(intent: CircuitIntent) -> float | None:
    for row in intent.current_constraints + intent.load_requirements + intent.voltage_constraints:
        value = first_float(
            row,
            ("load_current_a", "current_a", "max_current_a", "required_current_a"),
        )
        if value is not None:
            return value
    return None


def _choose_regulator(
    available: set[str],
    *,
    input_v: float | None,
    output_v: float | None,
) -> tuple[str, List[str]]:
    candidates: List[str] = []
    for module_id in sorted(available):
        if power_conversion_kind(module_id) not in STEP_DOWN_KINDS:
            continue
        min_in, max_in = module_input_range(module_id)
        min_out, max_out = output_voltage_range_v(module_id)
        if input_v is not None and min_in is not None and max_in is not None:
            if not (min_in <= input_v <= max_in):
                continue
        if output_v is not None:
            if min_out is None or max_out is None or not (min_out <= output_v <= max_out):
                continue
        candidates.append(module_id)
    return (candidates[0] if len(candidates) == 1 else "", candidates)


def _check_regulator(
    module_id: str,
    input_v: float | None,
    output_v: float | None,
    load_current_a: float | None,
    constraints: List[Constraint],
    missing: List[str],
) -> None:
    min_in, max_in = module_input_range(module_id)
    if min_in is None or max_in is None:
        missing.append("regulator_input_range_contract")
        constraints.append(
            blocked(
                f"{module_id}_input_range",
                "voltage",
                module_id,
                "Regulator input range is absent from the structured component contract.",
            )
        )
    elif input_v is not None:
        if min_in <= input_v <= max_in:
            constraints.append(
                passed(
                    f"{module_id}_input_range",
                    "voltage",
                    module_id,
                    "Input rail is inside the structured regulator input range.",
                    value={"input_v": input_v, "min_in_v": min_in, "max_in_v": max_in},
                )
            )
        else:
            missing.append("regulator_input_range")
            constraints.append(
                blocked(
                    f"{module_id}_input_range",
                    "voltage",
                    module_id,
                    "Input rail is outside the structured regulator input range.",
                    value={"input_v": input_v, "min_in_v": min_in, "max_in_v": max_in},
                )
            )

    min_out, max_out = output_voltage_range_v(module_id)
    if min_out is None or max_out is None:
        missing.append("regulator_output_range_contract")
        constraints.append(
            blocked(
                f"{module_id}_output_voltage",
                "voltage",
                module_id,
                "Regulator output range is absent from the structured component contract.",
            )
        )
    elif output_v is not None:
        if min_out <= output_v <= max_out:
            constraints.append(
                passed(
                    f"{module_id}_output_voltage",
                    "voltage",
                    module_id,
                    "Target output rail is inside the structured regulator output range.",
                    value={
                        "target_output_v": output_v,
                        "min_output_v": min_out,
                        "max_output_v": max_out,
                    },
                )
            )
        else:
            missing.append("regulator_output_range")
            constraints.append(
                blocked(
                    f"{module_id}_output_voltage",
                    "voltage",
                    module_id,
                    "Target output rail is outside the structured regulator output range.",
                    value={
                        "target_output_v": output_v,
                        "min_output_v": min_out,
                        "max_output_v": max_out,
                    },
                )
            )

    current_limit_a = max_output_current_a(module_id)
    if current_limit_a is None:
        missing.append("regulator_current_rating_contract")
        constraints.append(
            blocked(
                f"{module_id}_current_margin",
                "current",
                module_id,
                "Regulator output-current rating is absent from the structured component contract.",
                value={"current_limit_a": None, "load_current_a": load_current_a},
            )
        )
    elif load_current_a is not None:
        required = load_current_a * CURRENT_MARGIN_MULTIPLIER
        if current_limit_a >= required:
            constraints.append(
                passed(
                    f"{module_id}_current_margin",
                    "current",
                    module_id,
                    "Structured regulator current rating covers load current with design-policy margin.",
                    value={
                        "current_limit_a": current_limit_a,
                        "load_current_a": load_current_a,
                        "required_with_margin_a": required,
                    },
                )
            )
        else:
            missing.append("regulator_current_margin")
            constraints.append(
                blocked(
                    f"{module_id}_current_margin",
                    "current",
                    module_id,
                    "Structured regulator current rating is below the design-policy margin.",
                    value={
                        "current_limit_a": current_limit_a,
                        "load_current_a": load_current_a,
                        "required_with_margin_a": required,
                    },
                )
            )

    if power_conversion_kind(module_id) == "ldo" and input_v is not None and output_v is not None and load_current_a is not None:
        watts = max(0.0, input_v - output_v) * load_current_a
        if watts <= LDO_REVIEW_DISSIPATION_W:
            constraints.append(
                passed(
                    f"{module_id}_thermal_dissipation",
                    "thermal",
                    module_id,
                    "Estimated LDO dissipation is below the explicit review-policy threshold.",
                    value={"dissipation_w": round(watts, 3)},
                )
            )
        elif watts <= LDO_BLOCK_DISSIPATION_W:
            constraints.append(
                warned(
                    f"{module_id}_thermal_dissipation",
                    "thermal",
                    module_id,
                    "Estimated LDO dissipation needs bench thermal confirmation under design policy.",
                    value={"dissipation_w": round(watts, 3)},
                )
            )
        else:
            missing.append("ldo_thermal_margin")
            constraints.append(
                blocked(
                    f"{module_id}_thermal_dissipation",
                    "thermal",
                    module_id,
                    "Estimated LDO dissipation exceeds the explicit bounded-planner policy threshold.",
                    value={"dissipation_w": round(watts, 3)},
                )
            )


def _recommended_modules(available: set[str], selected_modules: List[str]) -> List[str]:
    out = list(selected_modules)
    controller = first_controller(available)
    if controller:
        out.append(controller)
    return dedupe(out)


def _verification_gates(
    *,
    input_v: float | None,
    output_v: float | None,
    load_current_a: float | None,
) -> List[Dict[str, Any]]:
    return [
        {
            "gate_id": "regulator_no_load_voltage",
            "gate_type": "dmm_voltage",
            "critical": True,
            "prompt": "Measure regulator output with no load before connecting downstream modules.",
            "expected_input_v": input_v,
            "expected_output_v": output_v,
            "status": "open",
        },
        {
            "gate_id": "regulator_loaded_voltage",
            "gate_type": "dmm_voltage_current",
            "critical": True,
            "prompt": "Measure output voltage and current under expected load.",
            "expected_load_current_a": load_current_a,
            "status": "open",
        },
        {
            "gate_id": "regulator_thermal_check",
            "gate_type": "thermal",
            "critical": True,
            "prompt": "Capture thermal reading after short loaded run before enclosure or sustained operation.",
            "status": "open",
        },
    ]
