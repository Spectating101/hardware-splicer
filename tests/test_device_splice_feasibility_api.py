"""Splice feasibility is reachable through both product-facing HTTP surfaces."""
import json
from pathlib import Path
from fastapi.testclient import TestClient
from hardware_splicer.api import create_app
from hardware_splicer.product_api import create_product_app

FIXTURE = Path(__file__).resolve().parents[1] / "eval/device_splice_feasibility/controller_display_demo.json"

def test_engine_and_product_expose_same_splice_screen():
    candidate = json.loads(FIXTURE.read_text())
    for app in (create_app(), create_product_app()):
        client = TestClient(app)
        response = client.post("/v1/splice/feasibility", json=candidate)
        assert response.status_code == 200, response.text
        result = response.json()["assessment"]
        assert result["overall_status"] == "adaptable_pending_validation"
        assert not result["fabrication_authorized"]
        assert not result["power_on_authorized"]

def test_invalid_references_get_422_not_false_success():
    candidate = json.loads(FIXTURE.read_text())
    candidate["interfaces"][0]["from"] = "unidentified_part"
    response = TestClient(create_app()).post("/v1/splice/feasibility", json=candidate)
    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "invalid_splice_candidate"
