from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.engineering_source_multipart_api import (
    ingest_multipart_source_bytes,
)
from hardware_splicer.machine_project import AuthorityState
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.source_storage_operations import (
    SourceStorageCleanupRequest,
    audit_project_source_storage,
    cleanup_project_source_storage,
)
from hardware_splicer.source_storage_operations_api import (
    create_source_storage_operations_router,
)
from hardware_splicer.source_upload_session import (
    SourceUploadSessionCreate,
    create_source_upload_session,
    store_source_upload_chunk,
)


def _ingest(root: Path, content: bytes, filename: str) -> dict:
    return ingest_multipart_source_bytes(
        project_id="robot-r1",
        filename=filename,
        content=content,
        declared_media_type="application/octet-stream",
        authority_ceiling=AuthorityState.DECLARED,
        captured_at=None,
        metadata={},
        project_root=root,
    ).model_dump(mode="json")


def _seed(store: ProjectStore, referenced: dict | None = None) -> None:
    snapshot = {
        "projectId": "robot-r1",
        "projectName": "Robot R1",
        "mode": "greenfield",
        "currentStage": "source_intake",
        "engineeringSources": [],
        "engineeringSourceUploads": [],
    }
    if referenced:
        snapshot["engineeringSources"] = [referenced["source_descriptor"]]
        snapshot["engineeringSourceUploads"] = [
            {
                "schema_version": referenced["schema_version"],
                "source_id": referenced["source_id"],
                "original_filename": referenced["original_filename"],
                "content_hash": referenced["content_hash"],
                "size_bytes": referenced["size_bytes"],
                "blob_ref": referenced["blob_ref"],
                "classification": referenced["classification"],
                "authority_ceiling": referenced["authority_ceiling"],
                "metadata": referenced["metadata"],
            }
        ]
    store.save(
        "robot-r1",
        snapshot,
        expected_revision=0,
        metadata={"source": "test"},
    )


def _make_old(path: Path, hours: float = 48.0) -> None:
    timestamp = (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()
    os.utime(path, (timestamp, timestamp))


def test_audit_distinguishes_referenced_orphan_and_corrupt_blobs(
    tmp_path: Path,
) -> None:
    referenced = _ingest(tmp_path, b"referenced", "manual.pdf")
    orphan = _ingest(tmp_path, b"orphan", "orphan.bin")
    store = ProjectStore(tmp_path)
    _seed(store, referenced)
    orphan_path = tmp_path / "robot-r1" / orphan["blob_ref"]
    _make_old(orphan_path)
    corrupt_path = (
        tmp_path
        / "robot-r1"
        / "sources"
        / "sha256"
        / "aa"
        / ("a" * 64)
    )
    corrupt_path.parent.mkdir(parents=True, exist_ok=True)
    corrupt_path.write_bytes(b"wrong-content")
    _make_old(corrupt_path)

    snapshot = store.load("robot-r1")["snapshot"]
    report = audit_project_source_storage(
        "robot-r1",
        snapshot,
        project_root=tmp_path,
    )

    by_ref = {row.blob_ref: row for row in report.blobs}
    assert by_ref[referenced["blob_ref"]].referenced is True
    assert by_ref[referenced["blob_ref"]].orphan is False
    assert by_ref[referenced["blob_ref"]].content_hash_valid is True
    assert by_ref[orphan["blob_ref"]].orphan is True
    assert by_ref[orphan["blob_ref"]].content_hash_valid is True
    corrupt_ref = corrupt_path.relative_to(tmp_path / "robot-r1").as_posix()
    assert by_ref[corrupt_ref].orphan is True
    assert by_ref[corrupt_ref].corrupt is True
    assert report.summary["orphan_blob_count"] == 2
    assert report.summary["corrupt_blob_count"] == 1
    assert report.automatic_deletion is False


def test_cleanup_is_dry_run_by_default_and_never_deletes_referenced_blob(
    tmp_path: Path,
) -> None:
    referenced = _ingest(tmp_path, b"referenced", "manual.pdf")
    orphan = _ingest(tmp_path, b"orphan", "orphan.bin")
    store = ProjectStore(tmp_path)
    _seed(store, referenced)
    referenced_path = tmp_path / "robot-r1" / referenced["blob_ref"]
    orphan_path = tmp_path / "robot-r1" / orphan["blob_ref"]
    _make_old(referenced_path)
    _make_old(orphan_path)
    snapshot = store.load("robot-r1")["snapshot"]

    result = cleanup_project_source_storage(
        "robot-r1",
        snapshot,
        SourceStorageCleanupRequest(),
        project_root=tmp_path,
    )

    assert result.dry_run is True
    assert result.candidate_blob_refs == [orphan["blob_ref"]]
    assert result.deleted_blob_refs == []
    assert result.bytes_reclaimable == len(b"orphan")
    assert referenced_path.is_file()
    assert orphan_path.is_file()
    assert store.load("robot-r1")["revision"] == 1


def test_destructive_cleanup_requires_exact_project_confirmation(
    tmp_path: Path,
) -> None:
    orphan = _ingest(tmp_path, b"orphan", "orphan.bin")
    store = ProjectStore(tmp_path)
    _seed(store)
    orphan_path = tmp_path / "robot-r1" / orphan["blob_ref"]
    _make_old(orphan_path)
    snapshot = store.load("robot-r1")["snapshot"]

    try:
        cleanup_project_source_storage(
            "robot-r1",
            snapshot,
            SourceStorageCleanupRequest(
                dry_run=False,
                confirm_project_id="wrong-project",
            ),
            project_root=tmp_path,
        )
    except ValueError as exc:
        assert "exactly match" in str(exc)
    else:
        raise AssertionError("cleanup accepted the wrong confirmation")

    assert orphan_path.is_file()
    assert store.load("robot-r1")["revision"] == 1


def test_apply_cleanup_deletes_only_old_valid_orphan_without_revision(
    tmp_path: Path,
) -> None:
    referenced = _ingest(tmp_path, b"referenced", "manual.pdf")
    old_orphan = _ingest(tmp_path, b"old-orphan", "old.bin")
    young_orphan = _ingest(tmp_path, b"young-orphan", "young.bin")
    store = ProjectStore(tmp_path)
    _seed(store, referenced)
    referenced_path = tmp_path / "robot-r1" / referenced["blob_ref"]
    old_path = tmp_path / "robot-r1" / old_orphan["blob_ref"]
    young_path = tmp_path / "robot-r1" / young_orphan["blob_ref"]
    _make_old(referenced_path)
    _make_old(old_path)
    snapshot = store.load("robot-r1")["snapshot"]

    result = cleanup_project_source_storage(
        "robot-r1",
        snapshot,
        SourceStorageCleanupRequest(
            dry_run=False,
            minimum_age_hours=24,
            confirm_project_id="robot-r1",
        ),
        project_root=tmp_path,
    )

    assert result.deleted_blob_refs == [old_orphan["blob_ref"]]
    assert result.bytes_reclaimed == len(b"old-orphan")
    assert result.project_revision_mutated is False
    assert not old_path.exists()
    assert young_path.is_file()
    assert referenced_path.is_file()
    assert store.load("robot-r1")["revision"] == 1


def test_corrupt_orphan_is_report_only_unless_explicitly_included(
    tmp_path: Path,
) -> None:
    store = ProjectStore(tmp_path)
    _seed(store)
    corrupt_path = (
        tmp_path / "robot-r1" / "sources" / "sha256" / "aa" / ("a" * 64)
    )
    corrupt_path.parent.mkdir(parents=True, exist_ok=True)
    corrupt_path.write_bytes(b"wrong")
    _make_old(corrupt_path)
    snapshot = store.load("robot-r1")["snapshot"]

    default = cleanup_project_source_storage(
        "robot-r1",
        snapshot,
        SourceStorageCleanupRequest(),
        project_root=tmp_path,
    )
    included = cleanup_project_source_storage(
        "robot-r1",
        snapshot,
        SourceStorageCleanupRequest(include_corrupt_orphans=True),
        project_root=tmp_path,
    )

    corrupt_ref = corrupt_path.relative_to(tmp_path / "robot-r1").as_posix()
    assert corrupt_ref not in default.candidate_blob_refs
    assert corrupt_ref in included.candidate_blob_refs
    assert corrupt_path.is_file()


def test_expired_open_session_chunks_are_dry_run_then_cleaned(
    tmp_path: Path,
) -> None:
    store = ProjectStore(tmp_path)
    _seed(store)
    session = create_source_upload_session(
        SourceUploadSessionCreate(
            project_id="robot-r1",
            filename="fixture.bin",
            total_size_bytes=7,
            expected_revision=1,
        ),
        project_root=tmp_path,
    )
    store_source_upload_chunk(
        "robot-r1",
        session.session_id,
        0,
        b"fixture",
        project_root=tmp_path,
    )
    manifest = (
        tmp_path
        / "robot-r1"
        / "source_upload_sessions"
        / session.session_id
        / "session.json"
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=1)
    ).isoformat()
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    snapshot = store.load("robot-r1")["snapshot"]

    dry_run = cleanup_project_source_storage(
        "robot-r1",
        snapshot,
        SourceStorageCleanupRequest(),
        project_root=tmp_path,
    )
    assert dry_run.candidate_session_ids == [session.session_id]
    chunks = manifest.parent / "chunks"
    assert chunks.is_dir()

    applied = cleanup_project_source_storage(
        "robot-r1",
        snapshot,
        SourceStorageCleanupRequest(
            dry_run=False,
            confirm_project_id="robot-r1",
        ),
        project_root=tmp_path,
    )
    assert applied.cleaned_session_ids == [session.session_id]
    assert applied.bytes_reclaimed == len(b"fixture")
    assert not chunks.exists()
    updated = json.loads(manifest.read_text(encoding="utf-8"))
    assert updated["status"] == "abandoned"
    assert store.load("robot-r1")["revision"] == 1


def test_storage_api_returns_audit_and_dry_run_without_project_mutation(
    tmp_path: Path,
) -> None:
    orphan = _ingest(tmp_path, b"orphan", "orphan.bin")
    store = ProjectStore(tmp_path)
    _seed(store)
    _make_old(tmp_path / "robot-r1" / orphan["blob_ref"])
    app = FastAPI()
    app.include_router(create_source_storage_operations_router(store))
    client = TestClient(app)

    audit = client.get("/v1/projects/robot-r1/source-storage/audit")
    cleanup = client.post(
        "/v1/projects/robot-r1/source-storage/cleanup",
        json={"dry_run": True, "minimum_age_hours": 24},
    )

    assert audit.status_code == 200
    assert audit.json()["audit"]["summary"]["orphan_blob_count"] == 1
    assert cleanup.status_code == 200
    assert cleanup.json()["cleanup"]["candidate_blob_refs"] == [
        orphan["blob_ref"]
    ]
    assert cleanup.json()["project_revision_mutated"] is False
    assert store.load("robot-r1")["revision"] == 1


def test_product_app_mounts_storage_operation_routes(tmp_path: Path) -> None:
    paths = create_product_app(ProjectStore(tmp_path)).openapi()["paths"]
    assert "/v1/engineering/sources/storage/schema" in paths
    assert "/v1/projects/{project_id}/source-storage/audit" in paths
    assert "/v1/projects/{project_id}/source-storage/cleanup" in paths
