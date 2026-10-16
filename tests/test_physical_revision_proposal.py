from __future__ import annotations

from hardware_splicer.mission_physical_log import MissionPhysicalLog
from hardware_splicer.mission_store import MissionStore
from hardware_splicer.physical_revision_proposal import PhysicalRevisionProposalBuilder
from hardware_splicer.project_store import ProjectStore


AGENT = {"kind": "agent", "id": "fabricator-agent"}
HUMAN = {"kind": "human", "id": "bench-owner"}


def _snapshot():
    return {
        "projectId": "logger",
        "projectName": "Logger",
        "currentStage": "design",
        "mode": "greenfield",
        "graph": {"nodes": [], "edges": []},
        "machineProject": {"project_id": "logger", "name": "Logger", "purpose": "test"},
    }


def test_failed_promoted_evidence_grounds_reviewable_revision_without_mutating_mission(tmp_path):
    projects = ProjectStore(tmp_path)
    projects.save("logger", _snapshot(), expected_revision=0)
    missions = MissionStore(projects)
    mission = missions.open_mission(
        "logger",
        intake={"goal": "make a logger", "constraints": [], "inventory": []},
        author=AGENT,
    )
    mission = missions.accept_mission("logger", mission["mission_id"], author=HUMAN)
    before_seq = mission["last_event_seq"]

    physical = MissionPhysicalLog(missions)
    physical.record(
        "logger",
        mission["mission_id"],
        receipt_type="evidence",
        source={
            "schema_version": "hardware_splicer.physical_evidence.v1",
            "evidence_id": "ev-fit-1",
            "project_id": "logger",
            "candidate_revision": "candidate-a-r1",
            "kind": "dimensional_measurement",
            "target_ids": ["enclosure"],
            "procedure_id": "fit-check",
            "passed": False,
            "captured_at": "2026-10-17T00:00:00+00:00",
            "operator": "bench-owner",
            "measured_values": {"connector_offset_mm": 1.8},
            "acceptance_criteria": {"max_abs_offset_mm": 0.5},
            "instrument_ids": [],
            "calibration_ids": [],
            "artifact_hashes": {},
            "environment": {},
            "fixture_state": {},
            "interlock_state": {},
            "raw_refs": [],
            "authority": "measured",
            "metadata": {"simulated": False},
        },
    )

    proposal = PhysicalRevisionProposalBuilder(physical_log=physical).build(
        "logger", mission["mission_id"]
    )
    assert proposal["needs_revision"] is True
    assert proposal["failed_evidence"][0]["evidence_id"] == "ev-fit-1"
    assert proposal["automatic_project_mutation"] is False
    assert proposal["automatic_mission_reopen"] is False
    PhysicalRevisionProposalBuilder.require_grounded_revision(proposal)

    after = missions.get_mission("logger", mission["mission_id"])
    assert after["last_event_seq"] == before_seq
    assert projects.load("logger")["revision"] == 1
