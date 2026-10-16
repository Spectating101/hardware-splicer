"""Mission-driven address straps and independent I2C buses."""
import copy
import random

import pytest

from hardware_splicer.device_draft import draft_from_parts_text
from hardware_splicer.device_plan import build_device_plan, module_library
from hardware_splicer.device_suggestions import apply_first_suggestions


def two_sensors(second=None, board="Raspberry Pi Pico"):
    spec = draft_from_parts_text({"text": f"{board}\n2x BME280"})["spec"]
    if second:
        for wire in spec["connections"]:
            if wire["from"] == "sensor_2.SDI":
                wire["to"] = f"mcu.{second[0]}"
            if wire["from"] == "sensor_2.SCK":
                wire["to"] = f"mcu.{second[1]}"
    return spec


def rules(plan, severity=None):
    return [f["rule"] for f in plan["findings"] if severity is None or f["severity"] == severity]


@pytest.mark.parametrize("target", ["mcu.GND", "sensor_2.GND"])
@pytest.mark.parametrize("reverse", [False, True])
def test_bme280_ground_strap_selects_0x76(target, reverse):
    spec = two_sensors()
    a, b = "sensor_2.SDO", target
    spec["connections"].append({"from": b if reverse else a, "to": a if reverse else b})
    plan = build_device_plan(spec)
    assert not rules(plan, "error")
    assert "i2c_address_overlap" not in rules(plan)
    sensor = next(m for m in plan["modules"] if m["id"] == "sensor_2")
    assert sensor["i2c_address"]["effective"] == "0x76"
    assert sensor["i2c_address"]["decision"] == "strap"


def test_open_defaults_offer_one_strap_then_replan_clean():
    spec = two_sensors()
    original = copy.deepcopy(spec)
    plan = build_device_plan(spec)
    for sensor in [m for m in plan["modules"] if m["kind"] == "i2c_breakout"]:
        assert sensor["i2c_address"]["effective"] == "0x77"
        assert sensor["i2c_address"]["decision"] == "default"
    clash = next(f for f in plan["findings"] if f["rule"] == "i2c_address_overlap")
    suggestion = clash["suggestions"][0]
    assert suggestion["action"] == "strap_address" and suggestion["pin"] == "SDO"
    assert suggestion["module"] == "sensor_2"
    assert suggestion["to_one_of"][0].endswith(".GND")
    repaired, changed = apply_first_suggestions(spec, plan)
    assert changed and spec == original
    assert len(repaired["connections"]) == len(spec["connections"]) + 1
    assert not [f for f in build_device_plan(repaired)["findings"] if f["severity"] in {"error", "warning"}]


@pytest.mark.parametrize("target", ["mcu.GP10", "mcu.3V3", "mcu.VBUS", "sensor.SDI"])
def test_unsupported_address_strap_is_an_error(target):
    spec = two_sensors()
    spec["connections"].append({"from": "sensor_2.SDO", "to": target})
    plan = build_device_plan(spec)
    finding = next(f for f in plan["findings"] if f["rule"] == "address_select_wiring")
    assert finding["severity"] == "error" and "ground" in finding["message"]


def test_cs_stays_unsupported_and_same_address_straps_still_overlap():
    spec = two_sensors()
    for ref in ("sensor", "sensor_2"):
        spec["connections"].append({"from": f"{ref}.SDO", "to": "mcu.GND"})
    assert "i2c_address_overlap" in rules(build_device_plan(spec), "warning")
    spec["connections"].append({"from": "sensor.CS", "to": "mcu.GP10"})
    assert "unsupported_breakout_pin" in rules(build_device_plan(spec), "error")


@pytest.mark.parametrize("pins", [("GP6", "GP7"), ("GP2", "GP3"), ("GP18", "GP19")])
def test_two_pico_controllers_have_independent_addresses(pins):
    plan = build_device_plan(two_sensors(pins))
    assert not rules(plan, "error")
    assert "i2c_address_overlap" not in rules(plan)
    assert len(plan["i2c_buses"]) == 2
    assert {b["controller"] for b in plan["i2c_buses"]} == {0, 1}


@pytest.mark.parametrize("pins,rule", [(("GP8", "GP9"), "i2c_controller_shared"),
                                      (("GP6", "GP9"), "i2c_mixed_controllers")])
def test_pico_bus_controller_limits(pins, rule):
    assert rule in rules(build_device_plan(two_sensors(pins)), "error")


def test_a_shared_data_net_cannot_have_two_clock_buses():
    spec = two_sensors(("GP4", "GP7"))
    assert "i2c_split_bus" in rules(build_device_plan(spec), "error")


@pytest.mark.parametrize("pins", [("GP18", "GP19"), ("GP6", "GP9"), ("GP8", "GP9")])
def test_bus_findings_are_independent_of_connection_order(pins):
    spec = two_sensors(pins)
    def findings(s):
        # Wire ids identify input positions; compare the complete semantic findings.
        return [{k: v for k, v in f.items() if k != "wire"} for f in build_device_plan(s)["findings"]]
    expected = findings(spec)
    for seed in range(12):
        permuted = copy.deepcopy(spec)
        random.Random(seed).shuffle(permuted["connections"])
        assert findings(permuted) == expected


def test_esp32_accepts_two_buses_and_refuses_a_third():
    spec = two_sensors(("IO18", "IO19"), "ESP32")
    plan = build_device_plan(spec)
    assert not rules(plan, "error") and "i2c_address_overlap" not in rules(plan)
    spec["modules"].append({"id": "third", "module": "adafruit-bme280-stemma-qt"})
    spec["connections"] += [{"from": f"third.{pin}", "to": f"mcu.{target}"}
                            for pin, target in [("Vin", "3V3"), ("GND", "GND"), ("SDI", "IO25"), ("SCK", "IO26")]]
    assert "i2c_controller_count" in rules(build_device_plan(spec), "error")


def test_new_library_facts_are_sourced_and_do_not_invent_a_3v3_strap():
    entries = {m["id"]: m for m in module_library()["modules"]}
    bme = entries["adafruit-bme280-stemma-qt"]
    sdo = next(p for p in bme["pins"] if p["name"] == "SDO")
    assert sdo["roles"] == ["i2c_address_select"]
    assert sdo["address_select"] == {"ground": "0x76", "open": "0x77"}
    assert sdo["address_select_source"] in {s["url"] for s in bme["sources"]}
    assert bme["i2c"]["default_address"] == "0x77"
    assert bme["i2c"]["default_address_source"] == sdo["address_select_source"]
    esp = entries["esp32-devkitc-v4"]
    assert esp["electrical"]["i2c_controller_count"] == 2
    assert esp["electrical"]["i2c_controller_count_source"] in {s["url"] for s in esp["sources"]}


def test_pullups_on_independent_buses_are_not_reported_as_stacked():
    spec = draft_from_parts_text({"text": "Raspberry Pi Pico\nBH1750\nDS3231"})["spec"]
    for wire in spec["connections"]:
        if wire["from"] == "sensor_2.SDA":
            wire["to"] = "mcu.GP6"
        elif wire["from"] == "sensor_2.SCL":
            wire["to"] = "mcu.GP7"
    assert "i2c_pullup_stack" not in rules(build_device_plan(spec))


@pytest.mark.parametrize("second", [None, ("GP6", "GP7")])
def test_a_clean_multi_sensor_plan_does_not_silently_export_single_sensor_firmware(second):
    from hardware_splicer.device_application import build_device_application
    from hardware_splicer.device_plan import DevicePlanError

    spec = two_sensors(second)
    if second is None:
        spec["connections"].append({"from": "sensor_2.SDO", "to": "mcu.GND"})
    assert not [f for f in build_device_plan(spec)["findings"] if f["severity"] in {"error", "warning"}]
    with pytest.raises(DevicePlanError, match="only one sensor breakout"):
        build_device_application(spec)


def test_an_address_strap_is_not_a_modules_missing_ground_return():
    spec = two_sensors()
    spec["connections"] = [w for w in spec["connections"] if w["from"] != "sensor_2.GND"]
    spec["connections"].append({"from": "sensor_2.SDO", "to": "sensor_2.GND"})
    assert any(f["rule"] == "missing_connection" and "sensor_2" in f["message"] and "ground" in f["message"]
               for f in build_device_plan(spec)["findings"])
