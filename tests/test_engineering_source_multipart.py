from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.engineering_source_ingestion import MAX_ENGINEERING_SOURCE_BYTES
from hardware_splicer.engineering_source_multipart_api import (
    create_engineering_source_multipart_router,
    ingest_multipart_source_bytes,
)
from hardware_splicer.machine_project import AuthorityState
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def _seed(store: ProjectStore, project_id: str = "robot-r1") -> None:
    store.save(
        project_id,
        {
            "projectId": project_id,
            "projectName": "Robot R1",
            "mode": "greenfield",
            "currentStage": "source_intake",
            "engineeringSources": [],
            "engineeringSourceUploads": [],
        },
        expected_revision=0,
        metadata={"source": "test"},
    )


def _client(tmp_path: Path) -> tuple[ProjectStore, TestClient]:
    store = ProjectStore(tmp_path)
    _seed(store)
    app = FastAPI()
    app.include_router(create_engineering_source_multipart_router(store))
    return store, TestClient(app)


def test_direct_multipart_byte_ingestion_hashes_and_stores_raw_bytes(
    tmp_path: Path,
) -> None:
    content = b'<robot name="r"><link name="base"/></robot>'

    result = ingest_multipart_source_bytes(
        project_id="robot-r1",
        filename="robot.urdf",
        content=content,
        declared_media_type="application/xml",
        authority_ceiling=AuthorityState.DECLARED,
        captured_at=None,
        metadata={"fixture": True},
        project_root=tmp_path,
    )

    expected = f"sha256:{hashlib.sha256(content).hexdigest()}"
    assert result.content_hash == expected
    assert result.classification.parser_route == "robot_model_import"
    assert result.source_descriptor["metadata"]["transport_encoding"] == (
        "multipart/form-data"
    )
    assert result.automatic_authorization is False
    assert "content" not in result.model_dump(mode="json")
    assert (tmp_path / "robot-r1" / result.blob_ref).read_bytes() == content


def test_multipart_api_registers_source_in_optimistic_revision(
    tmp_path: Path,
) -> None:
    store, client = _client(tmp_path)
    content = b'<robot name="r"><link name="base"/></robot>'

    response = client.post(
        "/v1/projects/robot-r1/sources/ingest-file",
        files={"file": ("robot.urdf", content, "application/xml")},
        data={
            "expected_revision": "1",
            "authority_ceiling": "declared",
            "captured_at": "",
            "metadata_json": '{"browser":"test"}',
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    assert payload["registered"] is True
    assert payload["revision"] == 2
    assert payload["transport"] == "multipart/form-data"
    assert payload["authority_unchanged"] is True
    assert payload["ingestion"]["classification"]["structured_format"] == "urdf"
    assert payload["ingestion"]["metadata"]["raw_bytes_in_response"] is False

    saved = store.load("robot-r1", revision=2)
    snapshot = saved["snapshot"]
    assert len(snapshot["engineeringSources"]) == 1
    assert len(snapshot["engineeringSourceUploads"]) == 1
    assert snapshot["engineeringSourceUploads"][0]["transport_encoding"] == (
        "multipart/form-data"
    )
    assert "content_base64" not in str(snapshot)
    assert content.decode("utf-8") not in str(snapshot)
    blob_ref = payload["ingestion"]["blob_ref"]
    assert (tmp_path / "robot-r1" / blob_ref).read_bytes() == content


def test_repeated_multipart_filename_and_content_is_idempotent(
    tmp_path: Path,
) -> None:
    store, client = _client(tmp_path)
    request = {
        "files": {"file": ("manual.pdf", b"%PDF-1.7\nfixture", "application/pdf")},
        "data": {
            "expected_revision": "1",
            "authority_ceiling": "declared",
            "metadata_json": "{}",
        },
    }
    first = client.post(
        "/v1/projects/robot-r1/sources/ingest-file",
        **request,
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/v1/projects/robot-r1/sources/ingest-file",
        files={"file": ("manual.pdf", b"%PDF-1.7\nfixture", "application/pdf")},
        data={
            "expected_revision": "2",
            "authority_ceiling": "declared",
            "metadata_json": "{}",
        },
    )

    assert duplicate.status_code == 201
    assert duplicate.json()["registered"] is False
    assert duplicate.json()["revision"] == 2
    assert store.load("robot-r1")["revision"] == 2


def test_multipart_api_rejects_stale_revision_before_registration(
    tmp_path: Path,
) -> None:
    store, client = _client(tmp_path)

    response = client.post(
        "/v1/projects/robot-r1/sources/ingest-file",
        files={"file": ("manual.pdf", b"%PDF-1.7\nfixture", "application/pdf")},
        data={
            "expected_revision": "9",
            "authority_ceiling": "declared",
            "metadata_json": "{}",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["type"] == (
        "engineering_source_multipart_revision_conflict"
    )
    assert store.load("robot-r1")["revision"] == 1
    assert not (tmp_path / "robot-r1" / "sources").exists()


def test_multipart_api_rejects_elevated_authority_without_blob_side_effect(
    tmp_path: Path,
) -> None:
    store, client = _client(tmp_path)

    response = client.post(
        "/v1/projects/robot-r1/sources/ingest-file",
        files={"file": ("photo.jpg", b"\xff\xd8\xfffixture", "image/jpeg")},
        data={
            "expected_revision": "1",
            "authority_ceiling": "observed",
            "metadata_json": "{}",
        },
    )

    assert response.status_code == 422
    assert "cannot enter above declared authority" in response.json()["detail"]["message"]
    assert store.load("robot-r1")["revision"] == 1
    assert not (tmp_path / "robot-r1" / "sources").exists()


def test_multipart_api_rejects_invalid_metadata_json(tmp_path: Path) -> None:
    store, client = _client(tmp_path)

    response = client.post(
        "/v1/projects/robot-r1/sources/ingest-file",
        files={"file": ("notes.txt", b"fixture", "text/plain")},
        data={
            "expected_revision": "1",
            "authority_ceiling": "declared",
            "metadata_json": "[]",
        },
    )

    assert response.status_code == 422
    assert "must be a JSON object" in response.json()["detail"]["message"]
    assert store.load("robot-r1")["revision"] == 1


def test_multipart_api_rejects_oversized_upload_without_revision(
    tmp_path: Path,
) -> None:
    store, client = _client(tmp_path)
    content = b"x" * (MAX_ENGINEERING_SOURCE_BYTES + 1)

    response = client.post(
        "/v1/projects/robot-r1/sources/ingest-file",
        files={"file": ("too-large.bin", content, "application/octet-stream")},
        data={
            "expected_revision": "1",
            "authority_ceiling": "declared",
            "metadata_json": "{}",
        },
    )

    assert response.status_code == 422
    assert "exceeds" in response.json()["detail"]["message"]
    assert store.load("robot-r1")["revision"] == 1
    assert not (tmp_path / "robot-r1" / "sources").exists()


def test_product_app_mounts_multipart_routes(tmp_path: Path) -> None:
    paths = create_product_app(ProjectStore(tmp_path)).openapi()["paths"]

    assert "/v1/engineering/sources/multipart/schema" in paths
    assert "/v1/projects/{project_id}/sources/ingest-file" in paths
