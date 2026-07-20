from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.electrical_design_api import create_electrical_design_router


def design_payload() -> dict:
    return {
        "design_id": "robot-electrical",
        "project_id": "robot",
        "components": [
            {
                "component_id": "controller",
                "reference": "U1",
                "name": "Controller",
                "pin_ids": ["controller-vin"],
            }
        ],
        "pins": [
            {
                "pin_id": "controller-vin",
                "component_id": "controller",
                "number": "1",
                "name": "VIN",
                "electrical_type": "power_in",
                "required": True,
            }
        ],
        "nets": [
            {"net_id": "vcc", "name": "VCC", "kind": "power"},
        ],
    }


def client() -> TestClient:
    app = FastAPI()
    app.include_router(create_electrical_design_router())
    return TestClient(app)


def test_edit_api_connects_pin_and_returns_erc_findings() -> None:
    response = client().post(
        "/v1/electrical-designs/edit",
        json={
            "design": design_payload(),
            "operations": [
                {
                    "type": "connect_pin",
                    "payload": {"pin_id": "controller-vin", "net_id": "vcc"},
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["design"]["pins"][0]["net_id"] == "vcc"
    assert body["design"]["nets"][0]["pin_ids"] == ["controller-vin"]
    assert {issue["code"] for issue in body["erc"]["issues"]} >= {
        "single_pin_net",
        "undriven_input_net",
        "power_without_source",
    }


def test_edit_api_rejects_verified_authoring() -> None:
    response = client().post(
        "/v1/electrical-designs/edit",
        json={
            "design": design_payload(),
            "operations": [
                {
                    "type": "upsert_pin",
                    "payload": {
                        "pin_id": "controller-vin",
                        "authority": "verified",
                    },
                }
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "invalid_electrical_edit"
    assert "cannot assign verified" in response.json()["detail"]["message"]
