from __future__ import annotations

import pytest
from pydantic import ValidationError

from hardware_splicer.machine_project import (
    AuthorityState,
    Component,
    ComponentSource,
    Constraint,
    Domain,
    EvidenceRef,
    Function,
    Interface,
    InterfaceContract,
    InterfaceEndpoint,
    MachineProject,
    ReleaseState,
    Requirement,
    RequirementKind,
    Subsystem,
    VerificationMethod,
    VerificationStatus,
    VerificationType,
    machine_project_from_session,
)


def inspection_robot_project() -> MachineProject:
    requirements = [
        Requirement(
            requirement_id="req-runtime",
            statement="The robot shall inspect continuously for 90 minutes.",
            kind=RequirementKind.PERFORMANCE,
            allocated_to=["power-system"],
            verification_method_ids=["verify-runtime"],
        ),
        Requirement(
            requirement_id="req-safe-start",
            statement="The drivetrain shall remain disabled until commanded motion is authorized.",
            kind=RequirementKind.SAFETY,
            allocated_to=["drive-system", "motor-command"],
            verification_method_ids=["verify-safe-start"],
        ),
    ]
    functions = [
        Function(
            function_id="function-move",
            name="Move through inspection area",
            allocated_subsystem_ids=["drive-system"],
            requirement_ids=["req-safe-start"],
        )
    ]
    subsystems = [
        Subsystem(
            subsystem_id="power-system",
            name="Power system",
            domain=Domain.ELECTRICAL,
            requirement_ids=["req-runtime"],
            component_ids=["battery"],
            interface_ids=["motor-power"],
        ),
        Subsystem(
            subsystem_id="drive-system",
            name="Drivetrain",
            domain=Domain.MECHANICAL,
            requirement_ids=["req-safe-start"],
            function_ids=["function-move"],
            component_ids=["motor-driver", "left-motor"],
            interface_ids=["motor-power", "motor-command"],
        ),
        Subsystem(
            subsystem_id="control-system",
            name="Control system",
            domain=Domain.FIRMWARE,
            component_ids=["controller"],
            interface_ids=["motor-command"],
        ),
    ]
    components = [
        Component(
            component_id="battery",
            name="Battery pack",
            domain=Domain.ELECTRICAL,
            subsystem_id="power-system",
            source=ComponentSource.NEW,
            requirement_ids=["req-runtime"],
        ),
        Component(
            component_id="motor-driver",
            name="Motor driver",
            domain=Domain.ELECTRICAL,
            subsystem_id="drive-system",
            source=ComponentSource.NEW,
            requirement_ids=["req-safe-start"],
        ),
        Component(
            component_id="left-motor",
            name="Left motor",
            domain=Domain.MECHANICAL,
            subsystem_id="drive-system",
            source=ComponentSource.DONOR,
        ),
        Component(
            component_id="controller",
            name="Robot controller",
            domain=Domain.FIRMWARE,
            subsystem_id="control-system",
            source=ComponentSource.GENERATED,
        ),
    ]
    interfaces = [
        Interface(
            interface_id="motor-power",
            name="Battery to motor power",
            kind="power",
            endpoints=[
                InterfaceEndpoint(object_id="battery", port="output"),
                InterfaceEndpoint(object_id="motor-driver", port="vmotor"),
            ],
            contracts=[
                InterfaceContract(
                    contract_type="electrical",
                    values={"nominal_voltage_v": 12, "peak_current_a": 8},
                    authority=AuthorityState.DECLARED,
                )
            ],
        ),
        Interface(
            interface_id="motor-command",
            name="Controller motor command",
            kind="control",
            endpoints=[
                InterfaceEndpoint(object_id="controller", port="pwm"),
                InterfaceEndpoint(object_id="motor-driver", port="enable"),
            ],
            requirement_ids=["req-safe-start"],
            verification_method_ids=["verify-safe-start"],
            contracts=[
                InterfaceContract(
                    contract_type="electrical",
                    values={"logic_voltage_v": 3.3, "direction": "controller_to_driver"},
                    authority=AuthorityState.VERIFIED,
                )
            ],
            authority=AuthorityState.VERIFIED,
        ),
    ]
    constraints = [
        Constraint(
            constraint_id="constraint-current",
            name="Motor current rating",
            domain=Domain.ELECTRICAL,
            statement="The motor power path shall support 8 A peak current.",
            applies_to=["motor-power", "motor-driver"],
            source_requirement_ids=["req-runtime"],
            verification_method_ids=["verify-runtime"],
        )
    ]
    evidence = [
        EvidenceRef(
            evidence_id="evidence-runtime",
            kind="bench_test",
            basis="instrument",
            supports=["req-runtime", "battery"],
            authority=AuthorityState.MEASURED,
        ),
        EvidenceRef(
            evidence_id="evidence-safe-start",
            kind="hardware_in_loop_test",
            basis="test_result",
            supports=["req-safe-start", "motor-command"],
            authority=AuthorityState.VERIFIED,
        ),
    ]
    verifications = [
        VerificationMethod(
            verification_id="verify-runtime",
            name="Runtime load test",
            method_type=VerificationType.TEST,
            status=VerificationStatus.PASSED,
            requirement_ids=["req-runtime"],
            target_ids=["power-system", "battery"],
            evidence_ids=["evidence-runtime"],
        ),
        VerificationMethod(
            verification_id="verify-safe-start",
            name="Safe-start hardware-in-loop test",
            method_type=VerificationType.TEST,
            status=VerificationStatus.PASSED,
            requirement_ids=["req-safe-start"],
            target_ids=["drive-system", "motor-command"],
            evidence_ids=["evidence-safe-start"],
        ),
    ]
    return MachineProject(
        project_id="inspection-robot",
        name="Mobile inspection robot",
        purpose="Inspect a building while carrying environmental and visual sensors.",
        requested_release_state=ReleaseState.OPERATIONALLY_AUTHORIZED,
        requirements=requirements,
        functions=functions,
        subsystems=subsystems,
        components=components,
        interfaces=interfaces,
        constraints=constraints,
        verifications=verifications,
        evidence=evidence,
    )


def test_complete_machine_project_has_cross_discipline_traceability() -> None:
    project = inspection_robot_project()

    assert project.traceability_issues() == []
    assessment = project.assess_release()
    assert assessment.allowed is True
    assert assessment.achieved_state == ReleaseState.OPERATIONALLY_AUTHORIZED


def test_unknown_references_are_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown object"):
        MachineProject(
            project_id="broken",
            name="Broken machine",
            purpose="Prove reference validation.",
            subsystems=[
                Subsystem(
                    subsystem_id="control",
                    name="Control",
                    domain=Domain.FIRMWARE,
                    component_ids=["missing-controller"],
                )
            ],
        )


def test_ids_are_globally_unique_across_disciplines() -> None:
    with pytest.raises(ValidationError, match="used by both"):
        MachineProject(
            project_id="duplicate-test",
            name="Duplicate test",
            purpose="Prove global identifiers.",
            requirements=[Requirement(requirement_id="shared-id", statement="A requirement")],
            subsystems=[Subsystem(subsystem_id="shared-id", name="Subsystem", domain=Domain.SYSTEM)],
        )


def test_unresolved_interface_cannot_claim_verified_authority() -> None:
    with pytest.raises(ValidationError, match="unresolved"):
        Interface(
            interface_id="donor-harness",
            name="Unknown donor harness",
            kind="electrical",
            endpoints=[
                InterfaceEndpoint(object_id="source", port="J1"),
                InterfaceEndpoint(object_id="target", port="J2"),
            ],
            contracts=[
                InterfaceContract(
                    contract_type="electrical",
                    unresolved_fields=["pin_mapping"],
                    authority=AuthorityState.UNKNOWN,
                )
            ],
            authority=AuthorityState.VERIFIED,
        )


def test_simulated_evidence_cannot_become_physical_measurement() -> None:
    with pytest.raises(ValidationError, match="simulated evidence"):
        EvidenceRef(
            evidence_id="simulation",
            kind="digital_twin",
            basis="simulation",
            simulated=True,
            authority=AuthorityState.MEASURED,
        )


def test_passed_verification_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="must reference evidence"):
        VerificationMethod(
            verification_id="empty-pass",
            name="Empty pass",
            method_type=VerificationType.TEST,
            status=VerificationStatus.PASSED,
        )


def test_legacy_session_migration_preserves_source_without_authority_upgrade() -> None:
    session = {
        "projectId": "robot-drive",
        "projectName": "Robot drive",
        "goal": "Reuse a donor motor stage in a mobile robot",
        "mode": "salvage",
        "currentStage": "verify",
        "graph": {
            "phrase": "robot drive",
            "nodes": [
                {"id": "controller", "data": {"label": "ESP32"}},
                {"id": "donor-driver", "data": {"label": "Donor motor driver"}},
            ],
            "edges": [
                {
                    "id": "control-link",
                    "source": "controller",
                    "target": "donor-driver",
                    "sourceHandle": "gpio18",
                }
            ],
        },
        "buildDir": "/tmp/robot-build",
        "benchSession": {"power_on_authorized": True},
    }

    project = machine_project_from_session(session)

    assert project.project_id == "robot-drive"
    assert project.lifecycle_state.value == "verify"
    assert project.discipline_payloads["splice_session"]["benchSession"]["power_on_authorized"] is True
    assert project.metadata["authority_preserved_without_upgrade"] is True
    assert all(component.authority == AuthorityState.PROPOSED for component in project.components)
    assert project.interfaces[0].authority == AuthorityState.UNKNOWN
    assert project.interfaces[0].contracts[0].unresolved_fields == [
        "pin_mapping",
        "voltage_domain",
        "direction",
    ]
    assert project.artifacts[0].ref == "/tmp/robot-build"


def test_release_assessment_blocks_unclosed_safety_requirement() -> None:
    project = MachineProject(
        project_id="unsafe-machine",
        name="Unsafe machine",
        purpose="Exercise release blockers.",
        requested_release_state=ReleaseState.BUILD_READY,
        requirements=[
            Requirement(
                requirement_id="req-estop",
                statement="The machine shall stop when emergency stop is pressed.",
                kind=RequirementKind.SAFETY,
            )
        ],
    )

    assessment = project.assess_release()

    assert assessment.allowed is False
    assert {blocker.code for blocker in assessment.blockers} >= {
        "unverified_requirement",
        "safety_not_closed",
        "release_state_not_reached",
    }
