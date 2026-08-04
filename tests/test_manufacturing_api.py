from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app


def test_product_api_mounts_manufacturing_closure_routes() -> None:
    paths = set(create_product_app().openapi()["paths"])

    assert "/v1/engineering/manufacturing-closure" in paths
    assert "/v1/engineering/manufacturing-closure/schema" in paths


def test_manufacturing_endpoint_blocks_incomplete_release_inputs() -> None:
    client = TestClient(create_product_app())
    response = client.post(
        "/v1/engineering/manufacturing-closure",
        json={
            "plan": {
                "machine_project": {
                    "project_id": "incomplete-rover",
                    "metadata": {},
                    "discipline_payloads": {},
                }
            }
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "blocked"
    assert body["blocking_check_count"] > 0
    assert body["fabrication_authorized"] is False
    assert body["release_authorized"] is False


def test_manufacturing_endpoint_rejects_pin_map_conflict() -> None:
    client = TestClient(create_product_app())
    response = client.post(
        "/v1/engineering/manufacturing-closure",
        json={
            "plan": {
                "machine_project": {
                    "project_id": "pin-conflict",
                    "metadata": {},
                    "discipline_payloads": {},
                },
                "normalized_intake": {
                    "electrical_pins": [
                        {"component_id": "mcu", "pin": "gpio12", "net": "left_pwm"}
                    ],
                    "firmware_pin_map": [
                        {"component_id": "mcu", "physical_pin": "gpio12", "net": "right_pwm"}
                    ],
                    "connectors": [
                        {"connector_id": "j1", "mates_with": "p1"},
                        {"connector_id": "p1", "mates_with": "j1"},
                    ],
                    "harnesses": [
                        {
                            "harness_id": "h1",
                            "endpoints": ["j1", "p1"],
                            "conductors": [{"from_pin": "1", "to_pin": "1"}],
                        }
                    ],
                    "bom": [{"part_id": "mcu", "quantity": 1}],
                    "physical_instances": [{"part_id": "mcu", "quantity": 1}],
                    "fasteners": [{"fastener_id": "m3", "size": "M3"}],
                    "assembly_steps": [{"instruction": "Install the M3 fastener."}],
                    "mounts": [{"mount_id": "board", "cad_id": "board-step"}],
                    "cad_models": [{"cad_id": "board-step"}],
                    "fabrication_artifacts": [
                        {"artifact_id": "board", "revision": "r1", "content_hash": "sha256:board"}
                    ],
                },
                "candidate_revision": "r1",
            }
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    mismatch = next(
        row
        for row in body["manufacturing_closure"]["checks"]
        if row["check_id"] == "pin-mcu-gpio12"
    )
    assert mismatch["status"] == "fail"
    assert body["status"] == "blocked"
