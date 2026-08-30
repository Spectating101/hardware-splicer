from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app


def _anchor(
    anchor_id: str,
    object_id: str,
    point: list[float],
    normal: list[float],
    *,
    hash_char: str,
    interface_id: str = "if-display",
) -> dict:
    return {
        "anchor_id": anchor_id,
        "interface_id": interface_id,
        "object_id": object_id,
        "source_id": f"{object_id}.step",
        "model_id": f"model-{object_id}",
        "content_hash": f"sha256:{hash_char * 64}",
        "placement_id": f"place-{object_id}",
        "frame_id": "assembly",
        "anchor_point_mm": point,
        "outward_normal": normal,
        "face_index": 1,
        "face_geom_type": "PLANE",
        "authority": "declared",
        "status": "ready",
        "kernel_surface_snap": True,
        "connector_mating_verified": False,
        "physical_measurement": False,
        "fabrication_authorized": False,
    }


def _request() -> dict:
    return {
        "project_id": "deck-001",
        "mating_id": "mate-if-display",
        "first_anchor": _anchor("anchor-board", "board", [0, 0, 0], [1, 0, 0], hash_char="a"),
        "second_anchor": _anchor("anchor-display", "display", [0.2, 0.1, 0], [-1, 0, 0], hash_char="b"),
        "requirements": {
            "max_normal_opposition_error_deg": 5,
            "max_lateral_offset_mm": 0.5,
            "target_axial_offset_mm": 0,
            "axial_offset_tolerance_mm": 0.5,
        },
    }


def test_product_mounts_brep_anchor_mating_surface() -> None:
    app = create_product_app()
    paths = set(app.openapi()["paths"])
    assert "/v1/engineering/mechanical/geometry/brep/mating" in paths
    assert "/v1/engineering/mechanical/geometry/brep/mating/schema" in paths

    body = TestClient(app).get(
        "/v1/engineering/mechanical/geometry/brep/mating/schema"
    ).json()
    assert body["requires_ready_exact_surface_anchors"] is True
    assert body["same_interface_required"] is True
    assert body["common_frame_required"] is True
    assert body["normal_opposition_evaluated"] is True
    assert body["coaxiality_requires_declared_axis"] is True
    assert body["engagement_depth_kernel_inferred"] is False
    assert body["connector_mating_verified"] is False
    assert body["fabrication_authorized"] is False


def test_mating_api_passes_only_declared_geometry_tolerance() -> None:
    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/mating",
        json=_request(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["mating_geometry_evaluated"] is True
    assert body["geometric_mating_passed"] is True
    assert body["common_frame"] is True
    assert body["geometric_mating_only"] is True
    assert body["connector_mating_verified"] is False
    assert body["protocol_compatibility_verified"] is False
    assert body["pin_compatibility_verified"] is False
    assert body["fabrication_authorized"] is False
    report = body["brep_anchor_mating"]
    assert report["status"] == "ready"
    assert report["interface_id"] == "if-display"
    assert report["normal_opposition_error_deg"] == 0
    assert report["signed_axial_offset_mm"] == 0.2
    assert report["lateral_offset_mm"] == 0.1
    assert report["metadata"]["connector_mating_verified"] is False


def test_mating_api_keeps_missing_required_engagement_unknown() -> None:
    request = _request()
    request["requirements"]["required_engagement_depth_mm"] = 4.0
    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/mating",
        json=request,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mating_geometry_evaluated"] is False
    assert body["geometric_mating_passed"] is None
    report = body["brep_anchor_mating"]
    assert report["status"] == "unknown"
    assert report["required_evidence"][0]["field"] == "declared_engagement_depth_mm"
    assert body["connector_mating_verified"] is False


def test_mating_api_rejects_cross_interface_pair() -> None:
    request = _request()
    request["second_anchor"]["interface_id"] = "if-power"
    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/mating",
        json=request,
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["type"] == "invalid_brep_anchor_mating_request"
    assert "same interface_id" in detail["message"]


def test_mating_api_rejects_promoted_or_non_kernel_anchor_input() -> None:
    request = _request()
    request["first_anchor"]["connector_mating_verified"] = True
    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/mating",
        json=request,
    )
    assert response.status_code == 422

    request = _request()
    request["first_anchor"]["kernel_surface_snap"] = False
    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/mating",
        json=request,
    )
    assert response.status_code == 422
