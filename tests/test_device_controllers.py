"""More than one controller board, added as library data: the planner, case and review must treat each by its own figures."""
import copy
import hashlib
import json

import pytest

from hardware_splicer.device_application import build_device_application
from hardware_splicer.device_case import build_device_case, mesh_report
from hardware_splicer.device_engineering import build_engineering_review
from hardware_splicer.device_firmware import build_device_firmware
from hardware_splicer.device_plan import (
    DevicePlanError, _check_controller, build_device_plan, example_specs, module_library,
)

# What the ESP32 examples produced before the planner stopped carrying ESP32 wording in code. If these change, generalising
# the planner changed an existing board's plan, which is a regression.
ESP32_PLAN_SHA256 = {
    "esp32_oled_usb": "c29c3483d2bd7be05f97bb6720d130e1c59db375b3ce5ddbb1c2704d14f3329c",
    "esp32_oled_bme280_usb": "62841b0cf9db6c293878049b61fa970eebb586789922f308ae028f7e7949fa5e",
}
PICO_I2C0_SDA = {"GP0", "GP4", "GP8", "GP12", "GP16", "GP20"}
PICO_I2C0_SCL = {"GP1", "GP5", "GP9", "GP13", "GP17", "GP21"}
PICO_I2C1_SDA = {"GP2", "GP6", "GP10", "GP14", "GP18", "GP26"}
PICO_I2C1_SCL = {"GP3", "GP7", "GP11", "GP15", "GP19", "GP27"}


def library():
    return {m["id"]: m for m in module_library()["modules"]}


def pico_variant(sda, scl):
    spec = copy.deepcopy(example_specs()["pico_oled_usb"])
    for wire in spec["connections"]:
        if wire["from"] == "display.SDA":
            wire["to"] = f"mcu.{sda}"
        if wire["from"] == "display.SCL":
            wire["to"] = f"mcu.{scl}"
    return build_device_plan(spec)


def rules(plan, severity="error"):
    return sorted(f["rule"] for f in plan["findings"] if f["severity"] == severity)


def test_the_esp32_plans_are_byte_identical_to_before_the_planner_was_generalised():
    for name, expected in ESP32_PLAN_SHA256.items():
        plan = build_device_plan(example_specs()[name])
        assert hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest() == expected, name


@pytest.mark.parametrize("name", sorted(example_specs()))
def test_every_example_plans_without_errors_reviews_and_exports_a_closed_case(name):
    spec = example_specs()[name]
    plan = build_device_plan(spec)
    assert plan["counts"]["errors"] == 0 and plan["wires"]
    review = build_engineering_review(spec)
    assert review["physical_correctness"] == "UNPROVEN" and review["domains"]
    meta, _ = build_device_case(spec)
    assert all(m["closed_manifold"] and m["volume_mm3"] > 0 for m in meta["meshes"].values())
    assert meta["printed"] is False and meta["firmware_authorized"] is False


def test_the_pico_pin_table_agrees_with_the_published_pinout():
    pico = library()["raspberry-pi-pico"]
    by_number = {p["number"]: p for p in pico["pins"]}
    assert sorted(by_number) == list(range(1, 41))
    assert [by_number[n]["name"] for n in (1, 6, 7, 21, 30, 36, 37, 39, 40)] == ["GP0", "GP4", "GP5", "GP16", "RUN", "3V3", "3V3_EN", "VSYS", "VBUS"]
    grounds = [n for n, p in by_number.items() if "ground" in p["roles"]]
    assert grounds == [3, 8, 13, 18, 23, 28, 33, 38]  # seven GND pins and AGND
    gpio = {p["name"] for p in pico["pins"] if "gpio" in p["roles"]}
    assert len(gpio) == 26 and "GP23" not in gpio and "GP24" not in gpio and "GP25" not in gpio and "GP29" not in gpio
    named = {"i2c_sda_capable": (PICO_I2C0_SDA | PICO_I2C1_SDA), "i2c_scl_capable": (PICO_I2C0_SCL | PICO_I2C1_SCL)}
    for role, expected in named.items():
        assert {p["name"] for p in pico["pins"] if role in p["roles"]} == expected
    controller = {p["name"]: p["i2c_controller"] for p in pico["pins"] if "i2c_controller" in p}
    assert {n for n, c in controller.items() if c == 0} == PICO_I2C0_SDA | PICO_I2C0_SCL
    assert {n for n, c in controller.items() if c == 1} == PICO_I2C1_SDA | PICO_I2C1_SCL
    # 2.54 mm pitch down each row, the rows 17.78 mm apart, 48.26 mm from the first pin to the last (datasheet Figure 3)
    left = sorted((p for p in pico["pins"] if p["header"] == "left"), key=lambda p: p["y"])
    right = sorted((p for p in pico["pins"] if p["header"] == "right"), key=lambda p: p["y"])
    for row in (left, right):
        assert [round(b["y"] - a["y"], 2) for a, b in zip(row, row[1:])] == [2.54] * 19
        assert round(row[-1]["y"] - row[0]["y"], 2) == 48.26
    assert round(right[0]["x"] - left[0]["x"], 2) == 17.78


def test_the_default_i2c_pins_are_gp4_and_gp5_and_a_pin_with_no_i2c_function_is_refused():
    assert rules(pico_variant("GP4", "GP5")) == []
    assert rules(pico_variant("GP6", "GP7")) == []  # I2C1 is a valid pair
    assert "swapped_default_i2c" in rules(pico_variant("GP5", "GP4"), "warning") or "not_an_i2c_pin" in rules(pico_variant("GP5", "GP4"))
    bad = pico_variant("GP22", "GP5")
    assert "not_an_i2c_pin" in rules(bad)
    assert "no I2C function" in next(f["message"] for f in bad["findings"] if f["rule"] == "not_an_i2c_pin")
    swapped = pico_variant("GP1", "GP5")  # GP1 is an SCL pin
    assert "an I2C SCL pin" in next(f["message"] for f in swapped["findings"] if f["rule"] == "not_an_i2c_pin")


def test_one_bus_may_not_mix_the_two_i2c_controllers():
    mixed = pico_variant("GP4", "GP7")
    finding = next(f for f in mixed["findings"] if f["rule"] == "i2c_mixed_controllers")
    assert "I2C0" in finding["message"] and "I2C1" in finding["message"]
    assert "i2c_mixed_controllers" not in rules(pico_variant("GP26", "GP27"))  # I2C1, analogue-capable pins


@pytest.mark.parametrize("pin,rule", [("RUN", "reset_pin"), ("3V3_EN", "reset_pin"), ("ADC_VREF", "flash_pin"), ("VBUS", "power_to_signal")])
def test_pins_that_should_carry_nothing_are_refused_with_the_boards_own_reason(pin, rule):
    plan = pico_variant(pin, "GP5")
    assert rule in rules(plan)
    if pin == "ADC_VREF":
        assert "ADC's reference voltage" in next(f["message"] for f in plan["findings"] if f["rule"] == rule)  # not the ESP32's flash text


def test_the_planners_wording_comes_from_each_boards_own_entry():
    pico = build_device_plan(example_specs()["pico_oled_bme280_usb"])
    esp = build_device_plan(example_specs()["esp32_oled_bme280_usb"])
    pico_text = " ".join(f["message"] + f["basis"] for f in pico["findings"] + [])
    pico_text += " ".join(step["detail"] if "detail" in step else json.dumps(step) for step in pico["steps"])
    for word in ("ESP32", "DevKitC", "WROOM", "Wi-Fi", "antenna", "Arduino"):
        assert word not in pico_text, word
    esp_text = " ".join(f["message"] for f in esp["findings"])
    assert "DevKitC" in esp_text and "antenna" in esp_text.lower()
    label = next(w["to"]["label"] for w in pico["wires"] if w["to"]["module"] == "mcu" and w["to"]["pin"] == "GP4")
    assert "counting from the USB end" in label and "antenna" not in label
    esp_label = next(w["to"]["label"] for w in esp["wires"] if w["to"]["module"] == "mcu" and w["to"]["pin"] == "IO21")
    assert "counting from the antenna end" in esp_label


def test_a_board_with_no_antenna_has_no_antenna_check_and_a_board_with_one_does():
    pico = build_engineering_review(example_specs()["pico_oled_usb"])
    esp = build_engineering_review(example_specs()["esp32_oled_usb"])
    ids = lambda review: {c["id"]: c for d in review["domains"] for c in d["checks"]}
    assert ids(pico)["antenna_clearance"]["status"] == "not_assessed"
    assert ids(esp)["antenna_clearance"]["status"] == "exceeds_limit"
    assert "antenna" not in ids(pico)["usb_insertion_support"]["summary"] and "antenna end" in ids(esp)["usb_insertion_support"]["summary"]


def test_the_review_uses_each_boards_regulator_and_temperature_limit():
    pico = build_engineering_review(example_specs()["pico_oled_bme280_usb"])
    checks = {c["id"]: c for d in pico["domains"] for c in d["checks"]}
    assert checks["supply_current"]["quantities"]["regulator"] == "switching"
    assert checks["enclosure_temperature"]["quantities"]["lowest_sourced_operating_limit_c"] == 70  # the Pico's recommended ambient, below the sensors' 85
    peak = checks["supply_current"]["quantities"]["sourced_peak_ma_upper_bound"]
    assert peak == pytest.approx(95.5 + 0.714)  # Pico demo maximum at 5 V and the BME280 maximum, nothing from the ESP32
    assert any("RT6150" in text for text in checks["supply_current"]["limits"])


def test_the_application_and_diagnostic_generators_refuse_a_board_they_have_no_firmware_for():
    spec = example_specs()["pico_oled_bme280_usb"]
    with pytest.raises(DevicePlanError, match="supports only the catalog ESP32-DevKitC V4"):
        build_device_application(spec)
    with pytest.raises(DevicePlanError, match="supports only the catalog ESP32-DevKitC V4"):
        build_device_firmware(spec)


def test_a_controller_entry_without_its_wording_or_sources_is_refused():
    pico = library()["raspberry-pi-pico"]
    _check_controller(pico)

    def broken(edit):
        entry = copy.deepcopy(pico)
        edit(entry)
        with pytest.raises(RuntimeError):
            _check_controller(entry)

    broken(lambda e: e["electrical"].pop("datasheet_basis"))
    broken(lambda e: e["electrical"].update(supply_options_note=""))
    broken(lambda e: e["electrical"].update(i2c_pin_mux="sometimes"))
    broken(lambda e: e["electrical"].pop("i2c_pin_note"))
    broken(lambda e: e.pop("pin_numbering_from"))
    broken(lambda e: next(p for p in e["pins"] if p["name"] == "GP4").pop("i2c_controller"))
    esp = library()["esp32-devkitc-v4"]
    _check_controller(esp)


def test_the_case_of_a_pico_is_sized_from_the_pico():
    meta, _ = build_device_case(example_specs()["pico_oled_usb"])
    plan = build_device_plan(example_specs()["pico_oled_usb"])
    assert plan["case"]["outer_mm"]["z"] < 40  # a 21 mm wide board needs a narrower case than the 28 mm DevKitC
    assert meta["meshes"]["case_base"]["size_mm"][:2] == [plan["case"]["outer_mm"]["x"], plan["case"]["outer_mm"]["z"]]
