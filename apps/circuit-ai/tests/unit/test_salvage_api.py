from src.api.v1 import main as main_module
from src.intelligence.salvage_workflow_engine import SalvageWorkflowEngine


def test_salvage_api_ingests_listing_and_returns_plan(tmp_path):
    workflow = SalvageWorkflowEngine(tmp_path / "inventory.json")
    user = {"user_id": "user-1"}

    response = main_module.salvage_ingest_listing(
        {
            "id": "lot-1",
            "title": "ESP32 relay lot",
            "price_usd": 5.0,
            "expected_capabilities": ["wireless", "actuator_driver", "power"],
            "expected_parts": ["esp32", "relay"],
        },
        commit=True,
        current_user=user,
        workflow=workflow,
    )

    assert response["metadata"]["committed"] is True
    assert response["result"]["inventory_size"] == 1

    plan = main_module.salvage_workflow_plan(current_user=user, workflow=workflow)
    assert plan["report"]["inventory"]["asset_count"] == 1
    assert plan["metadata"]["user_id"] == "user-1"


def test_salvage_api_records_test_result(tmp_path):
    workflow = SalvageWorkflowEngine(tmp_path / "inventory.json")
    created = workflow.ingest_listing(
        {
            "title": "ESP32 module",
            "price_usd": 2.0,
            "expected_capabilities": ["wireless"],
            "expected_parts": ["esp32"],
        }
    )
    asset_id = created["created_asset"]["asset_id"]

    response = main_module.salvage_record_test_result(
        asset_id,
        {"test_status": "passed_boot", "condition": "working", "notes": "boots at 3.3V"},
        current_user={"user_id": "user-1"},
        workflow=workflow,
    )

    assert response["result"]["updated"]["test_status"] == "passed_boot"
    assert response["result"]["updated"]["condition"] == "working"


def test_salvage_pipeline_api_runs_listing_only(tmp_path):
    workflow = SalvageWorkflowEngine(tmp_path / "inventory.json")

    response = main_module.salvage_pipeline(
        files=None,
        listings='{"title":"ESP32 sensor lot","price_usd":8,"expected_capabilities":["controller","wireless","sensor_or_adc"],"expected_parts":["esp32","bme280"]}',
        backend="hybrid",
        enable_ocr=True,
        commit=False,
        current_user={"user_id": "user-1"},
        analyzer=None,
        workflow=workflow,
    )

    assert response["build_package"]["mode"] == "salvage_build_package"
    assert response["metadata"]["listing_count"] == 1
    assert response["metadata"]["committed"] is False
    assert "Salvage-To-Product Report" in response["markdown_report"]
