from src.api.v1 import main as main_module
from src.intelligence.repair_encyclopedia import RepairEncyclopedia
from src.intelligence.repair_market_coverage import RepairMarketCoverage
from src.intelligence.repair_video_playbook import RepairVideoPlaybookBuilder


def _motor_driver_analysis():
    return {
        "detection_summary": {
            "total_components": 10,
            "components_by_type": {"connector": 5, "transistor": 4, "inductor": 1},
            "average_confidence": 0.64,
        },
        "board_understanding": {
            "board_identity": {
                "primary_type": "motor_or_actuator_driver",
                "confidence": 0.78,
            },
            "functional_blocks": [
                {
                    "block_type": "actuator_drive",
                    "confidence": 0.85,
                    "component_count": 9,
                    "function": "Switches current for motors, relays, solenoids, or loads",
                },
                {
                    "block_type": "power_input_protection",
                    "confidence": 0.9,
                    "component_count": 10,
                    "function": "Accepts incoming power and protects downstream circuitry",
                },
                {
                    "block_type": "io_connectivity",
                    "confidence": 0.82,
                    "component_count": 5,
                    "function": "Provides external electrical connections",
                },
            ],
        },
        "machine_connection_map": {"connector_count": 5},
        "marking_analysis": {"components": [{"text": "ESP8266"}]},
        "aoi_inspection": {"readiness": "prototype_ready", "blockers": []},
        "salvage_opportunities": {
            "asset_summary": {
                "capabilities": {"actuator_driver": 1, "controller": 1, "power": 1},
            }
        },
    }


def test_repair_encyclopedia_generates_motor_driver_repair_flow():
    guide = RepairEncyclopedia().generate(
        analysis=_motor_driver_analysis(),
        symptoms=["fan will not spin", "driver gets hot"],
        device_hint="USB desk fan motor board",
    )

    assert guide["device_family"]["id"] == "small_dc_motor_gadget"
    assert guide["scan_evidence"]["components_detected"] == 10
    assert guide["safety_profile"]["risk_level"] == "low_to_medium"
    assert any(candidate["fault_id"] == "driver_stage_or_load_fault" for candidate in guide["fault_candidates"])
    assert any(step["title"] == "Output/load isolation" for step in guide["diagnostic_flow"])
    assert "dummy load" in guide["parts_and_tools"]["tools"]
    assert guide["confidence"] > 0.5


def test_repair_encyclopedia_keeps_weak_evidence_in_collection_mode():
    guide = RepairEncyclopedia().generate(
        analysis={},
        symptoms=[],
        device_hint="unknown gadget",
    )

    assert guide["device_family"]["id"] == "generic_electronic_module"
    assert "top-side and bottom-side board photos" in guide["evidence_to_collect_next"]
    assert guide["confidence"] < 0.4


def test_repair_encyclopedia_covers_real_case_lanes_without_scan():
    encyclopedia = RepairEncyclopedia()

    controller = encyclopedia.generate(
        analysis={},
        symptoms=["stick drift", "thumbstick axis is unreliable"],
        device_hint="Xbox game controller",
    )
    assert controller["device_family"]["id"] == "game_controller_input"
    assert controller["fault_candidates"][0]["fault_id"] == "analog_stick_or_button_contact_fault"

    toothbrush = encyclopedia.generate(
        analysis={},
        symptoms=["not charging", "battery does not hold charge"],
        device_hint="electric toothbrush charging dock",
    )
    assert toothbrush["device_family"]["id"] == "battery_charging_gadget"
    assert any(candidate["fault_id"] == "battery_charge_path_fault" for candidate in toothbrush["fault_candidates"])

    coffee = encyclopedia.generate(
        analysis={},
        symptoms=["coffee maker not heating", "not hot enough"],
        device_hint="coffee maker heater appliance",
    )
    assert coffee["device_family"]["id"] == "mains_heater_appliance"
    assert coffee["safety_profile"]["risk_level"] == "high"
    assert coffee["fault_candidates"][0]["fault_id"] == "heater_thermal_cutoff_or_control_fault"


def test_repair_guide_api_accepts_existing_analysis_payload():
    response = main_module.repair_guide(
        {
            "analysis": _motor_driver_analysis(),
            "symptoms": ["motor buzzes but does not spin"],
            "device_hint": "small pump",
        },
        current_user={"user_id": "user-1"},
        encyclopedia=RepairEncyclopedia(),
    )

    guide = response["repair_guide"]
    assert response["metadata"]["user_id"] == "user-1"
    assert guide["device_family"]["id"] == "small_dc_motor_gadget"
    assert guide["fault_candidates"][0]["likelihood"] > 0.5


def test_repair_coverage_api_returns_portfolio_and_query():
    coverage = RepairMarketCoverage()

    portfolio = main_module.repair_coverage_portfolio(
        current_user={"user_id": "user-1"},
        coverage=coverage,
    )
    query = main_module.repair_coverage_query(
        {"query": "Game Boy restoration battery corrosion"},
        current_user={"user_id": "user-1"},
        coverage=coverage,
    )

    assert portfolio["coverage"]["summary"]["strong_count"] >= 2
    assert query["coverage"]["top_matches"][0]["item_id"] == "retro_handheld_console"


def test_repair_video_playbook_api_returns_playbook():
    response = main_module.repair_video_playbook(
        {
            "video_reference": {
                "title": "Fixing a USB fan that will not spin",
                "channel": "repair reference",
                "observed_actions": ["inspect PCB", "test motor driver"],
            },
            "analysis": _motor_driver_analysis(),
            "symptoms": ["fan will not spin"],
            "device_hint": "USB desk fan",
        },
        current_user={"user_id": "user-1"},
        builder=RepairVideoPlaybookBuilder(RepairEncyclopedia()),
    )

    assert response["metadata"]["user_id"] == "user-1"
    assert response["playbook"]["repair_guide"]["device_family"]["id"] == "small_dc_motor_gadget"
