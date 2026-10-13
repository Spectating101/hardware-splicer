"""The engineering review: every number sourced or assumed on the page, checked against a hand calculation."""
import copy
import json
import re

import pytest

from hardware_splicer.device_engineering import (
    ADVISORY, ASSUMED, EXCEEDS, NOT_ASSESSED, SOURCED, WITHIN, build_engineering_review,
)
from hardware_splicer.device_parts import example_spec_for_part
from hardware_splicer.device_plan import DevicePlanError, build_device_plan, example_specs


def checks(review):
    return {c["id"]: c for d in review["domains"] for c in d["checks"]}


@pytest.fixture(scope="module")
def bme():
    spec = example_specs()["esp32_oled_bme280_usb"]
    return spec, build_device_plan(spec), build_engineering_review(spec)


def test_no_check_ever_says_pass_and_nothing_is_authorized(bme):
    _spec, _plan, review = bme
    allowed = {EXCEEDS, ADVISORY, WITHIN, NOT_ASSESSED}
    assert {c["status"] for c in checks(review).values()} <= allowed
    assert review["physical_correctness"] == "UNPROVEN"
    assert review["firmware_authorized"] is False and review["power_on_authorized"] is False
    assert sum(review["counts"].values()) == len(checks(review))
    assert review["not_assessed"] and all(row["why"] for row in review["not_assessed"])


def test_every_input_is_sourced_with_a_url_or_assumed_with_a_reason(bme):
    _spec, _plan, review = bme
    for c in checks(review).values():
        for item in c["inputs"]:
            assert item["basis"] in {"sourced", "assumed"}, (c["id"], item)
            assert item["source"].strip(), (c["id"], item)
            if item["basis"] == "sourced" and item["name"] in SOURCED:
                assert item["url"].startswith("https://")
    names = {a["name"] for a in review["assumptions"]}
    assert names and names <= set(ASSUMED)
    # Sourced inputs are the table above plus the two read from the module library and the Bosch note, each with its own source text.
    assert {s["name"] for s in review["sourced_inputs"]} - set(SOURCED) <= {"io_v", "bosch_note"}


def test_the_antenna_gap_agrees_with_the_plans_own_finding_and_is_judged_against_the_sourced_15_mm(bme):
    _spec, plan, review = bme
    finding = next(f for f in plan["findings"] if f["rule"] == "antenna_keepout")
    stated = float(re.search(r"in this layout is ([\d.]+) mm", finding["message"]).group(1))
    c = checks(review)["antenna_clearance"]
    assert c["quantities"]["gap_to_case_wall_mm"] == pytest.approx(stated)
    assert c["quantities"]["recommended_clearance_mm"] == 15
    assert c["status"] == EXCEEDS
    assert c["quantities"]["extra_case_length_needed_mm"] == pytest.approx(15 - stated)
    assert "15 mm is recommended" in next(i for i in c["inputs"] if i["name"] == "antenna_housing_clearance_mm")["source"]


def test_the_case_temperature_matches_a_hand_calculation(bme):
    _spec, plan, review = bme
    o = plan["case"]["outer_mm"]
    area = (o["x"] * o["z"] + 2 * o["x"] * o["y"] + 2 * o["z"] * o["y"]) / 1e6  # top and four sides; the bottom sits on a surface
    c = checks(review)["enclosure_temperature"]
    assert c["quantities"]["case_surface_area_m2"] == pytest.approx(area, abs=1e-4)
    watts = 5.0 * 0.379
    assert c["quantities"]["input_power_w"]["wifi_transmit_continuous_peak"] == pytest.approx(watts, abs=0.01)
    assert c["quantities"]["case_surface_rise_k"]["wifi_transmit_continuous_peak"]["worst_k"] == pytest.approx(watts / (5.0 * area), abs=0.1)
    assert c["quantities"]["case_surface_rise_k"]["wifi_transmit_continuous_peak"]["best_k"] == pytest.approx(watts / (10.0 * area), abs=0.1)
    assert c["status"] in {ADVISORY, EXCEEDS}  # a surface floor can never clear the parts inside
    assert any("surface only" in text for text in c["limits"])


def test_a_surface_floor_over_the_lowest_sourced_limit_is_reported_as_exceeded(monkeypatch):
    import hardware_splicer.device_engineering as module

    hot = dict(ASSUMED)
    hot["convection_w_per_m2k"] = ((0.5, 1.0), "W/m2K", "a sealed box with no airflow at all")
    monkeypatch.setattr(module, "ASSUMED", hot)
    review = module.build_engineering_review(example_specs()["esp32_oled_usb"])
    assert checks(review)["enclosure_temperature"]["status"] == EXCEEDS


def test_the_temperature_sensor_is_flagged_by_its_distance_to_the_controller_board(bme):
    _spec, plan, review = bme
    sensor = next(m for m in plan["modules"] if m["id"] == "sensor")
    mcu = next(m for m in plan["modules"] if m["id"] == "mcu")
    gap_z = max(mcu["box"]["z0"] - sensor["box"]["z1"], sensor["box"]["z0"] - mcu["box"]["z1"], 0)
    c = checks(review)["temperature_bias_sensor"]
    assert c["quantities"]["gap_to_controller_board_mm"] == pytest.approx(gap_z, abs=0.1)
    assert c["status"] == ADVISORY and "above the room" in c["summary"]
    assert "temperature_bias_sensor" not in checks(build_engineering_review(example_specs()["esp32_oled_usb"]))


def test_unknown_pullups_are_not_assessed_and_stated_ones_follow_the_i2c_rise_time_formula():
    unknown = checks(build_engineering_review(example_specs()["esp32_oled_bme280_usb"]))["i2c_bus"]
    assert unknown["status"] == NOT_ASSESSED and unknown["quantities"]["pullups_unknown"] == ["display", "sensor"]
    spec = example_spec_for_part("adafruit-bh1750-stemma-qt")
    c = checks(build_engineering_review(spec))["i2c_bus"]
    assert c["quantities"]["pullups_known"] == [{"module": "sensor", "ohm": 10000}]
    assert c["quantities"]["rp_effective_ohm"] == 10000
    assert c["quantities"]["bus_capacitance_tolerated_pf"] == pytest.approx(1000e-9 / (0.8473 * 10000) * 1e12, abs=0.1)
    assert c["quantities"]["rp_min_ohm"] == pytest.approx((3.3 - 0.4) / 0.003, abs=1)
    assert c["status"] == WITHIN
    assert "unknown" in " ".join(c["limits"]).lower() or "do not state" in " ".join(c["limits"]).lower()


def test_a_heavily_loaded_bus_is_reported_as_exceeded(monkeypatch):
    import hardware_splicer.device_engineering as module

    loaded = dict(ASSUMED)
    loaded["wire_pf_per_m"] = ((3000.0, 6000.0), "pF/m", "an absurdly capacitive cable")
    monkeypatch.setattr(module, "ASSUMED", loaded)
    review = module.build_engineering_review(example_spec_for_part("adafruit-bh1750-stemma-qt"))
    assert checks(review)["i2c_bus"]["status"] == EXCEEDS


def test_the_supply_check_reports_what_is_unsourced_instead_of_guessing(bme):
    _spec, _plan, review = bme
    c = checks(review)["supply_current"]
    assert c["quantities"]["sourced_peak_ma"] == 379 and c["quantities"]["headroom_for_unsourced_loads_ma"] == 121
    assert set(c["quantities"]["modules_without_a_sourced_current"]) == {"display", "sensor"}
    assert c["quantities"]["if_linear_regulator_dissipation_w"] == pytest.approx(1.7 * 0.379, abs=0.01)
    assert c["status"] == ADVISORY


def test_gaps_and_the_usb_board_travel_come_from_the_plans_layout(bme):
    _spec, plan, review = bme
    c = checks(review)["usb_insertion_support"]
    assert c["quantities"]["board_travel_mm"] == pytest.approx(1.0, abs=0.01)
    fit = checks(review)["module_to_wall_gaps"]
    assert fit["quantities"]["smallest"]["gap_mm"] == pytest.approx(1.0, abs=0.01)
    assert {g["module"] for g in fit["quantities"]["all"]} == {"mcu", "display", "sensor"}


def test_a_plan_with_errors_is_refused_and_a_supplied_plan_is_ignored():
    spec = copy.deepcopy(example_specs()["esp32_oled_usb"])
    honest = build_engineering_review(copy.deepcopy(spec))
    spec["plan"] = {"case": {"outer_mm": {"x": 1, "y": 1, "z": 1}}}
    assert build_engineering_review(spec) == honest
    bad = copy.deepcopy(example_specs()["esp32_oled_usb"])
    bad["connections"].append({"from": "display.VCC", "to": "mcu.GND"})
    with pytest.raises(DevicePlanError):
        build_engineering_review(bad)


def test_the_http_endpoint_returns_the_same_review(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from hardware_splicer.product_api import create_product_app
    from hardware_splicer.project_store import ProjectStore

    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    client = TestClient(create_product_app(ProjectStore(tmp_path / "store")))
    spec = example_specs()["esp32_oled_bme280_usb"]
    response = client.post("/v1/devices/engineering", json=spec)
    assert response.status_code == 200
    body = response.json()
    assert body.pop("ok") is True and body == build_engineering_review(spec)
    assert client.post("/v1/devices/engineering", content=b"nope").status_code == 422
