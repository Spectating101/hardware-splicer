from __future__ import annotations

import json
import sys

import pytest

from hardware_splicer.cli_entry import main_capability_freeze


def _project(camera_part: str = "OV3660") -> dict:
    return {
        "project_id": "vision-project",
        "name": "Vision Core",
        "purpose": "Embedded vision baseline",
        "lifecycle_state": "verify",
        "requested_release_state": "design_ready",
        "subsystems": [
            {
                "subsystem_id": "vision-electrical",
                "name": "Vision electrical",
                "domain": "electrical",
                "component_ids": ["camera"],
            }
        ],
        "components": [
            {
                "component_id": "camera",
                "name": "Camera sensor",
                "domain": "electrical",
                "subsystem_id": "vision-electrical",
                "source": "new",
                "part": {
                    "manufacturer": "OmniVision",
                    "manufacturer_part_number": camera_part,
                },
                "authority": "declared",
            }
        ],
        "artifacts": [
            {
                "artifact_id": "firmware",
                "kind": "firmware",
                "ref": "firmware.bin",
                "authority": "verified",
                "metadata": {"content_hash": "sha256:firmware"},
            }
        ],
    }


def test_capability_freeze_projects_machine_project_and_hashes_source(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project.json"
    specs = tmp_path / "deps.json"
    output = tmp_path / "manifest.json"
    project.write_text(json.dumps(_project()), encoding="utf-8")
    specs.write_text(
        json.dumps(
            [
                {
                    "object_id": "camera",
                    "dependency_id": "component:camera:sensor_identity",
                    "kind": "component_identity",
                    "resolved": True,
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hs-capability-freeze",
            "--project",
            str(project),
            "--project-revision",
            "project-rev-7",
            "--capability-id",
            "vision-core",
            "--revision",
            "vision-a-r1",
            "--dependencies",
            str(specs),
            "--out",
            str(output),
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main_capability_freeze()

    assert exc.value.code == 0
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["status"] == "machine_project_projection"
    assert manifest["source_boundary"]["project_revision"] == "project-rev-7"
    assert manifest["source_boundary"]["project_content_hash"].startswith("sha256:")
    assert manifest["source_boundary"]["project_artifact_hashes"] == {
        "firmware": "sha256:firmware"
    }
    assert manifest["dependencies"][0]["value"]["part"]["manufacturer_part_number"] == "OV3660"
    assert manifest["metadata"]["alternate_engineering_truth_store"] is False


def test_capability_freeze_rejects_unknown_machine_project_object(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project.json"
    specs = tmp_path / "deps.json"
    output = tmp_path / "manifest.json"
    project.write_text(json.dumps(_project()), encoding="utf-8")
    specs.write_text(
        json.dumps([{"object_id": "not-real", "dependency_id": "x", "resolved": True}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hs-capability-freeze",
            "--project",
            str(project),
            "--project-revision",
            "project-rev-7",
            "--capability-id",
            "vision-core",
            "--revision",
            "vision-a-r1",
            "--dependencies",
            str(specs),
            "--out",
            str(output),
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main_capability_freeze()

    assert exc.value.code == 2
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "invalid"
    assert "unknown MachineProject object" in report["error"]
    assert report["physical_authority_granted"] is False


def test_capability_freeze_rejects_empty_dependency_scope(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project.json"
    specs = tmp_path / "deps.json"
    project.write_text(json.dumps(_project()), encoding="utf-8")
    specs.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hs-capability-freeze",
            "--project",
            str(project),
            "--project-revision",
            "project-rev-7",
            "--capability-id",
            "vision-core",
            "--revision",
            "vision-a-r1",
            "--dependencies",
            str(specs),
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main_capability_freeze()

    assert exc.value.code == 2
