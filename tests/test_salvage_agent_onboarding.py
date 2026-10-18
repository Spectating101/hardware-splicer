"""Scripted cold-client controls, not evidence of a live LLM or physical build.

The operator fixture prepares an isolated mission. The client side discovers
payloads through the same gateway functions as MCP, never MissionStore internals.
"""
from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, ValidationError

from hardware_splicer.mcp_backend_gateway import describe_operation, dispatch_operation
from hardware_splicer.mission_store import _EVAL_OPERATIONS, _PROPOSE_TYPES
from hardware_splicer.operator_identity import hash_operator_token
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.salvage_fabrication_manifest import salvage_fabrication_manifest

PROJECT = "cold-client-control"
DONOR = "donor:toy:motor-board"


@pytest.fixture()
def host(tmp_path, monkeypatch):
    # A synthetic human exists only in this fixture; its credential is never
    # handed to the cold client or represented as real bench evidence.
    token = "protocol-fixture-" + "x" * 48
    monkeypatch.setenv("HARDWARE_SPLICER_OPERATOR_TOKENS", json.dumps({
        hash_operator_token(token): {"kind": "human", "id": "fixture-operator"},
    }))
    store = ProjectStore(tmp_path)
    store.save(PROJECT, {
        "projectId": PROJECT, "projectName": "Protocol control", "currentStage": "design",
        "mode": "salvage", "graph": {"nodes": [], "edges": []},
        "machineProject": {"project_id": PROJECT, "name": "Protocol control", "purpose": "protocol control"},
    }, expected_revision=0)
    app = create_product_app(store)
    client = TestClient(app)

    def prepare(*, unknown_junk=False):
        intake = {"goal": "Exercise the agent interface without claiming a physical build",
                  "inventory": ["unidentified battery toy board"] if unknown_junk else ["ESP32", "BME280", "OLED"]}
        if unknown_junk:
            intake["donors"] = [{"donor_id": DONOR, "label": "Unidentified toy board"}]
        response = client.post(f"/v1/projects/{PROJECT}/missions", json={
            "intake": intake, "author": {"kind": "agent", "id": "fixture-preparer"},
        })
        assert response.status_code == 201, response.text
        mid = response.json()["mission"]["mission_id"]
        accepted = client.post(f"/v1/projects/{PROJECT}/missions/{mid}/accept",
                               headers={"X-HS-Operator-Token": token})
        assert accepted.status_code == 200, accepted.text
        return mid

    return app, client, prepare


class ColdClient:
    """No source-derived operation IDs, hidden mutation helpers or human token."""

    def __init__(self, app, mission_id):
        self.app = app
        self.manifest = salvage_fabrication_manifest(app)
        self.path_params = {"project_id": PROJECT, "mission_id": mission_id}
        self.calls = []

    def operation(self, method, suffix):
        return next(op for op in self.manifest["operations"]
                    if op["method"] == method and op["path"].endswith(suffix))

    def call(self, op, *, body=None, extra_path=None):
        available = {**self.path_params, **(extra_path or {})}
        bound = {key: value for key, value in available.items() if "{" + key + "}" in op["path"]}
        result = asyncio.run(dispatch_operation(
            op["operation_id"], app=self.app,
            path_params=bound, json_body=body,
        ))
        self.calls.append({"operation_id": op["operation_id"], "status_code": result["status_code"],
                           "response_bytes": len(json.dumps(result).encode())})
        return result

    def context(self):
        return self.call(self.operation("GET", "/salvage-fabrication"))["body"]["context"]

    def proposal(self, kind, context):
        op = self.operation("POST", "/events")
        described = describe_operation(op["operation_id"], self.app)
        content = described["operation"]["requestBody"]["content"]["application/json"]
        body = copy.deepcopy(content["examples"][kind]["value"])
        body["expected_event_seq"] = context["last_event_seq"]
        return op, body, content["schema"]


def test_compact_manifest_is_small_and_full_contracts_are_on_demand(host):
    app, _, _ = host
    compact = salvage_fabrication_manifest(app)
    full = salvage_fabrication_manifest(app, include_schemas=True)
    size = lambda value: len(json.dumps(value, indent=2, sort_keys=True).encode())
    assert compact["detail"] == "compact"
    assert full["detail"] == "full"
    assert compact["schema_version"] == "hardware_splicer.salvage_fabrication_manifest.v2"
    assert compact["operation_ids"] == full["operation_ids"]
    assert size(compact) < 14000
    assert size(compact) < size(full) * 0.35
    assert all("referenced_schemas" not in op and "operation" not in op for op in compact["operations"])
    assert all("referenced_schemas" in op for op in full["operations"])
    paths = {op["path"] for op in compact["operations"]}
    assert "/v1/devices/draft" in paths and "/v1/devices/spec-schema" in paths
    assert "/v1/devices/parts-reading" in paths
    assert "/v1/fabricator/intelligence/vision/donor-drafts" in paths
    assert any(path.endswith("/salvage-fabrication") for path in paths)
    assert not any(path.endswith(("/accept", "/answer", "/evidence", "/confirm", "/approve", "/execute"))
                   for path in paths)


def test_discovered_event_and_run_schemas_follow_the_canonical_enums(host):
    app, _, prepare = host
    agent = ColdClient(app, prepare(unknown_junk=True))
    op = agent.operation("POST", "/events")
    content = describe_operation(op["operation_id"], app)["operation"]["requestBody"]["content"]["application/json"]
    schema = content["schema"]
    assert {variant["properties"]["type"]["const"] for variant in schema["properties"]["event"]["oneOf"]} == _PROPOSE_TYPES
    assert set(content["examples"]) == _PROPOSE_TYPES
    for example in content["examples"].values():
        Draft202012Validator(schema).validate(example["value"])
    run = agent.operation("POST", "/run")
    body = describe_operation(run["operation_id"], app)["operation"]["requestBody"]["content"]["application/json"]
    assert set(body["schema"]["properties"]["operation"]["enum"]) == _EVAL_OPERATIONS
    assert set(body["examples"]) == _EVAL_OPERATIONS


def test_contracts_and_runtime_both_refuse_forged_evidence_or_system_events(host):
    app, _, prepare = host
    agent = ColdClient(app, prepare(unknown_junk=True))
    context = agent.context()
    op, body, schema = agent.proposal("finding_offered", context)
    body["event"]["finding"]["donor_id"] = DONOR
    body["event"]["finding"]["grade"] = "person_measurement"
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(body)
    assert agent.call(op, body=body)["status_code"] == 422
    body["event"] = {"type": "evaluation_recorded"}
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(body)
    assert agent.call(op, body=body)["status_code"] == 422
    assert agent.context()["last_event_seq"] == context["last_event_seq"]


def test_measurement_request_schema_names_the_required_quantity(host):
    app, _, prepare = host
    agent = ColdClient(app, prepare(unknown_junk=True))
    _, body, schema = agent.proposal("evidence_required", agent.context())
    body["event"]["request"] = {"kind": "electrical", "target": DONOR,
                               "instructions": "Only a qualified person may supply actual measurements."}
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(body)
    body["event"]["request"]["quantity"] = "voltage"
    Draft202012Validator(schema).validate(body)
    body["event"]["request"]["kind"] = "boot_log"
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(body)


def test_quickstart_uses_the_canonical_surface_and_labels_the_legacy_lane():
    docs = Path(__file__).resolve().parents[1] / "docs"
    quickstart = (docs / "AGENT_QUICKSTART.md").read_text()
    assert "salvage_fabrication" in quickstart and "hardware_splicer.backend_mcp_server" in quickstart
    assert "LEGACY_COMPOSE_AGENT_QUICKSTART.md" in quickstart
    assert (docs / "LEGACY_COMPOSE_AGENT_QUICKSTART.md").is_file()
    assert "scripted protocol" in (docs / "SALVAGE_AGENT_TRIAL.md").read_text()


def test_cold_client_finds_junk_records_a_bounded_finding_and_recovers_stale_sequence(host):
    app, client, prepare = host
    mid = prepare(unknown_junk=True)
    agent = ColdClient(app, mid)
    before = agent.context()
    assert before["inventory"] == ["unidentified battery toy board"]
    assert before["inventory_reading"]["reading"]["left_out"]
    assert before["investigation_queue"]["items"]
    op, body, schema = agent.proposal("finding_offered", before)
    body["event"]["finding"].update({
        "donor_id": DONOR, "source": "Synthetic protocol-control caption, not manufacturer evidence",
        "claim": "The fixture labels the object a toy board; its identity and interface remain unresolved.",
    })
    Draft202012Validator(schema).validate(body)
    assert agent.call(op, body=body)["status_code"] == 201
    resumed = ColdClient(app, mid)
    after = resumed.context()
    assert after["context_sha256"] != before["context_sha256"]
    assert after["hypotheses"][0]["support_state"] == "unsupported_hypothesis"
    assert after["hypotheses"][0]["physical_fact"] is False
    # The stale request is an explicit recovery control, not a claimed happy-path success.
    stale = resumed.call(op, body=body)
    assert stale["status_code"] == 409
    assert resumed.context()["last_event_seq"] == after["last_event_seq"]
    need_op, need, schema = resumed.proposal("evidence_required", resumed.context())
    need["event"]["need"] = "Find public interface documentation; do not infer pinout or voltage from appearance."
    Draft202012Validator(schema).validate(need)
    assert resumed.call(need_op, body=need)["status_code"] == 201
    final = resumed.context()
    assert final["needs"] and final["terminal"] is None
    assert "continue_independent_research_or_design" in final["next_state"]["recommended_intents"]
    assert final["truth_contract"]["agent_can_supply_human_measurement"] is False
    # A direct attempt still hits the human gate, even outside the bounded manifest.
    assert client.post(f"/v1/projects/{PROJECT}/missions/{mid}/accept").status_code == 403


def test_catalog_control_reaches_a_package_and_resumes_without_chat_state(host):
    app, client, prepare = host
    mid = prepare()
    agent = ColdClient(app, mid)
    context = agent.context()
    draft = agent.call(agent.operation("POST", "/v1/devices/draft"),
                       body={"text": "\n".join(context["inventory"])})
    assert draft["ok"], draft
    op, body, schema = agent.proposal("candidate_proposed", context)
    body["event"]["candidate"]["spec"] = draft["body"]["spec"]
    body["event"]["candidate"]["kind"] = "clean_sheet"
    Draft202012Validator(schema).validate(body)
    assert agent.call(op, body=body)["ok"]
    resumed = ColdClient(app, mid)
    current = resumed.context()
    candidate = current["candidates"][0]["candidate_id"]
    run = resumed.operation("POST", "/run")
    examples = describe_operation(run["operation_id"], app)["operation"]["requestBody"]["content"]["application/json"]["examples"]
    for operation in ("device_plan", "device_engineering"):
        result = resumed.call(run, body=examples[operation]["value"], extra_path={"candidate_id": candidate})
        assert result["ok"], result
        assert result["body"]["evaluation"]["result"]["errors"] == 0
    current = resumed.context()
    assert set(current["candidates"][0]["recorded_checks"]) == {"device_plan", "device_engineering"}
    terminal_op, terminal, schema = resumed.proposal("terminal_proposed", current)
    terminal["event"]["candidate_id"] = candidate
    Draft202012Validator(schema).validate(terminal)
    assert resumed.call(terminal_op, body=terminal)["ok"]
    package = resumed.call(resumed.operation("POST", "/package"))
    assert package["ok"], package
    state = client.get(f"/v1/projects/{PROJECT}/missions/{mid}").json()["mission"]
    assert state["terminal"]["state"] == "READY_FOR_HUMAN_BUILD"
    assert state["physical_correctness"] == "UNPROVEN"
    assert state["power_on_authorized"] is False
    assert all(call["status_code"] < 300 for call in agent.calls + resumed.calls)


def test_resumed_context_marks_pre_repair_checks_stale_using_the_canonical_boundary(host):
    app, _, prepare = host
    agent = ColdClient(app, prepare())
    context = agent.context()
    draft = agent.call(agent.operation("POST", "/v1/devices/draft"),
                       body={"text": "\n".join(context["inventory"])})["body"]["spec"]
    broken = copy.deepcopy(draft)
    connection = next(row for row in broken["connections"] if row["from"].endswith(".SDA"))
    broken["connections"].remove(connection)
    op, body, _ = agent.proposal("candidate_proposed", context)
    body["event"]["candidate"].update({"spec": broken, "kind": "clean_sheet"})
    assert agent.call(op, body=body)["ok"]
    run = agent.operation("POST", "/run")
    failed = agent.call(run, body={"operation": "device_plan"}, extra_path={"candidate_id": "A"})
    assert failed["body"]["evaluation"]["result"]["errors"] > 0
    before = agent.context()
    assert before["candidates"][0]["recorded_checks"]["device_plan"]["current"] is True
    op, repair, _ = agent.proposal("repair_proposed", before)
    repair["event"]["spec"] = draft
    assert agent.call(op, body=repair)["ok"]
    resumed = ColdClient(app, context["mission_id"])
    repaired = resumed.context()
    summary = repaired["candidates"][0]
    assert summary["recorded_checks"]["device_plan"]["current"] is False
    assert summary["recorded_checks"]["device_plan"]["seq"] <= summary["evaluation_base_seq"]
    assert resumed.call(run, body={"operation": "device_plan"}, extra_path={"candidate_id": "A"})["ok"]
    assert resumed.context()["candidates"][0]["recorded_checks"]["device_plan"]["current"] is True
