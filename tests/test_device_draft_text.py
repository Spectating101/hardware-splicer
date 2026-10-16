"""A parts list typed as plain text becomes a draft, and every line says what it was matched to, or that nothing matched.

The matcher only names library modules. It never guesses a part the library does not hold, never reads a variant
(ESP32-S3) as the listed board, and says when a match rests on a generic word such as "OLED" rather than a chip name.
"""
import pytest
from fastapi.testclient import TestClient

from hardware_splicer.device_draft import draft_from_parts_text, parse_parts_text
from hardware_splicer.device_plan import DevicePlanError, build_device_plan
from hardware_splicer.product_api import create_product_app

ESP32, PICO = "esp32-devkitc-v4", "raspberry-pi-pico"
OLED, BME, BH = "ssd1306-096-i2c", "adafruit-bme280-stemma-qt", "adafruit-bh1750-stemma-qt"
MPU, DS, INA, ADS = "adafruit-mpu-6050-stemma-qt", "adafruit-ds3231-stemma-qt", "adafruit-ina219-stemma-qt", "adafruit-ads1115-stemma-qt"


def _modules(parsed):
    return [(m["module"], m["quantity"]) for f in parsed["fragments"] for m in f["matches"]]


def test_one_part_per_line_gives_the_controller_and_the_parts_in_the_order_typed():
    parsed = parse_parts_text("ESP32\nBME280\n0.96 inch OLED")
    assert parsed["controller"] == ESP32
    assert parsed["parts"] == [BME, OLED]
    assert parsed["left_out"] == []


def test_a_sentence_is_split_on_commas_and_joining_words():
    parsed = parse_parts_text("a Raspberry Pi Pico with a BH1750 and an SSD1306 display, plus a DS3231")
    assert parsed["controller"] == PICO
    assert parsed["parts"] == [BH, OLED, DS]


@pytest.mark.parametrize("typed", ["MPU-6050", "mpu6050", "MPU 6050", "Mpu-6050 breakout"])
def test_hyphens_spaces_and_case_do_not_matter(typed):
    assert parse_parts_text(f"pico\n{typed}")["parts"] == [MPU]


def test_a_quantity_written_as_2x_or_x2_repeats_the_part():
    parsed = parse_parts_text("esp32, 2x MPU6050, INA219 x2, ADS1115")
    assert parsed["parts"] == [MPU, MPU, INA, INA, ADS]
    assert (MPU, 2) in _modules(parsed) and (INA, 2) in _modules(parsed)


@pytest.mark.parametrize("typed", ["128x64 OLED", "0.96 inch OLED", "1 OLED"])
def test_sizes_and_resolutions_are_not_read_as_quantities(typed):
    assert parse_parts_text(f"esp32\n{typed}")["parts"] == [OLED]


def test_a_variant_of_a_listed_board_is_not_read_as_that_board():
    parsed = parse_parts_text("ESP32-S3 devkit\nBME280")
    assert parsed["controller"] is None
    assert "ESP32-S3 devkit" in parsed["left_out"]
    assert parse_parts_text("esp32s3\nBME280")["controller"] is None


def test_parts_the_library_does_not_hold_are_left_out_and_named():
    parsed = parse_parts_text("pico\nBME280\nSH1106 1.3 inch display\nHC-SR04 ultrasonic")
    assert parsed["parts"] == [BME]
    assert parsed["left_out"] == ["SH1106 1.3 inch display", "HC-SR04 ultrasonic"]
    unmatched = [f for f in parsed["fragments"] if not f["matches"]]
    assert [f["text"] for f in unmatched] == parsed["left_out"]


def test_every_match_says_whether_it_rests_on_a_chip_name_or_a_generic_word():
    parsed = parse_parts_text("esp32\nBME280\nOLED")
    basis = {m["module"]: m["basis"] for f in parsed["fragments"] for m in f["matches"]}
    assert basis[BME] == "chip"
    assert basis[OLED] == "generic_word"
    for fragment in parsed["fragments"]:
        for match in fragment["matches"]:
            assert match["name"] and match["matched_on"]


def test_drafting_from_text_returns_the_planners_findings_and_claims_nothing():
    draft = draft_from_parts_text({"text": "ESP32\nBME280\nOLED"})
    assert draft["parsed"]["controller"] == ESP32
    plan = build_device_plan(draft["spec"])
    assert draft["findings"] == plan["findings"]
    assert not [f for f in plan["findings"] if f["severity"] == "error"]
    assert not {"physical_correctness", "firmware_authorized", "power_on_authorized"} & set(draft)
    assert draft["assumptions"]


def test_two_parts_at_one_address_still_reach_the_planner():
    draft = draft_from_parts_text({"text": "esp32, 2x BME280"})
    assert any(f["rule"] == "i2c_address_overlap" for f in draft["findings"])


@pytest.mark.parametrize("text, message", [
    ("BME280\nOLED", "controller"),
    ("esp32\npico\nBME280", "one controller"),
    ("esp32", "part"),
    ("esp32\nHC-SR04", "part"),
    ("", "text"),
    ("esp32\n" + "BME280\n" * 9, "at most"),
    ("esp32\nBME​280", "invisible"),
    ("x" * 2001, "at most"),
])
def test_text_that_cannot_make_a_draft_is_refused_with_a_reason(text, message):
    with pytest.raises(DevicePlanError, match=message):
        draft_from_parts_text({"text": text})


def test_the_draft_route_accepts_text_and_still_accepts_ids():
    client = TestClient(create_product_app())
    typed = client.post("/v1/devices/draft", json={"text": "pico\nBH1750"})
    assert typed.status_code == 200
    body = typed.json()
    assert body["parsed"]["controller"] == PICO and body["spec"]["modules"][0]["module"] == PICO
    ids = client.post("/v1/devices/draft", json={"controller": PICO, "parts": [OLED]})
    assert ids.status_code == 200 and "parsed" not in ids.json()
    bad = client.post("/v1/devices/draft", json={"text": "BME280"})
    assert bad.status_code == 422 and bad.json()["detail"]["type"] == "invalid_device_spec"


@pytest.mark.parametrize("typed", ["ESP32 S3", "esp32 C3 devkit", "Pico W", "Raspberry Pi Pico 2", "Pico 2 W", "RP2350 board"])
def test_space_separated_variants_are_not_the_listed_board_and_say_why(typed):
    parsed = parse_parts_text(f"{typed}\nBME280")
    assert parsed["controller"] is None
    fragment = parsed["fragments"][0]
    assert fragment["matches"] == [] and fragment["text"] in parsed["left_out"]
    assert "different board" in fragment["note"]


def test_the_listed_boards_full_names_and_suffix_quantities_still_match():
    assert parse_parts_text("ESP32 DevKitC V4\nBME280 x2")["parts"] == [BME, BME]
    assert parse_parts_text("Raspberry Pi Pico\nBH1750")["controller"] == PICO
    assert "note" not in parse_parts_text("pico\nBME280")["fragments"][0]


def test_windows_line_endings_and_tabs_are_accepted():
    parsed = parse_parts_text("ESP32\r\nBME280\r\n\tOLED")
    assert parsed["controller"] == ESP32 and parsed["parts"] == [BME, OLED]
