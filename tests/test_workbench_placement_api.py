from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from hardware_splicer.engineering_source_ingestion import (
    EngineeringSourceIngestionRequest,
    ingest_engineering_source,
)
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.workbench_placement_api import WORKBENCH_PLACEMENTS_FIELD


STEP = """ISO-10303-21;
HEADER;
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));
ENDSEC;
DATA;
#1=PRODUCT('fixture','Fixture','',());
#2=SI_UNIT(.MILLI.,.METRE.);
#3=CARTESIAN_POINT('',(0.0,0.0,0.0));
#4=CARTESIAN_POINT('',(10.0,8.0,6.0));
ENDSEC;
END-ISO-10303-21;
"""


def _project_with_binding(tmp_path: Path) -> tuple[ProjectStore, dict, TestClient]:
    project_id = "workbench-placement"
    store = ProjectStore(tmp_path)
    store.save(
        project_id,
        {"projectId": project_id, "projectName": "Placement fixture", "engineeringSources": []},
        expected_revision=0,
        metadata={"source": "test"},
    )
    result = ingest_engineering_source(
        EngineeringSourceIngestionRequest(
            project_id=project_id,
            filename="fixture.step",
            content_base64=base64.b64encode(STEP.encode("utf-8")).decode("ascii"),
        ),
        project_root=tmp_path,
    )
    source = result.source_descriptor
    snapshot = store.load(project_id)["snapshot"]
    snapshot["engineeringSources"] = [source]
    store.save(project_id, snapshot, expected_revision=1, metadata={"source": "registered_step_source"})
    client = TestClient(create_product_app(store))
    binding = client.post(
        f"/v1/projects/{project_id}/workbench/step-bindings",
        json={
            "expected_revision": 2,
            "candidate_id": "balanced",
            "resource_id": "display",
            "entity_id": "cmp-display",
            "source_id": source["source_id"],
            "model_id": source["source_id"],
            "content_hash": source["content_hash"],
        },
    )
    assert binding.status_code == 201, binding.text
    assert binding.json()["revision"] == 3
    return store, source, client


def _placement(source: dict, *, revision: int, x: float = 12.0) -> dict:
    return {
        "expected_revision": revision,
        "candidate_id": "balanced",
        "resource_id": "display",
        "entity_id": "cmp-display",
        "source_id": source["source_id"],
        "model_id": source["source_id"],
        "content_hash": source["content_hash"],
        "placement_id": "placement-balanced-display",
        "target_frame": "assembly",
        "translation_mm": [x, -5.0, 3.0],
        "rotation_deg_xyz": [0.0, 0.0, 90.0],
        "authority": "declared",
    }


def test_product_mounts_durable_workbench_placement_surface() -> None:
    app = create_product_app()
    paths = set(app.openapi()["paths"])
    assert "/v1/engineering/workbench/placements/schema" in paths
    assert "/v1/projects/{project_id}/workbench/placements" in paths
    assert "/v1/projects/{project_id}/workbench/placements/clear" in paths

    body = TestClient(app).get("/v1/engineering/workbench/placements/schema").json()
    assert body["project_snapshot_field"] == WORKBENCH_PLACEMENTS_FIELD
    assert body["registered_source_binding_required"] is True
    assert body["registered_source_hash_reverified_before_write"] is True
    assert body["declared_transform_only"] is True
    assert body["derived_aabb_persisted"] is False
    assert body["brep_mesh_persisted"] is False
    assert body["surface_anchor_persisted"] is False
    assert body["physical_authority_unchanged"] is True


def test_declared_placement_persists_only_source_bound_transform_intent(tmp_path: Path) -> None:
    store, source, client = _project_with_binding(tmp_path)
    response = client.post(
        "/v1/projects/workbench-placement/workbench/placements",
        json=_placement(source, revision=3),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["registered"] is True
    assert body["revision"] == 4
    assert body["registered_source_hash_reverified"] is True
    assert body["derived_geometry_persisted"] is False

    row = store.load("workbench-placement")["snapshot"][WORKBENCH_PLACEMENTS_FIELD][0]
    assert row["translation_mm"] == [12.0, -5.0, 3.0]
    assert row["rotation_deg_xyz"] == [0.0, 0.0, 90.0]
    assert row["authority"] == "declared"
    assert row["source_binding_required"] is True
    assert row["registered_source_hash_reverified"] is True
    assert row["derived_geometry_persisted"] is False
    assert "minimum_mm" not in row
    assert "maximum_mm" not in row
    assert "vertices_mm" not in row
    assert "anchor_point_mm" not in row
    assert row["fabrication_authorized"] is False

    duplicate = client.post(
        "/v1/projects/workbench-placement/workbench/placements",
        json=_placement(source, revision=4),
    )
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["registered"] is False
    assert duplicate.json()["revision"] == 4
    assert store.load("workbench-placement")["revision"] == 4


def test_placement_rejects_binding_identity_drift_and_tampered_blob(tmp_path: Path) -> None:
    store, source, client = _project_with_binding(tmp_path)
    wrong = _placement(source, revision=3)
    wrong["entity_id"] = "cmp-other"
    response = client.post(
        "/v1/projects/workbench-placement/workbench/placements",
        json=wrong,
    )
    assert response.status_code == 422, response.text
    assert "current resource binding" in response.json()["detail"]["message"]
    assert WORKBENCH_PLACEMENTS_FIELD not in store.load("workbench-placement")["snapshot"]

    blob_ref = source["metadata"]["blob_ref"]
    blob_path = tmp_path / "workbench-placement" / blob_ref
    blob_path.write_bytes(STEP.replace("(10.0,8.0,6.0)", "(11.0,8.0,6.0)").encode("utf-8"))
    response = client.post(
        "/v1/projects/workbench-placement/workbench/placements",
        json=_placement(source, revision=3),
    )
    assert response.status_code == 422, response.text
    assert "content_hash" in response.json()["detail"]["message"]


def test_clear_requires_current_placement_identity_and_advances_revision(tmp_path: Path) -> None:
    store, source, client = _project_with_binding(tmp_path)
    created = client.post(
        "/v1/projects/workbench-placement/workbench/placements",
        json=_placement(source, revision=3),
    )
    assert created.status_code == 201, created.text

    stale = {
        key: value
        for key, value in _placement(source, revision=4).items()
        if key not in {"target_frame", "translation_mm", "rotation_deg_xyz", "authority"}
    }
    stale["placement_id"] = "placement-stale"
    response = client.post(
        "/v1/projects/workbench-placement/workbench/placements/clear",
        json=stale,
    )
    assert response.status_code == 422, response.text
    assert store.load("workbench-placement")["revision"] == 4

    clear = dict(stale)
    clear["placement_id"] = "placement-balanced-display"
    response = client.post(
        "/v1/projects/workbench-placement/workbench/placements/clear",
        json=clear,
    )
    assert response.status_code == 200, response.text
    assert response.json()["cleared"] is True
    assert response.json()["revision"] == 5
    assert store.load("workbench-placement")["snapshot"][WORKBENCH_PLACEMENTS_FIELD] == []
