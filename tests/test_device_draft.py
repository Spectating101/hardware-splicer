"""A draft wires a list of parts the plain way and hands the result to the planner, which keeps every verdict."""
import pytest
from fastapi.testclient import TestClient

from hardware_splicer.device_draft import MAX_PARTS, draft_device_spec
from hardware_splicer.device_plan import DevicePlanError, build_device_plan, example_specs
from hardware_splicer.product_api import create_product_app

ESP32, PICO = "esp32-devkitc-v4", "raspberry-pi-pico"
OLED, BME, BH = "ssd1306-096-i2c", "adafruit-bme280-stemma-qt", "adafruit-bh1750-stemma-qt"


@pytest.mark.parametrize("controller", [ESP32, PICO])
def test_a_drafted_spec_plans_without_errors_on_either_controller(controller):
    draft = draft_device_spec({"controller": controller, "parts": [OLED, BME]})
    plan = build_device_plan(draft["spec"])
    assert not [f for f in plan["findings"] if f["severity"] == "error"]
    assert draft["findings"] == plan["findings"]


def test_a_draft_of_the_published_example_parts_wires_the_same_pins_as_the_example():
    draft = draft_device_spec({"controller": ESP32, "parts": [OLED, BME]})
    reference = example_specs()["esp32_oled_bme280_usb"]
    assert {(c["from"], c["to"]) for c in draft["spec"]["connections"]} == {(c["from"], c["to"]) for c in reference["connections"]}


def test_two_parts_at_one_address_are_reported_by_the_planner_not_hidden():
    draft = draft_device_spec({"controller": ESP32, "parts": [BME, BME]})
    assert any(f["rule"] == "i2c_address_overlap" for f in draft["findings"])
    assert [m["id"] for m in draft["spec"]["modules"]] == ["mcu", "sensor", "sensor_2"]


def test_a_draft_states_what_it_assumed_and_claims_nothing():
    draft = draft_device_spec({"controller": PICO, "parts": [BH]})
    text = " ".join(draft["assumptions"]).lower()
    assert "default i2c bus" in text and "GP4" in " ".join(draft["assumptions"])
    assert not {"physical_correctness", "firmware_authorized", "power_on_authorized"} & set(draft)


@pytest.mark.parametrize("request_body, message", [
    ([], "must be an object"),
    ({"parts": [OLED]}, "controller must be"),
    ({"controller": ESP32, "parts": []}, "parts must be"),
    ({"controller": ESP32, "parts": [OLED] * (MAX_PARTS + 1)}, "parts must be"),
    ({"controller": ESP32, "parts": [7]}, "parts must be"),
    ({"controller": OLED, "parts": [BME]}, "not a controller"),
    ({"controller": ESP32, "parts": [PICO]}, "only displays and I2C breakouts"),
    ({"controller": "no-such-board", "parts": [OLED]}, ""),
    ({"controller": ESP32, "parts": ["no-such-part"]}, ""),
])
def test_bad_requests_are_refused_with_a_reason(request_body, message):
    with pytest.raises(DevicePlanError, match=message):
        draft_device_spec(request_body)


def test_the_draft_route_returns_a_spec_and_refuses_bad_input_with_a_422():
    client = TestClient(create_product_app())
    good = client.post("/v1/devices/draft", json={"controller": PICO, "parts": [OLED]})
    assert good.status_code == 200 and good.json()["spec"]["modules"][0]["module"] == PICO
    bad = client.post("/v1/devices/draft", json={"controller": PICO, "parts": ["no-such-part"]})
    assert bad.status_code == 422 and bad.json()["detail"]["type"] == "invalid_device_spec"
    assert client.post("/v1/devices/draft", content=b"not json").status_code == 422
