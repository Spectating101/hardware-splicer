from __future__ import annotations

from fastapi.testclient import TestClient

import hardware_splicer.mechanical_brep as mechanical_brep
from hardware_splicer.product_api import create_product_app


STEP = """ISO-10303-21;
HEADER;
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));
ENDSEC;
DATA;
#1=PRODUCT('fixture','Fixture','',());
#2=SI_UNIT(.MILLI.,.METRE.);
#3=CARTESIAN_POINT('',(0.0,0.0,0.0));
#4=CARTESIAN_POINT('',(100.0,50.0,10.0));
ENDSEC;
END-ISO-10303-21;
"""


def _request() -> dict:
    return {
        "project_id": "brep-api",
        "first_source": {"source_id": "left.step", "model_id": "left", "content": STEP},
        "second_source": {"source_id": "right.step", "model_id": "right", "content": STEP},
        "first_placement": {
            "placement_id": "place-left",
            "object_id": "left-part",
            "model_id": "left",
            "target_frame": "assembly",
            "translation_mm": [0.0, 0.0, 0.0],
            "rotation_deg_xyz": [0.0, 0.0, 0.0],
            "authority": "declared",
        },
        "second_placement": {
            "placement_id": "place-right",
            "object_id": "right-part",
            "model_id": "right",
            "target_frame": "assembly",
            "translation_mm": [120.0, 0.0, 0.0],
            "rotation_deg_xyz": [0.0, 0.0, 0.0],
            "authority": "declared",
        },
    }


def test_product_mounts_optional_brep_pair_route_and_declares_scope() -> None:
    app = create_product_app()
    paths = set(app.openapi()["paths"])
    assert "/v1/engineering/mechanical/geometry/brep/interference" in paths

    client = TestClient(app)
    schema = client.get("/v1/engineering/mechanical/schema")
    assert schema.status_code == 200
    body = schema.json()
    assert body["optional_brep_kernel"] == "cadquery-isolated"
    assert body["exact_pair_brep_interference_when_kernel_available"] is True
    assert body["full_brep_collision"] is False
    assert "brep_pair_interference_request_schema" in body
    assert "brep_pair_interference_report_schema" in body


def test_brep_pair_route_returns_unknown_without_optional_kernel_and_never_falls_back(monkeypatch) -> None:
    monkeypatch.setattr(mechanical_brep, "_cadquery_available", lambda: False)
    client = TestClient(create_product_app())

    response = client.post(
        "/v1/engineering/mechanical/geometry/brep/interference",
        json=_request(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["kernel_available"] is False
    assert body["exact_pair_interference_evaluated"] is False
    assert body["exact_solid_interference"] is None
    assert body["minimum_distance_mm"] is None
    assert body["intersection_volume_mm3"] is None
    assert body["aabb_fallback_used"] is False
    assert body["full_brep_collision"] is False
    assert body["connector_mating_verified"] is False
    assert body["cable_routing_verified"] is False
    assert body["service_access_verified"] is False
    assert body["fabrication_authorized"] is False
    report = body["brep_interference"]
    assert report["status"] == "unknown"
    assert report["required_evidence"][0]["field"] == "cadquery-isolated"
    assert report["metadata"]["aabb_fallback_used"] is False
    assert report["metadata"]["specialist_capability"] == "cadquery-isolated"


def test_brep_pair_route_rejects_source_placement_identity_mismatch() -> None:
    client = TestClient(create_product_app())
    request = _request()
    request["first_placement"]["model_id"] = "wrong-model"

    response = client.post(
        "/v1/engineering/mechanical/geometry/brep/interference",
        json=request,
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["type"] == "invalid_brep_interference_request"
    assert "wrong-model" in detail["message"]


def test_brep_pair_route_rejects_authority_promotion_before_kernel_execution() -> None:
    client = TestClient(create_product_app())
    request = _request()
    request["first_placement"]["authority"] = "verified"

    response = client.post(
        "/v1/engineering/mechanical/geometry/brep/interference",
        json=request,
    )

    assert response.status_code == 422
