from hardware_splicer.backends import BackendStatus, build_circuit_json_projection
from hardware_splicer.bench import donor_interface_discovery_recipe
from hardware_splicer.donor import (
    Contact,
    InterfaceContract,
    InterfaceStatus,
    SignalContract,
    SignalDirection,
    accepted_measurement,
    interface_from_functional_salvage,
)
from hardware_splicer.integration_stack import IntegrationStack


def test_functional_analogy_does_not_inherit_l298n_contract() -> None:
    contract = interface_from_functional_salvage(
        {
            "board_id": "enabot-mainboard",
            "block_id": "dual-hbridge-01",
            "name": "Dual H-bridge",
            "function_type": "actuator_driver",
            "connector_refs": ["J_LOGIC"],
        }
    )
    assert contract.virtual_module_id == "donor:enabot-mainboard:dual-hbridge-01"
    assert contract.reference_equivalents == [
        {
            "module_id": "l298n",
            "relationship": "functional_analogy_only",
            "electrical_contract_inherited": False,
        }
    ]
    assert contract.can_generate_firmware() is False
    assert "interface_complete" in contract.unresolved_fields()
    assert contract.to_resolved_module()["module_id"].startswith("donor:")


def test_verified_interface_can_authorize_firmware() -> None:
    voltage = accepted_measurement(
        3.3,
        unit="V",
        evidence_id="m-voltage",
        method="DMM",
    )
    active = accepted_measurement(
        "high",
        unit=None,
        evidence_id="m-polarity",
        method="stimulus response",
    )
    contract = InterfaceContract(
        interface_id="if:test:driver",
        board_id="test",
        block_id="driver",
        functional_role="motor_driver",
        contacts=[Contact(contact_id="J1.1")],
        signals=[
            SignalContract(
                signal_id="enable",
                contact_id="J1.1",
                direction=SignalDirection.INPUT,
                voltage_max_v=voltage,
                active_level=active,
                controller_pin=accepted_measurement(
                    "GPIO16",
                    unit=None,
                    evidence_id="design-binding",
                    method="approved pin assignment",
                ),
            )
        ],
        interface_complete=accepted_measurement(
            True,
            unit=None,
            evidence_id="interface-review",
            method="complete interface review",
        ),
        status=InterfaceStatus.VERIFIED,
    )
    assert contract.can_generate_firmware() is True


def test_bench_recipe_blocks_missing_observations() -> None:
    recipe = donor_interface_discovery_recipe("if:test")
    result = recipe.run_manual({})
    assert result["outcome"] == "blocked"
    assert result["power_authorized"] is False


def test_tscircuit_projection_preserves_donor_metadata() -> None:
    projection = build_circuit_json_projection(
        modules=[
            {
                "id": "driver-1",
                "module_id": "donor:test:driver",
                "source": "donor_interface_contract",
                "interface_status": "partial",
                "firmware_authorized": False,
            }
        ],
        wires=[],
        project_name="test",
    )
    donor = next(item for item in projection if item["type"] == "source_group")
    assert donor["hardware_splicer"]["firmware_authorized"] is False


def test_stack_emits_blocked_interface_package() -> None:
    stack = IntegrationStack(graph_id="g1")
    [contract] = stack.ingest_functional_salvage(
        [
            {
                "board_id": "board",
                "block_id": "driver",
                "function_type": "actuator_driver",
            }
        ]
    )
    package = stack.build_interface_package(contract.interface_id)
    assert package["compile_status"] == "blocked"
    assert package["resolved_module"]["firmware_authorized"] is False


def test_interface_recompute_promotes_authoritative_signals() -> None:
    contract = InterfaceContract(
        interface_id="if:board:driver",
        board_id="board",
        block_id="driver",
        functional_role="actuator_driver",
        contacts=[Contact(contact_id="J1.1", connector_ref="J1", pin_number="1")],
        signals=[
            SignalContract(
                signal_id="enable",
                contact_id="J1.1",
                direction=SignalDirection.INPUT,
                voltage_max_v=accepted_measurement(
                    3.3, unit="V", evidence_id="m-voltage", method="DMM"
                ),
                active_level=accepted_measurement(
                    "high", unit=None, evidence_id="m-polarity", method="protected stimulus"
                ),
                controller_pin=accepted_measurement(
                    "GPIO16", unit=None, evidence_id="design-binding", method="approved pin assignment"
                ),
            )
        ],
        interface_complete=accepted_measurement(
            True,
            unit=None,
            evidence_id="interface-review",
            method="complete interface review",
        ),
    )

    assert contract.recompute_status() == InterfaceStatus.VERIFIED
    assert contract.can_generate_firmware() is True
    assert contract.unresolved_fields() == []


def test_interface_requires_complete_attestation_for_firmware() -> None:
    contract = InterfaceContract(
        interface_id="if:board:driver",
        board_id="board",
        block_id="driver",
        functional_role="actuator_driver",
        contacts=[Contact(contact_id="J1.1")],
        signals=[
            SignalContract(
                signal_id="enable",
                contact_id="J1.1",
                direction=SignalDirection.INPUT,
                voltage_max_v=accepted_measurement(
                    3.3, unit="V", evidence_id="m-voltage", method="DMM"
                ),
                active_level=accepted_measurement(
                    "high", unit=None, evidence_id="m-polarity", method="protected stimulus"
                ),
                controller_pin=accepted_measurement(
                    "GPIO16", unit=None, evidence_id="design-binding", method="approved pin assignment"
                ),
            )
        ],
    )

    assert contract.recompute_status() == InterfaceStatus.PARTIAL
    assert contract.can_generate_firmware() is False
    assert "interface_complete" in contract.unresolved_fields()


def test_interface_requires_controller_pin_for_firmware() -> None:
    contract = InterfaceContract(
        interface_id="if:board:driver",
        board_id="board",
        block_id="driver",
        functional_role="actuator_driver",
        contacts=[Contact(contact_id="J1.1")],
        signals=[
            SignalContract(
                signal_id="enable",
                contact_id="J1.1",
                direction=SignalDirection.INPUT,
                voltage_max_v=accepted_measurement(
                    3.3, unit="V", evidence_id="m-voltage", method="DMM"
                ),
                active_level=accepted_measurement(
                    "high", unit=None, evidence_id="m-polarity", method="protected stimulus"
                ),
            )
        ],
        interface_complete=accepted_measurement(
            True,
            unit=None,
            evidence_id="interface-review",
            method="complete interface review",
        ),
    )

    contract.recompute_status()
    assert contract.can_generate_firmware() is False
    assert "signals.enable.controller_pin" in contract.unresolved_fields()
