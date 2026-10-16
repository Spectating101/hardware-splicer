"""A fabrication mission is an append-only event log beside a project, replayed into a state machine.

The agent proposes; HS code decides. Evaluations are recorded only by HS itself, never through a proposal. Success is
reaching the correct terminal state with an evidence trail: READY_FOR_HUMAN_BUILD is refused until HS's own evaluations
support it, and every BLOCKED_* state must cite the evidence that blocks it. A mission never changes a project
snapshot or revision and never grants physical authority.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.mission_store import (
    PHASES,
    TERMINAL_STATES,
    MissionConflict,
    MissionNotFound,
    MissionStateError,
    MissionStore,
    MissionValidationError,
)
from hardware_splicer.project_store import ProjectNotFound, ProjectStore

AGENT = {"kind": "agent", "id": "planner-model"}
HUMAN = {"kind": "human", "id": "bench-lead"}
SPEC = {"schema_version": "x", "modules": [], "connections": []}


def snapshot() -> dict:
    return {"projectId": "monitor", "projectName": "Field monitor", "currentStage": "design", "mode": "greenfield",
            "graph": {"nodes": [], "edges": []},
            "machineProject": {"project_id": "monitor", "name": "Field monitor", "purpose": "Portable environmental monitor"}}


def _store(tmp_path: Path) -> tuple[ProjectStore, MissionStore]:
    projects = ProjectStore(tmp_path)
    projects.save("monitor", snapshot(), expected_revision=0)
    return projects, MissionStore(projects)


def _open(missions: MissionStore, accepted: bool = True, **budgets) -> dict:
    intake = {"goal": "A portable environmental monitor", "constraints": ["USB powered", "under NT$2000"],
              "inventory": ["Raspberry Pi Pico", "BME280 breakout", "0.96 inch OLED"]}
    if budgets:
        intake["budgets"] = budgets
    mission = missions.open_mission("monitor", intake=intake, author=AGENT)
    if accepted:
        # A person accepts the mission and its budgets once; that is what lets HS record its own checks.
        mission = missions.accept_mission("monitor", mission["mission_id"], author=HUMAN)
    return mission


def _candidate(missions, mission, cid="A", kind="clean_sheet"):
    view = missions.get_mission("monitor", mission["mission_id"])
    return missions.propose("monitor", mission["mission_id"], {"type": "candidate_proposed", "candidate": {
        "id": cid, "kind": kind, "label": f"Candidate {cid}", "spec": SPEC, "rationale": "fits the inventory"}},
        author=AGENT, expected_event_seq=view["last_event_seq"])


def _evaluate(missions, mission, cid="A", operation="device_plan", errors=0, warnings=0):
    return missions.record_evaluation("monitor", mission["mission_id"], candidate_id=cid, operation=operation,
                                      result={"errors": errors, "warnings": warnings, "result_sha256": "0" * 64,
                                              "summary": f"{operation}: {errors} errors, {warnings} warnings"})


def _propose(missions, mission, event):
    view = missions.get_mission("monitor", mission["mission_id"])
    return missions.propose("monitor", mission["mission_id"], event, author=AGENT, expected_event_seq=view["last_event_seq"])


def test_a_new_mission_is_anchored_to_the_latest_revision_and_claims_nothing(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions, accepted=False)
    assert mission["project_id"] == "monitor" and mission["revision"] == 1
    assert mission["phase"] == "INTAKE" == PHASES[0]
    assert mission["terminal"] is None and mission["candidates"] == []
    assert mission["budgets"]["max_candidates"] == 3
    assert mission["last_event_seq"] == 1 and mission["events"][0]["type"] == "opened"
    assert mission["physical_correctness"] == "UNPROVEN"
    assert mission["firmware_authorized"] is False and mission["power_on_authorized"] is False


def test_the_log_is_append_only_files_and_the_state_is_derived_from_it(tmp_path):
    projects, missions = _store(tmp_path)
    mission = _open(missions)
    _candidate(missions, mission)
    _evaluate(missions, mission)
    events_dir = projects.root / "monitor" / "missions" / mission["mission_id"] / "events"
    assert sorted(p.name for p in events_dir.iterdir()) == ["00000001.json", "00000002.json", "00000003.json", "00000004.json"]
    stored = json.loads((projects.root / "monitor" / "missions" / mission["mission_id"] / "mission.json").read_text())
    assert "phase" not in stored and "terminal" not in stored, "state is replayed from events, never stored"
    view = missions.get_mission("monitor", mission["mission_id"])
    assert view["phase"] == "EVALUATING"
    assert missions.get_mission("monitor", mission["mission_id"]) == view


def test_a_mission_never_changes_the_project(tmp_path):
    projects, missions = _store(tmp_path)
    before = projects.load("monitor")
    mission = _open(missions)
    _candidate(missions, mission)
    _evaluate(missions, mission)
    after = projects.load("monitor")
    assert after["revision"] == before["revision"] == 1
    assert after["snapshot"] == before["snapshot"]


def test_at_most_the_budgeted_candidates_with_known_kinds_and_unique_ids(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions)
    for cid, kind in (("A", "clean_sheet"), ("B", "reclaim_heavy"), ("C", "hybrid")):
        _candidate(missions, mission, cid, kind)
    assert missions.get_mission("monitor", mission["mission_id"])["phase"] == "ARCHITECTING"
    with pytest.raises(MissionStateError, match="candidates"):
        _candidate(missions, mission, "D", "hybrid")
    other = _open(missions)
    with pytest.raises(MissionValidationError):
        _candidate(missions, other, "A", "magic")
    _candidate(missions, other, "A")
    with pytest.raises(MissionValidationError, match="already"):
        _candidate(missions, other, "A")


def test_a_proposal_cannot_record_an_evaluation(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions)
    _candidate(missions, mission)
    with pytest.raises(MissionValidationError):
        _propose(missions, mission, {"type": "evaluation_recorded", "candidate_id": "A", "operation": "device_plan",
                                     "result": {"errors": 0, "warnings": 0}})


def test_ready_for_human_build_is_refused_until_hs_evaluations_support_it(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions)
    _candidate(missions, mission)
    ready = {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD", "candidate_id": "A", "reason": "looks done"}
    with pytest.raises(MissionStateError, match="plan"):
        _propose(missions, mission, ready)
    _evaluate(missions, mission, errors=1)
    with pytest.raises(MissionStateError, match="plan"):
        _propose(missions, mission, ready)
    _evaluate(missions, mission, warnings=0, errors=0)
    with pytest.raises(MissionStateError, match="engineering"):
        _propose(missions, mission, ready)
    _evaluate(missions, mission, operation="device_engineering")
    done = _propose(missions, mission, ready)
    assert done["phase"] == "TERMINAL" and done["terminal"]["state"] == "READY_FOR_HUMAN_BUILD"
    assert done["terminal"]["physical_evidence_required"], "ready still lists what only a person can establish"
    assert done["physical_correctness"] == "UNPROVEN" and done["power_on_authorized"] is False


def test_nothing_is_appended_after_a_terminal_state(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions)
    _candidate(missions, mission)
    _evaluate(missions, mission)
    _evaluate(missions, mission, operation="device_engineering")
    _propose(missions, mission, {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD", "candidate_id": "A", "reason": "checks pass"})
    with pytest.raises(MissionStateError, match="terminal"):
        _candidate(missions, mission, "B")
    with pytest.raises(MissionStateError, match="terminal"):
        _evaluate(missions, mission)


def test_a_repair_needs_a_failing_evaluation_resets_readiness_and_has_a_budget(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions, max_repairs_per_candidate=1)
    _candidate(missions, mission)
    repair = {"type": "repair_proposed", "candidate_id": "A", "spec": SPEC, "rationale": "apply the planner's suggestion"}
    with pytest.raises(MissionStateError, match="failing"):
        _propose(missions, mission, repair)
    _evaluate(missions, mission, errors=2)
    view = _propose(missions, mission, repair)
    assert view["phase"] == "REPAIRING"
    assert view["budgets"]["repairs_used"] == {"A": 1}
    _evaluate(missions, mission, errors=1)
    with pytest.raises(MissionStateError, match="repair"):
        _propose(missions, mission, repair)


def test_a_clean_plan_before_a_repair_does_not_count_after_it(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions)
    _candidate(missions, mission)
    _evaluate(missions, mission, operation="device_engineering")
    _evaluate(missions, mission, warnings=1)
    _propose(missions, mission, {"type": "repair_proposed", "candidate_id": "A", "spec": SPEC, "rationale": "fix the warning"})
    with pytest.raises(MissionStateError, match="plan"):
        _propose(missions, mission, {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD", "candidate_id": "A", "reason": "x"})


def test_a_blocked_state_must_cite_the_evidence_need_that_blocks_it(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions)
    _candidate(missions, mission, "B", "reclaim_heavy")
    blocked = {"type": "terminal_proposed", "state": "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT", "reason": "donor rail unknown", "cites": []}
    with pytest.raises(MissionStateError, match="cite"):
        _propose(missions, mission, blocked)
    need = _propose(missions, mission, {"type": "evidence_required", "candidate_id": "B", "blocker": "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT",
                                         "need": "Measure the donor's 3.3 V rail under load"})
    assert need["phase"] == "EVIDENCE_REQUIRED"
    wrong = dict(blocked, state="BLOCKED_UNSAFE", cites=[need["last_event_seq"]])
    with pytest.raises(MissionStateError, match="cite"):
        _propose(missions, mission, wrong)
    done = _propose(missions, mission, dict(blocked, cites=[need["last_event_seq"]]))
    assert done["terminal"]["state"] == "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT"
    assert done["terminal"]["cites"] == [need["last_event_seq"]]


def test_no_feasible_architecture_needs_every_candidate_failing_with_repairs_spent(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions, max_repairs_per_candidate=1)
    _candidate(missions, mission, "A")
    _candidate(missions, mission, "B", "hybrid")
    nope = {"type": "terminal_proposed", "state": "NO_FEASIBLE_ARCHITECTURE", "reason": "nothing passes"}
    _evaluate(missions, mission, "A", errors=1)
    with pytest.raises(MissionStateError):
        _propose(missions, mission, nope)
    for cid in ("A", "B"):
        if cid == "B":
            _evaluate(missions, mission, "B", errors=1)
        _propose(missions, mission, {"type": "repair_proposed", "candidate_id": cid, "spec": SPEC, "rationale": "try"})
        _evaluate(missions, mission, cid, errors=1)
    assert _propose(missions, mission, nope)["terminal"]["state"] == "NO_FEASIBLE_ARCHITECTURE"


def test_budget_exhausted_needs_the_operator_budget_spent_and_the_budget_is_enforced(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions, max_operator_jobs=2)
    _candidate(missions, mission)
    spent = {"type": "terminal_proposed", "state": "BUDGET_EXHAUSTED", "reason": "out of jobs"}
    _evaluate(missions, mission, errors=1)
    with pytest.raises(MissionStateError, match="budget"):
        _propose(missions, mission, spent)
    _evaluate(missions, mission, errors=1)
    with pytest.raises(MissionStateError, match="budget"):
        _evaluate(missions, mission)
    assert _propose(missions, mission, spent)["terminal"]["state"] == "BUDGET_EXHAUSTED"


@pytest.mark.parametrize("key", ["physical_correctness", "firmware_authorized", "power_on_authorized", "authority"])
def test_authority_keys_are_refused_in_intake_and_events(tmp_path, key):
    _projects, missions = _store(tmp_path)
    with pytest.raises(MissionValidationError):
        missions.open_mission("monitor", intake={"goal": "x", key: True}, author=AGENT)
    mission = _open(missions)
    with pytest.raises(MissionValidationError):
        _propose(missions, mission, {"type": "candidate_proposed", key: True,
                                     "candidate": {"id": "A", "kind": "clean_sheet", "label": "A", "spec": SPEC, "rationale": "r"}})


def test_stale_writes_conflict_and_missing_things_are_named(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions)
    with pytest.raises(MissionConflict):
        missions.propose("monitor", mission["mission_id"], {"type": "candidate_proposed", "candidate": {
            "id": "A", "kind": "clean_sheet", "label": "A", "spec": SPEC, "rationale": "r"}}, author=AGENT, expected_event_seq=5)
    with pytest.raises(MissionNotFound):
        missions.get_mission("monitor", "mission-0000000000000000")
    with pytest.raises(ProjectNotFound):
        missions.open_mission("nope", intake={"goal": "x"}, author=AGENT)
    with pytest.raises(MissionValidationError):
        missions.open_mission("monitor", intake={"goal": ""}, author=AGENT)
    assert [m["mission_id"] for m in missions.list_missions("monitor")] == [mission["mission_id"]]


def test_the_terminal_states_are_the_documented_set():
    assert set(TERMINAL_STATES) == {"READY_FOR_HUMAN_BUILD", "BLOCKED_NEEDS_PART_DATA", "BLOCKED_NEEDS_REVERSE_ENGINEERING",
                                    "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT", "BLOCKED_NEEDS_PROCUREMENT_EVIDENCE", "BLOCKED_UNSAFE",
                                    "NO_FEASIBLE_ARCHITECTURE", "BUDGET_EXHAUSTED"}
    assert PHASES == ("INTAKE", "ARCHITECTING", "EVALUATING", "REPAIRING", "EVIDENCE_REQUIRED", "TERMINAL")


def test_no_feasible_architecture_needs_a_verdict_since_each_candidates_latest_repair(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions, max_repairs_per_candidate=1)
    _candidate(missions, mission, "A")
    _evaluate(missions, mission, "A", errors=1)
    _propose(missions, mission, {"type": "repair_proposed", "candidate_id": "A", "spec": SPEC, "rationale": "try"})
    nope = {"type": "terminal_proposed", "state": "NO_FEASIBLE_ARCHITECTURE", "reason": "nothing passes"}
    with pytest.raises(MissionStateError, match="since"):
        _propose(missions, mission, nope)
    _evaluate(missions, mission, "A", errors=1)
    assert _propose(missions, mission, nope)["terminal"]["state"] == "NO_FEASIBLE_ARCHITECTURE"


@pytest.mark.parametrize("named", ["A", None])
def test_ready_is_refused_while_an_evidence_need_stands_for_that_candidate_or_the_mission(tmp_path, named):
    _projects, missions = _store(tmp_path)
    mission = _open(missions)
    _candidate(missions, mission, "A")
    need = {"type": "evidence_required", "blocker": "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT", "need": "Measure the donor rail"}
    if named:
        need["candidate_id"] = named
    _propose(missions, mission, need)
    _evaluate(missions, mission)
    _evaluate(missions, mission, operation="device_engineering")
    with pytest.raises(MissionStateError, match="evidence"):
        _propose(missions, mission, {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD", "candidate_id": "A", "reason": "x"})


def test_a_need_for_another_candidate_does_not_block_this_one(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions)
    _candidate(missions, mission, "A")
    _candidate(missions, mission, "B", "reclaim_heavy")
    _propose(missions, mission, {"type": "evidence_required", "candidate_id": "B", "blocker": "BLOCKED_NEEDS_REVERSE_ENGINEERING", "need": "Identify the donor board"})
    _evaluate(missions, mission, "A")
    _evaluate(missions, mission, "A", operation="device_engineering")
    done = _propose(missions, mission, {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD", "candidate_id": "A", "reason": "A passes"})
    assert done["terminal"]["state"] == "READY_FOR_HUMAN_BUILD"


def test_a_second_repair_needs_a_failing_verdict_on_the_repaired_spec(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions)
    _candidate(missions, mission)
    _evaluate(missions, mission, errors=1)
    repair = {"type": "repair_proposed", "candidate_id": "A", "spec": SPEC, "rationale": "apply the suggestion"}
    _propose(missions, mission, repair)
    with pytest.raises(MissionStateError, match="current spec"):
        _propose(missions, mission, repair)
    _evaluate(missions, mission, errors=1)
    assert _propose(missions, mission, repair)["budgets"]["repairs_used"] == {"A": 2}


def test_a_terminal_proposal_cannot_name_a_candidate_that_does_not_exist(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions)
    _candidate(missions, mission, "A")
    need = _propose(missions, mission, {"type": "evidence_required", "blocker": "BLOCKED_UNSAFE", "need": "Mains-powered donor"})
    with pytest.raises(MissionValidationError, match="does not exist"):
        _propose(missions, mission, {"type": "terminal_proposed", "state": "BLOCKED_UNSAFE", "candidate_id": "Z",
                                     "reason": "unsafe", "cites": [need["last_event_seq"]]})



# Found by the Gemini 4 Argon review of the first mission store, each reproduced before it was fixed.


def test_ready_needs_an_engineering_review_without_errors(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions)
    _candidate(missions, mission)
    _evaluate(missions, mission)
    _evaluate(missions, mission, operation="device_engineering", errors=5)
    with pytest.raises(MissionStateError, match="no errors"):
        _propose(missions, mission, {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD", "candidate_id": "A", "reason": "x"})


def test_a_blocked_state_cannot_borrow_another_candidates_need_or_cite_unrelated_events(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions)
    _candidate(missions, mission, "A")
    _candidate(missions, mission, "B", "reclaim_heavy")
    need = _propose(missions, mission, {"type": "evidence_required", "candidate_id": "B", "blocker": "BLOCKED_NEEDS_PART_DATA", "need": "B datasheet"})
    seq = need["last_event_seq"]
    blocked = {"type": "terminal_proposed", "state": "BLOCKED_NEEDS_PART_DATA", "candidate_id": "A", "reason": "x"}
    with pytest.raises(MissionStateError, match="this candidate"):
        _propose(missions, mission, dict(blocked, cites=[seq]))
    with pytest.raises(MissionStateError, match="only existing"):
        _propose(missions, mission, dict(blocked, candidate_id="B", cites=[seq, 999]))
    with pytest.raises(MissionStateError, match="only existing"):
        _propose(missions, mission, dict(blocked, candidate_id="B", cites=[1, seq]))
    assert _propose(missions, mission, dict(blocked, candidate_id="B", cites=[seq]))["terminal"]["candidate_id"] == "B"


def test_a_mission_cannot_stop_short_of_a_candidate_that_is_already_ready(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions, max_operator_jobs=2)
    _candidate(missions, mission)
    _evaluate(missions, mission)
    _evaluate(missions, mission, operation="device_engineering")
    with pytest.raises(MissionStateError, match="ready for a human build"):
        _propose(missions, mission, {"type": "terminal_proposed", "state": "BUDGET_EXHAUSTED", "reason": "jobs used up"})


def test_an_agent_cannot_write_as_hardware_splicer(tmp_path):
    _projects, missions = _store(tmp_path)
    system = {"kind": "system", "id": "hardware-splicer"}
    with pytest.raises(MissionValidationError, match="system"):
        missions.open_mission("monitor", intake={"goal": "x"}, author=system)
    mission = _open(missions)
    with pytest.raises(MissionValidationError, match="system"):
        missions.propose("monitor", mission["mission_id"], {"type": "candidate_proposed", "candidate": {
            "id": "A", "kind": "clean_sheet", "label": "A", "spec": SPEC, "rationale": "r"}}, author=system)


@pytest.mark.parametrize("container", ["list", "tuple"])
def test_authority_fields_are_refused_inside_lists_too(tmp_path, container):
    _projects, missions = _store(tmp_path)
    mission = _open(missions)
    rows = [{"id": "m1", "power_on_authorized": True}]
    spec = {"modules": rows if container == "list" else tuple(rows)}
    with pytest.raises(MissionValidationError, match="authority"):
        _candidate_with_spec = missions.propose("monitor", mission["mission_id"], {"type": "candidate_proposed", "candidate": {
            "id": "A", "kind": "clean_sheet", "label": "A", "spec": spec, "rationale": "r"}}, author=AGENT)


def test_a_bad_author_id_is_refused_before_anything_is_written(tmp_path):
    projects, missions = _store(tmp_path)
    with pytest.raises(MissionValidationError, match="surrogate"):
        missions.open_mission("monitor", intake={"goal": "x"}, author={"kind": "agent", "id": "planner-\ud800"})
    assert not (projects.root / "monitor" / "missions").exists() or not any((projects.root / "monitor" / "missions").iterdir())


@pytest.mark.parametrize("spec", [{"x": float("nan")}, {"pins": {1: "VCC"}}, {"pins": {1: "VCC", "gnd": "GND"}}, {"rows": (1, 2)}])
def test_a_spec_must_come_back_from_the_log_exactly_as_given(tmp_path, spec):
    _projects, missions = _store(tmp_path)
    mission = _open(missions)
    with pytest.raises(MissionValidationError, match="plain JSON"):
        missions.propose("monitor", mission["mission_id"], {"type": "candidate_proposed", "candidate": {
            "id": "A", "kind": "clean_sheet", "label": "A", "spec": spec, "rationale": "r"}}, author=AGENT)


# Mission-level acceptance (P2): one human acceptance of the mission and its budgets covers HS's software checks.


def test_hs_records_no_evaluation_until_a_person_accepts_the_mission(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions, accepted=False)
    assert mission["accepted"] is None
    _candidate(missions, mission)
    with pytest.raises(MissionStateError, match="accepted"):
        _evaluate(missions, mission)
    accepted = missions.accept_mission("monitor", mission["mission_id"], author=HUMAN)
    assert accepted["accepted"]["by"] == HUMAN and accepted["accepted"]["budgets"] == accepted["budgets"]
    assert accepted["phase"] == "ARCHITECTING", "acceptance changes no phase"
    _evaluate(missions, mission)


@pytest.mark.parametrize("author", [AGENT, {"kind": "system", "id": "hardware-splicer"}])
def test_only_a_person_can_accept_a_mission(tmp_path, author):
    _projects, missions = _store(tmp_path)
    mission = _open(missions, accepted=False)
    with pytest.raises(MissionValidationError, match="person"):
        missions.accept_mission("monitor", mission["mission_id"], author=author)


def test_a_mission_is_accepted_once_and_never_after_it_ends(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions)
    with pytest.raises(MissionStateError, match="already accepted"):
        missions.accept_mission("monitor", mission["mission_id"], author=HUMAN)
    other = _open(missions, accepted=False)
    _candidate(missions, other)
    need = _propose(missions, other, {"type": "evidence_required", "blocker": "BLOCKED_UNSAFE", "need": "Mains donor"})
    _propose(missions, other, {"type": "terminal_proposed", "state": "BLOCKED_UNSAFE", "reason": "mains", "cites": [need["last_event_seq"]]})
    with pytest.raises(MissionStateError, match="terminal"):
        missions.accept_mission("monitor", other["mission_id"], author=HUMAN)


def test_an_agent_cannot_propose_an_acceptance(tmp_path):
    _projects, missions = _store(tmp_path)
    mission = _open(missions, accepted=False)
    with pytest.raises(MissionValidationError):
        _propose(missions, mission, {"type": "accepted"})

