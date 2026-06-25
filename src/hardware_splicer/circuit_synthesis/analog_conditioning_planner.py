"""Bounded analog sensor-to-ADC conditioning planner."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from ..pcb.module_registry import find_module
from .common import (
    available_module_ids,
    blocked,
    build_path,
    dedupe,
    first_available,
    first_controller,
    first_float,
    first_power_source,
    has_blocker,
    module_has_role,
    module_logic_voltage,
    passed,
    warned,
)
from .ir import CircuitIntent, Constraint, SynthesisCandidate, TopologyOperator


KNOWN_ANALOG_MODULES = (
    "soil_moisture",
    "ldr_photoresistor",
    "mq-2_gas_sensor",
    "potentiometer",
)


def plan_analog_conditioning(intent: CircuitIntent | Mapping[str, Any]) -> SynthesisCandidate:
    """Plan an analog source into a controller ADC input."""

    circuit_intent = intent if isinstance(intent, CircuitIntent) else CircuitIntent.from_dict(intent)
    available = available_module_ids(circuit_intent)
    constraints: List[Constraint] = []
    missing: List[str] = []
    topology: List[TopologyOperator] = []

    controller = first_controller(available)
    power_source = first_power_source(available)
    analog_source = _select_analog_source(available)
    source_max_v = _source_max_voltage(circuit_intent)
    adc_max_v = _adc_max_voltage(circuit_intent, controller)
    sample_rate_hz = _sample_rate(circuit_intent)
    wants_filter = _wants_filter(circuit_intent)

    if not controller:
        missing.append("controller_module")
        constraints.append(blocked("controller_module", "evidence_required", "controller", "Provide a known controller with an ADC input."))
    elif not _controller_has_adc(controller):
        missing.append("controller_adc_pin")
        constraints.append(blocked("controller_adc_pin", "evidence_required", controller, "Selected controller must expose an ADC-capable pin."))
    if not analog_source:
        missing.append("analog_source_or_sensor")
        constraints.append(blocked("analog_source_or_sensor", "evidence_required", "analog_source", "Provide an analog-output sensor/source module."))
    if source_max_v is None:
        missing.append("analog_source_max_voltage")
        constraints.append(blocked("analog_source_max_voltage", "voltage", "analog_source", "Declare maximum analog source voltage."))
    if adc_max_v is None:
        missing.append("adc_input_max_voltage")
        constraints.append(blocked("adc_input_max_voltage", "voltage", "adc", "Declare or infer ADC maximum input voltage."))

    if source_max_v is not None and adc_max_v is not None:
        if source_max_v <= adc_max_v + 0.05:
            constraints.append(
                passed(
                    "adc_voltage_range",
                    "voltage",
                    "adc",
                    "Analog source is inside ADC input range.",
                    value={"source_max_v": source_max_v, "adc_max_v": adc_max_v},
                )
            )
            topology.append(
                TopologyOperator(
                    operator_id="direct_adc_interface",
                    operator_type="adc_interface",
                    inputs=["analog_source", "ground"],
                    outputs=["adc_input"],
                    required_part_types=["analog_source", "controller_adc"],
                    required_ports=["AOUT", "ADC", "GND"],
                    notes="Direct ADC candidate; input impedance and calibration still need review.",
                    metadata={"source_max_v": source_max_v, "adc_max_v": adc_max_v},
                )
            )
        else:
            ratio = adc_max_v / source_max_v
            divider = _divider_values(ratio)
            constraints.append(
                passed(
                    "adc_voltage_divider_ratio",
                    "voltage",
                    "adc",
                    "Generated divider ratio keeps ADC input below maximum voltage.",
                    value={
                        "source_max_v": source_max_v,
                        "adc_max_v": adc_max_v,
                        "divider_ratio": round(ratio, 4),
                        **divider,
                    },
                )
            )
            topology.append(
                TopologyOperator(
                    operator_id="adc_protection_divider",
                    operator_type="voltage_divider",
                    inputs=["analog_source", "ground"],
                    outputs=["adc_safe_signal"],
                    required_part_types=["resistor_divider", "controller_adc"],
                    required_ports=["AOUT", "ADC", "GND"],
                    notes="Divider values are first-pass synthesis values; measure the output before connecting to ADC.",
                    metadata={"source_max_v": source_max_v, "adc_max_v": adc_max_v, **divider},
                )
            )
            topology.append(
                TopologyOperator(
                    operator_id="adc_input_clamp_review",
                    operator_type="protection_diode",
                    inputs=["adc_safe_signal", "logic_rail", "ground"],
                    outputs=["adc_overvoltage_clamp_candidate"],
                    required_part_types=["series_resistor_or_clamp"],
                    required_ports=["ADC", "VREF", "GND"],
                    notes="Use protection appropriate to the controller ADC absolute maximum rating.",
                )
            )

    if wants_filter:
        if sample_rate_hz is None:
            missing.append("analog_sample_rate")
            constraints.append(blocked("analog_sample_rate", "frequency", "adc", "Declare sample rate or desired filter cutoff."))
        else:
            cutoff_hz = max(1.0, min(sample_rate_hz / 5.0, 100.0))
            constraints.append(
                warned(
                    "analog_rc_filter_cutoff",
                    "frequency",
                    "adc",
                    "Generated RC filter cutoff is a first-order noise-reduction estimate.",
                    value={"sample_rate_hz": sample_rate_hz, "suggested_cutoff_hz": round(cutoff_hz, 2)},
                )
            )
            topology.append(
                TopologyOperator(
                    operator_id="adc_rc_noise_filter",
                    operator_type="rc_filter",
                    inputs=["adc_safe_signal", "ground"],
                    outputs=["filtered_adc_signal"],
                    required_part_types=["series_resistor", "shunt_capacitor"],
                    required_ports=["ADC", "GND"],
                    notes="Filter cutoff must be reviewed against sensor bandwidth and ADC sampling strategy.",
                    metadata={"sample_rate_hz": sample_rate_hz, "suggested_cutoff_hz": round(cutoff_hz, 2)},
                )
            )

    selected_modules = dedupe([power_source, controller, analog_source])
    result = "blocked" if has_blocker(constraints, missing) else "ready_for_review"
    return SynthesisCandidate(
        candidate_id="analog_conditioning_candidate",
        selected_parts=[
            {
                "id": analog_source or "analog_source",
                "type": "analog_conditioning",
                "source_max_v": source_max_v,
                "adc_max_v": adc_max_v,
                "sample_rate_hz": sample_rate_hz,
            }
        ],
        selected_modules=dedupe([analog_source] if analog_source else []),
        generated_topology=topology,
        assumptions=[
            "Analog-conditioning candidate is ready for human review only; divider output and ADC readings must be measured."
            if result == "ready_for_review"
            else "Planner stopped before compile/readiness approval because analog/ADC constraints are missing."
        ],
        missing_evidence=dedupe(missing),
        constraints=constraints,
        verification_gates=_verification_gates(source_max_v=source_max_v, adc_max_v=adc_max_v),
        recommended_build_path=build_path(
            available=available,
            selected=selected_modules,
            build_id="generic_low_voltage_build",
            notes=[
                "Compile path captures known modules; discrete divider/filter parts are synthesis topology and require review.",
                "ADC range measurements close the authority gate, not planner confidence.",
            ],
        ),
        result=result,
        notes="Bounded analog sensor-to-ADC conditioning topology plan.",
        metadata={"goal": circuit_intent.goal, "controller": controller, "analog_source": analog_source},
    )


def _select_analog_source(available: set[str]) -> str:
    known = first_available(available, KNOWN_ANALOG_MODULES)
    if known:
        return known
    for module_id in sorted(available):
        if module_has_role(module_id, {"analog_in"}):
            spec = find_module(module_id) or {}
            if spec.get("category") != "mcu":
                return module_id
    return ""


def _source_max_voltage(intent: CircuitIntent) -> float | None:
    for row in intent.signal_requirements + intent.voltage_constraints + intent.load_requirements:
        value = first_float(row, ("source_max_v", "analog_max_v", "sensor_output_max_v", "output_max_v", "voltage_v"))
        if value is not None:
            return value
    return None


def _adc_max_voltage(intent: CircuitIntent, controller: str) -> float | None:
    for row in intent.signal_requirements + intent.voltage_constraints:
        value = first_float(row, ("adc_max_v", "adc_voltage_v", "controller_adc_max_v", "controller_voltage_v"))
        if value is not None:
            return value
    return module_logic_voltage(controller) if controller else None


def _sample_rate(intent: CircuitIntent) -> float | None:
    for row in intent.frequency_constraints + intent.signal_requirements:
        value = first_float(row, ("sample_rate_hz", "sampling_hz", "frequency_hz", "bandwidth_hz"))
        if value is not None:
            return value
    return None


def _wants_filter(intent: CircuitIntent) -> bool:
    text = f"{intent.goal} {intent.notes}".lower()
    if any(token in text for token in ("filter", "noisy", "noise", "smooth", "rc")):
        return True
    return any(str(row.get("filter") or row.get("noise_filter") or "").lower() in {"1", "true", "yes", "rc"} for row in intent.signal_requirements)


def _controller_has_adc(controller: str) -> bool:
    return bool(controller and module_has_role(controller, {"analog_in"}))


def _divider_values(ratio: float) -> Dict[str, Any]:
    # Rbottom/(Rtop+Rbottom)=ratio. Use a 10k lower leg for a readable first-pass value.
    bottom = 10_000
    top = int(round(bottom * (1.0 / max(ratio, 0.01) - 1.0), -2))
    return {"r_top_ohm": max(100, top), "r_bottom_ohm": bottom}


def _verification_gates(*, source_max_v: float | None, adc_max_v: float | None) -> List[Dict[str, Any]]:
    return [
        {
            "gate_id": "adc_input_range_measurement",
            "gate_type": "dmm_voltage",
            "critical": True,
            "prompt": "Measure ADC input voltage at minimum, nominal, and maximum sensor output before connecting to controller firmware.",
            "expected_source_max_v": source_max_v,
            "adc_max_v": adc_max_v,
            "status": "open",
        },
        {
            "gate_id": "adc_firmware_calibration_capture",
            "gate_type": "bench_capture",
            "critical": True,
            "prompt": "Capture raw ADC counts for known physical input points and store calibration notes.",
            "status": "open",
        },
    ]
