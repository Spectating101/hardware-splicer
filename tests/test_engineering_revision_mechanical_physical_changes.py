from __future__ import annotations

from hardware_splicer.engineering_revision_diff import diff_engineering_revisions


def _plan() -> dict:
    return {
        "machine_project": {
            "project_id": "domain-diff",
            "components": [],
            "interfaces": [],
            "artifacts": [
                {
                    "artifact_id": "step-model-bracket",
                    "kind": "step_model",
                    "ref": "bracket.step",
                    "authority": "declared",
                    "metadata": {"content_hash": "sha256:old"},
                }
            ],
            "evidence": [],
            "verifications": [],
            "discipline_payloads": {},
        },
        "engineering_source_graph": {"unresolved_source_ids": [], "conflicts": []},
        "robot_topology": {"links": [], "joints": [], "actuators": [], "sensors": [], "unresolved": []},
        "engineering_analysis": {"findings": []},
        "manufacturing_closure": {"checks": []},
        "engineering_execution_plan": {"unresolved": []},
        "change_impact": {"impacts": [], "unresolved": []},
        "missing_info": [],
        "engineering_readiness": {"status": "candidate"},
        "mechanical_geometry": {
            "models": [
                {
                    "model_id": "bracket",
                    "content_hash": "sha256:old",
                    "file_schema": ["AP242"],
                    "products": ["Bracket"],
                    "units": ["mm"],
                    "bounding_box": {"minimum_mm": [0, 0, 0], "maximum_mm": [10, 10, 2]},
                    "unresolved": [],
                }
            ],
            "mounts": [],
        },
        "mechanical_fit": {
            "checks": [
                {
                    "check_id": "clearance",
                    "category": "aabb_clearance",
                    "status": "pass",
                    "message": "Clearance passes.",
                    "target_ids": ["arm", "enclosure"],
                    "unresolved_fields": [],
                    "metadata": {"clearance_mm": 3.0},
                }
            ],
            "clearance_boxes": [
                {
                    "object_id": "arm",
                    "frame_id": "assembly",
                    "minimum_mm": [0, 0, 0],
                    "maximum_mm": [10, 10, 10],
                }
            ],
            "clearance_requirements": [],
            "fastener_stacks": [],
        },
        "physical_evidence_package": {
            "calibrations": [
                {
                    "calibration_id": "cal-1",
                    "instrument_id": "meter-1",
                    "calibrated_at": "2026-08-01T00:00:00Z",
                    "authority": "verified",
                }
            ],
            "evidence": [],
            "decision": {
                "authorization_id": "auth-1",
                "status": "authorized",
                "scope": {"candidate_revision": "r1"},
                "reviewer": "reviewer",
            },
            "assessment": {"applicable": True, "authorized_operations": ["bench_power"]},
        },
        "scoped_release_assessment": {"allowed": True, "allowed_operations": ["bench_power"]},
    }


def test_revision_diff_tracks_mechanical_and_physical_scope_changes() -> None:
    base = _plan()
    candidate = _plan()
    candidate["machine_project"]["artifacts"][0]["metadata"]["content_hash"] = "sha256:new"
    candidate["mechanical_geometry"]["models"][0]["content_hash"] = "sha256:new"
    candidate["mechanical_fit"]["checks"][0]["status"] = "fail"
    candidate["mechanical_fit"]["checks"][0]["message"] = "Clearance fails."
    candidate["mechanical_fit"]["checks"][0]["metadata"]["clearance_mm"] = -1.0
    candidate["physical_evidence_package"]["decision"]["status"] = "revoked"
    candidate["physical_evidence_package"]["assessment"] = {
        "applicable": False,
        "authorized_operations": [],
        "blockers": ["Authorization revoked."],
    }
    candidate["scoped_release_assessment"] = {
        "allowed": False,
        "allowed_operations": [],
        "blockers": ["Authorization revoked."],
    }

    report = diff_engineering_revisions(base, candidate, base_revision="r1", candidate_revision="r2")

    assert report.artifact_changes[0]["change"] == "changed"
    mechanical_ids = {row["mechanical_id"] for row in report.mechanical_changes}
    assert "step_model:bracket" in mechanical_ids
    assert "fit_check:clearance" in mechanical_ids
    physical_ids = {row["physical_record_id"] for row in report.physical_authorization_changes}
    assert "authorization:auth-1" in physical_ids
    assert "physical_assessment" in physical_ids
    assert "scoped_release_assessment" in physical_ids
    assert report.summary["mechanical_change_count"] >= 2
    assert report.summary["physical_authorization_change_count"] >= 3
