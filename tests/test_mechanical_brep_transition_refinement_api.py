from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

import hardware_splicer.mechanical_brep_sweep as brep_sweep
import hardware_splicer.mechanical_brep_transition_refinement as brep_refinement
from hardware_splicer.engineering_source_ingestion import (
    EngineeringSourceIngestionRequest,
    ingest_engineering_source,
)
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


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


def _hash(content: str) -> str:
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


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
        "sweep_id": "display-approach-refine",
        "moving_source": {
            "source_id": "display.step",
            "model_id": "display-model",
            "content_hash": _hash(STEP),
            "content": STEP,
        },
        "fixed_source": {
            "source_id": "board.step",
            "model_id": "board-model",
            "content_hash": _hash(STEP),
            "content": STEP,
        },
        "moving_start_placement": _placement("display-start", "display-object", "display-model", 30.0),
        "moving_end_placement": _placement("display-end", "display-object", "display-model", 5.0),
        "fixed_placement": _placement("board-fixed", "board-object", "board-model", 0.0),
        "sample_count": 6,
        "engagement_start_fraction": 0.8,
        "contact_distance_tolerance_mm": 0.001,
        "refinement_max_depth": 8,
        "refinement_fraction_tolerance": 0.001,
    }


def _stored_project(tmp_path: Path) -> tuple[ProjectStore, dict, dict]:
    project_id = "deck-refine-stored"
    store = ProjectStore(tmp_path)
    store.save(
        project_id,
        {
            "projectId": project_id,
            "projectName": "Stored STEP mating path refinement",
            "engineeringSources": [],
        },
        expected_revision=0,
        metadata={"source": "test"},
    )
    descriptors: list[dict] = []
    for filename in ("display.step", "board.step"):
        result = ingest_engineering_source(
            EngineeringSourceIngestionRequest(
                project_id=project_id,
                filename=filename,
                content_base64=base64.b64encode(STEP.encode("utf-8")).decode("ascii"),
            ),
            project_root=tmp_path,
        )
        descriptors.append(result.source_descriptor)
    snapshot = store.load(project_id)["snapshot"]
    snapshot["engineeringSources"] = descriptors
    store.save(
        project_id,
        snapshot,
        expected_revision=1,
        metadata={"source": "registered_step_sources"},
    )
    return store, descriptors[0], descriptors[1]


def _stored_request(moving: dict, fixed: dict) -> dict:
    request = _request()
    request["project_id"] = "deck-refine-stored"
    request["moving_source"] = {
        "source_id": moving["source_id"],
        "model_id": "display-model",
        "content_hash": moving["content_hash"],
    }
    request["fixed_source"] = {
        "source_id": fixed["source_id"],
        "model_id": "board-model",
        "content_hash": fixed["content_hash"],
    }
    return request


def test_product_mounts_brep_mating_path_refinement_surface() -> None:
    app = create_product_app()
    paths = set(app.openapi()["paths"])
    assert "/v1/engineering/mechanical/geometry/brep/mating-path/refine" in paths
    assert "/v1/engineering/mechanical/geometry/brep/mating-path/refine/stored" in paths
    assert "/v1/engineering/mechanical/geometry/brep/mating-path/refine/schema" in paths

    body = TestClient(app).get(
        "/v1/engineering/mechanical/geometry/brep/mating-path/refine/schema"
    ).json()
    assert body["adaptive_transition_refinement"] is True
    assert body["transition_brackets_only"] is True
    assert body["refined_predicates"] == ["clearance_boundary", "interference_boundary"]
    assert body["max_total_pose_budget"] == 256
    assert body["timeout_budget_scope"] == "coarse_and_refinement_total"
    assert body["unique_transition_pose_verified"] is False
    assert body["monotonicity_inside_bracket_verified"] is False
    assert body["registered_source_materialization"] == "registered_blob_hash_reverified_server_side"
    assert body["raw_step_bytes_returned"] is False
    assert body["continuous_path_verified"] is False
    assert body["continuous_collision_free_verified"] is False
    assert body["connector_mating_verified"] is False
    assert body["whole_assembly_collision"] is False
    assert body["fabrication_authorized"] is False


def test_refinement_api_fails_closed_without_optional_kernel_and_never_uses_aabb(monkeypatch) -> None:
    monkeypatch.setattr(brep_sweep, "_cadquery_available", lambda: False)
    monkeypatch.setattr(brep_refinement, "_cadquery_available", lambda: False)
    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/mating-path/refine",
        json=_request(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    report = body["brep_mating_path_refinement"]
    assert body["kernel_available"] is False
    assert body["refinement_evaluated"] is False
    assert report["status"] == "unknown"
    assert report["required_evidence"]
    assert body["adaptive_transition_refinement"] is True
    assert body["transition_brackets_only"] is True
    assert body["unique_transition_pose_verified"] is False
    assert body["monotonicity_inside_bracket_verified"] is False
    assert body["aabb_fallback_used"] is False
    assert body["raw_step_bytes_returned"] is False
    assert body["max_total_pose_budget"] == 256
    assert body["continuous_path_verified"] is False
    assert body["continuous_collision_free_verified"] is False
    assert body["connector_mating_verified"] is False
    assert body["whole_assembly_collision"] is False
    assert body["fabrication_authorized"] is False


def test_stored_refinement_uses_shared_store_and_reverifies_both_registered_sources(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store, moving, fixed = _stored_project(tmp_path)
    monkeypatch.setattr(brep_sweep, "_cadquery_available", lambda: False)
    monkeypatch.setattr(brep_refinement, "_cadquery_available", lambda: False)

    response = TestClient(create_product_app(store)).post(
        "/v1/engineering/mechanical/geometry/brep/mating-path/refine/stored",
        json=_stored_request(moving, fixed),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["registered_sources_materialized"] is True
    assert body["registered_source_hashes_reverified"] is True
    assert body["moving_registered_source_hash_reverified"] is True
    assert body["fixed_registered_source_hash_reverified"] is True
    assert body["raw_registered_source_bytes_returned"] is False
    assert body["raw_step_bytes_returned"] is False
    report = body["brep_mating_path_refinement"]
    assert report["moving_content_hash"] == moving["content_hash"]
    assert report["fixed_content_hash"] == fixed["content_hash"]
    assert report["metadata"]["source_materialization"] == "registered_blob_hash_reverified_server_side"
    assert report["metadata"]["moving_registered_source_hash_reverified"] is True
    assert report["metadata"]["fixed_registered_source_hash_reverified"] is True
    assert STEP not in response.text


def test_stored_refinement_rejects_tampered_registered_blob_before_kernel_discovery(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store, moving, fixed = _stored_project(tmp_path)
    monkeypatch.setattr(
        brep_sweep,
        "_cadquery_available",
        lambda: (_ for _ in ()).throw(AssertionError("kernel discovery must not run after blob tamper")),
    )
    monkeypatch.setattr(
        brep_refinement,
        "_cadquery_available",
        lambda: (_ for _ in ()).throw(AssertionError("kernel discovery must not run after blob tamper")),
    )
    blob = tmp_path / "deck-refine-stored" / moving["metadata"]["blob_ref"]
    blob.write_bytes(b"tampered")

    response = TestClient(create_product_app(store)).post(
        "/v1/engineering/mechanical/geometry/brep/mating-path/refine/stored",
        json=_stored_request(moving, fixed),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["type"] == "invalid_stored_brep_mating_path_refinement_request"
    assert "no longer matches its content_hash" in detail["message"]


def test_refinement_api_rejects_stale_inline_source_hash_before_any_authority_promotion() -> None:
    request = _request()
    request["moving_source"]["content_hash"] = f"sha256:{'f' * 64}"
    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/mating-path/refine",
        json=request,
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["type"] == "invalid_brep_mating_path_refinement_request"
    assert "content_hash" in detail["message"]


def test_refinement_api_bounds_depth_and_fraction_tolerance() -> None:
    client = TestClient(create_product_app())

    request = _request()
    request["refinement_max_depth"] = 0
    assert client.post(
        "/v1/engineering/mechanical/geometry/brep/mating-path/refine", json=request
    ).status_code == 422

    request = _request()
    request["refinement_max_depth"] = 13
    assert client.post(
        "/v1/engineering/mechanical/geometry/brep/mating-path/refine", json=request
    ).status_code == 422

    request = _request()
    request["refinement_fraction_tolerance"] = 0.0000001
    assert client.post(
        "/v1/engineering/mechanical/geometry/brep/mating-path/refine", json=request
    ).status_code == 422

    request = _request()
    request["refinement_fraction_tolerance"] = 0.3
    assert client.post(
        "/v1/engineering/mechanical/geometry/brep/mating-path/refine", json=request
    ).status_code == 422


def test_refinement_api_rejects_requests_whose_worst_case_pose_budget_is_too_large() -> None:
    request = _request()
    request["sample_count"] = 33
    request["refinement_max_depth"] = 12

    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/mating-path/refine",
        json=request,
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["type"] == "invalid_brep_mating_path_refinement_request"
    assert "pose budget" in detail["message"]
    assert "reduce coarse sample_count or refinement_max_depth" in detail["message"]
