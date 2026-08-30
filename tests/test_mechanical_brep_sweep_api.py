from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app


STEP = """ISO-10303-21;
HEADER;
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));
ENDSEC;
DATA;
#1=CARTESIAN_POINT('',(0.,0.,0.));
#2=CARTESIAN_POINT('',(10.,10.,10.));
ENDSEC;
END-ISO-10303-21;
"""


def _placement(placement_id: str, object_id: str, model_id: str, x_mm: float) -> dict:
    return {
        "placement_id": placement_id,
        "object_id": object_id,
        "model_id": model_id,
        "target_frame": "assembly",
        "translation_mm": [x_mm, 0.0, 0.0],
        "rotation_deg_xyz": [0.0, 0.0, 0.0],
        "authority": "declared",
    }


def _request() -> dict:
    return {
        "project_id": "deck-001",
        "sweep_id": "display-approach",
        "moving_source": {
            "source_id": "display.step",
            "model_id": "display-model",
            "content": STEP,
        },
        "fixed_source": {
            "source_id": "board.step",
            "model_id": "board-model",
            "content": STEP,
        },
        "moving_start_placement": _placement("display-start", "display-object", "display-model", 30.0),
        "moving_end_placement": _placement("display-end", "display-object", "display-model", 5.0),
        "fixed_placement": _placement("board-fixed", "board-object", "board-model", 0.0),
        "sample_count": 6,
        "engagement_start_fraction": 0.8,
        "contact_distance_tolerance_mm": 0.001,
    }


def test_product_mounts_brep_mating_path_surface() -> None:
    app = create_product_app()
    paths = set(app.openapi()["paths"])
    assert "/v1/engineering/mechanical/geometry/brep/mating-path" in paths
    assert "/v1/engineering/mechanical/geometry/brep/mating-path/schema" in paths

    body = TestClient(app).get(
        "/v1/engineering/mechanical/geometry/brep/mating-path/schema"
    ).json()
    assert body["translation_only_path"] is True
    assert body["exact_brep_per_sample"] is True
    assert body["contact_event_is_sampled_only"] is True
    assert body["declared_engagement_region_supported"] is True
    assert body["continuous_path_verified"] is False
    assert body["continuous_collision_free_verified"] is False
    assert body["connector_mating_verified"] is False
    assert body["whole_assembly_collision"] is False
    assert body["fabrication_authorized"] is False


def test_mating_path_api_fails_closed_without_optional_kernel() -> None:
    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/mating-path",
        json=_request(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    report = body["brep_mating_path"]
    if body["kernel_available"] is False:
        assert body["sampled_path_evaluated"] is False
        assert body["sampled_path_interference_free"] is None
        assert report["status"] == "unknown"
        assert report["required_evidence"][0]["field"] == "cadquery-isolated"
    else:
        # Specialist-enabled environments execute the same exact route rather than
        # substituting any AABB approximation.
        assert report["status"] in {"ready", "unknown"}
    assert body["aabb_fallback_used"] is False
    assert body["sampled_path_only"] is True
    assert body["continuous_path_verified"] is False
    assert body["connector_mating_verified"] is False
    assert body["whole_assembly_collision"] is False
    assert body["fabrication_authorized"] is False


def test_mating_path_api_rejects_promoted_or_rotating_placement() -> None:
    request = _request()
    request["moving_start_placement"]["authority"] = "verified"
    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/mating-path",
        json=request,
    )
    assert response.status_code == 422

    request = _request()
    request["moving_end_placement"]["rotation_deg_xyz"] = [0.0, 0.0, 10.0]
    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/mating-path",
        json=request,
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["type"] == "invalid_brep_mating_path_request"
    assert "translation-only" in detail["message"]


def test_mating_path_api_bounds_sample_count() -> None:
    request = _request()
    request["sample_count"] = 1
    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/mating-path",
        json=request,
    )
    assert response.status_code == 422

    request["sample_count"] = 34
    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/mating-path",
        json=request,
    )
    assert response.status_code == 422
