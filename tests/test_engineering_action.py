from __future__ import annotations

from hardware_splicer.engineering_action import prepare_engineering_action
from hardware_splicer.machine_project_seed import machine_project_from_intake


def _base_plan() -> dict:
    project = machine_project_from_intake(
        {
            "project_name": "action-project",
            "goal": "Prepare the next engineering action.",
            "available_parts": [{"name": "controller", "type": "controller"}],
        }
    )
    return {
        "machine_project": project.model_dump(mode="json"),
        "engineering_source_graph": {"unresolved_source_ids": [], "conflicts": []},
        "robot_topology": {"topology_id": "generic", "links": [], "joints": [], "actuators": [], "sensors": [], "unresolved": []},
        "engineering_analysis": {"findings": []},
        "manufacturing_closure": {"checks": []},
        "engineering_execution_plan": {"checks": [], "unresolved": []},
        "change_impact": {"impacts": [], "unresolved": []},
        "missing_info": [],
        "engineering_readiness": {"status": "candidate"},
        "operator_guide": {"steps": []},
    }


def test_source_action_returns_decision_packet() -> None:
    plan = _base_plan()
    plan["engineering_source_graph"] = {
        "unresolved_source_ids": ["model-a"],
        "conflicts": [
            {
                "conflict_id": "conflict-voltage",
                "blocking": True,
                "reason": "Battery voltage differs.",
                "source_ids": ["manual-a", "manual-b"],
            }
        ],
    }

    prepared = prepare_engineering_action(plan)

    assert prepared.action.action_id == "next-source"
    assert prepared.payload["unresolved_source_ids"] == ["model-a"]
    assert prepared.payload["blocking_conflicts"][0]["conflict_id"] == "conflict-voltage"
    assert prepared.payload["decision_route"] == "/v1/engineering/sources/resolve-conflicts"
    assert prepared.metadata["automatic_execution"] is False
    assert prepared.metadata["motion_authorized"] is False


def test_execution_action_previews_checks_without_running_them(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EXECUTION_ROOT", str(tmp_path))
    (tmp_path / "artifact.bin").write_bytes(b"preview")
    plan = _base_plan()
    plan["engineering_execution_plan"] = {
        "checks": [
            {
                "execution_id": "hash-release",
                "operation": "artifact_hash",
                "workspace": ".",
                "target": "artifact.bin",
                "timeout_s": 30,
                "options": {},
                "expected_outputs": [],
                "execute": False,
            }
        ],
        "unresolved": [
            {
                "artifact_id": "remote-model",
                "reason": "Model is not materialized locally.",
            }
        ],
    }
    plan["missing_info"] = ["Prepare bounded execution input for remote-model: Model is not materialized locally."]

    prepared = prepare_engineering_action(plan, action_id="next-execution")

    assert prepared.action.category == "execution"
    assert prepared.payload["previews"][0]["status"] == "planned"
    assert prepared.payload["previews"][0]["metadata"]["execute_requested"] is False
    assert prepared.warnings == ["Model is not materialized locally."]
    assert prepared.metadata["device_access_authorized"] is False
    assert prepared.metadata["flash_authorized"] is False


def test_release_action_returns_human_review_packet_without_authority() -> None:
    plan = _base_plan()

    prepared = prepare_engineering_action(plan, action_id="next-release")

    assert prepared.action.category == "release"
    assert prepared.payload["physical_evidence_required"] is True
    assert prepared.payload["human_authorization_required"] is True
    assert prepared.payload["review_route"] == "/v1/engineering/guide"
    assert prepared.metadata["release_authorized"] is False
