"""Projection of existing HardwareCompileSpec-shaped payloads into MachineProject.

The adapter preserves the full legacy compile payload and exposes its major
cross-discipline objects for traceability. It does not infer electrical or
mechanical interfaces, and release documents are represented as reviewed
artifacts rather than automatic operational authorization.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from .machine_project import (
    ArtifactRef,
    AuthorityState,
    Component,
    ComponentSource,
    Constraint,
    Domain,
    EvidenceRef,
    Function,
    LifecycleState,
    MachineProject,
    Requirement,
    RequirementKind,
    Subsystem,
    VerificationMethod,
    VerificationStatus,
    VerificationType,
)


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(row) for row in value if str(row).strip()] if isinstance(value, list) else []


def _slug(value: str, fallback: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-._")
    return slug[:96] or fallback


def _status_passed(value: Any) -> bool:
    return str(value or "").lower() in {"pass", "passed", "verified", "complete", "completed", "mitigated"}


def _purpose(spec: Mapping[str, Any]) -> str:
    machine = _dict(spec.get("machine"))
    robotics = _dict(spec.get("robotics_project"))
    mission = _strings(robotics.get("mission"))
    return str(
        machine.get("design_intent")
        or robotics.get("purpose")
        or (mission[0] if mission else "")
        or spec.get("goal")
        or spec.get("project_name")
        or machine.get("machine_name")
        or "Hardware Splicer machine project"
    ).strip()


def _component(
    *,
    component_id: str,
    name: str,
    domain: Domain,
    subsystem_id: str,
    role: str,
    metadata: Mapping[str, Any],
) -> Component:
    return Component(
        component_id=component_id,
        name=name,
        domain=domain,
        subsystem_id=subsystem_id,
        role=role,
        source=ComponentSource.EXTERNAL,
        authority=AuthorityState.DECLARED,
        metadata=dict(metadata),
    )


def _capture_rows(capture: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, value in capture.items():
        if key == "artifact_uris":
            continue
        rows.extend(_rows(value))
    return rows


def _capture_verification(
    *,
    capture_name: str,
    capture: Mapping[str, Any],
    target_id: str,
    evidence_authority: AuthorityState,
) -> tuple[EvidenceRef | None, VerificationMethod | None, list[ArtifactRef]]:
    if not capture:
        return None, None, []
    capture_id = _slug(capture_name, "capture")
    rows = _capture_rows(capture)
    artifact_uris = _strings(capture.get("artifact_uris"))
    passed = bool(rows) and all(_status_passed(row.get("status")) for row in rows)
    evidence_id = f"evidence-{capture_id}"
    evidence = EvidenceRef(
        evidence_id=evidence_id,
        kind=capture_name,
        basis="captured_result",
        ref=artifact_uris[0] if artifact_uris else None,
        supports=[target_id],
        authority=evidence_authority if passed else AuthorityState.OBSERVED,
        simulated=False,
        metadata={"capture": dict(capture)},
    )
    verification = VerificationMethod(
        verification_id=f"verify-{capture_id}",
        name=capture_name.replace("_", " ").title(),
        method_type=VerificationType.TEST,
        status=VerificationStatus.PASSED if passed else VerificationStatus.BLOCKED,
        target_ids=[target_id],
        evidence_ids=[evidence_id] if passed else [],
        procedure="Imported from an existing Hardware Splicer capture packet.",
        acceptance_criteria={"all_reported_statuses": "pass_or_verified"},
        authority=AuthorityState.VERIFIED if passed else AuthorityState.OBSERVED,
        metadata={"capture_name": capture_name},
    )
    artifacts = [
        ArtifactRef(
            artifact_id=f"artifact-{capture_id}-{index + 1}",
            kind=capture_name,
            ref=uri,
            authority=evidence_authority if passed else AuthorityState.OBSERVED,
        )
        for index, uri in enumerate(artifact_uris)
    ]
    return evidence, verification, artifacts


def machine_project_from_compile_spec(spec: Mapping[str, Any]) -> MachineProject:
    body = dict(spec or {})
    machine = _dict(body.get("machine"))
    mechanism = _dict(body.get("mechanism"))
    robotics_project = _dict(body.get("robotics_project"))
    robotics_actuation = _dict(body.get("robotics_actuation"))
    control_stack = _dict(body.get("control_stack"))
    safety_case = _dict(body.get("safety_case"))
    board_design_files = _dict(body.get("board_design_files"))

    project_name = str(body.get("project_name") or machine.get("machine_name") or "machine-project")
    project_id = _slug(project_name, "machine-project")
    purpose = _purpose(body)

    subsystem_specs: dict[str, tuple[str, Domain, str]] = {
        "system": ("Machine system", Domain.SYSTEM, purpose),
    }
    boards = _rows(machine.get("boards"))
    if boards or board_design_files:
        subsystem_specs["electrical-system"] = (
            "Electrical and PCB system",
            Domain.ELECTRICAL,
            "Boards, power architecture, interconnect, and electrical implementation.",
        )
    if mechanism:
        subsystem_specs["mechanical-system"] = (
            "Mechanical system",
            Domain.MECHANICAL,
            "Structure, enclosure, motion geometry, and physical integration.",
        )
    if robotics_project or robotics_actuation:
        subsystem_specs["robotics-system"] = (
            "Robotics and actuation",
            Domain.MECHANICAL,
            "Platform motion, actuators, sensors, and mission behavior.",
        )
    if control_stack:
        subsystem_specs["firmware-control"] = (
            "Firmware and control",
            Domain.FIRMWARE,
            "Controllers, loops, communications, and failsafes.",
        )
    capture_names = (
        "mechanical_measurement_capture",
        "mechanical_bench_capture",
        "robotics_bench_capture",
        "integrated_bench_capture",
        "field_validation",
    )
    if any(_dict(body.get(name)) for name in capture_names):
        subsystem_specs["verification-system"] = (
            "Verification and evidence",
            Domain.VERIFICATION,
            "Measurements, bench tests, field validation, and release evidence.",
        )

    requirements: list[Requirement] = [
        Requirement(
            requirement_id="req-primary-purpose",
            statement=purpose,
            kind=RequirementKind.FUNCTIONAL,
            allocated_to=["system"],
            authority=AuthorityState.DECLARED,
        )
    ]
    safety_requirement_ids: list[str] = []
    for index, hazard in enumerate(_rows(safety_case.get("hazards"))):
        hazard_id = _slug(str(hazard.get("id") or hazard.get("name") or f"hazard-{index + 1}"), f"hazard-{index + 1}")
        requirement_id = f"req-safety-{hazard_id}"
        safety_requirement_ids.append(requirement_id)
        mitigation = str(hazard.get("mitigation") or "must be mitigated")
        requirements.append(
            Requirement(
                requirement_id=requirement_id,
                statement=f"Hazard {hazard_id} shall be controlled: {mitigation}.",
                kind=RequirementKind.SAFETY,
                allocated_to=["robotics-system" if "robotics-system" in subsystem_specs else "system"],
                authority=AuthorityState.DECLARED,
                metadata={"safety_case_hazard": hazard},
            )
        )

    components: list[Component] = []
    component_ids_by_subsystem: dict[str, list[str]] = {}

    for index, board in enumerate(boards):
        board_id = _slug(str(board.get("board_id") or f"board-{index + 1}"), f"board-{index + 1}")
        component_id = f"board-{board_id}"
        components.append(
            _component(
                component_id=component_id,
                name=str(board.get("name") or board.get("board_id") or component_id),
                domain=Domain.ELECTRICAL,
                subsystem_id="electrical-system",
                role="PCB assembly",
                metadata=board,
            )
        )
        component_ids_by_subsystem.setdefault("electrical-system", []).append(component_id)

    mechanism_keys = (
        "enclosure",
        "bracket",
        "servo_mount",
        "linear_axis",
        "leadscrew_axis",
        "rotary_joint",
        "belt_reduction",
        "drive_base",
        "gripper",
        "pan_tilt",
        "assembly",
    )
    for key in mechanism_keys:
        row = _dict(mechanism.get(key))
        if not row:
            continue
        component_id = f"mechanism-{_slug(str(row.get('name') or key), key)}"
        components.append(
            _component(
                component_id=component_id,
                name=str(row.get("name") or key.replace("_", " ").title()),
                domain=Domain.MECHANICAL,
                subsystem_id="mechanical-system",
                role=key,
                metadata=row,
            )
        )
        component_ids_by_subsystem.setdefault("mechanical-system", []).append(component_id)

    for index, actuator in enumerate(_rows(robotics_actuation.get("actuators"))):
        actuator_id = _slug(str(actuator.get("id") or f"actuator-{index + 1}"), f"actuator-{index + 1}")
        component_id = f"actuator-{actuator_id}"
        components.append(
            _component(
                component_id=component_id,
                name=str(actuator.get("name") or actuator.get("role") or actuator_id),
                domain=Domain.MECHANICAL,
                subsystem_id="robotics-system",
                role=str(actuator.get("type") or "actuator"),
                metadata=actuator,
            )
        )
        component_ids_by_subsystem.setdefault("robotics-system", []).append(component_id)

    for index, sensor in enumerate(_rows(robotics_actuation.get("sensors"))):
        sensor_id = _slug(str(sensor.get("id") or f"sensor-{index + 1}"), f"sensor-{index + 1}")
        component_id = f"sensor-{sensor_id}"
        components.append(
            _component(
                component_id=component_id,
                name=str(sensor.get("name") or sensor.get("role") or sensor_id),
                domain=Domain.ELECTRICAL,
                subsystem_id="robotics-system",
                role=str(sensor.get("type") or "sensor"),
                metadata=sensor,
            )
        )
        component_ids_by_subsystem.setdefault("robotics-system", []).append(component_id)

    for index, controller in enumerate(_rows(control_stack.get("controllers"))):
        controller_id = _slug(str(controller.get("id") or f"controller-{index + 1}"), f"controller-{index + 1}")
        component_id = f"firmware-{controller_id}"
        components.append(
            _component(
                component_id=component_id,
                name=str(controller.get("firmware") or controller_id),
                domain=Domain.FIRMWARE,
                subsystem_id="firmware-control",
                role="embedded control firmware",
                metadata=controller,
            )
        )
        component_ids_by_subsystem.setdefault("firmware-control", []).append(component_id)

    constraints: list[Constraint] = []
    robotics_constraints = _dict(robotics_project.get("constraints"))
    for index, (key, value) in enumerate(sorted(robotics_constraints.items())):
        constraint_id = f"constraint-robotics-{_slug(str(key), str(index + 1))}"
        constraints.append(
            Constraint(
                constraint_id=constraint_id,
                name=str(key).replace("_", " ").title(),
                domain=Domain.SYSTEM,
                statement=f"{str(key).replace('_', ' ')} shall be {value}.",
                applies_to=["robotics-system" if "robotics-system" in subsystem_specs else "system"],
                authority=AuthorityState.DECLARED,
                metadata={"raw_value": value, "source": "robotics_project.constraints"},
            )
        )

    subsystems: list[Subsystem] = []
    child_ids = [value for value in subsystem_specs if value != "system"]
    for subsystem_id, (name, domain, subsystem_purpose) in subsystem_specs.items():
        subsystems.append(
            Subsystem(
                subsystem_id=subsystem_id,
                name=name,
                domain=domain,
                purpose=subsystem_purpose,
                parent_subsystem_id=None if subsystem_id == "system" else "system",
                requirement_ids=(
                    ["req-primary-purpose", *safety_requirement_ids]
                    if subsystem_id == "system"
                    else safety_requirement_ids if subsystem_id == "robotics-system" else []
                ),
                function_ids=["function-primary"] if subsystem_id == "system" else [],
                component_ids=component_ids_by_subsystem.get(subsystem_id, []),
                authority=AuthorityState.PROPOSED,
            )
        )

    functions = [
        Function(
            function_id="function-primary",
            name="Deliver machine mission",
            description=purpose,
            allocated_subsystem_ids=child_ids or ["system"],
            requirement_ids=["req-primary-purpose"],
            authority=AuthorityState.PROPOSED,
        )
    ]

    evidence: list[EvidenceRef] = []
    verifications: list[VerificationMethod] = []
    artifacts: list[ArtifactRef] = []
    capture_targets = {
        "mechanical_measurement_capture": ("mechanical-system", AuthorityState.MEASURED),
        "mechanical_bench_capture": ("mechanical-system", AuthorityState.VERIFIED),
        "robotics_bench_capture": ("robotics-system", AuthorityState.VERIFIED),
        "integrated_bench_capture": ("system", AuthorityState.VERIFIED),
        "field_validation": ("system", AuthorityState.VERIFIED),
    }
    for capture_name, (target_id, authority) in capture_targets.items():
        capture = _dict(body.get(capture_name))
        if not capture or target_id not in subsystem_specs:
            continue
        evidence_row, verification_row, artifact_rows = _capture_verification(
            capture_name=capture_name,
            capture=capture,
            target_id=target_id,
            evidence_authority=authority,
        )
        if evidence_row:
            evidence.append(evidence_row)
        if verification_row:
            verifications.append(verification_row)
        artifacts.extend(artifact_rows)

    for release_name in (
        "circuit_release",
        "mechanical_release",
        "robotics_release",
        "mechatronics_release",
        "robotics_project_release",
    ):
        release = _dict(body.get(release_name))
        if not release:
            continue
        reviewed = bool(release.get("acceptance_reviewed"))
        for index, uri in enumerate(_strings(release.get("artifact_uris"))):
            artifacts.append(
                ArtifactRef(
                    artifact_id=f"artifact-{_slug(release_name, 'release')}-{index + 1}",
                    kind=release_name,
                    ref=uri,
                    authority=AuthorityState.VERIFIED if reviewed else AuthorityState.DECLARED,
                    metadata={"scope_statement": release.get("scope_statement"), "acceptance_reviewed": reviewed},
                )
            )

    for board_id, board_file in board_design_files.items():
        row = _dict(board_file)
        ref = str(row.get("path") or "").strip()
        if ref:
            artifacts.append(
                ArtifactRef(
                    artifact_id=f"artifact-board-source-{_slug(str(board_id), 'board')}",
                    kind=str(row.get("kind") or "board_design_file"),
                    ref=ref,
                    authority=AuthorityState.DECLARED,
                    metadata={"board_id": board_id},
                )
            )

    return MachineProject(
        project_id=project_id,
        name=project_name.replace("_", " ").strip(),
        purpose=purpose,
        lifecycle_state=LifecycleState.ARCHITECTURE,
        requirements=requirements,
        functions=functions,
        subsystems=subsystems,
        components=components,
        constraints=constraints,
        verifications=verifications,
        evidence=evidence,
        artifacts=artifacts,
        discipline_payloads={"hardware_compile_spec": body},
        metadata={
            "adapter": "machine_project_from_compile_spec.v1",
            "interfaces_inferred": False,
            "release_documents_promote_authority": False,
            "authority_preserved_without_upgrade": True,
        },
    )
