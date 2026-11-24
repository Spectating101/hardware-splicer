"""Inspect retained delivery without creating the deliverable being graded."""
import hashlib
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.mission_delivery import build_mission_package
from hardware_splicer.mission_runner import run_mission
from hardware_splicer.product_api import create_product_app
from test_mission_delivery import _mission
from test_intact_reuse import host, propose, run


def _tree(root):
    return {str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in root.rglob("*") if path.is_file()}


def _get(client, mid):
    response = client.get(f"/v1/projects/monitor/missions/{mid}/delivery")
    assert response.status_code == 200, response.text
    return response.json()["delivery"]


def test_inspecting_ready_does_not_build_or_store_a_package(tmp_path, monkeypatch):
    projects, missions, mid, _ = _mission(tmp_path, ["ESP32", "BME280", "OLED"])
    client = TestClient(create_product_app(projects))
    before = _tree(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("Delivery inspection must not generate or store artifacts")

    monkeypatch.setattr("hardware_splicer.mission_delivery.build_mission_package", forbidden)
    monkeypatch.setattr("hardware_splicer.mission_delivery.build_device_application", forbidden)
    monkeypatch.setattr("hardware_splicer.mission_delivery.build_device_case", forbidden)
    monkeypatch.setattr(type(missions), "store_package", forbidden)
    first = _get(client, mid)
    assert _get(client, mid) == first
    assert first["prototype_package"]["status"] == "not_generated"
    assert first["prototype_package"]["build_path"].endswith("/package")
    assert first["prototype_package"]["retained_packages"] == []
    assert first["inspection_generated_artifacts"] is False
    assert first["file_presence_proves_agent_delivery"] is False
    assert first["sale_readiness"] == "NOT_ASSESSED"
    assert any(row["kind"] == "check_result" and row["status"] == "available" for row in first["recorded_files"])
    assert _tree(tmp_path) == before


def test_waiting_mission_still_exposes_available_check_output_without_ready(tmp_path):
    projects, _, mid, _ = _mission(tmp_path, ["ESP32", "BME280", "OLED"], run=False)
    client = TestClient(create_product_app(projects))
    before = _tree(tmp_path)
    result = _get(client, mid)
    assert result["prototype_package"]["status"] == "blocked"
    assert result["prototype_package"]["build_path"] is None
    assert result["recorded_files"] == []
    assert _tree(tmp_path) == before


def test_existing_prototype_package_is_downloaded_without_regeneration(tmp_path, monkeypatch):
    projects, missions, mid, _ = _mission(tmp_path, ["ESP32", "BME280", "OLED"])
    manifest = build_mission_package(missions, "monitor", mid)
    digest = manifest["package_sha256"]
    original = missions.read_package("monitor", mid, digest)
    client = TestClient(create_product_app(projects))
    before = _tree(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("Retained downloads must not call a generator")

    monkeypatch.setattr("hardware_splicer.mission_delivery.build_mission_package", forbidden)
    monkeypatch.setattr(type(missions), "store_package", forbidden)
    result = _get(client, mid)
    assert result["prototype_package"]["status"] == "available"
    row, = result["prototype_package"]["retained_packages"]
    assert row["sha256"] == digest
    assert row["deliverables"] == manifest["deliverables"]
    assert row["producer_attribution"] == "not_recorded"
    response = client.get(row["download_path"])
    assert response.status_code == 200
    assert response.content == original
    assert response.headers["x-content-sha256"] == digest
    assert _tree(tmp_path) == before


def test_readonly_download_does_not_generate_a_missing_package(tmp_path):
    projects, _, mid, _ = _mission(tmp_path, ["ESP32", "BME280", "OLED"])
    client = TestClient(create_product_app(projects))
    before = _tree(tmp_path)
    response = client.get(f"/v1/projects/monitor/missions/{mid}/delivery/packages/" + "a" * 64)
    assert response.status_code == 404
    assert _tree(tmp_path) == before


def test_foreign_package_cannot_be_credited_or_downloaded(tmp_path):
    projects, missions, mid, _ = _mission(tmp_path, ["ESP32", "BME280", "OLED"])
    manifest = build_mission_package(missions, "monitor", mid)
    data = missions.read_package("monitor", mid, manifest["package_sha256"])
    other = missions.open_mission("monitor", intake={"goal": "Different mission", "inventory": ["ESP32", "BME280", "OLED"]},
                                  author={"kind": "agent", "id": "inspection-test"})
    other_id = other["mission_id"]
    actor = {"kind": "agent", "id": "inspection-test"}
    missions.accept_mission("monitor", other_id, author={"kind": "human", "id": "fixture-host"})
    assert run_mission(missions, "monitor", other_id, author=actor)["terminal"]["state"] == "READY_FOR_HUMAN_BUILD"
    digest = missions.store_package("monitor", other_id, data)
    client = TestClient(create_product_app(projects))
    before = _tree(tmp_path)
    result = _get(client, other_id)
    assert result["prototype_package"]["retained_packages"] == []
    response = client.get(f"/v1/projects/monitor/missions/{other_id}/delivery/packages/{digest}")
    assert response.status_code == 404
    assert _tree(tmp_path) == before


def test_self_consistent_zip_with_foreign_spec_is_not_a_current_package(tmp_path):
    projects, missions, mid, _ = _mission(tmp_path, ["ESP32", "BME280", "OLED"])
    manifest = build_mission_package(missions, "monitor", mid)
    original = missions.read_package("monitor", mid, manifest["package_sha256"])
    with zipfile.ZipFile(io.BytesIO(original)) as z:
        files = {name: z.read(name) for name in z.namelist()}
    m = json.loads(files["MISSION_PACKAGE.json"])
    m["spec_sha256"] = "0" * 64
    files["MISSION_PACKAGE.json"] = json.dumps(m).encode()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    digest = missions.store_package("monitor", mid, stream.getvalue())
    client = TestClient(create_product_app(projects))
    result = _get(client, mid)
    assert [p["sha256"] for p in result["prototype_package"]["retained_packages"]] == [manifest["package_sha256"]]
    assert client.get(f"/v1/projects/monitor/missions/{mid}/delivery/packages/{digest}").status_code == 404


def test_intact_software_bundle_is_visible_before_physical_readiness(host):
    store, _, client, prefix, _, _ = host
    propose(host)
    _, report = run(host)
    before = _tree(store.root)
    response = client.get(prefix + "/delivery")
    assert response.status_code == 200, response.text
    result = response.json()["delivery"]
    assert result["prototype_package"]["status"] == "blocked"
    row, = [row for row in result["recorded_files"] if row["kind"] == "software_review_bundle"]
    assert row["status"] == "available" and row["current"] is True
    assert row["scope"] == "SOFTWARE_REVIEW_ONLY"
    assert row["sha256"] == report["package_sha256"]
    download = client.get(row["download_path"])
    assert download.status_code == 200
    assert hashlib.sha256(download.content).hexdigest() == row["sha256"]
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["sale_readiness"] == "NOT_ASSESSED"
    assert _tree(store.root) == before


def test_missing_check_output_is_not_reported_as_available(tmp_path):
    projects, missions, mid, _ = _mission(tmp_path, ["ESP32", "BME280", "OLED"])
    view = missions.get_mission("monitor", mid)
    artifact = view["candidates"][0]["evaluations"][0]["artifact"]
    path = tmp_path / "monitor" / "missions" / mid / artifact
    path.unlink()
    client = TestClient(create_product_app(projects))
    before = _tree(tmp_path)
    result = _get(client, mid)
    row = next(row for row in result["recorded_files"] if row["operation"] == "device_plan")
    assert row["status"] == "unavailable" and row["download_path"] is None
    assert _tree(tmp_path) == before


def test_corrupt_retained_package_cannot_be_credited_or_silently_rebuilt(tmp_path):
    projects, missions, mid, _ = _mission(tmp_path, ["ESP32", "BME280", "OLED"])
    manifest = build_mission_package(missions, "monitor", mid)
    digest = manifest["package_sha256"]
    path = tmp_path / "monitor" / "missions" / mid / "packages" / f"{digest[:16]}.zip"
    path.write_bytes(b"corrupted fixture bytes")
    client = TestClient(create_product_app(projects))
    before = _tree(tmp_path)
    result = _get(client, mid)
    assert result["prototype_package"]["status"] == "unavailable"
    assert result["prototype_package"]["scan_complete"] is False
    response = client.get(f"/v1/projects/monitor/missions/{mid}/delivery/packages/{digest}")
    assert response.status_code == 409
    assert _tree(tmp_path) == before


def test_missing_software_bundle_is_not_listed_as_available(host):
    store, _, client, prefix, mid, _ = host
    propose(host)
    _, report = run(host)
    digest = report["package_sha256"]
    (store.root / "mouse" / "missions" / mid / "packages" / f"{digest[:16]}.zip").unlink()
    before = _tree(store.root)
    result = client.get(prefix + "/delivery").json()["delivery"]
    row, = [item for item in result["recorded_files"] if item["kind"] == "software_review_bundle"]
    assert row["status"] == "unavailable" and row["download_path"] is None
    assert _tree(store.root) == before


def test_orphan_software_zip_does_not_count_as_a_recorded_deliverable(host):
    from hardware_splicer.intact_reuse import build_intact_reuse
    from hardware_splicer.mission_store import MissionStore

    store, _, client, prefix, mid, spec = host
    propose(host)
    view = client.get(prefix).json()["mission"]
    _, data = build_intact_reuse(spec, view=view, project=store.load("mouse"),
                                 candidate_id="mouse_reuse", project_root=store.root)
    MissionStore(store).store_package("mouse", mid, data)
    before = _tree(store.root)
    result = client.get(prefix + "/delivery").json()["delivery"]
    assert result["recorded_files"] == []
    assert result["prototype_package"]["retained_packages"] == []
    assert _tree(store.root) == before


def test_old_software_output_is_explicitly_historical_after_repair(host):
    from hardware_splicer.mission_store import MissionStore

    store, _, client, prefix, mid, spec = host
    propose(host)
    run(host)
    missions = MissionStore(store)
    # Internal fault control: an actual failing recorded result permits repair;
    # the agent cannot manufacture an evaluation through its public tools.
    missions.record_evaluation("mouse", mid, candidate_id="mouse_reuse", operation="intact_reuse",
        result={"errors": 1, "warnings": 0, "summary": "Synthetic failing control", "result_sha256": "0" * 64})
    repaired = {**spec, "interface": {**spec["interface"], "action": "different_action"}}
    response = client.post(prefix + "/events", json={"author": {"kind": "agent", "id": "inspection-test"},
        "event": {"type": "repair_proposed", "candidate_id": "mouse_reuse", "spec": repaired,
                  "rationale": "Explicitly distinguish old output from the revised proposal."}})
    assert response.status_code == 201, response.text
    before = _tree(store.root)
    result = client.get(prefix + "/delivery").json()["delivery"]
    row, = [item for item in result["recorded_files"] if item["kind"] == "software_review_bundle"]
    assert row["current"] is False and row["status"] == "available"
    assert _tree(store.root) == before


def test_inspection_operations_are_discoverable_and_non_mutating():
    from hardware_splicer.salvage_fabrication_manifest import salvage_fabrication_manifest

    rows = salvage_fabrication_manifest()["operations"]
    paths = {row["path"]: row for row in rows}
    for suffix in ("/delivery", "/delivery/packages/{package_sha256}"):
        row = next(value for path, value in paths.items() if path.endswith(suffix))
        assert row["method"] == "GET" and row["mutation"] is False
