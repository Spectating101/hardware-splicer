from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import hardware_splicer.project_engineering_plan_api as project_plan_api
from hardware_splicer.engineering_source_ingestion import (
    EngineeringSourceIngestionRequest,
    ingest_engineering_source,
)
from hardware_splicer.project_engineering_plan_api import (
    create_project_engineering_plan_router,
)
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.stored_source_parser import (
    execute_stored_source_parser,
    read_registered_source_bytes,
)


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _minimal_plan() -> Dict[str, Any]:
    return {
        "schema_version": "hardware_splicer.guided_engineering_plan.v1",
        "project_name": "robot-r1",
        "machine_project": {"project_id": "robot-r1", "name": "Robot R1"},
        "engineering_context": {"normalized_mode": "greenfield"},
        "engineering_source_graph": {"sources": [], "claims": [], "conflicts": []},
        "robot_topology": {},
        "engineering_analysis": {},
        "change_impact": {},
        "engineering_identity_map": {},
        "verification_bridge": {},
        "engineering_artifact_projection": {},
        "manufacturing_projection": {},
        "manufacturing_closure": {},
        "engineering_execution_plan": {},
        "operator_guide": {"steps": []},
        "ordered_steps": [],
        "source_adapter": {},
        "engineering_readiness": {
            "status": "blocked",
            "fabrication_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        },
        "engineering_status": {"overall_status": "blocked", "blockers": []},
        "missing_info": [],
    }


def test_inventory_only_execution_still_reverifies_blob_hash(tmp_path: Path) -> None:
    result = ingest_engineering_source(
        EngineeringSourceIngestionRequest(
            project_id="robot-r1",
            filename="manual.pdf",
            content_base64=_b64(b"%PDF-1.7\nfixture"),
        ),
        project_root=tmp_path,
    )
    source = result.source_descriptor
    blob = tmp_path / "robot-r1" / result.blob_ref
    blob.write_bytes(b"tampered")

    with pytest.raises(ValueError, match="no longer matches"):
        execute_stored_source_parser(
            "robot-r1",
            source,
            project_root=tmp_path,
        )


def test_project_directory_symlink_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    content = b'<robot name="r"><link name="base"/></robot>'
    digest = hashlib.sha256(content).hexdigest()
    blob = outside / "sources" / "sha256" / digest[:2] / digest
    blob.parent.mkdir(parents=True)
    blob.write_bytes(content)
    (tmp_path / "robot-r1").symlink_to(outside, target_is_directory=True)
    source = {
        "source_id": "upload-test",
        "source_type": "cad",
        "content_hash": f"sha256:{digest}",
        "revision": f"sha256:{digest}",
        "authority_ceiling": "declared",
        "metadata": {
            "blob_ref": f"sources/sha256/{digest[:2]}/{digest}",
            "parser_disposition": "structured",
            "parser_route": "robot_model_import",
            "structured_format": "urdf",
        },
    }

    with pytest.raises(ValueError, match="must not be a symlink"):
        read_registered_source_bytes(
            "robot-r1",
            source,
            project_root=tmp_path,
        )


def test_obsolete_parser_identity_does_not_materialize_robot_bytes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = ProjectStore(tmp_path)
    ingestion = ingest_engineering_source(
        EngineeringSourceIngestionRequest(
            project_id="robot-r1",
            filename="robot.urdf",
            content_base64=_b64(
                b'<robot name="r"><link name="base"/></robot>'
            ),
        ),
        project_root=tmp_path,
    )
    store.save(
        "robot-r1",
        {
            "projectId": "robot-r1",
            "projectName": "Robot R1",
            "mode": "greenfield",
            "currentStage": "source_intake",
            "engineeringSources": [ingestion.source_descriptor],
            "engineeringSourceParserRuns": [
                {
                    "schema_version": "hardware_splicer.stored_source_parser.v1",
                    "parser_identity": "obsolete-parser-build",
                    "project_id": "robot-r1",
                    "source_id": ingestion.source_id,
                    "content_hash": ingestion.content_hash,
                    "parser_route": "robot_model_import",
                    "status": "parsed",
                    "authority_ceiling": "declared",
                    "parsed_output": {},
                    "derived_sources": [],
                    "limitations": [],
                    "raw_bytes_returned": False,
                    "automatic_authorization": False,
                    "metadata": {},
                }
            ],
        },
        expected_revision=0,
        metadata={"source": "test"},
    )
    captured: Dict[str, Any] = {}

    def fake_planner(
        intake,
        *,
        engineering_sources,
        declared_conflicts,
        baseline_project,
        skip_vision,
    ):
        captured["sources"] = list(engineering_sources)
        return _minimal_plan()

    monkeypatch.setattr(project_plan_api, "plan_guided_engineering_project", fake_planner)
    app = FastAPI()
    app.include_router(create_project_engineering_plan_router(store))
    client = TestClient(app)

    response = client.post(
        "/v1/projects/robot-r1/engineering/plan",
        json={
            "expected_revision": 1,
            "intake": {"project_name": "robot-r1", "goal": "Plan robot"},
        },
    )

    assert response.status_code == 200
    assert response.json()["materialized_robot_source_count"] == 0
    assert "content" not in captured["sources"][0]
