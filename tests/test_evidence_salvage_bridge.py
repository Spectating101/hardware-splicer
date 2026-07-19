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


def test_bridge_separates_authority_modules_from_legacy_projection() -> None:
    package = attach_evidence_first_integrations(
        {
            "recommended_build_id": "robot_drive",
            "resolved_modules": [
                {
                    "module_id": "esp32-devkit",
                    "role": "mcu",
                    "source": "user_inventory",
                },
                {
                    "module_id": "l298n",
                    "role": "drv",
                    "source": "donor_functional_salvage",
                    "board_id": "enabot-mainboard",
                    "donor_block_id": "dual-hbridge-01",
                },
            ],
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
        }
    )

    authority_ids = [row["module_id"] for row in package["authority_resolved_modules"]]
    assert "esp32-devkit" in authority_ids
    assert "donor:enabot-mainboard:dual-hbridge-01" in authority_ids
    assert "l298n" not in authority_ids

    compatibility = package["evidence_integrations"]["compatibility"]
    assert compatibility["mode"] == "legacy_graph_projection"
    assert compatibility["legacy_catalog_projection"][0]["module_id"] == "l298n"
