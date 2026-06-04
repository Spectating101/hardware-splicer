from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping


SCHEMA_VERSION = "hardware_splicer.robotics_actuation.v1"

LEVELS = [
    "actuation_candidate",
    "actuator_model",
    "electrical_drive_matched",
    "mechanical_load_verified",
    "controlled_motion_verified",
    "production_robotics_release",
]

LEVEL_SCORES = {
    "actuation_candidate": 0.18,
    "actuator_model": 0.36,
    "electrical_drive_matched": 0.58,
    "mechanical_load_verified": 0.76,
    "controlled_motion_verified": 0.91,
    "production_robotics_release": 1.00,
}

PASS_STATUSES = {"pass", "passed", "ok", "verified", "accepted", "closed", "true"}
FAIL_STATUSES = {"fail", "failed", "block", "blocked", "error", "critical", "unsafe", "rejected"}


def build_robotics_actuation_packet(payload: Mapping[str, Any] | Any, *, engineering: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """Build a robotics/motion authority packet from mechanism, electronics, and bench evidence."""

    body = _to_dict(payload)
    engineering_body = _to_dict(engineering or {})
    mechanism = _dict(body.get("mechanism"))
    robotics = _first_dict(body.get("robotics_actuation"), mechanism.get("robotics_actuation"))
    analysis = _dict(engineering_body.get("analysis"))
    control = _dict(analysis.get("control_coupling"))
    power = _merge_power_evidence(_dict(analysis.get("power")), _declared_power(body))
    mechanism_analysis = _dict(analysis.get("mechanism"))

    actuators = _actuator_inventory(mechanism, robotics)
    springs = _spring_inventory(robotics)
    sensors = _sensor_inventory(robotics, mechanism)
    requirements = _drive_requirements(actuators, springs)
    coupling = _electrical_coupling(requirements, control, power, robotics)
    load = _mechanical_load_status(body, mechanism_analysis)
    bench = _motion_bench_status(body, robotics)
    release = _release_status(body, robotics)

    stages = _stages(
        actuators=actuators,
        springs=springs,
        requirements=requirements,
        coupling=coupling,
        load=load,
        bench=bench,
        release=release,
    )
    current_level = _current_level(stages)
    score = LEVEL_SCORES.get(current_level, 0.0) if current_level else 0.0
    production_authorized = current_level == "production_robotics_release"

    return {
        "schema_version": SCHEMA_VERSION,
        "current_authority_level": current_level or "no_robotics_actuation_authority",
        "authority_score": round(score, 2),
        "production_authorized": production_authorized,
        "release_decision": "authorized_scoped_robotics_release" if production_authorized else "evidence_required_before_robotics_release",
        "next_action_id": _next_action_id(stages),
        "stages": stages,
        "can": _capabilities(stages),
        "actuation_profile": {
            "actuator_count": len(actuators),
            "spring_count": len(springs),
            "sensor_count": len(sensors),
            "actuators": actuators,
            "springs": springs,
            "sensors": sensors,
        },
        "drive_requirements": requirements,
        "electrical_coupling": coupling,
        "power_evidence": power,
        "mechanical_load_status": load,
        "motion_bench_status": bench,
        "release_status": release,
        "claim_boundary": _claim_boundary(current_level),
        "scope_limits": _scope_limits(actuators, springs, release),
        "next_engineering_actions": _next_engineering_actions(stages, coupling, load, bench),
    }


def _actuator_inventory(mechanism: Dict[str, Any], robotics: Dict[str, Any]) -> List[Dict[str, Any]]:
    actuators: List[Dict[str, Any]] = []
    for row in _list_dicts(robotics.get("actuators")):
        actuator = _normalize_explicit_actuator(row)
        if actuator:
            actuators.append(actuator)

    pan_tilt = _dict(mechanism.get("pan_tilt"))
    if pan_tilt:
        actuators.append(_servo(f"{pan_tilt.get('name') or 'pan_tilt'}_pan", str(pan_tilt.get("pan_servo") or "sg90"), "pan axis"))
        actuators.append(_servo(f"{pan_tilt.get('name') or 'pan_tilt'}_tilt", str(pan_tilt.get("tilt_servo") or "sg90"), "tilt axis"))

    gripper = _dict(mechanism.get("gripper"))
    if gripper:
        actuators.append(_servo(f"{gripper.get('name') or 'gripper'}_servo", str(gripper.get("servo_type") or "sg90"), "gripper jaw"))

    if _dict(mechanism.get("linear_axis")):
        actuators.append(_stepper("linear_axis_stepper", "linear axis belt drive"))
    if _dict(mechanism.get("leadscrew_axis")):
        actuators.append(_stepper("leadscrew_axis_stepper", "lead screw axis"))
    if _dict(mechanism.get("belt_reduction")):
        actuators.append(_stepper("belt_reduction_motor", "belt reduction input"))

    return _dedupe_by_id(actuators)


def _normalize_explicit_actuator(row: Dict[str, Any]) -> Dict[str, Any]:
    kind = str(row.get("type") or row.get("kind") or "").strip().lower()
    if not kind:
        return {}
    if kind in {"servo", "rc_servo"}:
        return _with_numeric_fields(
            _servo(
                str(row.get("id") or row.get("name") or "servo"),
                str(row.get("model") or row.get("servo_type") or "sg90"),
                str(row.get("role") or "servo"),
            ),
            row,
        )
    if kind in {"stepper", "stepper_motor"}:
        return _with_numeric_fields(
            _stepper(
                str(row.get("id") or row.get("name") or "stepper"),
                str(row.get("role") or "stepper axis"),
                current_a=_float(row.get("current_a"), 1.2),
            ),
            row,
        )
    if kind in {"dc_motor", "brushed_motor"}:
        return _with_numeric_fields({
            "id": str(row.get("id") or row.get("name") or "dc_motor"),
            "type": "dc_motor",
            "role": str(row.get("role") or "drive motor"),
            "drive": str(row.get("drive") or "h_bridge"),
            "channels": {"dc_motor": 1},
            "voltage_v": _float(row.get("voltage_v"), 6.0),
            "run_current_a": _float(row.get("current_a") or row.get("run_current_a"), 0.5),
            "stall_current_a": _float(row.get("stall_current_a"), max(_float(row.get("current_a"), 0.5) * 3.0, 1.0)),
            "model_source": "explicit",
        }, row)
    if kind in {"fan", "blower", "impeller"}:
        return {
            "id": str(row.get("id") or row.get("name") or "fan"),
            "type": "fan",
            "role": str(row.get("role") or "air mover"),
            "drive": str(row.get("drive") or "mosfet_pwm"),
            "channels": {"fan": 1},
            "voltage_v": _float(row.get("voltage_v"), 5.0),
            "run_current_a": _float(row.get("current_a") or row.get("run_current_a"), 0.25),
            "stall_current_a": _float(row.get("stall_current_a") or row.get("startup_current_a"), max(_float(row.get("current_a"), 0.25) * 2.0, 0.5)),
            "model_source": "explicit",
        }
    if kind in {"pump", "solenoid"}:
        current = _float(row.get("current_a") or row.get("run_current_a"), 0.8)
        return {
            "id": str(row.get("id") or row.get("name") or kind),
            "type": kind,
            "role": str(row.get("role") or kind),
            "drive": str(row.get("drive") or "low_side_mosfet"),
            "channels": {kind: 1},
            "voltage_v": _float(row.get("voltage_v"), 12.0),
            "run_current_a": current,
            "stall_current_a": _float(row.get("stall_current_a") or row.get("pull_in_current_a"), current),
            "model_source": "explicit",
        }
    return {
        "id": str(row.get("id") or row.get("name") or kind),
        "type": kind,
        "role": str(row.get("role") or kind),
        "drive": str(row.get("drive") or "unknown"),
        "channels": {kind: 1},
        "voltage_v": _float(row.get("voltage_v"), 0.0),
        "run_current_a": _float(row.get("current_a") or row.get("run_current_a"), 0.0),
        "stall_current_a": _float(row.get("stall_current_a"), 0.0),
        "model_source": "explicit",
    }


def _with_numeric_fields(actuator: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    for key in [
        "free_speed_rpm",
        "output_free_speed_rpm",
        "gear_ratio",
        "stall_torque_nm",
        "output_stall_torque_nm",
        "continuous_torque_nm",
        "output_continuous_torque_nm",
        "wheel_torque_nm",
        "continuous_torque_fraction",
        "wheel_d_mm",
        "wheel_diameter_mm",
        "startup_current_a",
        "no_load_current_a",
    ]:
        if source.get(key) is not None:
            actuator[key] = _float(source.get(key), 0.0)
    return actuator


def _servo(actuator_id: str, model: str, role: str) -> Dict[str, Any]:
    model_l = model.strip().lower()
    if model_l == "mg996r":
        return {
            "id": actuator_id,
            "type": "servo",
            "model": "mg996r",
            "role": role,
            "drive": "servo_pwm",
            "channels": {"servo_pwm": 1},
            "voltage_v": 6.0,
            "run_current_a": 0.8,
            "stall_current_a": 1.8,
            "stall_torque_nm": 0.98,
            "model_source": "inferred_mechanism",
        }
    return {
        "id": actuator_id,
        "type": "servo",
        "model": "sg90",
        "role": role,
        "drive": "servo_pwm",
        "channels": {"servo_pwm": 1},
        "voltage_v": 5.0,
        "run_current_a": 0.25,
        "stall_current_a": 0.65,
        "stall_torque_nm": 0.18,
        "model_source": "inferred_mechanism",
    }


def _stepper(actuator_id: str, role: str, *, current_a: float = 1.2) -> Dict[str, Any]:
    return {
        "id": actuator_id,
        "type": "stepper",
        "model": "nema17_reference",
        "role": role,
        "drive": "step_dir_driver",
        "channels": {"stepper": 1},
        "voltage_v": 12.0,
        "run_current_a": current_a,
        "stall_current_a": current_a,
        "model_source": "inferred_mechanism",
    }


def _spring_inventory(robotics: Dict[str, Any]) -> List[Dict[str, Any]]:
    springs: List[Dict[str, Any]] = []
    for row in _list_dicts(robotics.get("springs")):
        spring = {
            "id": str(row.get("id") or row.get("name") or "spring"),
            "type": str(row.get("type") or "spring"),
            "role": str(row.get("role") or "stored energy"),
            "k_n_per_mm": _float(row.get("k_n_per_mm") or row.get("spring_rate_n_per_mm"), 0.0),
            "preload_mm": _float(row.get("preload_mm"), 0.0),
            "travel_mm": _float(row.get("travel_mm"), 0.0),
            "energy_j": 0.0,
        }
        spring["energy_j"] = round(0.5 * spring["k_n_per_mm"] * 1000.0 * ((spring["travel_mm"] / 1000.0) ** 2), 4)
        springs.append(spring)
    return springs


def _sensor_inventory(robotics: Dict[str, Any], mechanism: Dict[str, Any]) -> List[Dict[str, Any]]:
    sensors = [
        {
            "id": str(row.get("id") or row.get("name") or "sensor"),
            "type": str(row.get("type") or row.get("kind") or "sensor"),
            "role": str(row.get("role") or "feedback"),
        }
        for row in _list_dicts(robotics.get("sensors"))
    ]
    if _dict(mechanism.get("linear_axis")).get("include_endstops") is True:
        sensors.append({"id": "linear_axis_endstop", "type": "endstop", "role": "axis limit"})
    if _dict(mechanism.get("leadscrew_axis")).get("include_endstops") is True:
        sensors.append({"id": "leadscrew_axis_endstop", "type": "endstop", "role": "axis limit"})
    return _dedupe_by_id(sensors)


def _drive_requirements(actuators: List[Dict[str, Any]], springs: List[Dict[str, Any]]) -> Dict[str, Any]:
    channels: Dict[str, int] = {}
    peak_current_a = 0.0
    run_current_a = 0.0
    rails: Dict[str, float] = {}
    drive_types = set()
    for actuator in actuators:
        drive_types.add(str(actuator.get("drive") or "unknown"))
        for key, value in _dict(actuator.get("channels")).items():
            channels[key] = channels.get(key, 0) + int(_float(value, 0))
        run_current_a += max(_float(actuator.get("run_current_a"), 0.0), 0.0)
        peak_current_a += max(_float(actuator.get("stall_current_a"), _float(actuator.get("run_current_a"), 0.0)), 0.0)
        voltage = _float(actuator.get("voltage_v"), 0.0)
        if voltage > 0:
            rails[f"{voltage:g}V"] = rails.get(f"{voltage:g}V", 0.0) + max(_float(actuator.get("stall_current_a"), 0.0), 0.0)

    spring_energy_j = sum(max(_float(row.get("energy_j"), 0.0), 0.0) for row in springs)
    protections = []
    if any(str(a.get("type")) in {"dc_motor", "fan", "pump", "solenoid"} for a in actuators):
        protections.extend(["flyback_or_tvs", "current_limit", "separate_actuator_supply"])
    if any(str(a.get("type")) == "stepper" for a in actuators):
        protections.extend(["stepper_current_limit", "thermal_check", "endstop_or_homing_plan"])
    if any(str(a.get("type")) == "servo" for a in actuators):
        protections.extend(["servo_bulk_capacitance", "logic_power_isolation"])
    if spring_energy_j > 0:
        protections.extend(["spring_preload_guard", "stored_energy_release_plan"])

    return {
        "channels": channels,
        "drive_types": sorted(drive_types),
        "estimated_run_current_a": round(run_current_a, 3),
        "estimated_peak_current_a": round(peak_current_a, 3),
        "rail_peak_currents_a": {key: round(value, 3) for key, value in sorted(rails.items())},
        "spring_stored_energy_j": round(spring_energy_j, 4),
        "required_protections": sorted(set(protections)),
    }


def _electrical_coupling(requirements: Dict[str, Any], control: Dict[str, Any], power: Dict[str, Any], robotics: Dict[str, Any]) -> Dict[str, Any]:
    blockers: List[str] = []
    warnings: List[str] = []

    for issue in _list_dicts(control.get("issues")) + _list_dicts(power.get("issues")):
        severity = str(issue.get("severity") or "").lower()
        message = str(issue.get("message") or issue.get("topic") or "electrical coupling issue")
        if severity in {"error", "block", "critical"}:
            blockers.append(message)
        elif severity in {"warning", "warn"}:
            warnings.append(message)

    control_requirements = _dict(control.get("requirements"))
    if control_requirements:
        if int(_float(control_requirements.get("servo_channels"), 0)) < int(_float(_dict(requirements.get("channels")).get("servo_pwm"), 0)):
            blockers.append("Controller coupling did not account for all servo PWM channels.")
        if int(_float(control_requirements.get("stepper_channels"), 0)) < int(_float(_dict(requirements.get("channels")).get("stepper"), 0)):
            blockers.append("Controller coupling did not account for all stepper channels.")

    protections = set(_string_list(robotics.get("protections")) + _string_list(robotics.get("safety_features")))
    missing_protections = [
        item
        for item in _string_list(requirements.get("required_protections"))
        if item not in protections
    ]
    if missing_protections:
        warnings.append(f"Protection plan is not explicit for: {', '.join(missing_protections)}.")

    if _float(requirements.get("estimated_peak_current_a"), 0.0) > 0 and not (power.get("rails") or power.get("source_currents_a")):
        warnings.append("No simulated actuator power rails were found; verify supply, wiring, and current limit before motion.")

    return {
        "matched": not blockers,
        "blockers": _dedupe_strings(blockers),
        "warnings": _dedupe_strings(warnings),
        "control_requirements_seen": bool(control_requirements),
        "power_paths_seen": bool(power.get("rails") or power.get("source_currents_a")),
        "power_evidence_source": power.get("evidence_source") or "analysis",
    }


def _declared_power(body: Dict[str, Any]) -> Dict[str, Any]:
    machine = _dict(body.get("machine"))
    sources: List[Dict[str, Any]] = []
    rails: List[Dict[str, Any]] = []
    loads: List[Dict[str, Any]] = []
    for board in _list_dicts(machine.get("boards")):
        requirements = _dict(board.get("requirements"))
        power = _dict(requirements.get("power"))
        sources.extend(_list_dicts(power.get("sources")))
        rails.extend(_list_dicts(power.get("rails")))
        loads.extend(_list_dicts(power.get("loads")))
    for row in _list_dicts(machine.get("power_tree")):
        if row.get("source"):
            sources.append({"name": row.get("source"), "voltage_v": row.get("voltage_v"), "max_current_a": row.get("max_current_a")})
        if row.get("rail"):
            rails.append({"name": row.get("rail"), "voltage_v": row.get("voltage_v"), "max_current_a": row.get("max_current_a")})
        if row.get("load_current_a"):
            loads.append({"name": row.get("rail") or row.get("source"), "rail": row.get("rail"), "current_a": row.get("load_current_a")})
    return {
        "sources": sources,
        "rails": rails,
        "loads": loads,
        "source_currents_a": _source_currents(sources),
        "evidence_source": "declared_requirements",
    } if sources or rails or loads else {}


def _merge_power_evidence(analysis_power: Dict[str, Any], declared_power: Dict[str, Any]) -> Dict[str, Any]:
    if analysis_power.get("rails") or analysis_power.get("source_currents_a"):
        merged = dict(analysis_power)
        merged["evidence_source"] = "analysis"
        return merged
    if not declared_power:
        return analysis_power
    merged = dict(analysis_power)
    for key in ["sources", "rails", "loads", "source_currents_a"]:
        if declared_power.get(key):
            merged[key] = declared_power[key]
    merged["evidence_source"] = "declared_requirements"
    return merged


def _source_currents(sources: List[Dict[str, Any]]) -> Dict[str, float]:
    currents: Dict[str, float] = {}
    for source in sources:
        name = str(source.get("name") or source.get("rail") or "source").strip()
        current = _float(source.get("max_current_a"), 0.0)
        if name and current > 0:
            currents[name] = round(max(currents.get(name, 0.0), current), 3)
    return currents


def _mechanical_load_status(body: Dict[str, Any], mechanism_analysis: Dict[str, Any]) -> Dict[str, Any]:
    simulation = _list_dicts(mechanism_analysis.get("simulation"))
    blockers = [
        str(row.get("message") or row.get("domain") or "mechanical load simulation blocker")
        for row in simulation
        if str(row.get("severity") or "").lower() in {"block", "error", "critical"} or _row_failed(row)
    ]
    measured = _has_measurement_capture(body)
    return {
        "simulation_available": bool(simulation),
        "measured_geometry_available": measured,
        "blockers": _dedupe_strings(blockers),
        "verified": bool(simulation) and measured and not blockers,
    }


def _motion_bench_status(body: Dict[str, Any], robotics: Dict[str, Any]) -> Dict[str, Any]:
    capture = _first_dict(body.get("mechanical_bench_capture"), body.get("robotics_bench_capture"), robotics.get("bench_capture"))
    rows = []
    for key in ["motion_tests", "load_tests", "fit_checks", "cycle_tests", "fan_tests", "spring_tests", "current_tests"]:
        rows.extend(_list_dicts(capture.get(key)))
    passed = [row for row in rows if _row_passed(row)]
    failed = [row for row in rows if _row_failed(row)]
    artifacts = _artifact_count(capture)
    explicit = bool(capture.get("motion_verified") is True or capture.get("bench_verified") is True)

    blockers = []
    if not capture:
        blockers.append("Run controlled robotics bench tests: first motion, load/current, stall/limit, cycle, and thermal observations.")
    if failed:
        blockers.extend(str(row.get("message") or row.get("target") or "bench motion failure") for row in failed)
    if len(passed) < 3 and not explicit:
        blockers.append("Record at least three passing controlled motion/load/current/cycle checks.")
    if artifacts < 1 and not explicit:
        blockers.append("Attach bench artifacts, logs, photos, or videos.")

    return {
        "available": bool(capture),
        "passed_test_count": len(passed),
        "failed_test_count": len(failed),
        "artifact_count": artifacts,
        "motion_verified": bool(explicit or (len(passed) >= 3 and artifacts >= 1 and not failed)),
        "blockers": _dedupe_strings(blockers),
    }


def _release_status(body: Dict[str, Any], robotics: Dict[str, Any]) -> Dict[str, Any]:
    release = _first_dict(body.get("robotics_release"), robotics.get("release"), body.get("mechanical_release"), body.get("production_release"))
    blockers = []
    if not release:
        blockers.append("Attach robotics_release or mechanical_release with reviewed motion scope and artifacts.")
    if release and not str(release.get("scope_statement") or "").strip():
        blockers.append("Release needs a scope_statement for motion/load limits.")
    if release and not bool(release.get("acceptance_reviewed")):
        blockers.append("Release acceptance must be reviewed.")
    if release and _artifact_count(release) < 1:
        blockers.append("Release needs artifact_uris or an equivalent release evidence reference.")
    return {"available": bool(release), "release_ready": bool(release and not blockers), "blockers": blockers, "scope_statement": str(release.get("scope_statement") or "").strip()}


def _stages(
    *,
    actuators: List[Dict[str, Any]],
    springs: List[Dict[str, Any]],
    requirements: Dict[str, Any],
    coupling: Dict[str, Any],
    load: Dict[str, Any],
    bench: Dict[str, Any],
    release: Dict[str, Any],
) -> List[Dict[str, Any]]:
    stages = []
    actuator_count = len(actuators) + len(springs)
    _stage(stages, "actuation_candidate", actuator_count > 0, [] if actuator_count else ["Provide actuator, motor, fan, spring, or mechanism evidence."], "Model actuator load, drive, current, and protection requirements.")

    model_blockers = []
    if actuator_count == 0:
        model_blockers.append("No actuator model available.")
    if any(_float(a.get("run_current_a"), 0.0) <= 0 and str(a.get("type")) not in {"spring"} for a in actuators):
        model_blockers.append("Every powered actuator needs run_current_a or an inferred reference current.")
    if any(str(a.get("drive") or "unknown") == "unknown" for a in actuators):
        model_blockers.append("Every powered actuator needs a drive mode.")
    if any(_float(s.get("k_n_per_mm"), 0.0) <= 0 and _float(s.get("energy_j"), 0.0) <= 0 for s in springs):
        model_blockers.append("Every spring needs spring rate/travel or stored energy evidence.")
    _stage(stages, "actuator_model", _passed(stages, "actuation_candidate") and not model_blockers, model_blockers, "Match actuator requirements to controller channels, drivers, rails, and protections.")

    _stage(stages, "electrical_drive_matched", _passed(stages, "actuator_model") and coupling["matched"], coupling["blockers"], "Verify mechanical loads against measured geometry and simulation.")
    _stage(stages, "mechanical_load_verified", _passed(stages, "electrical_drive_matched") and load["verified"], load["blockers"] or (["Simulation and measured geometry are required."] if not load["verified"] else []), "Run controlled motion/load/current bench tests.")
    _stage(stages, "controlled_motion_verified", _passed(stages, "mechanical_load_verified") and bench["motion_verified"], bench["blockers"], "Close reviewed robotics release scope and artifacts.")
    _stage(stages, "production_robotics_release", _passed(stages, "controlled_motion_verified") and release["release_ready"], release["blockers"], "No remaining action for this scoped robotics release.")
    return stages


def _stage(stages: List[Dict[str, Any]], stage_id: str, passed: bool, blockers: List[str], next_unlock: str) -> None:
    stages.append(
        {
            "stage_id": stage_id,
            "status": "pass" if passed else "open",
            "score_if_current": LEVEL_SCORES[stage_id],
            "blockers": blockers[:12] if not passed else [],
            "next_unlock": next_unlock,
        }
    )


def _capabilities(stages: List[Dict[str, Any]]) -> Dict[str, bool]:
    return {
        "plan_robotic_mechanism": _passed(stages, "actuation_candidate"),
        "size_drivers_and_power": _passed(stages, "actuator_model"),
        "wire_controlled_actuators": _passed(stages, "electrical_drive_matched"),
        "run_motion_bench": _passed(stages, "mechanical_load_verified"),
        "use_scoped_robotic_machine": _passed(stages, "controlled_motion_verified"),
        "claim_production_robotics_release": _passed(stages, "production_robotics_release"),
    }


def _claim_boundary(level: str | None) -> str:
    if level == "production_robotics_release":
        return "Scoped robotic/moving machine release is authorized within the reviewed motion/load envelope."
    if level == "controlled_motion_verified":
        return "Controlled bench motion is verified; release packaging and scope review remain open."
    if level == "mechanical_load_verified":
        return "Mechanical load and drive model are ready for controlled first-motion testing."
    if level == "electrical_drive_matched":
        return "Actuator wiring/drive plan is matched; physical load and motion evidence remain required."
    if level == "actuator_model":
        return "Actuators are modeled, but controller/power/driver coupling is not authoritative yet."
    if level == "actuation_candidate":
        return "Robotic actuation candidate only; loads, drive, and safety remain unproven."
    return "No robotics actuation claim authority is available."


def _scope_limits(actuators: List[Dict[str, Any]], springs: List[Dict[str, Any]], release: Dict[str, Any]) -> List[str]:
    limits = []
    if release.get("scope_statement"):
        limits.append(str(release["scope_statement"]))
    if actuators:
        limits.append("Actuator scope: " + ", ".join(f"{row.get('id')}:{row.get('type')}" for row in actuators))
    if springs:
        limits.append("Stored-energy scope includes spring elements; guarding and release procedures are required.")
    limits.append("No human-carrying, vehicle-road, medical, pressure, or certified safety claim is implied.")
    return limits


def _next_engineering_actions(stages: List[Dict[str, Any]], coupling: Dict[str, Any], load: Dict[str, Any], bench: Dict[str, Any]) -> List[str]:
    actions = []
    for stage in stages:
        if stage.get("status") != "pass":
            actions.extend(str(item) for item in stage.get("blockers") or [])
            break
    actions.extend(coupling.get("warnings") or [])
    if not load.get("measured_geometry_available"):
        actions.append("Capture measured geometry and interface tolerances for moving parts.")
    if not bench.get("available"):
        actions.append("Prepare first-motion bench protocol with current limit and emergency stop.")
    return _dedupe_strings(actions)[:12]


def _current_level(stages: List[Dict[str, Any]]) -> str | None:
    current = None
    for stage in stages:
        if stage.get("status") == "pass":
            current = str(stage.get("stage_id") or "")
        else:
            break
    return current


def _next_action_id(stages: List[Dict[str, Any]]) -> str | None:
    for stage in stages:
        if stage.get("status") != "pass":
            return f"close_{stage.get('stage_id')}"
    return None


def _passed(stages: List[Dict[str, Any]], stage_id: str) -> bool:
    return any(stage.get("stage_id") == stage_id and stage.get("status") == "pass" for stage in stages)


def _has_measurement_capture(body: Dict[str, Any]) -> bool:
    capture = _first_dict(body.get("mechanical_measurement_capture"), body.get("measured_geometry_capture"), body.get("mechanical_measurements"))
    if capture.get("geometry_verified") is True:
        return True
    rows = []
    for key in ["measurements", "dimensions", "clearances", "interfaces", "materials", "tolerances"]:
        rows.extend(_list_dicts(capture.get(key)))
    verified = [row for row in rows if _row_passed(row) or any(row.get(key) not in (None, "") for key in ["value", "value_mm", "clearance_mm", "material"])]
    return len(verified) >= 3 and _artifact_count(capture) >= 1


def _row_passed(row: Dict[str, Any]) -> bool:
    status = str(row.get("status") or row.get("result") or row.get("decision") or "").strip().lower()
    return status in PASS_STATUSES or row.get("pass") is True


def _row_failed(row: Dict[str, Any]) -> bool:
    status = str(row.get("status") or row.get("result") or row.get("decision") or "").strip().lower()
    return status in FAIL_STATUSES or row.get("pass") is False


def _artifact_count(capture: Dict[str, Any]) -> int:
    count = 0
    for key in ["artifact_uris", "artifacts", "evidence_uris", "logs", "photos", "videos"]:
        value = capture.get(key)
        if isinstance(value, list):
            count += len([item for item in value if item])
        elif isinstance(value, str) and value.strip():
            count += 1
    return count


def _dedupe_by_id(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    seen = set()
    for row in rows:
        key = str(row.get("id") or row.get("name") or len(out))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


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
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
