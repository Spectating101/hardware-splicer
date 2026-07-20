from __future__ import annotations

import pytest

from hardware_splicer.machine_project import (
    AuthorityState,
    Domain,
    Interface,
    InterfaceContract,
    InterfaceEndpoint,
    MachineProject,
    Requirement,
    RequirementKind,
    Subsystem,
)
from hardware_splicer.machine_project_edit import MachineEditError, apply_machine_edits


def project() -> MachineProject:
    return MachineProject(
        project_id="robot",
        name="Inspection robot",
        purpose="Inspect a building",
        requirements=[
            Requirement(
                requirement_id="req-safe",
                statement="Motion shall remain disabled at startup.",
                kind=RequirementKind.SAFETY,
                allocated_to=["control"],
            )
        ],
        subsystems=[
            Subsystem(
                subsystem_id="control",
                name="Control",
                domain=Domain.FIRMWARE,
                requirement_ids=["req-safe"],
                interface_ids=["control-link"],
            ),
            Subsystem(
                subsystem_id="drive",
                name="Drive",
                domain=Domain.MECHANICAL,
                interface_ids=["control-link"],
            ),
        ],
        interfaces=[
            Interface(
                interface_id="control-link",
                name="Control link",
                kind="control",
                endpoints=[
                    InterfaceEndpoint(object_id="control", port="command"),
                    InterfaceEndpoint(object_id="drive", port="enable"),
                ],
                contracts=[
                    InterfaceContract(
                        contract_type="electrical",
                        values={"logic_voltage_v": 3.3},
                        unresolved_fields=["pin_mapping"],
                        authority=AuthorityState.DECLARED,
                    )
                ],
            )
        ],
    )


def test_upsert_and_allocate_requirement() -> None:
    candidate = apply_machine_edits(
        project(),
        [
            {
                "type": "upsert_requirement",
                "payload": {
                    "requirement_id": "req-runtime",
                    "statement": "The robot shall operate for 90 minutes.",
                    "kind": "performance",
                },
            },
            {
                "type": "allocate_requirement",
                "payload": {
                    "requirement_id": "req-runtime",
                    "allocated_to": ["drive"],
                },
            },
        ],
    )

    runtime = next(row for row in candidate.requirements if row.requirement_id == "req-runtime")
    assert runtime.allocated_to == ["drive"]
    assert runtime.authority == AuthorityState.DECLARED


def test_interface_contract_edit_closes_declared_fields_without_claiming_verification() -> None:
    candidate = apply_machine_edits(
        project(),
        [
            {
                "type": "update_interface_contract",
                "payload": {
                    "interface_id": "control-link",
                    "contract_type": "electrical",
                    "values": {"logic_voltage_v": 3.3, "pin_mapping": {"command": "GPIO18"}},
                    "unresolved_fields": [],
                    "authority": "declared",
                },
            }
        ],
    )

    contract = candidate.interfaces[0].contracts[0]
    assert contract.unresolved_fields == []
    assert contract.values["pin_mapping"]["command"] == "GPIO18"
    assert contract.authority == AuthorityState.DECLARED


def test_ordinary_authoring_cannot_assign_verified_authority() -> None:
    with pytest.raises(MachineEditError, match="require evidence workflows"):
        apply_machine_edits(
            project(),
            [
                {
                    "type": "update_interface_contract",
                    "payload": {
                        "interface_id": "control-link",
                        "contract_type": "electrical",
                        "unresolved_fields": [],
                        "authority": "verified",
                    },
                }
            ],
        )


def test_safety_requirement_removal_needs_confirmation_and_no_references() -> None:
    with pytest.raises(MachineEditError, match="confirm_safety_removal"):
        apply_machine_edits(
            project(),
            [{"type": "remove_requirement", "payload": {"requirement_id": "req-safe"}}],
        )

    with pytest.raises(MachineEditError, match="still referenced"):
        apply_machine_edits(
            project(),
            [
                {
                    "type": "remove_requirement",
                    "payload": {
                        "requirement_id": "req-safe",
                        "confirm_safety_removal": True,
                    },
                }
            ],
        )


def test_cross_domain_invariants_reject_dangling_component() -> None:
    with pytest.raises(MachineEditError, match="violates machine-project invariants"):
        apply_machine_edits(
            project(),
            [
                {
                    "type": "upsert_component",
                    "payload": {
                        "component_id": "ghost",
                        "name": "Ghost controller",
                        "domain": "firmware",
                        "subsystem_id": "missing",
                    },
                }
            ],
        )
