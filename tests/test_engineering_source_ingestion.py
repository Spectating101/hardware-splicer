from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from hardware_splicer.engineering_source_ingestion import (
    EngineeringSourceIngestionRequest,
    EngineeringSourceKind,
    ParserDisposition,
    classify_engineering_source,
    ingest_engineering_source,
)
from hardware_splicer.engineering_source_ingestion_api import (
    create_engineering_source_ingestion_router,
)
from hardware_splicer.machine_project import AuthorityState
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _seed_project(store: ProjectStore, project_id: str = "rover-r1") -> dict:
    return store.save(
        project_id,
        {
            "projectId": project_id,
            "projectName": "Rover R1",
            "mode": "greenfield",
            "currentStage": "source_intake",
        },
        expected_revision=0,
        metadata={"source": "test"},
    )


def test_ingests_content_addressed_json_and_reuses_duplicate_blob(tmp_path: Path) -> None:
    content = b'{"source_id":"manual-a","source_type":"manual"}'
    request = EngineeringSourceIngestionRequest(
        project_id="rover-r1",
        filename="source.json",
        content_base64=_b64(content),
    )

    first = ingest_engineering_source(request, project_root=tmp_path)
    second = ingest_engineering_source(request, project_root=tmp_path)

    assert first.content_hash.startswith("sha256:")
    assert first.classification.kind == EngineeringSourceKind.JSON_DESCRIPTOR
    assert first.classification.parser_disposition == ParserDisposition.STRUCTURED
    assert first.classification.parser_route == "engineering_source_descriptor"
    assert first.duplicate_blob is False
    assert second.duplicate_blob is True
    assert first.blob_ref == second.blob_ref
    assert first.authority_ceiling == AuthorityState.DECLARED
    assert first.automatic_authorization is False
    assert first.metadata["fabrication_authorized"] is False
    assert "content_base64" not in first.model_dump(mode="json")

    blob = tmp_path / "rover-r1" / first.blob_ref
    assert blob.read_bytes() == content


@pytest.mark.parametrize(
    ("filename", "content", "kind", "route", "disposition"),
    [
        (
            "robot.urdf",
            b'<robot name="r"><link name="base"/></robot>',
            EngineeringSourceKind.ROBOT_MODEL,
            "robot_model_import",
            ParserDisposition.STRUCTURED,
        ),
        (
            "frame.step",
            b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;",
            EngineeringSourceKind.STEP_CAD,
            "step_geometry",
            ParserDisposition.STRUCTURED,
        ),
        (
            "manual.pdf",
            b"%PDF-1.7\nbounded fixture",
            EngineeringSourceKind.PDF_DOCUMENT,
            None,
            ParserDisposition.INVENTORY_ONLY,
        ),
        (
            "firmware.zip",
            b"PK\x03\x04bounded archive fixture",
            EngineeringSourceKind.ARCHIVE,
            None,
            ParserDisposition.INVENTORY_ONLY,
        ),
    ],
)
def test_classification_routes_supported_formats_and_keeps_others_inventory_only(
    filename: str,
    content: bytes,
    kind: EngineeringSourceKind,
    route: str | None,
    disposition: ParserDisposition,
) -> None:
    result = classify_engineering_source(filename, content)

    assert result.kind == kind
    assert result.parser_route == route
    assert result.parser_disposition == disposition
    assert result.limitations


def test_upload_cannot_claim_observed_or_higher_authority() -> None:
    with pytest.raises(ValidationError, match="cannot enter above declared authority"):
        EngineeringSourceIngestionRequest(
            project_id="rover-r1",
            filename="photo.jpg",
            content_base64=_b64(b"\xff\xd8\xfffixture"),
            authority_ceiling=AuthorityState.OBSERVED,
        )


def test_invalid_base64_is_rejected_without_creating_project_source_tree(
    tmp_path: Path,
) -> None:
    request = EngineeringSourceIngestionRequest(
        project_id="rover-r1",
        filename="broken.bin",
        content_base64="not canonical base64!",
    )

    with pytest.raises(ValueError, match="canonical base64"):
        ingest_engineering_source(request, project_root=tmp_path)

    assert not (tmp_path / "rover-r1" / "sources").exists()


def test_project_ingestion_api_registers_source_in_optimistic_revision(
    tmp_path: Path,
) -> None:
    store = ProjectStore(tmp_path)
    _seed_project(store)
    app = FastAPI()
    app.include_router(create_engineering_source_ingestion_router(store))
    client = TestClient(app)

    response = client.post(
        "/v1/projects/rover-r1/sources/ingest",
        json={
            "filename": "robot.urdf",
            "content_base64": _b64(
                b'<robot name="r"><link name="base"/></robot>'
            ),
            "declared_media_type": "application/xml",
            "expected_revision": 1,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    assert payload["registered"] is True
    assert payload["revision"] == 2
    assert payload["authority_unchanged"] is True
    assert payload["ingestion"]["classification"]["structured_format"] == "urdf"

    saved = store.load("rover-r1", revision=2)
    snapshot = saved["snapshot"]
    assert len(snapshot["engineeringSourceUploads"]) == 1
    assert len(snapshot["engineeringSources"]) == 1
    assert snapshot["engineeringSources"][0]["content_hash"].startswith("sha256:")
    assert "content_base64" not in str(snapshot)
    assert saved["metadata"]["automatic_authorization"] is False
    assert saved["metadata"]["physical_authority_unchanged"] is True

    duplicate = client.post(
        "/v1/projects/rover-r1/sources/ingest",
        json={
            "filename": "robot.urdf",
            "content_base64": _b64(
                b'<robot name="r"><link name="base"/></robot>'
            ),
            "declared_media_type": "application/xml",
            "expected_revision": 2,
        },
    )

    assert duplicate.status_code == 201
    assert duplicate.json()["registered"] is False
    assert duplicate.json()["revision"] == 2
    assert store.load("rover-r1")["revision"] == 2


def test_project_ingestion_api_rejects_stale_revision(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    _seed_project(store)
    app = FastAPI()
    app.include_router(create_engineering_source_ingestion_router(store))
    client = TestClient(app)

    response = client.post(
        "/v1/projects/rover-r1/sources/ingest",
        json={
            "filename": "manual.pdf",
            "content_base64": _b64(b"%PDF-1.7\nfixture"),
            "expected_revision": 9,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["type"] == "engineering_source_revision_conflict"
    assert store.load("rover-r1")["revision"] == 1
    assert not (tmp_path / "rover-r1" / "sources").exists()


def test_canonical_product_app_mounts_ingestion_routes(tmp_path: Path) -> None:
    app = create_product_app(ProjectStore(tmp_path))
    paths = app.openapi()["paths"]

    assert "/v1/engineering/sources/ingestion/schema" in paths
    assert "/v1/projects/{project_id}/sources/ingest" in paths
