"""Bounded quantitative analysis for engineering candidates.

Calculations only run when the required declared or measured inputs exist. Missing
inputs stay explicit; no analysis result grants fabrication, power-on, motion, or
release authority.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Any, Dict, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from .machine_project import AuthorityState
from .robot_topology import RobotTopology


ENGINEERING_ANALYSIS_SCHEMA = "hardware_splicer.engineering_analysis.v1"


class AnalysisStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    REVIEW = "review"
    UNKNOWN = "unknown"


class AnalysisModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class AnalysisFinding(AnalysisModel):
    finding_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    status: AnalysisStatus
    message: str = Field(min_length=1)
    target_ids: list[str] = Field(default_factory=list)
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    blocking: bool = False
    authority: AuthorityState = AuthorityState.PROPOSED


class EngineeringAnalysisReport(AnalysisModel):
    schema_version: str = ENGINEERING_ANALYSIS_SCHEMA
    findings: list[AnalysisFinding] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def blocking_findings(self) -> list[AnalysisFinding]:
        return [row for row in self.findings if row.blocking]


_G = 9.80665


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _parts(intake: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = intake.get("available_parts") or intake.get("parts") or intake.get("resources") or []
    return [dict(row) for row in raw if isinstance(row, Mapping)] if isinstance(raw, list) else []


def _number(source: Mapping[str, Any], keys: Sequence[str]) -> float | None:
    for key in keys:
        value = source.get(key)
        if value is None or isinstance(value, bool):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _find_part(parts: Sequence[Mapping[str, Any]], tokens: Sequence[str]) -> list[Mapping[str, Any]]:
    lowered = [token.lower() for token in tokens]
    rows: list[Mapping[str, Any]] = []
    for part in parts:
        text = " ".join(str(part.get(key) or "") for key in ("name", "type", "role", "category")).lower()
        if any(token in text for token in lowered):
            rows.append(part)
    return rows


def _unknown(
    finding_id: str,
    category: str,
    message: str,
    missing: Sequence[str],
    *,
    target_ids: Sequence[str] = (),
    blocking: bool = False,
) -> AnalysisFinding:
    return AnalysisFinding(
        finding_id=finding_id,
        category=category,
        status=AnalysisStatus.UNKNOWN,
        message=message,
        target_ids=list(target_ids),
        missing_inputs=list(missing),
        blocking=blocking,
    )


def _power_runtime(intake: Mapping[str, Any]) -> list[AnalysisFinding]:
    constraints = _mapping(intake.get("constraints"))
    parts = _parts(intake)
    batteries = _find_part(parts, ("battery", "power pack"))
    battery = batteries[0] if batteries else {}
    voltage = _number(constraints, ("battery_voltage_v", "voltage_v", "nominal_voltage_v"))
    if voltage is None:
        voltage = _number(battery, ("voltage_v", "nominal_voltage_v", "battery_voltage_v"))
    energy_wh = _number(constraints, ("battery_energy_wh", "capacity_wh"))
    if energy_wh is None:
        energy_wh = _number(battery, ("energy_wh", "capacity_wh"))
    capacity_ah = _number(constraints, ("battery_capacity_ah", "capacity_ah"))
    if capacity_ah is None:
        capacity_ah = _number(battery, ("capacity_ah", "battery_capacity_ah"))
    if energy_wh is None and voltage is not None and capacity_ah is not None:
        energy_wh = voltage * capacity_ah

    load_power_w = _number(constraints, ("continuous_power_w", "average_power_w", "load_power_w"))
    if load_power_w is None:
        total = 0.0
        found = False
        for part in parts:
            quantity = max(int(part.get("quantity") or 1), 1)
            power = _number(part, ("continuous_power_w", "average_power_w", "power_w"))
            current = _number(part, ("continuous_current_a", "average_current_a", "current_a"))
            part_voltage = _number(part, ("voltage_v", "nominal_voltage_v")) or voltage
            if power is not None:
                total += power * quantity
                found = True
            elif current is not None and part_voltage is not None:
                total += current * part_voltage * quantity
                found = True
        if found:
            load_power_w = total

    requested_runtime_min = _number(constraints, ("runtime_min", "minimum_runtime_min", "target_runtime_min"))
    derating = _number(constraints, ("battery_usable_fraction", "usable_energy_fraction")) or 0.8
    findings: list[AnalysisFinding] = []
    if energy_wh is None or load_power_w is None or load_power_w <= 0:
        missing = []
        if energy_wh is None:
            missing.append("battery_energy_wh or battery_voltage_v + battery_capacity_ah")
        if load_power_w is None or load_power_w <= 0:
            missing.append("continuous or average load power")
        findings.append(
            _unknown(
                "analysis-runtime",
                "power_runtime",
                "Runtime cannot be calculated from the available battery and load data.",
                missing,
                target_ids=("power-system",),
                blocking=requested_runtime_min is not None,
            )
        )
    else:
        runtime_min = energy_wh * max(min(derating, 1.0), 0.0) / load_power_w * 60.0
        passed = requested_runtime_min is None or runtime_min >= requested_runtime_min
        findings.append(
            AnalysisFinding(
                finding_id="analysis-runtime",
                category="power_runtime",
                status=AnalysisStatus.PASS if passed else AnalysisStatus.FAIL,
                message=(
                    f"Estimated bounded runtime is {runtime_min:.1f} minutes"
                    + (f" against a {requested_runtime_min:.1f} minute requirement." if requested_runtime_min is not None else ".")
                ),
                target_ids=["power-system"],
                inputs={
                    "battery_energy_wh": energy_wh,
                    "load_power_w": load_power_w,
                    "usable_energy_fraction": derating,
                    "requested_runtime_min": requested_runtime_min,
                },
                outputs={"estimated_runtime_min": round(runtime_min, 2)},
                assumptions=["Constant average load and declared usable battery fraction."],
                blocking=not passed,
            )
        )

    supply_limit_a = _number(constraints, ("supply_current_limit_a", "battery_current_limit_a", "current_limit_a"))
    peak_current_a = _number(constraints, ("peak_current_a", "startup_current_a", "maximum_current_a"))
    if peak_current_a is None:
        total_peak = 0.0
        found_peak = False
        for part in parts:
            peak = _number(part, ("peak_current_a", "stall_current_a", "startup_current_a"))
            if peak is not None:
                total_peak += peak * max(int(part.get("quantity") or 1), 1)
                found_peak = True
        if found_peak:
            peak_current_a = total_peak
    if supply_limit_a is None or peak_current_a is None:
        findings.append(
            _unknown(
                "analysis-current-margin",
                "power_current",
                "Peak-current margin is unresolved.",
                [
                    name
                    for name, value in (
                        ("supply_current_limit_a", supply_limit_a),
                        ("peak_current_a or per-load peak/stall current", peak_current_a),
                    )
                    if value is None
                ],
                target_ids=("power-system",),
                blocking=True,
            )
        )
    else:
        margin = supply_limit_a - peak_current_a
        findings.append(
            AnalysisFinding(
                finding_id="analysis-current-margin",
                category="power_current",
                status=AnalysisStatus.PASS if margin >= 0 else AnalysisStatus.FAIL,
                message=f"Declared supply current margin is {margin:.2f} A.",
                target_ids=["power-system"],
                inputs={"supply_current_limit_a": supply_limit_a, "peak_current_a": peak_current_a},
                outputs={"current_margin_a": round(margin, 3)},
                blocking=margin < 0,
            )
        )
    return findings


def _stability_and_payload(intake: Mapping[str, Any], topology: RobotTopology) -> list[AnalysisFinding]:
    constraints = _mapping(intake.get("constraints"))
    payload_mass_kg = _number(constraints, ("payload_mass_kg",))
    if payload_mass_kg is None:
        payload_g = _number(constraints, ("payload_mass_g", "payload_g"))
        if payload_g is not None:
            payload_mass_kg = payload_g / 1000.0
    payload_limit_kg = _number(constraints, ("payload_limit_kg", "maximum_payload_kg", "rated_payload_kg"))
    findings: list[AnalysisFinding] = []
    if payload_mass_kg is None or payload_limit_kg is None:
        findings.append(
            _unknown(
                "analysis-payload-margin",
                "payload",
                "Payload capacity margin cannot be calculated.",
                [
                    name
                    for name, value in (
                        ("payload_mass_kg", payload_mass_kg),
                        ("payload_limit_kg", payload_limit_kg),
                    )
                    if value is None
                ],
                target_ids=(topology.root_link_id,),
                blocking=payload_mass_kg is not None,
            )
        )
    else:
        margin = payload_limit_kg - payload_mass_kg
        findings.append(
            AnalysisFinding(
                finding_id="analysis-payload-margin",
                category="payload",
                status=AnalysisStatus.PASS if margin >= 0 else AnalysisStatus.FAIL,
                message=f"Declared payload margin is {margin:.3f} kg.",
                target_ids=[topology.root_link_id],
                inputs={"payload_mass_kg": payload_mass_kg, "payload_limit_kg": payload_limit_kg},
                outputs={"payload_margin_kg": round(margin, 4)},
                blocking=margin < 0,
            )
        )

    support_width_mm = _number(constraints, ("support_width_mm", "wheel_track_mm", "base_width_mm", "width_mm"))
    cg_height_mm = _number(constraints, ("combined_cg_height_mm", "center_of_mass_height_mm", "current_payload_height_mm", "payload_height_mm"))
    required_margin_deg = _number(constraints, ("static_tilt_margin_deg", "minimum_tilt_margin_deg"))
    if support_width_mm is None or cg_height_mm is None or cg_height_mm <= 0:
        findings.append(
            _unknown(
                "analysis-static-stability",
                "stability",
                "Static tip-angle margin requires measured support geometry and combined center-of-mass height.",
                [
                    name
                    for name, value in (
                        ("support_width_mm or wheel_track_mm", support_width_mm),
                        ("combined_cg_height_mm", cg_height_mm),
                    )
                    if value is None
                ],
                target_ids=(topology.root_link_id,),
                blocking=required_margin_deg is not None or "tip" in str(intake.get("goal") or "").lower(),
            )
        )
    else:
        static_tip_angle_deg = math.degrees(math.atan((support_width_mm / 2.0) / cg_height_mm))
        passed = required_margin_deg is None or static_tip_angle_deg >= required_margin_deg
        findings.append(
            AnalysisFinding(
                finding_id="analysis-static-stability",
                category="stability",
                status=AnalysisStatus.PASS if passed else AnalysisStatus.FAIL,
                message=(
                    f"Idealized static lateral tip angle is {static_tip_angle_deg:.1f}°"
                    + (f" against a {required_margin_deg:.1f}° requirement." if required_margin_deg is not None else ".")
                ),
                target_ids=[topology.root_link_id],
                inputs={
                    "support_width_mm": support_width_mm,
                    "combined_cg_height_mm": cg_height_mm,
                    "required_tilt_margin_deg": required_margin_deg,
                },
                outputs={"idealized_static_tip_angle_deg": round(static_tip_angle_deg, 2)},
                assumptions=[
                    "Rigid body on level ground, centered CG, quasi-static lateral tipping, no suspension or dynamic effects."
                ],
                blocking=not passed,
            )
        )
    return findings


def _torque(intake: Mapping[str, Any], topology: RobotTopology) -> AnalysisFinding:
    constraints = _mapping(intake.get("constraints"))
    payload_mass_kg = _number(constraints, ("payload_mass_kg",))
    if payload_mass_kg is None:
        payload_g = _number(constraints, ("payload_mass_g",))
        if payload_g is not None:
            payload_mass_kg = payload_g / 1000.0
    lever_arm_m = _number(constraints, ("payload_lever_arm_m", "lever_arm_m"))
    if lever_arm_m is None:
        lever_arm_mm = _number(constraints, ("payload_lever_arm_mm", "lever_arm_mm"))
        if lever_arm_mm is not None:
            lever_arm_m = lever_arm_mm / 1000.0
    actuator_torque_nm = _number(constraints, ("actuator_continuous_torque_nm", "actuator_torque_nm"))
    load_sharing = _number(constraints, ("load_sharing_actuator_count",)) or 1.0
    missing = [
        name
        for name, value in (
            ("payload_mass_kg", payload_mass_kg),
            ("payload_lever_arm_m", lever_arm_m),
            ("actuator_continuous_torque_nm", actuator_torque_nm),
        )
        if value is None
    ]
    if missing:
        return _unknown(
            "analysis-actuator-torque",
            "actuator_torque",
            "Actuator torque margin cannot be calculated.",
            missing,
            target_ids=tuple(row.actuator_id for row in topology.actuators[:4]) or (topology.topology_id,),
            blocking=topology.degree_of_freedom_count > 0,
        )
    required = payload_mass_kg * _G * lever_arm_m / max(load_sharing, 1.0)
    margin = actuator_torque_nm - required
    return AnalysisFinding(
        finding_id="analysis-actuator-torque",
        category="actuator_torque",
        status=AnalysisStatus.PASS if margin >= 0 else AnalysisStatus.FAIL,
        message=f"Idealized actuator torque margin is {margin:.3f} N·m.",
        target_ids=[row.actuator_id for row in topology.actuators[:4]] or [topology.topology_id],
        inputs={
            "payload_mass_kg": payload_mass_kg,
            "payload_lever_arm_m": lever_arm_m,
            "load_sharing_actuator_count": load_sharing,
            "actuator_continuous_torque_nm": actuator_torque_nm,
        },
        outputs={"required_static_torque_nm": round(required, 4), "torque_margin_nm": round(margin, 4)},
        assumptions=["Static gravity load only; acceleration, impact, friction, gearing losses, and safety factor are excluded."],
        blocking=margin < 0,
    )


def _dimensional_envelope(intake: Mapping[str, Any], topology: RobotTopology) -> AnalysisFinding:
    constraints = _mapping(intake.get("constraints"))
    candidate_width = _number(constraints, ("candidate_width_mm", "base_width_mm", "actual_width_mm"))
    max_width = _number(constraints, ("maximum_width_mm", "max_width_mm", "width_limit_mm"))
    declared_width = _number(constraints, ("width_mm",))
    if max_width is None and candidate_width is not None and declared_width is not None:
        max_width = declared_width
    if candidate_width is None or max_width is None:
        return _unknown(
            "analysis-dimensional-envelope",
            "dimensional_envelope",
            "Candidate width cannot be checked against the user envelope.",
            [
                name
                for name, value in (
                    ("candidate_width_mm", candidate_width),
                    ("maximum_width_mm", max_width),
                )
                if value is None
            ],
            target_ids=(topology.root_link_id,),
            blocking=max_width is not None,
        )
    margin = max_width - candidate_width
    return AnalysisFinding(
        finding_id="analysis-dimensional-envelope",
        category="dimensional_envelope",
        status=AnalysisStatus.PASS if margin >= 0 else AnalysisStatus.FAIL,
        message=f"Candidate width margin is {margin:.1f} mm.",
        target_ids=[topology.root_link_id],
        inputs={"candidate_width_mm": candidate_width, "maximum_width_mm": max_width},
        outputs={"width_margin_mm": round(margin, 2)},
        blocking=margin < 0,
    )


def _thermal(intake: Mapping[str, Any]) -> AnalysisFinding:
    constraints = _mapping(intake.get("constraints"))
    loss_w = _number(constraints, ("estimated_power_loss_w", "thermal_loss_w"))
    thermal_resistance = _number(constraints, ("thermal_resistance_c_per_w", "theta_ca_c_per_w"))
    ambient_c = _number(constraints, ("ambient_temperature_c", "ambient_c"))
    max_temp_c = _number(constraints, ("maximum_component_temperature_c", "max_temperature_c"))
    missing = [
        name
        for name, value in (
            ("estimated_power_loss_w", loss_w),
            ("thermal_resistance_c_per_w", thermal_resistance),
            ("ambient_temperature_c", ambient_c),
            ("maximum_component_temperature_c", max_temp_c),
        )
        if value is None
    ]
    if missing:
        return _unknown(
            "analysis-thermal",
            "thermal",
            "Thermal rise cannot be estimated.",
            missing,
            target_ids=("power-system",),
            blocking=False,
        )
    estimated = ambient_c + loss_w * thermal_resistance
    margin = max_temp_c - estimated
    return AnalysisFinding(
        finding_id="analysis-thermal",
        category="thermal",
        status=AnalysisStatus.PASS if margin >= 0 else AnalysisStatus.FAIL,
        message=f"Estimated steady-state temperature margin is {margin:.1f} °C.",
        target_ids=["power-system"],
        inputs={
            "estimated_power_loss_w": loss_w,
            "thermal_resistance_c_per_w": thermal_resistance,
            "ambient_temperature_c": ambient_c,
            "maximum_component_temperature_c": max_temp_c,
        },
        outputs={"estimated_component_temperature_c": round(estimated, 2), "temperature_margin_c": round(margin, 2)},
        assumptions=["Lumped steady-state thermal resistance model."],
        blocking=margin < 0,
    )


def analyze_engineering_candidate(
    intake: Mapping[str, Any],
    *,
    topology: RobotTopology,
) -> EngineeringAnalysisReport:
    findings: list[AnalysisFinding] = []
    findings.extend(_power_runtime(intake))
    findings.extend(_stability_and_payload(intake, topology))
    findings.append(_torque(intake, topology))
    findings.append(_dimensional_envelope(intake, topology))
    findings.append(_thermal(intake))
    counts = {status.value: sum(row.status == status for row in findings) for status in AnalysisStatus}
    return EngineeringAnalysisReport(
        findings=findings,
        summary={
            "finding_count": len(findings),
            "blocking_count": sum(row.blocking for row in findings),
            "counts_by_status": counts,
            "known_fraction": round(sum(row.status != AnalysisStatus.UNKNOWN for row in findings) / len(findings), 3) if findings else 1.0,
        },
        metadata={
            "candidate_only": True,
            "analysis_authority": AuthorityState.PROPOSED.value,
            "physical_validation_required": True,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        },
    )
