"""The application on the Raspberry Pi Pico: the same application core, a Pico adapter, and an RP2040 vendor-host lane."""
import copy
import io
import json
import re
import zipfile
from pathlib import Path

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


def test_the_pico_package_ships_the_rp2040_wire_model_and_a_board_config_for_its_controller():
    metadata, files = _files(example_specs()["pico_oled_bme280_usb"])
    root = Path(__file__).resolve().parents[1] / "src/hardware_splicer/data/firmware_application/vendor_host"
    assert files["test/vendor_host/Wire.h"] == (root / "rp2040" / "Wire.h").read_text()
    assert files["test/vendor_host/Wire.cpp"] == (root / "rp2040" / "Wire.cpp").read_text()
    assert "arduino-pico TwoWire" in files["test/vendor_host/Wire.h"]
    assert files["test/vendor_host/board_config.h"].splitlines()[2:] == [
        "#define HS_RP2040 1", "#define HS_PLANNED_I2C 0", "#define HS_WIRE Wire",
        "#define HS_PLANNED_SDA 4", "#define HS_PLANNED_SCL 5"]
    assert metadata["part"]["vendor_host_supported"] is True
    assert "RP2040 Wire driver's real timing" in metadata["vendor_host_claim_boundary"]
    assert "ESP32" not in metadata["vendor_host_claim_boundary"]
    assert not any("ESP32 Wire" in claim for claim in metadata["non_claims"])
    assert metadata["firmware_authorized"] is False and metadata["physical_correctness"] == "UNPROVEN"
    _metadata, wire1 = _files(_on_i2c1(example_specs()["pico_oled_bme280_usb"]))
    assert "#define HS_PLANNED_I2C 1\n#define HS_WIRE Wire1\n#define HS_PLANNED_SDA 2\n#define HS_PLANNED_SCL 3" in wire1["test/vendor_host/board_config.h"]


def test_an_esp32_package_keeps_the_esp32_wire_model_and_no_board_config():
    _metadata, files = _files(example_specs()["esp32_oled_bme280_usb"])
    root = Path(__file__).resolve().parents[1] / "src/hardware_splicer/data/firmware_application/vendor_host"
    assert files["test/vendor_host/Wire.h"] == (root / "Wire.h").read_text()
    assert "test/vendor_host/board_config.h" not in files and "test/vendor_host/wire_pins_rp2040.h" not in files


def test_the_vendor_host_compile_selects_the_board_from_the_package(tmp_path):
    from hardware_splicer.device_application_execution import vendor_host_compile_command

    host = tmp_path / "test" / "vendor_host"
    host.mkdir(parents=True)
    esp = vendor_host_compile_command(tmp_path, tmp_path, tmp_path / "out")
    assert "-DARDUINO_ARCH_ESP32" in esp and "-DARDUINO_ARCH_RP2040" not in esp
    (host / "board_config.h").write_text("#define HS_RP2040 1\n")
    pico = vendor_host_compile_command(tmp_path, tmp_path, tmp_path / "out")
    assert "-DARDUINO_ARCH_RP2040" in pico and "-DHS_RP2040" in pico and "-DESP32" not in pico


def _vendor_libs():
    import os

    named = os.environ.get("HS_VENDOR_LIBS", "").strip()
    return Path(named) if named and Path(named).is_dir() else None


def _vendor_run(tmp_path, spec, edits=()):
    from hardware_splicer.device_application_execution import _run_vendor_host

    libs = _vendor_libs()
    if libs is None:
        pytest.skip("not run: HS_VENDOR_LIBS names no pinned libdeps directory")
    _metadata, data = build_device_application(spec)
    project = tmp_path / "project"
    zipfile.ZipFile(io.BytesIO(data)).extractall(project)
    for path, old, new in edits:
        text = (project / path).read_text()
        assert text.count(old) == 1, (path, old)
        (project / path).write_text(text.replace(old, new, 1))
    profile = json.loads((project / "FIRMWARE_PROPOSAL.json").read_text())["part"]["vendor_profile"]
    report, log = _run_vendor_host(project, libs, profile)
    return report, log


@pytest.mark.parametrize("variant", ["i2c0_bme280", "i2c1_bme280", "i2c0_bh1750"])
def test_the_real_adafruit_sources_run_against_the_rp2040_wire_model(tmp_path, variant):
    spec = {"i2c0_bme280": example_specs()["pico_oled_bme280_usb"],
            "i2c1_bme280": _on_i2c1(example_specs()["pico_oled_bme280_usb"]),
            "i2c0_bh1750": _on_pico(example_spec_for_part("adafruit-bh1750-stemma-qt"))}[variant]
    report, log = _vendor_run(tmp_path, spec)
    assert report["scenarios"], log.decode(errors="replace")[-2000:]
    assert [s["scenario"] for s in report["scenarios"] if not s["pass"] and not s.get("finding")] == []
    pins = next(s for s in report["scenarios"] if s["scenario"] == "wire_pins_stay_explicit")["detail"]
    assert ("Wire1 on sda=2 scl=3" if variant == "i2c1_bme280" else "Wire on sda=4 scl=5") in pins
    assert "nothing on the other controller" in pins


PICO_MUTANTS = [
    ("the display uses Wire though the plan wired I2C1", [("Adafruit_SSD1306 display_{128, 64, &Wire1, -1};", "Adafruit_SSD1306 display_{128, 64, &Wire, -1};")]),
    ("recovery restarts the bus without ending it", [("        Wire1.end();\n", "")]),
    ("setup never sets the planned I2C1 pins", [("    if (!Wire1.setSDA(SDA_PIN) || !Wire1.setSCL(SCL_PIN)) {", "    if (false) {")]),
    ("setup sets 400 kHz", [("    Wire1.setClock(100000);\n    Wire1.setTimeout(50);\n    Wire1.begin();", "    Wire1.setClock(400000);\n    Wire1.setTimeout(50);\n    Wire1.begin();")]),
    # Found by the Argon review of #117: the display library restores 100 kHz, which hid a recovery at another clock.
    ("recovery restarts at 400 kHz", [("        Wire1.setClock(100000);", "        Wire1.setClock(400000);")]),
    # Found by the same review: two starts at boot used to stand in for a recovery that never restarts the bus.
    ("boot starts the bus twice and recovery does nothing", [
        ("\n    Wire1.begin();\n", "\n    Wire1.begin();\n    Wire1.end();\n    Wire1.begin();\n"),
        ("        Wire1.end();\n", "        return true;\n")]),
]


@pytest.mark.parametrize("name,edits", PICO_MUTANTS, ids=[m[0] for m in PICO_MUTANTS])
def test_the_rp2040_lane_fails_a_broken_pico_adapter(tmp_path, name, edits):
    edits = [("src/main.cpp", old, new) for old, new in edits]
    report, log = _vendor_run(tmp_path, _on_i2c1(example_specs()["pico_oled_bme280_usb"]), edits)
    assert report["scenarios"], f"{name}: no scenario ran: {log.decode(errors='replace')[-1500:]}"
    assert [s for s in report["scenarios"] if not s["pass"] and not s.get("finding")], f"{name} was not caught"


def test_a_core_panic_fails_each_scenario_once_with_its_message(tmp_path):
    # An illegal pin panics in setup(); scenarios that fork isolated cases must still report exactly once each.
    report, log = _vendor_run(tmp_path, _on_i2c1(example_specs()["pico_oled_bme280_usb"]),
                              [("src/main.cpp", "constexpr int SDA_PIN = 2;", "constexpr int SDA_PIN = 4;")])
    names = [s["scenario"] for s in report["scenarios"]]
    assert names and len(names) == len(set(names)), log.decode(errors="replace")[-1500:]
    assert all(not s["pass"] and "illegal pin 4" in s["detail"] for s in report["scenarios"])
    assert "RP2040 Wire timing" in report["claim_boundary"] and "ESP32" not in report["claim_boundary"]


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


def test_the_rp2040_wire_model_behaves_as_the_pinned_core_source(tmp_path):
    """Run directly against the model: what the mutation tests above can only catch if the model is faithful."""
    import shutil
    import subprocess

    if shutil.which("g++") is None:
        pytest.skip("g++ is not installed")
    root = Path(__file__).resolve().parents[1]
    host = root / "src/hardware_splicer/data/firmware_application/vendor_host"
    (tmp_path / "board_config.h").write_text("#pragma once\n#define HS_RP2040 1\n#define HS_PLANNED_I2C 0\n")
    binary = tmp_path / "model_test"
    built = subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-DHS_RP2040", "-DARDUINO_ARCH_RP2040",
                            "-I", str(tmp_path), "-I", str(host / "rp2040"), "-I", str(host),
                            str(root / "tests/data/device_vendor_host/rp2040_wire_model_test.cpp"),
                            str(host / "rp2040" / "Wire.cpp"), str(host / "arduino_core.cpp"), "-o", str(binary)],
                           capture_output=True, text=True)
    assert built.returncode == 0, built.stderr[-3000:]
    run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stdout
    assert "MODEL CHECKS PASSED" in run.stdout


def test_the_pico_lane_readme_gives_the_rp2040_build_command():
    _metadata, files = _files(example_specs()["pico_oled_bme280_usb"])
    readme = files["test/vendor_host/README.md"]
    assert "-DARDUINO_ARCH_RP2040" in readme and "-DESP32" not in readme and "ESP32 Wire driver" not in readme
    assert "arduino-pico TwoWire" in readme and "The Wire model follows arduino-esp32" not in readme
