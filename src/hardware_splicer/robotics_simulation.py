from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Mapping

from .robotics_actuation import build_robotics_actuation_packet


SCHEMA_VERSION = "hardware_splicer.robotics_simulation.v1"
BLOCKING_SEVERITIES = {"block", "blocked", "error", "critical", "unsafe"}


def build_robotics_simulation_packet(
    payload: Mapping[str, Any] | Any,
    *,
    engineering: Mapping[str, Any] | None = None,
    robotics_actuation: Mapping[str, Any] | None = None,
    mechatronics_authority: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Run deterministic robotics simulation checks over the declared hardware envelope."""

    body = _to_dict(payload)
    engineering_body = _to_dict(engineering or {})
    actuation = _to_dict(robotics_actuation or build_robotics_actuation_packet(body, engineering=engineering_body))
    mechatronics = _to_dict(mechatronics_authority or {})
    project = _project(body)
    platform = _platform(body, project)
    mechanism = _dict(body.get("mechanism"))
    constraints = _dict(project.get("constraints"))
    actuators = _list_dicts(_dict(actuation.get("actuation_profile")).get("actuators"))
    drive_requirements = _dict(actuation.get("drive_requirements"))

    findings: List[Dict[str, Any]] = []
    power_budget = _power_budget(body, actuation, drive_requirements, findings)
    runtime = _runtime_estimate(body, project, drive_requirements, actuators, power_budget, findings)
    drive = _drive_kinematics(body, project, platform, mechanism, actuators, constraints, findings)
    servo = _servo_load_margins(mechanism, actuators, findings)
    safety = _safety_envelope(body, project, platform, drive_requirements, findings)
    integration = _integration_status(mechatronics, findings)

    blocking = [row for row in findings if str(row.get("severity") or "").lower() in BLOCKING_SEVERITIES]
    warnings = [row for row in findings if str(row.get("severity") or "").lower() in {"warn", "warning"}]
    domains = _simulation_domains(power_budget, runtime, drive, servo, safety)
    ready = not blocking

    return {
        "schema_version": SCHEMA_VERSION,
        "simulation_ready": ready,
        "release_gate": "simulation_clear_for_scoped_release" if ready else "simulation_blockers_require_design_work",
        "blocking_finding_count": len(blocking),
        "warning_count": len(warnings),
        "coverage": {
            "domains": domains,
            "computed_domain_count": len(domains),
            "missing_inputs": _missing_inputs(power_budget, runtime, drive, servo),
        },
        "power_budget": power_budget,
        "runtime_estimate": runtime,
        "drive_kinematics": drive,
        "servo_load_margins": servo,
        "safety_envelope": safety,
        "integration_status": integration,
        "findings": findings,
        "blocking_findings": blocking,
        "claim_boundary": _claim_boundary(ready, domains),
    }


def _power_budget(
    body: Dict[str, Any],
    actuation: Dict[str, Any],
    drive_requirements: Dict[str, Any],
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    peak_current = _float(drive_requirements.get("estimated_peak_current_a"), 0.0)
    run_current = _float(drive_requirements.get("estimated_run_current_a"), 0.0)
    explicit_budget = _explicit_current_budget_a(body, actuation)
    margin = _ratio(explicit_budget, peak_current)

    status = "not_applicable"
    if peak_current > 0:
        status = "pass"
        if explicit_budget <= 0:
            status = "warning"
            _finding(findings, "power_budget", "warn", "No explicit actuator current budget was found for simulation.")
        elif peak_current > explicit_budget:
            status = "block"
            _finding(
                findings,
                "power_budget",
                "block",
                f"Actuator peak current {peak_current:g} A exceeds explicit current budget {explicit_budget:g} A.",
                {"peak_current_a": peak_current, "budget_a": explicit_budget},
            )
        elif margin < 1.2:
            status = "warning"
            _finding(
                findings,
                "power_budget",
                "warn",
                f"Actuator current margin is only {margin:.2f}x; target at least 1.2x before field use.",
                {"current_margin": round(margin, 3)},
            )

    return {
        "available": peak_current > 0,
        "status": status,
        "estimated_run_current_a": round(run_current, 3),
        "estimated_peak_current_a": round(peak_current, 3),
        "explicit_current_budget_a": round(explicit_budget, 3),
        "peak_current_margin": round(margin, 3) if margin else 0.0,
        "rail_peak_currents_a": _dict(drive_requirements.get("rail_peak_currents_a")),
        "required_protections": _string_list(drive_requirements.get("required_protections")),
    }


def _runtime_estimate(
    body: Dict[str, Any],
    project: Dict[str, Any],
    drive_requirements: Dict[str, Any],
    actuators: List[Dict[str, Any]],
    power_budget: Dict[str, Any],
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    battery = _battery(body, project)
    constraints = _dict(project.get("constraints"))
    target_runtime_min = _float(constraints.get("runtime_min") or constraints.get("min_runtime_min"), 0.0)
    duty_cycle = _bounded(_float(constraints.get("mission_duty_cycle"), 0.65), 0.05, 1.0)
    baseline_current_a = _float(constraints.get("baseline_current_a"), 0.25 if actuators else 0.0)
    run_current = _float(drive_requirements.get("estimated_run_current_a"), 0.0)
    voltage = _float(battery.get("nominal_voltage_v") or battery.get("voltage_v"), 0.0)
    capacity_ah = _battery_capacity_ah(battery)
    usable_fraction = _bounded(_float(battery.get("usable_fraction"), 0.8 if battery else 0.0), 0.0, 1.0)
    avg_current = max(run_current * duty_cycle + baseline_current_a, 0.0)
    energy_wh = _battery_energy_wh(battery, voltage, capacity_ah, usable_fraction)
    avg_power_w = avg_current * voltage if avg_current > 0 and voltage > 0 else 0.0
    runtime_min = (energy_wh / avg_power_w * 60.0) if avg_power_w > 0 and energy_wh > 0 else 0.0
    margin = _ratio(runtime_min, target_runtime_min)

    status = "not_applicable"
    if target_runtime_min > 0 or battery:
        status = "pass"
        if not battery:
            status = "warning"
            _finding(findings, "runtime", "warn", "Battery capacity/voltage is missing, so runtime cannot be estimated.")
        elif runtime_min <= 0:
            status = "warning"
            _finding(findings, "runtime", "warn", "Battery runtime inputs were incomplete.")
        elif target_runtime_min > 0 and runtime_min < target_runtime_min * 0.75:
            status = "block"
            _finding(
                findings,
                "runtime",
                "block",
                f"Estimated runtime {runtime_min:.1f} min is below the required {target_runtime_min:g} min.",
                {"estimated_runtime_min": round(runtime_min, 2), "target_runtime_min": target_runtime_min},
            )
        elif target_runtime_min > 0 and runtime_min < target_runtime_min * 1.2:
            status = "warning"
            _finding(
                findings,
                "runtime",
                "warn",
                f"Estimated runtime margin is only {margin:.2f}x.",
                {"runtime_margin": round(margin, 3)},
            )

    return {
        "available": bool(battery and runtime_min > 0),
        "status": status,
        "battery": battery,
        "duty_cycle": round(duty_cycle, 3),
        "baseline_current_a": round(baseline_current_a, 3),
        "average_current_a": round(avg_current, 3),
        "usable_energy_wh": round(energy_wh, 3),
        "average_power_w": round(avg_power_w, 3),
        "estimated_runtime_min": round(runtime_min, 2),
        "target_runtime_min": round(target_runtime_min, 2),
        "runtime_margin": round(margin, 3) if margin else 0.0,
        "peak_current_margin": power_budget.get("peak_current_margin", 0.0),
    }


def _drive_kinematics(
    body: Dict[str, Any],
    project: Dict[str, Any],
    platform: Dict[str, Any],
    mechanism: Dict[str, Any],
    actuators: List[Dict[str, Any]],
    constraints: Dict[str, Any],
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    del body
    drive_motors = [row for row in actuators if _is_drive_motor(row)]
    domains = set(_string_list(platform.get("domains")))
    robot_class = str(project.get("robot_class") or platform.get("type") or "").lower()
    mobility = _first_dict(platform.get("mobility"), project.get("mobility"))
    locomotion = bool(drive_motors or "locomotion" in domains or any(word in robot_class for word in ["rover", "wheeled", "mobile"]))
    if not locomotion:
        return {"available": False, "status": "not_applicable", "reason": "No locomotion domain detected."}

    target_speed = _float(constraints.get("max_speed_mps") or constraints.get("target_speed_mps"), 0.0)
    wheel_d_mm = _wheel_diameter_mm(mechanism, mobility, drive_motors)
    wheel_radius_m = wheel_d_mm / 2000.0 if wheel_d_mm > 0 else 0.0
    required_wheel_rpm = (target_speed / (math.pi * wheel_d_mm / 1000.0) * 60.0) if target_speed > 0 and wheel_d_mm > 0 else 0.0
    available_rpms = [_available_output_rpm(row) for row in drive_motors]
    available_rpms = [rpm for rpm in available_rpms if rpm > 0]
    available_rpm = min(available_rpms) if available_rpms else 0.0
    speed_margin = _ratio(available_rpm, required_wheel_rpm)

    mass_kg = _mass_kg(project, constraints)
    acceleration = _float(constraints.get("acceleration_mps2"), 0.5 if target_speed > 0 else 0.0)
    rolling_coeff = _float(constraints.get("rolling_resistance_coefficient"), 0.03)
    required_force_n = mass_kg * acceleration + mass_kg * 9.81 * rolling_coeff if mass_kg > 0 else 0.0
    available_force_n = _available_tractive_force_n(drive_motors, wheel_radius_m)
    force_margin = _ratio(available_force_n, required_force_n)

    status = "pass"
    if not drive_motors:
        status = "block"
        _finding(findings, "drive_kinematics", "block", "Locomotion domain has no drive motor models.")
    if target_speed > 0 and wheel_d_mm <= 0:
        status = "block"
        _finding(findings, "drive_kinematics", "block", "Locomotion target speed needs wheel_d_mm or equivalent track geometry.")
    if target_speed > 0 and available_rpm <= 0:
        status = "block"
        _finding(findings, "drive_kinematics", "block", "Drive motors need free_speed_rpm or output_free_speed_rpm for speed simulation.")
    if required_wheel_rpm > 0 and available_rpm > 0:
        if available_rpm < required_wheel_rpm:
            status = "block"
            _finding(
                findings,
                "drive_kinematics",
                "block",
                f"Available wheel speed {available_rpm:.1f} rpm cannot reach required {required_wheel_rpm:.1f} rpm.",
                {"available_wheel_rpm": round(available_rpm, 2), "required_wheel_rpm": round(required_wheel_rpm, 2)},
            )
        elif speed_margin < 1.25:
            status = "warning" if status == "pass" else status
            _finding(
                findings,
                "drive_kinematics",
                "warn",
                f"Wheel speed margin is only {speed_margin:.2f}x.",
                {"speed_margin": round(speed_margin, 3)},
            )
    if required_force_n > 0 and available_force_n <= 0:
        status = "warning" if status == "pass" else status
        _finding(findings, "drive_kinematics", "warn", "Drive motors do not declare torque, so traction margin cannot be estimated.")
    elif required_force_n > 0 and available_force_n < required_force_n:
        status = "block"
        _finding(
            findings,
            "drive_kinematics",
            "block",
            f"Available tractive force {available_force_n:.2f} N is below required {required_force_n:.2f} N.",
            {"available_force_n": round(available_force_n, 3), "required_force_n": round(required_force_n, 3)},
        )
    elif required_force_n > 0 and force_margin < 1.5:
        status = "warning" if status == "pass" else status
        _finding(
            findings,
            "drive_kinematics",
            "warn",
            f"Traction/acceleration margin is only {force_margin:.2f}x.",
            {"force_margin": round(force_margin, 3)},
        )

    return {
        "available": True,
        "status": status,
        "mobility": mobility,
        "drive_motor_ids": [str(row.get("id") or row.get("name") or "drive_motor") for row in drive_motors],
        "target_speed_mps": round(target_speed, 3),
        "wheel_d_mm": round(wheel_d_mm, 3),
        "required_wheel_rpm": round(required_wheel_rpm, 2),
        "available_wheel_rpm": round(available_rpm, 2),
        "speed_margin": round(speed_margin, 3) if speed_margin else 0.0,
        "mass_kg": round(mass_kg, 3),
        "acceleration_mps2": round(acceleration, 3),
        "required_force_n": round(required_force_n, 3),
        "available_force_n": round(available_force_n, 3),
        "force_margin": round(force_margin, 3) if force_margin else 0.0,
    }


def _servo_load_margins(mechanism: Dict[str, Any], actuators: List[Dict[str, Any]], findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    pan_tilt = _dict(mechanism.get("pan_tilt"))
    servo_rows = [row for row in actuators if str(row.get("type") or "").lower() in {"servo", "rc_servo"}]
    if not pan_tilt and not servo_rows:
        return {"available": False, "status": "not_applicable", "axes": []}

    payload_n = _float(pan_tilt.get("max_payload_n") or pan_tilt.get("payload_n"), 0.0)
    offset_mm = _float(pan_tilt.get("payload_offset_mm"), 0.0)
    required_torque = payload_n * offset_mm / 1000.0 if payload_n > 0 and offset_mm > 0 else 0.0
    axes = []
    status = "pass"
    for row in servo_rows:
        torque = _float(row.get("stall_torque_nm") or row.get("torque_nm"), 0.0)
        margin = _ratio(torque, required_torque)
        axis_status = "pass"
        if required_torque <= 0:
            axis_status = "warning"
        elif torque <= 0:
            axis_status = "warning"
            _finding(findings, "servo_load", "warn", f"Servo {row.get('id') or 'servo'} lacks torque data for load simulation.")
        elif torque < required_torque:
            axis_status = "block"
            status = "block"
            _finding(
                findings,
                "servo_load",
                "block",
                f"Servo {row.get('id') or 'servo'} torque {torque:.3f} Nm is below payload torque {required_torque:.3f} Nm.",
                {"servo_id": row.get("id"), "available_torque_nm": round(torque, 4), "required_torque_nm": round(required_torque, 4)},
            )
        elif margin < 1.5:
            axis_status = "warning"
            status = "warning" if status == "pass" else status
            _finding(
                findings,
                "servo_load",
                "warn",
                f"Servo {row.get('id') or 'servo'} load margin is only {margin:.2f}x.",
                {"servo_id": row.get("id"), "torque_margin": round(margin, 3)},
            )
        axes.append(
            {
                "servo_id": str(row.get("id") or row.get("name") or "servo"),
                "role": str(row.get("role") or ""),
                "available_torque_nm": round(torque, 4),
                "required_payload_torque_nm": round(required_torque, 4),
                "torque_margin": round(margin, 3) if margin else 0.0,
                "status": axis_status,
            }
        )

    if servo_rows and required_torque <= 0:
        status = "warning" if status == "pass" else status
        _finding(findings, "servo_load", "warn", "Servo payload force/offset is missing, so payload torque margin is partial.")

    return {
        "available": bool(servo_rows),
        "status": status,
        "payload_n": round(payload_n, 3),
        "payload_offset_mm": round(offset_mm, 3),
        "required_payload_torque_nm": round(required_torque, 4),
        "axes": axes,
    }


def _safety_envelope(
    body: Dict[str, Any],
    project: Dict[str, Any],
    platform: Dict[str, Any],
    drive_requirements: Dict[str, Any],
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    control = _first_dict(body.get("control_stack"), project.get("control_stack"), _dict(body.get("robotics_actuation")).get("control_stack"))
    safety = _first_dict(body.get("safety_case"), project.get("safety_case"))
    failsafes = set(_string_list(control.get("failsafes")) + _string_list(safety.get("failsafes")))
    mitigations = set(_string_list(safety.get("mitigations")) + _string_list(safety.get("protections")) + _string_list(safety.get("safety_features")))
    protections = set(_string_list(drive_requirements.get("required_protections")))
    domains = set(_string_list(platform.get("domains")))
    robot_class = str(project.get("robot_class") or platform.get("type") or "").lower()
    locomotion = "locomotion" in domains or any(word in robot_class for word in ["rover", "mobile", "wheeled", "tracked"])
    constraints = _dict(project.get("constraints"))
    max_speed = _float(constraints.get("max_speed_mps"), 0.0)

    blockers = []
    if locomotion and "e_stop" not in failsafes:
        blockers.append("Mobile robot safety envelope needs e_stop.")
    if locomotion and "signal_loss_stop" not in failsafes:
        blockers.append("Mobile robot safety envelope needs signal_loss_stop.")
    if protections and "current_limit" not in failsafes:
        blockers.append("Motion safety envelope needs current_limit failsafe.")
    missing_protections = sorted(item for item in protections if item not in failsafes and item not in mitigations)
    if missing_protections:
        blockers.append("Safety envelope is missing drive protections: " + ", ".join(missing_protections) + ".")
    if max_speed > 1.0 and not (({"guarded_wheels", "physical_boundary", "speed_limit"} & failsafes) or ({"guarded_wheels", "physical_boundary", "speed_limit"} & mitigations)):
        blockers.append("Higher-speed mobile operation needs explicit physical boundary, speed limit, or wheel guarding.")

    for blocker in blockers:
        _finding(findings, "safety_envelope", "block", blocker)

    return {
        "available": bool(control or safety),
        "status": "pass" if not blockers else "block",
        "locomotion": locomotion,
        "max_speed_mps": round(max_speed, 3),
        "failsafes": sorted(failsafes),
        "mitigations": sorted(mitigations),
        "required_protections": sorted(protections),
        "blockers": _dedupe_strings(blockers),
    }


def _integration_status(mechatronics: Dict[str, Any], findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    trace = _dict(mechatronics.get("integration_trace"))
    gaps = _string_list(trace.get("open_gaps"))
    technical_gaps = [gap for gap in gaps if not _authority_only_integration_gap(gap)]
    for gap in technical_gaps:
        _finding(findings, "integration_trace", "block", f"Simulation cannot clear release while integration gap is open: {gap}")
    return {
        "available": bool(trace),
        "trace_quality_band": trace.get("quality_band"),
        "trace_quality_score": trace.get("quality_score"),
        "open_gap_count": len(gaps),
        "open_gaps": gaps,
        "technical_gap_count": len(technical_gaps),
        "authority_gap_count": len(gaps) - len(technical_gaps),
    }


def _authority_only_integration_gap(gap: str) -> bool:
    lowered = str(gap).lower()
    authority_markers = (
        "integrated_bench",
        "field_validation",
        "release_review",
        "robotics_release",
        "mechatronics_release",
        "production_mechanical",
        "mechanical_release_ready",
    )
    return any(marker in lowered for marker in authority_markers)


def _explicit_current_budget_a(body: Dict[str, Any], actuation: Dict[str, Any]) -> float:
    machine = _dict(body.get("machine"))
    total = 0.0
    for board in _list_dicts(machine.get("boards")):
        caps = _dict(board.get("capabilities"))
        total += max(_float(caps.get("actuation_current_budget_a"), 0.0), 0.0)
        power = _dict(_dict(board.get("requirements")).get("power"))
        for rail in _list_dicts(power.get("rails")):
            name = str(rail.get("name") or rail.get("rail") or "").lower()
            if any(token in name for token in ["act", "motor", "servo", "drive"]):
                total = max(total, _float(rail.get("max_current_a"), total))
        for source in _list_dicts(power.get("sources")):
            name = str(source.get("name") or source.get("rail") or "").lower()
            if any(token in name for token in ["act", "motor", "servo", "drive"]):
                total = max(total, _float(source.get("max_current_a"), total))
    for source, current in _dict(_dict(actuation.get("power_evidence")).get("source_currents_a")).items():
        name = str(source).lower()
        if any(token in name for token in ["act", "motor", "servo", "drive"]):
            total = max(total, _float(current, 0.0))
    return total


def _battery(body: Dict[str, Any], project: Dict[str, Any]) -> Dict[str, Any]:
    candidates = [
        _dict(_dict(project.get("power")).get("battery")),
        _dict(project.get("battery")),
        _dict(_dict(body.get("robotics_actuation")).get("battery")),
        _dict(_dict(body.get("robotics_simulation")).get("battery")),
        _dict(_dict(body.get("machine")).get("battery")),
        _dict(_dict(_dict(body.get("machine")).get("power")).get("battery")),
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    return {}


def _battery_capacity_ah(battery: Dict[str, Any]) -> float:
    if _float(battery.get("capacity_ah"), 0.0) > 0:
        return _float(battery.get("capacity_ah"), 0.0)
    return _float(battery.get("capacity_mah"), 0.0) / 1000.0


def _battery_energy_wh(battery: Dict[str, Any], voltage: float, capacity_ah: float, usable_fraction: float) -> float:
    explicit = _float(battery.get("energy_wh"), 0.0)
    if explicit > 0:
        return explicit * (usable_fraction if usable_fraction > 0 else 1.0)
    if voltage > 0 and capacity_ah > 0:
        return voltage * capacity_ah * usable_fraction
    return 0.0


def _wheel_diameter_mm(mechanism: Dict[str, Any], mobility: Dict[str, Any], drive_motors: List[Dict[str, Any]]) -> float:
    drive_base = _dict(mechanism.get("drive_base"))
    for value in [
        drive_base.get("wheel_d_mm"),
        drive_base.get("wheel_diameter_mm"),
        mobility.get("wheel_d_mm"),
        mobility.get("wheel_diameter_mm"),
    ]:
        number = _float(value, 0.0)
        if number > 0:
            return number
    for motor in drive_motors:
        number = _float(motor.get("wheel_d_mm") or motor.get("wheel_diameter_mm"), 0.0)
        if number > 0:
            return number
    return 0.0


def _available_output_rpm(actuator: Dict[str, Any]) -> float:
    output = _float(actuator.get("output_free_speed_rpm"), 0.0)
    if output > 0:
        return output
    free = _float(actuator.get("free_speed_rpm"), 0.0)
    if free <= 0:
        return 0.0
    gear_ratio = _float(actuator.get("gear_ratio"), 1.0)
    if gear_ratio > 1.0:
        return free / gear_ratio
    return free


def _available_tractive_force_n(drive_motors: List[Dict[str, Any]], wheel_radius_m: float) -> float:
    if wheel_radius_m <= 0:
        return 0.0
    total_torque = 0.0
    for motor in drive_motors:
        torque = _float(
            motor.get("continuous_torque_nm")
            or motor.get("output_continuous_torque_nm")
            or motor.get("wheel_torque_nm"),
            0.0,
        )
        if torque <= 0:
            stall = _float(motor.get("stall_torque_nm") or motor.get("output_stall_torque_nm"), 0.0)
            torque = stall * _float(motor.get("continuous_torque_fraction"), 0.35)
        total_torque += max(torque, 0.0)
    return total_torque / wheel_radius_m


def _mass_kg(project: Dict[str, Any], constraints: Dict[str, Any]) -> float:
    for key in ["mass_kg", "robot_mass_kg", "estimated_mass_kg"]:
        value = _float(constraints.get(key) or project.get(key), 0.0)
        if value > 0:
            return value
    payload = _float(constraints.get("payload_kg") or project.get("payload_kg"), 0.0)
    return payload + 1.0 if payload > 0 else 0.0


def _simulation_domains(*packets: Dict[str, Any]) -> List[str]:
    domains = []
    names = ["power_budget", "runtime_estimate", "drive_kinematics", "servo_load_margins", "safety_envelope"]
    for name, packet in zip(names, packets):
        if packet.get("available") or packet.get("status") in {"pass", "warning", "block"}:
            domains.append(name)
    return domains


def _missing_inputs(power: Dict[str, Any], runtime: Dict[str, Any], drive: Dict[str, Any], servo: Dict[str, Any]) -> List[str]:
    missing = []
    if power.get("available") and _float(power.get("explicit_current_budget_a"), 0.0) <= 0:
        missing.append("explicit actuator current budget")
    if runtime.get("status") == "warning" and not runtime.get("available"):
        missing.append("battery voltage/capacity")
    if drive.get("available"):
        if _float(drive.get("wheel_d_mm"), 0.0) <= 0:
            missing.append("wheel diameter")
        if _float(drive.get("available_wheel_rpm"), 0.0) <= 0:
            missing.append("drive motor free speed")
        if _float(drive.get("available_force_n"), 0.0) <= 0:
            missing.append("drive motor torque")
    if servo.get("available") and _float(servo.get("required_payload_torque_nm"), 0.0) <= 0:
        missing.append("servo payload force and offset")
    return _dedupe_strings(missing)


def _claim_boundary(ready: bool, domains: List[str]) -> str:
    if ready:
        return "Deterministic robotics simulation has no blocking findings within the declared scope: " + ", ".join(domains) + "."
    return "Simulation found blockers; do not claim scoped robotics release until these are resolved and re-run."


def _project(body: Dict[str, Any]) -> Dict[str, Any]:
    return _first_dict(body.get("robotics_project"), body.get("mechatronics_project"), body.get("mission"))


def _platform(body: Dict[str, Any], project: Dict[str, Any]) -> Dict[str, Any]:
    return _first_dict(body.get("robotics_platform"), project.get("platform"))


def _is_drive_motor(actuator: Dict[str, Any]) -> bool:
    text = " ".join(str(actuator.get(key) or "") for key in ["id", "name", "role", "type", "drive"]).lower()
    return str(actuator.get("type") or "").lower() in {"dc_motor", "brushed_motor", "stepper"} and any(
        word in text for word in ["drive", "wheel", "track", "left", "right", "locomotion"]
    )


def _finding(findings: List[Dict[str, Any]], domain: str, severity: str, message: str, evidence: Dict[str, Any] | None = None) -> None:
    row = {"domain": domain, "severity": severity, "message": message}
    if evidence:
        row["evidence"] = evidence
    findings.append(row)


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _bounded(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _dedupe_strings(rows: Iterable[str]) -> List[str]:
    out = []
    seen = set()
    for row in rows:
        text = str(row).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _to_dict(value: Mapping[str, Any] | Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "to_dict"):
        try:
            return _dict(value.to_dict())
        except Exception:
            return {}
    return _dict(value)


def _dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, Mapping) and value:
            return dict(value)
    return {}


def _list_dicts(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, Mapping):
        return [str(item).strip() for item in value.values() if str(item).strip()]
    if isinstance(value, Iterable):
        return [str(item).strip() for item in value if str(item).strip()]
    return []
