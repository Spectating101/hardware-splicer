from __future__ import annotations

from hardware_splicer.machine_project import (
    AuthorityState,
    Component,
    ComponentSource,
    Domain,
    EvidenceRef,
    Interface,
    InterfaceContract,
    InterfaceEndpoint,
    MachineProject,
    Requirement,
    RequirementKind,
    Subsystem,
)
from hardware_splicer.machine_project_diff import ChangeType, diff_machine_projects


def base_project() -> MachineProject:
    return MachineProject(
        project_id="inspection-robot",
        name="Inspection robot",
        purpose="Inspect the workshop.",
        requirements=[
            Requirement(
                requirement_id="req-estop",
                statement="The machine shall stop on emergency stop.",
                kind=RequirementKind.SAFETY,
            )
        ],
        subsystems=[
            Subsystem(
                subsystem_id="drive-system",
                name="Drive system",
                domain=Domain.MECHANICAL,
                component_ids=["motor-driver"],
                interface_ids=["motor-command"],
            )
        ],
        components=[
            Component(
                component_id="motor-driver",
                name="Motor driver",
                domain=Domain.ELECTRICAL,
                subsystem_id="drive-system",
                source=ComponentSource.NEW,
                authority=AuthorityState.PROPOSED,
                metadata={"editor_note": "draft"},
            )
        ],
        interfaces=[
            Interface(
                interface_id="motor-command",
                name="Motor command",
                kind="control",
                endpoints=[
                    InterfaceEndpoint(object_id="drive-system", port="controller"),
                    InterfaceEndpoint(object_id="motor-driver", port="enable"),
                ],
                contracts=[
                    InterfaceContract(
                        contract_type="electrical",
                        unresolved_fields=["logic_voltage"],
                        authority=AuthorityState.UNKNOWN,
                    )
                ],
                authority=AuthorityState.UNKNOWN,
            )
        ],
    )


def candidate_project() -> MachineProject:
    return MachineProject(
        project_id="inspection-robot",
        name="Inspection robot",
        purpose="Inspect the workshop and record environmental data.",
        subsystems=[
            Subsystem(
                subsystem_id="drive-system",
                name="Drive system",
                domain=Domain.MECHANICAL,
                component_ids=["motor-driver"],
                interface_ids=["motor-command"],
            )
        ],
        components=[
            Component(
                component_id="motor-driver",
                name="Motor driver",
                domain=Domain.ELECTRICAL,
                subsystem_id="drive-system",
                source=ComponentSource.NEW,
                authority=AuthorityState.VERIFIED,
                metadata={"editor_note": "reviewed"},
            )
        ],
        interfaces=[
            Interface(
                interface_id="motor-command",
                name="Motor command",
                kind="control",
                endpoints=[
                    InterfaceEndpoint(object_id="drive-system", port="controller"),
                    InterfaceEndpoint(object_id="motor-driver", port="enable"),
                ],
                contracts=[
                    InterfaceContract(
                        contract_type="electrical",
                        values={"logic_voltage_v": 3.3},
                        unresolved_fields=[],
                        authority=AuthorityState.VERIFIED,
                    )
                ],
                authority=AuthorityState.VERIFIED,
            )
        ],
        evidence=[
            EvidenceRef(
                evidence_id="evidence-logic-level",
                kind="instrument_measurement",
                basis="oscilloscope",
                supports=["motor-command"],
                authority=AuthorityState.MEASURED,
            )
        ],
    )


def change_map(diff):
    return {(row.collection, row.object_id): row for row in diff.object_changes}


def test_semantic_diff_tracks_identity_and_field_changes() -> None:
    diff = diff_machine_projects(base_project(), candidate_project())
    changes = change_map(diff)

    assert diff.project_changes[0].path == "purpose"
    assert changes[("requirements", "req-estop")].change_type == ChangeType.REMOVED
    assert changes[("components", "motor-driver")].change_type == ChangeType.MODIFIED
    assert changes[("interfaces", "motor-command")].change_type == ChangeType.MODIFIED
    assert changes[("evidence", "evidence-logic-level")].change_type == ChangeType.ADDED
    assert diff.summary() == {
        "added": 1,
        "removed": 1,
        "modified": 2,
        "project_fields_changed": 1,
        "review_required": True,
    }


def test_diff_requires_review_for_safety_removal_and_authority_escalation() -> None:
    diff = diff_machine_projects(base_project(), candidate_project())
    changes = change_map(diff)

    safety_flags = {flag.code for flag in changes[("requirements", "req-estop")].review_flags}
    component_flags = {flag.code for flag in changes[("components", "motor-driver")].review_flags}
    interface_flags = {flag.code for flag in changes[("interfaces", "motor-command")].review_flags}
    evidence_flags = {flag.code for flag in changes[("evidence", "evidence-logic-level")].review_flags}

    assert "safety_requirement_removed" in safety_flags
    assert "authority_escalation" in component_flags
    assert "authority_escalation" in interface_flags
    assert "trusted_object_added" in evidence_flags
    assert diff.review_required is True


def test_metadata_noise_is_ignored_unless_requested() -> None:
    original = base_project()
    changed = original.model_copy(deep=True)
    changed.components[0].metadata["editor_note"] = "changed only in metadata"

    quiet = diff_machine_projects(original, changed)
    verbose = diff_machine_projects(original, changed, include_metadata=True)

    assert quiet.object_changes == []
    assert len(verbose.object_changes) == 1
    assert verbose.object_changes[0].field_changes[0].path == "metadata.editor_note"


def test_authority_regression_is_visible_but_not_automatically_required() -> None:
    verified = candidate_project()
    proposed = verified.model_copy(deep=True)
    proposed.components[0].authority = AuthorityState.PROPOSED

    diff = diff_machine_projects(verified, proposed)
    component = change_map(diff)[("components", "motor-driver")]

    assert {flag.code for flag in component.review_flags} == {"authority_regression"}
    assert component.review_required is False
