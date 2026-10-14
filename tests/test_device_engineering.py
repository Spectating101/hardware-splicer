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


def test_the_case_meets_the_antenna_clearance_at_its_end_but_the_review_still_checks_every_other_direction(bme):
    _spec, plan, review = bme
    finding = next(f for f in plan["findings"] if f["rule"] == "antenna_keepout")
    stated = float(re.search(r"in this layout is ([\d.]+) mm", finding["message"]).group(1))
    c = checks(review)["antenna_clearance"]
    assert stated == pytest.approx(15, abs=0.01)
    assert c["quantities"]["gap_to_case_wall_mm"] == pytest.approx(stated)
    assert c["quantities"]["recommended_clearance_mm"] == 15
    assert c["quantities"]["extra_case_length_needed_mm"] == 0
    # The source says "in all directions". The case is lengthened at the antenna end only, so across it is as tight as the
    # boards: that is not within the recommendation, and the review says so instead of judging one axis.
    mcu = next(m for m in plan["modules"] if m["id"] == "mcu")
    half_z = plan["case"]["inner_mm"]["z"] / 2
    side = min(mcu["box"]["z0"] + half_z, half_z - mcu["box"]["z1"])
    assert c["quantities"]["gaps_by_direction_mm"]["side_walls_at_least"] == pytest.approx(side, abs=0.01)
    assert side < 15 and c["status"] == ADVISORY and "a side wall" in c["summary"]


def test_the_nearest_module_is_measured_from_the_antenna_ends_footprint_not_from_its_tip(bme):
    _spec, plan, review = bme
    mcu = next(m for m in plan["modules"] if m["id"] == "mcu")
    display = next(m for m in plan["modules"] if m["id"] == "display")
    # The display lies on the -x side of the antenna end and across the same z band, so the gap is from the board's +x
    # edge, where the antenna end starts, to the display's +x edge.
    expected = mcu["box"]["x1"] - display["box"]["x1"]
    got = checks(review)["antenna_clearance"]["quantities"]["antenna_end_to_nearest_other_module_mm"]
    assert got == pytest.approx(expected, abs=0.01)
    assert got < expected + mcu["overhang_mm"]["antenna_end"] - 1  # not inflated by the antenna's own length


def test_a_case_that_opts_out_of_the_antenna_clearance_is_reported_as_too_short():
    spec = copy.deepcopy(example_specs()["esp32_oled_bme280_usb"])
    spec["case"]["antenna_clearance"] = False
    plan = build_device_plan(spec)
    stated = float(re.search(r"in this layout is ([\d.]+) mm", next(f for f in plan["findings"] if f["rule"] == "antenna_keepout")["message"]).group(1))
    c = checks(build_engineering_review(spec))["antenna_clearance"]
    assert stated == 1.0 and c["status"] == EXCEEDS
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
    assert c["quantities"]["heat_w_at_measured_rails"]["peak_load"] == pytest.approx(watts, abs=0.005)
    assert c["quantities"]["case_surface_rise_k"]["peak_load"]["worst_k"] == pytest.approx(watts / (5.0 * area), abs=0.1)
    assert c["quantities"]["case_surface_rise_k"]["peak_load"]["best_k"] == pytest.approx(watts / (10.0 * area), abs=0.1)
    assert c["status"] in {ADVISORY, EXCEEDS}  # a surface estimate can never clear the parts inside
    # A range from the convection assumption, at the warm ambient: never called a floor or "at least".
    hot = ASSUMED["ambient_c"][0][1]
    surface = c["quantities"]["surface_c_at_warm_ambient"]["peak_load"]
    assert surface["low"] == pytest.approx(hot + watts / (10.0 * area), abs=0.2)
    assert surface["high"] == pytest.approx(hot + watts / (5.0 * area), abs=0.2)
    assert "at least" not in c["summary"] and "floor" not in " ".join(c["quantities"])
    assert any("surface only" in text for text in c["limits"])


def test_the_case_is_over_its_limit_only_when_even_the_sustained_load_with_the_better_convection_reaches_it(monkeypatch):
    import hardware_splicer.device_engineering as module

    def review_with(h):
        changed = dict(ASSUMED)
        changed["convection_w_per_m2k"] = (h, "W/m2K", "a test value")
        monkeypatch.setattr(module, "ASSUMED", changed)
        c = checks(module.build_engineering_review(example_specs()["esp32_oled_usb"]))["enclosure_temperature"]
        return c, c["quantities"]["surface_c_at_warm_ambient"], c["quantities"]["lowest_sourced_operating_limit_c"]

    # Only the transmit peak with the worse convection reaches the limit: that needs checking, it is not "over a limit".
    c, surface, limit = review_with((0.5, 1.0))
    assert surface["peak_load"]["high"] >= limit and surface["sustained_load"]["low"] < limit
    assert c["status"] == ADVISORY
    # The steady load with the better convection reaches it as well: now it is over the limit.
    c, surface, limit = review_with((0.2, 0.4))
    assert surface["sustained_load"]["low"] >= limit and c["status"] == EXCEEDS


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
    # The display on the same bus does not state its pull-ups. Any it has are in parallel: they help the rise time and
    # can break the sink limit, so the stated values alone cannot close the check.
    assert c["quantities"]["pullups_unknown"] == ["display"]
    assert c["status"] == ADVISORY and "display does not state its pull-ups" in c["summary"]


def test_a_bus_whose_every_module_states_its_pull_ups_is_judged_on_them():
    from hardware_splicer.device_draft import draft_device_spec

    spec = draft_device_spec({"controller": "esp32-devkitc-v4", "parts": ["adafruit-bh1750-stemma-qt"]})["spec"]
    c = checks(build_engineering_review(spec))["i2c_bus"]
    assert c["quantities"]["pullups_unknown"] == [] and c["quantities"]["rp_effective_ohm"] == 10000
    assert c["status"] == WITHIN


def test_the_low_capacitance_estimate_is_the_wire_alone_because_pin_capacitance_has_only_a_maximum(bme):
    _spec, plan, review = bme
    c = checks(review)["i2c_bus"]
    low_wire = ASSUMED["wire_pf_per_m"][0][0]
    longest = max(c["quantities"]["wire_length_m"].values())
    assert c["quantities"]["bus_capacitance_pf_estimate"]["low"] == pytest.approx(longest * low_wire, abs=0.15)


def test_a_heavily_loaded_bus_is_reported_as_exceeded(monkeypatch):
    import hardware_splicer.device_engineering as module

    loaded = dict(ASSUMED)
    loaded["wire_pf_per_m"] = ((10000.0, 20000.0), "pF/m", "an absurdly capacitive cable")
    monkeypatch.setattr(module, "ASSUMED", loaded)
    from hardware_splicer.device_draft import draft_device_spec

    # Every module on this bus states its pull-ups, so the stated resistance is the resistance and a verdict can be given.
    review = module.build_engineering_review(draft_device_spec({"controller": "esp32-devkitc-v4", "parts": ["adafruit-bh1750-stemma-qt"]})["spec"])
    c = checks(review)["i2c_bus"]
    # Over the limit only because even the low estimate, the wire alone, is more than the pull-up can drive.
    assert c["quantities"]["bus_capacitance_pf_estimate"]["low"] > c["quantities"]["bus_capacitance_tolerated_pf"]
    assert c["status"] == EXCEEDS


def test_the_supply_check_reports_what_is_unsourced_instead_of_guessing(bme):
    _spec, _plan, review = bme
    c = checks(review)["supply_current"]
    assert c["quantities"]["sourced_peak_ma_sum"] == pytest.approx(379.714)
    assert c["quantities"]["port_budget_left_after_sourced_peaks_ma"] == pytest.approx(500 - 379.714)
    # The ESP32's datasheet asks for a 0.5 A supply for the module alone: the summary says the port leaves no margin by that
    # measure, before it says how much is "left over" from the published peaks.
    assert c["summary"].startswith("The controller's datasheet asks for a supply that can deliver at least 0.5 A")
    assert "at most" not in c["summary"] and "at least 120" not in c["summary"]
    assert c["quantities"]["modules_without_a_sourced_current"] == ["display"]
    assert c["quantities"]["regulator"] == "not stated"  # the DevKitC sources do not say, so nothing about it is assumed
    assert c["status"] == ADVISORY


def test_gaps_and_the_usb_board_travel_come_from_the_plans_layout(bme):
    _spec, plan, review = bme
    c = checks(review)["usb_insertion_support"]
    assert c["status"] == WITHIN and c["quantities"]["stop_count"] == 2 and c["quantities"]["board_travel_mm"] == 0.5
    assert any("strength is not assessed" in text for text in c["limits"])
    fit = checks(review)["module_to_wall_gaps"]
    assert fit["quantities"]["smallest"]["gap_mm"] == pytest.approx(1.0, abs=0.01)
    bare = copy.deepcopy(_spec)
    bare["case"].update(antenna_clearance=False, board_stops=False)
    unprotected = checks(build_engineering_review(bare))["usb_insertion_support"]
    assert unprotected["status"] == ADVISORY and unprotected["quantities"]["board_travel_mm"] == pytest.approx(1.0, abs=0.01)
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
    assert after["sourced_peak_ma_sum"] == pytest.approx(before["sourced_peak_ma_sum"] + 20.0)
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


# --- figures that carry the words they were read from ------------------------------------------------------------------


def _with_clock_and_imu():
    from hardware_splicer.device_draft import draft_device_spec

    return draft_device_spec({"controller": "esp32-devkitc-v4", "parts": ["adafruit-ds3231-stemma-qt", "adafruit-mpu-6050-stemma-qt"]})["spec"]


def test_a_figure_may_carry_a_verbatim_quote_but_it_must_be_text():
    from hardware_splicer.device_plan import _check_engineering, module_library

    library = {m["id"]: m for m in module_library()["modules"]}
    entry = copy.deepcopy(library["adafruit-bme280-stemma-qt"])
    urls = [s["url"] for s in entry["sources"]]
    assert entry["engineering"]["operating_temp_c"]["quote"].startswith("Operating range")
    _check_engineering(entry, urls)
    for edit in (lambda e: e["engineering"]["operating_temp_c"].update(quote=""),
                 lambda e: e["engineering"]["operating_temp_c"].update(quote=5),
                 lambda e: e["engineering"]["loads"][0].update(quote=None)):
        broken = copy.deepcopy(entry)
        edit(broken)
        with pytest.raises(RuntimeError):
            _check_engineering(broken, urls)


def test_a_peak_row_may_state_only_the_maximum_a_datasheet_publishes_but_a_sustained_row_may_not():
    from hardware_splicer.device_plan import _check_engineering, module_library

    library = {m["id"]: m for m in module_library()["modules"]}
    clock = copy.deepcopy(library["adafruit-ds3231-stemma-qt"])
    urls = [s["url"] for s in clock["sources"]]
    assert all("typical_ma" not in row and row["kind"] == "peak" for row in clock["engineering"]["loads"])
    _check_engineering(clock, urls)
    for edit in (lambda e: e["engineering"]["loads"][0].update(kind="sustained"),   # nothing typical to sustain on
                 lambda e: e["engineering"]["loads"][0].pop("max_ma"),               # and no figure at all
                 lambda e: e["engineering"]["loads"][0].update(max_ma=-1)):
        broken = copy.deepcopy(clock)
        edit(broken)
        with pytest.raises(RuntimeError):
            _check_engineering(broken, urls)


def test_the_bme280_pressure_row_no_longer_borrows_the_one_hertz_average_as_a_typical():
    from hardware_splicer.device_plan import module_library

    rows = {m["id"]: m for m in module_library()["modules"]}["adafruit-bme280-stemma-qt"]["engineering"]["loads"]
    pressure = next(r for r in rows if r["mode"] == "Pressure measurement")
    assert "typical_ma" not in pressure and pressure["max_ma"] == 0.714
    assert next(r for r in rows if r["kind"] == "sustained")["typical_ma"] == 0.0036


def test_the_clock_and_the_motion_sensor_now_state_their_figures_and_the_supply_total_counts_them():
    from hardware_splicer.device_plan import module_library

    library = {m["id"]: m for m in module_library()["modules"]}
    for module_id in ("adafruit-ds3231-stemma-qt", "adafruit-mpu-6050-stemma-qt"):
        eng = library[module_id]["engineering"]
        assert eng["gaps"] == [] and eng["loads"] and eng["operating_temp_c"]["quote"]
    review = build_engineering_review(_with_clock_and_imu())
    supply = checks(review)["supply_current"]["quantities"]
    assert supply["modules_without_a_sourced_current"] == []
    # Its worst published figure, 575 uA, is in the peak total beside the controller's.
    sourced = [i for i in checks(review)["supply_current"]["inputs"] if i["name"].startswith("adafruit-ds3231")]
    assert sourced and max(i["value"] for i in sourced) == pytest.approx(0.575)


def test_every_shipped_engineering_figure_carries_the_words_it_was_read_from():
    """A locator says where to look; only a quote can be checked. The words themselves are checked against the cited
    document by scripts/verify_device_module_quotes.py, which needs the captured pages and so does not run here."""
    from hardware_splicer.device_plan import module_library

    missing = []
    for entry in module_library()["modules"]:
        eng = entry.get("engineering", {})
        rows = [(name, eng[name]) for name in ("operating_temp_c", "supply_min_a", "power_stage") if name in eng]
        rows += [(f"loads[{i}]", row) for i, row in enumerate(eng.get("loads", []))]
        missing += [f"{entry['id']}.{name}" for name, row in rows if not str(row.get("quote", "")).strip()]
    assert missing == []


def test_no_check_lists_two_inputs_under_one_name_even_when_a_module_has_two_rows_of_a_kind():
    import collections

    from hardware_splicer.device_draft import draft_device_spec

    specs = [example_specs()["esp32_oled_bme280_usb"],
             draft_device_spec({"controller": "esp32-devkitc-v4", "parts": ["adafruit-ds3231-stemma-qt", "adafruit-mpu-6050-stemma-qt"]})["spec"],
             draft_device_spec({"controller": "raspberry-pi-pico", "parts": ["adafruit-ds3231-stemma-qt"]})["spec"]]
    for spec in specs:
        for check in checks(build_engineering_review(spec)).values():
            names = collections.Counter(item["name"] for item in check["inputs"])
            assert [name for name, count in names.items() if count > 1] == [], check["id"]


def test_a_module_that_publishes_only_peaks_is_named_and_not_silently_left_out_of_the_sustained_sum():
    from hardware_splicer.device_draft import draft_device_spec

    spec = draft_device_spec({"controller": "esp32-devkitc-v4", "parts": ["adafruit-ds3231-stemma-qt"]})["spec"]
    c = checks(build_engineering_review(spec))["supply_current"]
    assert c["quantities"]["modules_with_only_peak_figures"] == ["sensor"]
    assert "only peak figures" in c["summary"]
