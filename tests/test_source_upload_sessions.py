from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.engineering_source_ingestion import MAX_ENGINEERING_SOURCE_BYTES
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.source_upload_session import SOURCE_UPLOAD_CHUNK_BYTES
from hardware_splicer.source_upload_session_api import (
    create_source_upload_session_router,
)


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
    app.include_router(create_source_upload_session_router(store))
    return store, TestClient(app)


def _create_session(
    client: TestClient,
    content: bytes,
    *,
    expected_revision: int = 1,
    expected_hash: bool = True,
) -> dict:
    content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
    response = client.post(
        "/v1/projects/robot-r1/source-upload-sessions",
        json={
            "filename": "robot.urdf",
            "total_size_bytes": len(content),
            "expected_revision": expected_revision,
            "declared_media_type": "application/xml",
            "authority_ceiling": "declared",
            "expected_content_hash": content_hash if expected_hash else None,
            "metadata": {"test": True},
        },
    )
    assert response.status_code == 201
    return response.json()["session"]


def _chunks(content: bytes) -> list[bytes]:
    return [
        content[index : index + SOURCE_UPLOAD_CHUNK_BYTES]
        for index in range(0, len(content), SOURCE_UPLOAD_CHUNK_BYTES)
    ]


def _assert_no_raw_payload(value: object) -> None:
    """Raw source bytes must never be embedded in persisted project JSON."""
    if isinstance(value, dict):
        forbidden = {"content", "raw_bytes", "raw_content", "body_bytes"}
        assert not (forbidden & set(value))
        for child in value.values():
            _assert_no_raw_payload(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_raw_payload(child)


def test_resumable_session_does_not_mutate_project_until_finalize(
    tmp_path: Path,
) -> None:
    store, client = _client(tmp_path)
    content = b"a" * (SOURCE_UPLOAD_CHUNK_BYTES + 117)
    session = _create_session(client, content)
    session_id = session["session_id"]

    assert session["chunk_count"] == 2
    assert store.load("robot-r1")["revision"] == 1

    for index, chunk in enumerate(_chunks(content)):
        digest = f"sha256:{hashlib.sha256(chunk).hexdigest()}"
        response = client.put(
            f"/v1/projects/robot-r1/source-upload-sessions/{session_id}/chunks/{index}",
            content=chunk,
            headers={
                "content-type": "application/octet-stream",
                "X-Chunk-SHA256": digest,
            },
        )
        assert response.status_code == 200
        assert response.json()["registered"] is True
        assert response.json()["project_mutated"] is False

    assert store.load("robot-r1")["revision"] == 1
    status_response = client.get(
        f"/v1/projects/robot-r1/source-upload-sessions/{session_id}"
    )
    assert status_response.status_code == 200
    assert status_response.json()["complete"] is True
    assert status_response.json()["received_chunk_count"] == 2

    finalized = client.post(
        f"/v1/projects/robot-r1/source-upload-sessions/{session_id}/finalize",
        json={"expected_revision": 1},
    )
    assert finalized.status_code == 200
    payload = finalized.json()
    assert payload["registered"] is True
    assert payload["revision"] == 2
    assert payload["session"]["status"] == "finalized"
    assert payload["ingestion"]["content_hash"] == (
        f"sha256:{hashlib.sha256(content).hexdigest()}"
    )
    assert payload["authority_unchanged"] is True

    snapshot = store.load("robot-r1", revision=2)["snapshot"]
    assert len(snapshot["engineeringSources"]) == 1
    assert len(snapshot["engineeringSourceUploads"]) == 1
    assert snapshot["engineeringSourceUploads"][0]["transport_encoding"] == (
        "resumable-raw-chunks"
    )
    _assert_no_raw_payload(snapshot)
    blob_ref = payload["ingestion"]["blob_ref"]
    assert (tmp_path / "robot-r1" / blob_ref).read_bytes() == content
    session_dir = (
        tmp_path / "robot-r1" / "source_upload_sessions" / session_id
    )
    assert not (session_dir / "chunks").exists()


def test_chunk_retry_is_idempotent_and_conflicting_retry_is_rejected(
    tmp_path: Path,
) -> None:
    _, client = _client(tmp_path)
    content = b"fixture"
    session_id = _create_session(client, content)["session_id"]
    endpoint = (
        f"/v1/projects/robot-r1/source-upload-sessions/{session_id}/chunks/0"
    )
    digest = f"sha256:{hashlib.sha256(content).hexdigest()}"

    first = client.put(
        endpoint,
        content=content,
        headers={"X-Chunk-SHA256": digest},
    )
    duplicate = client.put(
        endpoint,
        content=content,
        headers={"X-Chunk-SHA256": digest},
    )
    conflict = client.put(endpoint, content=b"changed")

    assert first.status_code == 200
    assert first.json()["registered"] is True
    assert duplicate.status_code == 200
    assert duplicate.json()["registered"] is False
    assert duplicate.json()["received_chunk_count"] == 1
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["type"] == "source_upload_session_conflict"
    assert "different content" in conflict.json()["detail"]["message"]


def test_wrong_chunk_hash_is_rejected_without_manifest_progress(
    tmp_path: Path,
) -> None:
    _, client = _client(tmp_path)
    content = b"fixture"
    session_id = _create_session(client, content)["session_id"]

    response = client.put(
        f"/v1/projects/robot-r1/source-upload-sessions/{session_id}/chunks/0",
        content=content,
        headers={"X-Chunk-SHA256": "sha256:" + "0" * 64},
    )

    assert response.status_code == 422
    status_response = client.get(
        f"/v1/projects/robot-r1/source-upload-sessions/{session_id}"
    )
    assert status_response.json()["received_chunk_count"] == 0
    assert status_response.json()["complete"] is False


def test_incomplete_session_cannot_finalize(tmp_path: Path) -> None:
    store, client = _client(tmp_path)
    content = b"a" * (SOURCE_UPLOAD_CHUNK_BYTES + 1)
    session_id = _create_session(client, content)["session_id"]
    first_chunk = content[:SOURCE_UPLOAD_CHUNK_BYTES]
    client.put(
        f"/v1/projects/robot-r1/source-upload-sessions/{session_id}/chunks/0",
        content=first_chunk,
    )

    response = client.post(
        f"/v1/projects/robot-r1/source-upload-sessions/{session_id}/finalize",
        json={"expected_revision": 1},
    )

    assert response.status_code == 409
    assert "missing chunks" in response.json()["detail"]["message"]
    assert store.load("robot-r1")["revision"] == 1


def test_project_revision_change_blocks_uncommitted_session(
    tmp_path: Path,
) -> None:
    store, client = _client(tmp_path)
    content = b"fixture"
    session_id = _create_session(client, content)["session_id"]
    client.put(
        f"/v1/projects/robot-r1/source-upload-sessions/{session_id}/chunks/0",
        content=content,
    )
    current = store.load("robot-r1")
    store.save(
        "robot-r1",
        {**current["snapshot"], "unrelatedChange": True},
        expected_revision=1,
        metadata={"source": "concurrent-test"},
    )

    response = client.post(
        f"/v1/projects/robot-r1/source-upload-sessions/{session_id}/finalize",
        json={"expected_revision": 1},
    )

    assert response.status_code == 409
    assert "session pinned 1" in response.json()["detail"]["message"]
    assert store.load("robot-r1")["revision"] == 2


def test_whole_file_hash_mismatch_blocks_finalize(tmp_path: Path) -> None:
    store, client = _client(tmp_path)
    content = b"fixture"
    response = client.post(
        "/v1/projects/robot-r1/source-upload-sessions",
        json={
            "filename": "robot.urdf",
            "total_size_bytes": len(content),
            "expected_revision": 1,
            "expected_content_hash": "sha256:" + "0" * 64,
        },
    )
    assert response.status_code == 201
    session_id = response.json()["session"]["session_id"]
    client.put(
        f"/v1/projects/robot-r1/source-upload-sessions/{session_id}/chunks/0",
        content=content,
    )

    finalized = client.post(
        f"/v1/projects/robot-r1/source-upload-sessions/{session_id}/finalize",
        json={"expected_revision": 1},
    )

    assert finalized.status_code == 409
    assert "expected_content_hash" in finalized.json()["detail"]["message"]
    assert store.load("robot-r1")["revision"] == 1


def test_abandon_session_removes_chunks_without_mutating_project(
    tmp_path: Path,
) -> None:
    store, client = _client(tmp_path)
    content = b"fixture"
    session_id = _create_session(client, content)["session_id"]
    client.put(
        f"/v1/projects/robot-r1/source-upload-sessions/{session_id}/chunks/0",
        content=content,
    )

    response = client.delete(
        f"/v1/projects/robot-r1/source-upload-sessions/{session_id}"
    )

    assert response.status_code == 200
    assert response.json()["abandoned"] is True
    assert response.json()["project_mutated"] is False
    assert store.load("robot-r1")["revision"] == 1
    session_dir = (
        tmp_path / "robot-r1" / "source_upload_sessions" / session_id
    )
    assert not (session_dir / "chunks").exists()
    assert (session_dir / "session.json").is_file()


def test_create_session_rejects_oversized_total(tmp_path: Path) -> None:
    store, client = _client(tmp_path)

    response = client.post(
        "/v1/projects/robot-r1/source-upload-sessions",
        json={
            "filename": "large.bin",
            "total_size_bytes": MAX_ENGINEERING_SOURCE_BYTES + 1,
            "expected_revision": 1,
        },
    )

    assert response.status_code == 422
    assert store.load("robot-r1")["revision"] == 1


def test_product_app_mounts_upload_session_routes(tmp_path: Path) -> None:
    paths = create_product_app(ProjectStore(tmp_path)).openapi()["paths"]

    assert "/v1/engineering/sources/upload-sessions/schema" in paths
    assert "/v1/projects/{project_id}/source-upload-sessions" in paths
    assert (
        "/v1/projects/{project_id}/source-upload-sessions/{session_id}"
        in paths
    )
    assert (
        "/v1/projects/{project_id}/source-upload-sessions/{session_id}/chunks/{chunk_index}"
        in paths
    )
    assert (
        "/v1/projects/{project_id}/source-upload-sessions/{session_id}/finalize"
        in paths
    )
