from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

from .mechanical_authority import build_mechanical_authority
from .mechatronics_authority import build_mechatronics_authority
from .robotics_actuation import build_robotics_actuation_packet
from .robotics_simulation import build_robotics_simulation_packet


SCHEMA_VERSION = "hardware_splicer.robotics_platform_authority.v1"

LEVELS = [
    "robotics_project_intake",
    "platform_architecture",
    "power_drive_architecture",
    "control_safety_architecture",
    "simulation_bench_authority",
    "field_validation_authority",
    "production_robotics_project_release",
]

LEVEL_SCORES = {
    "robotics_project_intake": 0.14,
    "platform_architecture": 0.30,
    "power_drive_architecture": 0.48,
    "control_safety_architecture": 0.66,
    "simulation_bench_authority": 0.82,
    "field_validation_authority": 0.93,
    "production_robotics_project_release": 1.00,
}

PASS_STATUSES = {"pass", "passed", "ok", "verified", "accepted", "closed", "true", "mitigated"}
FAIL_STATUSES = {"fail", "failed", "block", "blocked", "error", "critical", "unsafe", "rejected"}


def build_robotics_platform_authority(
    payload: Mapping[str, Any] | Any,
    *,
    engineering: Mapping[str, Any] | None = None,
    mechanical_authority: Mapping[str, Any] | None = None,
    robotics_actuation: Mapping[str, Any] | None = None,
    mechatronics_authority: Mapping[str, Any] | None = None,
    robotics_simulation: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build broad robotics/mechatronics project authority beyond individual actuators."""

    body = _to_dict(payload)
    engineering_body = _to_dict(engineering or {})
    mechanical = _to_dict(mechanical_authority or build_mechanical_authority(body, engineering=engineering_body))
    actuation = _to_dict(robotics_actuation or build_robotics_actuation_packet(body, engineering=engineering_body))
    mechatronics = _to_dict(
        mechatronics_authority
        or build_mechatronics_authority(
            body,
            engineering=engineering_body,
            mechanical_authority=mechanical,
            robotics_actuation=actuation,
        )
    )
    simulation = _to_dict(
        robotics_simulation
        or build_robotics_simulation_packet(
            body,
            engineering=engineering_body,
            robotics_actuation=actuation,
            mechatronics_authority=mechatronics,
        )
    )

    profile = _project_profile(body)
    topology = _platform_topology(body, engineering_body, actuation)
    power_drive = _power_drive_status(body, engineering_body, actuation)
    control_safety = _control_safety_status(body, topology, power_drive)
    validation = _validation_status(body, mechanical, actuation, mechatronics, simulation)
    release = _release_status(body)

    stages = _stages(
        profile=profile,
        topology=topology,
        power_drive=power_drive,
        control_safety=control_safety,
        validation=validation,
        release=release,
    )
    current_level = _current_level(stages)
    score = LEVEL_SCORES.get(current_level, 0.0) if current_level else 0.0
    production_authorized = current_level == "production_robotics_project_release"

    return {
        "schema_version": SCHEMA_VERSION,
        "current_authority_level": current_level or "no_robotics_platform_authority",
        "authority_score": round(score, 2),
        "production_authorized": production_authorized,
        "release_decision": "authorized_scoped_robotics_project_release" if production_authorized else "evidence_required_before_robotics_project_release",
        "next_action_id": _next_action_id(stages),
        "stages": stages,
        "project_profile": profile,
        "platform_topology": topology,
        "power_drive_budget": power_drive,
        "control_safety_architecture": control_safety,
        "simulation_status": simulation,
        "validation_status": validation,
        "release_status": release,
        "subsystem_authority": {
            "mechanical_level": mechanical.get("current_authority_level"),
            "mechanical_authorized": bool(mechanical.get("production_authorized")),
            "actuation_level": actuation.get("current_authority_level"),
            "actuation_authorized": bool(actuation.get("production_authorized")),
            "mechatronics_level": mechatronics.get("current_authority_level"),
            "mechatronics_authorized": bool(mechatronics.get("production_authorized")),
            "simulation_ready": bool(simulation.get("simulation_ready")),
        },
        "can": _capabilities(stages),
        "claim_boundary": _claim_boundary(current_level),
        "scope_limits": _scope_limits(profile, topology, release),
        "next_engineering_actions": _next_engineering_actions(stages, control_safety, validation, release),
    }


def _project_profile(body: Dict[str, Any]) -> Dict[str, Any]:
    project = _first_dict(
        body.get("robotics_project"),
        body.get("mechatronics_project"),
        body.get("mission"),
        body.get("project_profile"),
    )
    platform = _first_dict(body.get("robotics_platform"), project.get("platform"))
    machine = _dict(body.get("machine"))
    mission = _string_list(project.get("mission") or project.get("intended_behaviors") or project.get("tasks"))
    if not mission:
        intent = str(project.get("goal") or project.get("objective") or machine.get("design_intent") or "").strip()
        if intent:
            mission = [intent]
    robot_class = str(
        project.get("robot_class")
        or project.get("platform_class")
        or platform.get("robot_class")
        or platform.get("type")
        or _infer_robot_class(body)
        or ""
    ).strip()
    environment = _first_dict(project.get("operating_environment"), project.get("environment"), body.get("operating_environment"))
    constraints = _first_dict(project.get("constraints"), body.get("constraints"))
    operating_modes = _string_list(project.get("operating_modes") or project.get("modes"))
    blockers = []
    if not robot_class:
        blockers.append("Declare robotics_project.robot_class or robotics_platform.type.")
    if not mission:
        blockers.append("Declare at least one mission, task, intended behavior, or project objective.")
    if not environment:
        blockers.append("Declare operating_environment with domain, boundaries, hazards, or constraints.")

    return {
        "available": bool(project or platform or mission or robot_class),
        "robot_class": robot_class,
        "mission": mission,
        "operating_environment": environment,
        "constraints": constraints,
        "operating_modes": operating_modes,
        "blockers": blockers,
    }


def _platform_topology(body: Dict[str, Any], engineering: Dict[str, Any], actuation: Dict[str, Any]) -> Dict[str, Any]:
    platform = _first_dict(body.get("robotics_platform"), _dict(body.get("robotics_project")).get("platform"))
    mechanism = _dict(body.get("mechanism"))
    analysis = _dict(engineering.get("analysis"))
    mechanism_analysis = _dict(analysis.get("mechanism"))
    actuation_profile = _dict(actuation.get("actuation_profile"))
    actuators = _list_dicts(actuation_profile.get("actuators"))
    springs = _list_dicts(actuation_profile.get("springs"))
    sensors = _list_dicts(actuation_profile.get("sensors"))
    primitives = _mechanism_primitives(mechanism)
    outputs = _string_list(mechanism_analysis.get("outputs"))
    domains = _domains(actuators, springs, primitives, platform)
    mobility = _first_dict(platform.get("mobility"), _dict(body.get("robotics_project")).get("mobility"))
    dof = _int(platform.get("degrees_of_freedom") or platform.get("dof"), 0)
    if dof <= 0:
        dof = _infer_dof(actuators, primitives)

    blockers = []
    if not primitives and not outputs:
        blockers.append("No mechanical primitives or generated mechanical outputs are connected to the robotics platform.")
    if not actuators and not springs:
        blockers.append("No actuators, motors, fans, pumps, springs, or moving elements are connected to the platform.")
    if "locomotion" in domains and not (mobility or any(_has_word(row, ["wheel", "track", "leg", "drive"]) for row in actuators)):
        blockers.append("Locomotion domain needs mobility topology such as differential_drive, tracked, legged, or aerial.")
    if "manipulation" in domains and dof <= 0:
        blockers.append("Manipulator/motion platform needs degrees_of_freedom or inferred actuator axes.")

    return {
        "available": bool(platform or primitives or actuators or springs),
        "mechanism_primitives": primitives,
        "generated_outputs": outputs,
        "domains": domains,
        "mobility": mobility,
        "degrees_of_freedom": dof,
        "actuator_count": len(actuators),
        "spring_count": len(springs),
        "sensor_count": len(sensors),
        "actuators": actuators,
        "springs": springs,
        "sensors": sensors,
        "blockers": _dedupe_strings(blockers),
    }


def _power_drive_status(body: Dict[str, Any], engineering: Dict[str, Any], actuation: Dict[str, Any]) -> Dict[str, Any]:
    drive = _dict(actuation.get("drive_requirements"))
    coupling = _dict(actuation.get("electrical_coupling"))
    analysis = _dict(engineering.get("analysis"))
    power = _dict(analysis.get("power"))
    machine = _dict(body.get("machine"))
    boards = _list_dicts(machine.get("boards"))
    current_budget_a = 0.0
    for board in boards:
        caps = _dict(board.get("capabilities"))
        current_budget_a += max(_float(caps.get("actuation_current_budget_a"), 0.0), 0.0)
    if current_budget_a <= 0:
        for source in _list_dicts(power.get("sources")):
            current_budget_a += max(_float(source.get("max_current_a"), 0.0), 0.0)

    peak_current = _float(drive.get("estimated_peak_current_a"), 0.0)
    run_current = _float(drive.get("estimated_run_current_a"), 0.0)
    blockers = list(_string_list(coupling.get("blockers")))
    warnings = list(_string_list(coupling.get("warnings")))
    if peak_current > 0 and current_budget_a > 0 and peak_current > current_budget_a:
        blockers.append(f"Estimated actuator peak current {peak_current:g} A exceeds explicit budget {current_budget_a:g} A.")
    if peak_current > 0 and current_budget_a <= 0:
        warnings.append("No explicit actuator current budget was found for robotics platform authority.")
    if peak_current > 0 and not _dict(drive.get("channels")):
        blockers.append("Drive requirements do not expose controller/driver channels.")

    return {
        "available": bool(drive),
        "estimated_run_current_a": round(run_current, 3),
        "estimated_peak_current_a": round(peak_current, 3),
        "explicit_current_budget_a": round(current_budget_a, 3),
        "channels": _dict(drive.get("channels")),
        "drive_types": _string_list(drive.get("drive_types")),
        "rail_peak_currents_a": _dict(drive.get("rail_peak_currents_a")),
        "required_protections": _string_list(drive.get("required_protections")),
        "coupling_matched": bool(coupling.get("matched")),
        "power_paths_seen": bool(coupling.get("power_paths_seen") or power.get("rails") or power.get("source_currents_a")),
        "blockers": _dedupe_strings(blockers),
        "warnings": _dedupe_strings(warnings),
    }


def _control_safety_status(body: Dict[str, Any], topology: Dict[str, Any], power_drive: Dict[str, Any]) -> Dict[str, Any]:
    control = _first_dict(
        body.get("control_stack"),
        _dict(body.get("robotics_project")).get("control_stack"),
        _dict(body.get("robotics_actuation")).get("control_stack"),
    )
    safety = _first_dict(body.get("safety_case"), _dict(body.get("robotics_project")).get("safety_case"))
    controllers = _list_dicts(control.get("controllers"))
    loops = _list_dicts(control.get("loops") or control.get("control_loops"))
    sensors = _list_dicts(control.get("sensors")) + _list_dicts(topology.get("sensors"))
    comms = _list_dicts(control.get("comms") or control.get("communication_links"))
    failsafes = _string_list(control.get("failsafes")) + _string_list(safety.get("failsafes"))
    mitigations = _string_list(safety.get("mitigations")) + _string_list(safety.get("protections"))
    hazards = _list_dicts(safety.get("hazards"))
    unmitigated = [row for row in hazards if not _row_passed(row) and not str(row.get("mitigation") or "").strip()]

    blockers = []
    if not controllers:
        blockers.append("Control stack needs at least one controller/firmware target.")
    if int(topology.get("actuator_count") or 0) > 0 and not loops:
        blockers.append("Moving platform needs control loops or command/update rates.")
    if int(topology.get("sensor_count") or 0) == 0 and not sensors:
        blockers.append("Robotics platform needs feedback, limit, perception, or operator-state sensors.")
    if not comms and _requires_comms(topology):
        blockers.append("Mobile or operator-controlled robot needs communication/control-link plan.")
    if int(topology.get("actuator_count") or 0) > 0 and not failsafes:
        blockers.append("Moving platform needs explicit failsafes such as e_stop, watchdog, signal_loss_stop, or current_limit.")

    required_protections = set(_string_list(power_drive.get("required_protections")))
    planned = set(failsafes + mitigations + _string_list(safety.get("safety_features")))
    missing = sorted(item for item in required_protections if item not in planned)
    if missing:
        blockers.append("Safety/control plan is missing required protections: " + ", ".join(missing) + ".")
    if unmitigated:
        blockers.append("Safety case has unmitigated hazards: " + ", ".join(str(row.get("id") or row.get("hazard") or "hazard") for row in unmitigated[:5]) + ".")

    return {
        "available": bool(control or safety),
        "controller_count": len(controllers),
        "loop_count": len(loops),
        "sensor_count": len(sensors),
        "communication_link_count": len(comms),
        "failsafes": _dedupe_strings(failsafes),
        "hazards": hazards,
        "mitigations": _dedupe_strings(mitigations),
        "blockers": _dedupe_strings(blockers),
    }


def _validation_status(
    body: Dict[str, Any],
    mechanical: Dict[str, Any],
    actuation: Dict[str, Any],
    mechatronics: Dict[str, Any],
    simulation: Dict[str, Any],
) -> Dict[str, Any]:
    validation = _first_dict(
        body.get("field_validation"),
        body.get("robotics_validation"),
        _dict(body.get("robotics_project")).get("validation"),
    )
    integrated = _first_dict(body.get("integrated_bench_capture"), body.get("hardware_bench_capture"), body.get("system_bench_capture"))
    simulations = _list_dicts(validation.get("simulations") or validation.get("simulation_tests"))
    bench_tests = _rows_from(validation, "bench_tests", "motion_tests", "load_tests", "power_tests", "thermal_tests", "cycle_tests")
    integrated_bench_tests = _rows_from(integrated, "tests", "electrical_tests", "motion_tests", "packaging_tests", "thermal_tests", "cycle_tests")
    field_tests = _rows_from(validation, "field_tests", "operational_tests", "mission_tests")
    passed_sim = [row for row in simulations if _row_passed(row)]
    passed_bench = [row for row in bench_tests if _row_passed(row)]
    passed_integrated_bench = [row for row in integrated_bench_tests if _row_passed(row)]
    passed_field = [row for row in field_tests if _row_passed(row)]
    failed = [row for row in simulations + bench_tests + integrated_bench_tests + field_tests if _row_failed(row)]
    artifacts = _artifact_count(validation) + _artifact_count(integrated)
    explicit_field = bool(validation.get("field_verified") is True or validation.get("mission_verified") is True)
    explicit_bench = bool(
        validation.get("bench_verified") is True
        or integrated.get("integrated_bench_ready") is True
        or integrated.get("system_verified") is True
    )
    integration_gaps = _string_list(_dict(mechatronics.get("integration_trace")).get("open_gaps"))
    simulation_ready = bool(simulation.get("simulation_ready"))
    simulation_blockers = _string_list(row.get("message") for row in _list_dicts(simulation.get("blocking_findings")))

    blockers = []
    if not bool(mechanical.get("production_authorized")):
        blockers.append("Mechanical subsystem must close production mechanical release for platform authority.")
    if not bool(actuation.get("production_authorized")):
        blockers.append("Robotics actuation subsystem must close production robotics release for platform authority.")
    if not bool(mechatronics.get("production_authorized")):
        blockers.append("Hardware-Splicer mechatronics authority must close before project-level robotics release.")
    if integration_gaps:
        blockers.append("Mechatronics integration trace still has open gaps: " + "; ".join(integration_gaps[:6]))
    if simulation and not simulation_ready:
        blockers.append("Robotics simulation has blocking findings: " + "; ".join(simulation_blockers[:6]))
    if failed:
        blockers.extend(str(row.get("message") or row.get("target") or "validation failure") for row in failed)
    if not (simulation_ready or passed_sim):
        blockers.append("Record deterministic simulation validation for the robotics platform.")
    if not (explicit_bench or passed_bench or passed_integrated_bench):
        blockers.append("Record controlled bench validation for the robotics platform.")
    if not (passed_field or explicit_field):
        blockers.append("Record field/mission validation in the declared operating environment.")
    if artifacts < 1 and not explicit_field:
        blockers.append("Attach validation artifacts, logs, photos, videos, or telemetry.")

    return {
        "available": bool(validation or integrated),
        "simulation_pass_count": len(passed_sim),
        "bench_pass_count": len(passed_bench) + len(passed_integrated_bench),
        "field_pass_count": len(passed_field),
        "failed_count": len(failed),
        "artifact_count": artifacts,
        "bench_ready": bool(explicit_bench or passed_bench or passed_integrated_bench),
        "field_ready": bool(explicit_field or passed_field),
        "simulation_ready": simulation_ready,
        "simulation_blocker_count": int(simulation.get("blocking_finding_count") or len(simulation_blockers)),
        "subsystems_ready": bool(
            mechanical.get("production_authorized")
            and actuation.get("production_authorized")
            and mechatronics.get("production_authorized")
            and not integration_gaps
            and simulation_ready
        ),
        "integration_gap_count": len(integration_gaps),
        "blockers": _dedupe_strings(blockers),
    }


def _release_status(body: Dict[str, Any]) -> Dict[str, Any]:
    release = _first_dict(
        body.get("robotics_project_release"),
        body.get("field_release"),
        body.get("mechatronics_release"),
        body.get("hardware_release"),
    )
    blockers = []
    if not release:
        blockers.append("Attach robotics_project_release with scope, artifact URIs, and acceptance review.")
    if release and not str(release.get("scope_statement") or "").strip():
        blockers.append("Robotics project release needs a scope_statement.")
    if release and not bool(release.get("acceptance_reviewed")):
        blockers.append("Robotics project release acceptance must be reviewed.")
    if release and _artifact_count(release) < 1:
        blockers.append("Robotics project release needs artifact_uris or equivalent evidence references.")
    return {
        "available": bool(release),
        "release_ready": bool(release and not blockers),
        "scope_statement": str(release.get("scope_statement") or "").strip(),
        "blockers": blockers,
    }


def _stages(
    *,
    profile: Dict[str, Any],
    topology: Dict[str, Any],
    power_drive: Dict[str, Any],
    control_safety: Dict[str, Any],
    validation: Dict[str, Any],
    release: Dict[str, Any],
) -> List[Dict[str, Any]]:
    stages: List[Dict[str, Any]] = []
    _stage(
        stages,
        "robotics_project_intake",
        not profile["blockers"],
        profile["blockers"],
        "Close platform topology, mechanisms, actuators, sensors, and generated outputs.",
    )
    _stage(
        stages,
        "platform_architecture",
        _passed(stages, "robotics_project_intake") and not topology["blockers"],
        topology["blockers"],
        "Close drive, power, channel, and protection budgets.",
    )
    _stage(
        stages,
        "power_drive_architecture",
        _passed(stages, "platform_architecture") and bool(power_drive["available"]) and not power_drive["blockers"],
        power_drive["blockers"] or ([] if power_drive["available"] else ["Robotics drive/power budget is missing."]),
        "Close controller, sensor, failsafe, and hazard mitigation architecture.",
    )
    _stage(
        stages,
        "control_safety_architecture",
        _passed(stages, "power_drive_architecture") and bool(control_safety["available"]) and not control_safety["blockers"],
        control_safety["blockers"] or ([] if control_safety["available"] else ["Control stack and safety case are missing."]),
        "Run simulation, controlled bench validation, and subsystem release closure.",
    )
    _stage(
        stages,
        "simulation_bench_authority",
        _passed(stages, "control_safety_architecture")
        and bool(validation["simulation_ready"])
        and bool(validation["bench_ready"])
        and bool(validation["subsystems_ready"])
        and not validation["failed_count"],
        validation["blockers"],
        "Run field/mission validation in the declared operating environment.",
    )
    _stage(
        stages,
        "field_validation_authority",
        _passed(stages, "simulation_bench_authority") and bool(validation["field_ready"]) and not validation["failed_count"],
        validation["blockers"],
        "Attach reviewed robotics project release scope and artifacts.",
    )
    _stage(
        stages,
        "production_robotics_project_release",
        _passed(stages, "field_validation_authority") and bool(release["release_ready"]),
        release["blockers"],
        "No remaining action for this scoped robotics project release.",
    )
    return stages


def _stage(stages: List[Dict[str, Any]], stage_id: str, passed: bool, blockers: List[str], next_unlock: str) -> None:
    stages.append(
        {
            "stage_id": stage_id,
            "status": "pass" if passed else "open",
            "score_if_current": LEVEL_SCORES[stage_id],
            "blockers": [] if passed else blockers[:12],
            "next_unlock": next_unlock,
        }
    )


def _capabilities(stages: List[Dict[str, Any]]) -> Dict[str, bool]:
    return {
        "write_robotics_project_brief": _passed(stages, "robotics_project_intake"),
        "plan_platform_topology": _passed(stages, "platform_architecture"),
        "size_power_drive_control": _passed(stages, "power_drive_architecture"),
        "claim_control_safety_architecture": _passed(stages, "control_safety_architecture"),
        "run_integrated_robotics_bench": _passed(stages, "simulation_bench_authority"),
        "claim_field_validated_robotics_project": _passed(stages, "field_validation_authority"),
        "claim_production_robotics_project_release": _passed(stages, "production_robotics_project_release"),
    }


def _claim_boundary(level: str | None) -> str:
    if level == "production_robotics_project_release":
        return "Scoped robotics/mechatronics project release is authorized within the reviewed mission, operating environment, and artifact bundle."
    if level == "field_validation_authority":
        return "Field/mission validation is present; final release scope review remains open."
    if level == "simulation_bench_authority":
        return "Subsystems and bench validation are ready for declared field/mission testing."
    if level == "control_safety_architecture":
        return "Control stack and safety case are coherent enough for controlled bench validation."
    if level == "power_drive_architecture":
        return "Platform topology and drive/power budgets are coherent; control/safety validation remains open."
    if level == "platform_architecture":
        return "Mission and platform topology are coherent; drive/power/control evidence remains open."
    if level == "robotics_project_intake":
        return "Robotics project intent is captured, but platform architecture remains unproven."
    return "No robotics platform/project authority is available."


def _scope_limits(profile: Dict[str, Any], topology: Dict[str, Any], release: Dict[str, Any]) -> List[str]:
    limits = []
    if release.get("scope_statement"):
        limits.append(str(release["scope_statement"]))
    robot_class = str(profile.get("robot_class") or "robotics platform")
    limits.append(f"Project class scope: {robot_class}.")
    missions = _string_list(profile.get("mission"))
    if missions:
        limits.append("Mission scope: " + "; ".join(missions[:5]))
    domains = _string_list(topology.get("domains"))
    if domains:
        limits.append("Motion domain scope: " + ", ".join(domains))
    limits.append("No human-carrying, road-vehicle, medical, aviation certification, pressure, or regulatory safety claim is implied.")
    return _dedupe_strings(limits)


def _next_engineering_actions(
    stages: List[Dict[str, Any]],
    control_safety: Dict[str, Any],
    validation: Dict[str, Any],
    release: Dict[str, Any],
) -> List[str]:
    actions: List[str] = []
    for stage in stages:
        if stage.get("status") != "pass":
            actions.extend(_string_list(stage.get("blockers")))
            break
    if not control_safety.get("available"):
        actions.append("Define controllers, command loops, sensors, communication links, failsafes, and hazard mitigations.")
    if not validation.get("available"):
        actions.append("Define simulation, bench, and field validation rows with evidence artifacts.")
    if not release.get("available"):
        actions.append("Add robotics_project_release with reviewed scope and artifact URIs.")
    return _dedupe_strings(actions)[:14]


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


def _infer_robot_class(body: Dict[str, Any]) -> str:
    mechanism = _dict(body.get("mechanism"))
    robotics = _dict(body.get("robotics_actuation"))
    actuators = _list_dicts(robotics.get("actuators"))
    text = " ".join(
        [str(key) for key, value in mechanism.items() if isinstance(value, Mapping)]
        + [str(row.get("role") or row.get("type") or row.get("id") or "") for row in actuators]
    ).lower()
    if any(word in text for word in ["wheel", "drive motor", "track", "rover"]):
        return "mobile_robot"
    if any(word in text for word in ["arm", "gripper", "manipulator"]):
        return "manipulator"
    if any(word in text for word in ["pump", "valve", "fluid"]):
        return "fluidic_machine"
    if any(word in text for word in ["fan", "blower", "air"]):
        return "airflow_machine"
    if any(word in text for word in ["pan", "tilt", "servo"]):
        return "positioning_robot"
    return ""


def _mechanism_primitives(mechanism: Dict[str, Any]) -> List[str]:
    return sorted(
        str(key)
        for key, value in mechanism.items()
        if key not in {"project_name", "mode", "process", "metadata"} and isinstance(value, Mapping) and value
    )


def _domains(
    actuators: List[Dict[str, Any]],
    springs: List[Dict[str, Any]],
    primitives: List[str],
    platform: Dict[str, Any],
) -> List[str]:
    domains = set(_string_list(platform.get("domains")))
    text = " ".join(
        primitives
        + [str(row.get("role") or row.get("type") or row.get("id") or "") for row in actuators]
        + [str(row.get("role") or row.get("type") or row.get("id") or "") for row in springs]
    ).lower()
    if any(word in text for word in ["wheel", "drive", "track", "leg", "locomotion", "rover"]):
        domains.add("locomotion")
    if any(word in text for word in ["gripper", "arm", "jaw", "manipulator"]):
        domains.add("manipulation")
    if any(word in text for word in ["pan", "tilt", "axis", "rotary", "leadscrew", "belt", "position"]):
        domains.add("positioning")
    if any(word in text for word in ["fan", "blower", "air"]):
        domains.add("airflow")
    if any(word in text for word in ["pump", "valve", "fluid", "soil", "water"]):
        domains.add("fluid")
    if springs:
        domains.add("stored_energy")
    return sorted(domains)


def _infer_dof(actuators: List[Dict[str, Any]], primitives: List[str]) -> int:
    moving_primitives = [item for item in primitives if item not in {"enclosure", "bracket", "assembly"}]
    return max(len(actuators), len(moving_primitives))


def _requires_comms(topology: Dict[str, Any]) -> bool:
    domains = set(_string_list(topology.get("domains")))
    return bool(domains & {"locomotion", "manipulation", "positioning"})


def _has_word(row: Dict[str, Any], words: List[str]) -> bool:
    text = " ".join(str(row.get(key) or "") for key in ("id", "name", "role", "type", "model")).lower()
    return any(word in text for word in words)


def _rows_from(source: Dict[str, Any], *keys: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key in keys:
        rows.extend(_list_dicts(source.get(key)))
    return rows


def _row_passed(row: Dict[str, Any]) -> bool:
    status = str(row.get("status") or row.get("result") or row.get("decision") or "").strip().lower()
    return status in PASS_STATUSES or row.get("pass") is True


def _row_failed(row: Dict[str, Any]) -> bool:
    status = str(row.get("status") or row.get("result") or row.get("decision") or "").strip().lower()
    return status in FAIL_STATUSES or row.get("pass") is False


def _artifact_count(capture: Dict[str, Any]) -> int:
    count = 0
    for key in ["artifact_uris", "artifacts", "evidence_uris", "logs", "photos", "videos", "telemetry"]:
        value = capture.get(key)
        if isinstance(value, list):
            count += len([item for item in value if item])
        elif isinstance(value, str) and value.strip():
            count += 1
    return count


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


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
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
        return [str(item) for item in value.values() if str(item).strip()]
    if isinstance(value, Iterable):
        return [str(item).strip() for item in value if str(item).strip()]
    return []
