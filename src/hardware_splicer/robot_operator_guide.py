"""Generate ordered, evidence-governed robot build and modification guidance."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .change_impact import ChangeImpactGraph, ChangeMode
from .engineering_analysis import EngineeringAnalysisReport
from .engineering_source_graph import EngineeringSourceGraph
from .machine_project import AuthorityState, MachineProject
from .robot_topology import RobotGenre, RobotTopology


ROBOT_OPERATOR_GUIDE_SCHEMA = "hardware_splicer.robot_operator_guide.v1"


class GuidePhase(str, Enum):
    SCOPE = "scope"
    SOURCES = "sources"
    PROCUREMENT = "procurement"
    MECHANICAL = "mechanical"
    ELECTRICAL = "electrical"
    FIRMWARE = "firmware"
    MIDDLEWARE = "middleware"
    SIMULATION = "simulation"
    CALIBRATION = "calibration"
    FIRST_POWER = "first_power"
    FIRST_MOTION = "first_motion"
    INTEGRATION = "integration"
    REGRESSION = "regression"
    ROLLBACK = "rollback"
    RELEASE = "release"


class GuideModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class GuideStep(GuideModel):
    step_id: str = Field(min_length=1)
    order: int = Field(ge=1)
    phase: GuidePhase
    title: str = Field(min_length=1)
    instructions: list[str] = Field(min_length=1)
    target_ids: list[str] = Field(default_factory=list)
    prerequisite_step_ids: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    hazards: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    evidence_to_capture: list[str] = Field(default_factory=list)
    acceptance_criteria: Dict[str, Any] = Field(default_factory=dict)
    rollback: list[str] = Field(default_factory=list)
    blocking: bool = True
    status: str = "planned"
    authority: AuthorityState = AuthorityState.PROPOSED


class RobotOperatorGuide(GuideModel):
    schema_version: str = ROBOT_OPERATOR_GUIDE_SCHEMA
    project_id: str = Field(min_length=1)
    robot_genre: RobotGenre
    mode: ChangeMode
    steps: list[GuideStep] = Field(default_factory=list)
    current_blockers: list[str] = Field(default_factory=list)
    next_step_id: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _source_claims(source_graph: EngineeringSourceGraph, predicate: str) -> list[Any]:
    return [row.value for row in source_graph.claims if row.predicate == predicate]


def _part_rows(plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = plan.get("normalized_parts") or (plan.get("normalized_intake") or {}).get("available_parts") or []
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _step(
    steps: list[GuideStep],
    phase: GuidePhase,
    title: str,
    instructions: list[str],
    **kwargs: Any,
) -> GuideStep:
    row = GuideStep(
        step_id=f"guide-{len(steps) + 1:02d}-{phase.value}",
        order=len(steps) + 1,
        phase=phase,
        title=title,
        instructions=instructions,
        **kwargs,
    )
    steps.append(row)
    return row


def build_robot_operator_guide(
    plan: Mapping[str, Any],
    *,
    project: MachineProject,
    topology: RobotTopology,
    source_graph: EngineeringSourceGraph,
    analysis: EngineeringAnalysisReport,
    change_impact: ChangeImpactGraph,
) -> RobotOperatorGuide:
    """Build a conservative guide from the canonical engineering plan."""

    steps: list[GuideStep] = []
    blockers: list[str] = []
    source_blockers = [row for row in source_graph.conflicts if row.blocking]
    analysis_blockers = analysis.blocking_findings
    unresolved_interfaces = [row for row in project.traceability_issues() if row.code == "unresolved_interface"]
    blockers.extend(f"Source conflict {row.conflict_id}: {row.reason}" for row in source_blockers)
    blockers.extend(f"Engineering finding {row.finding_id}: {row.message}" for row in analysis_blockers)
    blockers.extend(row.message for row in unresolved_interfaces)

    scope = _step(
        steps,
        GuidePhase.SCOPE,
        "Freeze the mission and operating envelope",
        [
            "Review the user goal, constraints, forbidden behaviors, environment, payload, runtime, speed, and budget.",
            "Record the exact project revision and identify whether this is a greenfield build, modification, repair, or field-failure revision.",
            "Do not proceed from an example project unless its revision and compatibility with the requested machine are explicit.",
        ],
        target_ids=[project.project_id],
        required_inputs=["approved requirement set", "operating environment", "operator and bystander safety boundary"],
        evidence_to_capture=["signed or recorded requirement review", "baseline revision for non-greenfield work"],
        acceptance_criteria={"requirements_reviewed": True, "scope_changes_recorded": True},
        rollback=["Return to intake and revise requirements before ordering or modifying hardware."],
    )

    source = _step(
        steps,
        GuidePhase.SOURCES,
        "Select and pin the engineering evidence set",
        [
            "Review every repository, CAD model, drawing, schematic, BOM, datasheet, firmware manifest, middleware contract, measurement, telemetry run, photo, or video observation.",
            "Pin each source by revision, commit, content hash, capture ID, or retrieval timestamp.",
            "Disposition every blocking conflict by selecting a coherent revision, accepting a documented variant, or scheduling a measurement. Never merge incompatible claims silently.",
        ],
        target_ids=[project.project_id],
        prerequisite_step_ids=[scope.step_id],
        required_inputs=["source identities", "revision or hash", "authority ceiling", "conflict disposition"],
        evidence_to_capture=["source manifest", "conflict review record", "selected model source"],
        acceptance_criteria={"blocking_source_conflicts": 0, "unresolved_source_references": 0},
        blocking=True,
        rollback=["Remove the disputed source from the candidate or return to a previously coherent revision boundary."],
    )

    part_rows = _part_rows(plan)
    procurement_lines = [
        f"Confirm {row.get('quantity', 1)} × {row.get('name') or row.get('component_id') or 'unnamed part'} including exact package, rating, and revision."
        for row in part_rows
    ] or ["Create a quantified BOM with exact part identities before procurement."]
    procurement = _step(
        steps,
        GuidePhase.PROCUREMENT,
        "Reconcile parts, tools, and substitutes",
        procurement_lines
        + [
            "Verify every substitute against mechanical envelope, connector, voltage, current, protocol, firmware, and sourcing constraints.",
            "Separate reusable donor blocks from unknown or damaged blocks; unknown interfaces remain quarantined until measured.",
        ],
        target_ids=[row.component_id for row in project.components],
        prerequisite_step_ids=[source.step_id],
        required_inputs=["quantified BOM", "part identity", "tool list", "substitute compatibility record"],
        tools=["calipers", "multimeter", "current-limited bench supply", "appropriate hand tools"],
        evidence_to_capture=["BOM reconciliation", "received-part inspection", "donor characterization"],
        acceptance_criteria={"all_required_parts_identified": True, "unknown_substitutions": 0},
        rollback=["Reject the substitute or update the design and rerun impact analysis."],
    )

    link_count = len(topology.links)
    joint_count = len(topology.joints)
    sensor_count = len(topology.sensors)
    mechanical = _step(
        steps,
        GuidePhase.MECHANICAL,
        "Build and inspect the mechanical topology",
        [
            f"Assemble {link_count} declared links and {joint_count} joint relationships using the canonical topology IDs.",
            "Verify orientation, handedness, fastener engagement, clearances, cable paths, collision envelopes, and service access before installing powered electronics.",
            f"Install {sensor_count} sensor mounts only after pose, field of view, vibration, and clearance requirements are recorded.",
            "Measure the finished support geometry, mass, center of mass, payload lever arms, and joint travel; update the analysis instead of relying on nominal CAD alone.",
        ],
        target_ids=[f"robot-link-{row.link_id}" for row in topology.links]
        + [f"robot-joint-{row.joint_id}" for row in topology.joints],
        prerequisite_step_ids=[procurement.step_id],
        required_inputs=["dimensioned topology", "fastener specification", "joint limits", "sensor poses", "mass properties"],
        tools=["calipers", "torque-appropriate drivers", "squares or alignment jigs", "scale"],
        hazards=["pinch points", "sharp printed or machined edges", "unstable unsupported assemblies"],
        stop_conditions=["binding joint", "unexpected collision", "cracked part", "unresolved fastener or load path"],
        evidence_to_capture=["measured dimensions", "joint range log", "fit photographs", "mass and center-of-mass record"],
        acceptance_criteria={"mechanical_fit": "pass", "joint_motion_unpowered": "free and bounded", "measured_geometry_attached": True},
        rollback=["Disassemble the affected module, restore the last measured-good geometry, and revise CAD or part selection."],
    )

    electrical = _step(
        steps,
        GuidePhase.ELECTRICAL,
        "Wire and inspect the electrical system with power removed",
        [
            "Create a point-to-point harness or PCB/net map from canonical component and interface IDs.",
            "Verify polarity, grounding, connector keying, conductor gauge, fusing, regulator headroom, motor/servo rails, logic rails, and emergency isolation.",
            "Continuity-test every supply and return path before connecting the battery or enabling a power supply.",
            "Resolve every actuator power contract and sensor pin/protocol contract; do not infer hidden pins from appearance or an unrelated revision.",
        ],
        target_ids=[row.interface_id for row in project.interfaces if row.kind in {"electrical_power", "sensor_data_channel"}],
        prerequisite_step_ids=[mechanical.step_id],
        required_inputs=["schematic or harness map", "pin map", "voltage/current limits", "protection plan"],
        tools=["multimeter", "continuity tester", "current-limited bench supply", "insulated probes"],
        hazards=["reverse polarity", "short circuit", "battery fire", "unexpected actuator movement"],
        stop_conditions=["continuity to an unintended rail", "unknown polarity", "missing protection", "current requirement exceeds supply or wiring rating"],
        evidence_to_capture=["continuity matrix", "resistance-to-ground checks", "harness photographs", "rail and protection review"],
        acceptance_criteria={"unintended_shorts": 0, "polarity_verified": True, "current_margin_nonnegative": True},
        rollback=["Disconnect all energy sources, isolate the faulty branch, and restore the last verified wiring revision."],
    )

    firmware_revision = _source_claims(source_graph, "source_revision")
    build_commands = _source_claims(source_graph, "build_command")
    binary_hashes = _source_claims(source_graph, "binary_hash")
    firmware = _step(
        steps,
        GuidePhase.FIRMWARE,
        "Build, configure, and stage firmware reproducibly",
        [
            "Pin the firmware repository revision, toolchain version, dependency lock, board profile, configuration, and pin-map hash.",
            "Build from a clean workspace and record the exact command, compiler output, binary hash, and warnings.",
            "Flash only while the actuator power path is isolated or mechanically restrained; record target hardware revision and flash result.",
            "Confirm fault handling, watchdog, command timeout, safe startup state, direction conventions, and current/position limits before motion testing.",
        ],
        target_ids=[row.component_id for row in project.components if row.domain.value == "firmware"],
        prerequisite_step_ids=[electrical.step_id],
        required_inputs=[
            "firmware source revision",
            "toolchain and dependency lock",
            "pin-map hash",
            "board and hardware revision",
        ],
        tools=["isolated programming/debug interface", "serial console", "version-controlled build environment"],
        hazards=["wrong pin map", "unbounded actuator command", "flashing the wrong hardware revision"],
        stop_conditions=["unreproducible build", "binary hash mismatch", "unknown board target", "unsafe startup output"],
        evidence_to_capture=["build log", "binary hash", "flash log", "configuration and pin-map hash", "safe-start observation"],
        acceptance_criteria={
            "source_revision_pinned": bool(firmware_revision),
            "build_command_recorded": bool(build_commands),
            "binary_hash_recorded": bool(binary_hashes),
            "safe_start_verified": True,
        },
        rollback=["Restore the last known-good binary and configuration; keep actuator power isolated until the cause is resolved."],
    )

    ros_topics = _source_claims(source_graph, "ros_topics")
    middleware = _step(
        steps,
        GuidePhase.MIDDLEWARE,
        "Align robot models, frames, and middleware contracts",
        [
            "Match joint, actuator, sensor, frame, topic, service, action, and parameter names to the canonical identity map.",
            "Verify URDF/SDF/MJCF revision, frame transforms, message types, units, sign conventions, QoS, rates, and timeout behavior.",
            "Run interface checks without physical motion and reject stale or cross-revision configurations.",
        ],
        target_ids=[row.component_id for row in project.components if row.domain.value == "software"],
        prerequisite_step_ids=[firmware.step_id],
        required_inputs=["robot model revision", "interface manifest", "frame tree", "message and unit contracts"],
        tools=["middleware introspection tools", "log capture", "simulation or replay environment"],
        stop_conditions=["duplicate frame", "unit/sign mismatch", "unexpected topic producer", "stale robot model"],
        evidence_to_capture=["interface inventory", "frame-tree snapshot", "message-rate log", "configuration hashes"],
        acceptance_criteria={"canonical_identity_alignment": True, "declared_topics_present": bool(ros_topics) or "not applicable"},
        rollback=["Restore the previous model and interface configuration, then rerun compatibility analysis."],
    )

    simulation = _step(
        steps,
        GuidePhase.SIMULATION,
        "Run design and control checks before energizing motion",
        [
            "Validate joint limits, collisions, payload, center of mass, support geometry, power budget, runtime, torque, thermal, and control assumptions with the best available model.",
            "Exercise startup, command timeout, emergency stop, sensor loss, communication loss, and invalid-command scenarios.",
            "Treat simulation and calculation as proposed evidence only; carry every model limitation into the bench plan.",
        ],
        target_ids=[topology.topology_id, project.project_id],
        prerequisite_step_ids=[middleware.step_id],
        required_inputs=["measured geometry where available", "mass/inertia", "limits", "load and power inputs", "failure scenarios"],
        tools=["robot simulator", "calculation report", "log and plot tools"],
        stop_conditions=["collision", "negative margin", "unstable response", "unmodeled safety-critical condition"],
        evidence_to_capture=["simulation revision", "input hashes", "plots/logs", "pass/fail disposition", "known model limitations"],
        acceptance_criteria={"blocking_analysis_findings": 0, "known_model_limitations_recorded": True},
        rollback=["Return to design, parts, wiring, firmware, or control configuration and regenerate the candidate."],
    )

    calibration = _step(
        steps,
        GuidePhase.CALIBRATION,
        "Calibrate sensors and actuators under restraint",
        [
            "Establish mechanical zero references and confirm joint direction one channel at a time.",
            "Calibrate current, position, velocity, IMU, magnetometer, camera, encoder, and force/torque channels that affect operation.",
            "Store calibration against the exact hardware, firmware, topology, and configuration revisions; never reuse values from a different assembly without verification.",
        ],
        target_ids=[f"robot-joint-{row.joint_id}" for row in topology.joints]
        + [f"robot-sensor-{row.sensor_id}" for row in topology.sensors],
        prerequisite_step_ids=[simulation.step_id],
        required_inputs=["calibration procedure", "reference fixture or instrument", "safe command limits"],
        tools=["fixtures or stands", "reference instruments", "current monitoring", "logging"],
        hazards=["unexpected movement", "pinch or impact", "sensor saturation"],
        stop_conditions=["wrong direction", "current spike", "mechanical binding", "non-repeatable zero", "sensor instability"],
        evidence_to_capture=["calibration constants", "raw calibration logs", "hardware and firmware revision hashes"],
        acceptance_criteria={"all_required_channels_calibrated": True, "repeatability_within_limit": True},
        rollback=["Disable the channel, restore prior calibration, and inspect mechanical/electrical identity before retrying."],
    )

    first_power = _step(
        steps,
        GuidePhase.FIRST_POWER,
        "Perform current-limited first power",
        [
            "Remove or restrain propellers, wheels, limbs, tools, and other moving hazards as appropriate to the robot genre.",
            "Use the lowest practical current limit and staged rail enablement; monitor logic and actuator rails separately when possible.",
            "Verify safe startup outputs, communication, sensor sanity, rail stability, regulator temperature, and emergency isolation before increasing the envelope.",
        ],
        target_ids=["power-system", project.project_id],
        prerequisite_step_ids=[calibration.step_id],
        required_inputs=["approved first-power checklist", "resolved voltage/current contracts", "emergency isolation"],
        tools=["current-limited bench supply", "multimeter", "oscilloscope or logger", "thermal monitoring"],
        hazards=["battery or regulator failure", "unexpected movement", "overheating", "electrical damage"],
        stop_conditions=["unexpected current", "rail sag or oscillation", "smoke/odor/heat", "reset", "uncommanded output"],
        evidence_to_capture=["rail waveforms", "startup current", "thermal observation", "safe-start and emergency-isolation result"],
        acceptance_criteria={"current_within_limit": True, "rails_stable": True, "uncommanded_motion": False},
        rollback=["Cut power immediately, discharge safely, isolate the faulty branch, and return to electrical/firmware analysis."],
        blocking=True,
    )

    motion_instructions = [
        "Test one actuator or motion degree of freedom at a time with reduced speed, acceleration, torque/current, and travel limits.",
        "Use a stand, tether, boundary, guard, or propeller-free setup appropriate to the robot; keep an independent emergency stop within reach.",
        "Confirm direction, limit behavior, command timeout, feedback plausibility, and current before coordinated motion.",
    ]
    if topology.robot_genre == RobotGenre.QUADRUPED:
        motion_instructions.append("Begin with the body supported, then static stance, weight transfer, single-leg motion, and only then bounded gait trials.")
    elif topology.robot_genre == RobotGenre.AERIAL:
        motion_instructions.append("Keep propellers removed for motor-direction tests; use a guarded or tethered test only after thrust, mixer, attitude, and failsafe checks close.")
    elif topology.robot_genre == RobotGenre.SERIAL_MANIPULATOR:
        motion_instructions.append("Start without payload, verify each joint and collision envelope, then increase payload only within measured torque and stability margins.")
    elif topology.robot_genre == RobotGenre.ROVER:
        motion_instructions.append("Raise driven wheels for direction/encoder tests, then use a marked low-speed ground boundary before autonomous navigation.")
    first_motion = _step(
        steps,
        GuidePhase.FIRST_MOTION,
        "Run bounded first motion",
        motion_instructions,
        target_ids=[f"robot-actuator-{row.actuator_id}" for row in topology.actuators],
        prerequisite_step_ids=[first_power.step_id],
        required_inputs=["first-power pass", "calibration pass", "bounded command profile", "safe-stop method"],
        tools=["stand/tether/guard", "current and telemetry logging", "independent emergency stop"],
        hazards=["impact", "pinch/crush", "fall/tip", "propeller or wheel contact", "runaway motion"],
        stop_conditions=["wrong direction", "overshoot", "instability", "current limit", "lost communication", "failed emergency stop"],
        evidence_to_capture=["command and feedback logs", "current and voltage", "motion video", "timeout and emergency-stop result"],
        acceptance_criteria={"all_actuators_direction_verified": True, "safe_stop_verified": True, "bounded_motion_pass": True},
        rollback=["Disable motion, restore the last safe limits/calibration, and reopen the affected joint, firmware, control, or power contract."],
    )

    integration = _step(
        steps,
        GuidePhase.INTEGRATION,
        "Run integrated mission tests progressively",
        [
            "Combine subsystems in increasing complexity: sensing, low-level control, coordinated motion, autonomy, payload, and environmental mission.",
            "Use a controlled test matrix with repeated runs, objective acceptance criteria, and explicit abort conditions.",
            "Compare physical telemetry to simulation and design expectations; create change-impact records for every material deviation.",
        ],
        target_ids=[project.project_id],
        prerequisite_step_ids=[first_motion.step_id],
        required_inputs=["mission test matrix", "safe test environment", "known-good baseline", "data logging"],
        tools=["telemetry/log capture", "test fixtures and boundaries", "operator checklist"],
        hazards=["combined subsystem failure", "environment interaction", "loss of localization/control", "payload instability"],
        stop_conditions=["safety boundary breach", "repeated unexplained reset", "thermal/current instability", "unexpected collision or tip"],
        evidence_to_capture=["mission logs", "telemetry", "operator observations", "failure records", "repeatability summary"],
        acceptance_criteria={"mission_tests_passed": True, "unresolved_failures": 0, "repeatability_demonstrated": True},
        rollback=["Return to the last passing subsystem combination and create a scoped change-impact revision."],
    )

    regression = _step(
        steps,
        GuidePhase.REGRESSION,
        "Close change-specific regression scope",
        [
            f"Execute all {len(change_impact.regression_checks)} planned regression checks generated from the change-impact graph.",
            "Link every result to the exact baseline and candidate revisions, affected target IDs, instruments, firmware binary, configuration, and operator disposition.",
            "Do not reuse prior release authority for affected subsystems; restore it only through new scoped evidence and human review.",
        ],
        target_ids=change_impact.affected_target_ids or [project.project_id],
        prerequisite_step_ids=[integration.step_id],
        required_inputs=["baseline revision", "candidate revision", "affected-subsystem list", "regression checks"],
        tools=["test equipment required by each regression method"],
        evidence_to_capture=["regression result per check", "before/after comparison", "remaining limitations"],
        acceptance_criteria={"blocking_regressions_passed": True, "affected_subsystems_reverified": True},
        rollback=["Reject the candidate revision and restore the baseline, or open a narrower corrective revision."],
        blocking=change_impact.mode != ChangeMode.GREENFIELD,
    )

    rollback = _step(
        steps,
        GuidePhase.ROLLBACK,
        "Prepare repair and rollback before release",
        [
            "Document how to isolate power, immobilize the machine, restore firmware/configuration, replace modules, and recover the previous project revision.",
            "Record spare parts, known failure modes, connector access, calibration restoration, and post-repair verification scope.",
            "Practice the safe-state and data-recovery procedure before depending on the robot in the field.",
        ],
        target_ids=[project.project_id],
        prerequisite_step_ids=[regression.step_id],
        required_inputs=["known-good revision", "safe-state procedure", "replacement mapping", "backup and restore method"],
        evidence_to_capture=["rollback rehearsal", "restored hashes", "post-repair test results"],
        acceptance_criteria={"safe_state_reachable": True, "known_good_revision_restorable": True},
        rollback=["Keep the system out of service until rollback and repair are demonstrably reliable."],
    )

    release = _step(
        steps,
        GuidePhase.RELEASE,
        "Perform scoped human release review",
        [
            "Review requirements, source conflicts, quantitative findings, unresolved interfaces, build/flash lineage, calibration, bench evidence, regression results, and operating limitations.",
            "Authorize only the tested hardware revision, software/firmware hashes, configuration, payload, environment, speed, runtime, and mission envelope.",
            "Any material change or failure opens a new revision and invalidates affected authority until regression closes.",
        ],
        target_ids=[project.project_id],
        prerequisite_step_ids=[rollback.step_id],
        required_inputs=["complete evidence package", "closed blockers", "scoped operating envelope", "human reviewer"],
        evidence_to_capture=["release decision", "authorized hashes/revisions", "limitations", "reviewer identity and date"],
        acceptance_criteria={"blocking_findings": 0, "physical_evidence_reviewed": True, "scope_explicit": True},
        rollback=["Do not release; return to the earliest failed or unresolved phase."],
    )

    next_step_id = next((row.step_id for row in steps if row.blocking), None)
    return RobotOperatorGuide(
        project_id=project.project_id,
        robot_genre=topology.robot_genre,
        mode=change_impact.mode,
        steps=steps,
        current_blockers=list(dict.fromkeys(blockers)),
        next_step_id=next_step_id,
        metadata={
            "candidate_only": True,
            "guide_authority": AuthorityState.PROPOSED.value,
            "step_count": len(steps),
            "physical_validation_required": True,
            "fabrication_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        },
    )
