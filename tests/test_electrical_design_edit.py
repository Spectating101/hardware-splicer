from __future__ import annotations

import pytest

from hardware_splicer.electrical_design import (
    ElectricalComponent,
    ElectricalDesign,
    ElectricalNet,
    ElectricalPin,
    NetKind,
    PinElectricalType,
)
from hardware_splicer.electrical_design_edit import ElectricalEditError, apply_electrical_edits


def design() -> ElectricalDesign:
    return ElectricalDesign(
        design_id="robot-electrical",
        project_id="robot",
        components=[
            ElectricalComponent(
                component_id="controller",
                reference="U1",
                name="Controller",
                pin_ids=["controller-tx", "controller-vin"],
            ),
            ElectricalComponent(
                component_id="radio",
                reference="U2",
                name="Radio",
                pin_ids=["radio-rx"],
            ),
        ],
        pins=[
            ElectricalPin(
                pin_id="controller-tx",
                component_id="controller",
                number="1",
                name="TX",
                electrical_type=PinElectricalType.OUTPUT,
            ),
            ElectricalPin(
                pin_id="controller-vin",
                component_id="controller",
                number="2",
                name="VIN",
                electrical_type=PinElectricalType.POWER_IN,
                required=True,
            ),
            ElectricalPin(
                pin_id="radio-rx",
                component_id="radio",
                number="1",
                name="RX",
                electrical_type=PinElectricalType.INPUT,
            ),
        ],
        nets=[
            ElectricalNet(net_id="uart-tx", name="UART_TX", kind=NetKind.SIGNAL),
            ElectricalNet(net_id="vcc", name="VCC", kind=NetKind.POWER),
        ],
    )


def test_connect_and_disconnect_pin_keep_membership_bidirectional() -> None:
    connected = apply_electrical_edits(
        design(),
        [
            {"type": "connect_pin", "payload": {"pin_id": "controller-tx", "net_id": "uart-tx"}},
            {"type": "connect_pin", "payload": {"pin_id": "radio-rx", "net_id": "uart-tx"}},
        ],
    )
    net = next(row for row in connected.nets if row.net_id == "uart-tx")
    assert net.pin_ids == ["controller-tx", "radio-rx"]
    assert next(row for row in connected.pins if row.pin_id == "controller-tx").net_id == "uart-tx"

    disconnected = apply_electrical_edits(
        connected,
        [{"type": "disconnect_pin", "payload": {"pin_id": "radio-rx"}}],
    )
    assert next(row for row in disconnected.pins if row.pin_id == "radio-rx").net_id is None
    assert next(row for row in disconnected.nets if row.net_id == "uart-tx").pin_ids == ["controller-tx"]


def test_upsert_pin_moves_component_and_net_membership() -> None:
    candidate = apply_electrical_edits(
        design(),
        [
            {
                "type": "upsert_pin",
                "payload": {
                    "pin_id": "controller-tx",
                    "component_id": "radio",
                    "number": "2",
                    "name": "TX2",
                    "electrical_type": "output",
                    "net_id": "uart-tx",
                },
            }
        ],
    )

    controller = next(row for row in candidate.components if row.component_id == "controller")
    radio = next(row for row in candidate.components if row.component_id == "radio")
    assert "controller-tx" not in controller.pin_ids
    assert "controller-tx" in radio.pin_ids
    assert next(row for row in candidate.nets if row.net_id == "uart-tx").pin_ids == ["controller-tx"]


def test_net_membership_edit_moves_pins_from_previous_net() -> None:
    connected = apply_electrical_edits(
        design(),
        [{"type": "connect_pin", "payload": {"pin_id": "controller-tx", "net_id": "uart-tx"}}],
    )
    moved = apply_electrical_edits(
        connected,
        [
            {
                "type": "upsert_net",
                "payload": {
                    "net_id": "alternate",
                    "name": "ALTERNATE",
                    "kind": "signal",
                    "pin_ids": ["controller-tx"],
                },
            }
        ],
    )

    assert next(row for row in moved.nets if row.net_id == "uart-tx").pin_ids == []
    assert next(row for row in moved.nets if row.net_id == "alternate").pin_ids == ["controller-tx"]
    assert next(row for row in moved.pins if row.pin_id == "controller-tx").net_id == "alternate"


def test_connected_pin_and_net_removal_require_explicit_disconnect() -> None:
    connected = apply_electrical_edits(
        design(),
        [{"type": "connect_pin", "payload": {"pin_id": "controller-tx", "net_id": "uart-tx"}}],
    )
    with pytest.raises(ElectricalEditError, match="force_disconnect"):
        apply_electrical_edits(
            connected,
            [{"type": "remove_pin", "payload": {"pin_id": "controller-tx"}}],
        )
    with pytest.raises(ElectricalEditError, match="force_disconnect"):
        apply_electrical_edits(
            connected,
            [{"type": "remove_net", "payload": {"net_id": "uart-tx"}}],
        )

    removed = apply_electrical_edits(
        connected,
        [{"type": "remove_net", "payload": {"net_id": "uart-tx", "force_disconnect": True}}],
    )
    assert "uart-tx" not in {row.net_id for row in removed.nets}
    assert next(row for row in removed.pins if row.pin_id == "controller-tx").net_id is None


def test_authoring_cannot_fabricate_verified_pin_truth() -> None:
    with pytest.raises(ElectricalEditError, match="cannot assign verified"):
        apply_electrical_edits(
            design(),
            [
                {
                    "type": "upsert_pin",
                    "payload": {
                        "pin_id": "controller-tx",
                        "authority": "verified",
                    },
                }
            ],
        )


def test_edited_design_returns_erc_findings_not_hidden_errors() -> None:
    candidate = apply_electrical_edits(
        design(),
        [
            {"type": "connect_pin", "payload": {"pin_id": "controller-vin", "net_id": "vcc"}},
        ],
    )
    assert "power_without_source" in {issue.code for issue in candidate.erc_issues()}
