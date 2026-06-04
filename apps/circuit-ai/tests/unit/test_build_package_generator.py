import json

from src.intelligence.build_package_generator import BuildPackageGenerator
from src.intelligence.salvage_workflow_engine import SalvageWorkflowEngine
from src.api.v1 import main as main_module


def _workflow_report():
    return {
        "inventory": {"estimated_inventory_value_usd": 12.0, "assets": []},
        "opportunity_report": {
            "confidence": 0.6,
            "best_opportunity": {
                "type": "build_from_salvage",
                "name": "Sensor Gateway / Data Logger",
                "score": 0.7,
                "category": "iot",
                "matched_assets": ["controller", "sensor_or_adc", "wireless"],
                "missing_assets": ["display_or_ui"],
                "estimated_output_value_usd": 24.0,
            },
        },
        "recipe_report": {
            "best_recipe": {
                "name": "WiFi Weather Station",
                "category": "weather_station",
                "required_components": ["esp32", "bme280", "oled_ssd1306"],
                "components_owned": ["esp32", "bme280"],
                "components_needed": ["oled_ssd1306"],
                "inventory_match_percent": 66.7,
                "missing_parts_cost": 6.0,
                "parts_cost": 19.0,
                "market_price_low": 20.0,
                "market_price_high": 35.0,
                "profit_margin": 8.5,
                "roi_percent": 44.7,
                "build_time_hours": 2.0,
            }
        },
        "execution_plan": {
            "status": "ready_to_execute",
            "target": "Sensor Gateway / Data Logger",
            "target_type": "build_from_salvage",
            "recipe_target": {
                "name": "WiFi Weather Station",
                "category": "weather_station",
                "required_components": ["esp32", "bme280", "oled_ssd1306"],
                "components_owned": ["esp32", "bme280"],
                "components_needed": ["oled_ssd1306"],
                "inventory_match_percent": 66.7,
                "missing_parts_cost": 6.0,
                "parts_cost": 19.0,
                "market_price_low": 20.0,
                "market_price_high": 35.0,
                "profit_margin": 8.5,
                "roi_percent": 44.7,
                "build_time_hours": 2.0,
            },
            "steps": ["reserve matched salvage assets"],
            "validation_gates": ["no unknown power polarity"],
        },
    }


def test_build_package_generator_creates_actionable_package():
    package = BuildPackageGenerator().generate(_workflow_report())

    assert package["package_type"] == "known_recipe_build"
    assert package["target_source"] == "recipe"
    assert package["bom"]["missing"] == ["oled_ssd1306"]
    assert "current-limited first power-up" in package["validation"]["required_tests"]
    assert package["firmware_plan"]["target_platform"] == "esp32"
    assert "Circuit-AI salvage starter firmware" in package["firmware_plan"]["starter_code"]
    assert package["commercialization"]["estimated_market_price_high_usd"] == 35.0
    json.dumps(package)


def test_workflow_report_includes_build_package(tmp_path):
    engine = SalvageWorkflowEngine(tmp_path / "inventory.json")
    engine.ingest_listing(
        {
            "title": "ESP32 BME280 OLED lot",
            "price_usd": 10.0,
            "expected_capabilities": ["controller", "wireless", "sensor_or_adc", "display_or_ui"],
            "expected_parts": ["esp32", "bme280", "oled_ssd1306"],
        }
    )

    report = engine.plan_from_inventory()

    assert report["build_package"]["work_order"]["steps"]
    assert "build_package" in report


def test_salvage_build_package_api_returns_package(tmp_path):
    workflow = SalvageWorkflowEngine(tmp_path / "inventory.json")
    workflow.ingest_listing(
        {
            "title": "ESP32 relay lot",
            "price_usd": 5.0,
            "expected_capabilities": ["wireless", "actuator_driver", "power"],
            "expected_parts": ["esp32", "relay"],
        }
    )

    response = main_module.salvage_build_package(
        current_user={"user_id": "user-1"},
        workflow=workflow,
    )

    assert response["build_package"]["mode"] == "salvage_build_package"
    assert response["metadata"]["user_id"] == "user-1"


def test_build_package_respects_collect_more_evidence_decision():
    report = _workflow_report()
    report["decision"] = {"action": "inventory_and_collect_more_evidence"}

    package = BuildPackageGenerator().generate(report)

    assert package["package_type"] == "evidence_collection"
    assert package["target"] == {}


def test_build_package_keeps_mismatched_recipe_as_candidate():
    report = _workflow_report()
    report["opportunity_report"]["best_opportunity"] = {
        "type": "build_from_salvage",
        "name": "Robot Motor Controller",
        "score": 0.61,
        "category": "robotics",
        "matched_assets": ["controller", "actuator_driver"],
        "missing_assets": [],
        "estimated_output_value_usd": 28.0,
    }
    report["execution_plan"]["target"] = "Robot Motor Controller"
    report["execution_plan"]["recipe_target"] = {
        "name": "IoT Smart Relay Controller",
        "category": "home_automation",
        "required_components": ["esp8266", "relay", "led"],
        "components_owned": ["esp8266", "relay"],
        "components_needed": ["led"],
    }

    package = BuildPackageGenerator().generate(report)

    assert package["package_type"] == "salvage_project_build"
    assert package["target_source"] == "opportunity"
    assert package["target"]["name"] == "Robot Motor Controller"
    assert package["candidate_recipe"]["name"] == "IoT Smart Relay Controller"
