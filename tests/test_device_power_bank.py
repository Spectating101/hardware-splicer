"""A device on a USB power bank: the same USB supply path, plus a runtime ceiling from the modules' published currents."""

from __future__ import annotations

import pytest

from hardware_splicer.device_draft import draft_device_spec
from hardware_splicer.device_engineering import ADVISORY, EXCEEDS, NOT_ASSESSED, build_engineering_review
from hardware_splicer.device_plan import DevicePlanError, build_device_plan


def _spec(power, parts=("adafruit-oled-1.3-128x64-stemma-qt", "adafruit-bme280-stemma-qt")):
    spec = draft_device_spec({"controller": "esp32-devkitc-v4", "parts": list(parts)})["spec"]
    spec["power"] = power
    return spec


def _runtime(review):
    return next(c for d in review["domains"] for c in d["checks"] if c["id"] == "power_bank_runtime")


def test_a_power_bank_plans_like_usb_and_says_so():
    plan = build_device_plan(_spec({"source": "usb_power_bank", "capacity_mah": 10000}))
    assert plan["counts"]["errors"] == 0
    assert plan["power"] == {"source": "usb_power_bank", "capacity_mah": 10000.0}
    assert "power_bank" in {f["rule"] for f in plan["findings"] if f["severity"] == "info"}


def test_runtime_ceiling_from_published_sustained_currents():
    """ESP32 Wi-Fi receive 112 mA + the OLED's 40 mA average (the BME280 publishes only microamps): 152 mA from 5 V."""

    review = build_engineering_review(_spec({"source": "usb_power_bank", "capacity_mah": 10000}))
    check = _runtime(review)
    q = check["quantities"]
    assert check["status"] == ADVISORY
    assert q["sourced_sustained_ma_at_usb"] == pytest.approx(152, abs=0.5)
    low, high = q["runtime_ceiling_h"]
    assert low == pytest.approx(10 * 3.7 * 0.8 / (0.152 * 5), abs=0.2) and high == pytest.approx(10 * 3.7 * 0.9 / (0.152 * 5), abs=0.2)
    assert "ceiling" in " ".join(check["limits"])
    assert review["firmware_authorized"] is False and review["power_on_authorized"] is False
    assert [i["name"] for i in review["given_inputs"]] == ["power.capacity_mah"]


def test_a_required_runtime_above_the_ceiling_exceeds_the_limit():
    review = build_engineering_review(_spec({"source": "usb_power_bank", "capacity_mah": 10000, "min_runtime_h": 48}))
    assert _runtime(review)["status"] == EXCEEDS
    review = build_engineering_review(_spec({"source": "usb_power_bank", "capacity_mah": 20000, "min_runtime_h": 48}))
    assert _runtime(review)["status"] == ADVISORY and "under the ceiling" in _runtime(review)["summary"]


def test_a_light_load_warns_about_auto_off(monkeypatch):
    """Every library controller draws over 100 mA, so the light load is a stand-in: 40 mA, under most banks' keep-alive."""

    from hardware_splicer import device_engineering

    real = device_engineering._loads
    monkeypatch.setattr(device_engineering, "_loads", lambda plan, library: {**real(plan, library), "sustained_ma": 40.0})
    check = _runtime(build_engineering_review(_spec({"source": "usb_power_bank", "capacity_mah": 5000})))
    assert "switch off" in check["summary"]
    monkeypatch.setattr(device_engineering, "_loads", lambda plan, library: {**real(plan, library), "sustained_ma": 0.0})
    assert _runtime(build_engineering_review(_spec({"source": "usb_power_bank", "capacity_mah": 5000})))["status"] == NOT_ASSESSED


def test_plain_usb_has_no_runtime_check():
    review = build_engineering_review(_spec({"source": "usb"}))
    assert all(c["id"] != "power_bank_runtime" for d in review["domains"] for c in d["checks"])


@pytest.mark.parametrize("power,match", [
    ({"source": "usb_power_bank"}, "capacity_mah"),
    ({"source": "usb_power_bank", "capacity_mah": 0}, "capacity_mah"),
    ({"source": "usb_power_bank", "capacity_mah": True}, "capacity_mah"),
    ({"source": "usb_power_bank", "capacity_mah": 10000, "cell_v": 12}, "cell_v"),
    ({"source": "usb_power_bank", "capacity_mah": 10000, "volts": 5}, "only"),
    ({"source": "usb", "capacity_mah": 10000}, "only to a usb_power_bank"),
])
def test_bad_power_bank_specs_are_refused(power, match):
    with pytest.raises(DevicePlanError, match=match):
        build_device_plan(_spec(power))


def test_an_unknown_source_is_still_an_error():
    plan = build_device_plan(_spec({"source": "lipo"}))
    assert "power_source_not_supported" in {f["rule"] for f in plan["findings"] if f["severity"] == "error"}
