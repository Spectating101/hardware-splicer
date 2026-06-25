"""Trusted bounded topology primitive library.

This is the ceiling contract for Hardware-Splicer's backend synthesis layer.
It deliberately describes low-voltage mechatronics primitives, not universal
electronics synthesis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping

from .ir import SynthesisCandidate


SCHEMA_VERSION = "hardware_splicer.topology_library.v1"
AUTHORITY_SCHEMA_VERSION = "hardware_splicer.topology_authority.v1"
DOMAIN = "low_voltage_mechatronics"

TRUSTED_STATUSES = {
    "module_graph",
    "terminal_semantics",
    "physical_support",
    "review_evidence",
}


@dataclass(frozen=True)
class TopologyPrimitive:
    primitive_id: str
    operator_type: str
    implementation_status: str
    summary: str
    required_inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    support_parts: List[str] = field(default_factory=list)
    static_checks: List[str] = field(default_factory=list)
    bench_gates: List[str] = field(default_factory=list)
    physical_lowering: str = "none"
    boundary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primitive_id": self.primitive_id,
            "operator_type": self.operator_type,
            "domain": DOMAIN,
            "implementation_status": self.implementation_status,
            "summary": self.summary,
            "required_inputs": list(self.required_inputs),
            "outputs": list(self.outputs),
            "support_parts": list(self.support_parts),
            "static_checks": list(self.static_checks),
            "bench_gates": list(self.bench_gates),
            "physical_lowering": self.physical_lowering,
            "trusted_for_ceiling": self.implementation_status in TRUSTED_STATUSES,
            "boundary": self.boundary,
        }


PRIMITIVES: Dict[str, TopologyPrimitive] = {
    "low_side_switch": TopologyPrimitive(
        primitive_id="primitive.low_side_switch",
        operator_type="low_side_switch",
        implementation_status="module_graph",
        summary="MCU controls a low-voltage DC load through a logic-level MOSFET module.",
        required_inputs=["load_supply", "control_signal", "ground", "load_current_estimate"],
        outputs=["switched_load_return"],
        support_parts=["flyback_or_tvs_for_inductive_load"],
        static_checks=["switch_current_rating", "logic_drive_voltage", "supply_current_margin"],
        bench_gates=["psu_current_limit_ramp", "thermal_touch_check", "inductive_protection_inspection"],
        physical_lowering="driver module graph; protection remains evidence unless explicit part is selected",
        boundary="Low-voltage DC only; not mains switching.",
    ),
    "motor_driver": TopologyPrimitive(
        primitive_id="primitive.motor_driver",
        operator_type="motor_driver",
        implementation_status="module_graph",
        summary="Rated motor-driver module path for DC motor/pump/fan loads.",
        required_inputs=["motor_supply", "control_signal", "ground", "load_current_estimate"],
        outputs=["motor_outputs"],
        support_parts=["integrated_or_external_inductive_protection"],
        static_checks=["driver_current_rating", "logic_drive_voltage", "supply_current_margin"],
        bench_gates=["psu_current_limit_ramp", "loaded_current_capture"],
        physical_lowering="known driver module graph",
        boundary="Does not tune motor control loops or certify stall behavior.",
    ),
    "h_bridge": TopologyPrimitive(
        primitive_id="primitive.h_bridge",
        operator_type="h_bridge",
        implementation_status="terminal_semantics",
        summary="Bidirectional DC motor drive with floating motor terminals.",
        required_inputs=["motor_supply", "control_signals", "ground", "run_or_stall_current"],
        outputs=["floating_motor_terminal_a", "floating_motor_terminal_b"],
        support_parts=["rated_h_bridge_module"],
        static_checks=["h_bridge_current_margin", "logic_drive_voltage"],
        bench_gates=["direction_test", "current_limit_ramp", "thermal_check"],
        physical_lowering="module graph plus floating_motor_terminal semantics",
        boundary="No closed-loop motor controller synthesis.",
    ),
    "relay_driver": TopologyPrimitive(
        primitive_id="primitive.relay_driver",
        operator_type="relay_driver",
        implementation_status="terminal_semantics",
        summary="Low-voltage relay module control with isolated contact semantics.",
        required_inputs=["logic_control", "relay_supply", "load_supply", "load_current"],
        outputs=["isolated_switched_contact"],
        support_parts=["relay_module", "contact_suppression_for_inductive_loads"],
        static_checks=["contact_current_review", "logic_drive_voltage", "hazardous_load_block"],
        bench_gates=["coil_current_check", "contact_continuity_check", "low_voltage_first_power"],
        physical_lowering="module graph plus isolated_relay_contact semantics",
        boundary="Mains or hazardous loads remain blocked/review-only.",
    ),
    "voltage_divider": TopologyPrimitive(
        primitive_id="primitive.voltage_divider",
        operator_type="voltage_divider",
        implementation_status="physical_support",
        summary="Two-resistor analog scaling network for ADC protection/range matching.",
        required_inputs=["source_voltage_max", "adc_voltage_max", "ground"],
        outputs=["scaled_analog_signal"],
        support_parts=["upper_resistor", "lower_resistor"],
        static_checks=["divider_ratio", "estimated_adc_max_voltage"],
        bench_gates=["adc_input_range_measurement"],
        physical_lowering="synthetic R footprints and graph/netlist/BOM nodes when endpoints are unambiguous",
        boundary="Impedance, noise, calibration, and source loading still require review.",
    ),
    "rc_filter": TopologyPrimitive(
        primitive_id="primitive.rc_filter",
        operator_type="rc_filter",
        implementation_status="physical_support",
        summary="First-order RC low-pass filter for sensor-to-ADC noise reduction.",
        required_inputs=["signal", "ground", "sample_rate_or_cutoff"],
        outputs=["filtered_signal"],
        support_parts=["series_resistor", "shunt_capacitor"],
        static_checks=["estimated_cutoff_frequency"],
        bench_gates=["first_readout_capture", "bandwidth_review"],
        physical_lowering="synthetic R/C footprints and graph/netlist/BOM nodes when endpoints are unambiguous",
        boundary="Not a general analog filter synthesis engine.",
    ),
    "pull_up": TopologyPrimitive(
        primitive_id="primitive.pull_up",
        operator_type="pull_up",
        implementation_status="physical_support",
        summary="Signal/bus pull-up network for I2C/one-wire/digital idle definition.",
        required_inputs=["signal_bus", "logic_rail"],
        outputs=["defined_idle_level"],
        support_parts=["pullup_resistor_or_breakout_evidence"],
        static_checks=["bus_pullup_presence"],
        bench_gates=["first_bus_readout"],
        physical_lowering="synthetic 4.7k/10k resistor footprints for bounded bus patterns",
        boundary="Does not size pull-ups from bus capacitance yet.",
    ),
    "pull_down": TopologyPrimitive(
        primitive_id="primitive.pull_down",
        operator_type="pull_down",
        implementation_status="physical_support",
        summary="Signal pull-down network for known idle-low inputs.",
        required_inputs=["signal", "ground"],
        outputs=["defined_idle_level"],
        support_parts=["pulldown_resistor"],
        static_checks=["idle_state_review"],
        bench_gates=["first_gpio_readout"],
        physical_lowering="synthetic resistor footprint when endpoint is unambiguous",
        boundary="Not used by all current planners.",
    ),
    "sensor_interface": TopologyPrimitive(
        primitive_id="primitive.sensor_interface",
        operator_type="sensor_interface",
        implementation_status="module_graph",
        summary="MCU-to-sensor/display wiring with bus, rail, and evidence checks.",
        required_inputs=["controller", "sensor_or_interface", "supply", "ground"],
        outputs=["sensor_reading"],
        support_parts=["pullups_or_level_shift_when_required"],
        static_checks=["supply_range", "logic_voltage", "bus_requirements"],
        bench_gates=["first_readout_capture"],
        physical_lowering="known module graph plus support primitives",
        boundary="Does not synthesize arbitrary sensor front ends.",
    ),
    "adc_interface": TopologyPrimitive(
        primitive_id="primitive.adc_interface",
        operator_type="adc_interface",
        implementation_status="module_graph",
        summary="Direct analog source to controller ADC when source range is safe.",
        required_inputs=["analog_source", "adc_input", "ground"],
        outputs=["adc_reading"],
        support_parts=[],
        static_checks=["adc_voltage_range"],
        bench_gates=["adc_input_range_measurement"],
        physical_lowering="module graph only",
        boundary="Calibration and impedance remain review items.",
    ),
    "level_shifter": TopologyPrimitive(
        primitive_id="primitive.level_shifter",
        operator_type="level_shifter",
        implementation_status="module_graph",
        summary="Logic-level translation through a known shifter module.",
        required_inputs=["low_voltage_logic", "high_voltage_logic", "shared_ground"],
        outputs=["translated_bus_or_signal"],
        support_parts=["level_shifter_module"],
        static_checks=["channel_count", "logic_voltage_ranges"],
        bench_gates=["first_signal_toggle"],
        physical_lowering="known module graph",
        boundary="Directionality and speed limitations require review.",
    ),
    "buck_regulator": TopologyPrimitive(
        primitive_id="primitive.buck_regulator",
        operator_type="buck_regulator",
        implementation_status="module_graph",
        summary="Step-down regulated rail using a known buck module.",
        required_inputs=["input_voltage", "target_voltage", "load_current"],
        outputs=["regulated_output_rail"],
        support_parts=["buck_module"],
        static_checks=["input_range", "output_current_margin"],
        bench_gates=["loaded_rail_voltage_capture"],
        physical_lowering="known module graph",
        boundary="No custom switcher compensation/layout synthesis.",
    ),
    "boost_regulator": TopologyPrimitive(
        primitive_id="primitive.boost_regulator",
        operator_type="boost_regulator",
        implementation_status="module_graph",
        summary="Step-up regulated rail using a known boost module.",
        required_inputs=["input_voltage", "target_voltage", "load_current"],
        outputs=["regulated_output_rail"],
        support_parts=["boost_module"],
        static_checks=["input_range", "output_current_margin"],
        bench_gates=["loaded_rail_voltage_capture"],
        physical_lowering="known module graph",
        boundary="No custom switcher compensation/layout synthesis.",
    ),
    "ldo_regulator": TopologyPrimitive(
        primitive_id="primitive.ldo_regulator",
        operator_type="ldo_regulator",
        implementation_status="module_graph",
        summary="Linear regulator rail using a known LDO module.",
        required_inputs=["input_voltage", "target_voltage", "load_current"],
        outputs=["regulated_output_rail"],
        support_parts=["ldo_module"],
        static_checks=["dropout_margin", "thermal_dissipation"],
        bench_gates=["loaded_rail_voltage_capture", "thermal_check"],
        physical_lowering="known module graph",
        boundary="Thermal margin can block; no bare regulator PCB synthesis.",
    ),
    "battery_charger": TopologyPrimitive(
        primitive_id="primitive.battery_charger",
        operator_type="battery_charger",
        implementation_status="review_evidence",
        summary="Single-cell Li-ion/LiPo charging path through known charger module.",
        required_inputs=["usb_or_charge_input", "protected_cell_evidence", "load_current"],
        outputs=["battery_voltage_rail"],
        support_parts=["protected_cell_or_protection_board"],
        static_checks=["protection_evidence", "charge_current_review"],
        bench_gates=["battery_protection_inspection", "loaded_rail_capture"],
        physical_lowering="charger module graph; cell/protection remains evidence item",
        boundary="Does not certify battery safety or design protection circuitry.",
    ),
    "protection_diode": TopologyPrimitive(
        primitive_id="primitive.protection_diode",
        operator_type="protection_diode",
        implementation_status="review_evidence",
        summary="Flyback, TVS, clamp, or snubber protection requirement.",
        required_inputs=["protected_node", "return_or_rail", "energy_source"],
        outputs=["clamped_or_suppressed_transient"],
        support_parts=["diode_tvs_or_snubber_selected_by_review"],
        static_checks=["protection_presence"],
        bench_gates=["polarity_and_part_inspection"],
        physical_lowering="review item unless polarity/load class is explicit",
        boundary="No arbitrary transient protection synthesis.",
    ),
    "high_side_switch": TopologyPrimitive(
        primitive_id="primitive.high_side_switch",
        operator_type="high_side_switch",
        implementation_status="planned_only",
        summary="High-side switching primitive reserved for future bounded implementation.",
        boundary="Not trusted for current ceiling.",
    ),
    "decoupling": TopologyPrimitive(
        primitive_id="primitive.decoupling",
        operator_type="decoupling",
        implementation_status="planned_only",
        summary="Decoupling capacitor placement primitive reserved for future physical lowering.",
        boundary="Currently suggestions only.",
    ),
    "series": TopologyPrimitive(
        primitive_id="primitive.series",
        operator_type="series",
        implementation_status="planned_only",
        summary="Generic series composition primitive reserved for future topology search.",
        boundary="Not trusted as arbitrary synthesis.",
    ),
    "parallel": TopologyPrimitive(
        primitive_id="primitive.parallel",
        operator_type="parallel",
        implementation_status="planned_only",
        summary="Generic parallel composition primitive reserved for future topology search.",
        boundary="Not trusted as arbitrary synthesis.",
    ),
    "analog_conditioning": TopologyPrimitive(
        primitive_id="primitive.analog_conditioning",
        operator_type="analog_conditioning",
        implementation_status="planned_only",
        summary="Composite analog conditioning primitive represented today by divider/filter/protection primitives.",
        boundary="Use the bounded sub-primitives instead.",
    ),
}


def topology_library_card() -> Dict[str, Any]:
    primitives = [primitive.to_dict() for primitive in PRIMITIVES.values()]
    trusted = [row for row in primitives if row["trusted_for_ceiling"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "domain": DOMAIN,
        "claim": "Trusted bounded low-voltage mechatronics synthesis, not universal electronics synthesis.",
        "trusted_primitive_count": len(trusted),
        "primitive_count": len(primitives),
        "trusted_operator_types": sorted(row["operator_type"] for row in trusted),
        "planned_or_review_limited_operator_types": sorted(
            row["operator_type"] for row in primitives if not row["trusted_for_ceiling"]
        ),
        "primitives": primitives,
    }


def primitive_for_operator(operator_type: str) -> Dict[str, Any] | None:
    primitive = PRIMITIVES.get(str(operator_type or ""))
    return primitive.to_dict() if primitive else None


def evaluate_topology_authority(
    candidate: SynthesisCandidate | Mapping[str, Any],
    *,
    graph: Mapping[str, Any] | None = None,
    lowering_report: Mapping[str, Any] | None = None,
    compile_ok: bool | None = None,
    build_ready: bool | None = None,
) -> Dict[str, Any]:
    """Evaluate whether a candidate sits inside the trusted synthesis ceiling."""

    synthesis_candidate = candidate if isinstance(candidate, SynthesisCandidate) else SynthesisCandidate.from_dict(candidate)
    graph = dict(graph or {})
    lowering_report = dict(lowering_report or {})
    operator_rows: List[Dict[str, Any]] = []
    unsupported: List[str] = []
    planned_only: List[str] = []
    review_limited: List[str] = []

    for operator in synthesis_candidate.generated_topology:
        primitive = primitive_for_operator(operator.operator_type)
        if primitive is None:
            unsupported.append(operator.operator_type)
            operator_rows.append(
                {
                    "operator_id": operator.operator_id,
                    "operator_type": operator.operator_type,
                    "trusted_for_ceiling": False,
                    "implementation_status": "missing",
                }
            )
            continue
        trusted = bool(primitive.get("trusted_for_ceiling"))
        status = str(primitive.get("implementation_status") or "")
        if not trusted:
            planned_only.append(operator.operator_type)
        if status == "review_evidence":
            review_limited.append(operator.operator_type)
        operator_rows.append(
            {
                "operator_id": operator.operator_id,
                "operator_type": operator.operator_type,
                "primitive_id": primitive.get("primitive_id"),
                "implementation_status": status,
                "trusted_for_ceiling": trusted,
                "physical_lowering": primitive.get("physical_lowering"),
                "boundary": primitive.get("boundary"),
            }
        )

    support_components = [dict(row) for row in graph.get("support_components") or [] if isinstance(row, Mapping)]
    physical_support = [
        row for row in support_components if row.get("placement") == "physical_synthetic_footprint"
    ]
    virtual_support = [
        row for row in support_components if row.get("placement") != "physical_synthetic_footprint"
    ]
    physical_report = dict(graph.get("physical_support_lowering") or {})
    actions = [dict(row) for row in lowering_report.get("actions") or [] if isinstance(row, Mapping)]

    blocked_constraints = [row for row in synthesis_candidate.constraints if row.status == "blocked"]
    has_unsupported_goal = any(row.type == "unsupported_goal" for row in synthesis_candidate.constraints)
    open_gates = [gate for gate in synthesis_candidate.verification_gates if str(gate.get("status") or "open") != "closed"]
    inside_ceiling = not unsupported and not planned_only and not has_unsupported_goal
    tier = _authority_tier(
        candidate=synthesis_candidate,
        inside_ceiling=inside_ceiling,
        compile_ok=compile_ok,
        build_ready=build_ready,
    )
    score = _authority_score(
        candidate=synthesis_candidate,
        inside_ceiling=inside_ceiling,
        compile_ok=compile_ok,
        build_ready=build_ready,
        review_limited=review_limited,
        physical_support_count=len(physical_support),
        virtual_support_count=len(virtual_support),
    )
    return {
        "schema_version": AUTHORITY_SCHEMA_VERSION,
        "domain": DOMAIN,
        "claim_boundary": "Bounded low-voltage mechatronics synthesis authority. Not universal electronics or production certification.",
        "candidate_id": synthesis_candidate.candidate_id,
        "candidate_result": synthesis_candidate.result,
        "inside_trusted_ceiling": inside_ceiling,
        "authority_tier": tier,
        "authority_score": score,
        "operator_count": len(operator_rows),
        "operators": operator_rows,
        "unsupported_operator_types": sorted(set(unsupported)),
        "planned_only_operator_types": sorted(set(planned_only)),
        "review_limited_operator_types": sorted(set(review_limited)),
        "blocked_constraint_count": len(blocked_constraints),
        "missing_evidence_count": len(synthesis_candidate.missing_evidence),
        "verification_gate_count": len(synthesis_candidate.verification_gates),
        "open_verification_gate_count": len(open_gates),
        "support_component_count": len(support_components),
        "physical_support_component_count": len(physical_support),
        "virtual_review_support_component_count": len(virtual_support),
        "physical_support_node_count": int(physical_report.get("node_count") or 0),
        "lowering_action_count": len(actions),
        "compile_ok": compile_ok,
        "build_ready": build_ready,
        "next_authority_gap": _next_gap(
            candidate=synthesis_candidate,
            unsupported=unsupported,
            planned_only=planned_only,
            review_limited=review_limited,
            blocked_constraints=blocked_constraints,
            virtual_support=virtual_support,
            build_ready=build_ready,
        ),
    }


def _authority_tier(
    *,
    candidate: SynthesisCandidate,
    inside_ceiling: bool,
    compile_ok: bool | None,
    build_ready: bool | None,
) -> str:
    if candidate.blocked:
        return "blocked"
    if not inside_ceiling:
        return "outside_registered_ceiling"
    if build_ready is True:
        return "bounded_compile_ready_for_review"
    if compile_ok is True:
        return "bounded_compile_review"
    return "bounded_plan_review"


def _authority_score(
    *,
    candidate: SynthesisCandidate,
    inside_ceiling: bool,
    compile_ok: bool | None,
    build_ready: bool | None,
    review_limited: List[str],
    physical_support_count: int,
    virtual_support_count: int,
) -> int:
    score = 20
    if not candidate.blocked:
        score += 20
    if inside_ceiling:
        score += 20
    if physical_support_count:
        score += 10
    if virtual_support_count == 0:
        score += 5
    if compile_ok is True:
        score += 10
    if build_ready is True:
        score += 10
    if candidate.verification_gates:
        score += 5
    if candidate.blocked:
        score = min(score, 45)
    if not inside_ceiling:
        score = min(score, 55)
    if review_limited:
        score = min(score, 85)
    return max(0, min(95, score))


def _next_gap(
    *,
    candidate: SynthesisCandidate,
    unsupported: List[str],
    planned_only: List[str],
    review_limited: List[str],
    blocked_constraints: List[Any],
    virtual_support: List[Mapping[str, Any]],
    build_ready: bool | None,
) -> str:
    if candidate.blocked:
        if candidate.missing_evidence:
            return f"Resolve missing evidence: {', '.join(candidate.missing_evidence[:4])}."
        if blocked_constraints:
            return f"Resolve blocked constraints: {', '.join(row.constraint_id for row in blocked_constraints[:4])}."
        return "Candidate is blocked before compile."
    if unsupported:
        return f"Add registered primitives for unsupported operators: {', '.join(sorted(set(unsupported)))}."
    if planned_only:
        return f"Implement planned-only primitives: {', '.join(sorted(set(planned_only)))}."
    if virtual_support:
        roles = sorted({str(row.get("role") or row.get("type") or "") for row in virtual_support if row})
        return f"Resolve review-only support items before stronger authority: {', '.join(roles[:4])}."
    if build_ready is not True:
        return "Close compile/fabrication/bench gates before stronger readiness claims."
    if review_limited:
        return f"Review-limited primitives remain: {', '.join(sorted(set(review_limited)))}."
    return "Inside current bounded synthesis ceiling; remaining claims require real bench/field evidence."
