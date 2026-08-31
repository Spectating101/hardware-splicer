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
from hardware_splicer.workbench_step_binding_api import WORKBENCH_STEP_BINDINGS_FIELD


STEP = """ISO-10303-21;
HEADER;
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));
ENDSEC;
DATA;
#1=PRODUCT('shared-fixture','Shared Fixture','',());
#2=SI_UNIT(.MILLI.,.METRE.);
#3=CARTESIAN_POINT('',(0.0,0.0,0.0));
#4=CARTESIAN_POINT('',(10.0,8.0,6.0));
ENDSEC;
END-ISO-10303-21;
"""


def _registered_project(tmp_path: Path) -> tuple[ProjectStore, dict]:
    project_id = "workbench-bindings"
    store = ProjectStore(tmp_path)
    store.save(
        project_id,
        {
            "projectId": project_id,
            "projectName": "Workbench binding reuse",
            "engineeringSources": [],
        },
        expected_revision=0,
        metadata={"source": "test"},
    )
    result = ingest_engineering_source(
        EngineeringSourceIngestionRequest(
            project_id=project_id,
            filename="shared.step",
            content_base64=base64.b64encode(STEP.encode("utf-8")).decode("ascii"),
        ),
        project_root=tmp_path,
    )
    source = result.source_descriptor
    snapshot = store.load(project_id)["snapshot"]
    snapshot["engineeringSources"] = [source]
    store.save(
        project_id,
        snapshot,
        expected_revision=1,
        metadata={"source": "registered_step_source"},
    )
    return store, source


def _binding(source: dict, *, revision: int, resource_id: str, entity_id: str) -> dict:
    return {
        "expected_revision": revision,
        "candidate_id": "balanced",
        "resource_id": resource_id,
        "entity_id": entity_id,
        "source_id": source["source_id"],
        "model_id": source["source_id"],
        "content_hash": source["content_hash"],
    }


def test_product_mounts_durable_workbench_step_binding_surface() -> None:
    app = create_product_app()
    paths = set(app.openapi()["paths"])
    assert "/v1/engineering/workbench/step-bindings/schema" in paths
    assert "/v1/projects/{project_id}/workbench/step-bindings" in paths

    body = TestClient(app).get("/v1/engineering/workbench/step-bindings/schema").json()
    assert body["project_snapshot_field"] == WORKBENCH_STEP_BINDINGS_FIELD
    assert body["content_addressed_source_reuse_supported"] is True
    assert body["same_source_may_back_multiple_resource_occurrences"] is True
    assert body["registered_source_hash_reverified_before_binding"] is True
    assert body["raw_registered_source_bytes_returned"] is False
    assert body["source_binding_only"] is True
    assert body["physical_authority_unchanged"] is True
    assert body["automatic_authorization"] is False


def test_same_registered_step_blob_can_back_multiple_durable_resource_occurrences(tmp_path: Path) -> None:
    store, source = _registered_project(tmp_path)
    client = TestClient(create_product_app(store))

    first = client.post(
        "/v1/projects/workbench-bindings/workbench/step-bindings",
        json=_binding(source, revision=2, resource_id="display-left", entity_id="display-left-entity"),
    )
    assert first.status_code == 201, first.text
    first_body = first.json()
    assert first_body["registered"] is True
    assert first_body["revision"] == 3
    assert first_body["registered_source_hash_reverified"] is True
    assert first_body["raw_registered_source_bytes_returned"] is False

    second = client.post(
        "/v1/projects/workbench-bindings/workbench/step-bindings",
        json=_binding(source, revision=3, resource_id="display-right", entity_id="display-right-entity"),
    )
    assert second.status_code == 201, second.text
    second_body = second.json()
    assert second_body["registered"] is True
    assert second_body["revision"] == 4

    reloaded = store.load("workbench-bindings")
    snapshot = reloaded["snapshot"]
    assert reloaded["revision"] == 4
    assert len(snapshot["engineeringSources"]) == 1
    bindings = snapshot[WORKBENCH_STEP_BINDINGS_FIELD]
    assert len(bindings) == 2
    assert {row["resource_id"] for row in bindings} == {"display-left", "display-right"}
    assert {row["entity_id"] for row in bindings} == {"display-left-entity", "display-right-entity"}
    assert {row["source_id"] for row in bindings} == {source["source_id"]}
    assert {row["content_hash"] for row in bindings} == {source["content_hash"]}
    assert all(row["source_binding_only"] is True for row in bindings)
    assert all(row["physical_authority_unchanged"] is True for row in bindings)

    duplicate = client.post(
        "/v1/projects/workbench-bindings/workbench/step-bindings",
        json=_binding(source, revision=4, resource_id="display-right", entity_id="display-right-entity"),
    )
    assert duplicate.status_code == 201, duplicate.text
    duplicate_body = duplicate.json()
    assert duplicate_body["registered"] is False
    assert duplicate_body["revision"] == 4
    assert store.load("workbench-bindings")["revision"] == 4


def test_binding_rejects_tampered_registered_blob_before_persistence(tmp_path: Path) -> None:
    store, source = _registered_project(tmp_path)
    blob_ref = source["metadata"]["blob_ref"]
    blob_path = tmp_path / "workbench-bindings" / blob_ref
    blob_path.write_bytes(STEP.replace("(10.0,8.0,6.0)", "(11.0,8.0,6.0)").encode("utf-8"))

    response = TestClient(create_product_app(store)).post(
        "/v1/projects/workbench-bindings/workbench/step-bindings",
        json=_binding(source, revision=2, resource_id="display-left", entity_id="display-left-entity"),
    )
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["type"] == "invalid_workbench_step_binding"
    assert "content_hash" in detail["message"]
    assert WORKBENCH_STEP_BINDINGS_FIELD not in store.load("workbench-bindings")["snapshot"]


def test_binding_rejects_ambiguous_entity_reuse_within_candidate(tmp_path: Path) -> None:
    store, source = _registered_project(tmp_path)
    client = TestClient(create_product_app(store))
    first = client.post(
        "/v1/projects/workbench-bindings/workbench/step-bindings",
        json=_binding(source, revision=2, resource_id="display-left", entity_id="shared-entity"),
    )
    assert first.status_code == 201, first.text

    conflicting = client.post(
        "/v1/projects/workbench-bindings/workbench/step-bindings",
        json=_binding(source, revision=3, resource_id="display-right", entity_id="shared-entity"),
    )
    assert conflicting.status_code == 422, conflicting.text
    detail = conflicting.json()["detail"]
    assert detail["type"] == "invalid_workbench_step_binding"
    assert "already bound" in detail["message"]
    assert store.load("workbench-bindings")["revision"] == 3
