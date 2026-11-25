"""A lab pack gathers the planner's outputs for a person to follow; HS ticks only what it ran, the rest is operator-supplied."""

from __future__ import annotations

import json

import pytest

from hardware_splicer.device_draft import draft_device_spec
from hardware_splicer.device_lab import DeviceLabError, build_lab, main, observe, record

PARTS = ["adafruit-oled-1.3-128x64-stemma-qt", "adafruit-bme280-stemma-qt"]


def _spec(parts=PARTS):
    return draft_device_spec({"controller": "esp32-devkitc-v4", "parts": parts, "name": "Room climate logger"})["spec"]


@pytest.fixture
def lab(tmp_path):
    build_lab(_spec(), tmp_path / "lab")
    return tmp_path / "lab"


def test_a_lab_holds_the_plan_case_firmware_and_a_status_ladder(lab):
    data = json.loads((lab / "lab.json").read_text())
    assert {rung: row["done"] for rung, row in data["status"].items()} == {
        "planned": True, "host_tested": False, "built": False, "flashed": False, "observed": False, "measured": False}
    assert data["physical_correctness"] == "UNPROVEN" and data["firmware_authorized"] is False and data["power_on_authorized"] is False
    for name in ("LAB.md", "plan.json", "engineering.json", "spec.json", "case/case_base.stl", "case/case_lid.stl", "firmware/platformio.ini", "firmware/src/main.cpp"):
        assert (lab / name).is_file(), name
    text = (lab / "LAB.md").read_text()
    plan = json.loads((lab / "plan.json").read_text())
    assert sum(1 for line in text.splitlines() if line.startswith("| display:") or line.startswith("| sensor:")) == len(plan["wires"])
    assert "BOOT sensor=0x77 display=0x3D" in text and "pio run -t upload -t monitor" in text
    assert "Not assessed at all" in text and "152 mA" in text


def test_pasted_serial_that_agrees_ticks_flashed_and_observed_as_operator_supplied(lab):
    data = observe(lab, "BOOT sensor=0x77 display=0x3D\nT=1000 STATE=OK TEMP_C=24.10 HUM_PCT=60.0 PRES_HPA=1009.2\n")
    for rung in ("built", "flashed", "observed"):
        assert data["status"][rung]["done"] is True and data["status"][rung]["provenance"] == "operator_supplied_text"
    assert data["status"]["measured"]["done"] is False and data["physical_correctness"] == "UNPROVEN"
    assert (lab / "observations.json").is_file()


def test_a_missing_display_is_not_observed(lab):
    data = observe(lab, "DISPLAY MISSING\nBOOT sensor=0x77 display=NONE\n")
    assert data["status"]["observed"]["done"] is False and data["status"]["observed"]["detail"]["display"] == "no_acknowledge"


def test_measurements_are_recorded_beside_the_estimate(lab):
    data = record(lab, usb_current_ma=190, case_fit="tight", minutes=50)
    entry = data["records"][-1]
    assert entry["provenance"] == "operator_supplied" and entry["current_vs_sourced_sum"] == pytest.approx(190 / 152, abs=0.01)
    assert data["status"]["measured"]["done"] is True
    with pytest.raises(DeviceLabError, match="case fit"):
        record(lab, usb_current_ma=190, case_fit="perfect", minutes=50)
    with pytest.raises(DeviceLabError, match="usb current"):
        record(lab, usb_current_ma=-1, case_fit="good", minutes=50)


def test_a_plan_with_warnings_does_not_become_a_lab(tmp_path):
    spec = _spec()
    spec["connections"] = [dict(c, to="mcu.5V") if c["from"] == "display.Vin" else c for c in spec["connections"]]
    with pytest.raises(DeviceLabError, match="five_volts_to_a_3v3_system"):
        build_lab(spec, tmp_path / "lab")
    assert not (tmp_path / "lab").exists()


def test_a_combination_without_application_firmware_still_makes_a_lab(tmp_path):
    build_lab(_spec(["adafruit-oled-1.3-128x64-stemma-qt"]), tmp_path / "lab")
    data = json.loads((tmp_path / "lab" / "lab.json").read_text())
    assert data["firmware"]["folder"] is None and "diagnostic" in (tmp_path / "lab" / "LAB.md").read_text()


def test_cli(tmp_path, capsys):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(_spec()))
    assert main(["build", str(spec), str(tmp_path / "lab")]) == 0
    serial = tmp_path / "serial.txt"
    serial.write_text("BOOT sensor=0x76 display=0x3C\n")
    assert main(["observe", str(tmp_path / "lab"), str(serial)]) == 0
    assert main(["record", str(tmp_path / "lab"), "--case-fit", "nope"]) == 2
    assert main(["observe", str(tmp_path / "missing"), str(serial)]) == 2
    capsys.readouterr()


def test_what_can_i_build_from_the_parts_on_the_bench():
    from hardware_splicer.device_lab import what_can_i_build
    from hardware_splicer.device_plan import module_library

    result = what_can_i_build(["esp32-devkitc-v4", "adafruit-bme280-stemma-qt"])
    assert result["ready"] == [{"controller": "esp32-devkitc-v4", "parts": ["adafruit-bme280-stemma-qt"], "missing": []}]
    assert all(len(row["missing"]) == 1 for row in result["one_part_away"])
    assert ("adafruit-oled-1.3-128x64-stemma-qt", 2) in result["best_single_addition"]
    total = len(result["ready"]) + len(result["one_part_away"]) + result["needs_two_or_more"]
    sensors = sum(1 for m in module_library()["modules"] if m["kind"] == "i2c_breakout")
    assert total == 2 * 3 * (sensors + 1) - 2  # two controllers, no/two displays, no/each sensor, less the two with nothing attached
    with pytest.raises(DeviceLabError, match="not in the module library"):
        what_can_i_build(["esp32-devkitc-v4", "flux-capacitor"])
