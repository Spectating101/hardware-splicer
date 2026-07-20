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


def test_upsert_and_allocate_requirement_updates_both_sides() -> None:
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
    drive = next(row for row in candidate.subsystems if row.subsystem_id == "drive")
    control = next(row for row in candidate.subsystems if row.subsystem_id == "control")
    assert runtime.allocated_to == ["drive"]
    assert runtime.authority == AuthorityState.DECLARED
    assert drive.requirement_ids == ["req-runtime"]
    assert control.requirement_ids == ["req-safe"]


def test_component_membership_moves_with_component() -> None:
    candidate = apply_machine_edits(
        project(),
        [
            {
                "type": "upsert_component",
                "payload": {
                    "component_id": "controller",
                    "name": "Controller",
                    "domain": "firmware",
                    "subsystem_id": "control",
                },
            },
            {
                "type": "upsert_component",
                "payload": {
                    "component_id": "controller",
                    "subsystem_id": "drive",
                    "domain": "firmware",
                },
            },
        ],
    )

    control = next(row for row in candidate.subsystems if row.subsystem_id == "control")
    drive = next(row for row in candidate.subsystems if row.subsystem_id == "drive")
    controller = next(row for row in candidate.components if row.component_id == "controller")
    assert controller.subsystem_id == "drive"
    assert "controller" not in control.component_ids
    assert drive.component_ids == ["controller"]


def test_new_interface_attaches_to_endpoint_subsystems() -> None:
    candidate = apply_machine_edits(
        project(),
        [
            {
                "type": "upsert_interface",
                "payload": {
                    "interface_id": "power-link",
                    "name": "Power link",
                    "kind": "power",
                    "endpoints": [
                        {"object_id": "control", "port": "vin"},
                        {"object_id": "drive", "port": "power"},
                    ],
                    "contracts": [
                        {
                            "contract_type": "electrical",
                            "values": {"nominal_voltage_v": 12},
                            "unresolved_fields": ["peak_current_a"],
                            "authority": "declared",
                        }
                    ],
                },
            }
        ],
    )

    assert {row.interface_id for row in candidate.interfaces} == {"control-link", "power-link"}
    assert all(
        "power-link" in row.interface_ids
        for row in candidate.subsystems
        if row.subsystem_id in {"control", "drive"}
    )


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
    with pytest.raises(MachineEditError, match="unknown component subsystem"):
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
