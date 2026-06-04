from src.intelligence.repair_video_playbook import RepairVideoPlaybookBuilder


def test_video_playbook_maps_restoration_video_to_cleaning_pattern():
    playbook = RepairVideoPlaybookBuilder().build(
        {
            "title": "Restoring a corroded retro handheld console",
            "channel": "Odd Tinkering style reference",
            "url": "https://www.youtube.com/example",
            "observed_actions": ["disassemble shell", "clean buttons", "repair battery corrosion"],
        },
        symptoms=["corrosion", "dirty contacts"],
        device_hint="retro handheld console",
    )

    assert playbook["video_pattern"]["id"] == "console_cleaning_restoration"
    assert playbook["can_follow_score"] > 0.45
    assert any("cleaning phase" == item["moment"] for item in playbook["watch_map"])
    assert "electronics are completely dry before power-up" in playbook["quality_gates"]


def test_video_playbook_uses_scan_evidence_for_motor_board():
    analysis = {
        "detection_summary": {
            "total_components": 10,
            "components_by_type": {"connector": 5, "transistor": 4, "inductor": 1},
        },
        "board_understanding": {
            "board_identity": {"primary_type": "motor_or_actuator_driver", "confidence": 0.78},
        },
        "machine_connection_map": {"connector_count": 5},
        "salvage_opportunities": {
            "asset_summary": {"capabilities": {"actuator_driver": 1, "power": 1}},
        },
    }

    playbook = RepairVideoPlaybookBuilder().build(
        {
            "title": "Fixing a broken USB desk fan that will not spin",
            "channel": "repair reference",
            "observed_actions": ["inspect PCB", "test motor", "replace MOSFET"],
        },
        analysis=analysis,
        symptoms=["fan will not spin"],
        device_hint="USB desk fan",
    )

    assert playbook["repair_guide"]["device_family"]["id"] == "small_dc_motor_gadget"
    assert playbook["repair_guide"]["fault_candidates"][0]["fault_id"] == "driver_stage_or_load_fault"
    assert playbook["can_follow_score"] > 0.7
    assert "clear PCB image before cleaning or rework" in playbook["circuit_ai_inputs"]


def test_video_playbook_maps_controller_and_charging_patterns():
    controller = RepairVideoPlaybookBuilder().build(
        {
            "title": "Xbox controller stick drift repair",
            "observed_actions": ["record input tester", "clean joystick", "replace stick module"],
        },
        symptoms=["stick drift"],
        device_hint="Xbox controller",
    )
    assert controller["video_pattern"]["id"] == "controller_input_repair"
    assert "controller tester/calibration passes after reassembly" in controller["quality_gates"]

    charging = RepairVideoPlaybookBuilder().build(
        {
            "title": "Electric toothbrush not charging",
            "observed_actions": ["clean contacts", "measure battery", "check charging dock"],
        },
        symptoms=["not charging"],
        device_hint="electric toothbrush",
    )
    assert charging["video_pattern"]["id"] == "battery_charging_diagnostics"
    assert any("charger output" in item for item in charging["circuit_ai_inputs"])
