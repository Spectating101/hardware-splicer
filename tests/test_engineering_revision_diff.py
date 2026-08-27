from __future__ import annotations

from hardware_splicer.engineering_revision_diff import diff_engineering_revisions


def _base_plan() -> dict:
    return {
        "machine_project": {
            "project_id": "revision-project",
            "components": [{"component_id": "controller"}],
            "interfaces": [],
            "artifacts": [
                {
                    "artifact_id": "firmware",
                    "kind": "binary",
                    "ref": "release/fw.bin",
                    "authority": "declared",
                    "metadata": {"revision": "r1", "content_hash": "sha256:old"},
                }
            ],
            "evidence": [],
            "verifications": [],
            "discipline_payloads": {
                "engineering_execution_evidence": {
                    "manifests": [
                        {
                            "execution_id": "pytest-main",
                            "operation": "pytest",
                            "status": "failed",
                            "manifest_hash": "sha256:failed",
                            "returncode": 1,
                            "output_hashes": {},
                        }
                    ]
                }
            },
        },
        "robot_topology": {
            "links": [{"link_id": "base"}],
            "joints": [],
            "actuators": [],
            "sensors": [],
            "unresolved": [],
        },
        "manufacturing_projection": {
            "projected_component_ids": [],
            "projected_interface_ids": [],
            "projected_artifact_ids": [],
        },
        "engineering_source_graph": {"unresolved_source_ids": [], "conflicts": []},
        "engineering_analysis": {
            "findings": [
                {
                    "finding_id": "analysis-current",
                    "category": "power",
                    "status": "fail",
                    "message": "Current margin is negative.",
                    "target_ids": ["controller"],
                    "missing_inputs": [],
                    "blocking": True,
                }
            ]
        },
        "manufacturing_closure": {"checks": []},
        "engineering_execution_plan": {"unresolved": []},
        "change_impact": {"impacts": [], "unresolved": []},
        "missing_info": [],
        "engineering_readiness": {"status": "blocked"},
    }


def _candidate_plan() -> dict:
    plan = _base_plan()
    plan["machine_project"] = dict(plan["machine_project"])
    plan["machine_project"]["components"] = [
        {"component_id": "controller"},
        {"component_id": "current-sensor"},
    ]
    plan["machine_project"]["artifacts"] = [
        {
            "artifact_id": "firmware",
            "kind": "binary",
            "ref": "release/fw.bin",
            "authority": "declared",
            "metadata": {"revision": "r2", "content_hash": "sha256:new"},
        }
    ]
    plan["machine_project"]["discipline_payloads"] = {
        "engineering_execution_evidence": {
            "manifests": [
                {
                    "execution_id": "pytest-main",
                    "operation": "pytest",
                    "status": "passed",
                    "manifest_hash": "sha256:passed",
                    "returncode": 0,
                    "output_hashes": {},
                }
            ]
        }
    }
    plan["engineering_analysis"] = {"findings": []}
    plan["manufacturing_closure"] = {
        "checks": [
            {
                "check_id": "harness-pinout",
                "status": "fail",
                "severity": "error",
                "message": "Harness pinout remains unresolved.",
                "target_ids": ["harness"],
                "source_ids": [],
                "unresolved_fields": ["conductors"],
            }
        ]
    }
    plan["engineering_readiness"] = {"status": "blocked"}
    return plan


def test_diff_tracks_resolved_opened_identity_artifact_and_execution_changes() -> None:
    report = diff_engineering_revisions(
        _base_plan(),
        _candidate_plan(),
        base_revision=1,
        candidate_revision=2,
    )

    assert {row.blocker_id for row in report.resolved_blockers} == {
        "analysis-current",
        "execution-result-pytest-main",
    }
    assert {row.blocker_id for row in report.opened_blockers} == {"harness-pinout"}
    component_change = next(row for row in report.identity_changes if row.category == "machine_components")
    assert component_change.added_ids == ["current-sensor"]
    assert report.artifact_changes[0].artifact_id == "firmware"
    assert report.artifact_changes[0].base["revision"] == "r1"
    assert report.artifact_changes[0].candidate["revision"] == "r2"
    assert report.execution_changes[0]["base"]["status"] == "failed"
    assert report.execution_changes[0]["candidate"]["status"] == "passed"
    assert report.summary["resolved_blocker_count"] == 2
    assert report.summary["opened_blocker_count"] == 1


def test_diff_flags_candidate_physical_authority_promotion() -> None:
    candidate = _candidate_plan()
    candidate["engineering_readiness"]["motion_authorized"] = True
    candidate["scenario"] = {"release_authorized": True}

    report = diff_engineering_revisions(_base_plan(), candidate)

    assert any("motion_authorized=true" in row for row in report.authority_regressions)
    assert any("release_authorized=true" in row for row in report.authority_regressions)
    assert report.metadata["physical_authority_unchanged"] is False
    assert report.metadata["automatic_merge"] is False
