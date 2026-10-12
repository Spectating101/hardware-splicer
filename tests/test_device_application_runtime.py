import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hardware_splicer import device_application_runtime as runtime
from hardware_splicer.device_application import build_device_application
from hardware_splicer.device_plan import DevicePlanError, example_specs
from hardware_splicer.product_api import create_product_app

SPEC = example_specs()["esp32_oled_bme280_usb"]


def test_real_core_execution_is_bound_to_the_exact_package_and_stays_partial_without_vendor_libraries(monkeypatch):
    monkeypatch.setenv("HS_DEVICE_RUNTIME_ENABLED", "1")
    monkeypatch.delenv("HS_DEVICE_RUNTIME_VENDOR_LIBS", raising=False)
    result = runtime.run_device_application(SPEC)
    _, package = build_device_application(SPEC)
    assert result["proposal_sha256"] == hashlib.sha256(package).hexdigest()
    assert result["status"] == "PARTIAL" and result["vendor_host"]["status"] == "NOT_RUN"
    assert len(result["host"]["scenarios"]) == 15 and result["host"]["pass"] is True
    traces = {row["scenario"]: row["modeled_serial"] for row in result["host"]["scenarios"]}
    assert any("TEMP_C=21.50" in line for line in traces["boot_ok"])
    assert any("FAULT_SENSOR_MISSING" in line for line in traces["sensor_missing_at_boot"])
    assert "RECOVERED" in traces["sensor_missing_at_boot"]
    assert result["esp32_compilation"] == "NOT_RUN" and result["physical_correctness"] == "UNPROVEN"
    assert result["firmware_authorized"] is False and result["power_on_authorized"] is False


def test_disabled_busy_bad_spec_and_bad_vendor_configuration_launch_no_compiler(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "_run_host", lambda _: pytest.fail("compiler must not run"))
    monkeypatch.delenv("HS_DEVICE_RUNTIME_ENABLED", raising=False)
    with pytest.raises(runtime.DeviceRuntimeError, match="disabled"):
        runtime.run_device_application(SPEC)
    monkeypatch.setenv("HS_DEVICE_RUNTIME_ENABLED", "1")
    runtime._RUN_SLOT.acquire()
    try:
        with pytest.raises(runtime.DeviceRuntimeError) as caught:
            runtime.run_device_application(SPEC)
        assert caught.value.status_code == 429
    finally:
        runtime._RUN_SLOT.release()
    with pytest.raises(DevicePlanError):
        runtime.run_device_application({"modules": []})
    monkeypatch.setenv("HS_DEVICE_RUNTIME_VENDOR_LIBS", str(tmp_path))
    with pytest.raises(runtime.DeviceRuntimeError, match="pinned"):
        runtime.run_device_application(SPEC)
    assert runtime._RUN_SLOT.acquire(blocking=False)
    runtime._RUN_SLOT.release()


def test_failures_do_not_become_partial_success_and_temporary_files_are_removed(monkeypatch):
    monkeypatch.setenv("HS_DEVICE_RUNTIME_ENABLED", "1")
    monkeypatch.delenv("HS_DEVICE_RUNTIME_VENDOR_LIBS", raising=False)
    paths = []
    def fail(project):
        paths.append(project)
        return {"pass": False, "reason": "scenario failure", "scenarios": []}, b"failed"
    monkeypatch.setattr(runtime, "_run_host", fail)
    result = runtime.run_device_application(SPEC)
    assert result["status"] == "FAILED"
    assert all(not path.exists() for path in paths)


def test_runtime_http_auth_validation_and_no_project_mutation(monkeypatch, tmp_path):
    monkeypatch.setenv("HARDWARE_SPLICER_PROJECT_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path / "outputs"))
    monkeypatch.setenv("HARDWARE_SPLICER_API_KEY", "fake-test-key-only")
    client = TestClient(create_product_app())
    monkeypatch.setattr(runtime, "_run_host", lambda _: pytest.fail("compiler must not run"))
    assert client.post("/v1/devices/application/run", json={"spec": SPEC}).status_code == 401
    assert client.post("/v1/devices/application/run", json={"spec": SPEC}, headers={"authorization": b"Bearer \xff"}).status_code == 401
    headers = {"authorization": "Bearer fake-test-key-only"}
    for payload in ({"spec": SPEC, "code": "injected"}, {"spec": SPEC, "vendor_libs": "/tmp"}, {"spec": SPEC, "power_on_authorized": True}):
        assert client.post("/v1/devices/application/run", json=payload, headers=headers).status_code == 422
    monkeypatch.delenv("HS_DEVICE_RUNTIME_ENABLED", raising=False)
    assert client.post("/v1/devices/application/run", json={"spec": SPEC}, headers=headers).status_code == 503
    assert not list(tmp_path.rglob("*.json"))


def test_real_vendor_execution_when_server_pinned_libraries_are_available(monkeypatch):
    root = Path(__file__).resolve().parents[1] / ".cache/hardware-splicer/device-application"
    choices = sorted(root.glob("*/project/.pio/libdeps/application"))
    if not choices:
        pytest.skip("pinned vendor libraries not available")
    monkeypatch.setenv("HS_DEVICE_RUNTIME_ENABLED", "1")
    monkeypatch.setenv("HS_DEVICE_RUNTIME_VENDOR_LIBS", str(choices[-1]))
    result = runtime.run_device_application(SPEC)
    assert result["status"] == "PASSED"
    assert len(result["vendor_host"]["scenarios"]) == 11
    assert len(result["vendor_host"]["library_manifest"]) == 5
    assert result["firmware_authorized"] is False and result["power_on_authorized"] is False


def test_remote_execution_requires_auth_and_failure_releases_the_slot(monkeypatch):
    monkeypatch.setenv("HS_DEVICE_RUNTIME_ENABLED", "1")
    monkeypatch.delenv("HARDWARE_SPLICER_API_KEY", raising=False)
    monkeypatch.delenv("CIRCUIT_AI_API_KEY", raising=False)
    monkeypatch.delenv("HS_DEVICE_RUNTIME_VENDOR_LIBS", raising=False)
    client = TestClient(create_product_app(), client=("203.0.113.20", 1234))
    assert client.post("/v1/devices/application/run", json={"spec": SPEC}).status_code == 403
    def broken(_):
        raise OSError("server path must not leak")
    monkeypatch.setattr(runtime, "_run_host", broken)
    with pytest.raises(runtime.DeviceRuntimeError, match="could not complete") as caught:
        runtime.run_device_application(SPEC)
    assert "server path" not in str(caught.value)
    assert runtime._RUN_SLOT.acquire(blocking=False)
    runtime._RUN_SLOT.release()


def test_sensor_only_export_does_not_claim_the_display_vendor_fixture_was_tested(monkeypatch):
    spec = json.loads(json.dumps(SPEC))
    spec["modules"] = [row for row in spec["modules"] if row["id"] != "display"]
    spec["connections"] = [row for row in spec["connections"] if not row["from"].startswith("display.")]
    monkeypatch.setenv("HS_DEVICE_RUNTIME_ENABLED", "1")
    monkeypatch.setenv("HS_DEVICE_RUNTIME_VENDOR_LIBS", "/operator-configured-path")
    monkeypatch.setattr(runtime, "_vendor_manifest", lambda _: {})
    monkeypatch.setattr(runtime, "_run_vendor_host", lambda *_: pytest.fail("display fixture must not run"))
    monkeypatch.setattr(runtime, "_run_host", lambda _: ({"pass": True, "scenarios": []}, b""))
    result = runtime.run_device_application(spec)
    assert result["status"] == "PARTIAL" and result["vendor_host"]["status"] == "NOT_RUN"
    assert "sensor-only adapter was not tested" in result["vendor_host"]["reason"]
