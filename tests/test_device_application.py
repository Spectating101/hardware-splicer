"""Host-testable application proposals. They report and propose; they never authorize physical use."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from hardware_splicer.device_application import build_device_application
from hardware_splicer.device_firmware import build_device_firmware
from hardware_splicer.device_plan import DevicePlanError, example_specs

PACKAGE_MEMBERS = {
    "src/app_core.h",
    "src/part_traits.h",
    "src/main.cpp",
    "platformio.ini",
    "test/host/harness.cpp",
    "test/host/part_fixtures.h",
    "test/host/README.md",
    "PART_DESCRIPTOR.json",
    "test/vendor_host/Arduino.h",
    "test/vendor_host/Print.h",
    "test/vendor_host/SPI.h",
    "test/vendor_host/Stream.h",
    "test/vendor_host/WString.h",
    "test/vendor_host/Wire.cpp",
    "test/vendor_host/Wire.h",
    "test/vendor_host/arduino_core.cpp",
    "test/vendor_host/models.cpp",
    "test/vendor_host/models.h",
    "test/vendor_host/pgmspace.h",
    "test/vendor_host/ssd1306_model.cpp",
    "test/vendor_host/ssd1306_model.h",
    "test/vendor_host/vendor_common.h",
    "test/vendor_host/README.md",
    "test/vendor_host/vendor_harness.cpp",
    "DEVICE_SPEC.json",
    "DEVICE_PLAN.json",
    "FIRMWARE_PROPOSAL.json",
    "README.md",
}

# Frozen before the I2C helper extract. The diagnostic ZIP must stay byte-identical.
# The diagnostic zip for the example spec. It changed once, deliberately, when the case began to meet Espressif's 15 mm antenna
# clearance and gained two board stops (the previous value was e26a56bc...). The ESP32 plans themselves are still pinned to their
# original bytes, under the options that restore the old case, in test_device_controllers.py.
DIAGNOSTIC_EXAMPLE_ZIP_SHA256 = "f9d5eefe75453894827ef7f4bc2cc8728fe05b57f4b92d90c088a8ef7a6419b1"

SCENARIOS = (
    "boot_ok",
    "default_address_binding",
    "sensor_missing_at_boot",
    "display_missing",
    "display_at_second_address",
    "transient_read_failure",
    "read_fault_persistent_recovery",
    "ambiguous_during_read_fault",
    "second_read_fault_starts_at_one_second",
    "implausible_values",
    "clock_wrap",
    "read_period",
    "two_devices_answer",
    "first_read_fails",
    "serial_grammar",
)

# Each mutation is a single textual change that a correct harness must reject.
MUTATIONS = (
    ("fail_threshold_3_to_1", "kReadFailThreshold = 3", "kReadFailThreshold = 1"),
    (
        "drop_range_check",
        "if (reading.temp_c < kTempMinC || reading.temp_c > kTempMaxC) return false;",
        "",
    ),
    (
        "drop_nan_check",
        "if (std::isnan(reading.temp_c) || std::isnan(reading.hum_pct) || std::isnan(reading.pres_hpa)) return false;",
        "",
    ),
    (
        "break_wrap_safe_subtraction",
        "const uint32_t elapsed = now - then;",
        "const uint32_t elapsed = (now >= then) ? (now - then) : 0;",
    ),
    (
        "log_display_missing_every_cycle",
        "if (display_declared_ && !display_ok_ && !display_missing_logged_)",
        "if (display_declared_ && !display_ok_)",
    ),
    (
        "pick_first_address_without_identity",
        "if (hal_.sensor_begin(addr)) { // identity must match; do not pick the first address",
        "if (true) { // identity must match; do not pick the first address",
    ),
    (
        "remove_backoff_cap",
        "                    take_reading(now);\n                    return;\n                }\n                backoff_ms_ *= 2;\n                if (backoff_ms_ > kBackoffCapMs) backoff_ms_ = kBackoffCapMs;",
        "                    take_reading(now);\n                    return;\n                }\n                backoff_ms_ *= 2;",
    ),
    (
        "skip_rebind_after_probe",
        "if (!hal_.sensor_begin(found)) return 0;",
        "",
    ),
    (
        "no_retry_in_read_fault",
        "if (state_ == AppState::FAULT_SENSOR_READ) {",
        "if (false && state_ == AppState::FAULT_SENSOR_READ) {",
    ),
    ("read_period_2000_to_200", "kReadPeriodMs = 2000", "kReadPeriodMs = 200"),
    ("pressure_max_1100_to_1200", "kPresMaxHpa = 1100.0f", "kPresMaxHpa = 1200.0f"),
    ("temp_min_-40_to_-50", "kTempMinC = -40.0f", "kTempMinC = -50.0f"),
    ("temp_max_85_to_90", "kTempMaxC = 85.0f", "kTempMaxC = 90.0f"),
    ("hum_min_0_to_-1", "kHumMinPct = 0.0f", "kHumMinPct = -1.0f"),
    ("hum_max_100_to_101", "kHumMaxPct = 100.0f", "kHumMaxPct = 101.0f"),
    ("pres_min_300_to_299", "kPresMinHpa = 300.0f", "kPresMinHpa = 299.0f"),
    (
        "nan_only_temp",
        "if (std::isnan(reading.temp_c) || std::isnan(reading.hum_pct) || std::isnan(reading.pres_hpa)) return false;",
        "if (std::isnan(reading.temp_c)) return false;",
    ),
    (
        "read_fault_retry_ignores_ambiguity",
        "                (void)hal_.bus_recover();\n                const int hits = probe_sensor();\n                if (hits > 1) {\n                    enter_fault(now, AppState::FAULT_AMBIGUOUS_ADDRESS, \"AMBIGUOUS ADDR\");\n                    return;\n                }\n                if (hits == 1) {\n                    take_reading(now);",
        "                (void)hal_.bus_recover();\n                const int hits = probe_sensor();\n                if (false && hits > 1) {\n                    enter_fault(now, AppState::FAULT_AMBIGUOUS_ADDRESS, \"AMBIGUOUS ADDR\");\n                    return;\n                }\n                if (hits >= 1) {\n                    take_reading(now);",
    ),
    (
        "ambiguous_state_retries",
        "        if (state_ == AppState::FAULT_AMBIGUOUS_ADDRESS) {\n            return;\n        }",
        "",
    ),
    (
        "display_probe_only_first_address",
        "for (size_t i = 0; i < n_display_; ++i) {",
        "for (size_t i = 0; i < n_display_ && i < 1; ++i) {",
    ),
    (
        "missing_sensor_backoff_linear_not_doubling",
        '                    take_reading(now);\n                    return;\n                }\n                backoff_ms_ *= 2;',
        '                    take_reading(now);\n                    return;\n                }\n                backoff_ms_ += kBackoffInitialMs;',
    ),
    (
        "read_fault_backoff_linear_not_doubling",
        '                        backoff_ms_ = kBackoffInitialMs;\n                        return;\n                    }\n                }\n                backoff_ms_ *= 2;',
        '                        backoff_ms_ = kBackoffInitialMs;\n                        return;\n                    }\n                }\n                backoff_ms_ += kBackoffInitialMs;',
    ),
)


def example():
    return example_specs()["esp32_oled_bme280_usb"]


def bme280_only():
    spec = example()
    spec["modules"] = [m for m in spec["modules"] if m["id"] != "display"]
    spec["connections"] = [w for w in spec["connections"] if not w["from"].startswith("display.")]
    spec["name"] = "ESP32 with a BME280, powered over USB"
    return spec


def _package(spec=None):
    return build_device_application(spec if spec is not None else example())


def _extract(data: bytes, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        archive.extractall(dest)
    return dest


def _gxx() -> str:
    path = shutil.which("g++")
    if not path:
        pytest.skip("g++ is missing")
    return path


def _compile_and_run(project: Path) -> subprocess.CompletedProcess:
    harness = project / "harness"
    compile_result = subprocess.run(
        [_gxx(), "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", "src", "test/host/harness.cpp", "-o", str(harness)],
        cwd=project,
        capture_output=True,
        text=True,
    )
    if compile_result.returncode != 0:
        return compile_result
    return subprocess.run([str(harness)], cwd=project, capture_output=True, text=True)


def test_package_is_deterministic_and_carries_no_authority():
    spec = example()
    before = copy.deepcopy(spec)
    meta, data = _package(spec)
    assert spec == before
    assert data == _package(spec)[1]
    assert meta["schema_version"] == "hardware_splicer.device_application_proposal.v1"
    assert meta["status"] == "HOST_TESTABLE_PROPOSAL"
    assert meta["compilation"] == "NOT_RUN"
    assert meta["behaviour_tests"] == "NOT_RUN"
    assert meta["firmware_authorized"] is meta["power_on_authorized"] is False
    assert meta["physical_correctness"] == "UNPROVEN"
    assert meta["non_claims"] and all(isinstance(item, str) and item.strip() for item in meta["non_claims"])
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == PACKAGE_MEMBERS
        proposal = json.loads(archive.read("FIRMWARE_PROPOSAL.json"))
        assert proposal["firmware_authorized"] is False
        assert proposal["power_on_authorized"] is False
        assert proposal["status"] == "HOST_TESTABLE_PROPOSAL"
        for name, facts in meta["files"].items():
            content = archive.read(name)
            assert hashlib.sha256(content).hexdigest() == facts["sha256"]
            assert len(content) == facts["size_bytes"]
        core = archive.read("src/app_core.h").decode()
        assert "#include <Arduino.h>" not in core and "#include <Wire.h>" not in core
        assert "Adafruit" not in core
        main = archive.read("src/main.cpp").decode()
        assert "Wire.begin(SDA_PIN, SCL_PIN, 100000)" in main
        assert "SDA_PIN = 21;" in main and "SCL_PIN = 22;" in main
        ini = archive.read("platformio.ini").decode()
        assert "platform = espressif32@6.10.0" in ini
        assert "board = esp32dev" in ini
        assert "framework = arduino" in ini
        assert "monitor_speed = 115200" in ini
        assert "adafruit/Adafruit BME280 Library @ 2.3.0" in ini
        assert "adafruit/Adafruit SSD1306 @ 2.5.17" in ini
        assert "adafruit/Adafruit GFX Library @ 1.12.6" in ini
        assert "adafruit/Adafruit BusIO @ 1.17.4" in ini
        assert "adafruit/Adafruit Unified Sensor @ 1.1.15" in ini
        readme = archive.read("test/host/README.md").decode()
        assert "g++ -std=c++17 -Wall -Wextra -Werror -I src test/host/harness.cpp -o harness && ./harness" in readme
    devices = {d["library_id"]: d for d in meta["declared_devices"]}
    assert devices["adafruit-bme280-stemma-qt"]["possible_addresses"] == ["0x77", "0x76"]
    assert devices["ssd1306-096-i2c"]["possible_addresses"] == ["0x3C", "0x3D"]
    assert all(d["basis"] and d["possible_addresses"] for d in meta["declared_devices"])


def test_bme280_alone_is_a_valid_application():
    meta, data = _package(bme280_only())
    assert {d["library_id"] for d in meta["declared_devices"]} == {"adafruit-bme280-stemma-qt"}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        main = archive.read("src/main.cpp").decode()
        assert "0x77" in main and "0x76" in main
        assert "0x3C" not in main and "0x3D" not in main


def test_gpio_numbers_come_from_the_wiring():
    spec = example()
    for wire in spec["connections"]:
        wire["to"] = wire["to"].replace("IO21", "IO16").replace("IO22", "IO17")
    meta, data = _package(spec)
    assert meta["pins"]["sda"]["gpio"] == 16
    assert meta["pins"]["scl"]["gpio"] == 17
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        main = archive.read("src/main.cpp").decode()
        assert "SDA_PIN = 16;" in main and "SCL_PIN = 17;" in main
        assert "SDA_PIN = 21;" not in main and "SCL_PIN = 22;" not in main


def test_diagnostic_export_for_the_same_spec_stays_byte_identical():
    spec = example()
    _, diagnostic = build_device_firmware(spec)
    assert hashlib.sha256(diagnostic).hexdigest() == DIAGNOSTIC_EXAMPLE_ZIP_SHA256
    _package(spec)
    _, again = build_device_firmware(spec)
    assert again == diagnostic


@pytest.mark.parametrize(
    "mutator,needle",
    [
        (lambda spec: spec["connections"].__setitem__(-1, {**spec["connections"][-1], "to": "mcu.D2"}) or spec, "wiring"),
        (lambda spec: (spec["modules"].__setitem__(0, {**spec["modules"][0], "module": "unknown-board"}), spec)[1], "unknown"),
        (lambda spec: example_specs()["esp32_oled_usb"], "BME280"),
        (
            lambda spec: (
                spec["modules"].append({"id": "sensor2", "module": "adafruit-bme280-stemma-qt"}),
                spec["connections"].__iadd__(
                    [{**w, "from": w["from"].replace("sensor.", "sensor2.")} for w in spec["connections"] if w["from"].startswith("sensor.")]
                ),
                spec,
            )[-1],
            "BME280|overlap",
        ),
        (
            lambda spec: (
                spec["modules"].__setitem__(2, {**spec["modules"][2], "module": "adafruit-ds3231-stemma-qt"}),
                [
                    w.update(
                        {
                            "from": w["from"]
                            .replace("sensor.SCK", "sensor.SCL")
                            .replace("sensor.SDI", "sensor.SDA")
                        }
                    )
                    for w in spec["connections"]
                ],
                spec,
            )[-1],
            "SSD1306",
        ),
        (
            lambda spec: (
                spec["modules"].append({"id": "light", "module": "adafruit-bh1750-stemma-qt"}),
                spec["connections"].__iadd__(
                    [
                        {"from": "light.VIN", "to": "mcu.3V3"},
                        {"from": "light.GND", "to": "mcu.GND"},
                        {"from": "light.SCL", "to": "mcu.IO22"},
                        {"from": "light.SDA", "to": "mcu.IO21"},
                    ]
                ),
                spec,
            )[-1],
            "SSD1306",
        ),
        (
            lambda spec: (
                spec["connections"].__setitem__(-1, {**spec["connections"][-1], "to": "mcu.IO25"}),
                spec["connections"].__setitem__(-2, {**spec["connections"][-2], "to": "mcu.IO26"}),
                spec,
            )[-1],
            "SDA",
        ),
    ],
)
def test_refused_cases_raise_device_plan_error_with_a_message(mutator, needle):
    spec = mutator(example())
    with pytest.raises(DevicePlanError, match=re.compile(needle, re.I)) as caught:
        _package(spec)
    assert str(caught.value).strip()


def test_host_harness_passes_every_named_scenario(tmp_path):
    _meta, data = _package()
    project = _extract(data, tmp_path / "app")
    result = _compile_and_run(project)
    assert result.returncode == 0, result.stdout + result.stderr
    reports = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    names = [row["scenario"] for row in reports]
    assert names == list(SCENARIOS)
    for row in reports:
        assert row["pass"] is True, row


def test_mutations_of_app_core_are_caught_by_the_harness(tmp_path):
    _meta, data = _package()
    original = _extract(data, tmp_path / "original")
    # The engine (app_core.h) and the part's ranges and formats (part_traits.h) are separate generated files.
    sources = {name: (original / "src" / name).read_text(encoding="utf-8") for name in ("app_core.h", "part_traits.h")}
    caught = {}
    for name, old, new in MUTATIONS:
        owners = [file for file, text in sources.items() if text.count(old) == 1]
        assert len(owners) == 1, f"mutation {name} original text must occur exactly once across the generated sources"
        mutated = tmp_path / name
        shutil.copytree(original, mutated)
        (mutated / "src" / owners[0]).write_text(sources[owners[0]].replace(old, new, 1), encoding="utf-8")
        result = _compile_and_run(mutated)
        failed = result.returncode != 0
        if result.returncode == 0:
            reports = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            failed = any(not row["pass"] for row in reports)
        caught[name] = failed
        assert failed, f"mutation {name} did not change host-observable behaviour; replace it"
    assert len(caught) >= 6 and all(caught.values())


def test_hal_sensor_begin_documents_rebind_even_on_false():
    _meta, data = _package()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        core = archive.read("src/app_core.h").decode()
    assert "(re)binds the driver to addr even when it returns false" in core


def test_display_begin_probes_presence_then_skips_library_wire_begin():
    _meta, data = _package()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        main = archive.read("src/main.cpp").decode()
    tx = main.find("Wire.beginTransmission(addr)")
    end = main.find("if (Wire.endTransmission() != 0) return false;")
    begin = main.find("display_.begin(SSD1306_SWITCHCAPVCC, addr, true, false)")
    assert 0 <= tx < end < begin
    assert "Adafruit_SSD1306.cpp" in main
    assert "2.5.17" in main
    assert "return true; // Success" in main


def test_uint32_t_printf_casts_to_unsigned():
    _meta, data = _package()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        core = archive.read("src/app_core.h").decode()
        traits = archive.read("src/part_traits.h").decode()
    assert re.search(r'"T=%u STATE=%s", \(unsigned\)now', core)
    assert re.search(r'"T=%u STATE=OK TEMP_C=%.2f HUM_PCT=%.1f PRES_HPA=%.1f"', traits)
    assert "(unsigned)now" in core and "(unsigned)now" in traits
    assert not re.search(r'"T=%u STATE=%s", now\b', core)
    assert not re.search(r'TEMP_C=%.2f HUM_PCT=%.1f PRES_HPA=%.1f",\s*now\b', traits)


def test_the_http_endpoint_serves_the_same_bytes_and_refuses_unsupported_specs(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from hardware_splicer.product_api import create_product_app
    from hardware_splicer.project_store import ProjectStore

    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    client = TestClient(create_product_app(ProjectStore(tmp_path / "store")))
    _meta, expected = _package()
    ok = client.post("/v1/devices/application", json=example_specs()["esp32_oled_bme280_usb"])
    assert ok.status_code == 200
    assert ok.headers["content-type"] == "application/zip"
    assert "device-application-proposal.zip" in ok.headers["content-disposition"]
    assert ok.content == expected
    wrapped = client.post("/v1/devices/application", json={"spec": example_specs()["esp32_oled_bme280_usb"]})
    assert wrapped.content == expected
    refused = client.post("/v1/devices/application", json=example_specs()["esp32_oled_usb"])
    assert refused.status_code == 422
    assert "BME280" in refused.json()["detail"]["message"]
    assert client.post("/v1/devices/application", content=b"nope").status_code == 422
