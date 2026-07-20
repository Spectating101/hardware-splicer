from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.machine_project_api import create_machine_project_router


def project_payload() -> dict:
    return {
        "project_id": "robot",
        "name": "Inspection robot",
        "purpose": "Inspect a building",
        "subsystems": [
            {
                "subsystem_id": "power",
                "name": "Power",
                "domain": "electrical",
                "component_ids": ["battery"],
            }
        ],
        "components": [
            {
                "component_id": "battery",
                "name": "Battery",
                "domain": "electrical",
                "subsystem_id": "power",
                "authority": "declared",
            }
        ],
    }


def capture() -> dict:
    return {
        "schema_version": "bench_topology_capture.v1",
        "capture_id": "battery-capture",
        "operator_id": "tech-1",
        "instruments": [
            {
                "instrument_id": "dmm-1",
                "instrument_type": "calibrated_dmm",
                "calibration_status": "valid",
            }
        ],
        "measurements": [
            {
                "gate_id": "gate-battery",
                "kind": "voltage",
                "status": "pass",
                "value": 12.0,
                "unit": "V",
                "instrument_id": "dmm-1",
            }
        ],
    }


def client() -> TestClient:
    app = FastAPI()
    app.include_router(create_machine_project_router())
    return TestClient(app)


def test_bench_capture_api_returns_digest_pinned_reviewable_candidate() -> None:
    response = client().post(
        "/v1/machine-projects/from-bench-capture",
        json={
            "project": project_payload(),
            "capture": capture(),
            "target_map": {
                "gate-battery": {
                    "collection": "components",
                    "object_id": "battery",
                }
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project"]["components"][0]["authority"] == "measured"
    assert body["project"]["evidence"][0]["metadata"]["capture_sha256"] == body["bench_capture"]["capture_sha256"]
    assert body["bench_capture"]["imported_count"] == 1
    assert body["review_required"] is True


def test_bench_capture_api_refuses_unmapped_measurements() -> None:
    response = client().post(
        "/v1/machine-projects/from-bench-capture",
        json={"project": project_payload(), "capture": capture()},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "invalid_bench_capture_evidence"
    assert "produced no canonical evidence" in response.json()["detail"]["message"]
