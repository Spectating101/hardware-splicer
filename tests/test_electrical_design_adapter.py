from __future__ import annotations

from hardware_splicer.electrical_design_adapter import electrical_design_from_machine_project
from hardware_splicer.machine_project import (
    AuthorityState,
    Component,
    Domain,
    Interface,
    InterfaceContract,
    InterfaceEndpoint,
    MachineProject,
    PartIdentity,
    Subsystem,
)


def machine() -> MachineProject:
    return MachineProject(
        project_id="robot",
        name="Inspection robot",
        purpose="Inspect a building",
        subsystems=[
            Subsystem(
                subsystem_id="electrical",
                name="Electrical",
                domain=Domain.ELECTRICAL,
                component_ids=["battery", "controller"],
                interface_ids=["battery-power", "unknown-link"],
            )
        ],
        components=[
            Component(
                component_id="battery",
                name="Battery",
                domain=Domain.ELECTRICAL,
                subsystem_id="electrical",
                part=PartIdentity(symbol_ref="Battery", footprint_ref="Battery:Pack"),
                authority=AuthorityState.DECLARED,
                metadata={
                    "reference": "BT1",
                    "electrical_pins": [
                        {
                            "number": "1",
                            "name": "POS",
                            "electrical_type": "power_out",
                            "voltage_min_v": 11.0,
                            "voltage_max_v": 12.6,
                            "max_current_a": 3.0,
                        },
                        {
                            "number": "2",
                            "name": "NEG",
                            "electrical_type": "power_out",
                        },
                    ],
                },
            ),
            Component(
                component_id="controller",
                name="Controller",
                domain=Domain.FIRMWARE,
                subsystem_id="electrical",
                part=PartIdentity(symbol_ref="MCU", footprint_ref="Package:QFN"),
                authority=AuthorityState.DECLARED,
                metadata={
                    "reference": "U1",
                    "electrical_pins": [
                        {
                            "number": "1",
                            "name": "VIN",
                            "electrical_type": "power_in",
                            "required": True,
                            "voltage_min_v": 9.0,
                            "voltage_max_v": 14.0,
                        }
                    ],
                },
            ),
        ],
        interfaces=[
            Interface(
                interface_id="battery-power",
                name="Battery power",
                kind="power",
                endpoints=[
                    InterfaceEndpoint(object_id="battery", port="POS"),
                    InterfaceEndpoint(object_id="controller", port="VIN"),
                ],
                contracts=[
                    InterfaceContract(
                        contract_type="electrical",
                        values={"nominal_voltage_v": 12.0, "peak_current_a": 2.0},
                        authority=AuthorityState.DECLARED,
                    )
                ],
                authority=AuthorityState.DECLARED,
            ),
            Interface(
                interface_id="unknown-link",
                name="Unknown donor harness",
                kind="signal",
                endpoints=[
                    InterfaceEndpoint(object_id="controller", port="GPIO18"),
                    InterfaceEndpoint(object_id="electrical", port="J3"),
                ],
                contracts=[
                    InterfaceContract(
                        contract_type="electrical",
                        unresolved_fields=["pin_mapping", "voltage_domain"],
                        authority=AuthorityState.UNKNOWN,
                    )
                ],
                authority=AuthorityState.VERIFIED,
            ),
        ],
    )


def test_projection_binds_only_exact_declared_pins() -> None:
    design = electrical_design_from_machine_project(machine())

    assert {row.component_id for row in design.components} == {"battery", "controller"}
    assert {row.reference for row in design.components} == {"BT1", "U1"}
    power = next(row for row in design.nets if row.net_id == "battery-power")
    assert power.pin_ids == ["battery:1", "controller:1"]
    assert power.voltage_min_v == 12.0
    assert power.voltage_max_v == 12.0
    assert power.peak_current_a == 2.0
    assert not power.unresolved_fields
    assert next(row for row in design.pins if row.pin_id == "battery:1").net_id == "battery-power"


def test_projection_keeps_unknown_endpoints_visible_and_downgrades_authority() -> None:
    design = electrical_design_from_machine_project(machine())
    unknown = next(row for row in design.nets if row.net_id == "unknown-link")

    assert unknown.pin_ids == []
    assert {
        "pin_mapping",
        "voltage_domain",
        "pin_mapping:controller:GPIO18",
        "endpoint_binding:electrical:J3",
    } <= set(unknown.unresolved_fields)
    assert unknown.authority == AuthorityState.DECLARED
    assert unknown.metadata["source_authority"] == "verified"
    assert unknown.metadata["authority_downgraded_for_unresolved"] is True
    assert "unresolved_net" in {issue.code for issue in design.erc_issues()}


def test_projection_does_not_invent_components_without_electrical_identity() -> None:
    project = machine()
    body = project.model_dump(mode="json")
    body["components"].append(
        {
            "component_id": "wheel",
            "name": "Wheel",
            "domain": "mechanical",
            "subsystem_id": "electrical",
            "source": "donor",
        }
    )
    body["subsystems"][0]["component_ids"].append("wheel")
    design = electrical_design_from_machine_project(MachineProject.model_validate(body))

    assert "wheel" not in {row.component_id for row in design.components}
