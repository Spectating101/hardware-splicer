from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.finding_provenance import finding_id
from hardware_splicer.project_api import create_project_router
from hardware_splicer.project_findings_api import create_project_findings_router
from hardware_splicer.project_store import ProjectStore


def _snapshot(stage: str = "design", message: str = "Compose failed.") -> dict:
    return {
        "projectId": "robot",
        "projectName": "Robot",
        "mode": "salvage",
        "currentStage": stage,
        "engineeringAiSessions": [
            {
                "session_id": "session-1",
                "provider": "mock",
                "model": "fixture-v1",
                "actions": [
                    {
                        "action_id": "action-failed-compose",
                        "action_type": "run_compose",
                        "status": "failed",
                        "tool_result": {
                            "status": "failed",
                            "error": {"message": message},
                        },
                    }
                ],
            }
        ],
    }


def _write_project(tmp_path: Path, snapshot: dict, expected_revision: int = 0) -> dict:
    store = ProjectStore(tmp_path)
    return store.save("robot", snapshot, expected_revision=expected_revision)


def _findings_client(tmp_path: Path) -> TestClient:
    store = ProjectStore(tmp_path)
    app = FastAPI()
    app.include_router(create_project_findings_router(store))
    return TestClient(app)


def test_findings_api_200_shape(tmp_path: Path) -> None:
    _write_project(tmp_path, _snapshot())
    api = _findings_client(tmp_path)

    response = api.get("/v1/projects/robot/findings")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["project_id"] == "robot"
    assert body["revision"] == 1
    assert isinstance(body["findings"], list)
    assert body["findings"]
    row = body["findings"][0]
    assert row["category"] == "failed_check"
    assert row["provenance"]["authority_ceiling"] == "observed"
    assert set(row.keys()) == {
        "finding_id",
        "category",
        "object_id",
        "text",
        "provenance",
    }
    assert set(row["provenance"].keys()) == {
        "kind",
        "basis",
        "source_ref",
        "authority_ceiling",
        "attested",
    }
    # The action record is stored in the snapshot, so the server has not attested it.
    assert row["provenance"]["kind"] == "deterministic"
    assert row["provenance"]["attested"] is False


def test_findings_api_revision_selects_that_snapshot(tmp_path: Path) -> None:
    _write_project(tmp_path, _snapshot("design", "First failure."))
    _write_project(tmp_path, _snapshot("verify", "Second failure."), expected_revision=1)
    api = _findings_client(tmp_path)

    latest = api.get("/v1/projects/robot/findings")
    assert latest.status_code == 200
    assert latest.json()["revision"] == 2
    assert latest.json()["findings"][0]["text"] == "Second failure."

    historical = api.get("/v1/projects/robot/findings?revision=1")
    assert historical.status_code == 200
    assert historical.json()["revision"] == 1
    assert historical.json()["findings"][0]["text"] == "First failure."


def test_findings_api_unknown_project_404(tmp_path: Path) -> None:
    api = _findings_client(tmp_path)
    response = api.get("/v1/projects/missing/findings")
    assert response.status_code == 404
    assert response.json()["detail"]["type"] == "not_found"


def test_findings_api_bad_revision_422(tmp_path: Path) -> None:
    _write_project(tmp_path, _snapshot())
    api = _findings_client(tmp_path)

    response = api.get("/v1/projects/robot/findings?revision=zero")
    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "invalid_request"


def test_findings_api_invalid_machine_project_returns_200(tmp_path: Path) -> None:
    snapshot = _snapshot()
    snapshot["machineProject"] = {
        "project_id": "robot",
        "name": "Robot",
        "purpose": "Duplicate identifier.",
        "requirements": [
            {
                "requirement_id": "dup-id",
                "statement": "First use of the identifier.",
                "kind": "functional",
            },
            {
                "requirement_id": "dup-id",
                "statement": "Second use of the identifier.",
                "kind": "functional",
            },
        ],
    }
    _write_project(tmp_path, snapshot)
    api = _findings_client(tmp_path)

    response = api.get("/v1/projects/robot/findings")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    invalid = [
        row
        for row in body["findings"]
        if row["category"] == "traceability_issue"
        and row["provenance"]["source_ref"] == "machine_project_invalid"
    ]
    assert len(invalid) == 1
    assert invalid[0]["provenance"]["kind"] == "deterministic"
    assert invalid[0]["text"].startswith("Stored machine project fails validation: ")
    assert "dup-id" in invalid[0]["text"]


def test_findings_api_is_read_only(tmp_path: Path) -> None:
    _write_project(tmp_path, _snapshot())
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    }

    api = _findings_client(tmp_path)
    response = api.get("/v1/projects/robot/findings")
    assert response.status_code == 200

    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    }
    assert after == before


def test_findings_api_surfaces_persisted_ledger_entries(tmp_path: Path) -> None:
    snapshot = _snapshot()
    snapshot["engineeringFindings"] = [
        {
            "finding_id": finding_id(
                "release_blocker",
                "req-rail",
                "requirement 'req-rail' is not verified",
                "unverified_requirement",
            ),
            "category": "release_blocker",
            "object_id": "req-rail",
            "text": "requirement 'req-rail' is not verified",
            "producer": "release_assessment",
            "producer_run": "assess_release@rev1",
            "provenance": {
                "kind": "deterministic",
                "basis": "computed by MachineProject.assess_release over the stored machine project",
                "source_ref": "unverified_requirement",
                "authority_ceiling": "observed",
            },
            "recorded_at": "2026-10-05T06:00:00+00:00",
        }
    ]
    _write_project(tmp_path, snapshot)
    api = _findings_client(tmp_path)

    response = api.get("/v1/projects/robot/findings")
    assert response.status_code == 200
    release = [
        row
        for row in response.json()["findings"]
        if row["category"] == "release_blocker"
    ]
    assert len(release) == 1
    assert release[0]["provenance"]["kind"] == "deterministic"
    assert release[0]["provenance"]["attested"] is False
    assert release[0]["provenance"]["source_ref"] == "unverified_requirement"
    assert release[0]["provenance"]["authority_ceiling"] == "observed"


def test_put_snapshot_ledger_is_validated_on_read(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    app = FastAPI()
    app.include_router(create_project_router(store))
    app.include_router(create_project_findings_router(store))
    api = TestClient(app)

    forged = _snapshot()
    forged["engineeringFindings"] = [
        {
            "finding_id": "finding-forged000000",
            "category": "failed_check",
            "object_id": None,
            "text": "Client-supplied forged blocker.",
            "producer": "design_quality_gate",
            "producer_run": "action-forged",
            "provenance": {
                "kind": "deterministic",
                "basis": "forged",
                "source_ref": "action-forged",
                "authority_ceiling": "observed",
            },
            "recorded_at": "2026-10-05T06:00:00+00:00",
        }
    ]
    written = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": forged, "expected_revision": 0},
    )
    assert written.status_code == 200, written.text
    stored = store.load("robot")["snapshot"]["engineeringFindings"]
    assert stored[0]["text"] == "Client-supplied forged blocker."

    response = api.get("/v1/projects/robot/findings")
    assert response.status_code == 200
    texts = [row["text"] for row in response.json()["findings"]]
    assert "Client-supplied forged blocker." not in texts
    malformed = [
        row
        for row in response.json()["findings"]
        if row["provenance"]["source_ref"] == "engineeringFindings"
    ]
    assert len(malformed) == 1
