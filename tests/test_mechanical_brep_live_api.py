from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app


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


def test_real_brep_api_reproduces_fail_25_pass_15_when_specialist_is_installed(tmp_path) -> None:
    cq = pytest.importorskip("cadquery", reason="optional cadquery-isolated specialist is not installed")
    step_path = tmp_path / "clearance-box.step"
    cq.exporters.export(cq.Workplane("XY").box(10.0, 10.0, 10.0), str(step_path))
    step_content = step_path.read_text(encoding="utf-8")

    request = {
        "project_id": "brep-live-api",
        "first_source": {
            "source_id": "left-box.step",
            "model_id": "left-box",
            "content": step_content,
        },
        "second_source": {
            "source_id": "right-box.step",
            "model_id": "right-box",
            "content": step_content,
        },
        "first_placement": _placement("place-left", "left-box-object", "left-box", 0.0),
        "second_placement": _placement("place-right", "right-box-object", "right-box", 30.0),
        "minimum_clearance_mm": 25.0,
    }
    client = TestClient(create_product_app())

    failed = client.post(
        "/v1/engineering/mechanical/geometry/brep/interference",
        json=request,
    )
    assert failed.status_code == 200, failed.text
    failed_body = failed.json()
    assert failed_body["kernel_available"] is True
    assert failed_body["exact_pair_interference_evaluated"] is True
    assert failed_body["exact_solid_interference"] is False
    assert failed_body["minimum_distance_mm"] == pytest.approx(20.0, rel=1e-6, abs=1e-6)
    assert failed_body["exact_minimum_clearance_evaluated"] is True
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
    assert passed_body["minimum_distance_mm"] == pytest.approx(20.0, rel=1e-6, abs=1e-6)
    assert passed_body["exact_minimum_clearance_evaluated"] is True
    assert passed_body["minimum_clearance_requirement_mm"] == 15.0
    assert passed_body["minimum_clearance_passed"] is True
    assert passed_body["minimum_clearance_message"] == (
        "Exact BREP minimum distance 20.000 mm meets the 15.000 mm requirement."
    )
    assert passed_body["aabb_fallback_used"] is False
    assert passed_body["full_brep_collision"] is False
    assert passed_body["connector_mating_verified"] is False
    assert passed_body["cable_routing_verified"] is False
    assert passed_body["service_access_verified"] is False
    assert passed_body["fabrication_authorized"] is False
