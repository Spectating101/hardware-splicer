"""Bounded power-rail conversion planner."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from .common import (
    available_module_ids,
    blocked,
    build_path,
    dedupe,
    first_available,
    first_float,
    first_power_source,
    has_blocker,
    module_current_limit_a,
    module_input_range,
    passed,
    voltage_from_text,
    warned,
)
from .ir import CircuitIntent, Constraint, SynthesisCandidate, TopologyOperator


BUCK_MODULES = ("buck-mp1584", "buck-lm2596")
LDO_OUTPUT_V = {
    "ldo-ams1117-3v3": 3.3,
    "ldo-ams1117-5v": 5.0,
}


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
    regulator = _choose_regulator(available, input_v=input_v, output_v=output_v, load_current_a=load_current_a)

    if input_v is None:
        missing.append("input_voltage")
        constraints.append(blocked("input_voltage", "voltage", "input_rail", "Declare source/input rail voltage."))
    if output_v is None:
        missing.append("target_output_voltage")
        constraints.append(blocked("target_output_voltage", "voltage", "output_rail", "Declare required regulated output voltage."))
    if load_current_a is None:
        missing.append("load_current_estimate")
        constraints.append(blocked("load_current_estimate", "measurement_required", "load", "Declare expected rail load current."))

    if input_v is not None and output_v is not None:
        if input_v <= output_v + 0.25:
            missing.append("step_down_headroom")
            constraints.append(
                blocked(
                    "step_down_headroom",
                    "voltage",
                    "regulator",
                    "Step-down regulator needs input voltage above output voltage.",
                    value={"input_v": input_v, "output_v": output_v},
                )
            )
        else:
            constraints.append(
                passed(
                    "step_down_headroom",
                    "voltage",
                    "regulator",
                    "Input voltage is above target output rail.",
                    value={"input_v": input_v, "output_v": output_v},
                )
            )

    if regulator:
        selected_modules.append(regulator)
        if source_module:
            selected_modules.insert(0, source_module)
        _check_regulator(regulator, input_v, output_v, load_current_a, constraints, missing)
        op_type = "ldo_regulator" if regulator in LDO_OUTPUT_V else "buck_regulator"
        topology.append(
            TopologyOperator(
                operator_id=f"{regulator}_rail_conversion",
                operator_type=op_type,
                inputs=["input_rail", "ground"],
                outputs=["regulated_output_rail", "ground"],
                required_part_types=["regulator_module", "load"],
                required_ports=["VIN", "GND", "VOUT"],
                notes=f"{regulator} selected for bounded power rail conversion.",
                metadata={"module_id": regulator, "input_v": input_v, "output_v": output_v, "load_current_a": load_current_a},
            )
        )
    else:
        missing.append("regulator_module")
        constraints.append(
            blocked(
                "regulator_module",
                "evidence_required",
                "regulator",
                "Provide a known buck/LDO regulator module that can generate the target rail.",
            )
        )

    result = "blocked" if has_blocker(constraints, missing) else "ready_for_review"
    assumptions = [
        "Power-rail candidate is ready for human review only; output voltage must be measured before connecting loads."
        if result == "ready_for_review"
        else "Planner stopped before compile/readiness approval because rail evidence is missing or incompatible."
    ]
    if regulator in LDO_OUTPUT_V and input_v is not None and output_v is not None and load_current_a is not None:
        assumptions.append("LDO thermal estimate is first-order only; bench thermal capture still controls sustained-load confidence.")

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
        verification_gates=_verification_gates(input_v=input_v, output_v=output_v, load_current_a=load_current_a),
        recommended_build_path=build_path(available=available, selected=modules_for_build),
        result=result,
        notes="Bounded regulated power-rail topology plan.",
        metadata={
            "goal": circuit_intent.goal,
            "input_voltage_v": input_v,
            "output_voltage_v": output_v,
            "load_current_a": load_current_a,
        },
    )


def _input_voltage(intent: CircuitIntent) -> float | None:
    for row in intent.supply_rails:
        role = str(row.get("role") or row.get("kind") or row.get("name") or "").lower()
        if any(token in role for token in ("input", "source", "vin", "adapter", "battery")):
            return first_float(row, ("voltage_v", "input_voltage_v", "source_voltage_v"))
    if intent.supply_rails:
        return first_float(intent.supply_rails[0], ("voltage_v", "input_voltage_v", "source_voltage_v"))
    return voltage_from_text(intent.goal)


def _output_voltage(intent: CircuitIntent) -> float | None:
    for row in intent.voltage_constraints:
        value = first_float(row, ("output_voltage_v", "target_voltage_v", "voltage_v", "required_voltage_v"))
        if value is not None:
            return value
    for row in intent.supply_rails[1:]:
        value = first_float(row, ("output_voltage_v", "target_voltage_v", "voltage_v", "required_voltage_v"))
        if value is not None:
            return value
    text = f"{intent.goal} {intent.notes}".lower()
    if "3v3" in text or "3.3v" in text or "3.3 v" in text:
        return 3.3
    if "5v" in text or "5 v" in text:
        return 5.0
    return None


def _load_current(intent: CircuitIntent) -> float | None:
    for row in intent.current_constraints + intent.load_requirements + intent.voltage_constraints:
        value = first_float(row, ("load_current_a", "current_a", "max_current_a", "required_current_a"))
        if value is not None:
            return value
    return None


def _choose_regulator(
    available: set[str],
    *,
    input_v: float | None,
    output_v: float | None,
    load_current_a: float | None,
) -> str:
    if output_v is not None and load_current_a is not None and load_current_a <= 0.25:
        for module_id, fixed_v in LDO_OUTPUT_V.items():
            if module_id in available and abs(fixed_v - output_v) <= 0.25:
                return module_id
    if input_v is not None and output_v is not None and input_v > output_v + 1.0:
        buck = first_available(available, BUCK_MODULES)
        if buck:
            return buck
    for module_id, fixed_v in LDO_OUTPUT_V.items():
        if module_id in available and (output_v is None or abs(fixed_v - output_v) <= 0.25):
            return module_id
    return first_available(available, BUCK_MODULES)


def _check_regulator(
    module_id: str,
    input_v: float | None,
    output_v: float | None,
    load_current_a: float | None,
    constraints: List[Constraint],
    missing: List[str],
) -> None:
    min_in, max_in = module_input_range(module_id)
    if input_v is not None and min_in is not None and max_in is not None:
        if min_in <= input_v <= max_in:
            constraints.append(
                passed(
                    f"{module_id}_input_range",
                    "voltage",
                    module_id,
                    "Input rail is inside regulator input range.",
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
                    "Input rail is outside regulator input range.",
                    value={"input_v": input_v, "min_in_v": min_in, "max_in_v": max_in},
                )
            )

    if output_v is not None and module_id in LDO_OUTPUT_V and abs(LDO_OUTPUT_V[module_id] - output_v) > 0.25:
        missing.append("fixed_regulator_output_mismatch")
        constraints.append(
            blocked(
                f"{module_id}_output_voltage",
                "voltage",
                module_id,
                "Fixed-output regulator does not match target output rail.",
                value={"fixed_output_v": LDO_OUTPUT_V[module_id], "target_output_v": output_v},
            )
        )
    elif output_v is not None:
        constraints.append(
            passed(
                f"{module_id}_output_voltage",
                "voltage",
                module_id,
                "Regulator can be set or is fixed to the target output rail.",
                value={"target_output_v": output_v},
            )
        )

    current_limit_a = module_current_limit_a(module_id, default_a=3.0 if module_id == "buck-mp1584" else 2.0 if module_id == "buck-lm2596" else 1.0)
    if load_current_a is not None and current_limit_a is not None:
        if current_limit_a >= load_current_a * 1.25:
            constraints.append(
                passed(
                    f"{module_id}_current_margin",
                    "current",
                    module_id,
                    "Regulator current rating covers load current with margin.",
                    value={"current_limit_a": current_limit_a, "load_current_a": load_current_a},
                )
            )
        else:
            missing.append("regulator_current_margin")
            constraints.append(
                blocked(
                    f"{module_id}_current_margin",
                    "current",
                    module_id,
                    "Regulator current rating is too close to or below expected load current.",
                    value={"current_limit_a": current_limit_a, "load_current_a": load_current_a},
                )
            )

    if module_id in LDO_OUTPUT_V and input_v is not None and output_v is not None and load_current_a is not None:
        watts = max(0.0, input_v - output_v) * load_current_a
        if watts <= 0.5:
            constraints.append(
                passed(
                    f"{module_id}_thermal_dissipation",
                    "thermal",
                    module_id,
                    "Estimated LDO dissipation is low enough for review.",
                    value={"dissipation_w": round(watts, 3)},
                )
            )
        elif watts <= 1.0:
            constraints.append(
                warned(
                    f"{module_id}_thermal_dissipation",
                    "thermal",
                    module_id,
                    "Estimated LDO dissipation needs bench thermal confirmation.",
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
                    "Estimated LDO dissipation is too high for this bounded planner.",
                    value={"dissipation_w": round(watts, 3)},
                )
            )


def _recommended_modules(available: set[str], selected_modules: List[str]) -> List[str]:
    out = list(selected_modules)
    for module_id in ("esp32-cam-module", "esp32-devkit", "arduino-nano", "rpi-pico"):
        if module_id in available:
            out.append(module_id)
            break
    return dedupe(out)


def _verification_gates(*, input_v: float | None, output_v: float | None, load_current_a: float | None) -> List[Dict[str, Any]]:
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
