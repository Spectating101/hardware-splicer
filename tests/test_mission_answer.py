"""A person answers a measurement request by typing the reading; HS builds the evidence envelope itself.

The browser never reproduces a hash. The route is a thin layer over `supply_evidence`, so everything that route
enforces (the envelope's hash and binding, single use, the requested range, terminal missions) holds here too, and
the same person-only rule applies: the decider is the verified operator token, never a name in the request.
"""
from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.device_plan import example_specs
from hardware_splicer.operator_identity import hash_operator_token
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore

AGENT = {"kind": "agent", "id": "planner-model"}
PERSON_TOKEN = "person-token-" + "a" * 48
AGENT_TOKEN = "agent-token-" + "b" * 48
BASE = "/v1/projects/monitor/missions"
ESP32 = "esp32-devkitc-v4"

VOLTAGE = {"kind": "electrical", "target": "the 3.3 V rail at the sensor", "quantity": "voltage",
           "expected": {"min": 3.2, "max": 3.4, "unit": "V"}, "instructions": "Measure 3V3 to GND at the sensor header."}
WIDTH = {"kind": "dimensional", "target": ESP32, "quantity": "pcb_mm.x", "instructions": "Measure the board's length."}
BOOT = {"kind": "boot_log", "target": "mcu", "instructions": "Flash it and copy the serial log."}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OPERATOR_TOKENS", (
        '{"%s": {"id": "bench-lead", "kind": "human"}, "%s": {"id": "some-agent", "kind": "agent"}}'
        % (hash_operator_token(PERSON_TOKEN), hash_operator_token(AGENT_TOKEN))))
    store = ProjectStore(tmp_path)
    store.save("monitor", {"projectId": "monitor", "projectName": "Field monitor", "currentStage": "design", "mode": "greenfield",
                           "graph": {"nodes": [], "edges": []},
                           "machineProject": {"project_id": "monitor", "name": "Field monitor", "purpose": "monitor"}},
               expected_revision=0)
    return TestClient(create_product_app(store))


def _seq(client, mid):
    return client.get(f"{BASE}/{mid}").json()["mission"]["last_event_seq"]


def _mission_with_need(client, request):
    mid = client.post(BASE, json={"intake": {"goal": "g", "inventory": ["ESP32", "BME280", "OLED"]}, "author": AGENT}).json()["mission"]["mission_id"]
    client.post(f"{BASE}/{mid}/accept", headers={"X-HS-Operator-Token": PERSON_TOKEN})
    client.post(f"{BASE}/{mid}/events", json={"event": {"type": "candidate_proposed", "candidate": {
        "id": "A", "kind": "clean_sheet", "label": "A", "spec": example_specs()["esp32_oled_bme280_usb"], "rationale": "r"}},
        "author": AGENT, "expected_event_seq": _seq(client, mid)})
    need = client.post(f"{BASE}/{mid}/events", json={"event": {"type": "evidence_required", "blocker": "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT",
                                                               "need": request["instructions"], "request": request},
                                                     "author": AGENT, "expected_event_seq": _seq(client, mid)}).json()["mission"]["last_event_seq"]
    return mid, need


def _answer(client, mid, need, values, token=PERSON_TOKEN, **extra):
    headers = {"X-HS-Operator-Token": token} if token else {}
    return client.post(f"{BASE}/{mid}/needs/{need}/answer", json={"values": values, **extra}, headers=headers)


def test_a_reading_within_range_resolves_the_need_with_an_envelope_hs_built(client):
    mid, need = _mission_with_need(client, VOLTAGE)
    done = _answer(client, mid, need, [{"quantity": "voltage", "value": 3.29, "unit": "V"}], expected_event_seq=need)
    assert done.status_code == 201, done.text
    mission = done.json()["mission"]
    event = mission["events"][-1]
    assert event["type"] == "evidence_supplied" and event["author"] == {"kind": "human", "id": "bench-lead"}
    assert event["comparison"] == "within" and event["envelope_hash"].startswith("sha256:") and event["evidence_id"]
    assert [n["need_state"] for n in mission["needs"]] == ["resolved"]
    assert mission["physical_correctness"] == "UNPROVEN" and mission["power_on_authorized"] is False


def test_a_reading_outside_the_range_keeps_the_need_open_as_contradicted_and_can_be_answered_again(client):
    mid, need = _mission_with_need(client, VOLTAGE)
    first = _answer(client, mid, need, [{"quantity": "voltage", "value": 4.9, "unit": "V"}])
    assert first.status_code == 201
    assert first.json()["mission"]["events"][-1]["comparison"] == "outside"
    assert [n["need_state"] for n in first.json()["mission"]["needs"]] == ["contradicted"]
    # The same fact measured again is a new answer with a new envelope, not a replay of the first.
    second = _answer(client, mid, need, [{"quantity": "voltage", "value": 3.31, "unit": "V"}])
    assert second.status_code == 201, second.text
    events = [e for e in second.json()["mission"]["events"] if e["type"] == "evidence_supplied"]
    assert len({e["envelope_hash"] for e in events}) == 2
    assert [n["need_state"] for n in second.json()["mission"]["needs"]] == ["resolved"]


def test_a_measured_size_becomes_a_usable_override_and_a_boot_log_is_kept_as_text(client):
    mid, need = _mission_with_need(client, WIDTH)
    assert _answer(client, mid, need, [{"quantity": "pcb_mm.x", "value": 28.1, "unit": "mm"}]).status_code == 201
    spec = copy.deepcopy(example_specs()["esp32_oled_bme280_usb"])
    spec["modules"][0]["overrides"] = {"pcb_mm": {"x": 28.1}}
    proposed = client.post(f"{BASE}/{mid}/events", json={"event": {"type": "candidate_proposed", "candidate": {
        "id": "B", "kind": "clean_sheet", "label": "B", "spec": spec, "rationale": "measured"}},
        "author": AGENT, "expected_event_seq": _seq(client, mid)})
    assert proposed.status_code == 201, proposed.text
    mid2, need2 = _mission_with_need(client, BOOT)
    done = _answer(client, mid2, need2, {"log": "[BOOT] sensor init failed at 0x76\n"})
    assert done.status_code == 201, done.text
    assert done.json()["mission"]["events"][-1]["values"] == {"log": "[BOOT] sensor init failed at 0x76\n"}
    assert done.json()["mission"]["events"][-1]["comparison"] == "not_comparable"


def test_only_a_verified_person_answers_and_the_body_cannot_name_who(client):
    mid, need = _mission_with_need(client, VOLTAGE)
    reading = [{"quantity": "voltage", "value": 3.3, "unit": "V"}]
    seq = _seq(client, mid)
    assert _answer(client, mid, need, reading, token=None).status_code == 403
    assert _answer(client, mid, need, reading, token=AGENT_TOKEN).status_code == 403
    assert _answer(client, mid, need, reading, token="unknown-" + "c" * 48).status_code == 401
    assert _seq(client, mid) == seq
    done = _answer(client, mid, need, reading, author={"kind": "human", "id": "someone-else"}, created_by="someone-else")
    assert done.status_code == 201
    assert done.json()["mission"]["events"][-1]["author"] == {"kind": "human", "id": "bench-lead"}


@pytest.mark.parametrize("values", [
    [{"quantity": "current", "value": 3.3, "unit": "A"}],       # not what was asked
    [{"quantity": "voltage", "value": "3.3", "unit": "V"}],     # a number is a number
    [{"quantity": "voltage", "value": 3.3}],                     # a unit is required
    [],
    "3.3 V",
])
def test_a_reading_that_is_not_what_was_asked_is_refused_and_records_nothing(client, values):
    mid, need = _mission_with_need(client, VOLTAGE)
    seq = _seq(client, mid)
    assert _answer(client, mid, need, values).status_code == 422
    assert _seq(client, mid) == seq


def test_a_resolved_need_a_stale_sequence_and_a_finished_mission_are_refused(client):
    mid, need = _mission_with_need(client, VOLTAGE)
    reading = [{"quantity": "voltage", "value": 3.3, "unit": "V"}]
    assert _answer(client, mid, need, reading, expected_event_seq=1).status_code == 409
    assert _answer(client, mid, need, reading).status_code == 201
    assert _answer(client, mid, need, reading).status_code == 409           # already resolved
    assert _answer(client, mid, 999, reading).status_code == 422             # not a need of this mission
    other, other_need = _mission_with_need(client, VOLTAGE)
    client.post(f"{BASE}/{other}/events", json={"event": {"type": "terminal_proposed", "state": "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT",
                                                          "reason": "waiting", "cites": [other_need]},
                                                "author": AGENT, "expected_event_seq": _seq(client, other)})
    assert _answer(client, other, other_need, reading).status_code == 409    # the mission has ended


def test_the_answer_route_is_not_offered_to_agents(client):
    from hardware_splicer.mcp_backend_gateway import task_operation_manifest

    offered = {path for op in task_operation_manifest("fabrication_mission", create_product_app())["operations"] for path in [op["path"]]}
    assert not any(path.endswith("/answer") or path.endswith("/evidence") for path in offered)


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_a_non_finite_number_sent_as_raw_json_is_refused(client, literal):
    mid, need = _mission_with_need(client, VOLTAGE)
    seq = _seq(client, mid)
    body = '{"values": [{"quantity": "voltage", "value": %s, "unit": "V"}]}' % literal
    response = client.post(f"{BASE}/{mid}/needs/{need}/answer", content=body,
                           headers={"X-HS-Operator-Token": PERSON_TOKEN, "content-type": "application/json"})
    assert response.status_code == 422
    assert _seq(client, mid) == seq
