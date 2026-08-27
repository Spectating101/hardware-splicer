from __future__ import annotations

from hardware_splicer.engineering_revision_diff import diff_engineering_revisions


def _plan() -> dict:
    return {
        "machine_project": {
            "project_id": "nested-authority",
            "components": [],
            "interfaces": [],
            "artifacts": [],
            "evidence": [],
            "verifications": [],
            "metadata": {},
            "discipline_payloads": {},
        },
        "engineering_source_graph": {"unresolved_source_ids": [], "conflicts": []},
        "robot_topology": {"links": [], "joints": [], "actuators": [], "sensors": [], "unresolved": []},
        "engineering_analysis": {"findings": []},
        "manufacturing_closure": {"checks": []},
        "manufacturing_projection": {},
        "engineering_execution_plan": {"unresolved": []},
        "change_impact": {"impacts": [], "unresolved": []},
        "missing_info": [],
        "engineering_readiness": {"status": "candidate"},
    }


def test_nested_machine_payload_authority_flags_are_detected() -> None:
    base = _plan()
    candidate = _plan()
    candidate["machine_project"]["metadata"]["power_on_authorized"] = True
    candidate["machine_project"]["discipline_payloads"] = {
        "robot_operator_guide": {
            "steps": [
                {
                    "step_id": "first-motion",
                    "metadata": {"motion_authorized": True},
                }
            ]
        }
    }
    candidate["manufacturing_closure"]["metadata"] = {"fabrication_authorized": True}

    report = diff_engineering_revisions(base, candidate)

    assert any("machine_project.metadata.power_on_authorized=true" in row for row in report.authority_regressions)
    assert any("motion_authorized=true" in row for row in report.authority_regressions)
    assert any("manufacturing_closure.metadata.fabrication_authorized=true" in row for row in report.authority_regressions)
    assert report.summary["authority_regression_count"] == 3
    assert report.metadata["physical_authority_unchanged"] is False
