from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.engineering_package_api import create_engineering_package_router
from hardware_splicer.engineering_package_download_api import (
    create_engineering_package_download_router,
)
from hardware_splicer.project_store import ProjectStore


def _snapshot() -> dict:
    session_id = "ai-session-package-api"
    action_id = "action-package-api"
    return {
        "projectId": "rover",
        "name": "Indoor rover",
        "engineeringSources": [
            {
                "source_id": "manual-1",
                "source_type": "manual",
                "content_hash": "sha256:manual",
                "authority_ceiling": "declared",
                "content": "SECRET RAW SOURCE",
            }
        ],
        "engineeringParsedSources": [],
        "engineeringAiSessions": [
            {
                "session_id": session_id,
                "project_id": "rover",
                "project_revision": 1,
                "mission": "Design a rover",
                "summary": "Candidate summary.",
                "requirements": [
                    {
                        "id": "req-1",
                        "statement": "Use a 3.3 V logic rail.",
                        "source_ids": ["manual-1"],
                    }
                ],
                "architecture_candidates": [
                    {
                        "id": "candidate-1",
                        "title": "Rover controller",
                        "summary": "Controller candidate.",
                    }
                ],
                "open_questions": ["Confirm the driver threshold."],
                "actions": [
                    {
                        "action_id": action_id,
                        "session_id": session_id,
                        "project_id": "rover",
                        "project_revision": 1,
                        "action_type": "run_compose",
                        "title": "Compose controller",
                        "rationale": "Validate the candidate.",
                        "status": "completed",
                        "source_ids": ["manual-1"],
                        "decision": {
                            "decision": "accepted",
                            "reviewer": "human",
                            "executed": False,
                        },
                        "tool_result": {
                            "status": "succeeded",
                            "executor_identity": "test-executor",
                            "summary": {"ok": True},
                            "artifact": {
                                "project_relative_path": "ai_tool_runs/result.json",
                                "sha256": "a" * 64,
                                "size_bytes": 20,
                            },
                            "automatic_execution": False,
                            "physical_authority_unchanged": True,
                        },
                        "automatic_execution": False,
                        "authority_effect": "none",
                    }
                ],
                "conversationTurns": [
                    {
                        "turn_id": "ai-turn-1",
                        "project_revision": 1,
                        "user_message": "Is it ready?",
                        "assistant_answer": "The software preview passed; physical evidence is still required.",
                        "answer_kind": "technical_answer",
                        "evidence_refs": [
                            {
                                "kind": "tool_result",
                                "id": action_id,
                                "reason": "The persisted preview passed.",
                            }
                        ],
                        "blockers": ["Physical evidence is missing."],
                    }
                ],
                "automatic_execution": False,
                "physical_authority_unchanged": True,
            }
        ],
        "fabrication_authorized": False,
        "firmware_flash_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "operational_authorized": False,
        "release_authorized": False,
    }


def _client(tmp_path: Path) -> tuple[TestClient, ProjectStore]:
    store = ProjectStore(tmp_path / "projects")
    store.save("rover", _snapshot())
    app = FastAPI()
    app.include_router(create_engineering_package_router(store))
    app.include_router(create_engineering_package_download_router(store))
    return TestClient(app), store


def test_package_api_creates_lists_downloads_and_replays(tmp_path: Path) -> None:
    client, store = _client(tmp_path)

    created = client.post(
        "/v1/projects/rover/engineering-packages",
        json={"expected_revision": 1},
    )

    assert created.status_code == 200, created.text
    body = created.json()
    assert body["revision"] == 2
    assert body["idempotent"] is False
    package = body["package"]
    assert package["source_revision"] == 1
    assert package["raw_source_bytes_included"] is False
    assert package["package_authority_effect"] == "none"
    assert body["authority_unchanged"] is True

    latest = store.load("rover")
    assert latest["revision"] == 2
    assert latest["snapshot"]["engineeringPackages"][0]["package_id"] == package["package_id"]
    assert latest["snapshot"]["power_on_authorized"] is False
    assert latest["snapshot"]["motion_authorized"] is False
    assert latest["snapshot"]["release_authorized"] is False

    listed = client.get("/v1/projects/rover/engineering-packages")
    assert listed.status_code == 200
    assert listed.json()["package_count"] == 1
    assert listed.json()["packages"][0]["zip_sha256"] == package["zip_sha256"]

    downloaded = client.get(
        f"/v1/projects/rover/engineering-packages/{package['package_id']}/download"
    )
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.headers["content-type"] == "application/zip"
    assert downloaded.headers["x-hardware-splicer-package-id"] == package["package_id"]
    assert downloaded.headers["x-hardware-splicer-package-sha256"] == package["zip_sha256"]
    assert hashlib.sha256(downloaded.content).hexdigest() == package["zip_sha256"]
    assert len(downloaded.content) == package["zip_size_bytes"]
    assert b"SECRET RAW SOURCE" not in downloaded.content

    replay = client.post(
        "/v1/projects/rover/engineering-packages",
        json={"expected_revision": 1},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["revision"] == 2
    assert replay.json()["idempotent"] is True
    assert replay.json()["package"]["package_id"] == package["package_id"]
    assert store.load("rover")["revision"] == 2


def test_package_api_refuses_stale_new_export_and_invalid_identity(tmp_path: Path) -> None:
    client, store = _client(tmp_path)
    store.save("rover", _snapshot(), expected_revision=1)

    stale = client.post(
        "/v1/projects/rover/engineering-packages",
        json={"expected_revision": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["type"] == "engineering_package_revision_conflict"

    invalid = client.get(
        "/v1/projects/rover/engineering-packages/../../project.json/download"
    )
    assert invalid.status_code in {404, 422}


def test_package_download_detects_tampering(tmp_path: Path) -> None:
    client, store = _client(tmp_path)
    created = client.post(
        "/v1/projects/rover/engineering-packages",
        json={"expected_revision": 1},
    )
    package = created.json()["package"]
    zip_path = store.root / "rover" / package["project_relative_zip"]
    zip_path.write_bytes(zip_path.read_bytes() + b"tampered")

    response = client.get(
        f"/v1/projects/rover/engineering-packages/{package['package_id']}/download"
    )
    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "invalid_engineering_package"


def test_package_schema_is_fail_closed(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)

    response = client.get("/v1/engineering/packages/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["deterministic_zip"] is True
    assert body["content_addressed_identity"] is True
    assert body["file_sha256_manifest"] is True
    assert body["raw_source_bytes_included"] is False
    assert body["package_authority_effect"] == "none"
    assert body["package_authorizes_physical_action"] is False
