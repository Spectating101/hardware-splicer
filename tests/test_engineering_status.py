from __future__ import annotations

from hardware_splicer.engineering_status import build_engineering_status


def _plan() -> dict:
    return {
        "machine_project": {
            "project_id": "status-rover",
            "verifications": [
                {
                    "verification_id": "verification-current",
                    "name": "Current margin test",
                    "status": "failed",
                    "target_ids": ["power-system"],
                    "evidence_ids": ["evidence-current"],
                }
            ],
            "discipline_payloads": {},
        },
        "engineering_source_graph": {
            "unresolved_source_ids": [],
            "conflicts": [
                {
                    "conflict_id": "conflict-voltage",
                    "reason": "Two source revisions declare different battery voltages.",
                    "blocking": True,
                    "subject_id": "battery",
                    "source_ids": ["manual-a", "manual-b"],
                    "verification_targets": ["measure battery voltage"],
                }
            ],
        },
        "robot_topology": {
            "topology_id": "rover-topology",
            "unresolved": [
                {
                    "object_id": "left-wheel-joint",
                    "field": "limits",
                    "reason": "Wheel joint speed limit is unresolved.",
                }
            ],
        },
        "engineering_analysis": {
            "findings": [
                {
                    "finding_id": "analysis-current-margin",
                    "category": "power_current",
                    "status": "fail",
                    "message": "Declared supply current margin is negative.",
                    "target_ids": ["power-system"],
                    "missing_inputs": [],
                    "blocking": True,
                }
            ]
        },
        "manufacturing_closure": {
            "checks": [
                {
                    "check_id": "pin-mcu-gpio12",
                    "status": "fail",
                    "severity": "error",
                    "message": "Firmware and electrical nets conflict at MCU GPIO12.",
                    "target_ids": ["gpio12"],
                    "source_ids": ["mcu"],
                    "unresolved_fields": [],
                }
            ]
        },
        "engineering_execution_plan": {
            "unresolved": [
                {
                    "artifact_id": "board",
                    "operation": "artifact_hash",
                    "reason": "Release artifact is not available as a local workspace path.",
                }
            ]
        },
        "change_impact": {
            "impacts": [
                {
                    "impact_id": "impact-power",
                    "blocking": True,
                    "reason": "Power regression remains open.",
                    "target_ids": ["power-system"],
                    "required_evidence": ["brownout regression"],
                }
            ],
            "unresolved": [],
        },
        "missing_info": [
            "Manufacturing closure pin-mcu-gpio12: Firmware and electrical nets conflict at MCU GPIO12."
        ],
        "engineering_readiness": {"status": "blocked"},
    }


def test_status_ranks_source_boundary_first_and_groups_actions() -> None:
    status = build_engineering_status(_plan())

    assert status.overall_status == "blocked"
    assert status.current_phase == "source"
    assert status.next_action_id == "next-source"
    assert status.next_actions[0].route == "/v1/engineering/sources/resolve-conflicts"
    assert [row.category for row in status.next_actions[:5]] == [
        "source",
        "topology",
        "analysis",
        "manufacturing",
        "execution",
    ]
    assert status.summary["blocking_count"] >= 6
    assert status.summary["manufacturing_issue_count"] == 1


def test_status_deduplicates_missing_info_that_repeats_closure() -> None:
    status = build_engineering_status(_plan())

    messages = [row.message.lower() for row in [*status.blockers, *status.advisories]]
    assert len([row for row in messages if "firmware and electrical nets conflict" in row]) == 1


def test_next_actions_never_request_automatic_or_physical_execution() -> None:
    status = build_engineering_status(_plan())

    assert all(row.physical_action is False for row in status.next_actions)
    assert all(row.automatic_execution is False for row in status.next_actions)
    assert status.metadata["fabrication_authorized"] is False
    assert status.metadata["flash_authorized"] is False
    assert status.metadata["power_on_authorized"] is False
    assert status.metadata["motion_authorized"] is False
    assert status.metadata["release_authorized"] is False


def test_clean_plan_advances_to_release_review_candidate() -> None:
    status = build_engineering_status(
        {
            "machine_project": {
                "project_id": "clean-project",
                "verifications": [],
                "discipline_payloads": {},
            },
            "engineering_source_graph": {"unresolved_source_ids": [], "conflicts": []},
            "robot_topology": {"topology_id": "clean-topology", "unresolved": []},
            "engineering_analysis": {"findings": []},
            "manufacturing_closure": {"checks": []},
            "engineering_execution_plan": {"unresolved": []},
            "change_impact": {"impacts": [], "unresolved": []},
            "missing_info": [],
            "engineering_readiness": {"status": "candidate"},
        }
    )

    assert status.overall_status == "candidate"
    assert status.current_phase == "release"
    assert status.blockers == []
    assert status.advisories == []
    assert status.next_action_id == "next-release"
    assert len(status.next_actions) == 1
    assert status.next_actions[0].route == "/v1/engineering/guide"
    assert status.next_actions[0].physical_action is False
