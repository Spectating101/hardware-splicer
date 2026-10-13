"""The engineering review: every number sourced or assumed on the page, checked against a hand calculation."""
import copy
import json
import re

import pytest

from hardware_splicer.device_engineering import (
    ADVISORY, ASSUMED, EXCEEDS, NOT_ASSESSED, STANDARDS, WITHIN, build_engineering_review,
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
            if item["basis"] == "sourced" and item["name"] in STANDARDS:
                assert item["url"].startswith("https://")
            if item["basis"] == "sourced" and "url" in item:
                assert item["url"].startswith("https://"), (c["id"], item)
    names = {a["name"] for a in review["assumptions"]}
    assert names and names <= set(ASSUMED)
    # Sourced inputs are the standards table plus figures read from the module library, named after the module that holds them.
    for item in review["sourced_inputs"]:
        assert item["name"] in STANDARDS or "." in item["name"] or item["name"] == "io_v", item["name"]


def test_the_antenna_gap_agrees_with_the_plans_own_finding_and_is_judged_against_the_sourced_15_mm(bme):
    _spec, plan, review = bme
    finding = next(f for f in plan["findings"] if f["rule"] == "antenna_keepout")
    stated = float(re.search(r"in this layout is ([\d.]+) mm", finding["message"]).group(1))
    c = checks(review)["antenna_clearance"]
    assert c["quantities"]["gap_to_case_wall_mm"] == pytest.approx(stated)
    assert c["quantities"]["recommended_clearance_mm"] == 15
    assert c["status"] == EXCEEDS
    assert c["quantities"]["extra_case_length_needed_mm"] == pytest.approx(15 - stated)
    assert "at least 15 mm is recommended" in next(i for i in c["inputs"] if i["name"].endswith("antenna_clearance"))["source"]


def test_the_case_temperature_matches_a_hand_calculation(bme):
    _spec, plan, review = bme
    o = plan["case"]["outer_mm"]
    area = (o["x"] * o["z"] + 2 * o["x"] * o["y"] + 2 * o["z"] * o["y"]) / 1e6  # top and four sides; the bottom sits on a surface
    c = checks(review)["enclosure_temperature"]
    assert c["quantities"]["case_surface_area_m2"] == pytest.approx(area, abs=1e-4)
    # A floor: each peak current at the rail it was measured on (ESP32 transmit 379 mA at 3.3 V, BME280 pressure 0.714 mA at 1.8 V).
    watts = 3.3 * 0.379 + 1.8 * 0.000714
    assert c["quantities"]["heat_floor_w"]["peak_load"] == pytest.approx(watts, abs=0.005)
    assert c["quantities"]["case_surface_rise_k"]["peak_load"]["worst_k"] == pytest.approx(watts / (5.0 * area), abs=0.1)
    assert c["quantities"]["case_surface_rise_k"]["peak_load"]["best_k"] == pytest.approx(watts / (10.0 * area), abs=0.1)
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
    assert unknown["status"] == NOT_ASSESSED and unknown["quantities"]["pullups_unknown"] == ["display", "sensor"]  # none states a value
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
    assert c["quantities"]["sourced_peak_ma_upper_bound"] == pytest.approx(379.714)
    assert c["quantities"]["headroom_for_unsourced_loads_ma_at_least"] == pytest.approx(500 - 379.714)
    assert c["quantities"]["modules_without_a_sourced_current"] == ["display"]
    assert c["quantities"]["regulator"] == "not stated"  # the DevKitC sources do not say, so nothing about it is assumed
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


def _with_library(monkeypatch, edit):
    import hardware_splicer.device_engineering as module

    real = module.module_library

    def patched():
        library = real()
        edit({m["id"]: m for m in library["modules"]})
        return library

    monkeypatch.setattr(module, "module_library", patched)
    return module


def test_a_part_is_added_by_adding_data_and_the_review_reads_it_without_code(monkeypatch):
    spec = example_specs()["esp32_oled_bme280_usb"]
    before = checks(build_engineering_review(spec))["supply_current"]["quantities"]

    def give_the_display_a_current(modules):
        modules["ssd1306-096-i2c"]["engineering"]["loads"] = [{
            "mode": "Typical white text on black", "kind": "sustained", "typical_ma": 12.0, "max_ma": 20.0, "rail_v": 3.3,
            "conditions": "example row for this test", "locator": "test table", "source": modules["ssd1306-096-i2c"]["sources"][0]["url"]}]

    module = _with_library(monkeypatch, give_the_display_a_current)
    after = checks(module.build_engineering_review(spec))["supply_current"]["quantities"]
    assert after["sourced_peak_ma_upper_bound"] == pytest.approx(before["sourced_peak_ma_upper_bound"] + 20.0)
    assert after["modules_without_a_sourced_current"] == []


def test_a_part_with_no_data_is_listed_as_missing_not_assumed(monkeypatch):
    spec = example_specs()["esp32_oled_bme280_usb"]

    def strip(modules):
        modules["adafruit-bme280-stemma-qt"].pop("engineering")

    module = _with_library(monkeypatch, strip)
    review = module.build_engineering_review(spec)
    sensor = next(row for row in review["coverage"] if row["module"] == "sensor")
    assert sensor["sourced"] == []
    thermal = checks(review)["enclosure_temperature"]
    assert "sensor" in thermal["quantities"]["modules_without_a_sourced_limit"]
    assert "temperature_bias_sensor" not in checks(review)  # no sourced note, so no claim


def test_the_library_refuses_engineering_figures_without_a_source_or_with_nonsense():
    import copy

    from hardware_splicer.device_plan import _check_engineering, module_library

    library = {m["id"]: m for m in module_library()["modules"]}
    base = library["esp32-devkitc-v4"]
    urls = [s["url"] for s in base["sources"]]
    _check_engineering(base, urls)  # the shipped entry is valid

    def broken(edit):
        entry = copy.deepcopy(base)
        edit(entry)
        with pytest.raises(RuntimeError):
            _check_engineering(entry, urls)

    broken(lambda e: e["engineering"]["operating_temp_c"].update(source="https://example.com/not-a-source-of-this-module"))
    broken(lambda e: e["engineering"]["operating_temp_c"].update(min=90, max=85))
    broken(lambda e: e["engineering"]["operating_temp_c"].update(kind="typical"))
    broken(lambda e: e["engineering"]["operating_temp_c"].update(locator=""))
    broken(lambda e: e["engineering"]["loads"][0].update(kind="average"))
    broken(lambda e: e["engineering"]["loads"][0].pop("rail_v"))
    broken(lambda e: e["engineering"]["loads"][0].update(rail_v=0))
    broken(lambda e: e["engineering"]["loads"][1].update(max_ma=1))  # below its typical
    broken(lambda e: e["engineering"]["loads"][0].update(typical_ma=float("nan")))
    broken(lambda e: e["engineering"]["loads"][0].update(typical_ma=True))
    broken(lambda e: e["engineering"]["antenna"].update(end="not_an_overhang"))
    broken(lambda e: e["engineering"]["antenna"].update(clearance_mm=0))
    broken(lambda e: e["engineering"].update(invented_field=1))
    broken(lambda e: e["engineering"].update(gaps=[{"field": "x"}]))
    pull = copy.deepcopy(library["adafruit-bh1750-stemma-qt"])
    pull_urls = [s["url"] for s in pull["sources"]]
    _check_engineering(pull, pull_urls)
    pull["i2c"]["pullups"]["rail"] = "3v3"
    with pytest.raises(RuntimeError):
        _check_engineering(pull, pull_urls)


def test_every_shipped_module_with_figures_names_its_gaps_where_it_has_none():
    from hardware_splicer.device_plan import module_library

    for entry in module_library()["modules"]:
        eng = entry.get("engineering")
        assert eng is not None, f"{entry['id']} should state its engineering figures or its gaps"
        if "operating_temp_c" not in eng:
            assert any(g["field"] == "operating_temp_c" for g in eng["gaps"]), entry["id"]
        if not eng.get("loads"):
            assert any(g["field"] == "loads" for g in eng["gaps"]), entry["id"]
