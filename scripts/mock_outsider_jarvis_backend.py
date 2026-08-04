#!/usr/bin/env python3
"""Stateful deterministic backend for the outsider JARVIS browser test."""

from __future__ import annotations

import io
import json
import zipfile
from copy import deepcopy
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

PROJECT_ID = "outsider-fixture"
SESSION_ID = "outsider-session"
FAILED_ACTION_ID = "action-failed-compose"
REPAIR_SESSION_ID = "outsider-repair-session"
TURN_ID = "turn-outsider-001"
VERIFY_ACTION_ID = "action-prepare-verification"
PACKAGE_ID = "engineering-package-r00000008-outsiderfixture"
SNAPSHOT_SHA = "1" * 64
MANIFEST_SHA = "2" * 64
ZIP_SHA = "3" * 64

app = FastAPI()
state: dict[str, Any] = {
    "revision": 6,
    "turn_added": False,
    "repair_added": False,
    "package": None,
}


def failed_action() -> dict[str, Any]:
    repair_sessions = []
    if state["repair_added"]:
        repair_sessions = [
            {
                "session_id": REPAIR_SESSION_ID,
                "failure_sha256": "f" * 64,
                "repair_iteration": 1,
            }
        ]
    return {
        "action_id": FAILED_ACTION_ID,
        "session_id": SESSION_ID,
        "project_id": PROJECT_ID,
        "project_revision": 4,
        "action_type": "run_compose",
        "title": "Compile the DUT validation adapter",
        "rationale": "Expose the unprotected 1.8 V and 3.3 V boundary.",
        "inputs": {"dut_io_v": 1.8, "controller_io_v": 3.3},
        "source_ids": ["dut-datasheet-r1", "fixture-controller-manual-r1"],
        "status": "failed",
        "authority": "proposed",
        "authority_effect": "none",
        "automatic_execution": False,
        "decision": {
            "decision": "accepted",
            "reviewer": "fixture-reviewer",
            "note": "Software preview only.",
        },
        "repair_sessions": repair_sessions,
        "tool_result": {
            "status": "failed",
            "session_id": SESSION_ID,
            "action_id": FAILED_ACTION_ID,
            "action_type": "run_compose",
            "executor_identity": "mock.compose.v1",
            "summary": {
                "message": "1.8 V DUT interface is not protected from 3.3 V controller"
            },
            "error": {
                "type": "RuntimeError",
                "message": "1.8 V DUT interface is not protected from 3.3 V controller",
            },
            "artifact": {
                "project_relative_path": "ai_tool_previews/failed-compose.json",
                "sha256": "a" * 64,
                "size_bytes": 512,
            },
            "automatic_execution": False,
            "authority_effect": "none",
            "fabrication_authorized": False,
            "firmware_flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "operational_authorized": False,
            "release_authorized": False,
        },
    }


def verify_action() -> dict[str, Any]:
    return {
        "action_id": VERIFY_ACTION_ID,
        "session_id": SESSION_ID,
        "project_id": PROJECT_ID,
        "project_revision": 6,
        "action_type": "prepare_verification",
        "title": "Prepare fixture pre-fabrication verification",
        "rationale": "Close level translation, no-connect, current-limit, and orientation evidence.",
        "inputs": {"scope": "dut_voltage_domains_and_fixture_safety"},
        "source_ids": ["dut-datasheet-r1", "fixture-controller-manual-r1"],
        "origin_turn_id": TURN_ID,
        "status": "proposed",
        "authority": "proposed",
        "authority_effect": "none",
        "automatic_execution": False,
        "decision": None,
        "tool_result": None,
    }


def parent_session() -> dict[str, Any]:
    turns = []
    actions = [failed_action()]
    if state["turn_added"]:
        turns = [
            {
                "turn_id": TURN_ID,
                "project_revision": 6,
                "user_message": "Is this fixture ready for fabrication?",
                "assistant_answer": "The fixture is not pre-fabrication ready. The 1.8 V DUT remains exposed to a 3.3 V controller assumption.",
                "answer_kind": "decision_briefing",
                "evidence_refs": [
                    {
                        "kind": "tool_result",
                        "id": FAILED_ACTION_ID,
                        "reason": "The deterministic compose preview failed on the voltage-domain boundary.",
                    },
                    {
                        "kind": "source",
                        "id": "dut-datasheet-r1",
                        "reason": "The declared DUT limit prohibits direct 3.3 V drive.",
                    },
                ],
                "blockers": [
                    "No powered-off high-impedance translator is proven.",
                    "No physical current-limited DUT evidence exists.",
                ],
                "recommended_action_id": VERIFY_ACTION_ID,
            }
        ]
        actions.append(verify_action())
    return {
        "session_id": SESSION_ID,
        "session_kind": "project_proposal",
        "project_id": PROJECT_ID,
        "project_revision": 2,
        "model_profile": "deep_synthesis",
        "provider": "mock",
        "model": "outsider-fixture-v1",
        "mission": "Prepare a safe low-voltage DUT validation adapter.",
        "summary": "The fixture is blocked by an unprotected 1.8 V and 3.3 V boundary.",
        "requirements": [
            {
                "id": "req-dut-domain",
                "statement": "Every DUT-facing digital signal must remain in the 1.8 V domain.",
                "source_ids": ["dut-datasheet-r1"],
            }
        ],
        "architecture_candidates": [
            {
                "id": "candidate-direct-controller-adapter",
                "title": "Direct controller DUT adapter",
                "summary": "A blocked candidate awaiting protected translation.",
                "tradeoffs": ["Direct 3.3 V drive is unsafe."],
            }
        ],
        "open_questions": ["Which powered-off-safe translator will be used?"],
        "actions": actions,
        "conversationTurns": turns,
        "automatic_execution": False,
        "physical_authority_unchanged": True,
    }


def repair_session() -> dict[str, Any]:
    return {
        "session_id": REPAIR_SESSION_ID,
        "session_kind": "failure_repair",
        "project_id": PROJECT_ID,
        "project_revision": 7,
        "model_profile": "design_repair",
        "provider": "mock",
        "model": "outsider-repair-v1",
        "mission": "Prepare a safe low-voltage DUT validation adapter.",
        "summary": "Add default-off 1.8 V referenced translation and explicit sequencing.",
        "requirements": [
            {
                "id": "req-default-off-translation",
                "statement": "Controller paths remain high impedance until translation is valid.",
                "source_ids": ["dut-datasheet-r1", "fixture-controller-manual-r1"],
            }
        ],
        "architecture_candidates": [
            {
                "id": "candidate-protected-dut-adapter",
                "title": "Default-off translated DUT adapter",
                "summary": "A successor with protected voltage domains and sequencing.",
                "tradeoffs": ["More BOM and routing complexity."],
                "lineage": {
                    "kind": "repair_successor",
                    "parent_session_id": SESSION_ID,
                    "parent_action_id": FAILED_ACTION_ID,
                    "failure_sha256": "f" * 64,
                    "repair_iteration": 1,
                },
            }
        ],
        "open_questions": ["Confirm the translator powered-off behavior."],
        "actions": [
            {
                "action_id": "action-revise-protected-interface",
                "action_type": "revise_candidate",
                "title": "Add protected translation",
                "rationale": "Resolve the voltage-domain failure.",
                "status": "proposed",
                "authority_effect": "none",
                "automatic_execution": False,
                "tool_result": None,
                "decision": None,
            }
        ],
        "repair_of": {
            "parent_session_id": SESSION_ID,
            "parent_action_id": FAILED_ACTION_ID,
            "failure_sha256": "f" * 64,
            "repair_iteration": 1,
        },
        "automatic_execution": False,
        "physical_authority_unchanged": True,
    }


def snapshot() -> dict[str, Any]:
    sessions = [parent_session()]
    if state["repair_added"]:
        sessions.append(repair_session())
    packages = [state["package"]] if state["package"] else []
    return {
        "projectId": PROJECT_ID,
        "name": "Outsider DUT fixture",
        "mission": "Prepare a safe low-voltage DUT validation adapter.",
        "engineeringSources": [
            {"source_id": "dut-datasheet-r1", "source_type": "datasheet"},
            {"source_id": "fixture-controller-manual-r1", "source_type": "manual"},
        ],
        "engineeringSourceParserRuns": [],
        "engineeringAiSessions": sessions,
        "engineeringPackages": packages,
        "fabrication_authorized": False,
        "firmware_flash_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "operational_authorized": False,
        "release_authorized": False,
    }


def package_record() -> dict[str, Any]:
    return {
        "package_id": PACKAGE_ID,
        "project_id": PROJECT_ID,
        "source_revision": 8,
        "snapshot_sha256": SNAPSHOT_SHA,
        "manifest_sha256": MANIFEST_SHA,
        "zip_sha256": ZIP_SHA,
        "zip_size_bytes": len(package_bytes()),
        "file_count": 15,
        "raw_source_bytes_included": False,
        "package_authority_effect": "none",
        "physical_authority_unchanged": True,
    }


def package_bytes() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("ENGINEERING_PACKAGE/README.md", "Outsider fixture package\n")
        archive.writestr(
            "ENGINEERING_PACKAGE/AUTHORITY_STATE.json",
            json.dumps({"package_authorizes_physical_action": False}),
        )
    return stream.getvalue()


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.get("/v1/projects/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    if project_id != PROJECT_ID:
        raise HTTPException(status_code=404, detail="project not found")
    return {
        "ok": True,
        "project": {
            "project_id": PROJECT_ID,
            "revision": state["revision"],
            "snapshot": snapshot(),
        },
    }


@app.get("/v1/projects/{project_id}/ai-sessions/{session_id}")
def get_session(project_id: str, session_id: str) -> dict[str, Any]:
    if project_id != PROJECT_ID:
        raise HTTPException(status_code=404, detail="project not found")
    if session_id == SESSION_ID:
        session = parent_session()
    elif session_id == REPAIR_SESSION_ID and state["repair_added"]:
        session = repair_session()
    else:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "ok": True,
        "project_id": PROJECT_ID,
        "revision": state["revision"],
        "session": session,
    }


@app.post("/v1/projects/{project_id}/ai-sessions/{session_id}/turns")
async def create_turn(project_id: str, session_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    if project_id != PROJECT_ID or session_id != SESSION_ID:
        raise HTTPException(status_code=404, detail="session not found")
    if int(body.get("expected_revision") or 0) != state["revision"]:
        raise HTTPException(status_code=409, detail="revision conflict")
    state["turn_added"] = True
    state["revision"] += 1
    session = parent_session()
    return {
        "ok": True,
        "project_id": PROJECT_ID,
        "revision": state["revision"],
        "session_id": SESSION_ID,
        "turn": session["conversationTurns"][0],
        "session": session,
        "idempotent": False,
        "automatic_execution": False,
        "authority_unchanged": True,
    }


@app.post(
    "/v1/projects/{project_id}/ai-sessions/{session_id}/actions/{action_id}/repair"
)
async def create_repair(
    project_id: str, session_id: str, action_id: str, request: Request
) -> dict[str, Any]:
    body = await request.json()
    if (project_id, session_id, action_id) != (
        PROJECT_ID,
        SESSION_ID,
        FAILED_ACTION_ID,
    ):
        raise HTTPException(status_code=404, detail="failed action not found")
    if int(body.get("expected_revision") or 0) != state["revision"]:
        raise HTTPException(status_code=409, detail="revision conflict")
    state["repair_added"] = True
    state["revision"] += 1
    return {
        "ok": True,
        "project_id": PROJECT_ID,
        "revision": state["revision"],
        "parent_action": failed_action(),
        "repair_session": repair_session(),
        "idempotent": False,
        "automatic_execution": False,
        "authority_unchanged": True,
    }


@app.get("/v1/projects/{project_id}/engineering-packages")
def list_packages(project_id: str) -> dict[str, Any]:
    if project_id != PROJECT_ID:
        raise HTTPException(status_code=404, detail="project not found")
    packages = [state["package"]] if state["package"] else []
    return {
        "ok": True,
        "project_id": PROJECT_ID,
        "revision": state["revision"],
        "packages": packages,
        "package_count": len(packages),
    }


@app.post("/v1/projects/{project_id}/engineering-packages")
async def create_package(project_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    if project_id != PROJECT_ID:
        raise HTTPException(status_code=404, detail="project not found")
    expected_revision = int(body.get("expected_revision") or 0)
    if state["package"] is not None:
        return {
            "ok": True,
            "project_id": PROJECT_ID,
            "revision": state["revision"],
            "package": state["package"],
            "idempotent": True,
            "authority_unchanged": True,
        }
    if expected_revision != state["revision"]:
        raise HTTPException(status_code=409, detail="revision conflict")
    state["package"] = package_record()
    state["revision"] += 1
    return {
        "ok": True,
        "project_id": PROJECT_ID,
        "revision": state["revision"],
        "package": state["package"],
        "idempotent": False,
        "authority_unchanged": True,
    }


@app.get(
    "/v1/projects/{project_id}/engineering-packages/{package_id}/download"
)
def download_package(project_id: str, package_id: str) -> Response:
    if project_id != PROJECT_ID or package_id != PACKAGE_ID or state["package"] is None:
        raise HTTPException(status_code=404, detail="package not found")
    content = package_bytes()
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{PACKAGE_ID}.zip"',
            "Content-Length": str(len(content)),
            "X-Hardware-Splicer-Package-Id": PACKAGE_ID,
            "X-Hardware-Splicer-Package-Sha256": ZIP_SHA,
            "X-Hardware-Splicer-Source-Revision": "8",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8090)
