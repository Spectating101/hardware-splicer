from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.device_plan import example_specs
from hardware_splicer.operator_identity import hash_operator_token
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.salvage_fabrication_manifest import salvage_fabrication_manifest

AGENT = {"kind": "agent", "id": "salvage-agent"}
PERSON_TOKEN = "person-token-" + "s" * 48
PROJECT = "salvage-loop"
BASE = f"/v1/projects/{PROJECT}/missions"
DONOR = "donor:router:button"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "HARDWARE_SPLICER_OPERATOR_TOKENS",
        '{"%s": {"id": "bench-lead", "kind": "human"}}' % hash_operator_token(PERSON_TOKEN),
    )
    store = ProjectStore(tmp_path)
    store.save(
        PROJECT,
        {
            "projectId": PROJECT,
            "projectName": "Salvage loop",
            "currentStage": "design",
            "mode": "salvage",
            "graph": {"nodes": [], "edges": []},
            "machineProject": {"project_id": PROJECT, "name": "Salvage loop", "purpose": "salvage"},
        },
        expected_revision=0,
    )
    return TestClient(create_product_app(store))


def _open(client: TestClient):
    response = client.post(
        BASE,
        json={
            "intake": {
                "goal": "Build a useful monitor from retained junk",
                "inventory": ["ESP32", "BME280", "OLED"],
                "donors": [{"donor_id": DONOR, "label": "Router front-panel button", "optional": True}],
            },
            "author": AGENT,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["mission"]


def _accept(client: TestClient, mission_id: str):
    response = client.post(
        f"{BASE}/{mission_id}/accept",
        headers={"X-HS-Operator-Token": PERSON_TOKEN},
    )
    assert response.status_code == 200, response.text
    return response.json()["mission"]


def _propose(client: TestClient, mission_id: str, event):
    current = client.get(f"{BASE}/{mission_id}").json()["mission"]
    response = client.post(
        f"{BASE}/{mission_id}/events",
        json={"event": event, "author": AGENT, "expected_event_seq": current["last_event_seq"]},
    )
    assert response.status_code == 201, response.text
    return response.json()["mission"]


def _context(client: TestClient, mission_id: str):
    response = client.get(f"{BASE}/{mission_id}/salvage-fabrication")
    assert response.status_code == 200, response.text
    return response.json()["context"]


def test_context_resumes_from_canonical_mission_state_across_turns(client):
    mission = _open(client)
    before = _context(client, mission["mission_id"])
    assert before["accepted"] is False
    assert before["donor_snapshot"] == "current_project_projection_pre_acceptance"
    assert before["donor_snapshot_frozen"] is False
    assert before["next_state"]["state"] == "awaiting_human_acceptance"
    assert before["truth_contract"]["persists_independent_truth"] is False

    accepted = _accept(client, mission["mission_id"])
    after = _context(client, mission["mission_id"])
    assert after["accepted"] is True
    assert after["donor_snapshot"] == "mission_frozen_donor_read"
    assert after["donor_snapshot_frozen"] is True
    assert after["last_event_seq"] == accepted["last_event_seq"]
    assert after["context_sha256"] != before["context_sha256"]
    assert after["next_state"]["state"] == "architecture_required"
    donor = next(row for row in after["resource_graph"]["resources"] if row["resource_id"] == DONOR)
    assert donor["contract_state"] == "unknown"
    assert donor["unresolved_facts"] == ["contract"]


def test_nonpromoting_findings_keep_artifact_hashes_explicitly_unverified(client):
    mission = _open(client)
    _accept(client, mission["mission_id"])
    _propose(
        client,
        mission["mission_id"],
        {
            "type": "finding_offered",
            "finding": {
                "donor_id": DONOR,
                "signal": "SW1",
                "claim": "The front-panel object appears to be a momentary button.",
                "method": "vision",
                "artifacts": [],
                "source": "retained front-panel inspection",
            },
        },
    )
    first = _context(client, mission["mission_id"])
    assert first["hypotheses"][0]["support_state"] == "unsupported_hypothesis"
    assert first["hypotheses"][0]["promotes_contract_truth"] is False
    assert first["hypotheses"][0]["physical_fact"] is False

    _propose(
        client,
        mission["mission_id"],
        {
            "type": "finding_offered",
            "finding": {
                "donor_id": DONOR,
                "signal": "SW1",
                "claim": "A closeup reference claims to show the switch marking.",
                "method": "marking",
                "artifacts": [{"name": "switch-closeup.jpg", "sha256": "a" * 64}],
                "source": "closeup image",
            },
        },
    )
    second = _context(client, mission["mission_id"])
    assert [row["support_state"] for row in second["hypotheses"]] == [
        "unsupported_hypothesis",
        "unverified_artifact_reference",
    ]
    referenced = second["hypotheses"][1]
    assert referenced["artifact_reference_verified"] is False
    assert referenced["artifact_hash_references"] == [{"name": "switch-closeup.jpg", "sha256": "a" * 64}]
    assert second["truth_contract"]["finding_artifact_hashes_are_verified_evidence"] is False
    assert all(row["physical_fact"] is False for row in second["hypotheses"])


def test_context_advances_to_candidate_work_without_copying_candidate_truth(client):
    mission = _open(client)
    _accept(client, mission["mission_id"])
    _propose(
        client,
        mission["mission_id"],
        {
            "type": "candidate_proposed",
            "candidate": {
                "id": "A",
                "kind": "clean_sheet",
                "label": "Known-parts monitor",
                "spec": example_specs()["esp32_oled_bme280_usb"],
                "rationale": "baseline clean-sheet architecture for comparison",
            },
        },
    )
    context = _context(client, mission["mission_id"])
    assert context["next_state"]["state"] == "architecture_in_progress"
    assert context["candidates"][0]["candidate_id"] == "A"
    assert context["candidates"][0]["latest_evaluation"] is None
    assert context["truth_contract"]["mission_truth_owner"] == "mission_store_event_replay"


def test_salvage_manifest_is_bounded_and_excludes_human_authority_operations(client):
    manifest = salvage_fabrication_manifest(client.app)
    offered = {(item["method"], item["path"]) for item in manifest["operations"]}
    assert ("GET", "/v1/projects/{project_id}/missions/{mission_id}/salvage-fabrication") in offered
    assert ("POST", "/v1/projects/{project_id}/missions/{mission_id}/events") in offered
    assert ("POST", "/v1/fabricator/intelligence/architecture/tradeoffs") in offered
    assert ("POST", "/v1/fabricator/lab/workflows") in offered
    assert ("POST", "/v1/fabrication/approval-requests") in offered

    forbidden_suffixes = ("/accept", "/evidence", "/approve", "/reject", "/execute")
    assert not any(path.endswith(forbidden_suffixes) for _method, path in offered)
    assert manifest["authority_contract"]["agent_can_accept_mission"] is False
    assert manifest["authority_contract"]["agent_can_supply_human_measurement"] is False
    assert manifest["authority_contract"]["agent_can_approve_physical_actuation"] is False


def test_context_exposes_non_authoritative_investigation_queue(client):
    mission = _open(client)
    _accept(client, mission["mission_id"])
    context = _context(client, mission["mission_id"])
    queue = context["investigation_queue"]
    assert queue["schema"] == "hardware_splicer.salvage_investigation_queue.v1"
    assert queue["total_unresolved"] >= 1
    assert all(not item["verified"] and not item["physical_authority_granted"]
               for item in queue["items"])
    assert queue["truth_contract"]["suggested_measurements_are_preapproved"] is False
