from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.testclient import TestClient

import hardware_splicer.project_engineering_plan_api as project_plan_api
from hardware_splicer.engineering_source_ingestion_api import (
    create_engineering_source_ingestion_router,
)
from hardware_splicer.project_engineering_plan_api import (
    create_project_engineering_plan_router,
)
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.stored_source_parser_api import (
    create_stored_source_parser_router,
)


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _plan(project_id: str = "robot-r1") -> Dict[str, Any]:
    return {
        "schema_version": "hardware_splicer.guided_engineering_plan.v1",
        "project_name": project_id,
        "machine_project": {"project_id": project_id, "name": "Robot R1"},
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


def _seed(store: ProjectStore) -> TestClient:
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
    app.include_router(create_stored_source_parser_router(store))
    app.include_router(create_project_engineering_plan_router(store))
    return TestClient(app)


def test_successfully_parsed_robot_blob_is_materialized_only_for_planner(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = ProjectStore(tmp_path)
    client = _seed(store)
    robot_xml = (
        b'<robot name="arm"><link name="base"/><link name="tool"/>'
        b'<joint name="joint_1" type="fixed">'
        b'<parent link="base"/><child link="tool"/>'
        b'</joint></robot>'
    )
    ingested = client.post(
        "/v1/projects/robot-r1/sources/ingest",
        json={
            "filename": "robot.urdf",
            "content_base64": _b64(robot_xml),
            "expected_revision": 1,
        },
    ).json()
    source_id = ingested["ingestion"]["source_id"]
    parsed = client.post(
        f"/v1/projects/robot-r1/sources/{source_id}/parse",
        json={"expected_revision": 2},
    )
    assert parsed.status_code == 201
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
        return _plan()

    monkeypatch.setattr(project_plan_api, "plan_guided_engineering_project", fake_planner)
    planned = client.post(
        "/v1/projects/robot-r1/engineering/plan",
        json={
            "expected_revision": 3,
            "intake": {"project_name": "robot-r1", "goal": "Plan the robot"},
        },
    )

    assert planned.status_code == 200
    payload = planned.json()
    assert payload["revision"] == 4
    assert payload["materialized_robot_source_count"] == 1
    planning_source = captured["sources"][0]
    assert planning_source["format"] == "urdf"
    assert planning_source["content"] == robot_xml.decode("utf-8")
    assert planning_source["metadata"]["planning_materialization"] == "ephemeral_verified_blob_read"

    snapshot = store.load("robot-r1", revision=4)["snapshot"]
    assert "content" not in snapshot["engineeringSources"][0]
    assert robot_xml.decode("utf-8") not in str(snapshot)
    assert len(snapshot["engineeringSourceParserRuns"]) == 1


def test_json_derived_sources_join_planning_boundary(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = ProjectStore(tmp_path)
    client = _seed(store)
    ingested = client.post(
        "/v1/projects/robot-r1/sources/ingest",
        json={
            "filename": "sources.json",
            "content_base64": _b64(
                b'[{"source_id":"manual-a","source_type":"manual"}]'
            ),
            "expected_revision": 1,
        },
    ).json()
    source_id = ingested["ingestion"]["source_id"]
    parsed = client.post(
        f"/v1/projects/robot-r1/sources/{source_id}/parse",
        json={"expected_revision": 2},
    )
    assert parsed.status_code == 201
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
        return _plan()

    monkeypatch.setattr(project_plan_api, "plan_guided_engineering_project", fake_planner)
    planned = client.post(
        "/v1/projects/robot-r1/engineering/plan",
        json={
            "expected_revision": 3,
            "intake": {"project_name": "robot-r1", "goal": "Plan from sources"},
        },
    )

    assert planned.status_code == 200
    payload = planned.json()
    assert payload["parsed_derived_source_count"] == 1
    assert payload["combined_source_count"] == 2
    assert {row["source_id"] for row in captured["sources"]} == {
        source_id,
        "manual-a",
    }
    derived = next(row for row in captured["sources"] if row["source_id"] == "manual-a")
    assert derived["authority_ceiling"] == "declared"
    assert derived["metadata"]["authority_bounded_by_parent_upload"] is True
