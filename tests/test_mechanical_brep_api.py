from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

import hardware_splicer.mechanical_api as mechanical_api
import hardware_splicer.mechanical_brep as mechanical_brep
from hardware_splicer.engineering_source_ingestion import (
    EngineeringSourceIngestionRequest,
    ingest_engineering_source,
)
from hardware_splicer.mechanical_brep import BrepPairInterferenceReport, BrepStatus
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


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

STEP_RIGHT = STEP.replace("'fixture','Fixture'", "'fixture-right','Fixture Right'").replace(
    "(100.0,50.0,10.0)", "(80.0,40.0,8.0)"
)


def _request() -> dict:
    return {
        "project_id": "brep-api",
        "first_source": {"source_id": "left.step", "model_id": "left", "content": STEP},
        "second_source": {"source_id": "right.step", "model_id": "right", "content": STEP_RIGHT},
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


def _exact_report(
    *,
    minimum_distance_mm: float = 20.0,
    interference: bool = False,
    intersection_volume_mm3: float = 0.0,
) -> BrepPairInterferenceReport:
    return BrepPairInterferenceReport(
        project_id="brep-api",
        first_source_id="left.step",
        second_source_id="right.step",
        first_model_id="left",
        second_model_id="right",
        first_content_hash=f"sha256:{'a' * 64}",
        second_content_hash=f"sha256:{'b' * 64}",
        frame_id="assembly",
        status=BrepStatus.INTERFERENCE if interference else BrepStatus.CLEAR,
        kernel_available=True,
        kernel="cadquery_occt",
        cadquery_version="test",
        first_shape_valid=True,
        second_shape_valid=True,
        first_solid_count=1,
        second_solid_count=1,
        minimum_distance_mm=minimum_distance_mm,
        intersection_volume_mm3=intersection_volume_mm3,
        exact_solid_interference=interference,
        exact_pair_interference_evaluated=True,
        metadata={"aabb_fallback_used": False},
    )


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _stored_project(tmp_path: Path, project_id: str = "brep-stored") -> tuple[ProjectStore, dict, dict]:
    store = ProjectStore(tmp_path)
    store.save(
        project_id,
        {
            "projectId": project_id,
            "projectName": "Stored STEP BREP",
            "engineeringSources": [],
        },
        expected_revision=0,
        metadata={"source": "test"},
    )
    first = ingest_engineering_source(
        EngineeringSourceIngestionRequest(
            project_id=project_id,
            filename="left.step",
            content_base64=_b64(STEP.encode("utf-8")),
        ),
        project_root=tmp_path,
    ).source_descriptor
    second = ingest_engineering_source(
        EngineeringSourceIngestionRequest(
            project_id=project_id,
            filename="right.step",
            content_base64=_b64(STEP_RIGHT.encode("utf-8")),
        ),
        project_root=tmp_path,
    ).source_descriptor
    snapshot = store.load(project_id)["snapshot"]
    snapshot["engineeringSources"] = [first, second]
    store.save(
        project_id,
        snapshot,
        expected_revision=1,
        metadata={"source": "test_registered_step_sources"},
    )
    return store, first, second


def _stored_request(first: dict, second: dict, project_id: str = "brep-stored") -> dict:
    request = _request()
    request["project_id"] = project_id
    request["first_source"] = {
        "source_id": first["source_id"],
        "content_hash": first["content_hash"],
        "model_id": "left",
    }
    request["second_source"] = {
        "source_id": second["source_id"],
        "content_hash": second["content_hash"],
        "model_id": "right",
    }
    return request


def test_product_mounts_optional_brep_pair_route_and_declares_scope() -> None:
    app = create_product_app()
    paths = set(app.openapi()["paths"])
    assert "/v1/engineering/mechanical/geometry/brep/interference" in paths
    assert "/v1/engineering/mechanical/geometry/brep/interference/stored" in paths

    client = TestClient(app)
    schema = client.get("/v1/engineering/mechanical/schema")
    assert schema.status_code == 200
    body = schema.json()
    assert body["optional_brep_kernel"] == "cadquery-isolated"
    assert body["exact_pair_brep_interference_when_kernel_available"] is True
    assert body["exact_pair_brep_minimum_clearance_when_kernel_available"] is True
    assert body["registered_source_brep_materialization"] == "content_addressed_hash_reverified_server_side"
    assert body["raw_registered_source_bytes_returned"] is False
    assert body["full_brep_collision"] is False
    assert "brep_pair_interference_request_schema" in body
    assert "stored_brep_pair_interference_request_schema" in body
    assert "brep_pair_interference_report_schema" in body


def test_brep_pair_route_returns_unknown_without_optional_kernel_and_never_falls_back(monkeypatch) -> None:
    monkeypatch.setattr(mechanical_brep, "_cadquery_available", lambda: False)
    client = TestClient(create_product_app())
    request = _request()
    request["minimum_clearance_mm"] = 25.0

    response = client.post(
        "/v1/engineering/mechanical/geometry/brep/interference",
        json=request,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["kernel_available"] is False
    assert body["exact_pair_interference_evaluated"] is False
    assert body["exact_solid_interference"] is None
    assert body["minimum_distance_mm"] is None
    assert body["intersection_volume_mm3"] is None
    assert body["exact_minimum_clearance_evaluated"] is False
    assert body["minimum_clearance_requirement_mm"] == 25.0
    assert body["minimum_clearance_passed"] is None
    assert "remains UNKNOWN" in body["minimum_clearance_message"]
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


def test_exact_brep_minimum_clearance_fails_25_and_passes_15_without_ui_math(monkeypatch) -> None:
    monkeypatch.setattr(
        mechanical_api,
        "check_step_brep_interference",
        lambda **_kwargs: _exact_report(minimum_distance_mm=20.0),
    )
    client = TestClient(create_product_app())

    request = _request()
    request["minimum_clearance_mm"] = 25.0
    failed = client.post(
        "/v1/engineering/mechanical/geometry/brep/interference",
        json=request,
    )
    assert failed.status_code == 200, failed.text
    failed_body = failed.json()
    assert failed_body["exact_pair_interference_evaluated"] is True
    assert failed_body["exact_minimum_clearance_evaluated"] is True
    assert failed_body["minimum_distance_mm"] == 20.0
    assert failed_body["minimum_clearance_requirement_mm"] == 25.0
    assert failed_body["minimum_clearance_passed"] is False
    assert failed_body["minimum_clearance_message"] == (
        "Exact BREP minimum distance 20.000 mm is below the 25.000 mm requirement."
    )

    request["minimum_clearance_mm"] = 15.0
    passed = client.post(
        "/v1/engineering/mechanical/geometry/brep/interference",
        json=request,
    )
    assert passed.status_code == 200, passed.text
    passed_body = passed.json()
    assert passed_body["exact_minimum_clearance_evaluated"] is True
    assert passed_body["minimum_clearance_passed"] is True
    assert passed_body["minimum_clearance_message"] == (
        "Exact BREP minimum distance 20.000 mm meets the 15.000 mm requirement."
    )
    assert passed_body["full_brep_collision"] is False
    assert passed_body["service_access_verified"] is False
    assert passed_body["fabrication_authorized"] is False


def test_exact_brep_interference_fails_even_zero_clearance_requirement(monkeypatch) -> None:
    monkeypatch.setattr(
        mechanical_api,
        "check_step_brep_interference",
        lambda **_kwargs: _exact_report(
            minimum_distance_mm=0.0,
            interference=True,
            intersection_volume_mm3=12.5,
        ),
    )
    client = TestClient(create_product_app())
    request = _request()
    request["minimum_clearance_mm"] = 0.0

    response = client.post(
        "/v1/engineering/mechanical/geometry/brep/interference",
        json=request,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["exact_solid_interference"] is True
    assert body["exact_minimum_clearance_evaluated"] is True
    assert body["minimum_clearance_passed"] is False
    assert "interfere by 12.500 mm^3" in body["minimum_clearance_message"]


def test_brep_pair_route_rejects_negative_exact_clearance_requirement() -> None:
    client = TestClient(create_product_app())
    request = _request()
    request["minimum_clearance_mm"] = -0.1

    response = client.post(
        "/v1/engineering/mechanical/geometry/brep/interference",
        json=request,
    )

    assert response.status_code == 422


def test_stored_brep_route_uses_injected_project_store_and_reverifies_registered_hashes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store, first, second = _stored_project(tmp_path)
    monkeypatch.setattr(mechanical_brep, "_cadquery_available", lambda: False)
    client = TestClient(create_product_app(store))
    request = _stored_request(first, second)
    request["minimum_clearance_mm"] = 25.0

    response = client.post(
        "/v1/engineering/mechanical/geometry/brep/interference/stored",
        json=request,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["registered_source_materialized"] is True
    assert body["registered_source_hash_reverified"] is True
    assert body["raw_registered_source_bytes_returned"] is False
    assert body["kernel_available"] is False
    assert body["exact_pair_interference_evaluated"] is False
    assert body["exact_minimum_clearance_evaluated"] is False
    assert body["minimum_clearance_requirement_mm"] == 25.0
    assert body["minimum_clearance_passed"] is None
    assert body["aabb_fallback_used"] is False
    report = body["brep_interference"]
    assert report["first_content_hash"] == first["content_hash"]
    assert report["second_content_hash"] == second["content_hash"]
    assert report["metadata"]["source_materialization"] == "registered_blob_hash_reverified_server_side"
    assert report["metadata"]["registered_raw_bytes_returned"] is False
    assert "content" not in body
    assert STEP not in response.text


def test_stored_brep_route_rejects_tampered_registered_blob_before_kernel_execution(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store, first, second = _stored_project(tmp_path)
    monkeypatch.setattr(
        mechanical_brep,
        "_cadquery_available",
        lambda: (_ for _ in ()).throw(AssertionError("kernel availability must not be queried after blob tamper")),
    )
    blob = tmp_path / "brep-stored" / first["metadata"]["blob_ref"]
    blob.write_bytes(b"tampered STEP bytes")
    client = TestClient(create_product_app(store))

    response = client.post(
        "/v1/engineering/mechanical/geometry/brep/interference/stored",
        json=_stored_request(first, second),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["type"] == "invalid_stored_brep_interference_request"
    assert "no longer matches its content_hash" in detail["message"]


def test_stored_brep_route_requires_exact_registered_source_identity(tmp_path: Path) -> None:
    store, first, second = _stored_project(tmp_path)
    request = _stored_request(first, second)
    request["first_source"]["content_hash"] = f"sha256:{'0' * 64}"
    client = TestClient(create_product_app(store))

    response = client.post(
        "/v1/engineering/mechanical/geometry/brep/interference/stored",
        json=request,
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["type"] == "invalid_stored_brep_interference_request"
    assert "was not found exactly once" in detail["message"]


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