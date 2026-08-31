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
from hardware_splicer.workbench_anchor_intent_api import WORKBENCH_ANCHOR_INTENTS_FIELD
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

STEP_REPLACEMENT = STEP.replace("fixture','Fixture", "fixture-v2','Fixture V2").replace(
    "(10.0,8.0,6.0)", "(12.0,8.0,6.0)"
)


def _project_with_placement(tmp_path: Path) -> tuple[ProjectStore, dict, TestClient]:
    project_id = "workbench-anchor-intent"
    store = ProjectStore(tmp_path)
    store.save(
        project_id,
        {"projectId": project_id, "projectName": "Anchor intent fixture", "engineeringSources": []},
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
    placement = client.post(
        f"/v1/projects/{project_id}/workbench/placements",
        json={
            "expected_revision": 3,
            "candidate_id": "balanced",
            "resource_id": "display",
            "entity_id": "cmp-display",
            "source_id": source["source_id"],
            "model_id": source["source_id"],
            "content_hash": source["content_hash"],
            "placement_id": "placement-balanced-display",
            "target_frame": "assembly",
            "translation_mm": [12.0, -5.0, 3.0],
            "rotation_deg_xyz": [0.0, 0.0, 90.0],
            "authority": "declared",
        },
    )
    assert placement.status_code == 201, placement.text
    assert placement.json()["revision"] == 4
    return store, source, client


def _intent(source: dict, *, revision: int, probe: list[float] | None = None) -> dict:
    return {
        "expected_revision": revision,
        "candidate_id": "balanced",
        "resource_id": "display",
        "entity_id": "cmp-display",
        "interface_id": "if-display",
        "anchor_id": "anchor-balanced-cmp-display-if-display",
        "source_id": source["source_id"],
        "model_id": source["source_id"],
        "content_hash": source["content_hash"],
        "placement_id": "placement-balanced-display",
        "target_frame": "assembly",
        "translation_mm": [12.0, -5.0, 3.0],
        "rotation_deg_xyz": [0.0, 0.0, 90.0],
        "probe_point_mm": probe or [17.1, -1.0, 6.0],
        "max_snap_distance_mm": 5.0,
        "authority": "declared",
    }


def test_product_mounts_durable_anchor_intent_surface() -> None:
    app = create_product_app()
    paths = set(app.openapi()["paths"])
    assert "/v1/engineering/workbench/anchor-intents/schema" in paths
    assert "/v1/projects/{project_id}/workbench/anchor-intents" in paths
    assert "/v1/projects/{project_id}/workbench/anchor-intents/clear" in paths

    body = TestClient(app).get("/v1/engineering/workbench/anchor-intents/schema").json()
    assert body["project_snapshot_field"] == WORKBENCH_ANCHOR_INTENTS_FIELD
    assert body["registered_source_binding_required"] is True
    assert body["durable_placement_required"] is True
    assert body["registered_source_hash_reverified_before_write"] is True
    assert body["probe_intent_only"] is True
    assert body["kernel_result_persisted"] is False
    assert body["face_identity_persisted"] is False
    assert body["surface_normal_persisted"] is False
    assert body["requires_occt_resnap_on_reopen"] is True
    assert body["physical_authority_unchanged"] is True


def test_anchor_intent_persists_probe_not_kernel_surface_output(tmp_path: Path) -> None:
    store, source, client = _project_with_placement(tmp_path)
    response = client.post(
        "/v1/projects/workbench-anchor-intent/workbench/anchor-intents",
        json=_intent(source, revision=4),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["registered"] is True
    assert body["revision"] == 5
    assert body["registered_source_hash_reverified"] is True
    assert body["kernel_result_persisted"] is False

    row = store.load("workbench-anchor-intent")["snapshot"][WORKBENCH_ANCHOR_INTENTS_FIELD][0]
    assert row["interface_id"] == "if-display"
    assert row["probe_point_mm"] == [17.1, -1.0, 6.0]
    assert row["placement_id"] == "placement-balanced-display"
    assert row["translation_mm"] == [12.0, -5.0, 3.0]
    assert row["rotation_deg_xyz"] == [0.0, 0.0, 90.0]
    assert row["requires_occt_resnap_on_reopen"] is True
    assert row["kernel_result_persisted"] is False
    assert row["face_identity_persisted"] is False
    assert row["anchor_point_persisted"] is False
    assert row["surface_normal_persisted"] is False
    assert "face_index" not in row
    assert "anchor_point_mm" not in row
    assert "outward_normal" not in row
    assert "snap_distance_mm" not in row
    assert row["connector_mating_verified"] is False
    assert row["physical_measurement"] is False
    assert row["fabrication_authorized"] is False

    duplicate = client.post(
        "/v1/projects/workbench-anchor-intent/workbench/anchor-intents",
        json=_intent(source, revision=5),
    )
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["registered"] is False
    assert duplicate.json()["revision"] == 5


def test_anchor_intent_requires_exact_current_durable_pose_and_blob(tmp_path: Path) -> None:
    store, source, client = _project_with_placement(tmp_path)

    stale_pose = _intent(source, revision=4)
    stale_pose["translation_mm"] = [13.0, -5.0, 3.0]
    response = client.post(
        "/v1/projects/workbench-anchor-intent/workbench/anchor-intents",
        json=stale_pose,
    )
    assert response.status_code == 422, response.text
    assert "translation disagrees" in response.json()["detail"]["message"]
    assert WORKBENCH_ANCHOR_INTENTS_FIELD not in store.load("workbench-anchor-intent")["snapshot"]

    blob_ref = source["metadata"]["blob_ref"]
    blob_path = tmp_path / "workbench-anchor-intent" / blob_ref
    blob_path.write_bytes(STEP.replace("(10.0,8.0,6.0)", "(11.0,8.0,6.0)").encode("utf-8"))
    response = client.post(
        "/v1/projects/workbench-anchor-intent/workbench/anchor-intents",
        json=_intent(source, revision=4),
    )
    assert response.status_code == 422, response.text
    assert "content_hash" in response.json()["detail"]["message"]


def test_placement_change_and_clear_invalidate_dependent_anchor_intent(tmp_path: Path) -> None:
    store, source, client = _project_with_placement(tmp_path)
    created = client.post(
        "/v1/projects/workbench-anchor-intent/workbench/anchor-intents",
        json=_intent(source, revision=4),
    )
    assert created.status_code == 201, created.text

    changed = client.post(
        "/v1/projects/workbench-anchor-intent/workbench/placements",
        json={
            "expected_revision": 5,
            "candidate_id": "balanced",
            "resource_id": "display",
            "entity_id": "cmp-display",
            "source_id": source["source_id"],
            "model_id": source["source_id"],
            "content_hash": source["content_hash"],
            "placement_id": "placement-balanced-display",
            "target_frame": "assembly",
            "translation_mm": [20.0, -5.0, 3.0],
            "rotation_deg_xyz": [0.0, 0.0, 90.0],
            "authority": "declared",
        },
    )
    assert changed.status_code == 201, changed.text
    assert changed.json()["anchor_intents_invalidated"] == 1
    assert store.load("workbench-anchor-intent")["snapshot"][WORKBENCH_ANCHOR_INTENTS_FIELD] == []

    recreated = client.post(
        "/v1/projects/workbench-anchor-intent/workbench/anchor-intents",
        json={**_intent(source, revision=6), "translation_mm": [20.0, -5.0, 3.0]},
    )
    assert recreated.status_code == 201, recreated.text

    cleared = client.post(
        "/v1/projects/workbench-anchor-intent/workbench/placements/clear",
        json={
            "expected_revision": 7,
            "candidate_id": "balanced",
            "resource_id": "display",
            "entity_id": "cmp-display",
            "source_id": source["source_id"],
            "model_id": source["source_id"],
            "content_hash": source["content_hash"],
            "placement_id": "placement-balanced-display",
        },
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["anchor_intents_invalidated"] == 1
    snapshot = store.load("workbench-anchor-intent")["snapshot"]
    assert snapshot[WORKBENCH_PLACEMENTS_FIELD] == []
    assert snapshot[WORKBENCH_ANCHOR_INTENTS_FIELD] == []


def test_anchor_intent_clear_is_revisioned_and_identity_bound(tmp_path: Path) -> None:
    store, source, client = _project_with_placement(tmp_path)
    created = client.post(
        "/v1/projects/workbench-anchor-intent/workbench/anchor-intents",
        json=_intent(source, revision=4),
    )
    assert created.status_code == 201, created.text

    clear_body = {
        key: value
        for key, value in _intent(source, revision=5).items()
        if key not in {"target_frame", "translation_mm", "rotation_deg_xyz", "probe_point_mm", "max_snap_distance_mm", "authority"}
    }
    stale = dict(clear_body)
    stale["interface_id"] = "if-other"
    response = client.post(
        "/v1/projects/workbench-anchor-intent/workbench/anchor-intents/clear",
        json=stale,
    )
    assert response.status_code == 422, response.text
    assert store.load("workbench-anchor-intent")["revision"] == 5

    response = client.post(
        "/v1/projects/workbench-anchor-intent/workbench/anchor-intents/clear",
        json=clear_body,
    )
    assert response.status_code == 200, response.text
    assert response.json()["cleared"] is True
    assert response.json()["revision"] == 6
    assert store.load("workbench-anchor-intent")["snapshot"][WORKBENCH_ANCHOR_INTENTS_FIELD] == []
