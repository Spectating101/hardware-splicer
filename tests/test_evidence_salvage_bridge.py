from hardware_splicer.evidence_salvage_bridge import attach_evidence_first_integrations


def test_bridge_blocks_unknown_donor_driver_firmware() -> None:
    package = attach_evidence_first_integrations(
        {
            "recommended_build_id": "robot_drive",
            "splice_plan": {
                "reusable_blocks": [
                    {
                        "board_id": "enabot-mainboard",
                        "block_id": "dual-hbridge-01",
                        "name": "Dual H-bridge motor driver",
                        "function_type": "actuator_driver",
                        "connector_refs": ["J_LOGIC"],
                    }
                ]
            },
            "firmware_scaffold": {"source": "generated/main.cpp"},
        }
    )
    authority = package["evidence_integrations"]["authority"]
    assert authority["firmware_authorized"] is False
    assert authority["unresolved_driver_interfaces"] == [
        "if:enabot-mainboard:dual-hbridge-01"
    ]
    assert package["firmware_scaffold"]["status"] == "blocked_needs_donor_control_interface"
    assert package["firmware_scaffold"]["source"] == "generated/main.cpp"


def test_bridge_does_not_block_package_without_donor_driver() -> None:
    package = attach_evidence_first_integrations(
        {
            "recommended_build_id": "sensor_logger",
            "splice_plan": {"reusable_blocks": []},
            "firmware_scaffold": {},
        }
    )
    assert package["evidence_integrations"]["authority"]["firmware_authorized"] is True
