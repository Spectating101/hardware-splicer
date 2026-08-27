from __future__ import annotations

import base64
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.engineering_source_ingestion_api import (
    create_engineering_source_ingestion_router,
)
from hardware_splicer.engineering_source_role_api import (
    create_engineering_source_role_router,
)
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _client(tmp_path: Path) -> tuple[ProjectStore, TestClient, str]:
    store = ProjectStore(tmp_path)
    store.save(
        "robot-r1",
        {
            "projectId": "robot-r1",
            "projectName": "Robot R1",
            "mode": "greenfield",
            "currentStage": "source_intake",
        },
        expected_revision=0,
        metadata={"source": "test"},
    )
    app = FastAPI()
    app.include_router(create_engineering_source_ingestion_router(store))
    app.include_router(create_engineering_source_role_router(store))
    client = TestClient(app)
    ingestion = client.post(
        "/v1/projects/robot-r1/sources/ingest",
        json={
            "filename": "notes.txt",
            "content_base64": _b64(b"declared notes"),
            "expected_revision": 1,
        },
    )
    assert ingestion.status_code == 201
    return store, client, ingestion.json()["ingestion"]["source_id"]


def test_role_correction_changes_type_without_rewriting_identity(tmp_path: Path) -> None:
    store, client, source_id = _client(tmp_path)
    before = store.load("robot-r1", revision=2)["snapshot"]["engineeringSources"][0]

    response = client.patch(
        f"/v1/projects/robot-r1/sources/{source_id}/role",
        json={
            "expected_revision": 2,
            "source_type": "service_note",
            "note": "Operator identified this as a service note.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["revision"] == 3
    assert payload["authority_elevated"] is False
    assert payload["immutable_identity_preserved"] is True
    assert payload["source"]["source_type"] == "service_note"

    after = store.load("robot-r1", revision=3)["snapshot"]["engineeringSources"][0]
    for field in ("source_id", "uri", "revision", "content_hash"):
        assert after[field] == before[field]
    assert after["metadata"]["source_role_user_corrected"] is True
    assert after["metadata"]["source_role_history"][-1]["note"]


def test_role_correction_may_reduce_but_not_elevate_authority(tmp_path: Path) -> None:
    store, client, source_id = _client(tmp_path)

    reduced = client.patch(
        f"/v1/projects/robot-r1/sources/{source_id}/role",
        json={
            "expected_revision": 2,
            "authority_ceiling": "proposed",
        },
    )
    assert reduced.status_code == 200
    assert reduced.json()["source"]["authority_ceiling"] == "proposed"

    elevated = client.patch(
        f"/v1/projects/robot-r1/sources/{source_id}/role",
        json={
            "expected_revision": 3,
            "authority_ceiling": "declared",
        },
    )
    assert elevated.status_code == 422
    assert "never elevate" in elevated.json()["detail"]["message"]
    assert store.load("robot-r1")["revision"] == 3


def test_role_correction_rejects_stale_revision(tmp_path: Path) -> None:
    store, client, source_id = _client(tmp_path)

    response = client.patch(
        f"/v1/projects/robot-r1/sources/{source_id}/role",
        json={"expected_revision": 9, "source_type": "manual"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["type"] == "source_role_revision_conflict"
    assert store.load("robot-r1")["revision"] == 2


def test_product_app_mounts_role_correction_route(tmp_path: Path) -> None:
    paths = create_product_app(ProjectStore(tmp_path)).openapi()["paths"]
    assert "/v1/projects/{project_id}/sources/{source_id}/role" in paths
