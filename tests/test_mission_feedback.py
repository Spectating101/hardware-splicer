"""A mission can ask a person for a physical fact, wait, and resume when the person answers.

The agent asks with a structured request on an evidence need and leaves the mission open. Only a person, with an
operator token, answers, and only with a physical-evidence envelope bound to this project, mission and need, whose
hash HS recomputes. An envelope is used once. A reading outside the expected range keeps the need open. A resolved
need stops blocking READY only after HS checks the design again. Nothing here authorizes anything physical.
"""
from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.device_plan import example_specs
from hardware_splicer.mission_store import MissionStateError, MissionStore, MissionValidationError
from hardware_splicer.operator_identity import hash_operator_token
from hardware_splicer.physical_evidence_ledger import build_physical_evidence_envelope
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore

AGENT = {"kind": "agent", "id": "planner-model"}
HUMAN = {"kind": "human", "id": "bench-lead"}
ESP32 = "esp32-devkitc-v4"


def _snapshot():
    return {"projectId": "monitor", "projectName": "Field monitor", "currentStage": "design", "mode": "greenfield",
            "graph": {"nodes": [], "edges": []},
            "machineProject": {"project_id": "monitor", "name": "Field monitor", "purpose": "monitor"}}


def _store(tmp_path):
    projects = ProjectStore(tmp_path)
    projects.save("monitor", _snapshot(), expected_revision=0)
    return MissionStore(projects)


def _mission(missions, intake_extra=None):
    mission = missions.open_mission("monitor", intake={"goal": "g", "inventory": ["ESP32", "BME280", "OLED"],
                                                       **(intake_extra or {})}, author=AGENT)
    return missions.accept_mission("monitor", mission["mission_id"], author=HUMAN)


def _propose(missions, mid, event):
    seq = missions.get_mission("monitor", mid)["last_event_seq"]
    return missions.propose("monitor", mid, event, author=AGENT, expected_event_seq=seq)


def _evaluate(missions, mid, cid="A", operation="device_plan", errors=0, warnings=0):
    return missions.record_evaluation("monitor", mid, candidate_id=cid, operation=operation,
                                      result={"errors": errors, "warnings": warnings, "result_sha256": "0" * 64,
                                              "summary": f"{operation}: {errors} errors"})


def _candidate(missions, mid, spec=None, cid="A"):
    return _propose(missions, mid, {"type": "candidate_proposed", "candidate": {
        "id": cid, "kind": "clean_sheet", "label": cid, "spec": spec or example_specs()["esp32_oled_bme280_usb"],
        "rationale": "r"}})


VOLTAGE_REQUEST = {"kind": "electrical", "target": "the 3.3 V rail at the sensor", "quantity": "voltage",
                   "expected": {"min": 3.2, "max": 3.4, "unit": "V"},
                   "instructions": "Measure 3V3 to GND at the sensor header with the board on USB."}
WIDTH_REQUEST = {"kind": "dimensional", "target": ESP32, "quantity": "pcb_mm.x",
                 "instructions": "Measure the board's length along the USB axis."}


def _need(missions, mid, request, cid=None, blocker="BLOCKED_NEEDS_PHYSICAL_MEASUREMENT"):
    event = {"type": "evidence_required", "blocker": blocker, "need": request["instructions"], "request": request}
    if cid:
        event["candidate_id"] = cid
    return _propose(missions, mid, event)["last_event_seq"]


def _envelope(mid, need_seq, values, *, project_id="monitor", kind="electrical_measurement", envelope_id="env-1",
              mission_id=None, bound_values=None):
    record = {"evidence_id": f"ev-{envelope_id}", "project_id": project_id, "candidate_revision": "mission",
              "kind": kind, "target_ids": ["mcu"], "procedure_id": "mission-need", "passed": True,
              "captured_at": "2026-10-16T12:00:00Z", "operator": "bench-lead"}
    metadata = {"mission": {"project_id": project_id, "mission_id": mission_id or mid, "need_seq": need_seq,
                            "values": values if bound_values is None else bound_values}}
    return build_physical_evidence_envelope(
        envelope_id=envelope_id, record=record,
        raw_files=[{"ref": "reading.txt", "content_hash": "sha256:" + "a" * 64}],
        created_at="2026-10-16T12:00:00Z", created_by="bench-lead", metadata=metadata,
    ).model_dump(mode="json")


def _supply(missions, mid, need_seq, values, **envelope_kwargs):
    seq = missions.get_mission("monitor", mid)["last_event_seq"]
    return missions.supply_evidence("monitor", mid, need_seq, envelope=_envelope(mid, need_seq, values, **envelope_kwargs),
                                    values=values, author=HUMAN, expected_event_seq=seq)


def test_a_request_is_validated_when_the_agent_asks(tmp_path):
    missions = _store(tmp_path)
    mid = _mission(missions)["mission_id"]
    for bad in ({**WIDTH_REQUEST, "target": "not-a-module"}, {**WIDTH_REQUEST, "quantity": "colour"},
                {**VOLTAGE_REQUEST, "kind": "smell"}, {**VOLTAGE_REQUEST, "expected": {"min": 3.4, "max": 3.2, "unit": "V"}}):
        with pytest.raises(MissionValidationError):
            _need(missions, mid, bad)


def test_a_reading_within_range_resolves_the_need_and_the_mission_resumes(tmp_path):
    missions = _store(tmp_path)
    mid = _mission(missions)["mission_id"]
    _candidate(missions, mid)
    need = _need(missions, mid, VOLTAGE_REQUEST)
    assert missions.get_mission("monitor", mid)["phase"] == "EVIDENCE_REQUIRED"
    view = _supply(missions, mid, need, [{"quantity": "voltage", "value": 3.29, "unit": "V"}])
    supplied = view["events"][-1]
    assert supplied["type"] == "evidence_supplied" and supplied["author"] == HUMAN
    assert supplied["comparison"] == "within" and supplied["envelope_hash"].startswith("sha256:")
    assert [n["need_state"] for n in view["needs"]] == ["resolved"]
    assert view["phase"] == "EVALUATING" and view["physical_correctness"] == "UNPROVEN"
    assert view["power_on_authorized"] is False and view["firmware_authorized"] is False


def test_a_resolved_need_unblocks_ready_only_after_hs_checks_again(tmp_path):
    missions = _store(tmp_path)
    mid = _mission(missions)["mission_id"]
    _candidate(missions, mid)
    _evaluate(missions, mid)
    _evaluate(missions, mid, operation="device_engineering")
    need = _need(missions, mid, VOLTAGE_REQUEST)
    ready = {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD", "candidate_id": "A", "reason": "checked"}
    with pytest.raises(MissionStateError, match="evidence need"):
        _propose(missions, mid, ready)
    _supply(missions, mid, need, [{"quantity": "voltage", "value": 3.3, "unit": "V"}])
    with pytest.raises(MissionStateError, match="after"):
        _propose(missions, mid, ready)  # the earlier checks predate the new fact
    _evaluate(missions, mid)
    _evaluate(missions, mid, operation="device_engineering")
    assert _propose(missions, mid, ready)["terminal"]["state"] == "READY_FOR_HUMAN_BUILD"


def test_a_reading_outside_the_range_keeps_the_need_open(tmp_path):
    missions = _store(tmp_path)
    mid = _mission(missions)["mission_id"]
    _candidate(missions, mid)
    need = _need(missions, mid, VOLTAGE_REQUEST)
    view = _supply(missions, mid, need, [{"quantity": "voltage", "value": 4.9, "unit": "V"}])
    assert view["events"][-1]["comparison"] == "outside"
    assert [n["need_state"] for n in view["needs"]] == ["contradicted"]
    assert view["phase"] == "EVIDENCE_REQUIRED"
    _evaluate(missions, mid)
    _evaluate(missions, mid, operation="device_engineering")
    with pytest.raises(MissionStateError, match="evidence need"):
        _propose(missions, mid, {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD", "candidate_id": "A", "reason": "r"})


@pytest.mark.parametrize("case", ["wrong_mission", "wrong_need", "wrong_project", "values_differ", "tampered", "wrong_kind",
                                  "wrong_quantity"])
def test_evidence_must_be_bound_to_this_need_and_untampered(tmp_path, case):
    missions = _store(tmp_path)
    mid = _mission(missions)["mission_id"]
    _candidate(missions, mid)
    need = _need(missions, mid, VOLTAGE_REQUEST)
    values = [{"quantity": "voltage", "value": 3.3, "unit": "V"}]
    kwargs = {"wrong_mission": {"mission_id": "mission-0000000000000000"}, "wrong_need": {},
              "wrong_project": {"project_id": "other"}, "values_differ": {"bound_values": [{"quantity": "voltage", "value": 3.0, "unit": "V"}]},
              "tampered": {}, "wrong_kind": {"kind": "dimensional_measurement"}, "wrong_quantity": {}}[case]
    envelope = _envelope(mid, need + (1 if case == "wrong_need" else 0), values, **kwargs)
    if case == "tampered":
        envelope["record"]["passed"] = False
    if case == "wrong_quantity":
        values = [{"quantity": "current", "value": 3.3, "unit": "A"}]
        envelope = _envelope(mid, need, values)
    seq = missions.get_mission("monitor", mid)["last_event_seq"]
    with pytest.raises(MissionValidationError):
        missions.supply_evidence("monitor", mid, need, envelope=envelope, values=values, author=HUMAN, expected_event_seq=seq)
    assert missions.get_mission("monitor", mid)["last_event_seq"] == seq


def test_an_envelope_is_used_once_in_a_project(tmp_path):
    missions = _store(tmp_path)
    first = _mission(missions)["mission_id"]
    _candidate(missions, first)
    need = _need(missions, first, VOLTAGE_REQUEST)
    values = [{"quantity": "voltage", "value": 3.3, "unit": "V"}]
    envelope = _envelope(first, need, values)
    seq = missions.get_mission("monitor", first)["last_event_seq"]
    missions.supply_evidence("monitor", first, need, envelope=envelope, values=values, author=HUMAN, expected_event_seq=seq)
    second_need = _need(missions, first, {**VOLTAGE_REQUEST, "instructions": "again"})
    seq = missions.get_mission("monitor", first)["last_event_seq"]
    with pytest.raises(MissionValidationError, match="already used"):
        missions.supply_evidence("monitor", first, second_need, envelope=envelope, values=values, author=HUMAN, expected_event_seq=seq)


def test_only_a_person_supplies_evidence_and_never_through_proposals(tmp_path):
    missions = _store(tmp_path)
    mid = _mission(missions)["mission_id"]
    _candidate(missions, mid)
    need = _need(missions, mid, VOLTAGE_REQUEST)
    values = [{"quantity": "voltage", "value": 3.3, "unit": "V"}]
    seq = missions.get_mission("monitor", mid)["last_event_seq"]
    with pytest.raises(MissionValidationError):
        missions.supply_evidence("monitor", mid, need, envelope=_envelope(mid, need, values), values=values,
                                 author=AGENT, expected_event_seq=seq)
    with pytest.raises(MissionValidationError):
        _propose(missions, mid, {"type": "evidence_supplied", "need_seq": need, "values": values})


def test_a_need_without_a_request_or_a_terminal_mission_takes_no_evidence(tmp_path):
    missions = _store(tmp_path)
    mid = _mission(missions)["mission_id"]
    plain = _propose(missions, mid, {"type": "evidence_required", "blocker": "BLOCKED_UNSAFE", "need": "x"})["last_event_seq"]
    values = [{"quantity": "voltage", "value": 3.3, "unit": "V"}]
    seq = missions.get_mission("monitor", mid)["last_event_seq"]
    with pytest.raises(MissionStateError, match="request"):
        missions.supply_evidence("monitor", mid, plain, envelope=_envelope(mid, plain, values), values=values,
                                 author=HUMAN, expected_event_seq=seq)
    need = _need(missions, mid, VOLTAGE_REQUEST)
    _propose(missions, mid, {"type": "terminal_proposed", "state": "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT",
                             "reason": "waiting", "cites": [need]})
    seq = missions.get_mission("monitor", mid)["last_event_seq"]
    with pytest.raises(MissionStateError, match="terminal"):
        missions.supply_evidence("monitor", mid, need, envelope=_envelope(mid, need, values, envelope_id="env-2"),
                                 values=values, author=HUMAN, expected_event_seq=seq)


def test_a_resolved_need_cannot_ground_a_blocker(tmp_path):
    missions = _store(tmp_path)
    mid = _mission(missions)["mission_id"]
    need = _need(missions, mid, VOLTAGE_REQUEST)
    _supply(missions, mid, need, [{"quantity": "voltage", "value": 3.3, "unit": "V"}])
    with pytest.raises(MissionStateError, match="resolved"):
        _propose(missions, mid, {"type": "terminal_proposed", "state": "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT",
                                 "reason": "still waiting", "cites": [need]})


def test_a_measured_size_becomes_an_override_for_its_module_only(tmp_path):
    missions = _store(tmp_path)
    mid = _mission(missions)["mission_id"]
    need = _need(missions, mid, WIDTH_REQUEST)
    _supply(missions, mid, need, [{"quantity": "pcb_mm.x", "value": 28.1, "unit": "mm"}], kind="dimensional_measurement")
    spec = copy.deepcopy(example_specs()["esp32_oled_bme280_usb"])
    spec["modules"][0]["overrides"] = {"pcb_mm": {"x": 28.1}}
    assert _candidate(missions, mid, spec)["candidates"][0]["spec"]["modules"][0]["overrides"] == {"pcb_mm": {"x": 28.1}}
    other = copy.deepcopy(spec)
    other["modules"][0]["overrides"] = {"pcb_mm": {"x": 30}}
    with pytest.raises(MissionValidationError, match="physical evidence"):
        _candidate(missions, mid, other, cid="B")
    sensor = copy.deepcopy(example_specs()["esp32_oled_bme280_usb"])
    sensor["modules"][2]["overrides"] = {"pcb_mm": {"x": 28.1}}
    with pytest.raises(MissionValidationError, match="physical evidence"):
        _candidate(missions, mid, sensor, cid="C")


def test_a_measured_size_cannot_contradict_the_intake(tmp_path):
    missions = _store(tmp_path)
    mid = _mission(missions, {"measurements": {ESP32: {"pcb_mm": {"x": 27.0}}}})["mission_id"]
    need = _need(missions, mid, WIDTH_REQUEST)
    with pytest.raises(MissionValidationError, match="intake"):
        _supply(missions, mid, need, [{"quantity": "pcb_mm.x", "value": 28.1, "unit": "mm"}], kind="dimensional_measurement")


def test_a_boot_log_is_kept_as_text_and_not_interpreted(tmp_path):
    missions = _store(tmp_path)
    mid = _mission(missions)["mission_id"]
    need = _need(missions, mid, {"kind": "boot_log", "target": "mcu", "instructions": "Flash and copy the serial log."})
    log = {"log": "[BOOT] sensor init failed at 0x76\n"}
    view = _supply(missions, mid, need, log, kind="inspection")
    assert view["events"][-1]["values"] == log and view["events"][-1]["comparison"] == "not_comparable"
    assert [n["need_state"] for n in view["needs"]] == ["resolved"]


def test_after_new_evidence_the_agent_may_repair(tmp_path):
    missions = _store(tmp_path)
    mid = _mission(missions)["mission_id"]
    _candidate(missions, mid)
    _evaluate(missions, mid)
    need = _need(missions, mid, {"kind": "boot_log", "target": "mcu", "instructions": "Flash and copy the serial log."})
    _supply(missions, mid, need, {"log": "sensor init failed"}, kind="inspection")
    repaired = _propose(missions, mid, {"type": "repair_proposed", "candidate_id": "A",
                                         "spec": example_specs()["esp32_oled_bme280_usb"], "rationale": "per the boot log"})
    assert repaired["candidates"][0]["repairs"] == 1


PERSON_TOKEN = "person-token-" + "a" * 48
AGENT_TOKEN = "agent-token-" + "b" * 48
BASE = "/v1/projects/monitor/missions"


def test_the_evidence_route_needs_a_persons_token(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OPERATOR_TOKENS", (
        '{"%s": {"id": "bench-lead", "kind": "human"}, "%s": {"id": "some-agent", "kind": "agent"}}'
        % (hash_operator_token(PERSON_TOKEN), hash_operator_token(AGENT_TOKEN))))
    store = ProjectStore(tmp_path)
    store.save("monitor", _snapshot(), expected_revision=0)
    client = TestClient(create_product_app(store))
    mid = client.post(BASE, json={"intake": {"goal": "g", "inventory": ["ESP32"]}, "author": AGENT}).json()["mission"]["mission_id"]
    client.post(f"{BASE}/{mid}/accept", headers={"X-HS-Operator-Token": PERSON_TOKEN})
    seq = client.get(f"{BASE}/{mid}").json()["mission"]["last_event_seq"]
    need = client.post(f"{BASE}/{mid}/events", json={"event": {"type": "evidence_required", "blocker": "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT",
                                                                "need": "v", "request": VOLTAGE_REQUEST},
                                                      "author": AGENT, "expected_event_seq": seq}).json()["mission"]["last_event_seq"]
    values = [{"quantity": "voltage", "value": 3.3, "unit": "V"}]
    body = {"envelope": _envelope(mid, need, values), "values": values, "expected_event_seq": need}
    route = f"{BASE}/{mid}/needs/{need}/evidence"
    assert client.post(route, json=body).status_code == 403
    assert client.post(route, json=body, headers={"X-HS-Operator-Token": AGENT_TOKEN}).status_code == 403
    assert client.post(route, json=body, headers={"X-HS-Operator-Token": "unknown-" + "c" * 48}).status_code == 401
    done = client.post(route, json=body, headers={"X-HS-Operator-Token": PERSON_TOKEN})
    assert done.status_code == 201, done.text
    assert done.json()["mission"]["events"][-1]["author"] == {"kind": "human", "id": "bench-lead"}
    from hardware_splicer.mcp_backend_gateway import task_operation_manifest
    offered = {path for _m, path in ((op["method"], op["path"]) for op in task_operation_manifest("fabrication_mission", create_product_app())["operations"])}
    assert not any(path.endswith("/evidence") for path in offered)
