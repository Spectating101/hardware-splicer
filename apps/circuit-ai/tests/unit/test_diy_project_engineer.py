import pytest

from src.intelligence.diy_project_engineer import build_diy_project_engineering_plan
from src.intelligence.hardware_plan import HardwarePlanOrchestrator


def _plant_watering_payload():
    return {
        "diy_project": "DIY automatic plant watering system for desk plants",
        "strategy_mode": "hybrid",
        "constraints": {"budget_usd": 5, "safety_level": "low_voltage_only"},
        "available_resources": [
            {
                "resource_id": "drawer_esp32",
                "name": "ESP32 dev board",
                "resource_kind": "owned",
                "capabilities": ["controller", "wireless", "usb_serial", "connector"],
                "confidence": 0.86,
                "evidence_status": "verified",
            },
            {
                "resource_id": "soil_probe",
                "name": "capacitive soil moisture sensor module",
                "resource_kind": "owned",
                "capabilities": ["sensor_or_adc", "connector"],
                "confidence": 0.76,
                "evidence_status": "needs_evidence",
            },
            {
                "resource_id": "usb_power_bank",
                "name": "USB power bank and cable",
                "resource_kind": "owned",
                "capabilities": ["power", "connector"],
                "confidence": 0.82,
                "evidence_status": "verified",
            },
            {
                "resource_id": "small_pump",
                "name": "5V mini water pump",
                "resource_kind": "owned",
                "capabilities": ["motor_or_load", "fan_or_pump"],
                "confidence": 0.72,
                "evidence_status": "needs_evidence",
            },
        ],
        "procurable_catalog": [
            {
                "resource_id": "logic_mosfet_module",
                "name": "logic-level MOSFET driver module with flyback diode",
                "resource_kind": "procurable",
                "capabilities": ["actuator_driver", "protection"],
                "cost_usd": 1.5,
                "confidence": 0.86,
            }
        ],
        "use_reference_catalog": False,
    }


def test_diy_project_engineer_turns_build_goal_into_architecture_and_gates():
    plan = build_diy_project_engineering_plan(_plant_watering_payload())

    required = set(plan["requirements"]["required_capabilities"])
    selected_ids = {row["resource_id"] for row in plan["resource_plan"]["selected_resources"]}
    gate_prompts = [gate["prompt"] for gate in plan["engineering_gates"]]

    assert plan["available"] is True
    assert plan["project_intent"]["profile_id"] == "automatic_plant_watering"
    assert {"controller", "sensor_or_adc", "actuator_driver", "motor_or_load", "fan_or_pump", "power", "connector", "protection"}.issubset(required)
    assert {"drawer_esp32", "soil_probe", "usb_power_bank", "small_pump", "logic_mosfet_module"}.issubset(selected_ids)
    assert plan["resource_plan"]["coverage"]["coverage_score"] == 1
    assert plan["readiness"]["level"] == "prototype_after_evidence"
    assert plan["readiness"]["can_build_or_power_now"] is False
    assert any("pump startup current" in prompt for prompt in gate_prompts)
    assert any(gate["type"] == "review" and "Wet/dry boundary" in gate["prompt"] for gate in plan["engineering_gates"])
    assert any(block["block_id"] == "pump_driver" and block["candidate_resource_ids"] == ["logic_mosfet_module"] for block in plan["architecture_blocks"])


def test_hardware_plan_uses_diy_requirements_when_capabilities_are_not_explicit():
    plan = HardwarePlanOrchestrator().plan(_plant_watering_payload())

    project = plan["integrated_plan"]["project_engineering"]
    strategy = plan["resource_strategy"]

    assert project["profile_id"] == "automatic_plant_watering"
    assert "actuator_driver" in strategy["required_capabilities"]
    assert "sensor_or_adc" in strategy["required_capabilities"]
    assert strategy["coverage"]["coverage_score"] == 1
    assert plan["analysis"]["diy_project_engineering"]["readiness"]["level"] == "prototype_after_evidence"
    assert plan["integrated_plan"]["status"] == "prototype_after_evidence"
    assert any("pump startup current" in gate["prompt"] for gate in plan["integrated_plan"]["evidence_gates"])


def test_diy_project_engineer_blocks_mains_heater_as_specialist_lane():
    plan = build_diy_project_engineering_plan(
        {
            "diy_project": "build a 120V mains heater controller",
            "strategy_mode": "open_procurement",
            "use_reference_catalog": False,
        }
    )

    safety_gates = [gate for gate in plan["engineering_gates"] if gate["type"] == "safety"]

    assert plan["available"] is True
    assert plan["readiness"]["level"] == "blocked_specialist_required"
    assert plan["readiness"]["can_start_design_now"] is False
    assert plan["readiness"]["can_build_or_power_now"] is False
    assert any(gate["status"] == "blocked" and "Mains/high-voltage" in gate["prompt"] for gate in safety_gates)


def test_diy_project_engineer_accepts_vague_goal_first_plant_watering_intake():
    plan = build_diy_project_engineering_plan(
        {
            "diy_project": "I need something that waters my plants while I am away. I have random old electronics and about $10.",
            "strategy_mode": "hybrid",
        }
    )

    assert plan["available"] is True
    assert plan["project_intent"]["profile_id"] == "automatic_plant_watering"
    assert plan["readiness"]["level"] == "prototype_after_evidence"
    assert plan["requirements"]["constraints"]["budget_usd"] == 10
    assert plan["resource_plan"]["procurement"]["budget_usd"] == 10
    assert plan["resource_plan"]["procurement"]["within_budget"] is False
    assert not any(gate["gate_id"] == "safety_mains_high_voltage" for gate in plan["engineering_gates"])
    assert any("Write the target output function" in gate["prompt"] for gate in plan["engineering_gates"])


def test_diy_project_engineer_does_not_default_unmatched_prompt_to_plant_watering():
    plan = build_diy_project_engineering_plan(
        {
            "diy_project": "My room gets too hot and I have spare fans and old adapters. Can we make something useful?",
            "strategy_mode": "hybrid",
        }
    )

    assert plan["available"] is True
    assert plan["project_intent"]["profile_id"] == "fume_extractor_or_fan"
    assert plan["project_intent"]["profile_id"] != "automatic_plant_watering"


@pytest.mark.parametrize(
    ("prompt", "expected_profile", "expected_readiness"),
    [
        ("I want an automatic irrigator for herbs using junk parts, cheap.", "automatic_plant_watering", "prototype_after_evidence"),
        ("Need solder smoke extractor from an old PC fan and USB cable.", "fume_extractor_or_fan", "prototype_after_evidence"),
        ("I want to monitor temperature and humidity in a cabinet and log it over time.", "sensor_logger", "prototype_after_evidence"),
        ("Make me a safe little bench power breakout from an old laptop adapter.", "bench_power_adapter", "prototype_after_evidence"),
        ("Build a USB powered desk light from LED strips and an old adapter.", "task_light_or_indicator", "prototype_after_evidence"),
        ("Can we build a tiny rover from toy motors, wheels, and random boards?", "robot_drive_base", "prototype_after_evidence"),
        ("I want a board inspection jig with light and a sliding camera mount.", "inspection_fixture", "prototype_after_evidence"),
        ("Need to switch a 12V solenoid valve from a microcontroller.", "load_controller", "prototype_after_evidence"),
        ("Can I make a USB macro keypad from spare switches and an old controller board?", "input_panel", "prototype_after_evidence"),
        ("I need a wifi network status indicator from spare LEDs.", "network_status_indicator", "prototype_after_evidence"),
        ("Make a little audio alert box from a speaker and USB power.", "audio_alert_box", "prototype_after_evidence"),
        ("Can we build a camera trigger inspection rig?", "camera_trigger_or_capture_rig", "prototype_after_evidence"),
        ("I have junk electronics and $5, what should I make?", "generic_low_voltage_build", "prototype_after_evidence"),
    ],
)
def test_diy_project_engineer_routes_common_build_specialties(prompt, expected_profile, expected_readiness):
    plan = build_diy_project_engineering_plan({"diy_project": prompt, "strategy_mode": "hybrid"})

    assert plan["available"] is True
    assert plan["project_intent"]["profile_id"] == expected_profile
    assert plan["readiness"]["level"] == expected_readiness
    assert plan["resource_plan"]["coverage"]["coverage_score"] == 1
    assert plan["readiness"]["can_build_or_power_now"] is False
    assert plan["next_evidence_tasks"]


@pytest.mark.parametrize(
    ("prompt", "expected_hazard"),
    [
        ("Build a wall outlet AC lamp controller from a relay.", "safety_mains_high_voltage"),
        ("Make a lithium 18650 battery pack for a portable project.", "safety_battery_pack_lithium"),
        ("I want to make a laser engraver from salvaged DVD parts.", "safety_laser_radiation"),
    ],
)
def test_diy_project_engineer_hard_blocks_specialist_hazards(prompt, expected_hazard):
    plan = build_diy_project_engineering_plan({"diy_project": prompt, "strategy_mode": "hybrid"})
    safety_gate_ids = [gate["gate_id"] for gate in plan["engineering_gates"] if gate["type"] == "safety"]

    assert plan["available"] is True
    assert plan["readiness"]["level"] == "blocked_specialist_required"
    assert safety_gate_ids.count(expected_hazard) == 1
    assert plan["readiness"]["can_start_design_now"] is False


def test_diy_project_engineer_does_not_hard_block_negated_ac_context():
    plan = build_diy_project_engineering_plan(
        {"diy_project": "I need automatic plant watering, no AC outlet, only USB power.", "strategy_mode": "hybrid"}
    )
    safety_gate_ids = [gate["gate_id"] for gate in plan["engineering_gates"] if gate["gate_id"].startswith("safety_")]

    assert plan["available"] is True
    assert plan["project_intent"]["profile_id"] == "automatic_plant_watering"
    assert plan["readiness"]["level"] == "prototype_after_evidence"
    assert "safety_mains_high_voltage" not in safety_gate_ids
    assert "safety_water_near_electronics" in safety_gate_ids


def test_diy_project_engineer_ignores_non_build_discovery_without_diy_trigger():
    plan = build_diy_project_engineering_plan({"description": "Can you identify this PCB from a photo?"})

    assert plan["available"] is False
