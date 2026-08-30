from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

import hardware_splicer.mechanical_brep_mesh as brep_mesh
from hardware_splicer.product_api import create_product_app


STEP = """ISO-10303-21;
HEADER;
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));
ENDSEC;
DATA;
#1=PRODUCT('fixture','Fixture','',());
#2=SI_UNIT(.MILLI.,.METRE.);
#3=CARTESIAN_POINT('',(0.0,0.0,0.0));
#4=CARTESIAN_POINT('',(10.0,10.0,10.0));
ENDSEC;
END-ISO-10303-21;
"""


def _hash(content: str = STEP) -> str:
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def _request() -> dict:
    return {
        "project_id": "mesh-api",
        "source": {
            "source_id": "fixture.step",
            "model_id": "fixture",
            "content_hash": _hash(),
            "content": STEP,
        },
        "placement": {
            "placement_id": "place-fixture",
            "object_id": "fixture-object",
            "model_id": "fixture",
            "target_frame": "assembly",
            "translation_mm": [20.0, 0.0, 0.0],
            "rotation_deg_xyz": [0.0, 0.0, 0.0],
            "authority": "declared",
        },
        "tolerance_mm": 0.5,
        "angular_tolerance_rad": 0.1,
    }


def test_product_mounts_bounded_brep_render_mesh_surface() -> None:
    app = create_product_app()
    paths = set(app.openapi()["paths"])
    assert "/v1/engineering/mechanical/geometry/brep/mesh" in paths
    assert "/v1/engineering/mechanical/geometry/brep/mesh/schema" in paths

    body = TestClient(app).get(
        "/v1/engineering/mechanical/geometry/brep/mesh/schema"
    ).json()
    assert body["optional_kernel"] == "cadquery-isolated"
    assert body["maximum_vertices"] == 25_000
    assert body["maximum_triangles"] == 50_000
    assert body["hash_bound_inline_source_supported"] is True
    assert body["declared_placement_supported"] is True
    assert body["placement_transform_convention"] == "Rz*Ry*Rx; canonical STEP XYZ"
    assert body["render_evidence_only"] is True
    assert body["physical_measurement"] is False
    assert body["fabrication_authorized"] is False


def test_mesh_route_returns_unknown_without_optional_kernel_and_preserves_placement_identity(monkeypatch) -> None:
    monkeypatch.setattr(brep_mesh, "_cadquery_available", lambda: False)
    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/mesh",
        json=_request(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["kernel_available"] is False
    assert body["exact_brep_mesh_evaluated"] is False
    assert body["declared_placement_applied"] is True
    assert body["vertex_count"] == 0
    assert body["triangle_count"] == 0
    assert body["raw_step_bytes_returned"] is False
    assert body["render_evidence_only"] is True
    assert body["fabrication_authorized"] is False
    report = body["brep_mesh"]
    assert report["status"] == "unknown"
    assert report["frame_id"] == "assembly"
    assert report["placement_id"] == "place-fixture"
    assert report["vertices_mm"] == []
    assert report["triangles"] == []
    assert report["required_evidence"][0]["field"] == "cadquery-isolated"


def test_mesh_route_rejects_changed_bytes_against_parser_issued_hash_before_kernel(monkeypatch) -> None:
    monkeypatch.setattr(
        brep_mesh,
        "_cadquery_available",
        lambda: (_ for _ in ()).throw(AssertionError("kernel discovery must not run after hash mismatch")),
    )
    request = _request()
    request["source"]["content"] = STEP.replace("(10.0,10.0,10.0)", "(11.0,10.0,10.0)")

    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/mesh",
        json=request,
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["type"] == "invalid_brep_mesh_request"
    assert "expected canonical content_hash" in detail["message"]


def test_mesh_route_rejects_placement_model_identity_mismatch() -> None:
    request = _request()
    request["placement"]["model_id"] = "wrong"

    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/mesh",
        json=request,
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["type"] == "invalid_brep_mesh_request"
    assert "mesh placement targets model 'wrong'" in detail["message"]
