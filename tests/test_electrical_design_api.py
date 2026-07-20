from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.electrical_design_api import create_electrical_design_router
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def machine_payload() -> dict:
    return {
        "project_id": "robot",
        "name": "Inspection robot",
        "purpose": "Inspect a building",
        "subsystems": [
            {
                "subsystem_id": "electrical",
                "name": "Electrical",
                "domain": "electrical",
                "component_ids": ["battery", "controller"],
                "interface_ids": ["battery-power"],
            }
        ],
        "components": [
            {
                "component_id": "battery",
                "name": "Battery",
                "domain": "electrical",
                "subsystem_id": "electrical",
                "authority": "declared",
                "metadata": {
                    "reference": "BT1",
                    "electrical_pins": [
                        {
                            "number": "1",
                            "name": "POS",
                            "electrical_type": "power_out",
                            "max_current_a": 3.0,
                        }
                    ],
                },
            },
            {
                "component_id": "controller",
                "name": "Controller",
                "domain": "firmware",
                "subsystem_id": "electrical",
                "authority": "declared",
                "metadata": {
                    "reference": "U1",
                    "electrical_pins": [
                        {
                            "number": "1",
                            "name": "VIN",
                            "electrical_type": "power_in",
                            "required": True,
                        }
                    ],
                },
            },
        ],
        "interfaces": [
            {
                "interface_id": "battery-power",
                "name": "Battery power",
                "kind": "power",
                "endpoints": [
                    {"object_id": "battery", "port": "POS"},
                    {"object_id": "controller", "port": "VIN"},
                ],
                "contracts": [
                    {
                        "contract_type": "electrical",
                        "values": {"nominal_voltage_v": 12.0, "peak_current_a": 2.0},
                        "authority": "declared",
                    }
                ],
                "authority": "declared",
            }
        ],
    }


def standalone_client() -> TestClient:
    app = FastAPI()
    app.include_router(create_electrical_design_router())
    return TestClient(app)


def test_machine_projection_api_returns_pin_level_design_and_erc() -> None:
    response = standalone_client().post(
        "/v1/electrical-designs/from-machine-project",
        json={"project": machine_payload()},
    )

    assert response.status_code == 200
    body = response.json()
    assert {row["pin_id"] for row in body["design"]["pins"]} == {"battery:1", "controller:1"}
    assert body["design"]["nets"][0]["pin_ids"] == ["battery:1", "controller:1"]
    assert body["erc"]["clean"] is True
    assert body["erc"]["error_count"] == 0


def test_erc_api_reports_driver_conflict() -> None:
    projected = standalone_client().post(
        "/v1/electrical-designs/from-machine-project",
        json={"project": machine_payload()},
    ).json()["design"]
    projected["pins"][1]["electrical_type"] = "power_out"

    response = standalone_client().post(
        "/v1/electrical-designs/erc",
        json={"design": projected},
    )

    assert response.status_code == 200
    assert "multiple_drivers" in {row["code"] for row in response.json()["erc"]["issues"]}


def test_product_app_mounts_electrical_design_router(tmp_path) -> None:
    client = TestClient(create_product_app(ProjectStore(tmp_path)))
    response = client.get("/v1/electrical-designs/schema")

    assert response.status_code == 200
    assert response.json()["schema"]["properties"]["schema_version"]["default"] == "hardware_splicer.electrical_design.v1"
