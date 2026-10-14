"""The application on the Raspberry Pi Pico: same application core, a Pico adapter, and no claim the ESP32 lanes made."""
import copy
import io
import re
import zipfile

import pytest

from hardware_splicer.device_application import CONTROLLERS, PICO_PLATFORM, build_device_application
from hardware_splicer.device_parts import available_parts, example_spec_for_part
from hardware_splicer.device_plan import DevicePlanError, build_device_plan, example_specs

PICO = "raspberry-pi-pico"


def _files(spec):
    metadata, data = build_device_application(spec)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return metadata, {name: archive.read(name).decode() for name in archive.namelist()}


def _on_pico(spec):
    """The same parts moved onto the Pico's default I2C0 pins, GP4 (SDA) and GP5 (SCL)."""
    moved = copy.deepcopy(spec)
    for row in moved["modules"]:
        if row["module"] == "esp32-devkitc-v4":
            row["module"] = PICO
    for wire in moved["connections"]:
        wire["to"] = wire["to"].replace("mcu.IO21", "mcu.GP4").replace("mcu.IO22", "mcu.GP5")
    return moved


def _on_i2c1(spec):
    moved = copy.deepcopy(spec)
    for wire in moved["connections"]:
        wire["to"] = wire["to"].replace("mcu.GP4", "mcu.GP2").replace("mcu.GP5", "mcu.GP3")
    return moved


def test_the_pico_package_targets_the_pinned_rp2040_core_and_uses_i2c0_on_its_default_pins():
    metadata, files = _files(example_specs()["pico_oled_bme280_usb"])
    assert metadata["target"] == {"platform": PICO_PLATFORM, "board": "pico", "framework": "arduino", "core": "earlephilhower"}
    assert "#" in PICO_PLATFORM and len(PICO_PLATFORM.split("#")[1]) == 40  # an exact commit, not a moving branch
    ini = files["platformio.ini"]
    assert f"platform = {PICO_PLATFORM}\nboard = pico\nframework = arduino\nboard_build.core = earlephilhower\n" in ini
    main = files["src/main.cpp"]
    assert "constexpr int SDA_PIN = 4;" in main and "constexpr int SCL_PIN = 5;" in main
    assert "Wire.setSDA(SDA_PIN)" in main and "Wire.setSCL(SCL_PIN)" in main and "Wire.begin();" in main
    assert "Wire1" not in main
    assert metadata["pins"]["sda"]["i2c_controller"] == metadata["pins"]["scl"]["i2c_controller"] == 0


def test_pins_of_the_second_i2c_controller_use_wire1_everywhere():
    spec = _on_i2c1(example_specs()["pico_oled_bme280_usb"])
    assert not [f for f in build_device_plan(spec)["findings"] if f["severity"] in {"error", "warning"}]
    metadata, files = _files(spec)
    main = files["src/main.cpp"]
    assert "constexpr int SDA_PIN = 2;" in main and "constexpr int SCL_PIN = 3;" in main
    assert "Wire1.setSDA(SDA_PIN)" in main and "&Wire1" in main and "Wire1.beginTransmission" in main
    # Every use of the bus is the second controller; a stray Wire would talk on I2C0. Comments are not code.
    code = "\n".join(line.split("//", 1)[0] for line in main.splitlines())
    assert not re.search(r"\bWire\.(?!h\b)|&Wire\b", code)
    assert metadata["pins"]["sda"]["i2c_controller"] == 1


def test_sda_and_scl_on_different_rp2040_controllers_are_refused_before_any_source_is_made():
    spec = copy.deepcopy(example_specs()["pico_oled_bme280_usb"])
    for wire in spec["connections"]:
        wire["to"] = wire["to"].replace("mcu.GP5", "mcu.GP3")  # SDA on I2C0, SCL on I2C1
    with pytest.raises(DevicePlanError):
        build_device_application(spec)


def test_the_pico_package_neither_ships_nor_claims_a_vendor_host_lane():
    metadata, files = _files(example_specs()["pico_oled_bme280_usb"])
    assert not [name for name in files if name.startswith("test/vendor_host/")]
    assert metadata["part"]["vendor_host_supported"] is False
    assert "RP2040 core" in metadata["vendor_host_claim_boundary"]
    assert not any(claim.startswith("Vendor-host scenarios") for claim in metadata["non_claims"])
    assert "esp32dev" not in files["README.md"] and "pico" in files["README.md"]
    assert metadata["firmware_authorized"] is False and metadata["power_on_authorized"] is False
    assert metadata["physical_correctness"] == "UNPROVEN" and metadata["compilation"] == "NOT_RUN"


@pytest.mark.parametrize("controller", sorted(CONTROLLERS))
@pytest.mark.parametrize("part", sorted(available_parts()))
def test_every_controller_and_part_fills_every_placeholder_and_shares_the_one_application_core(controller, part):
    spec = example_spec_for_part(part)
    if controller == PICO:
        spec = _on_pico(spec)
    _metadata, files = _files(spec)
    for name, text in files.items():
        assert "{{" not in text, f"{name} has an unfilled placeholder"
    esp32_core = _files(example_spec_for_part(part))[1]["src/app_core.h"]
    assert files["src/app_core.h"] == esp32_core


@pytest.mark.parametrize("part", sorted(available_parts()))
def test_the_esp32_adapter_still_starts_the_bus_the_esp32_way(part):
    main = _files(example_spec_for_part(part))[1]["src/main.cpp"]
    assert "    Wire.setTimeOut(50);\n    Wire.begin(SDA_PIN, SCL_PIN, 100000);" in main
    assert "        return Wire.begin(SDA_PIN, SCL_PIN, 100000);" in main
    assert "setSDA" not in main


@pytest.mark.parametrize("bindings", [
    {"sda": {"i2c_controller": 0}, "scl": {"i2c_controller": 1}},
    {"sda": {"i2c_controller": 0}, "scl": {}},
    {"sda": {}, "scl": {}},
])
def test_the_adapter_refuses_bindings_that_do_not_name_one_rp2040_controller(bindings):
    # The planner refuses such wiring first; this is the generator's own guard if a plan ever reached it.
    from hardware_splicer.device_application import _wiring

    with pytest.raises(DevicePlanError, match="same RP2040 I2C controller"):
        _wiring(PICO, bindings)


def test_the_verifier_says_the_missing_lane_is_the_boards_not_the_parts(tmp_path):
    import importlib.util
    import shutil
    from pathlib import Path

    if shutil.which("g++") is None:
        pytest.skip("g++ is not installed")
    path = Path(__file__).resolve().parents[1] / "scripts" / "verify_device_application.py"
    loader = importlib.util.spec_from_file_location("verify_device_application_under_test", path)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    _run, behaviour, compiled, vendor = module.verify(example_specs()["pico_oled_bme280_usb"], output_root=tmp_path)
    assert behaviour["pass"] is True and compiled is None
    assert vendor["pass"] is None
    assert "pico board" in vendor["reason"] and "for the BME280" not in vendor["reason"]
