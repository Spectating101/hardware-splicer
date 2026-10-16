from __future__ import annotations

import hashlib

import pytest

from hardware_splicer.device_draft import draft_from_parts_text
from hardware_splicer.mission_physical_log import MissionPhysicalLog
from hardware_splicer.mission_store import MissionStateError, MissionStore, MissionValidationError
from hardware_splicer.physical_observation_store import PhysicalObservationStore
from hardware_splicer.project_store import ProjectStore

AGENT = {"kind": "agent", "id": "planner-model"}
HUMAN = {"kind": "human", "id": "bench-lead"}
SPEC = draft_from_parts_text({"text": "Raspberry Pi Pico\nBME280 breakout\n0.96 inch OLED"})["spec"]


def _snapshot() -> dict:
    return {
        "projectId": "monitor",
        "projectName": "Field monitor",
        "currentStage": "design",
        "mode": "greenfield",
        "graph": {"nodes": [], "edges": []},
        "machineProject": {
            "project_id": "monitor",
            "name": "Field monitor",
            "purpose": "Portable environmental monitor",
        },
    }


def _runtime(tmp_path):
    projects = ProjectStore(tmp_path)
    projects.save("monitor", _snapshot(), expected_revision=0)
    missions = MissionStore(projects)
    mission = missions.open_mission(
        "monitor",
        intake={
            "goal": "A portable environmental monitor",
            "constraints": ["USB powered"],
            "inventory": ["Raspberry Pi Pico", "BME280 breakout", "0.96 inch OLED"],
        },
        author=AGENT,
    )
    return projects, missions, mission


def _accept_and_candidate(missions: MissionStore, mission: dict) -> dict:
    mission = missions.accept_mission("monitor", mission["mission_id"], author=HUMAN)
    return missions.propose(
        "monitor",
        mission["mission_id"],
        {
            "type": "candidate_proposed",
            "candidate": {
                "id": "A",
                "kind": "clean_sheet",
                "label": "Candidate A",
                "spec": SPEC,
                "rationale": "fits the inventory",
            },
        },
        author=AGENT,
        expected_event_seq=mission["last_event_seq"],
    )


def _ready(missions: MissionStore, mission: dict) -> dict:
    for operation in ("device_plan", "device_engineering"):
        mission = missions.record_evaluation(
            "monitor",
            mission["mission_id"],
            candidate_id="A",
            operation=operation,
            result={
                "errors": 0,
                "warnings": 0,
                "result_sha256": "0" * 64,
                "summary": f"{operation} passes",
            },
        )
    view = missions.get_mission("monitor", mission["mission_id"])
    return missions.propose(
        "monitor",
        mission["mission_id"],
        {
            "type": "terminal_proposed",
            "state": "READY_FOR_HUMAN_BUILD",
            "candidate_id": "A",
            "reason": "software checks support a human build",
        },
        author=AGENT,
        expected_event_seq=view["last_event_seq"],
    )


def _dispatch_receipt(mission_id: str) -> dict:
    return {
        "schema": "hardware_splicer.physical_dispatch_receipt.v1",
        "project_id": "monitor",
        "mission_id": mission_id,
        "operator_id": "printer-1",
        "operator_kind": "printer",
        "action": "start",
        "action_class": "actuate",
        "execution_plan_sha256": "1" * 64,
        "payload_sha256": "2" * 64,
        "authority": "human_grant_consumed",
        "grant_id": "pg-test",
        "physical_correctness": "UNPROVEN",
        "result": {"accepted": True},
    }


def test_physical_receipts_require_a_human_accepted_mission(tmp_path):
    _projects, missions, mission = _runtime(tmp_path)
    log = MissionPhysicalLog(missions)
    with pytest.raises(MissionStateError, match="accepted"):
        log.record(
            "monitor",
            mission["mission_id"],
            receipt_type="dispatch",
            source=_dispatch_receipt(mission["mission_id"]),
        )


def test_physical_log_continues_after_ready_terminal_without_reopening_mission(tmp_path):
    _projects, missions, mission = _runtime(tmp_path)
    mission = _accept_and_candidate(missions, mission)
    terminal = _ready(missions, mission)
    before = missions.get_mission("monitor", terminal["mission_id"])
    assert before["terminal"]["state"] == "READY_FOR_HUMAN_BUILD"

    log = MissionPhysicalLog(missions)
    recorded = log.record(
        "monitor",
        terminal["mission_id"],
        receipt_type="dispatch",
        source=_dispatch_receipt(terminal["mission_id"]),
        candidate_id="A",
    )
    after = missions.get_mission("monitor", terminal["mission_id"])
    assert after == before, "physical sidecar must not mutate mission replay truth"
    assert recorded["mission_terminal_state_unchanged"] is True
    assert recorded["physical_correctness"] == "UNPROVEN"
    assert recorded["grants_physical_authority"] is False
    assert log.list("monitor", terminal["mission_id"]) == [recorded]


def test_raw_observation_artifact_can_be_linked_without_becoming_a_pass(tmp_path):
    _projects, missions, mission = _runtime(tmp_path)
    mission = _accept_and_candidate(missions, mission)
    observations = PhysicalObservationStore(tmp_path / "raw-observations")
    raw = observations.put(
        kind="image",
        source_id="camera-a",
        media_type="image/png",
        data=b"frame",
    )
    log = MissionPhysicalLog(missions)
    recorded = log.record(
        "monitor",
        mission["mission_id"],
        receipt_type="observation",
        source=raw.public_dict(),
        candidate_id="A",
    )
    assert recorded["source"]["physical_correctness"] == "UNPROVEN"
    assert recorded["receipt_type"] == "observation"
    assert recorded["source_sha256"]


def test_log_refuses_fake_physical_correctness_and_unknown_candidate(tmp_path):
    _projects, missions, mission = _runtime(tmp_path)
    mission = _accept_and_candidate(missions, mission)
    log = MissionPhysicalLog(missions)
    receipt = _dispatch_receipt(mission["mission_id"])
    receipt["physical_correctness"] = "PROVEN"
    with pytest.raises(MissionValidationError, match="UNPROVEN"):
        log.record(
            "monitor",
            mission["mission_id"],
            receipt_type="dispatch",
            source=receipt,
            candidate_id="A",
        )

    with pytest.raises(MissionValidationError, match="does not exist"):
        log.record(
            "monitor",
            mission["mission_id"],
            receipt_type="dispatch",
            source=_dispatch_receipt(mission["mission_id"]),
            candidate_id="Z",
        )


def test_retained_source_hash_detects_tampering(tmp_path):
    projects, missions, mission = _runtime(tmp_path)
    mission = _accept_and_candidate(missions, mission)
    log = MissionPhysicalLog(missions)
    record = log.record(
        "monitor",
        mission["mission_id"],
        receipt_type="dispatch",
        source=_dispatch_receipt(mission["mission_id"]),
    )
    path = (
        projects.root
        / "monitor"
        / "missions"
        / mission["mission_id"]
        / "physical"
        / "receipts"
        / "00000001.json"
    )
    import json

    value = json.loads(path.read_text(encoding="utf-8"))
    value["source"]["action"] = "cancel"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(Exception, match="hash"):
        log.read("monitor", mission["mission_id"], 1)
