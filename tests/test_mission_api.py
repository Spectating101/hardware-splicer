"""Fabrication missions over HTTP: what an agent can do, and the one thing only a person can.

An agent may open a mission, read it, propose events, ask HS to run its software-only checks and read the run
files. Accepting a mission needs a person's operator token, so an agent cannot accept its own mission. No route
records an evaluation directly. The MCP task manifest offers the agent routes and never the acceptance.
"""
from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.device_plan import example_specs
from hardware_splicer.mcp_backend_gateway import task_operation_manifest
from hardware_splicer.operator_identity import hash_operator_token
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore

AGENT = {"kind": "agent", "id": "grok-agent"}
PERSON_TOKEN = "person-token-" + "a" * 48
AGENT_TOKEN = "agent-token-" + "b" * 48
BASE = "/v1/projects/monitor/missions"


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


def _open(client, **budgets):
    intake = {"goal": "A small sensor device from my parts", "inventory": ["ESP32", "BME280", "OLED"]}
    if budgets:
        intake["budgets"] = budgets
    response = client.post(BASE, json={"intake": intake, "author": AGENT})
    assert response.status_code == 201, response.text
    return response.json()["mission"]


def _accept(client, mid, token=PERSON_TOKEN):
    return client.post(f"{BASE}/{mid}/accept", headers={"X-HS-Operator-Token": token} if token else {})


def _propose(client, mid, event):
    seq = client.get(f"{BASE}/{mid}").json()["mission"]["last_event_seq"]
    return client.post(f"{BASE}/{mid}/events", json={"event": event, "author": AGENT, "expected_event_seq": seq})


def _candidate(client, mid, spec=None):
    return _propose(client, mid, {"type": "candidate_proposed", "candidate": {
        "id": "A", "kind": "clean_sheet", "label": "ESP32 + BME280 + OLED",
        "spec": spec or example_specs()["esp32_oled_bme280_usb"], "rationale": "the inventory as drafted"}})


def test_an_agent_opens_lists_and_reads_a_mission(client):
    mission = _open(client)
    assert mission["phase"] == "INTAKE" and mission["accepted"] is None
    assert [m["mission_id"] for m in client.get(BASE).json()["missions"]] == [mission["mission_id"]]
    read = client.get(f"{BASE}/{mission['mission_id']}").json()["mission"]
    assert read["mission_id"] == mission["mission_id"] and read["physical_correctness"] == "UNPROVEN"


def test_only_a_persons_operator_token_accepts_a_mission(client):
    mid = _open(client)["mission_id"]
    assert _accept(client, mid, token=None).status_code == 403
    assert _accept(client, mid, token=AGENT_TOKEN).status_code == 403
    assert _accept(client, mid, token="unknown-token-" + "c" * 48).status_code == 401
    accepted = _accept(client, mid)
    assert accepted.status_code == 200
    assert accepted.json()["mission"]["accepted"]["by"] == {"kind": "human", "id": "bench-lead"}
    assert _accept(client, mid).status_code == 409


def test_an_agent_cannot_open_or_propose_as_hardware_splicer(client):
    system = {"kind": "system", "id": "hardware-splicer"}
    assert client.post(BASE, json={"intake": {"goal": "x"}, "author": system}).status_code == 422
    mid = _open(client)["mission_id"]
    response = client.post(f"{BASE}/{mid}/events", json={"event": {"type": "candidate_proposed", "candidate": {
        "id": "A", "kind": "clean_sheet", "label": "A", "spec": {"modules": []}, "rationale": "r"}}, "author": system})
    assert response.status_code == 422


def test_a_proposal_cannot_record_an_evaluation_and_no_route_does(client):
    mid = _open(client)["mission_id"]
    _accept(client, mid)
    _candidate(client, mid)
    forged = _propose(client, mid, {"type": "evaluation_recorded", "candidate_id": "A", "operation": "device_plan",
                                    "result": {"errors": 0, "warnings": 0, "result_sha256": "0" * 64, "summary": "fine"}})
    assert forged.status_code == 422
    paths = {route.path for route in client.app.routes}
    assert not any("evaluation" in path for path in paths if "/missions" in path)


def test_hs_runs_checks_for_an_accepted_mission_and_serves_its_run_files(client):
    mid = _open(client)["mission_id"]
    _candidate(client, mid)
    assert client.post(f"{BASE}/{mid}/candidates/A/run", json={"operation": "device_plan"}).status_code == 409
    _accept(client, mid)
    ran = client.post(f"{BASE}/{mid}/candidates/A/run", json={"operation": "device_plan"})
    assert ran.status_code == 200, ran.text
    evaluation = ran.json()["evaluation"]
    assert evaluation["operation"] == "device_plan" and evaluation["result"]["errors"] == 0
    name = evaluation["artifact"].split("/", 1)[1]
    run = client.get(f"{BASE}/{mid}/runs/{name}")
    assert run.status_code == 200 and "findings" in run.json()["run"]
    assert client.get(f"{BASE}/{mid}/runs/not-a-run.json").status_code == 404
    assert client.post(f"{BASE}/{mid}/candidates/A/run", json={"operation": "shell"}).status_code == 422


def test_an_agent_reaches_ready_only_through_hs_checks(client):
    mid = _open(client)["mission_id"]
    _accept(client, mid)
    _candidate(client, mid)
    ready = {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD", "candidate_id": "A", "reason": "looks right"}
    assert _propose(client, mid, ready).status_code == 409
    client.post(f"{BASE}/{mid}/candidates/A/run", json={"operation": "device_plan"})
    client.post(f"{BASE}/{mid}/candidates/A/run", json={"operation": "device_engineering"})
    done = _propose(client, mid, ready)
    assert done.status_code == 201
    assert done.json()["mission"]["terminal"]["state"] == "READY_FOR_HUMAN_BUILD"


def test_errors_map_to_stable_status_codes(client):
    assert client.get(f"{BASE}/mission-0000000000000000").status_code == 404
    assert client.get("/v1/projects/nope/missions").status_code == 404
    mid = _open(client, max_operator_jobs=1)["mission_id"]
    _accept(client, mid)
    _candidate(client, mid)
    stale = client.post(f"{BASE}/{mid}/events", json={"event": {"type": "evidence_required", "blocker": "BLOCKED_UNSAFE", "need": "x"},
                                                       "author": AGENT, "expected_event_seq": 1})
    assert stale.status_code == 409
    client.post(f"{BASE}/{mid}/candidates/A/run", json={"operation": "device_plan"})
    spent = client.post(f"{BASE}/{mid}/candidates/A/run", json={"operation": "device_engineering"})
    assert spent.status_code == 409 and "budget" in spent.text


def test_the_mission_task_manifest_offers_the_agent_routes_and_never_acceptance(client):
    manifest = task_operation_manifest("fabrication_mission", create_product_app())
    offered = {(op["method"], op["path"]) for op in manifest["operations"]}
    assert ("POST", "/v1/projects/{project_id}/missions") in offered
    assert ("POST", "/v1/projects/{project_id}/missions/{mission_id}/events") in offered
    assert ("POST", "/v1/projects/{project_id}/missions/{mission_id}/candidates/{candidate_id}/run") in offered
    assert ("POST", "/v1/devices/draft") in offered
    assert not any(path.endswith("/accept") for _method, path in offered)
    assert manifest["authority_contract"]["projection_grants_physical_authority"] is False
