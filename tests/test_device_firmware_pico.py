"""The compile-only I2C diagnostic on the Raspberry Pi Pico: the arduino-pico way of starting the bus, on the planned
controller, with the same review boundary as the ESP32 diagnostic and no change to the ESP32 package."""
import hashlib
import io
import json
import re
import zipfile

import pytest

from hardware_splicer.device_application import PICO_PLATFORM
from hardware_splicer.device_firmware import build_device_firmware
from hardware_splicer.device_plan import example_specs
from hardware_splicer.firmware_scaffold import generate_rp2040_i2c_diagnostic_source

from test_device_application_pico import _on_i2c1


def _package(spec):
    metadata, data = build_device_firmware(spec)
    files = {name: zipfile.ZipFile(io.BytesIO(data)).read(name).decode() for name in zipfile.ZipFile(io.BytesIO(data)).namelist()}
    return metadata, data, files


# Hashes of the ESP32 diagnostic packages before the Pico diagnostic existed: the ESP32 output must not move.
ESP32_PACKAGES = {
    "esp32_oled_bme280_usb": "f9d5eefe75453894827ef7f4bc2cc8728fe05b57f4b92d90c088a8ef7a6419b1",
    "esp32_oled_usb": "bca8efef8c6720cb05ee3da3c6f4dcf4b511206847924860d95af1da2536265b",
}


@pytest.mark.parametrize("example", sorted(ESP32_PACKAGES))
def test_the_esp32_diagnostic_package_is_byte_for_byte_unchanged(example):
    _metadata, data = build_device_firmware(example_specs()[example])
    assert hashlib.sha256(data).hexdigest() == ESP32_PACKAGES[example]


def test_the_pico_diagnostic_targets_the_pinned_rp2040_core_on_i2c0():
    metadata, _data, files = _package(example_specs()["pico_oled_bme280_usb"])
    assert metadata["target"] == {"platform": PICO_PLATFORM, "board": "pico", "framework": "arduino", "core": "earlephilhower"}
    ini = files["platformio.ini"]
    assert "[env:diagnostic]" in ini and "board = pico" in ini and "board_build.core = earlephilhower" in ini
    assert PICO_PLATFORM in ini and "esp32" not in ini
    assert metadata["pins"]["sda"]["gpio"] == 4 and metadata["pins"]["scl"]["gpio"] == 5
    source = files["src/main.cpp"]
    for call in ("Wire.setSDA(SDA_PIN)", "Wire.setSCL(SCL_PIN)", "Wire.setClock(BUS_HZ)", "Wire.setTimeout(50)", "Wire.begin();",
                 "Wire.beginTransmission(address)", "Wire.end();", "Serial.read()"):
        assert call in source, call
    # The ESP32 core's begin(sda, scl, hz) does not exist on this core.
    assert "Wire.begin(SDA_PIN" not in source and "setTimeOut" not in source
    assert "constexpr int SDA_PIN = 4;" in source and "constexpr int SCL_PIN = 5;" in source


def test_pins_on_the_second_controller_use_wire1_for_every_call():
    _metadata, _data, files = _package(_on_i2c1(example_specs()["pico_oled_bme280_usb"]))
    source = files["src/main.cpp"]
    assert "constexpr int SDA_PIN = 2;" in source and "constexpr int SCL_PIN = 3;" in source
    assert "Wire1.setSDA(SDA_PIN)" in source and "Wire1.begin();" in source and "Wire1.end();" in source
    assert re.search(r"\bWire\.[A-Za-z_]+\(", source) is None, "a call went to Wire (I2C0) though the plan wired I2C1"
    assert "#include <Wire.h>" in source


def test_the_pico_diagnostic_keeps_the_review_boundary_and_claims_nothing():
    metadata, data, files = _package(example_specs()["pico_oled_bme280_usb"])
    assert metadata["status"] == "COMPILE_ONLY_PROPOSAL" and metadata["compilation"] == "NOT_RUN"
    assert metadata["physical_correctness"] == "UNPROVEN"
    assert metadata["firmware_authorized"] is False and metadata["power_on_authorized"] is False
    assert metadata["observations"] == []
    source = files["src/main.cpp"]
    assert "Not authorized for flashing or powering" in source and "No automatic scan" in source
    readme = files["README.md"]
    assert "pio run -e diagnostic" in readme and "Board profile pico" in readme and "esp32dev" not in readme
    assert "Do not upload from this package." in readme
    for name, facts in metadata["files"].items():
        assert hashlib.sha256(files[name].encode()).hexdigest() == facts["sha256"]
    assert json.loads(files["FIRMWARE_PROPOSAL.json"]) == metadata
    assert build_device_firmware(example_specs()["pico_oled_bme280_usb"])[1] == data


@pytest.mark.parametrize("kwargs", [
    {"sda": 4, "scl": 4, "controller": 0},
    {"sda": -1, "scl": 5, "controller": 0},
    {"sda": 4, "scl": 30, "controller": 0},
    {"sda": 4, "scl": 5, "controller": 2},
    {"sda": True, "scl": 5, "controller": 0},
])
def test_the_rp2040_generator_refuses_impossible_inputs(kwargs):
    with pytest.raises(ValueError):
        generate_rp2040_i2c_diagnostic_source(declared_addresses=["0x3C"], **kwargs)


def test_the_rp2040_generator_refuses_reserved_addresses():
    with pytest.raises(ValueError):
        generate_rp2040_i2c_diagnostic_source(sda=4, scl=5, controller=0, declared_addresses=["0x00"])
