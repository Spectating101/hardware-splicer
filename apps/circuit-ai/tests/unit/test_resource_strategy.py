from src.api.v1 import main as main_module
from src.intelligence.resource_strategy import ResourceStrategyPlanner


def test_constrained_strategy_prefers_available_reuse_over_catalog():
    strategy = ResourceStrategyPlanner().plan(
        {
            "goal": "build a USB fume extractor",
            "strategy_mode": "constrained",
            "required_capabilities": ["power", "motor_or_load", "fan_or_pump", "switch_or_button", "connector"],
            "available_resources": [
                {
                    "name": "verified 5V fan assembly",
                    "resource_kind": "salvaged",
                    "capabilities": ["power", "motor_or_load", "fan_or_pump"],
                    "confidence": 0.8,
                    "evidence_status": "verified",
                },
                {
                    "name": "owned toggle switch",
                    "resource_kind": "owned",
                    "capabilities": ["switch_or_button"],
                    "confidence": 0.76,
                    "evidence_status": "verified",
                },
                {
                    "name": "JST harness",
                    "resource_kind": "owned",
                    "capabilities": ["connector"],
                    "confidence": 0.7,
                    "evidence_status": "available",
                },
            ],
            "procurable_catalog": [
                {
                    "name": "new USB fan module",
                    "resource_kind": "procurable",
                    "capabilities": ["power", "motor_or_load", "fan_or_pump"],
                    "cost_usd": 2.5,
                    "confidence": 0.9,
                }
            ],
        }
    )

    selected_kinds = {resource["resource_kind"] for resource in strategy["selected_resources"]}
    assert strategy["recommended_path"] == "reuse_first"
    assert "procurable" not in selected_kinds
    assert strategy["coverage"]["missing_capabilities"] == []
    assert strategy["build_readiness"]["status"] == "ready_for_build_plan"


def test_open_procurement_prefers_known_catalog_over_uncertain_salvage():
    strategy = ResourceStrategyPlanner().plan(
        {
            "goal": "make a small cooling fan module",
            "strategy_mode": "open_procurement",
            "required_capabilities": ["power", "motor_or_load", "fan_or_pump"],
            "available_resources": [
                {
                    "name": "unknown fan wires from junk board",
                    "resource_kind": "salvaged",
                    "capabilities": ["power", "motor_or_load", "fan_or_pump"],
                    "confidence": 0.38,
                    "evidence_status": "needs_evidence",
                }
            ],
            "procurable_catalog": [
                {
                    "resource_id": "known_usb_fan",
                    "name": "known 5V USB fan module",
                    "resource_kind": "procurable",
                    "capabilities": ["power", "motor_or_load", "fan_or_pump"],
                    "cost_usd": 2.4,
                    "confidence": 0.92,
                }
            ],
            "use_reference_catalog": False,
        }
    )

    assert strategy["recommended_path"] == "buy_first"
    assert strategy["selected_resources"][0]["resource_id"] == "known_usb_fan"
    assert strategy["selected_resources"][0]["resource_kind"] == "procurable"
    assert strategy["procurement_plan"]["estimated_cost_usd"] == 2.4


def test_hybrid_strategy_reuses_verified_owned_block_and_buys_gaps():
    strategy = ResourceStrategyPlanner().plan(
        {
            "goal": "build a sensor logger",
            "strategy_mode": "hybrid",
            "constraints": {"budget_usd": 5},
            "required_capabilities": ["controller", "sensor_or_adc", "power"],
            "available_resources": [
                {
                    "resource_id": "drawer_esp32",
                    "name": "ESP32 board from drawer",
                    "resource_kind": "owned",
                    "capabilities": ["controller", "wireless", "usb_serial"],
                    "confidence": 0.84,
                    "evidence_status": "verified",
                }
            ],
            "procurable_catalog": [
                {
                    "resource_id": "sensor_breakout",
                    "name": "I2C sensor breakout",
                    "resource_kind": "procurable",
                    "capabilities": ["sensor_or_adc"],
                    "cost_usd": 2.5,
                    "confidence": 0.86,
                },
                {
                    "resource_id": "buck",
                    "name": "buck converter",
                    "resource_kind": "procurable",
                    "capabilities": ["power"],
                    "cost_usd": 2.0,
                    "confidence": 0.86,
                },
            ],
            "use_reference_catalog": False,
        }
    )

    selected_ids = {resource["resource_id"] for resource in strategy["selected_resources"]}
    selected_kinds = {resource["resource_kind"] for resource in strategy["selected_resources"]}
    assert strategy["recommended_path"] == "hybrid_gap_fill"
    assert {"drawer_esp32", "sensor_breakout", "buck"}.issubset(selected_ids)
    assert {"owned", "procurable"}.issubset(selected_kinds)
    assert strategy["procurement_plan"]["within_budget"] is True


def test_strategy_blocks_unsafe_salvage_instead_of_using_it_as_power():
    strategy = ResourceStrategyPlanner().plan(
        {
            "goal": "reuse a battery as a small supply",
            "strategy_mode": "constrained",
            "required_capabilities": ["power"],
            "available_resources": [
                {
                    "name": "swollen lithium pack",
                    "resource_kind": "salvaged",
                    "capabilities": ["power"],
                    "confidence": 0.7,
                }
            ],
            "use_reference_catalog": False,
        }
    )

    assert strategy["selected_resources"] == []
    assert strategy["blocked_resources"][0]["status"] == "unsafe_hold"
    assert strategy["coverage"]["missing_capabilities"] == ["power"]
    assert strategy["build_readiness"]["status"] == "blocked_missing_resources"


def test_constrained_strategy_does_not_treat_goal_text_salvage_hints_as_inventory():
    strategy = ResourceStrategyPlanner().plan(
        {
            "goal": "build a sensor logger from an ESP32",
            "strategy_mode": "constrained",
            "required_capabilities": ["controller", "sensor_or_adc", "power"],
            "available_resources": [
                {
                    "resource_id": "drawer_esp32",
                    "name": "ESP32 board from drawer",
                    "resource_kind": "owned",
                    "capabilities": ["controller", "wireless", "usb_serial"],
                    "confidence": 0.84,
                    "evidence_status": "verified",
                }
            ],
            "salvage_plan": {
                "mode": "salvage_splice_reuse_plan",
                "reusable_blocks": [
                    {
                        "block_id": "sensor",
                        "name": "sensor module",
                        "source": "text_signal",
                        "capabilities": ["sensor_or_adc"],
                        "confidence": 0.48,
                    }
                ],
            },
            "use_reference_catalog": False,
        }
    )

    selected_ids = {resource["resource_id"] for resource in strategy["selected_resources"]}

    assert selected_ids == {"drawer_esp32"}
    assert strategy["coverage"]["missing_capabilities"] == ["power", "sensor_or_adc"]
    assert strategy["build_readiness"]["status"] == "blocked_missing_resources"


def test_discovery_goal_derives_requirements_from_visible_board_candidates():
    strategy = ResourceStrategyPlanner().plan(
        {
            "goal": "inspect this photographed board for salvage and reuse options",
            "strategy_mode": "constrained",
            "available_resources": [
                {
                    "resource_id": "vision_cpu",
                    "name": "CPU / SoC",
                    "resource_kind": "salvaged",
                    "capabilities": ["controller"],
                    "confidence": 0.66,
                    "evidence_status": "needs_evidence",
                },
                {
                    "resource_id": "vision_usb_c",
                    "name": "USB-C power input",
                    "resource_kind": "salvaged",
                    "capabilities": ["connector", "power"],
                    "confidence": 0.66,
                    "evidence_status": "needs_evidence",
                },
                {
                    "resource_id": "vision_gpio",
                    "name": "40-pin GPIO header",
                    "resource_kind": "salvaged",
                    "capabilities": ["connector"],
                    "confidence": 0.66,
                    "evidence_status": "needs_evidence",
                },
            ],
            "use_reference_catalog": False,
        }
    )

    assert strategy["required_capabilities"] == ["controller", "power", "connector"]
    assert strategy["coverage"]["coverage_score"] == 1
    assert {resource["resource_id"] for resource in strategy["selected_resources"]} == {"vision_cpu", "vision_usb_c"}
    assert strategy["build_readiness"]["status"] == "prototype_after_evidence"
    assert strategy["evidence_gates"]


def test_discovery_goal_keeps_unknown_parts_as_identification_targets():
    strategy = ResourceStrategyPlanner().plan(
        {
            "goal": "inspect this board for salvage",
            "strategy_mode": "constrained",
            "available_resources": [
                {
                    "resource_id": "vision_u1",
                    "name": "unknown IC package",
                    "resource_kind": "salvaged",
                    "capabilities": ["unknown_reusable_part"],
                    "confidence": 0.62,
                    "evidence_status": "needs_evidence",
                }
            ],
            "use_reference_catalog": False,
        }
    )

    assert strategy["required_capabilities"] == ["unknown_reusable_part"]
    assert strategy["selected_resources"][0]["resource_id"] == "vision_u1"
    assert strategy["build_readiness"]["status"] == "prototype_after_evidence"


def test_resource_strategy_api_returns_metadata():
    response = main_module.resource_strategy(
        {
            "goal": "build a UART debug adapter",
            "strategy_mode": "hybrid",
            "required_capabilities": ["usb_serial", "connector"],
            "available_resources": [
                {
                    "name": "known CH340 adapter",
                    "resource_kind": "owned",
                    "capabilities": ["usb_serial", "connector"],
                    "confidence": 0.9,
                    "evidence_status": "verified",
                }
            ],
        },
        current_user={"user_id": "operator-1"},
    )

    assert response["metadata"]["user_id"] == "operator-1"
    assert response["metadata"]["strategy_mode"] == "hybrid"
    assert response["resource_strategy"]["build_readiness"]["status"] == "ready_for_build_plan"
