"""Donor application proposals use frozen context; modeled passes are not bench evidence."""
import copy
import hashlib
import io
import json
import os
import zipfile

import pytest

from hardware_splicer.device_application import build_device_application
from hardware_splicer.device_plan import DevicePlanError, example_specs
from hardware_splicer.donor_device_plan import mission_donor_modules
from test_donor_device_plan import _native, _wired
from test_mission_feedback import _store, _candidate, _propose
from test_mission_donors import DONOR, _open


def _fixture(tmp_path, *, pico=False, count=1):
    missions = _store(tmp_path)
    path = _native(missions)
    raw = json.loads(path.read_text())
    raw["signals"][0]["controller_pin"]["value"] = "GP2" if pico else "IO4"
    spec = copy.deepcopy(example_specs()["pico_oled_bme280_usb"]) if pico else _wired()
    if pico:
        spec["donors_used"] = [DONOR]
        spec["modules"].append({"id": "buttons", "module": DONOR})
        spec["connections"] += [{"from": "buttons.KEY", "to": "mcu.GP2"},
                                {"from": "buttons.GND", "to": "mcu.GND"}]
    for index in range(1, count):
        signal = copy.deepcopy(raw["signals"][0])
        signal.update(signal_id=f"KEY{index+1}", contact_id=f"J1.{index+2}")
        pin = f"GP{[2, 3, 6, 7][index]}" if pico else f"IO{15+index}"
        signal["controller_pin"]["value"] = pin
        raw["signals"].append(signal)
        raw["contacts"].append({**raw["contacts"][0], "contact_id": signal["contact_id"]})
        raw["planner_geometry"]["value"]["contacts"].append({"contact_id": signal["contact_id"],
            "x_mm": 2.54 * (index+2), "y_mm": 2.54, "z_mm": 4.6})
        spec["connections"].append({"from": "buttons." + signal["signal_id"], "to": "mcu." + pin})
    path.write_text(json.dumps(raw))
    view = _open(missions)
    return missions, view, spec, mission_donor_modules(view, spec)


def _files(package):
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        assert archive.testzip() is None
        return {name: archive.read(name) for name in archive.namelist()}


@pytest.mark.parametrize("pico", [False, True])
def test_native_application_contains_bound_inputs_and_keeps_library_behavior(tmp_path, pico):
    _, _, spec, context = _fixture(tmp_path, pico=pico)
    before = copy.deepcopy(context)
    metadata, package = build_device_application(spec, donor_modules=context)
    assert context == before
    assert package == build_device_application(spec, donor_modules=context)[1]
    files = _files(package)
    assert metadata["donor_inputs"][0]["gpio"] == (2 if pico else 4)
    assert metadata["donor_inputs"][0]["donor_id"] == DONOR
    assert metadata["donor_inputs"][0]["signal"] == "KEY"
    assert metadata["donor_inputs"][0]["evidence_ids"]
    main = files["src/main.cpp"].decode()
    assert 'hs_donor::begin();' in main and 'hs_donor::tick();' in main
    assert 'g_app->loop_once();' in main and 'sensor_read' in main
    assert b"INPUT_PULLUP" in files["src/donor_inputs.h"]
    assert "proposed" in files["DONOR_INPUTS.json"].decode().lower()
    assert metadata["donor_behaviour_tests"] == "NOT_RUN"
    assert metadata["physical_correctness"] == "UNPROVEN"
    assert not metadata["firmware_authorized"] and not metadata["power_on_authorized"]
    for name, row in metadata["files"].items():
        assert hashlib.sha256(files[name]).hexdigest() == row["sha256"]


@pytest.mark.parametrize("pico,count", [(False, 1), (True, 1), (False, 4), (True, 4)])
def test_real_generated_input_adapter_executes_modeled_scenarios(tmp_path, monkeypatch, pico, count):
    from hardware_splicer.device_application_runtime import run_device_application
    _, _, spec, context = _fixture(tmp_path, pico=pico, count=count)
    monkeypatch.setenv("HS_DEVICE_RUNTIME_ENABLED", "1")
    monkeypatch.delenv("HS_DEVICE_RUNTIME_VENDOR_LIBS", raising=False)
    result = run_device_application(spec, donor_modules=context)
    assert result["host"]["pass"] is True
    phase = result["donor_host"]
    assert phase["status"] == "PASSED" and phase["pass"] is True, phase
    assert len(phase["scenarios"]) == 10
    assert all(row["pass"] is True for row in phase["scenarios"])
    assert phase["output_sha256"] and phase["compiler"]
    assert result["status"] == "PARTIAL" and result["vendor_host"]["status"] == "NOT_RUN"
    assert not result["firmware_authorized"] and not result["power_on_authorized"]
    assert result["physical_correctness"] == "UNPROVEN"


def test_no_context_or_bad_topology_launches_no_input_firmware(tmp_path):
    _, _, spec, context = _fixture(tmp_path)
    with pytest.raises(DevicePlanError):
        build_device_application(spec)
    for target in ["mcu.IO21", "mcu.GND", "mcu.IO16"]:
        bad = copy.deepcopy(spec)
        bad["connections"][-2]["to"] = target
        with pytest.raises(DevicePlanError):
            build_device_application(bad, donor_modules=context)


@pytest.mark.parametrize("vendor_passed", [False, True])
def test_input_failure_cannot_be_reported_as_partial_success(tmp_path, monkeypatch, vendor_passed):
    from hardware_splicer import device_application_runtime as runtime
    _, _, spec, context = _fixture(tmp_path)
    monkeypatch.setenv("HS_DEVICE_RUNTIME_ENABLED", "1")
    monkeypatch.delenv("HS_DEVICE_RUNTIME_VENDOR_LIBS", raising=False)
    if vendor_passed:
        monkeypatch.setenv("HS_DEVICE_RUNTIME_VENDOR_LIBS", str(tmp_path / "mock-vendor-config"))
        monkeypatch.setattr(runtime, "_vendor_manifest", lambda *_: {})
        monkeypatch.setattr(runtime.shutil, "copytree", lambda *_: None)
        monkeypatch.setattr(runtime, "_run_vendor_host", lambda *_: ({"pass": True, "scenarios": []}, b"mock pass"))
    monkeypatch.setattr(runtime, "_run_donor_host", lambda _: ({"pass": False, "scenarios": [], "reason": "input failed"}, b"failed"))
    result = runtime.run_device_application(spec, donor_modules=context)
    assert result["status"] == "FAILED" and result["donor_host"]["status"] == "FAILED"


def test_mission_generates_runs_and_packages_inputs_without_authority(tmp_path, monkeypatch):
    from hardware_splicer.mission_executor import run_mission_operation
    from hardware_splicer.mission_delivery import build_mission_package, read_mission_package
    missions, view, spec, _ = _fixture(tmp_path)
    mid = view["mission_id"]
    _candidate(missions, mid, spec)
    monkeypatch.setenv("HS_DEVICE_RUNTIME_ENABLED", "1")
    monkeypatch.delenv("HS_DEVICE_RUNTIME_VENDOR_LIBS", raising=False)
    for operation in ["device_plan", "device_engineering", "device_application", "device_application_run"]:
        view = run_mission_operation(missions, "monitor", mid, candidate_id="A", operation=operation)
        evaluation = view["candidates"][0]["evaluations"][-1]
        assert evaluation["result"]["errors"] == 0, evaluation
        if operation == "device_application_run":
            assert evaluation["result"]["warnings"] == 1  # vendor lane unavailable, not a clean runtime pass
    _propose(missions, mid, {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD", "candidate_id": "A", "reason": "software checks"})
    first = build_mission_package(missions, "monitor", mid)
    assert first["deliverables"]["firmware"]["status"] == "generated"
    assert first["deliverables"]["firmware_test"]["status"] == "modeled_partial"
    assert first["package_sha256"] == build_mission_package(missions, "monitor", mid)["package_sha256"]
    files = _files(read_mission_package(missions, "monitor", mid))
    assert "03_firmware/src/donor_inputs.h" in files
    assert json.loads(files["02_design/donor_scope.json"])["firmware_implemented"] is True
    assert not first["firmware_authorized"] and not first["power_on_authorized"]
    assert missions.project_store.load("monitor")["revision"] == 3


@pytest.mark.parametrize("pico,part", [(False, "bme280"), (True, "bme280"), (False, "bh1750"), (True, "bh1750")])
def test_full_sensor_and_input_adapter_against_pinned_vendor_libraries(tmp_path, monkeypatch, pico, part):
    from hardware_splicer.device_application_runtime import run_device_application
    configured = os.environ.get("HS_VENDOR_LIBS", "").strip()
    if not configured:
        pytest.skip("set HS_VENDOR_LIBS to the pinned vendor library directory")
    _, _, spec, context = _fixture(tmp_path, pico=pico, count=2)
    if part == "bh1750":
        next(m for m in spec["modules"] if m["id"] == "sensor")["module"] = "adafruit-bh1750-stemma-qt"
        for connection in spec["connections"]:
            for end in ("from", "to"):
                connection[end] = connection[end].replace("sensor.SDI", "sensor.SDA").replace("sensor.SCK", "sensor.SCL")
    monkeypatch.setenv("HS_DEVICE_RUNTIME_ENABLED", "1")
    monkeypatch.setenv("HS_DEVICE_RUNTIME_VENDOR_LIBS", configured)
    result = run_device_application(spec, donor_modules=context)
    assert result["status"] == "PASSED", result
    assert result["vendor_host"]["status"] == "PASSED"
    assert result["donor_host"]["status"] == "PASSED"
    assert result["physical_correctness"] == "UNPROVEN"


@pytest.mark.parametrize("mutation", ["wrong_polarity", "wrong_pin", "wrong_mode", "broken_rollover"])
def test_input_harness_catches_seeded_adapter_defects(tmp_path, mutation):
    from hardware_splicer.device_application_execution import _run_donor_host
    _, _, spec, context = _fixture(tmp_path / "state")
    _, package = build_device_application(spec, donor_modules=context)
    project = tmp_path / "project"
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        archive.extractall(project)
    header = project / "src/donor_inputs.h"
    source = header.read_text()
    old, new = {
        "wrong_polarity": ("== LOW", "== HIGH"),
        "wrong_pin": ("kPins[] = { 4 }", "kPins[] = { 16 }"),
        "wrong_mode": ("pinMode(kPins[i], INPUT_PULLUP)", "pinMode(kPins[i], LOW)"),
        "broken_rollover": ("uint32_t(now - state.changed_ms) >= kDebounceMs", "now >= state.changed_ms + uint64_t(kDebounceMs)"),
    }[mutation]
    assert old in source
    header.write_text(source.replace(old, new))
    report, _ = _run_donor_host(project)
    assert report["pass"] is False, report
    assert report["scenarios"] and any(row["pass"] is False for row in report["scenarios"]), report


def test_public_application_routes_cannot_inject_donor_context(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from hardware_splicer.product_api import create_product_app
    from hardware_splicer import device_application_runtime as runtime
    missions, _, spec, context = _fixture(tmp_path)
    monkeypatch.setattr(runtime, "_run_donor_host", lambda _: pytest.fail("must refuse before compiling"))
    client = TestClient(create_product_app(missions.project_store))
    for route in ("/v1/devices/application", "/v1/devices/application/run"):
        response = client.post(route, json={"spec": {**spec, "donor_modules": context}})
        assert response.status_code == 422, response.text


def test_frozen_input_mapping_survives_source_edits(tmp_path):
    missions, view, spec, context = _fixture(tmp_path)
    before = build_device_application(spec, donor_modules=context)[1]
    path = missions.project_store.root / "monitor/donors/contracts" / (DONOR.replace(":", "__") + ".json")
    raw = json.loads(path.read_text())
    raw["signals"][0]["controller_pin"]["value"] = "IO16"
    path.write_text(json.dumps(raw))
    frozen = mission_donor_modules(missions.get_mission("monitor", view["mission_id"]), spec)
    assert build_device_application(spec, donor_modules=frozen)[1] == before


@pytest.mark.parametrize("problem", ["missing", "duplicate", "false_pass", "finding"])
def test_input_phase_requires_every_scenario_exactly_once(tmp_path, monkeypatch, problem):
    import subprocess
    from hardware_splicer import device_application_execution as execution
    from hardware_splicer.donor_device_application import DONOR_SCENARIOS
    rows = [{"scenario": name, "pass": True} for name in DONOR_SCENARIOS]
    if problem == "missing":
        rows.pop()
    elif problem == "duplicate":
        rows[-1] = rows[0]
    elif problem == "false_pass":
        rows[-1]["pass"] = "true"
    else:
        rows[-1]["finding"] = True
    def execute(command, **_):
        data = b"test compiler\n" if "--version" in command else (
            b"\n".join(json.dumps(row).encode() for row in rows) if command == [str(tmp_path / "donor_harness")] else b"")
        return subprocess.CompletedProcess(command, 0, data, b"")
    monkeypatch.setattr(execution, "_execute", execute)
    monkeypatch.setattr(execution.shutil, "which", lambda _: "/test/g++")
    report, _ = execution._run_donor_host(tmp_path)
    assert report["pass"] is False
    assert report["schema_version"] == "hardware_splicer.donor_input_behaviour.v1"


def test_mission_counts_a_failed_donor_scenario_even_with_other_phases_passed(tmp_path, monkeypatch):
    from hardware_splicer import mission_executor as executor
    missions, view, spec, _ = _fixture(tmp_path)
    mid = view["mission_id"]
    _candidate(missions, mid, spec)
    monkeypatch.setattr(executor, "run_device_application", lambda *_args, **_kwargs: {
        "status": "FAILED", "host": {"scenarios": [{"pass": True}]},
        "vendor_host": {"status": "PASSED", "scenarios": [{"pass": True}]},
        "donor_host": {"status": "FAILED", "scenarios": [{"pass": False}]}})
    view = executor.run_mission_operation(missions, "monitor", mid, candidate_id="A", operation="device_application_run")
    assert view["candidates"][0]["evaluations"][-1]["result"]["errors"] == 1
