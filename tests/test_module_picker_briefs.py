"""The offline picker on real briefs: named part numbers, counts, and hints that used to pick the wrong part.

Briefs come from the 26 Nov 2026 head-to-head (examples/head_to_head/agent_tools_20261126.json) and from Formwright's
published example projects, which HS did not write.
"""

from __future__ import annotations

from hardware_splicer.module_picker import _explicit_parts, _pick_modules_regex


def ids(text):
    return set(_pick_modules_regex(text).module_ids)


def test_an_led_strip_is_a_strip_not_a_display():
    got = ids("An ESP32 desk light: a strip of 60 WS2812B LEDs showing colour scenes, powered from a USB phone charger.")
    assert "ws2812b_strip" in got and "ssd1306-128x64" not in got


def test_a_robot_arm_gets_servos_not_a_wheel_motor_driver():
    pick = _pick_modules_regex("A small desk robot arm: four SG90 servos moved by an ESP32 from a phone app over Wi-Fi.")
    assert "sg90" in pick.module_ids and "l298n" not in pick.module_ids and pick.quantities == {"sg90": 4}
    assert "l298n" in ids("A plant watering robot that drives around the greenhouse on two DC motors")


def test_a_lora_node_on_a_cell_gets_a_radio_and_a_charger_and_no_usb_supply():
    got = ids("A LoRa soil moisture sensor running from one 18650 cell that sends a reading every 10 minutes.")
    assert {"lora_sx1278", "soil_moisture", "tp4056"} <= got and "usb-power-5v" not in got


def test_formwright_examples_get_their_named_parts():
    assert {"bme280", "ssd1306-128x64"} <= ids("Desk weather station: BME280 and an OLED in the lid, a wedge on a 25 degree stand, USB-C power")
    kitchen = ids("Kitchen timer: a countdown on an OLED, three buttons, a buzzer, a LiPo charged over USB-C")
    assert {"ssd1306-128x64", "tp4056"} <= kitchen
    assert "ssd1306-128x64" not in ids("Water leak alarm: a probe on a cable, a buzzer and a red LED, months of sleep on a LiPo")


def test_part_numbers_resolve_only_when_they_look_like_part_numbers():
    assert _explicit_parts("four SG90 servos and 60 WS2812B LEDs on an SX1278") == {"sg90": 4, "ws2812b_strip": 60, "lora_sx1278": 1}
    assert _explicit_parts("a servo, a relay and a fan") == {}
    assert "esp32-devkit" not in _explicit_parts("an ESP32-C3 board")


def test_brief_rules_correct_a_model_pick():
    """DeepSeek, through HS's model path, chose an Arduino Nano for 'An ESP32 distance meter' and no level shifter (26 Nov 2026)."""
    from hardware_splicer.module_picker import ModulePick, apply_brief_rules

    brief = "An ESP32 distance meter: an HC-SR04 ultrasonic sensor shows distance on a small OLED; four SG90 servos point it."
    fixed = apply_brief_rules(brief, ModulePick(module_ids=["arduino-nano", "hc-sr04", "ssd1306-128x64"], labels=[], hints=["model"]))
    assert "arduino-nano" not in fixed.module_ids and "esp32-devkit" in fixed.module_ids
    assert "level-shifter-4ch" in fixed.module_ids and fixed.quantities == {"sg90": 4} and "sg90" in fixed.module_ids
    untouched = apply_brief_rules("a weather display", ModulePick(module_ids=["arduino-nano", "bme280"], labels=[], hints=[]))
    assert untouched.module_ids == ["arduino-nano", "bme280"]  # no family named, no 5 V part on a 3.3 V controller
