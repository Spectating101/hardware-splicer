from __future__ import annotations

import pytest
from pydantic import ValidationError

from hardware_splicer.electrical_design import (
    ElectricalComponent,
    ElectricalDesign,
    ElectricalNet,
    ElectricalPin,
    NetKind,
    PinElectricalType,
    PowerDomain,
)


def valid_design() -> ElectricalDesign:
    return ElectricalDesign(
        design_id="robot-electrical",
        project_id="robot",
        components=[
            ElectricalComponent(
                component_id="battery",
                reference="BT1",
                name="Battery",
                pin_ids=["battery-pos", "battery-neg"],
            ),
            ElectricalComponent(
                component_id="controller",
                reference="U1",
                name="Controller",
                pin_ids=["controller-vin", "controller-gnd", "controller-tx"],
            ),
            ElectricalComponent(
                component_id="radio",
                reference="U2",
                name="Radio",
                pin_ids=["radio-vin", "radio-gnd", "radio-rx"],
            ),
        ],
        pins=[
            ElectricalPin(
                pin_id="battery-pos",
                component_id="battery",
                number="1",
                name="+",
                electrical_type=PinElectricalType.POWER_OUT,
                net_id="vbat",
                voltage_min_v=11.0,
                voltage_max_v=12.6,
                max_current_a=3.0,
            ),
            ElectricalPin(
                pin_id="battery-neg",
                component_id="battery",
                number="2",
                name="-",
                electrical_type=PinElectricalType.POWER_OUT,
                net_id="gnd",
            ),
            ElectricalPin(
                pin_id="controller-vin",
                component_id="controller",
                number="1",
                name="VIN",
                electrical_type=PinElectricalType.POWER_IN,
                required=True,
                net_id="vbat",
                voltage_min_v=9.0,
                voltage_max_v=14.0,
            ),
            ElectricalPin(
                pin_id="controller-gnd",
                component_id="controller",
                number="2",
                name="GND",
                electrical_type=PinElectricalType.POWER_IN,
                required=True,
                net_id="gnd",
            ),
            ElectricalPin(
                pin_id="controller-tx",
                component_id="controller",
                number="3",
                name="TX",
                electrical_type=PinElectricalType.OUTPUT,
                net_id="uart-tx",
                voltage_min_v=0.0,
                voltage_max_v=3.3,
            ),
            ElectricalPin(
                pin_id="radio-vin",
                component_id="radio",
                number="1",
                name="VIN",
                electrical_type=PinElectricalType.POWER_IN,
                net_id="vbat",
                voltage_min_v=9.0,
                voltage_max_v=14.0,
            ),
            ElectricalPin(
                pin_id="radio-gnd",
                component_id="radio",
                number="2",
                name="GND",
                electrical_type=PinElectricalType.POWER_IN,
                net_id="gnd",
            ),
            ElectricalPin(
                pin_id="radio-rx",
                component_id="radio",
                number="3",
                name="RX",
                electrical_type=PinElectricalType.INPUT,
                net_id="uart-tx",
                voltage_min_v=0.0,
                voltage_max_v=3.3,
            ),
        ],
        nets=[
            ElectricalNet(
                net_id="vbat",
                name="VBAT",
                kind=NetKind.POWER,
                pin_ids=["battery-pos", "controller-vin", "radio-vin"],
                voltage_min_v=11.0,
                voltage_max_v=12.6,
                peak_current_a=2.0,
            ),
            ElectricalNet(
                net_id="gnd",
                name="GND",
                kind=NetKind.GROUND,
                pin_ids=["battery-neg", "controller-gnd", "radio-gnd"],
            ),
            ElectricalNet(
                net_id="uart-tx",
                name="UART_TX",
                kind=NetKind.SIGNAL,
                pin_ids=["controller-tx", "radio-rx"],
                voltage_min_v=0.0,
                voltage_max_v=3.3,
            ),
        ],
        power_domains=[
            PowerDomain(
                domain_id="battery-domain",
                name="Battery power",
                nominal_voltage_v=12.0,
                voltage_min_v=11.0,
                voltage_max_v=12.6,
                source_net_ids=["vbat"],
                return_net_id="gnd",
                component_ids=["battery", "controller", "radio"],
            )
        ],
    )


def test_valid_pin_net_power_design_passes_erc() -> None:
    design = valid_design()
    assert design.erc_issues() == []


def test_reference_and_membership_invariants_are_enforced() -> None:
    body = valid_design().model_dump(mode="json")
    body["components"][0]["pin_ids"].append("missing-pin")
    with pytest.raises(ValidationError, match="unknown pin"):
        ElectricalDesign.model_validate(body)

    body = valid_design().model_dump(mode="json")
    body["pins"][0]["net_id"] = "uart-tx"
    with pytest.raises(ValidationError, match="membership"):
        ElectricalDesign.model_validate(body)


def test_erc_detects_multiple_drivers_voltage_mismatch_and_current_overload() -> None:
    body = valid_design().model_dump(mode="json")
    body["pins"].append(
        {
            "pin_id": "radio-tx",
            "component_id": "radio",
            "number": "4",
            "name": "TX",
            "electrical_type": "output",
            "net_id": "uart-tx",
            "voltage_min_v": 4.5,
            "voltage_max_v": 5.0,
        }
    )
    body["components"][2]["pin_ids"].append("radio-tx")
    body["nets"][2]["pin_ids"].append("radio-tx")
    body["nets"][0]["peak_current_a"] = 4.0
    design = ElectricalDesign.model_validate(body)

    codes = {issue.code for issue in design.erc_issues()}
    assert {"multiple_drivers", "voltage_domain_mismatch", "source_current_exceeded"} <= codes


def test_erc_detects_unconnected_required_pin_and_undriven_input() -> None:
    body = valid_design().model_dump(mode="json")
    body["pins"][2]["net_id"] = None
    body["nets"][0]["pin_ids"].remove("controller-vin")
    body["pins"][4]["electrical_type"] = "input"
    design = ElectricalDesign.model_validate(body)

    codes = {issue.code for issue in design.erc_issues()}
    assert "required_pin_unconnected" in codes
    assert "undriven_input_net" in codes


def test_differential_pair_and_no_connect_rules_are_explicit() -> None:
    body = valid_design().model_dump(mode="json")
    body["nets"].append(
        {
            "net_id": "usb-dp",
            "name": "USB_D+",
            "kind": "differential",
            "pin_ids": [],
            "pair_net_id": "uart-tx",
        }
    )
    body["pins"][7]["electrical_type"] = "no_connect"
    design = ElectricalDesign.model_validate(body)

    codes = {issue.code for issue in design.erc_issues()}
    assert "differential_pair_not_reciprocal" in codes
    assert "no_connect_pin_connected" in codes


def test_unresolved_electrical_truth_cannot_claim_verified_authority() -> None:
    with pytest.raises(ValidationError, match="unresolved"):
        ElectricalNet(
            net_id="unknown-power",
            name="Unknown power",
            unresolved_fields=["voltage_domain"],
            authority="verified",
        )
