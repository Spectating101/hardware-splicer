"""Catalog diagnostic proposals and compiler-only claims; never physical proof."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.device_api import create_device_router
from hardware_splicer.device_firmware import build_device_firmware
from hardware_splicer.device_plan import DevicePlanError, example_specs


def example():
    return example_specs()["esp32_oled_bme280_usb"]


def test_deterministic_package_binds_inputs_source_and_no_authority():
    spec = example()
    before = copy.deepcopy(spec)
    meta, data = build_device_firmware(spec)
    assert spec == before and data == build_device_firmware(spec)[1]
    assert meta["compilation"] == "NOT_RUN" and meta["observations"] == []
    assert meta["firmware_authorized"] is meta["power_on_authorized"] is False
    assert meta["physical_correctness"] == "UNPROVEN"
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {"src/main.cpp", "platformio.ini", "DEVICE_SPEC.json", "DEVICE_PLAN.json", "README.md", "FIRMWARE_PROPOSAL.json"}
        for name, facts in meta["files"].items():
            content = archive.read(name)
            assert hashlib.sha256(content).hexdigest() == facts["sha256"]
            assert len(content) == facts["size_bytes"]
        code = archive.read("src/main.cpp").decode()
        assert "SDA_PIN = 21;" in code and "SCL_PIN = 22;" in code
        assert "Wire.begin(SDA_PIN, SCL_PIN, BUS_HZ)" in code
        assert "Serial.read() != 's'" in code and "Wire.begin" not in code.split("void loop()")[0]
        assert "0x08; address <= 0x77" in code and "Wire.write" not in code
        assert "NOT observations" in code and "identity and function unverified" in code
        assert b"espressif32@6.10.0" in archive.read("platformio.ini")
    assert {d["module"] for d in meta["declared_devices"]} == {"sensor", "display"}


def test_custom_gpio_bindings_are_derived_not_defaulted():
    spec = example()
    for wire in spec["connections"]:
        wire["to"] = wire["to"].replace("IO21", "IO25").replace("IO22", "IO26")
    meta, data = build_device_firmware(spec)
    assert meta["pins"]["sda"]["gpio"] == 25 and meta["pins"]["scl"]["gpio"] == 26
    assert build_device_firmware(example())[0]["spec_sha256"] != meta["spec_sha256"]
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert b"SDA_PIN = 25;" in archive.read("src/main.cpp")


def test_extra_authority_or_code_fields_neither_promote_nor_inject_source():
    spec = example()
    spec["name"] = 'Name "); Wire.begin(9, 10); //'
    spec["firmware_authorized"] = True
    spec["power_on_authorized"] = True
    spec["extra_scripts"] = "malicious.py"
    meta, data = build_device_firmware(spec)
    assert meta["firmware_authorized"] is meta["power_on_authorized"] is False
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert b"malicious" not in archive.read("platformio.ini")
        assert b"Wire.begin(9, 10)" not in archive.read("src/main.cpp")


def test_reversed_daisy_chained_bus_and_renamed_ids():
    spec = example()
    for wire in spec["connections"]:
        wire["from"], wire["to"] = wire["to"], wire["from"]
        wire["from"] = wire["from"].replace("mcu.", "controller.")
    spec["modules"][0]["id"] = "controller"
    spec["connections"][-2]["from"] = "display.SCL"
    spec["connections"][-1]["from"] = "display.SDA"
    meta, _data = build_device_firmware(spec)
    assert meta["pins"]["sda"]["module"] == "controller"
    assert meta["pins"]["sda"]["gpio"] == 21


@pytest.mark.parametrize("bad", ["mcu.D2", "mcu.IO34", "mcu.5V", "mcu.IO12", "mcu.TX", "mcu.IO0"])
def test_bad_or_warning_wiring_cannot_export(bad):
    spec = example()
    spec["connections"][-1]["to"] = bad
    spec["findings"] = []
    spec["firmware_authorized"] = True
    with pytest.raises(DevicePlanError):
        build_device_firmware(spec)


def test_missing_signal_has_no_gpio_fallback():
    spec = example()
    spec["connections"] = [w for w in spec["connections"] if not w["from"].endswith((".SDA", ".SDI"))]
    with pytest.raises(DevicePlanError):
        build_device_firmware(spec)


def test_separate_peripheral_buses_are_not_silently_merged():
    spec = example()
    spec["connections"][-1]["to"] = "mcu.IO25"
    spec["connections"][-2]["to"] = "mcu.IO26"
    with pytest.raises(DevicePlanError, match="shared I2C bus"):
        build_device_firmware(spec)


def test_address_conflict_keeps_export_closed():
    spec = example()
    spec["modules"].append({"id": "sensor2", "module": "adafruit-bme280-stemma-qt"})
    spec["connections"] += [{**w, "from": w["from"].replace("sensor.", "sensor2.")} for w in spec["connections"] if w["from"].startswith("sensor.")]
    with pytest.raises(DevicePlanError, match="i2c_address_overlap"):
        build_device_firmware(spec)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_extra_fields_are_a_clear_refusal_not_http_500(value):
    spec = example()
    spec["extra"] = value
    with pytest.raises(DevicePlanError, match="finite"):
        build_device_firmware(spec)
    app = FastAPI()
    app.include_router(create_device_router())
    with TestClient(app) as client:
        assert client.post("/v1/devices/firmware", content=json.dumps(spec), headers={"content-type": "application/json"}).status_code == 422


@pytest.mark.parametrize("module,power,clock,data,addresses", [
    ("adafruit-bh1750-stemma-qt", "VIN", "SCL", "SDA", ["0x23", "0x5C"]),
    ("adafruit-ds3231-stemma-qt", "Vin", "SCL", "SDA", ["0x68"]),
])
def test_other_catalog_breakouts_keep_their_own_declared_addresses(module, power, clock, data, addresses):
    spec = example()
    spec["modules"][2]["module"] = module
    for wire in spec["connections"]:
        wire["from"] = wire["from"].replace("sensor.Vin", f"sensor.{power}").replace("sensor.SCK", f"sensor.{clock}").replace("sensor.SDI", f"sensor.{data}")
    meta, _archive = build_device_firmware(spec)
    assert next(d for d in meta["declared_devices"] if d["module"] == "sensor")["possible_addresses"] == addresses


def test_http_returns_bounded_zip_and_recomputes_instead_of_trusting_client():
    app = FastAPI()
    app.include_router(create_device_router())
    with TestClient(app) as client:
        response = client.post("/v1/devices/firmware", json={"spec": example(), "plan": {"firmware_authorized": True}})
        assert response.status_code == 200 and response.headers["content-type"] == "application/zip"
        assert response.headers["cache-control"] == "no-store"
        assert response.content == build_device_firmware(example())[1]
        bad = example()
        bad["connections"][-1]["to"] = "mcu.D2"
        assert client.post("/v1/devices/firmware", json={"spec": bad, "plan": {"findings": []}}).status_code == 422
        assert client.post("/v1/devices/firmware", content=b"x" * 65537).status_code == 413
        assert client.post("/v1/devices/firmware", content=b"not json").status_code == 422


@pytest.mark.parametrize("code,artifacts,version,timeout,passed", [
    (0, True, "6.1.18", False, True), (1, True, "6.1.18", False, False),
    (0, False, "6.1.18", False, False), (0, True, "6.2.0", False, False),
    (0, True, "6.1.18", True, False),
])
def test_compiler_contract_is_bound_and_never_credits_exit_alone(tmp_path, monkeypatch, code, artifacts, version, timeout, passed):
    path = Path(__file__).resolve().parents[1] / "scripts" / "verify_device_firmware.py"
    loader = importlib.util.spec_from_file_location("verify_device_firmware", path)
    mod = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(mod)
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        if "--version" in command:
            return subprocess.CompletedProcess(command, 0, f"PlatformIO Core, version {version}\n".encode(), b"")
        if timeout:
            raise subprocess.TimeoutExpired(command, 10, output=b"partial output")
        if artifacts:
            root = Path(command[command.index("--project-dir") + 1]) / ".pio/build/diagnostic"
            root.mkdir(parents=True)
            (root / "firmware.elf").write_bytes(b"synthetic elf")
            (root / "firmware.bin").write_bytes(b"synthetic bin")
        return subprocess.CompletedProcess(command, code, b"synthetic compiler log")
    monkeypatch.setattr(mod.subprocess, "run", run)
    directory, report = mod.verify(example(), output_root=tmp_path, platformio="test-pio")
    assert report["compile_pass"] is passed
    assert report["firmware_authorized"] is False and report["physical_correctness"] == "UNPROVEN"
    assert all("upload" not in command and "device" not in command for command in commands)
    assert report["proposal_sha256"] == hashlib.sha256((directory / "device-diagnostic-proposal.zip").read_bytes()).hexdigest()
    assert report["compile_log_sha256"] == hashlib.sha256((directory / "compile.log").read_bytes()).hexdigest()
    bundle = directory / "compiled-diagnostic-proposal.zip"
    assert bundle.exists() is passed
    if passed:
        with zipfile.ZipFile(bundle) as archive:
            assert archive.testzip() is None
            assert json.loads(archive.read("COMPILE_RESULT.json")) == report
            assert hashlib.sha256(archive.read("device-diagnostic-proposal.zip")).hexdigest() == report["proposal_sha256"]
