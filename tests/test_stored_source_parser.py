from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.engineering_source_ingestion import (
    EngineeringSourceIngestionRequest,
    ingest_engineering_source,
)
from hardware_splicer.engineering_source_ingestion_api import (
    create_engineering_source_ingestion_router,
)
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.stored_source_parser import (
    StoredParserStatus,
    execute_stored_source_parser,
    read_registered_source_bytes,
)
from hardware_splicer.stored_source_parser_api import (
    create_stored_source_parser_router,
)


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _seed(store: ProjectStore, project_id: str = "robot-r1") -> None:
    store.save(
        project_id,
        {
            "projectId": project_id,
            "projectName": "Robot R1",
            "mode": "greenfield",
            "currentStage": "source_intake",
        },
        expected_revision=0,
        metadata={"source": "test"},
    )


def _registered_source(
    root: Path,
    *,
    filename: str,
    content: bytes,
    project_id: str = "robot-r1",
) -> dict:
    result = ingest_engineering_source(
        EngineeringSourceIngestionRequest(
            project_id=project_id,
            filename=filename,
            content_base64=_b64(content),
        ),
        project_root=root,
    )
    return result.source_descriptor


def test_executes_robot_model_parser_and_preserves_fail_closed_authority(
    tmp_path: Path,
) -> None:
    source = _registered_source(
        tmp_path,
        filename="robot.urdf",
        content=(
            b'<robot name="arm">'
            b'<link name="base"/><link name="tool"/>'
            b'<joint name="joint_1" type="revolute">'
            b'<parent link="base"/><child link="tool"/>'
            b'<limit lower="-1" upper="1" effort="2" velocity="1"/>'
            b'</joint></robot>'
        ),
    )

    result = execute_stored_source_parser(
        "robot-r1",
        source,
        project_root=tmp_path,
    )

    assert result.status == StoredParserStatus.PARSED
    assert result.parser_route == "robot_model_import"
    assert result.parsed_output["summary"]["link_count"] == 2
    assert result.parsed_output["summary"]["joint_count"] == 1
    assert result.parsed_output["robot_topology"]["metadata"]["motion_authorized"] is False
    assert result.raw_bytes_returned is False
    assert result.automatic_authorization is False
    assert "content" not in result.model_dump(mode="json")


def test_json_descriptor_parser_caps_nested_authority(tmp_path: Path) -> None:
    source = _registered_source(
        tmp_path,
        filename="sources.json",
        content=(
            b'{"engineering_sources":[{'
            b'"source_id":"manual-a",'
            b'"source_type":"manual",'
            b'"authority_ceiling":"verified",'
            b'"claims":[{"subject_id":"machine","predicate":"mass",'
            b'"value":2,"authority":"measured"}]'
            b'}]}'
        ),
    )

    result = execute_stored_source_parser(
        "robot-r1",
        source,
        project_root=tmp_path,
    )

    assert result.status == StoredParserStatus.PARSED
    assert result.parser_route == "engineering_source_descriptor"
    assert result.derived_sources[0]["authority_ceiling"] == "declared"
    assert result.derived_sources[0]["claims"][0]["authority"] == "declared"
    graph = result.parsed_output["engineering_source_graph"]
    assert graph["sources"][0]["authority_ceiling"] == "declared"
    assert graph["claims"][0]["authority"] == "declared"


def test_step_parser_is_explicitly_unavailable_not_faked(tmp_path: Path) -> None:
    source = _registered_source(
        tmp_path,
        filename="frame.step",
        content=b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;",
    )

    result = execute_stored_source_parser(
        "robot-r1",
        source,
        project_root=tmp_path,
    )

    assert result.status == StoredParserStatus.SKIPPED
    assert result.parser_route == "step_geometry"
    assert result.metadata["parser_available"] is False
    assert any("No callable bounded STEP parser" in row for row in result.limitations)


def test_registered_blob_is_reverified_before_parser_execution(tmp_path: Path) -> None:
    source = _registered_source(
        tmp_path,
        filename="robot.urdf",
        content=b'<robot name="r"><link name="base"/></robot>',
    )
    blob = tmp_path / "robot-r1" / source["metadata"]["blob_ref"]
    blob.write_bytes(b"tampered")

    with pytest.raises(ValueError, match="no longer matches"):
        read_registered_source_bytes(
            "robot-r1",
            source,
            project_root=tmp_path,
        )


def test_parser_api_persists_run_and_derived_sources_idempotently(
    tmp_path: Path,
) -> None:
    store = ProjectStore(tmp_path)
    _seed(store)
    app = FastAPI()
    app.include_router(create_engineering_source_ingestion_router(store))
    app.include_router(create_stored_source_parser_router(store))
    client = TestClient(app)

    ingestion = client.post(
        "/v1/projects/robot-r1/sources/ingest",
        json={
            "filename": "sources.json",
            "content_base64": _b64(
                b'[{"source_id":"manual-a","source_type":"manual"}]'
            ),
            "expected_revision": 1,
        },
    )
    assert ingestion.status_code == 201
    source_id = ingestion.json()["ingestion"]["source_id"]

    parsed = client.post(
        f"/v1/projects/robot-r1/sources/{source_id}/parse",
        json={"expected_revision": 2},
    )
    assert parsed.status_code == 201
    assert parsed.json()["registered"] is True
    assert parsed.json()["revision"] == 3
    assert parsed.json()["derived_source_count"] == 1

    saved = store.load("robot-r1", revision=3)["snapshot"]
    assert len(saved["engineeringSourceParserRuns"]) == 1
    assert len(saved["engineeringParsedSources"]) == 1
    assert "content_base64" not in str(saved)

    duplicate = client.post(
        f"/v1/projects/robot-r1/sources/{source_id}/parse",
        json={"expected_revision": 3},
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["registered"] is False
    assert duplicate.json()["revision"] == 3
    assert store.load("robot-r1")["revision"] == 3


def test_parser_api_refuses_stale_revision_before_blob_read(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    _seed(store)
    app = FastAPI()
    app.include_router(create_stored_source_parser_router(store))
    client = TestClient(app)

    response = client.post(
        "/v1/projects/robot-r1/sources/missing/parse",
        json={"expected_revision": 9},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["type"] == "stored_source_parser_revision_conflict"


def test_product_app_mounts_parser_routes(tmp_path: Path) -> None:
    paths = create_product_app(ProjectStore(tmp_path)).openapi()["paths"]

    assert "/v1/engineering/sources/parser/schema" in paths
    assert "/v1/projects/{project_id}/sources/{source_id}/parse" in paths
