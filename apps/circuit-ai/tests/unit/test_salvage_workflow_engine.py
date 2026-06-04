import json

from src.intelligence.salvage_workflow_engine import SalvageWorkflowEngine


def _analysis():
    return {
        "board_understanding": {
            "board_identity": {"primary_type": "controller_or_embedded_compute", "confidence": 0.72},
            "functional_blocks": [{"block_type": "compute_control"}, {"block_type": "actuator_drive"}],
        },
        "marking_analysis": {
            "confidence": 0.8,
            "components": [
                {"candidates": [{"part_number": "ESP32"}]},
                {"candidates": [{"part_number": "ULN2003"}]},
            ],
        },
        "machine_connection_map": {
            "connector_count": 2,
            "interfaces": [{"type": "power"}, {"type": "uart_serial"}],
        },
        "defect_inspection": {"defect_count": 0},
        "salvage_opportunities": {
            "asset_summary": {
                "capabilities": {"controller": 1, "wireless": 1, "actuator_driver": 1, "power": 1},
                "parts": {"esp32": 1, "uln2003": 1},
                "connector_count": 2,
                "defect_count": 0,
                "evidence": ["part marking: esp32", "interface: power"],
            }
        },
    }


def _recipe_ready_analysis():
    analysis = _analysis()
    analysis["salvage_opportunities"]["asset_summary"]["capabilities"].update(
        {"sensor_or_adc": 1, "display_or_ui": 1}
    )
    analysis["salvage_opportunities"]["asset_summary"]["parts"].update(
        {"bme280": 1, "oled_ssd1306": 1}
    )
    analysis["salvage_opportunities"]["asset_summary"]["evidence"].extend(
        ["part marking: bme280", "part marking: oled_ssd1306"]
    )
    return analysis


def test_workflow_ingests_scan_into_persistent_inventory(tmp_path):
    inventory = tmp_path / "inventory.json"
    engine = SalvageWorkflowEngine(inventory)

    result = engine.ingest_analysis(_analysis(), source="scan-1")

    assert result["created_assets"]
    assert result["inventory_size"] >= 2
    assert inventory.exists()
    assert result["report"]["opportunity_report"]["opportunities"]

    reloaded = SalvageWorkflowEngine(inventory)
    assert reloaded.inventory_summary()["asset_count"] >= 2


def test_workflow_ingests_listing_and_scores_arbitrage(tmp_path):
    engine = SalvageWorkflowEngine(tmp_path / "inventory.json")

    result = engine.ingest_listing(
        {
            "id": "lot-1",
            "title": "cheap ESP32 relay lot",
            "price_usd": 5.0,
            "expected_capabilities": ["wireless", "actuator_driver", "power"],
            "expected_parts": ["esp32", "relay"],
        }
    )

    opportunities = result["report"]["opportunity_report"]["opportunities"]
    assert any(item["type"] == "ecommerce_arbitrage" for item in opportunities)
    assert result["report"]["decision"]["action"] in {"execute_top_opportunity", "validate_then_execute"}


def test_workflow_records_test_result(tmp_path):
    engine = SalvageWorkflowEngine(tmp_path / "inventory.json")
    result = engine.ingest_analysis(_analysis(), source="scan-1")
    asset_id = result["created_assets"][0]["asset_id"]

    update = engine.record_test_result(asset_id, "passed_basic_power_test", condition="working", notes="3.3V rail stable")

    assert update["updated"]["test_status"] == "passed_basic_power_test"
    assert update["updated"]["condition"] == "working"
    assert "3.3V rail stable" in update["updated"]["evidence"][-1]
    json.dumps(engine.plan_from_inventory())


def test_workflow_reports_recipe_optimizer_matches(tmp_path):
    engine = SalvageWorkflowEngine(tmp_path / "inventory.json")
    result = engine.ingest_analysis(_recipe_ready_analysis(), source="scan-1")

    recipe_report = result["report"]["recipe_report"]

    assert recipe_report["recipes"]
    assert recipe_report["best_recipe"]["inventory_match_percent"] >= 50
    assert "execution_plan" in result["report"]


def test_workflow_does_not_map_relay_driver_to_servo_project(tmp_path):
    engine = SalvageWorkflowEngine(tmp_path / "inventory.json")
    result = engine.ingest_listing(
        {
            "title": "ESP32 relay lot",
            "price_usd": 5.0,
            "expected_capabilities": ["wireless", "actuator_driver", "power"],
            "expected_parts": ["esp32", "relay"],
        }
    )

    best_recipe = result["report"]["recipe_report"]["best_recipe"]

    assert best_recipe is None or best_recipe["name"] != "Automatic Blind Controller"
