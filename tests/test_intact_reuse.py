"""Software deliverables for ordinary intact donors, without fictional dev boards."""
from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
import secrets
import subprocess
import sys
import zipfile

from fastapi.testclient import TestClient
import pytest

from hardware_splicer.intact_reuse import build_intact_reuse, IntactReuseSpec
from hardware_splicer.intact_reuse_adapter import Adapter
from hardware_splicer.operator_identity import hash_operator_token
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.salvage_fabrication_manifest import salvage_fabrication_manifest

AGENT = {"kind": "agent", "id": "intact-reuse-test"}
DONOR = "donor:usb-mouse:controller"


@pytest.fixture
def host(tmp_path, monkeypatch):
    token = secrets.token_urlsafe(48)
    monkeypatch.setenv("HARDWARE_SPLICER_OPERATOR_TOKENS", json.dumps({
        hash_operator_token(token): {"kind": "human", "id": "software-test-host"},
    }))
    store = ProjectStore(tmp_path)
    store.save("mouse", {"name": "Unobserved ordinary wired mouse; document-only example"}, expected_revision=0)
    app = create_product_app(store)
    client = TestClient(app)
    response = client.post("/v1/projects/mouse/sources/ingest-file", files={
        "file": ("public-packet.md", b"Synthetic document packet, not physical evidence or a USB descriptor.", "text/markdown"),
    }, data={"expected_revision": "1", "authority_ceiling": "declared"})
    assert response.status_code == 201, response.text
    source_id = response.json()["ingestion"]["source_id"]
    response = client.post("/v1/projects/mouse/missions", json={
        "intake": {"goal": "Document-only wired-mouse foot control without a purchased controller",
                   "inventory": ["Unidentified wired USB mouse"],
                   "donors": [{"donor_id": DONOR, "label": "Unobserved mouse controller"}]},
        "author": AGENT,
    })
    assert response.status_code == 201, response.text
    mid = response.json()["mission"]["mission_id"]
    prefix = f"/v1/projects/mouse/missions/{mid}"
    accepted = client.post(prefix + "/accept", headers={"X-HS-Operator-Token": token})
    assert accepted.status_code == 200, accepted.text
    spec = client.get(prefix + "/intact-reuse-spec").json()["example"]
    assert spec["source_ids"] == [source_id] and spec["donors_used"] == [DONOR]
    return store, app, client, prefix, mid, spec


def propose(host, spec=None):
    _, _, client, prefix, _, default = host
    response = client.post(prefix + "/events", json={"event": {"type": "candidate_proposed", "candidate": {
        "id": "mouse_reuse", "kind": "reclaim_heavy", "label": "Intact mouse pedal",
        "spec": default if spec is None else spec, "rationale": "Proposed external mechanism; no observed specimen."}}, "author": AGENT})
    assert response.status_code == 201, response.text
    return response.json()


def run(host):
    _, _, client, prefix, _, _ = host
    response = client.post(prefix + "/candidates/mouse_reuse/run", json={"operation": "intact_reuse"})
    assert response.status_code == 200, response.text
    result = response.json()
    return result, client.get(prefix + "/" + result["evaluation"]["artifact"]).json()["run"]


def test_real_mission_generates_hash_bound_download_without_any_catalog_module(host, tmp_path):
    store, _, client, prefix, mid, _ = host
    before = store.load("mouse")
    propose(host)
    result, report = run(host)
    assert result["evaluation"]["result"]["errors"] == 0
    assert result["evaluation"]["result"]["warnings"] == 4
    assert result["mission"]["budgets"]["operator_jobs_used"] == 1
    assert report["software_checks_passed"] is True
    assert len(report["offline_checks"]["scenarios"]) == 7
    assert all(row["pass"] for row in report["offline_checks"]["scenarios"])
    assert "modules" not in report["contract"]["design"]
    assert report["contract"]["physical_correctness"] == "UNPROVEN"
    assert report["contract"]["physical_authority_granted"] is False
    response = client.get(result["bundle_download_path"])
    assert response.status_code == 200 and response.headers["x-hs-artifact-scope"] == "software-review-only"
    assert hashlib.sha256(response.content).hexdigest() == report["package_sha256"]
    assert response.content == client.get(result["bundle_download_path"]).content
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.testzip() is None
        assert sorted(archive.namelist()) == ["README.md", "adapter.py", "contract.json", "example-events.jsonl", "offline-checks.json", "test_adapter.py"]
        for entry in report["files"]:
            assert hashlib.sha256(archive.read(entry["name"])).hexdigest() == entry["sha256"]
        archive.extractall(tmp_path / "delivered")
    delivered = tmp_path / "delivered"
    replay = subprocess.run([sys.executable, "-I", str(delivered / "test_adapter.py")], capture_output=True, text=True, timeout=10)
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout) == report["offline_checks"]
    cli = subprocess.run([sys.executable, "-I", str(delivered / "adapter.py")],
                         input=(delivered / "example-events.jsonl").read_text(), capture_output=True, text=True, timeout=10)
    assert cli.returncode == 0, cli.stderr
    assert [json.loads(line) for line in cli.stdout.splitlines()] == [{"type": "action", "action": "activate", "device_alias": "donor_mouse"}]
    assert store.load("mouse") == before  # No snapshot, ledger or donor-contract promotion.
    assert result["mission"]["terminal"] is None
    # A software review bundle does not bypass the old READY-delivery gate.
    assert client.post(prefix + "/package").status_code == 409
    assert client.post(prefix + "/events", json={"author": AGENT, "event": {
        "type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD", "candidate_id": "mouse_reuse", "reason": "Offline adapter tests passed"}}).status_code == 409


def test_bundle_is_deterministic_for_identical_spec_source_and_revision(host):
    store, _, client, prefix, _, spec = host
    propose(host)
    view = client.get(prefix).json()["mission"]
    report1, data1 = build_intact_reuse(spec, view=view, project=store.load("mouse"), candidate_id="mouse_reuse", project_root=store.root)
    report2, data2 = build_intact_reuse(copy.deepcopy(spec), view=view, project=store.load("mouse"), candidate_id="mouse_reuse", project_root=store.root)
    assert data1 == data2 and report1 == report2


@pytest.mark.parametrize("defect", ["unknown_source", "extra_code", "bad_binding", "wrong_class", "empty_mechanics"])
def test_invalid_native_specs_are_recorded_as_failures_not_fake_successes(host, defect):
    _, _, client, prefix, _, spec = host
    spec = copy.deepcopy(spec)
    if defect == "unknown_source":
        spec["source_ids"] = ["not-admitted"]
    elif defect == "extra_code":
        spec["code"] = "raise RuntimeError('never executed')"
    elif defect == "bad_binding":
        spec["interface"]["action"] = "touch /tmp/not-an-action-command"
    elif defect == "wrong_class":
        spec["design_class"] = "any_usb_device"
    else:
        spec["mechanical"]["load_path"] = ""
    propose(host, spec)
    result, report = run(host)
    assert result["evaluation"]["result"]["errors"] == 1
    assert "refused" in report and "bundle_download_path" not in result
    assert client.get(prefix + "/" + result["evaluation"]["artifact"] + "/bundle").status_code == 404


def test_failed_intact_check_can_be_repaired_without_erasing_donor(host):
    _, _, client, prefix, _, spec = host
    broken = copy.deepcopy(spec)
    broken["source_ids"] = ["not-admitted"]
    propose(host, broken)
    run(host)
    response = client.post(prefix + "/events", json={"author": AGENT, "event": {
        "type": "repair_proposed", "candidate_id": "mouse_reuse", "spec": spec, "rationale": "Use the admitted source instead of an unknown ID."}})
    assert response.status_code == 201, response.text
    result, _ = run(host)
    assert result["evaluation"]["result"]["errors"] == 0
    # Unresolved physical warnings do not make a clean software spec an endlessly repairable failure.
    assert client.post(prefix + "/events", json={"author": AGENT, "event": {
        "type": "repair_proposed", "candidate_id": "mouse_reuse", "spec": spec, "rationale": "No new failure or evidence."}}).status_code == 409


@pytest.mark.parametrize("tamper", ["source", "run", "bundle"])
def test_tampered_source_run_or_bundle_never_downloads_as_verified(host, tamper):
    store, _, client, prefix, mid, _ = host
    propose(host)
    if tamper == "source":
        source = store.load("mouse")["snapshot"]["engineeringSources"][0]
        from hardware_splicer.stored_source_parser import _blob_path
        _blob_path(store.root, "mouse", source).write_bytes(b"tampered fixture")
        result, _ = run(host)
        assert result["evaluation"]["result"]["errors"] == 1
        return
    result, report = run(host)
    mission_dir = store.root / "mouse/missions" / mid
    path = mission_dir / (result["evaluation"]["artifact"] if tamper == "run" else f"packages/{report['package_sha256'][:16]}.zip")
    path.write_bytes(b"tampered fixture")
    assert client.get(result["bundle_download_path"]).status_code == (404 if tamper == "run" else 500)


def test_remote_contact_option_keeps_an_additional_unknown_and_emits_no_wiring(host):
    _, _, client, _, _, spec = host
    spec["mechanical"]["approach"] = "remote_contact"
    propose(host, spec)
    result, report = run(host)
    assert result["evaluation"]["result"]["warnings"] == 5
    assert "no wiring or pinout" in report["contract"]["unresolved_physical_questions"][-1]


def test_discovery_is_small_and_part_of_the_agent_manifest(host):
    _, app, client, prefix, _, _ = host
    schema = client.get(prefix + "/intact-reuse-spec").json()
    assert IntactReuseSpec.model_validate(schema["example"])
    assert len(json.dumps(schema).encode()) < 7000
    paths = {row["path"] for row in salvage_fabrication_manifest(app)["operations"]}
    assert any(path.endswith("/intact-reuse-spec") for path in paths)
    assert any(path.endswith("/runs/{name}/bundle") for path in paths)


@pytest.mark.parametrize("mutation", ["repeated_press", "wrong_device", "wrong_button", "connect_armed"])
def test_delivered_replays_kill_seeded_adapter_faults(host, monkeypatch, mutation):
    actual_read = Path.read_text
    def mutated_read(path, *args, **kwargs):
        text = actual_read(path, *args, **kwargs)
        if path.name == "intact_reuse_adapter.py":
            old, new = {
                "repeated_press": ('elif self.state == "armed":', 'elif True:'),
                "wrong_device": ('if event["device"] != self.device:', 'if False:'),
                "wrong_button": ('elif event["button"] == self.button and self.state != "disconnected":', 'elif self.state != "disconnected":'),
                "connect_armed": ('elif kind == "connected":\n            self.state = "wait_release"', 'elif kind == "connected":\n            self.state = "armed"'),
            }[mutation]
            assert old in text
            return text.replace(old, new)
        return text
    monkeypatch.setattr(Path, "read_text", mutated_read)
    propose(host)
    result, report = run(host)
    assert result["evaluation"]["result"]["errors"] == 1
    assert "failed synthetic replay" in report["refused"]
    assert "bundle_download_path" not in result


def test_unaccepted_mission_and_exhausted_budget_refuse_new_adapter_runs(host, monkeypatch):
    store, app, client, prefix, mid, spec = host
    # A new mission has not inherited the first mission's acceptance.
    opened = client.post("/v1/projects/mouse/missions", json={"author": AGENT, "intake": {
        "goal": "Unaccepted software trial", "inventory": ["unknown wired mouse"],
        "donors": [{"donor_id": DONOR, "label": "Unknown donor"}],
        "budgets": {"max_operator_jobs": 1}}}).json()["mission"]
    other = f"/v1/projects/mouse/missions/{opened['mission_id']}"
    submitted = client.post(other + "/events", json={"author": AGENT, "event": {"type": "candidate_proposed", "candidate": {
        "id": "A", "kind": "reclaim_heavy", "label": "Unaccepted design", "spec": spec, "rationale": "Not accepted."}}})
    assert submitted.status_code == 201
    assert client.post(other + "/candidates/A/run", json={"operation": "intact_reuse"}).status_code == 409
    assert not (store.root / "mouse/missions" / opened["mission_id"] / "packages").exists()
    propose(host)
    result, _ = run(host)
    # Wrong-mission lookup must not expose the first mission's bundle.
    name = result["evaluation"]["artifact"].split("/")[1]
    assert client.get(other + f"/runs/{name}/bundle").status_code == 404
    token = secrets.token_urlsafe(48)
    monkeypatch.setenv("HARDWARE_SPLICER_OPERATOR_TOKENS", json.dumps({
        hash_operator_token(token): {"kind": "human", "id": "budget-test-host"}}))
    assert client.post(other + "/accept", headers={"X-HS-Operator-Token": token}).status_code == 200
    assert client.post(other + "/candidates/A/run", json={"operation": "intact_reuse"}).status_code == 200
    assert client.post(other + "/candidates/A/run", json={"operation": "intact_reuse"}).status_code == 409


@pytest.mark.parametrize("event", [None, [], {}, {"type": "shell", "device": "mouse"}, {"type": "pressed", "device": "mouse"}])
def test_adapter_rejects_malformed_input(event):
    with pytest.raises(ValueError):
        Adapter("mouse", "left", "activate").feed(event)


def test_only_one_symbolic_action_is_emitted_no_host_side_effects():
    adapter = Adapter("mouse", "left", "activate")
    assert adapter.feed({"type": "connected", "device": "mouse"}) == []
    assert adapter.feed({"type": "pressed", "device": "mouse", "button": "left"}) == []
    assert adapter.feed({"type": "released", "device": "mouse", "button": "left"}) == []
    assert adapter.feed({"type": "pressed", "device": "mouse", "button": "left"}) == [{"type": "action", "action": "activate", "device_alias": "mouse"}]
    assert adapter.feed({"type": "pressed", "device": "mouse", "button": "left"}) == []


def test_direct_smoke_entrypoint_is_not_shadowed_by_legacy_script():
    script = Path(__file__).resolve().parents[1] / "scripts/smoke_intact_reuse_mcp.py"
    result = subprocess.run([sys.executable, "-I", str(script), "--help"], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "--output" in result.stdout
