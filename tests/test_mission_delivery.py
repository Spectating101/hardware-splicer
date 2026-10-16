"""A READY mission delivers one package a person can build from, and stages its design for a person's review.

READY_FOR_HUMAN_BUILD says HS's software checks support the candidate. The package is what the person gets: the
accepted intake, the design, the firmware and enclosure HS can generate, every software check it recorded, and the
physical checks that remain. A deliverable HS cannot generate is named as blocked, never faked. Nothing in the
package claims physical truth.

Staging turns the mission's final candidate, with the chain of repairs that produced it, into a staged project
review. A review is not a revision: only a person's decision on that review promotes it, through the existing review
workflow. The mission never decides it.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.device_plan import example_specs
from hardware_splicer.mission_delivery import build_mission_package, read_mission_package, stage_mission_design
from hardware_splicer.mission_runner import run_mission
from hardware_splicer.mission_store import MissionStateError, MissionStore
from hardware_splicer.operator_identity import hash_operator_token
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_review_store import ProjectReviewStore
from hardware_splicer.project_store import ProjectStore

AGENT = {"kind": "agent", "id": "mission-runner"}
HUMAN = {"kind": "human", "id": "bench-lead"}
FORBIDDEN_STATUSES = {"validated", "verified", "approved", "passed_physical", "safe"}


def _snapshot():
    return {"projectId": "monitor", "projectName": "Field monitor", "currentStage": "design", "mode": "greenfield",
            "graph": {"nodes": [], "edges": []},
            "machineProject": {"project_id": "monitor", "name": "Field monitor", "purpose": "monitor"}}


def _missing_sda():
    spec = copy.deepcopy(example_specs()["esp32_oled_bme280_usb"])
    spec["connections"] = [c for c in spec["connections"] if c["from"] != "sensor.SDI"]
    return spec


def _mission(tmp_path: Path, inventory, starting_spec=None, run=True):
    projects = ProjectStore(tmp_path)
    projects.save("monitor", _snapshot(), expected_revision=0)
    missions = MissionStore(projects)
    mission = missions.open_mission("monitor", intake={"goal": "A sensor device from my parts", "inventory": inventory},
                                    author=AGENT)
    missions.accept_mission("monitor", mission["mission_id"], author=HUMAN)
    view = run_mission(missions, "monitor", mission["mission_id"], author=AGENT, starting_spec=starting_spec) if run else None
    return projects, missions, mission["mission_id"], view


def _zip(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_only_a_ready_mission_has_a_package(tmp_path):
    _projects, missions, mid, view = _mission(tmp_path, ["ESP32", "BME280", "HC-SR04 ultrasonic"])
    assert view["terminal"]["state"] == "BLOCKED_NEEDS_PART_DATA"
    with pytest.raises(MissionStateError, match="READY_FOR_HUMAN_BUILD"):
        build_mission_package(missions, "monitor", mid)
    _projects, missions, mid, _ = _mission(tmp_path / "open", ["ESP32", "BME280", "OLED"], run=False)
    with pytest.raises(MissionStateError, match="READY_FOR_HUMAN_BUILD"):
        build_mission_package(missions, "monitor", mid)


def test_the_package_is_deterministic_and_content_addressed(tmp_path):
    _projects, missions, mid, view = _mission(tmp_path, ["ESP32", "BME280", "OLED"])
    assert view["terminal"]["state"] == "READY_FOR_HUMAN_BUILD"
    first = build_mission_package(missions, "monitor", mid)
    second = build_mission_package(missions, "monitor", mid)
    assert first == second
    data = read_mission_package(missions, "monitor", mid)
    assert hashlib.sha256(data).hexdigest() == first["package_sha256"]
    stored = list((tmp_path / "monitor" / "missions" / mid / "packages").glob("*.zip"))
    assert [p.name for p in stored] == [f"{first['package_sha256'][:16]}.zip"]


def test_the_package_holds_the_intake_design_deliverables_checks_and_provenance(tmp_path):
    _projects, missions, mid, view = _mission(tmp_path, ["ESP32", "BME280", "OLED"])
    manifest = build_mission_package(missions, "monitor", mid)
    files = _zip(read_mission_package(missions, "monitor", mid))
    for required in ("MISSION_PACKAGE.json", "01_requirements/intake.json", "01_requirements/inventory_read.json",
                     "02_design/spec.json", "02_design/plan.json", "02_design/engineering.json",
                     "05_validation/software_checks.json", "05_validation/physical_checks_required.md",
                     "06_provenance/events.jsonl"):
        assert required in files, required
    assert any(name.startswith("03_firmware/") for name in files)
    assert any(name.startswith("04_enclosure/") for name in files)
    # The manifest inside the zip is the manifest returned, and it hashes every other file.
    assert json.loads(files["MISSION_PACKAGE.json"]) == {k: v for k, v in manifest.items() if k != "package_sha256"}
    for name, entry in manifest["files"].items():
        assert hashlib.sha256(files[name]).hexdigest() == entry["sha256"], name
    assert set(manifest["files"]) == set(files) - {"MISSION_PACKAGE.json"}
    candidate = next(c for c in view["candidates"] if c["id"] == view["terminal"]["candidate_id"])
    assert json.loads(files["02_design/spec.json"]) == candidate["spec"]
    # The design files are HS's own recorded run outputs for the evaluations READY rests on.
    plan_eval = [e for e in candidate["evaluations"] if e["operation"] == "device_plan"][-1]
    assert hashlib.sha256(files["02_design/plan.json"]).hexdigest() == plan_eval["result"]["result_sha256"]
    assert manifest["mission_id"] == mid and manifest["candidate_id"] == candidate["id"]


def test_the_package_never_claims_physical_truth(tmp_path):
    _projects, missions, mid, _ = _mission(tmp_path, ["ESP32", "BME280", "OLED"])
    manifest = build_mission_package(missions, "monitor", mid)
    assert manifest["physical_correctness"] == "UNPROVEN"
    assert manifest["firmware_authorized"] is False and manifest["power_on_authorized"] is False
    assert manifest["deliverables"]["physical"]["status"] == "required"
    assert manifest["deliverables"]["physical"]["checks"]
    statuses = {d["status"] for d in manifest["deliverables"].values()}
    assert not statuses & FORBIDDEN_STATUSES


def test_a_deliverable_hs_cannot_generate_is_named_as_blocked_not_faked(tmp_path):
    # The application source supports one sensor breakout; this device has two (BH1750 and DS3231).
    _projects, missions, mid, view = _mission(tmp_path, ["Raspberry Pi Pico", "BH1750", "DS3231", "OLED"])
    assert view["terminal"]["state"] == "READY_FOR_HUMAN_BUILD"
    manifest = build_mission_package(missions, "monitor", mid)
    firmware = manifest["deliverables"]["firmware"]
    assert firmware["status"] == "blocked" and "sensor" in firmware["reason"]
    files = _zip(read_mission_package(missions, "monitor", mid))
    assert [name for name in files if name.startswith("03_firmware/")] == ["03_firmware/BLOCKED.md"]
    assert manifest["deliverables"]["enclosure"]["status"] == "generated"


def test_firmware_testing_is_reported_from_recorded_runs_only(tmp_path):
    _projects, missions, mid, _ = _mission(tmp_path, ["ESP32", "BME280", "OLED"])
    manifest = build_mission_package(missions, "monitor", mid)
    # The runner never asked HS for an off-hardware run, so nothing was tested and the package says so.
    assert manifest["deliverables"]["firmware_test"]["status"] == "not_run"


def test_staging_opens_a_review_and_promotes_nothing(tmp_path):
    projects, missions, mid, view = _mission(tmp_path, ["ESP32", "BME280", "OLED"])
    revision_before = projects.load_latest_with_recovery("monitor")["revision"]
    staged = stage_mission_design(missions, "monitor", mid, author=AGENT)
    assert projects.load_latest_with_recovery("monitor")["revision"] == revision_before
    review = ProjectReviewStore(projects).get("monitor", staged["review_id"])
    assert review["status"] == "pending"
    design = review["candidate_snapshot"]["deviceDesigns"][mid]
    candidate = next(c for c in view["candidates"] if c["id"] == view["terminal"]["candidate_id"])
    assert design["spec"] == candidate["spec"]
    assert design["package_sha256"] == build_mission_package(missions, "monitor", mid)["package_sha256"]
    assert design["physical_correctness"] == "UNPROVEN"
    assert any(flag["severity"] == "required" for flag in review["review_flags"])
    # Staging is recorded on the mission by HS, and staging again returns the same review.
    events = missions.get_mission("monitor", mid)["events"]
    assert events[-1]["type"] == "design_staged" and events[-1]["review_id"] == staged["review_id"]
    assert events[-1]["author"] == {"kind": "system", "id": "hardware-splicer"}
    assert stage_mission_design(missions, "monitor", mid, author=AGENT)["review_id"] == staged["review_id"]
    assert len(ProjectReviewStore(projects).list("monitor")) == 1


def test_a_staged_design_carries_the_repair_chain_that_produced_it(tmp_path):
    projects, missions, mid, view = _mission(tmp_path, ["ESP32", "BME280", "OLED"], starting_spec=_missing_sda())
    assert view["terminal"]["state"] == "READY_FOR_HUMAN_BUILD"
    staged = stage_mission_design(missions, "monitor", mid, author=AGENT)
    design = ProjectReviewStore(projects).get("monitor", staged["review_id"])["candidate_snapshot"]["deviceDesigns"][mid]
    assert len(design["repairs"]) == 1
    repair = design["repairs"][0]
    assert repair["rationale"] and len(repair["spec_sha256"]) == 64
    motivating = next(e for e in missions.get_mission("monitor", mid)["events"] if e["seq"] == repair["after_evaluation_seq"])
    assert motivating["type"] == "evaluation_recorded" and motivating["operation"] == "device_plan"
    assert motivating["result"]["errors"] > 0


PERSON_TOKEN = "person-token-" + "a" * 48
BASE = "/v1/projects/monitor/missions"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OPERATOR_TOKENS",
                       '{"%s": {"id": "bench-lead", "kind": "human"}}' % hash_operator_token(PERSON_TOKEN))
    store = ProjectStore(tmp_path)
    store.save("monitor", _snapshot(), expected_revision=0)
    return TestClient(create_product_app(store))


def _ready_over_http(client):
    mid = client.post(BASE, json={"intake": {"goal": "g", "inventory": ["ESP32", "BME280", "OLED"]}, "author": AGENT}).json()["mission"]["mission_id"]
    client.post(f"{BASE}/{mid}/accept", headers={"X-HS-Operator-Token": PERSON_TOKEN})
    seq = client.get(f"{BASE}/{mid}").json()["mission"]["last_event_seq"]
    client.post(f"{BASE}/{mid}/events", json={"event": {"type": "candidate_proposed", "candidate": {
        "id": "A", "kind": "clean_sheet", "label": "A", "spec": example_specs()["esp32_oled_bme280_usb"], "rationale": "r"}},
        "author": AGENT, "expected_event_seq": seq})
    for operation in ("device_plan", "device_engineering"):
        assert client.post(f"{BASE}/{mid}/candidates/A/run", json={"operation": operation}).status_code == 200
    return mid


def test_the_package_and_staging_routes(client):
    mid = _ready_over_http(client)
    assert client.post(f"{BASE}/{mid}/package").status_code == 409  # not READY yet
    assert client.post(f"{BASE}/{mid}/stage", json={"author": AGENT}).status_code == 409
    seq = client.get(f"{BASE}/{mid}").json()["mission"]["last_event_seq"]
    done = client.post(f"{BASE}/{mid}/events", json={"event": {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD",
                                                                "candidate_id": "A", "reason": "checks"},
                                                      "author": AGENT, "expected_event_seq": seq})
    assert done.status_code == 201, done.text
    manifest = client.post(f"{BASE}/{mid}/package").json()["package"]
    download = client.get(f"{BASE}/{mid}/package")
    assert download.status_code == 200 and download.headers["content-type"] == "application/zip"
    assert hashlib.sha256(download.content).hexdigest() == manifest["package_sha256"]
    staged = client.post(f"{BASE}/{mid}/stage", json={"author": AGENT})
    assert staged.status_code == 201 and staged.json()["review_id"].startswith("review-")
    # No mission route decides a review: promotion stays the person's review decision.
    paths = set(client.app.openapi()["paths"])
    assert not any("/missions" in path and ("decide" in path or "decision" in path or path.endswith("/accept-review")) for path in paths)


def test_the_mission_task_offers_delivery_but_never_a_review_decision():
    from hardware_splicer.mcp_backend_gateway import task_operation_manifest

    offered = {(op["method"], op["path"]) for op in task_operation_manifest("fabrication_mission", create_product_app())["operations"]}
    assert ("POST", "/v1/projects/{project_id}/missions/{mission_id}/package") in offered
    assert ("POST", "/v1/projects/{project_id}/missions/{mission_id}/stage") in offered
    assert not any("/reviews" in path or path.endswith("/accept") for _method, path in offered)


def test_hardware_splicer_cannot_be_named_as_the_stager(tmp_path):
    from hardware_splicer.mission_store import MissionValidationError

    _projects, missions, mid, _ = _mission(tmp_path, ["ESP32", "BME280", "OLED"])
    with pytest.raises(MissionValidationError):
        stage_mission_design(missions, "monitor", mid, author={"kind": "system", "id": "hardware-splicer"})
