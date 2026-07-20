from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.project_store import (
    CorruptProject,
    InvalidProjectId,
    ProjectNotFound,
    ProjectStore,
    RevisionConflict,
)


def snapshot(project_id: str = "robot") -> dict:
    return {
        "projectId": project_id,
        "projectName": "Robot drive",
        "mode": "salvage",
        "currentStage": "design",
        "graph": {
            "phrase": "ESP32 robot with donor motor driver",
            "nodes": [{"id": "esp32"}, {"id": "donor-driver"}],
            "edges": [{"source": "esp32", "target": "donor-driver"}],
        },
        "buildDir": "/tmp/external-build-reference",
        "evidence": {"firmware_authorized": False, "power_authorized": False},
    }


def test_save_load_and_revision_conflict(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    first = store.save("robot", snapshot(), expected_revision=0)
    second = store.save("robot", {**snapshot(), "currentStage": "verify"}, expected_revision=1)

    assert first["revision"] == 1
    assert second["revision"] == 2
    assert store.load("robot")["snapshot"]["currentStage"] == "verify"
    assert store.load("robot", revision=1)["snapshot"]["currentStage"] == "design"

    with pytest.raises(RevisionConflict):
        store.save("robot", snapshot(), expected_revision=1)


def test_rejects_unsafe_project_ids(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    for unsafe in ("../robot", "/absolute", ".", "", "robot/child", " robot"):
        with pytest.raises(InvalidProjectId):
            store.save(unsafe, snapshot())


def test_corrupt_latest_revision_recovers_previous_valid_snapshot(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    store.save("robot", {**snapshot(), "currentStage": "verify"}, expected_revision=1)

    latest_path = tmp_path / "robot" / "revisions" / "00000002.json"
    latest_path.write_text("{not-json", encoding="utf-8")

    recovered = store.load("robot")
    assert recovered["revision"] == 1
    assert recovered["snapshot"]["currentStage"] == "design"


def test_corrupt_all_revisions_is_reported(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot())
    (tmp_path / "robot" / "revisions" / "00000001.json").write_text("[]", encoding="utf-8")
    with pytest.raises(CorruptProject):
        store.load("robot")


def test_list_archive_duplicate_and_delete(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot())
    duplicate = store.duplicate("robot", "robot-copy")

    assert duplicate["snapshot"]["projectId"] == "robot-copy"
    assert duplicate["metadata"] == {"duplicated_from": "robot", "source_revision": 1}
    assert {row["project_id"] for row in store.list_projects()} == {"robot", "robot-copy"}

    store.set_archived("robot", True)
    assert {row["project_id"] for row in store.list_projects()} == {"robot-copy"}
    assert {row["project_id"] for row in store.list_projects(include_archived=True)} == {"robot", "robot-copy"}

    store.delete("robot-copy")
    with pytest.raises(ProjectNotFound):
        store.load("robot-copy")


def test_store_keeps_build_directory_as_reference_only(tmp_path: Path) -> None:
    external = tmp_path / "external-build"
    external.mkdir()
    (external / "large.bin").write_bytes(b"x" * 1024)
    state = snapshot()
    state["buildDir"] = str(external)

    store = ProjectStore(tmp_path / "store")
    store.save("robot", state)

    revision = tmp_path / "store" / "robot" / "revisions" / "00000001.json"
    body = json.loads(revision.read_text(encoding="utf-8"))
    assert body["snapshot"]["buildDir"] == str(external)
    assert not list((tmp_path / "store").rglob("large.bin"))
