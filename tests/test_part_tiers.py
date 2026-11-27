"""One catalogue over both part libraries, with each part's real capabilities and no implied promotion between tiers."""

from __future__ import annotations

import pytest

from hardware_splicer.device_draft import draft_device_spec
from hardware_splicer.part_tiers import PartCheckError, check_any_wiring, unified_catalog


def test_every_part_from_both_libraries_is_listed_once_with_what_hs_can_do_with_it():
    catalog = unified_catalog()
    ids = [p["id"] for p in catalog["parts"]]
    assert len(ids) == len(set(ids)) == catalog["count"]
    counts = catalog["capability_counts"]
    native = [p for p in catalog["parts"] if p["library"] not in ("wirestudio", "platformio", "wokwi", "black_wire")]
    assert counts["wiring_check"] == len(native)
    assert counts["design_review"] == sum(p["library"] == "wirestudio" for p in catalog["parts"]) > 100  # WireStudio's parts and boards
    assert counts["board_metadata"] == sum(p["library"] == "platformio" for p in catalog["parts"]) > 500  # PlatformIO's boards
    assert counts["device_plan"] == sum(1 for p in catalog["parts"] if p["library"] == "device_planner")
    assert 0 < counts["device_plan"] < counts["pcb_compose"] < counts["wiring_check"]
    # Only planner modules can be planned into a case; an engine part never claims it.
    assert all(("device_plan" in p["capabilities"]) == (p["library"] == "device_planner") for p in catalog["parts"])


def test_engine_parts_link_to_cited_boards_only_through_a_named_chip():
    by_id = {p["id"]: p for p in unified_catalog()["parts"]}
    assert by_id["bme280"]["cited_boards_with_this_chip"] == ["adafruit-bme280-stemma-qt"]
    assert by_id["ds3231_rtc"]["cited_boards_with_this_chip"] == ["adafruit-ds3231-stemma-qt"]
    assert "cited_boards_with_this_chip" not in by_id["hc-sr04"]
    assert ["esp32-cam-module", "esp32_cam"] in unified_catalog()["engine_entries_sharing_a_part_number"]


def test_search_filters_both_libraries():
    hits = {p["id"] for p in unified_catalog("bme280")["parts"]}
    assert {"bme280", "adafruit-bme280-stemma-qt"} <= hits


SONAR = {"modules": [{"id": "mcu", "module": "esp32-devkit"}, {"id": "sonar", "module": "hc-sr04"}],
         "connections": [{"from": "sonar.VCC", "to": "mcu.VIN"}, {"from": "sonar.GND", "to": "mcu.GND"},
                         {"from": "sonar.TRIG", "to": "mcu.GPIO5"}, {"from": "sonar.ECHO", "to": "mcu.GPIO18"}]}


def test_engine_parts_get_wiring_rules_and_an_honest_no_case():
    result = check_any_wiring(SONAR)
    rules = {f["rule"] for f in result["findings"]}
    assert result["library"] == "engine" and result["capabilities"] == ["wiring_check"]
    assert "logic" in rules and result["counts"]["errors"] >= 1  # the 5 V ECHO into a 3.3 V GPIO
    assert "no_case" in rules and "plan" not in result and result["physical_correctness"] == "UNPROVEN"


def test_planner_parts_get_the_full_plan():
    spec = draft_device_spec({"controller": "esp32-devkitc-v4", "parts": ["adafruit-bme280-stemma-qt"]})["spec"]
    result = check_any_wiring(spec)
    assert result["library"] == "device_planner" and "case" in result["plan"]


@pytest.mark.parametrize("spec,match", [
    ({"modules": [{"id": "mcu", "module": "esp32-devkitc-v4"}, {"id": "s", "module": "hc-sr04"}]}, "use engine ids"),
    ({"modules": [{"id": "mcu", "module": "esp32-devkit"}, {"id": "x", "module": "flux-capacitor"}]}, "no part"),
    ({**SONAR, "connections": [{"from": "sonar.ECHO", "to": "mcu.GPIO99"}]}, "has no pin 'GPIO99'"),
    ({"modules": []}, "modules list"),
])
def test_bad_specs_are_refused(spec, match):
    with pytest.raises(PartCheckError, match=match):
        check_any_wiring(spec)


def test_the_device_api_serves_the_catalogue_and_the_wiring_check(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from hardware_splicer.product_api import create_product_app

    monkeypatch.setenv("HARDWARE_SPLICER_STATE_DIR", str(tmp_path / "state"))
    client = TestClient(create_product_app())
    parts = client.get("/v1/devices/parts", params={"q": "hc-sr04"}).json()
    assert parts["ok"] and {"hc-sr04", "wirestudio:hc-sr04", "wokwi:hc-sr04"} <= {p["id"] for p in parts["parts"]}
    checked = client.post("/v1/devices/check-wiring", json=SONAR).json()
    assert checked["ok"] and checked["library"] == "engine"
    refused = client.post("/v1/devices/check-wiring", json={"modules": []})
    assert refused.status_code == 422


def test_a_promoted_engine_part_gains_a_cited_planner_board():
    """The SCD-41 was promoted from the engine library with geometry from Adafruit's board file and cited electrical text."""
    from hardware_splicer.device_plan import build_device_plan, module_library

    entry = next(m for m in module_library()["modules"] if m["id"] == "adafruit-scd41-stemma-qt")
    assert entry["pcb_mm"] == {"x": 25.4, "y": 22.86, "z": 1.6} and entry["i2c"]["addresses"] == ["0x62"]
    assert any("blob/c83995482b4c830a835caef158e6196a507025b3" in s["url"] for s in entry["sources"])
    assert {p["id"]: p["roles"] for p in entry["pins"]} == {"VCC": ["power_in"], "3.3V": ["power_3v3"], "GND": ["ground"],
                                                            "SCL": ["i2c_scl"], "SDA": ["i2c_sda"]}
    by_id = {p["id"]: p for p in unified_catalog()["parts"]}
    assert by_id["scd41-co2"]["cited_boards_with_this_chip"] == ["adafruit-scd41-stemma-qt"]
    plan = build_device_plan(draft_device_spec({"controller": "esp32-devkitc-v4",
                                                "parts": ["adafruit-oled-1.3-128x64-stemma-qt", "adafruit-scd41-stemma-qt"]})["spec"])
    assert plan["counts"]["errors"] == 0 and plan["counts"]["warnings"] == 0


def test_the_vl53l0x_was_promoted_with_the_current_board_outline():
    from hardware_splicer.device_plan import build_device_plan, module_library

    entry = next(m for m in module_library()["modules"] if m["id"] == "adafruit-vl53l0x-stemma-qt")
    assert entry["pcb_mm"]["x"] == 25.4 and entry["i2c"]["addresses"] == ["0x29"]
    assert "July 2020" in entry["dimension_basis"]["heights"]  # the product page's size is the old board
    assert {"vl53l0x_tof"} <= {p["id"] for p in unified_catalog("vl53")["parts"]}
    plan = build_device_plan(draft_device_spec({"controller": "raspberry-pi-pico", "parts": ["adafruit-vl53l0x-stemma-qt"]})["spec"])
    assert plan["counts"]["errors"] == 0 and plan["counts"]["warnings"] == 0


def test_wokwi_parts_are_listed_and_corroborate_the_oled_pin_order():
    """Wokwi's SSD1306 module and Adafruit's 1.3 inch board file give the same eight pins in the same order."""
    from hardware_splicer.device_plan import module_library

    by_id = {p["id"]: p for p in unified_catalog()["parts"]}
    wokwi = by_id["wokwi:ssd1306"]["pins"]
    adafruit = [p["name"] for p in sorted(next(m for m in module_library()["modules"]
                                               if m["id"] == "adafruit-oled-1.3-128x64-stemma-qt")["pins"], key=lambda p: p["x"])]
    assert [w.upper() for w in wokwi] == [a.upper() for a in ["Data", "Clk", "DC", "Rst", "CS", "3v3", "Vin", "GND"]] == [a.upper() for a in adafruit]
    assert unified_catalog()["capability_counts"]["pin_signals"] >= 30


def test_an_led_strip_takes_power_rather_than_supplying_it():
    """Its 5V pin was typed power_out, so a strip on an MCU's VIN read as a supply (found in the 26 Nov 2026 head-to-head)."""
    strip = {"modules": [{"id": "mcu", "module": "esp32-devkit"}, {"id": "strip", "module": "ws2812b_strip"}],
             "connections": [{"from": "strip.5V", "to": "mcu.VIN"}, {"from": "strip.GND", "to": "mcu.GND"}, {"from": "strip.DIN", "to": "mcu.GPIO18"}]}
    rules = {f["rule"] for f in check_any_wiring(strip)["findings"]}
    assert "logicLow" in rules and "noSource" in rules  # two power inputs joined: nothing on that wire supplies the strip


MCU = {"id": "mcu", "module": "esp32-devkit"}


def _servos(n):
    pins = ["GPIO16", "GPIO17", "GPIO18", "GPIO23"]
    return {"modules": [MCU, *({"id": f"s{i}", "module": "sg90"} for i in range(n))],
            "connections": [c for i in range(n) for c in ({"from": f"s{i}.VCC", "to": "mcu.VIN"}, {"from": f"s{i}.GND", "to": "mcu.GND"},
                                                           {"from": f"s{i}.SIG", "to": f"mcu.{pins[i]}"})]}


def _strip(count=None):
    row = {"id": "strip", "module": "ws2812b_strip", **({"count": count} if count else {})}
    return {"modules": [MCU, row], "connections": [{"from": "strip.5V", "to": "mcu.VIN"}, {"from": "strip.GND", "to": "mcu.GND"},
                                                   {"from": "strip.DIN", "to": "mcu.GPIO18"}]}


def _budget(spec):
    return [(f["severity"], f["rule"]) for f in check_any_wiring(spec)["findings"] if f["rule"].startswith("usbBudget")]


def test_loads_on_the_controller_5v_pin_are_added_up_against_a_usb_port():
    """The head-to-head traps: four SG90s, and 60 WS2812B pixels, on a DevKit's 5 V pin fed from USB (cited figures)."""
    assert _budget(_servos(4)) == [("error", "usbBudget")]
    assert _budget(_servos(1)) == [("warning", "usbBudget")]  # 500 mA: the whole port before the board's own draw
    assert _budget(_strip(60)) == [("error", "usbBudget")]
    assert _budget(_strip(4)) == []  # 240 mA
    assert _budget(_strip()) == [("warning", "usbBudgetUnsized")]
    message = next(f["message"] for f in check_any_wiring(_strip(60))["findings"] if f["rule"] == "usbBudget")
    assert "60 x 60 mA = 3600 mA" in message and "learn.adafruit.com" in message
