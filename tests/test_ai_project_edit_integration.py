from __future__ import annotations

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import base64
import hashlib
import json
from pathlib import Path
import shutil

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from hardware_splicer.ai_project_action_inputs import validate_action_inputs
from hardware_splicer.ai_project_execution_receipts import content_hash
from hardware_splicer.ai_project_orchestrator import parse_ai_project_response
from hardware_splicer.ai_project_tool_executor import execute_ai_project_action_preview
from hardware_splicer.ai_project_tool_executor_api import create_ai_project_tool_executor_router
from hardware_splicer.artifact_retention import install_at_save_retention, load_artifact_pin, read_pinned_artifact_sidecars
from hardware_splicer.engineering_source_ingestion import ingest_engineering_source
from hardware_splicer.project_candidates import list_candidates, read_candidate_file
from hardware_splicer.project_review_store import ProjectReviewStore
from hardware_splicer.project_store import ProjectStore


REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb"
SESSION = "ai-session-native-edit"
ACTION = "action-native-edit"


def _action(action_type="propose_kicad_edit", inputs=None):
    return {
        "action_id": ACTION, "session_id": SESSION, "project_id": "splice", "project_revision": 1,
        "action_type": action_type, "title": "Move the retained resistor", "rationale": "Check the new placement",
        "inputs": inputs if inputs is not None else {"kind": "pcb", "ops": [{"op": "move", "ref": "R2", "x_mm": 118.25, "y_mm": 82.55}]},
        "status": "accepted", "decision": {"decision": "accepted", "reviewer": "engineer", "decided_at": "2026-11-18T09:00:00Z", "executed": False},
        "tool_result": None,
    }


def _session(action):
    return {"session_id": SESSION, "project_id": "splice", "project_revision": 1,
            "mission": "", "constraints": {}, "actions": [action]}


def _seed(tmp_path, monkeypatch, action=None):
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    # This integration exercises native text editing/review/retention. Native
    # DRC with source-rule sidecars has separate tests and a real smoke proof.
    monkeypatch.setattr("hardware_splicer.project_candidates.capability_probe", lambda: {"available": False})
    build = tmp_path / "source/build_compilation"
    build.mkdir(parents=True)
    shutil.copyfile(SOURCE, build / SOURCE.name)
    store = install_at_save_retention(ProjectStore(tmp_path / "projects"))
    snapshot = {
        "projectId": "splice", "name": "Donor revision", "buildDir": str(build.parent),
        "machineProject": {"project_id": "splice", "name": "Splice", "purpose": "Revise a native donor"},
        "engineeringSources": [], "fabrication_authorized": False, "power_on_authorized": False,
    }
    store.save("splice", snapshot, expected_revision=0)
    # The source action remains pinned to revision 1; only its accepted AI
    # bookkeeping is added in revision 2.
    snapshot["engineeringAiSessions"] = [_session(action or _action())]
    store.save("splice", snapshot, expected_revision=1)
    app = FastAPI()
    app.include_router(create_ai_project_tool_executor_router(store))
    return store, TestClient(app), build / SOURCE.name


def _url(suffix="execute-preview"):
    return f"/v1/projects/splice/ai-sessions/{SESSION}/actions/{ACTION}/{suffix}"


def test_native_edit_receipt_preserves_review_base_and_is_idempotent(tmp_path, monkeypatch):
    store, client, original = _seed(tmp_path, monkeypatch)
    original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    result = client.post(_url(), json={"expected_revision": 2})
    assert result.status_code == 200, result.text
    body = result.json()
    summary = body["tool_result"]["summary"]
    assert body["tool_result"]["status"] == "succeeded", body
    assert body["revision"] == store.load("splice")["revision"] == 2
    assert summary["source_identity"]["design_revision"] == 1
    assert summary["base_revision"] == 2
    assert summary["candidate_accepted"] is False
    reviews = ProjectReviewStore(store)
    assert reviews.get("splice", summary["review_id"])["status"] == "pending"
    edited, _ = read_candidate_file(store, "splice", summary["candidate_id"], "pcb")
    assert b"118.25" in edited
    assert hashlib.sha256(original.read_bytes()).hexdigest() == original_hash

    again = client.post(_url(), json={"expected_revision": 2})
    assert again.status_code == 200 and again.json()["idempotent"] is True
    assert again.json()["tool_result"] == body["tool_result"]
    assert len(list_candidates(store, "splice")) == 1
    visible = client.get(_url("execution"))
    assert visible.status_code == 200
    assert visible.json()["executed"] is True
    assert visible.json()["review_state"]["stale"] is False
    # An explicit subsequent review decision still works; execution did not
    # stale or implicitly accept the proposed native edit.
    accepted = reviews.decide("splice", summary["review_id"], decision="accepted", actor="engineer")
    assert accepted["status"] == "accepted"
    assert store.load("splice")["revision"] == 3


def test_design_change_after_action_pin_blocks_native_edit(tmp_path, monkeypatch):
    store, client, _ = _seed(tmp_path, monkeypatch)
    snapshot = store.load("splice")["snapshot"]
    snapshot["constraints"] = {"changed_mounting_pitch_mm": 12}
    store.save("splice", snapshot, expected_revision=2)
    result = client.post(_url(), json={"expected_revision": 3})
    assert result.status_code == 409, result.text
    assert list_candidates(store, "splice") == []


def test_receipt_cannot_replay_changed_accepted_action(tmp_path, monkeypatch):
    store, client, _ = _seed(tmp_path, monkeypatch)
    assert client.post(_url(), json={"expected_revision": 2}).status_code == 200
    snapshot = store.load("splice")["snapshot"]
    snapshot["engineeringAiSessions"][0]["actions"][0]["inputs"]["ops"][0]["x_mm"] = 120
    store.save("splice", snapshot, expected_revision=2)
    changed = client.post(_url(), json={"expected_revision": 3})
    assert changed.status_code == 422, changed.text
    assert "accepted action" in changed.json()["detail"]["message"]
    assert len(list_candidates(store, "splice")) == 1


def test_execution_receipt_result_tamper_is_rejected(tmp_path, monkeypatch):
    store, client, _ = _seed(tmp_path, monkeypatch)
    body = client.post(_url(), json={"expected_revision": 2}).json()
    receipt_path = store.root / "splice" / body["tool_result"]["execution_receipt_relative_path"]
    receipt = json.loads(receipt_path.read_text())
    receipt["tool_result"]["summary"]["candidate_accepted"] = True
    receipt_path.write_text(json.dumps(receipt))
    response = client.get(_url("execution"))
    assert response.status_code == 422
    assert "integrity" in response.json()["detail"]["message"]


def test_simultaneous_edit_retries_create_one_candidate(tmp_path, monkeypatch):
    store, client, _ = _seed(tmp_path, monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.post(_url(), json={"expected_revision": 2}), range(2)))
    assert all(result.status_code == 200 for result in results)
    assert results[0].json()["tool_result"] == results[1].json()["tool_result"]
    assert sorted(result.json()["idempotent"] for result in results) == [False, True]
    assert len(list_candidates(store, "splice")) == 1
    assert store.load("splice")["revision"] == 2


@pytest.mark.parametrize("without_artifact", [False, True])
def test_failed_native_edit_receipt_replays_without_advancing_project(tmp_path, monkeypatch, without_artifact):
    action = _action()
    action["inputs"]["ops"][0]["ref"] = "NO_SUCH_DONOR_COMPONENT"
    store, client, original = _seed(tmp_path, monkeypatch, action)
    source_bytes = original.read_bytes()
    response = client.post(_url(), json={"expected_revision": 2})
    assert response.status_code == 200, response.text
    expected = response.json()["tool_result"]
    assert expected["status"] == "failed"
    assert expected["error"]["type"] == "InvalidEdit"
    if without_artifact:
        # The current executor normally writes failure.json. A diagnostic-only
        # receipt is also valid and must not require a nonexistent artifact.
        receipt_path = store.root / "splice" / expected["execution_receipt_relative_path"]
        receipt = json.loads(receipt_path.read_text())
        (store.root / "splice" / expected["artifact"]["project_relative_path"]).unlink()
        expected["artifact"] = None
        receipt["tool_result"] = expected
        receipt["tool_result_sha256"] = content_hash(expected)
        receipt_path.write_text(json.dumps(receipt))
    repeated = client.post(_url(), json={"expected_revision": 2})
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["idempotent"] is True
    assert repeated.json()["tool_result"] == expected
    read = client.get(_url("execution"))
    assert read.status_code == 200, read.text
    assert read.json()["tool_result"] == expected
    assert read.json()["review_state"] is None
    assert store.load("splice")["revision"] == 2
    assert list_candidates(store, "splice") == []
    assert ProjectReviewStore(store).list("splice") == []
    assert original.read_bytes() == source_bytes


@pytest.mark.parametrize("mutation", ["successful_without_artifact", "invalid_status", "different_action"])
def test_diagnostic_only_receipt_keeps_status_and_identity_guards(tmp_path, monkeypatch, mutation):
    action = _action()
    action["inputs"]["ops"][0]["ref"] = "NO_SUCH_DONOR_COMPONENT"
    store, client, _ = _seed(tmp_path, monkeypatch, action)
    body = client.post(_url(), json={"expected_revision": 2}).json()
    receipt_path = store.root / "splice" / body["tool_result"]["execution_receipt_relative_path"]
    receipt = json.loads(receipt_path.read_text())
    result = receipt["tool_result"]
    result["artifact"] = None
    if mutation == "successful_without_artifact":
        result["status"] = "succeeded"
    elif mutation == "invalid_status":
        result["status"] = "pending"
    else:
        result["action_id"] = "action-someone-else"
    receipt["tool_result_sha256"] = content_hash(result)
    receipt_path.write_text(json.dumps(receipt))
    read = client.get(_url("execution"))
    assert read.status_code == 422, read.text
    assert store.load("splice")["revision"] == 2


def test_explicit_canvas_reaches_production_compose_without_phrase(tmp_path):
    nodes = [{"id": "donor-power", "moduleId": "usb-power-5v"}, {"id": "donor-sensor", "moduleId": "dht22"}]
    wires = [{"id": "custom-ground", "from": {"nodeId": "donor-power", "pinId": "GND"}, "to": {"nodeId": "donor-sensor", "pinId": "GND"}}]
    action = _action("run_compose", {"canvas_nodes": nodes, "canvas_wires": wires, "wire_only": True})
    store = ProjectStore(tmp_path / "projects")
    store.save("splice", {"projectId": "splice"})
    result = execute_ai_project_action_preview(store, "splice", _session(action), action)
    assert result["status"] == "succeeded", result
    artifact = json.loads((store.root / "splice" / result["artifact"]["project_relative_path"]).read_text())
    assert artifact["mode"] == "canvas"
    assert artifact["graph"]["nodes"] == nodes
    assert artifact["graph"]["wires"] == wires


def test_structured_compose_inputs_are_not_silently_truncated():
    nodes = [{"id": f"custom-{i}", "moduleId": "dht22"} for i in range(180)]
    response = {"summary": "Use the supplied graph", "requirements": [], "open_questions": [],
                "architecture_candidates": [], "actions": [{"action_type": "run_compose", "title": "Compile", "rationale": "Preserve all donor identities", "inputs": {"canvas_nodes": nodes, "wire_only": True}, "source_ids": []}]}
    parsed = parse_ai_project_response(json.dumps(response), project_id="splice", project_revision=1, session_id=SESSION, max_actions=2)
    assert parsed["actions"][0]["inputs"]["canvas_nodes"] == nodes


@pytest.mark.parametrize("invalid", [{"out_dir": "/tmp/escape"}, {"allow_llm_first": True}, {"netlist": []}, {"canvas_nodes": ["lost-node"]}])
def test_structured_compose_rejects_execution_overrides_or_lost_structure(invalid):
    with pytest.raises(ValueError):
        validate_action_inputs("run_compose", invalid)


def test_source_promotion_input_selection_matches_bundle_limit():
    assert validate_action_inputs("promote_registered_sources", {}) == {}
    for size in (1, 16):
        sources = [f"source-{index}" for index in range(size)]
        assert validate_action_inputs("promote_registered_sources", {"source_ids": sources})["source_ids"] == sources
    for size in (0, 17):
        with pytest.raises(ValueError):
            validate_action_inputs("promote_registered_sources", {"source_ids": [f"source-{index}" for index in range(size)]})


def test_ai_promotion_keeps_committed_source_bytes_when_manifest_publication_fails(tmp_path, monkeypatch):
    import hardware_splicer.project_store as store_module

    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path / "outputs"))
    store = ProjectStore(tmp_path / "projects")
    original = SOURCE.read_bytes()
    source = ingest_engineering_source({"project_id": "splice", "filename": "donor.kicad_pcb",
        "content_base64": base64.b64encode(original).decode()}, project_root=store.root).source_descriptor
    snapshot = {"projectId": "splice", "engineeringSources": [source]}
    store.save("splice", snapshot)
    action = _action("promote_registered_sources", {"source_ids": [source["source_id"]]})
    snapshot["engineeringAiSessions"] = [_session(action)]
    store.save("splice", snapshot, expected_revision=1)
    app = FastAPI()
    app.include_router(create_ai_project_tool_executor_router(store))
    client = TestClient(app)
    atomic_write = store_module._atomic_write_json

    def fail_manifest(path, value, **kwargs):
        if path == store.root / "splice/project.json":
            raise OSError("manifest publication failed after immutable revision write")
        return atomic_write(path, value, **kwargs)

    monkeypatch.setattr(store_module, "_atomic_write_json", fail_manifest)
    response = client.post(_url(), json={"expected_revision": 2})
    assert response.status_code == 500, response.text
    assert store.load("splice")["revision"] == 2
    committed = store.load("splice", revision=3)["snapshot"]
    workspace = Path(committed["sourceEditing"]["build_dir"])
    assert (workspace / "build_compilation/donor.kicad_pcb").read_bytes() == original
    assert committed["engineeringAiSessions"][0]["actions"][0]["tool_result"]["status"] == "succeeded"


@pytest.mark.parametrize("action_type,kind,suffix", [("run_drc", "pcb", ".kicad_pcb"), ("run_erc", "schematic", ".kicad_sch")])
@pytest.mark.parametrize("native_available", [False, True])
def test_native_check_uses_matching_retained_kind_without_upload_fallback(tmp_path, monkeypatch, action_type, kind, suffix, native_available):
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    build = tmp_path / "native/build_compilation"
    build.mkdir(parents=True)
    for extension in (".kicad_pcb", ".kicad_sch", ".kicad_pro"):
        shutil.copyfile(SOURCE.with_suffix(extension), build / ("donor" + extension))
    store = install_at_save_retention(ProjectStore(tmp_path / "projects"))
    action = _action(action_type, {})
    session = _session(action)
    store.save("splice", {"projectId": "splice", "buildDir": str(build.parent), "engineeringAiSessions": [session]})
    calls = []
    fallback = []

    def native_check(selected_kind, text, *, timeout_s, sidecars=None):
        calls.append((selected_kind, text.encode(), sidecars))
        return {"errors": 0, "warnings": 0, "total": 0, "by_type": {}}

    monkeypatch.setattr("hardware_splicer.project_candidates.capability_probe", lambda: {"available": native_available, "version": "test"})
    monkeypatch.setattr("hardware_splicer.project_candidates._run_one_check", native_check)
    monkeypatch.setattr("hardware_splicer.ai_project_tool_executor.analyze_registered_project_bundle",
                        lambda *args, **kwargs: fallback.append(True) or {})
    result = execute_ai_project_action_preview(store, "splice", session, action)
    assert not fallback
    if native_available:
        assert result["status"] == "succeeded", result
        assert calls and all(selected == kind and raw == SOURCE.with_suffix(suffix).read_bytes() for selected, raw, _ in calls)
        assert all(sidecars == {"project": SOURCE.with_suffix(".kicad_pro").read_bytes()} for _, _, sidecars in calls)
        assert result["summary"]["check_executed"] is True
    else:
        assert result["status"] == "failed", result
        assert "did not run" in result["error"]["message"]
        assert not calls
        assert not result["summary"].get("check_executed")


def test_netlist_splice_and_module_inputs_reach_compose_intact(tmp_path):
    values = {"netlist": {"components": [{"ref": "U91", "footprint": "Custom:part"}], "nets": []},
              "resolved_modules": [{"module_id": "new-module", "source_id": "donor-a"}],
              "splice_plan": {"custom_graph": {"nodes": [{"id": "U91"}], "wires": []}},
              "build_id": "generic_low_voltage_build", "drc_fixup": {"edge_pad_extra_mm": 1.0}}
    action = _action("run_compose", deepcopy(values))
    store = ProjectStore(tmp_path / "projects")
    store.save("splice", {"projectId": "splice"})
    calls = []
    result = execute_ai_project_action_preview(store, "splice", _session(action), action,
        compose_callable=lambda **kwargs: calls.append(kwargs) or {"ok": True, "mode": "netlist"})
    assert result["status"] == "succeeded"
    assert all(calls[0][key] == value for key, value in values.items())
    assert calls[0]["allow_llm_first"] is False and calls[0]["export_gerber"] is False


def test_uploaded_bundle_promotes_once_then_native_edit_opens_pending_review(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path / "outputs"))
    monkeypatch.setattr("hardware_splicer.project_candidates.capability_probe", lambda: {"available": False})
    store = install_at_save_retention(ProjectStore(tmp_path / "projects"))
    originals = {
        "donor.kicad_pcb": SOURCE.read_bytes(),
        "donor.kicad_pro": b'{"board":{"design_settings":{"rules":{"min_clearance":0.37}}}}',
        "donor.kicad_dru": b'(version 1)\n(rule "donor" (constraint clearance (min 0.37mm)))\n',
    }
    sources = [ingest_engineering_source({"project_id": "splice", "filename": name,
        "content_base64": base64.b64encode(data).decode()}, project_root=store.root).source_descriptor
        for name, data in originals.items()]
    snapshot = {"projectId": "splice", "engineeringSources": sources, "power_on_authorized": False}
    store.save("splice", snapshot)
    promotion_action = _action("promote_registered_sources", {"source_ids": [row["source_id"] for row in sources]})
    snapshot["engineeringAiSessions"] = [_session(promotion_action)]
    active_session = snapshot["engineeringAiSessions"][0]
    active_session["buildDir"] = str(tmp_path / "old-active-build")
    active_session["projectPackage"] = {"build_dir": str(tmp_path / "old-active-build"), "note": "keep package context"}
    active_session["package"] = {"build_dir": str(tmp_path / "old-active-build")}
    store.save("splice", snapshot, expected_revision=1)
    app = FastAPI()
    app.include_router(create_ai_project_tool_executor_router(store))
    client = TestClient(app)
    response = client.post(_url(), json={"expected_revision": 2})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["tool_result"]["status"] == "succeeded", result
    assert result["revision"] == 3
    promoted = store.load("splice")
    assert promoted["snapshot"]["engineeringSources"] == sources
    assert promoted["snapshot"]["sourceRevisionImpact"]["status"] == "requires_recheck"
    pin = load_artifact_pin(store, "splice", 3)
    assert pin and pin["artifacts"]["pcb"]
    sidecars = read_pinned_artifact_sidecars(store, "splice", 3, "pcb")
    assert sidecars["project"][0] == originals["donor.kicad_pro"]
    assert sidecars["rules"][0] == originals["donor.kicad_dru"]
    build_dir = Path(promoted["snapshot"]["buildDir"])
    promoted_session = promoted["snapshot"]["engineeringAiSessions"][0]
    assert promoted_session["buildDir"] == str(build_dir)
    assert promoted_session["projectPackage"]["build_dir"] == str(build_dir)
    assert promoted_session["projectPackage"]["note"] == "keep package context"
    assert promoted_session["package"]["build_dir"] == str(build_dir)
    assert promoted_session["actions"][0]["status"] == "completed"
    assert all((build_dir / "build_compilation" / name).read_bytes() == data for name, data in originals.items())
    repeated = client.post(_url(), json={"expected_revision": 3})
    assert repeated.json()["idempotent"] is True
    assert store.load("splice")["revision"] == 3

    edit = _action()
    edit["action_id"] = "action-followup-edit"
    edit["project_revision"] = 3
    snapshot = promoted["snapshot"]
    snapshot["engineeringAiSessions"][0]["actions"].append(edit)
    store.save("splice", snapshot, expected_revision=3)
    followup = client.post(_url().replace(ACTION, edit["action_id"]), json={"expected_revision": 4})
    assert followup.status_code == 200, followup.text
    summary = followup.json()["tool_result"]["summary"]
    assert followup.json()["tool_result"]["status"] == "succeeded", followup.text
    assert summary["base_revision"] == 4
    assert summary["source_identity"]["design_revision"] == 3
    assert summary["source_revision_impact"]["basis"] == "native_candidate_edit"
    assert store.load("splice")["revision"] == 4
    assert store.load("splice")["snapshot"]["buildDir"] == str(build_dir)
    assert ProjectReviewStore(store).get("splice", summary["review_id"])["status"] == "pending"

    ProjectReviewStore(store).decide("splice", summary["review_id"], decision="accepted", actor="engineer")
    accepted = store.load("splice")
    assert accepted["revision"] == 5
    edited_bytes, edited_hash = read_candidate_file(store, "splice", summary["candidate_id"], "pcb")
    assert edited_bytes != originals["donor.kicad_pcb"]
    calls = []

    def native_check(kind, text, *, timeout_s, sidecars=None):
        calls.append((kind, text.encode(), sidecars))
        return {"errors": 1, "warnings": 0, "total": 1, "by_type": {"clearance": 1}}

    monkeypatch.setattr("hardware_splicer.project_candidates.capability_probe", lambda: {"available": True, "version": "test"})
    monkeypatch.setattr("hardware_splicer.project_candidates._run_one_check", native_check)
    actions = []
    for pinned_revision in (5, 3):
        action = _action("run_drc", {})
        action["action_id"] = f"action-drc-revision-{pinned_revision}"
        action["project_revision"] = pinned_revision
        actions.append(action)
    accepted["snapshot"]["engineeringAiSessions"][0]["actions"].extend(actions)
    store.save("splice", accepted["snapshot"], expected_revision=5)
    for expected_current, action, expected_bytes, expected_hash in (
        (6, actions[0], edited_bytes, edited_hash),
        (7, actions[1], originals["donor.kicad_pcb"], "sha256:" + hashlib.sha256(originals["donor.kicad_pcb"]).hexdigest()),
    ):
        calls.clear()
        checked = client.post(_url().replace(ACTION, action["action_id"]), json={"expected_revision": expected_current})
        assert checked.status_code == 200, checked.text
        tool_result = checked.json()["tool_result"]
        assert tool_result["status"] == "succeeded", tool_result
        check_summary = tool_result["summary"]
        assert check_summary["source_sha256"] == expected_hash
        assert check_summary["source_revision"] == action["project_revision"]
        assert check_summary["rule_finding_count"] == 1
        assert check_summary["project_context"] == "retained_native_revision"
        assert calls and all(kind == "pcb" and raw == expected_bytes for kind, raw, _ in calls)
        assert all(sidecars == {"project": originals["donor.kicad_pro"], "rules": originals["donor.kicad_dru"]}
                   for _, _, sidecars in calls)
