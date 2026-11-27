"""A second, larger display added as library data: Adafruit's 1.3 inch STEMMA QT OLED, with its geometry from the maker's board file."""

from __future__ import annotations

import pytest

from hardware_splicer.device_draft import draft_device_spec
from hardware_splicer.device_plan import build_device_plan, module_library

OLED13 = "adafruit-oled-1.3-128x64-stemma-qt"


def _entry():
    return next(m for m in module_library()["modules"] if m["id"] == OLED13)


def _findings(plan, severity=None):
    return {f["rule"] for f in plan["findings"] if severity is None or f["severity"] == severity}


def test_the_entry_carries_the_board_files_geometry():
    entry = _entry()
    assert entry["kind"] == "display" and entry["pin_order_varies"] is False
    pins = {p["name"]: p for p in entry["pins"]}
    # Seen from the screen: Data at the left, 0.1 inch pitch, 2.54 mm from the top edge, centred on the 35.56 mm board.
    assert [p["name"] for p in sorted(entry["pins"], key=lambda p: p["x"])] == ["Data", "Clk", "DC", "Rst", "CS", "3v3", "Vin", "GND"]
    assert pins["Data"]["x"] + pins["GND"]["x"] == pytest.approx(entry["pcb_mm"]["x"])
    assert all(p["y"] == 2.54 for p in entry["pins"])
    assert pins["Data"]["roles"] == ["i2c_sda"] and pins["Clk"]["roles"] == ["i2c_scl"] and pins["Vin"]["roles"] == ["power_in"]
    assert entry["panel"]["active_mm"] == {"x": 29.42, "y": 14.7} and entry["panel"]["center_offset_published"] is True
    assert entry["electrical"]["onboard_pullups"] is True
    assert all(s["url"].startswith("https://") for s in entry["sources"])
    assert any("blob/02c953af" in s["url"] for s in entry["sources"])  # the board file is pinned to a commit


@pytest.mark.parametrize("controller", ["esp32-devkitc-v4", "raspberry-pi-pico"])
def test_a_drafted_device_with_the_larger_display_plans_cleanly(controller):
    plan = build_device_plan(draft_device_spec({"controller": controller, "parts": [OLED13]})["spec"])
    assert not _findings(plan, "error") and not _findings(plan, "warning")
    window = plan["case"]["window"]
    assert window["width_mm"] == pytest.approx(29.42 + 3.0) and window["depth_mm"] == pytest.approx(14.7 + 3.0)
    assert "maker's board file" in window["basis"]
    assert "i2c_pullups_note" in _findings(plan)
    assert plan["case"]["outer_mm"]["z"] > 35.56  # the case grows to hold the wider board


def test_the_small_display_keeps_its_unpublished_offset_wording():
    plan = build_device_plan(draft_device_spec({"controller": "esp32-devkitc-v4", "parts": ["ssd1306-096-i2c"]})["spec"])
    assert "not published" in plan["case"]["window"]["basis"]


def test_vin_from_5v_warns_that_the_bus_follows_vin():
    """The board pulls SDA and SCL up to Vin, so 5 V on Vin is 5 V on the controller's I2C pins."""

    spec = draft_device_spec({"controller": "esp32-devkitc-v4", "parts": [OLED13]})["spec"]
    spec["connections"] = [dict(c, to="mcu.5V") if c["from"] == "display.Vin" else c for c in spec["connections"]]
    plan = build_device_plan(spec)
    assert "five_volts_to_a_3v3_system" in _findings(plan, "warning")
    message = next(f["message"] for f in plan["findings"] if f["rule"] == "five_volts_to_a_3v3_system")
    assert "5 V on SDA and SCL" in message


def test_the_regulator_output_is_not_a_second_supply():
    spec = draft_device_spec({"controller": "esp32-devkitc-v4", "parts": [OLED13]})["spec"]
    spec["connections"] = spec["connections"] + [{"from": "display.3v3", "to": "mcu.3V3"}]
    assert "supplies_joined" in _findings(build_device_plan(spec), "error")


def _logger_spec():
    return draft_device_spec({"controller": "esp32-devkitc-v4", "parts": [OLED13, "adafruit-bme280-stemma-qt"]})["spec"]


def test_the_application_drives_any_sourced_ssd1306_display():
    import io
    import zipfile

    from hardware_splicer.device_application import build_device_application
    from hardware_splicer.device_plan import ssd1306_display_ids

    assert ssd1306_display_ids() == {"ssd1306-096-i2c", OLED13}
    _meta, archive = build_device_application(_logger_spec())
    main = zipfile.ZipFile(io.BytesIO(archive)).read("src/main.cpp").decode()
    # Adafruit's 1.3 inch board defaults to 0x3D, so the library lists it first and the application probes it first.
    assert "static const uint8_t kDisplayAddrs[] = { 0x3D, 0x3C };" in main


def test_bench_output_from_the_larger_display_is_read_as_a_presence_check():
    from hardware_splicer.device_observations import check_device_observations

    text = "BOOT sensor=0x77 display=0x3D\n"
    by_id = {m["id"]: m for m in check_device_observations(_logger_spec(), text)["modules"]}
    assert by_id["display"]["status"] == "acknowledged" and by_id["display"]["evidence"] == "application_presence_check"
    assert "not a display identity" in by_id["display"]["note"]
    missing = {m["id"]: m for m in check_device_observations(_logger_spec(), "DISPLAY MISSING\nBOOT sensor=0x77 display=NONE\n")["modules"]}
    assert missing["display"]["status"] == "no_acknowledge"
