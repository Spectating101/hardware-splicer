"""A typed parts line may name more than the library part it matched. The reader must not let that extra part vanish.

Two red-team findings: "BME280 alongside an HC-SR04 ultrasonic" read as one BME280 with nothing left out, and
"2 BME280" read as one BME280. A mission holds a candidate to the person's list, so a part the reader silently
dropped is a part a mission could silently drop.
"""
import pytest

from hardware_splicer.device_draft import parse_parts_text

ESP32, PICO = "esp32-devkitc-v4", "raspberry-pi-pico"
OLED, BME, MPU = "ssd1306-096-i2c", "adafruit-bme280-stemma-qt", "adafruit-mpu-6050-stemma-qt"


@pytest.mark.parametrize("typed, unread", [
    ("BME280 alongside an HC-SR04 ultrasonic", ["HC-SR04"]),
    ("BME280 next to a VL53L0X", ["VL53L0X"]),
    ("BME280 / SHT31", ["SHT31"]),
    ("MPU6050 or an ICM-20948", ["ICM-20948"]),
])
def test_a_part_number_beside_a_matched_part_is_unread_and_left_out(typed, unread):
    parsed = parse_parts_text(f"esp32\n{typed}")
    fragment = parsed["fragments"][1]
    assert fragment["matches"], "the library part on the line is still matched"
    assert fragment["unread"] == unread
    assert typed in parsed["left_out"]


@pytest.mark.parametrize("typed, parts", [
    ("2 BME280", [BME, BME]),
    ("3 MPU6050", [MPU, MPU, MPU]),
    ("1 OLED", [OLED]),
])
def test_a_bare_leading_count_is_a_quantity(typed, parts):
    assert parse_parts_text(f"pico\n{typed}")["parts"] == parts


@pytest.mark.parametrize("typed", [
    "ESP32\nBME280\n0.96 inch OLED",
    "ESP32 DevKitC V4\nBME280 x2",
    "ESP32-DevKitC V4 (ESP32-WROOM-32E)\nBME280",
    "Raspberry Pi Pico\nBH1750\nDS3231\nOLED",
    "Raspberry Pi Pico\n2x BME280",
    "esp32\n128x64 OLED",
    'esp32\n0.96" OLED',
    "esp32\nSSD1306 0.96 inch 128x64 display",
    "pico\nMpu-6050 breakout",
    "pico\nAdafruit BME280 I2C/SPI breakout",
    "a Raspberry Pi Pico with a BH1750 and an SSD1306 display, plus a DS3231",
    "esp32\nBME280 3.3V breakout",
    "esp32\n0.96 inch 128x64 I2C OLED",
])
def test_ordinary_lines_read_exactly_as_before(typed):
    parsed = parse_parts_text(typed)
    assert all(not f.get("unread") for f in parsed["fragments"]), parsed
    assert all(f["matches"] for f in parsed["fragments"]), parsed
    assert parsed["left_out"] == []


def test_unread_text_on_an_unmatched_line_is_not_reported_twice():
    parsed = parse_parts_text("pico\nBME280\nHC-SR04 ultrasonic")
    assert parsed["left_out"] == ["HC-SR04 ultrasonic"]
    assert "unread" not in parsed["fragments"][2]


def test_one_line_naming_one_module_twice_counts_it_once():
    parsed = parse_parts_text("ESP32-DevKitC V4 (ESP32-WROOM-32E)\nBME280")
    assert parsed["fragments"][0]["matches"] == [parsed["fragments"][0]["matches"][0]]
    assert parsed["controller"] == ESP32 and parsed["parts"] == [BME]
