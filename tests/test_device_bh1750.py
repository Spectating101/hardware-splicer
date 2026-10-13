"""The BH1750 application: a second part generated from its descriptor with no change to the fault scenarios."""
import copy
import hashlib
import io
import shutil
import zipfile

import pytest

from hardware_splicer.device_application import build_device_application
from hardware_splicer.device_parts import (
    PartDescriptorError, available_parts, example_spec_for_part, load_part, render_fixtures, validate_part,
)
from hardware_splicer.device_plan import DevicePlanError, example_specs

BME280 = "adafruit-bme280-stemma-qt"
BH1750 = "adafruit-bh1750-stemma-qt"


def bh1750_spec():
    return example_spec_for_part(BH1750)


def extract(data, directory):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        archive.extractall(directory)
    return directory


def test_the_bh1750_descriptor_states_that_the_part_cannot_identify_itself_and_cites_its_pages():
    part = load_part(BH1750)
    assert part["identity"] is None and part["identity_note"]
    assert all(fact["page"] >= 1 for fact in part["datasheet"]["facts"])
    assert "static constexpr bool kHasIdentity = false;" in render_fixtures(part)
    unexplained = copy.deepcopy(part)
    unexplained.pop("identity_note")
    with pytest.raises(PartDescriptorError):
        validate_part(unexplained)


def test_the_two_names_of_a_channel_may_coincide():
    single = load_part(BH1750)["channels"][0]
    assert single["short"] == single["field"]  # allowed: different namespaces


def test_the_bh1750_application_is_generated_with_its_limits_stated():
    meta, data = build_device_application(bh1750_spec())
    assert meta["part"]["chip"] == "BH1750"
    assert meta["part"]["identity_check"] is False
    assert meta["part"]["vendor_host_supported"] is True and meta["part"]["vendor_profile"] == "bh1750"
    assert meta["part"]["review_status"] == "UNREVIEWED_EXTRACT"
    assert meta["physical_correctness"] == "UNPROVEN"
    assert meta["firmware_authorized"] is False and meta["power_on_authorized"] is False
    assert any("no ID register" in claim for claim in meta["non_claims"])
    assert not any("No vendor-host lane" in claim for claim in meta["non_claims"])
    assert any("does not model L-resolution quantisation" in claim for claim in meta["non_claims"])
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
        # The BH1750's lane ships its own bus model and harness, and none of the BME280's.
        assert {"test/vendor_host/models_bh1750.cpp", "test/vendor_host/vendor_harness_bh1750.cpp"} <= names
        assert not names & {"test/vendor_host/models.cpp", "test/vendor_host/models.h", "test/vendor_host/vendor_harness.cpp"}
        assert {"src/part_traits.h", "test/host/part_fixtures.h", "PART_DESCRIPTOR.json"} <= names
        assert hashlib.sha256(archive.read("PART_DESCRIPTOR.json")).hexdigest() == meta["part"]["descriptor_sha256"]
        ini = archive.read("platformio.ini").decode()
        main = archive.read("src/main.cpp").decode()
    assert "BME280" not in ini and "Unified Sensor" not in ini and "BH1750" not in ini
    # The stock library prints error lines to Serial that the documented grammar does not allow.
    assert "#include <BH1750.h>" not in main and "BH1750::" not in main
    assert "Serial.print" not in main.replace("Serial.println(line)", "")  # only the application's own log line
    assert "SDA_PIN = 21;" in main and "kSensorAddrs[] = { 0x23, 0x5C }" in main


def test_a_bme280_package_is_unchanged_in_kind_and_still_has_its_vendor_lane():
    meta, data = build_device_application(example_specs()["esp32_oled_bme280_usb"])
    assert meta["part"]["chip"] == "BME280" and meta["part"]["vendor_host_supported"] is True
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
        assert "test/vendor_host/vendor_harness.cpp" in names
        assert not any("bh1750" in name for name in names if name.startswith("test/vendor_host/"))
        assert "adafruit/Adafruit BME280 Library @ 2.3.0" in archive.read("platformio.ini").decode()


def test_a_descriptor_whose_addresses_disagree_with_the_catalogue_is_not_exported(monkeypatch):
    import hardware_splicer.device_application as module

    parts = copy.deepcopy(available_parts())
    parts[BH1750]["addresses"] = ["0x5C", "0x23"]
    monkeypatch.setattr(module, "available_parts", lambda: parts)
    with pytest.raises(DevicePlanError, match="disagree with the catalog"):
        module.build_device_application(bh1750_spec())


@pytest.mark.skipif(shutil.which("g++") is None, reason="needs a host compiler")
def test_the_bh1750_host_harness_passes_every_named_scenario_with_no_battery_edits(tmp_path):
    from hardware_splicer.device_application_execution import HOST_SCENARIOS, _run_host

    _meta, data = build_device_application(bh1750_spec())
    report, _log = _run_host(extract(data, tmp_path / "app"))
    assert report["pass"] is True, report["reason"]
    assert [row["scenario"] for row in report["scenarios"]] == list(HOST_SCENARIOS)
    boot = next(row for row in report["scenarios"] if row["scenario"] == "boot_ok")
    assert boot["modeled_serial"] == ["BOOT sensor=0x5C display=0x3C", "T=0 STATE=OK LUX=320.0"]


@pytest.mark.skipif(shutil.which("g++") is None, reason="needs a host compiler")
def test_the_runtime_reports_a_bh1750_run_as_partial_without_vendor_libraries(monkeypatch):
    from hardware_splicer import device_application_runtime as runtime

    monkeypatch.setenv("HS_DEVICE_RUNTIME_ENABLED", "1")
    monkeypatch.delenv("HS_DEVICE_RUNTIME_VENDOR_LIBS", raising=False)
    result = runtime.run_device_application(bh1750_spec())
    assert result["status"] == "PARTIAL"
    assert result["host"]["status"] == "PASSED"
    assert result["vendor_host"]["status"] == "NOT_RUN"
    assert "libraries are not configured" in result["vendor_host"]["reason"]
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["firmware_authorized"] is False and result["power_on_authorized"] is False
    assert result["esp32_compilation"] == "NOT_RUN"


def _pinned_libraries():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / ".cache/hardware-splicer/device-application"
    import os

    named = os.environ.get("HS_VENDOR_LIBS", "").strip()
    return [Path(named)] if named else sorted(root.glob("*/project/.pio/libdeps/application"))


@pytest.mark.skipif(shutil.which("g++") is None, reason="needs a host compiler")
def test_the_bh1750_adapter_passes_its_vendor_host_scenarios_against_the_datasheet_model(monkeypatch):
    from hardware_splicer import device_application_runtime as runtime
    from hardware_splicer.device_application_execution import vendor_libs_available
    from hardware_splicer.device_vendor_profiles import vendor_profile

    choices = [path for path in _pinned_libraries() if vendor_libs_available(path, "bh1750")]
    if not choices:
        pytest.skip("pinned vendor libraries not available")
    monkeypatch.setenv("HS_DEVICE_RUNTIME_ENABLED", "1")
    monkeypatch.setenv("HS_DEVICE_RUNTIME_VENDOR_LIBS", str(choices[-1]))
    result = runtime.run_device_application(bh1750_spec())
    assert result["status"] == "PASSED"
    scenarios = [row["scenario"] for row in result["vendor_host"]["scenarios"]]
    assert scenarios == list(vendor_profile("bh1750")["scenarios"]) and len(scenarios) == 11
    # The BH1750 reads through its own Wire driver, so only the display stack is vendor code and only it is pinned.
    assert sorted(result["vendor_host"]["library_manifest"]) == ["Adafruit BusIO", "Adafruit GFX Library", "Adafruit SSD1306"]
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["firmware_authorized"] is False and result["power_on_authorized"] is False
