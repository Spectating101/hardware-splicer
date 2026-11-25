"""The offline picker on real briefs: named part numbers, counts, and hints that used to pick the wrong part.

Briefs come from the 26 Nov 2026 head-to-head (examples/head_to_head/agent_tools_20261126.json) and from Formwright's
published example projects, which HS did not write.
"""

from __future__ import annotations

from hardware_splicer.module_picker import _pick_modules_regex


def ids(text):
    return set(_pick_modules_regex(text).module_ids)


def test_an_led_strip_is_a_strip_not_a_display():
    got = ids("An ESP32 desk light: a strip of 60 WS2812B LEDs showing colour scenes, powered from a USB phone charger.")
    assert "ws2812b_strip" in got and "ssd1306-128x64" not in got


def test_a_robot_arm_gets_servos_not_a_wheel_motor_driver():
    got = ids("A small desk robot arm: four SG90 servos moved by an ESP32 from a phone app over Wi-Fi.")
    assert "sg90" in got and "l298n" not in got
    assert "l298n" in ids("A plant watering robot that drives around the greenhouse on two DC motors")


def test_a_lora_node_on_a_cell_gets_a_radio_and_a_charger_and_no_usb_supply():
    got = ids("A LoRa soil moisture sensor running from one 18650 cell that sends a reading every 10 minutes.")
    assert {"lora_sx1278", "soil_moisture", "tp4056"} <= got and "usb-power-5v" not in got


def test_formwright_examples_get_their_named_parts():
    assert {"bme280", "ssd1306-128x64"} <= ids("Desk weather station: BME280 and an OLED in the lid, a wedge on a 25 degree stand, USB-C power")
    kitchen = ids("Kitchen timer: a countdown on an OLED, three buttons, a buzzer, a LiPo charged over USB-C")
    assert {"ssd1306-128x64", "tp4056"} <= kitchen
    assert "ssd1306-128x64" not in ids("Water leak alarm: a probe on a cable, a buzzer and a red LED, months of sleep on a LiPo")
