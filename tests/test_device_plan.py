"""The whole-device plan: modules, wires and a case, checked against pin roles. It is a proposal and approves nothing."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.device_plan import DevicePlanError, build_device_plan, example_specs, module_library
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore

EXAMPLE = example_specs()["esp32_oled_usb"]


def _with(connections: list[dict]) -> dict:
    spec = copy.deepcopy(EXAMPLE)
    spec["connections"] = connections
    return spec


def _rules(plan: dict, severity: str | None = None) -> set[str]:
    return {f["rule"] for f in plan["findings"] if severity is None or f["severity"] == severity}


GOOD = EXAMPLE["connections"]
ADVISORY_RULES = {"oled_supply_note", "i2c_pullups_note", "single_power_supply", "pin_order_assumed", "supply_current", "antenna_keepout", "kit_fit"}


def test_the_library_names_a_source_for_every_module_and_says_what_is_typical() -> None:
    library = module_library()
    assert [m["id"] for m in library["modules"]] == ["esp32-devkitc-v4", "ssd1306-096-i2c"]
    for module in library["modules"]:
        assert module["sources"] and all(s["url"].startswith("https://") and s["as_of"] for s in module["sources"])
        assert module["dimension_basis"]
    esp = library["modules"][0]
    # The pin table is Espressif's: 19 + 19 pins, three grounds, and the I2C defaults are IO21 and IO22.
    assert len(esp["pins"]) == 38 and sum(1 for p in esp["pins"] if p["name"] == "GND") == 3
    assert [p["id"] for p in esp["pins"] if "i2c_sda_default" in p["roles"]] == ["J3-6"]
    assert [p["id"] for p in esp["pins"] if "i2c_scl_default" in p["roles"]] == ["J3-3"]
    # The six flash pins are marked unusable and the input-only pins are marked as such.
    assert {p["name"] for p in esp["pins"] if "do_not_use" in p["roles"]} == {"D0", "D1", "D2", "D3", "CMD", "CLK"}
    assert {p["name"] for p in esp["pins"] if "gpio_input_only" in p["roles"]} == {"VP", "VN", "IO34", "IO35"}
    assert {p["name"] for p in esp["pins"] if "strapping" in p["roles"]} == {"IO0", "IO2", "IO5", "IO12", "IO15"}
    oled = library["modules"][1]
    assert oled["pin_order_varies"] is True and oled["i2c"]["addresses"] == ["0x3C", "0x3D"]
    assert "Measure yours" in oled["dimension_basis"]["pcb"]


def test_the_pin_positions_match_espressifs_drawing() -> None:
    esp = module_library()["modules"][0]
    by_id = {p["id"]: p for p in esp["pins"]}
    # Rows 25.40 mm apart, 2.54 mm pitch, 1.27 mm in from the edge: 27.94 across.
    assert by_id["J3-1"]["x"] - by_id["J2-1"]["x"] == pytest.approx(25.40)
    assert by_id["J2-2"]["y"] - by_id["J2-1"]["y"] == pytest.approx(2.54)
    assert by_id["J2-19"]["y"] == pytest.approx(1.27 + 18 * 2.54)
    assert esp["pcb_mm"]["x"] == 27.94 and esp["pcb_mm"]["y"] == 48.26 and esp["overhang_mm"]["antenna_end"] == 6.04
    assert by_id["J2-1"]["name"] == "3V3" and by_id["J2-19"]["name"] == "5V"


def test_only_the_two_sourced_chip_roles_are_published() -> None:
    library = module_library()
    assert [(m["id"], c["marking"], c["role"]) for m in library["modules"] for c in m["chips"]] == [
        ("esp32-devkitc-v4", "ESP32-WROOM-32E", "Wi-Fi/Bluetooth module on the board"),
        ("ssd1306-096-i2c", "SSD1306", "display controller on the module"),
    ]
    for module in library["modules"]:
        assert all(c["source"] in [s["url"] for s in module["sources"]] for c in module["chips"])


@pytest.fixture
def synthetic_library(tmp_path, monkeypatch):
    from hardware_splicer import device_plan

    path = tmp_path / "device_modules.json"
    data = module_library()
    monkeypatch.setattr(device_plan, "LIBRARY_PATH", path)
    def load(chips):
        candidate = copy.deepcopy(data)
        if chips is ...:
            candidate["modules"][0].pop("chips", None)
        else:
            candidate["modules"][0]["chips"] = chips
        path.write_text(json.dumps(candidate), encoding="utf-8")
        device_plan._library.cache_clear()
        return module_library()
    yield load
    device_plan._library.cache_clear()


def test_a_chip_source_outside_its_own_module_sources_is_refused(synthetic_library):
    # A real source for the other module still cannot support this module's chip entry.
    chip = {"marking": "fixture", "role": "fixture role", "source": module_library()["modules"][1]["sources"][0]["url"]}
    with pytest.raises(RuntimeError, match="source"):
        synthetic_library([chip])


@pytest.mark.parametrize("chips", [None, {}, "fixture", [None], [{}], [{}] * 9])
def test_bad_chip_list_shapes_are_refused(synthetic_library, chips):
    with pytest.raises(RuntimeError, match="chips"):
        synthetic_library(chips)


@pytest.mark.parametrize("field,value", [
    ("marking", ""), ("marking", " " * 41), ("marking", "x" * 41), ("marking", 123),
    ("marking", "fixture\u200b"), ("marking", "fixture\n"),
    ("role", ""), ("role", "x" * 81), ("role", None), ("role", "\u202econtroller"),
    ("source", ""), ("source", "x" * 2049), ("source", []), ("source", "url\x00"),
])
def test_chip_text_is_bounded_printable_and_required(synthetic_library, field, value):
    chip = {"marking": "fixture", "role": "fixture role", "source": module_library()["modules"][0]["sources"][0]["url"]}
    chip[field] = value
    with pytest.raises(RuntimeError, match="chips"):
        synthetic_library([chip])


@pytest.mark.parametrize("chips", [..., []])
def test_chip_knowledge_is_optional(synthetic_library, chips):
    assert synthetic_library(chips)["modules"][0].get("chips", []) == []


def test_eight_printable_chip_entries_at_the_text_limits_are_allowed(synthetic_library):
    chip = {"marking": "標" * 40, "role": "角" * 80, "source": module_library()["modules"][0]["sources"][0]["url"]}
    assert synthetic_library([chip] * 8)["modules"][0]["chips"] == [chip] * 8


def test_the_example_has_supply_notes_with_logical_pins_and_ordered_steps() -> None:
    plan = build_device_plan(EXAMPLE)
    assert _rules(plan) == ADVISORY_RULES and plan["counts"]["errors"] == 0
    assert all(f["severity"] == "info" for f in plan["findings"])
    display = next(m for m in plan["modules"] if m["id"] == "display")
    electrical = module_library()["modules"][1]["electrical"]
    assert all(electrical[key] in display["notes"] for key in ("supply_note", "pullups_note"))
    wires = {(w["from"]["pin"], w["to"]["pin_id"]) for w in plan["wires"]}
    assert wires == {("VCC", "J2-1"), ("GND", "J2-14"), ("SCL", "J3-3"), ("SDA", "J3-6")}
    colors = {w["from"]["pin"]: w["color"] for w in plan["wires"]}
    assert colors == {"VCC": "red", "GND": "black", "SCL": "yellow", "SDA": "green"}
    kinds = [s["kind"] for s in plan["steps"]]
    assert kinds[:3] == ["gather", "measure", "place"] and kinds[-3:] == ["close", "power", "test"]
    assert kinds.index("measure") < kinds.index("place") < kinds.index("wire") < kinds.index("check") < kinds.index("close") < kinds.index("power")
    assert [s["order"] for s in plan["steps"]] == list(range(1, len(plan["steps"]) + 1))
    assert "0x3C" in plan["steps"][-1]["instruction"]
    assert "approves" in plan["authority"]


def test_wire_endpoints_are_the_real_pin_positions_and_ground_takes_the_nearest_pin() -> None:
    plan = build_device_plan(EXAMPLE)
    esp = next(m for m in plan["modules"] if m["id"] == "mcu")
    pins = {p["id"]: p["point"] for p in esp["pins"]}
    for wire in plan["wires"]:
        assert wire["to"]["point"] == pins[wire["to"]["pin_id"]]
        # The wire leaves the far end of each female housing; the housing stands on (or hangs from) the pin.
        assert wire["bezier"][0] == wire["from"]["exit"] and wire["bezier"][-1] == wire["to"]["exit"]
        assert wire["to"]["housing"]["y0"] == wire["to"]["point"]["y"] and wire["to"]["exit"]["y"] == wire["to"]["housing"]["y1"]
        assert wire["from"]["housing"]["y1"] == wire["from"]["point"]["y"] and wire["from"]["exit"]["y"] == wire["from"]["housing"]["y0"]
        assert wire["curve_mm"] >= wire["straight_mm"] - 14.0 * 2 and wire["stock_length_mm"] * 1.0 >= wire["curve_mm"] * 1.15
    ground = next(w for w in plan["wires"] if w["from"]["pin"] == "GND")
    assert ground["to"]["chosen_among_several"] is True
    chosen = math.dist(*[(p["x"], p["y"], p["z"]) for p in (ground["from"]["point"], ground["to"]["point"])])
    others = [p for p in esp["pins"] if p["name"] == "GND" and p["id"] != ground["to"]["pin_id"]]
    assert all(math.dist((ground["from"]["point"]["x"], ground["from"]["point"]["y"], ground["from"]["point"]["z"]), (o["point"]["x"], o["point"]["y"], o["point"]["z"])) >= chosen for o in others)


def test_the_board_sits_inside_the_case_and_the_display_clears_the_wires_and_the_antenna() -> None:
    plan = build_device_plan(EXAMPLE)
    case, mods = plan["case"], {m["id"]: m for m in plan["modules"]}
    half_x, half_z = case["inner_mm"]["x"] / 2, case["inner_mm"]["z"] / 2
    for module in mods.values():
        box = module["box"]
        assert -half_x <= box["x0"] and box["x1"] <= half_x and -half_z <= box["z0"] and box["z1"] <= half_z, module["id"]
    esp = mods["mcu"]
    # The antenna overhang reaches +x and still fits.
    assert esp["box"]["x1"] + esp["overhang_mm"]["antenna_end"] <= half_x
    # The display is above the tallest wire housing, and the lid is above the display.
    display = mods["display"]
    assert display["base_y"] >= esp["base_y"] + esp["pcb_mm"]["z"] + 3.0 + 14.0 + 10.0   # housings plus room for the wires to bend
    assert case["lid_underside_y"] > display["base_y"] + display["pcb_mm"]["z"] + display["above_board_mm"]
    # The display is not over the antenna end.
    assert display["box"]["x1"] < esp["box"]["x1"] - 6.0
    assert case["usb_cutout"]["wall"] == "-x" and case["window"]["width_mm"] > 21.74
    assert "has not been printed" in case["basis"]


# --- wiring mistakes the plan must catch ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("change", "rule", "severity"),
    [
        ({"display.SDA": "mcu.D2"}, "flash_pin", "error"),
        ({"display.SDA": "mcu.IO34"}, "input_only_pin", "error"),
        ({"display.SDA": "mcu.EN"}, "reset_pin", "error"),
        ({"display.SDA": "mcu.IO22"}, "swapped_default_i2c", "warning"),
        ({"display.SDA": "mcu.IO12"}, "i2c_on_mtdi", "error"),
        ({"display.SDA": "mcu.TX"}, "serial_pin", "warning"),
        ({"display.SDA": "mcu.IO19"}, "custom_i2c_pin", "info"),
        ({"display.VCC": "mcu.5V"}, "five_volts_to_a_3v3_system", "warning"),
    ],
)
def test_a_wrong_or_risky_pin_is_flagged_with_the_right_severity(change: dict[str, str], rule: str, severity: str) -> None:
    spec = _with([{**c, "to": change.get(c["from"], c["to"])} for c in GOOD])
    plan = build_device_plan(spec)
    assert rule in _rules(plan, severity), plan["findings"]
    finding = next(f for f in plan["findings"] if f["rule"] == rule)
    assert finding["basis"] and finding["wire"].startswith("wire-")


@pytest.mark.parametrize(
    ("connections", "rule"),
    [
        ([{"from": "display.VCC", "to": "mcu.GND"}, *GOOD[1:]], "ground_to_other"),
        ([{"from": "display.SDA", "to": "mcu.3V3"}, *GOOD[:3]], "power_to_signal"),
        ([GOOD[0], GOOD[1], {"from": "display.SCL", "to": "mcu.IO21"}, {"from": "display.SDA", "to": "mcu.IO21"}], "pin_used_twice"),
        ([{"from": "display.SDA", "to": "display.SCL"}, *GOOD[:3]], None),
        (GOOD[:3], "missing_connection"),
        ([], "missing_connection"),
    ],
)
def test_shorts_double_use_and_missing_wires_are_errors(connections: list[dict], rule: str | None) -> None:
    spec = _with(connections)
    if rule is None:
        with pytest.raises(DevicePlanError, match="same module"):
            build_device_plan(spec)
        return
    plan = build_device_plan(spec)
    assert rule in _rules(plan, "error"), plan["findings"]
    assert plan["counts"]["errors"] >= 1


def test_swapping_sda_and_scl_between_the_two_modules_is_caught_in_either_direction() -> None:
    forward = build_device_plan(_with([GOOD[0], GOOD[1], {"from": "display.SCL", "to": "mcu.IO21"}, {"from": "display.SDA", "to": "mcu.IO22"}]))
    reverse = build_device_plan(_with([GOOD[0], GOOD[1], {"from": "mcu.IO21", "to": "display.SCL"}, {"from": "mcu.IO22", "to": "display.SDA"}]))
    for plan in (forward, reverse):
        assert [f["rule"] for f in plan["findings"]].count("swapped_default_i2c") == 2
    # Written the other way round, the same good wiring is still good.
    flipped = build_device_plan(_with([{"from": c["to"], "to": c["from"]} for c in GOOD]))
    assert _rules(flipped) == ADVISORY_RULES


@pytest.mark.parametrize("source", ["lipo_direct", "battery", "5v_barrel"])
def test_non_usb_power_does_not_invent_a_battery_wire(source) -> None:
    spec = copy.deepcopy(EXAMPLE)
    spec["power"] = {"source": source}
    plan = build_device_plan(spec)
    finding = next(f for f in plan["findings"] if f["rule"] == "power_source_not_supported")
    assert finding["severity"] == "error" and "one and only one" in finding["message"]
    assert "battery" not in finding["message"].split("is not supported yet.", 1)[1].lower()
    assert "3.6 V" not in finding["message"]
    assert not any(s["kind"] == "power" for s in plan["steps"])
    assert not any("Connect the Micro-USB" in s["instruction"] for s in plan["steps"])


# --- the spec ---------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda s: s.update(modules=[]), "modules"),
        (lambda s: s["modules"][0].update(module="not-a-module"), "unknown module"),
        (lambda s: s["modules"][1].update(id="mcu"), "used twice"),
        (lambda s: s["modules"][0].update(id="Bad Id"), "lowercase"),
        (lambda s: s["connections"].append({"from": "display.NOPE", "to": "mcu.3V3"}), "no pin named"),
        (lambda s: s["connections"].append({"from": "ghost.SDA", "to": "mcu.3V3"}), "no module"),
        (lambda s: s["connections"].append({"from": "display", "to": "mcu.3V3"}), "module.PIN"),
        (lambda s: s["connections"].append({"from": "display.SDA", "to": "mcu.IO21", "wire": "pink"}), "wire must be"),
        (lambda s: s.update(name=""), "name"),
        (lambda s: s.update(schema_version="x"), "schema_version"),
        (lambda s: s["case"].update(wall_mm=99), "wall_mm"),
        (lambda s: s["modules"][1].update(overrides={"colour": 1}), "cannot be overridden"),
        (lambda s: s["modules"][1].update(overrides={"pcb_mm": {"x": float("nan")}}), "number"),
        (lambda s: s["modules"][1].update(overrides={"pcb_mm": {"x": 9999}}), "between"),
        (lambda s: s.update(connections=[{"from": "display.SDA", "to": "mcu.IO21"}] * 65), "at most 64"),
    ],
)
def test_a_spec_that_cannot_make_a_plan_is_refused_with_a_reason(mutate, message: str) -> None:
    spec = copy.deepcopy(EXAMPLE)
    mutate(spec)
    with pytest.raises(DevicePlanError, match=message):
        build_device_plan(spec)


@pytest.mark.parametrize("bad", [None, [], "x", 5, {"modules": "x"}])
def test_something_that_is_not_a_spec_is_refused(bad) -> None:
    with pytest.raises(DevicePlanError):
        build_device_plan(bad)


def test_measured_sizes_change_the_case_and_are_recorded() -> None:
    spec = copy.deepcopy(EXAMPLE)
    spec["modules"][1]["overrides"] = {"pcb_mm": {"x": 30.0, "y": 30.0}}
    plan = build_device_plan(spec)
    base = build_device_plan(EXAMPLE)
    display = next(m for m in plan["modules"] if m["id"] == "display")
    assert display["pcb_mm"]["x"] == 30.0 and display["overridden"] == ["pcb_mm"]
    assert plan["case"]["inner_mm"]["z"] > base["case"]["inner_mm"]["z"]


def test_it_is_deterministic_and_changes_nothing() -> None:
    before = json.dumps(EXAMPLE, sort_keys=True)
    one, two = build_device_plan(EXAMPLE), build_device_plan(EXAMPLE)
    assert one == two and json.dumps(EXAMPLE, sort_keys=True) == before


# --- over HTTP ---------------------------------------------------------------------------------------------------------------


@pytest.fixture()
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    return TestClient(create_product_app(ProjectStore(tmp_path / "store")))


def test_the_library_examples_and_a_plan_are_served_api(api: TestClient) -> None:
    assert api.get("/v1/devices/modules").json()["library"]["modules"][0]["id"] == "esp32-devkitc-v4"
    assert api.get("/v1/devices/modules").json()["library"]["modules"][0]["chips"][0]["marking"] == "ESP32-WROOM-32E"
    assert "esp32_oled_usb" in api.get("/v1/devices/examples").json()["examples"]
    served = api.get("/v1/devices/examples/esp32_oled_usb/plan").json()
    assert served["plan"]["counts"]["errors"] == 0 and served["spec"]["name"].startswith("ESP32")
    assert api.get("/v1/devices/examples/nope/plan").status_code == 404
    posted = api.post("/v1/devices/plan", json=EXAMPLE)
    assert posted.status_code == 200 and posted.json()["plan"] == served["plan"]
    assert api.post("/v1/devices/plan", json={"spec": EXAMPLE}).json()["plan"] == served["plan"]


def test_a_bad_request_is_a_clear_422_and_a_huge_one_is_refused_api(api: TestClient) -> None:
    bad = api.post("/v1/devices/plan", json={**EXAMPLE, "modules": []})
    assert bad.status_code == 422 and bad.json()["detail"]["type"] == "invalid_device_spec"
    assert api.post("/v1/devices/plan", content=b"not json", headers={"content-type": "application/json"}).status_code == 422
    huge = {**EXAMPLE, "name": "x" * 70000}
    assert api.post("/v1/devices/plan", json=huge).status_code == 413


def test_planning_writes_nothing_api(api: TestClient, tmp_path: Path) -> None:
    before = sorted(str(p) for p in tmp_path.rglob("*"))
    for _ in range(3):
        assert api.post("/v1/devices/plan", json=EXAMPLE).status_code == 200
    assert sorted(str(p) for p in tmp_path.rglob("*")) == before


# --- review findings ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("swap", "rule"),
    [
        ({"display.GND": "mcu.EN"}, "reset_pin"),
        ({"display.VCC": "mcu.EN"}, "reset_pin"),
        ({"display.VCC": "mcu.D0"}, "flash_pin"),
        ({"display.GND": "mcu.CMD"}, "flash_pin"),
        ({"display.SCL": "mcu.CLK"}, "flash_pin"),
    ],
)
def test_the_reset_and_flash_pins_are_wrong_to_wire_to_whatever_they_are_wired_to(swap: dict[str, str], rule: str) -> None:
    plan = build_device_plan(_with([{**c, "to": swap.get(c["from"], c["to"])} for c in GOOD]))
    assert rule in _rules(plan, "error"), plan["findings"]
    # The wire that was rejected does not count as the display's power, ground or clock, so that pin is also reported missing.
    assert "missing_connection" in _rules(plan, "error"), plan["findings"]
    assert plan["counts"]["errors"] >= 2


def test_two_supply_pins_joined_together_is_an_error_in_either_direction() -> None:
    # Only reachable between modules, so use the display's power pin to stand in: 3V3 to 5V cannot be wired directly here,
    # but the rule is what stops a 3V3 pin and a 5V pin being joined.
    from hardware_splicer.device_plan import _check_connection, _Placed, _module

    mcu = _Placed("mcu", _module("esp32-devkitc-v4"), {})
    other = _Placed("other", _module("esp32-devkitc-v4"), {})
    pins = {p["name"]: p for p in mcu.entry["pins"]}
    for a, b in ((pins["3V3"], pins["5V"]), (pins["5V"], pins["3V3"])):
        findings = _check_connection("wire-01", (mcu, a), (other, b))
        assert [f["rule"] for f in findings] == ["supplies_joined"] and findings[0]["severity"] == "error"


@pytest.mark.parametrize(
    "overrides",
    [
        {"pcb_mm": {"x": 300.0, "y": 300.0}},
        {"pcb_mm": {"x": 80.0}},
        {"above_board_mm": 60.0},
    ],
)
def test_a_measured_override_always_gives_a_case_that_contains_every_module(overrides: dict) -> None:
    spec = copy.deepcopy(EXAMPLE)
    spec["modules"][1]["overrides"] = overrides
    mcu_spec = copy.deepcopy(EXAMPLE)
    mcu_spec["modules"][0]["overrides"] = {"above_board_mm": 40.0}
    for candidate in (spec, mcu_spec):
        plan = build_device_plan(candidate)
        case, half_x, half_z = plan["case"], plan["case"]["inner_mm"]["x"] / 2, plan["case"]["inner_mm"]["z"] / 2
        for module in plan["modules"]:
            box = module["box"]
            reach = module["overhang_mm"].get("antenna_end", 0.0) if module["kind"] == "mcu_board" else 0.0
            assert -half_x - 1e-6 <= box["x0"] and box["x1"] + reach <= half_x + 1e-6, (module["id"], box, half_x)
            assert -half_z - 1e-6 <= box["z0"] and box["z1"] <= half_z + 1e-6, (module["id"], box, half_z)
            top = module["base_y"] + module["pcb_mm"]["z"] + module["above_board_mm"]
            assert top <= case["lid_underside_y"] + 1e-6, (module["id"], top, case["lid_underside_y"])
        win = case["window"]
        assert -case["outer_mm"]["x"] / 2 <= win["x"] - win["width_mm"] / 2 and win["x"] + win["width_mm"] / 2 <= case["outer_mm"]["x"] / 2
        assert -case["outer_mm"]["z"] / 2 <= win["z"] - win["depth_mm"] / 2 and win["z"] + win["depth_mm"] / 2 <= case["outer_mm"]["z"] / 2


@pytest.mark.parametrize("wire", [[], {}, 5, True, ["red"]])
def test_a_wire_colour_that_is_not_a_name_is_a_clear_refusal_not_a_crash(wire) -> None:
    spec = copy.deepcopy(EXAMPLE)
    spec["connections"][0]["wire"] = wire
    with pytest.raises(DevicePlanError, match="wire must be"):
        build_device_plan(spec)


def test_a_spec_with_any_value_swapped_for_something_odd_is_a_plan_or_a_clear_refusal_never_a_crash() -> None:
    import random

    odd = [None, True, False, 0, -1, 1e308, float("nan"), float("inf"), "", "x" * 300, "mcu.\u0000", [], {}, [[]], {"a": {"b": []}}, "\ud83d\ude00", -0.0, 10**30]
    rng = random.Random(20261009)

    def leaves(node, path=()):
        if isinstance(node, dict):
            for key, value in node.items():
                yield from leaves(value, path + (key,))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                yield from leaves(value, path + (index,))
        else:
            yield path

    paths = list(leaves(EXAMPLE))
    for _ in range(400):
        spec = copy.deepcopy(EXAMPLE)
        for path in rng.sample(paths, k=rng.randint(1, 3)):
            target = spec
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = rng.choice(odd)
        try:
            plan = build_device_plan(spec)
        except DevicePlanError:
            continue
        assert plan["schema_version"].endswith("v1") and all(math.isfinite(v) for module in plan["modules"] for v in module["box"].values())


def test_a_body_with_no_declared_length_is_refused_as_soon_as_it_is_too_big_api(api: TestClient) -> None:
    def pieces():
        # A chunked upload: no content-length, far more than the limit, and never finished.
        for _ in range(100000):
            yield b"x" * 1024

    assert api.post("/v1/devices/plan", content=pieces(), headers={"content-type": "application/json"}).status_code == 413


def test_json_nested_far_too_deeply_is_a_422_not_a_server_error_api(api: TestClient) -> None:
    deep = b"[" * 30000 + b"0" + b"]" * 30000        # about 60 KB: under the size limit, far over what the parser can nest
    response = api.post("/v1/devices/plan", content=deep, headers={"content-type": "application/json"})
    assert response.status_code == 422 and "nested" in response.json()["detail"]["message"]


def test_a_display_measured_smaller_than_its_own_screen_is_refused_rather_than_given_an_impossible_window() -> None:
    spec = copy.deepcopy(EXAMPLE)
    spec["modules"][1]["overrides"] = {"pcb_mm": {"x": 5.0, "y": 5.0}}
    with pytest.raises(DevicePlanError, match="too small for its screen"):
        build_device_plan(spec)


def test_wires_that_are_each_fine_but_together_join_two_supplies_are_an_error() -> None:
    both = _with([*GOOD, {"from": "display.VCC", "to": "mcu.5V"}])
    plan = build_device_plan(both)
    bridged = [f for f in plan["findings"] if f["rule"] == "nets_bridged"]
    assert len(bridged) == 1 and bridged[0]["severity"] == "error" and "3.3 V and 5 V" in bridged[0]["message"]
    assert "mcu.3V3" in bridged[0]["message"] and "mcu.5V" in bridged[0]["message"]
    # Each wire on its own was only the 5 V warning; it is the pair that is the problem.
    assert _rules(build_device_plan(_with(GOOD))) == ADVISORY_RULES
    assert "nets_bridged" not in _rules(build_device_plan(_with([{"from": "display.VCC", "to": "mcu.5V"}, *GOOD[1:]])))


def test_a_supply_reaching_ground_through_the_modules_own_ground_pins_is_caught() -> None:
    # display.GND to the board's ground, and display.VCC to the board's 3V3: fine. Add display.VCC to a second GND pin.
    plan = build_device_plan(_with([*GOOD, {"from": "display.VCC", "to": "mcu.J3-7"}]))
    rules = _rules(plan, "error")
    assert "ground_to_other" in rules       # the wire itself
    # No double report for a net that already has a rejected wire.
    assert [f["rule"] for f in plan["findings"]].count("nets_bridged") == 0
    # Three ground pins are one net, so a supply that meets ground through two of them is still one problem.
    indirect = build_device_plan(_with([GOOD[0], {"from": "display.GND", "to": "mcu.J2-14"}, {"from": "display.GND", "to": "mcu.J3-1"}, GOOD[2], GOOD[3]]))
    assert _rules(indirect) == ADVISORY_RULES       # neither ground wire adds a fault


def test_the_board_can_be_wired_correctly_to_any_of_its_three_ground_pins() -> None:
    for pin in ("mcu.J2-14", "mcu.J3-1", "mcu.J3-7", "mcu.GND"):
        plan = build_device_plan(_with([GOOD[0], {"from": "display.GND", "to": pin}, GOOD[2], GOOD[3]]))
        assert _rules(plan) == ADVISORY_RULES, (pin, plan["findings"])


def test_a_rejected_wire_does_not_hide_a_separate_supply_bridge() -> None:
    plan = build_device_plan(_with([*GOOD, {"from": "display.VCC", "to": "mcu.5V"}, {"from": "display.VCC", "to": "mcu.EN"}]))
    rules = [f["rule"] for f in plan["findings"]]
    assert "reset_pin" in rules and rules.count("nets_bridged") == 1, plan["findings"]
    # Removing the reset wire does not make the bridge go away, and the plan said so from the start.
    without = build_device_plan(_with([*GOOD, {"from": "display.VCC", "to": "mcu.5V"}]))
    assert [f["rule"] for f in without["findings"]].count("nets_bridged") == 1
    # A wire that is itself rejected is reported once, by its own rule, and not again as part of a net.
    shorted = build_device_plan(_with([GOOD[0], {"from": "display.GND", "to": "mcu.3V3"}, GOOD[2], GOOD[3]]))
    assert [f["rule"] for f in shorted["findings"]].count("nets_bridged") == 0 and "ground_to_other" in _rules(shorted, "error")


def test_an_integer_too_big_to_be_a_number_is_a_clear_refusal_in_a_device_spec_too_api(api: TestClient) -> None:
    huge = 10 ** 400
    spec = copy.deepcopy(EXAMPLE)
    spec["modules"][0]["overrides"] = {"above_board_mm": huge}
    with pytest.raises(DevicePlanError, match="must be a number"):
        build_device_plan(spec)
    spec = copy.deepcopy(EXAMPLE)
    spec["case"]["wall_mm"] = huge
    with pytest.raises(DevicePlanError, match="must be a number"):
        build_device_plan(spec)
    response = api.post("/v1/devices/plan", content=json.dumps(spec).encode(), headers={"content-type": "application/json"})
    assert response.status_code == 422


@pytest.mark.parametrize("hidden", ["\u202eKit", "Kit\u200b", "\u2028Kit"])
def test_a_device_name_cannot_hide_direction_changes(hidden: str) -> None:
    spec = copy.deepcopy(EXAMPLE)
    spec["name"] = hidden
    with pytest.raises(DevicePlanError, match="control or invisible characters"):
        build_device_plan(spec)


def test_a_chip_entry_may_carry_nothing_but_marking_role_and_source(synthetic_library):
    source = module_library()["modules"][0]["sources"][0]["url"]
    base = {"marking": "fixture", "role": "fixture role", "source": source}
    synthetic_library([base])                                                                    # the plain entry loads
    for extra in ({"verified": True}, {"pins": [{"id": "1"}]}, {"electrical": {"io_v": 3.3}}):
        with pytest.raises(RuntimeError, match="exactly marking, role and source"):
            synthetic_library([{**base, **extra}])


def test_malformed_module_sources_fail_closed_with_the_loaders_own_error(tmp_path, monkeypatch):
    from hardware_splicer import device_plan

    original = copy.deepcopy(module_library())
    path = tmp_path / "device_modules.json"
    monkeypatch.setattr(device_plan, "LIBRARY_PATH", path)
    try:
        for bad in ("https://docs.espressif.com/x", [{"label": "no url"}], [42], [{"url": 7}]):
            data = copy.deepcopy(original)
            data["modules"][0]["sources"] = bad
            path.write_text(json.dumps(data), encoding="utf-8")
            device_plan._library.cache_clear()
            with pytest.raises(RuntimeError, match="sources must be a list"):
                module_library()
    finally:
        device_plan._library.cache_clear()


# --- electronics audit regressions (W3) -------------------------------------------------------------------------------------

@pytest.mark.parametrize("pin", ["IO34", "IO35", "VP", "VN"])
@pytest.mark.parametrize("reverse", [False, True])
def test_ground_on_an_input_only_pin_is_an_error_and_not_a_ground_return(pin, reverse):
    connections = [{**c, "to": f"mcu.{pin}" if c["from"] == "display.GND" else c["to"]} for c in GOOD]
    if reverse:
        connections = [{"from": c["to"], "to": c["from"]} for c in connections]
    plan = build_device_plan(_with(connections))
    assert "ground_to_other" in _rules(plan, "error")
    assert any(f["rule"] == "missing_connection" and "ground" in f["message"] for f in plan["findings"])
    isolation = next(c for s in plan["steps"] for c in s["checks"] if c["check"] == "isolation")
    assert isolation["to"] == "mcu.GND"


@pytest.mark.parametrize("signal", ["SDA", "SCL"])
@pytest.mark.parametrize("reverse", [False, True])
def test_i2c_pullups_on_io12_are_an_error_without_a_pin_routing_note(signal, reverse):
    connections = [{**c, "to": "mcu.IO12" if c["from"] == f"display.{signal}" else c["to"]} for c in GOOD]
    if reverse:
        connections = [{"from": c["to"], "to": c["from"]} for c in connections]
    plan = build_device_plan(_with(connections))
    finding = next(f for f in plan["findings"] if f["rule"] == "i2c_on_mtdi")
    assert finding["severity"] == "error" and "1.8 V" in finding["message"]
    assert "IO12 should be kept low" in finding["basis"]
    assert "custom_i2c_pin" not in _rules(plan)
    assert "missing_connection" in _rules(plan, "error")


@pytest.mark.parametrize("reverse", [False, True])
def test_five_volt_oled_warning_covers_logic_and_pullups_and_gates_usb(reverse):
    connections = [{**c, "to": "mcu.5V" if c["from"] == "display.VCC" else c["to"]} for c in GOOD]
    if reverse:
        connections = [{"from": c["to"], "to": c["from"]} for c in connections]
    plan = build_device_plan(_with(connections))
    finding = next(f for f in plan["findings"] if f["rule"] == "five_volts_to_a_3v3_system")
    assert finding["severity"] == "warning"
    assert all(text in finding["message"] for text in ("1.65", "3.3 V", "regulator", "damage", "SDA", "SCL"))
    assert not any(s["kind"] == "power" for s in plan["steps"])
    assert any("Do not plug in until you have checked the warnings above" in s["instruction"] for s in plan["steps"])


@pytest.mark.parametrize("target", ["mcu.IO0", "mcu.IO22", "mcu.D2"])
def test_any_warning_or_error_adds_a_power_review(target):
    plan = build_device_plan(_with([{**c, "to": target if c["from"] == "display.SDA" else c["to"]} for c in GOOD]))
    assert any("Do not plug in until you have checked the warnings above" in s["instruction"] for s in plan["steps"])
    assert not any(s["kind"] == "power" for s in plan["steps"])


def test_io0_note_names_the_devkit_auto_program_circuit_with_a_source_limit():
    plan = build_device_plan(_with([{**c, "to": "mcu.IO0" if c["from"] == "display.SDA" else c["to"]} for c in GOOD]))
    finding = next(f for f in plan["findings"] if f["rule"] == "strapping_pin")
    assert "auto-program" in finding["message"]
    assert "ESP-IDF ADC docs" in finding["basis"] and "supervisor" not in finding["basis"]


def test_supply_and_pullup_notes_survive_missing_or_rejected_wires():
    for connections in ([], [{"from": "display.SDA", "to": "mcu.D2"}]):
        plan = build_device_plan(_with(connections))
        assert ADVISORY_RULES <= _rules(plan, "info")
        display = next(m for m in plan["modules"] if m["id"] == "display")
        assert any("pull-up resistors" in note for note in display["notes"])


def test_oled_pin_order_is_an_explicit_drawing_choice_with_an_assumed_default():
    oled = module_library()["modules"][1]
    assert oled["pin_order_varies"] is True
    assert [order["signals"] for order in oled["pin_orders"]] == [["GND", "VCC", "SCL", "SDA"], ["VCC", "GND", "SCL", "SDA"]]
    assert all(order["source"] in {source["url"] for source in oled["sources"]} for order in oled["pin_orders"])
    assert "usual" not in oled["dimension_basis"]["pins"]
    assert all(p["id"] == p["name"] and "number" not in p for p in oled["pins"])
    plan = build_device_plan(EXAMPLE)
    display = next(m for m in plan["modules"] if m["id"] == "display")
    order = next(order for order in oled["pin_orders"] if order["id"] == oled["default_pin_order"])
    assert display["pin_order"] == order["id"]
    assert [p["name"] for p in display["pins"]] == order["signals"]
    assert all(p["roles"] and "printed label" in p["label"] for p in display["pins"])
    assert len({tuple(p["point"].values()) for p in display["pins"]}) == 4
    finding = next(f for f in plan["findings"] if f["rule"] == "pin_order_assumed")
    assert finding["severity"] == "info" and "assumed" in finding["message"]
    assert order["label"] in finding["message"] and order["source"] in finding["basis"]
    assert "pin_order_drawn" not in _rules(plan)
    pins = {p["id"]: p["point"] for p in display["pins"]}
    assert len(plan["wires"]) == 4
    for wire in plan["wires"]:
        assert "point_basis" not in wire["from"]
        assert wire["from"]["point"] == pins[wire["from"]["pin_id"]]
    assert [step["wire"] for step in plan["steps"] if step["kind"] == "wire"] == [wire["id"] for wire in plan["wires"]]
    with pytest.raises(DevicePlanError, match="no pin named"):
        build_device_plan(_with([{"from": "display.P1", "to": "mcu.GND"}]))


def test_choosing_the_other_pin_order_moves_the_vcc_wire_without_changing_signals():
    original = copy.deepcopy(EXAMPLE)
    library_before = module_library()
    plans = []
    for order in library_before["modules"][1]["pin_orders"]:
        spec = copy.deepcopy(EXAMPLE)
        spec["modules"][1]["pin_order"] = order["id"]
        plan = build_device_plan(spec)
        display = next(m for m in plan["modules"] if m["id"] == "display")
        assert [p["name"] for p in sorted(display["pins"], key=lambda p: p["point"]["x"])] == order["signals"]
        assert {p["name"]: p["roles"] for p in display["pins"]} == {p["name"]: p["roles"] for p in library_before["modules"][1]["pins"]}
        assert "pin_order_drawn" in _rules(plan, "info") and "pin_order_assumed" not in _rules(plan)
        finding = next(f for f in plan["findings"] if f["rule"] == "pin_order_drawn")
        assert ', '.join(order["signals"]) in finding["message"]
        assert "connect by the printed labels, not by position in the picture" in finding["message"]
        vcc = next(wire for wire in plan["wires"] if wire["from"]["pin"] == "VCC")
        assert vcc["from"]["point"] == next(p["point"] for p in display["pins"] if p["name"] == "VCC")
        plans.append(vcc)
        # Also check connections written in the other direction land on those pads.
        spec["connections"] = [{"from": w["to"], "to": w["from"]} for w in spec["connections"]]
        reverse = build_device_plan(spec)
        assert next(w for w in reverse["wires"] if w["to"]["pin"] == "VCC")["to"]["point"] == vcc["from"]["point"]
    assert plans[0]["from"]["point"] != plans[1]["from"]["point"]
    assert plans[0]["to"]["point"] == plans[1]["to"]["point"]
    assert plans[0]["bezier"][0] != plans[1]["bezier"][0]
    assert module_library() == library_before and EXAMPLE == original


@pytest.mark.parametrize("bad", [None, 3, True, [], {}, "", "unknown", "gnd-vcc-scl-sda\n"])
def test_invalid_pin_order_is_refused_with_the_valid_ids(bad):
    spec = copy.deepcopy(EXAMPLE)
    spec["modules"][1]["pin_order"] = bad
    with pytest.raises(DevicePlanError) as caught:
        build_device_plan(spec)
    assert "pin_order must be text" in str(caught.value)
    for order in module_library()["modules"][1]["pin_orders"]:
        assert order["id"] in str(caught.value)


def test_pin_order_is_refused_on_a_module_without_orders():
    spec = copy.deepcopy(EXAMPLE)
    spec["modules"][0]["pin_order"] = "gnd-vcc-scl-sda"
    with pytest.raises(DevicePlanError, match="none for this module"):
        build_device_plan(spec)


def test_wroom_datasheet_redirect_is_used_by_sources_and_chips():
    esp = module_library()["modules"][0]
    url = "https://documentation.espressif.com/esp32-wroom-32e_esp32-wroom-32ue_datasheet_en.pdf"
    source = next(s for s in esp["sources"] if s["url"] == url)
    assert source["as_of"] == "2026-10-10"
    assert "link updated" in source["label"] and "supervisor" not in source["label"]
    assert esp["chips"][0]["source"] == url


def test_display_seating_uses_board_edges():
    plan = build_device_plan(EXAMPLE)
    seating = next(s for s in plan["steps"] if s["kind"] == "place" and s["parts"] == ["display"])
    assert "circuit-board edges, not by the glass" in seating["instruction"]
    assert "Press the display" not in seating["instruction"]


def test_checks_request_observations_without_predicting_readings():
    plan = build_device_plan(EXAMPLE)
    for step in plan["steps"]:
        for check in step["checks"]:
            assert check["expect"] == "record what you observe; this plan supplies no reading"
    assert "should report one device" not in plan["steps"][-1]["instruction"]


def test_supply_current_note_is_present_without_wires_or_display():
    for spec in (EXAMPLE, _with([]), {**EXAMPLE, "modules": EXAMPLE["modules"][:1], "connections": []}):
        plan = build_device_plan(spec)
        finding = next(f for f in plan["findings"] if f["rule"] == "supply_current")
        assert finding["severity"] == "info"
        assert "at least 0.5 A" in finding["message"]
        assert all(text in finding["message"] for text in ("weak charger", "long or thin cable", "unpowered hub", "resets when Wi-Fi starts", "General practice, not from the datasheet"))
        assert "Table 14" in finding["basis"]
        assert module_library()["modules"][0]["electrical"]["supply_current_source"] in finding["basis"]
    assert build_device_plan(EXAMPLE)["counts"]["errors"] == 0
    assert build_device_plan(EXAMPLE)["counts"]["warnings"] == 0


@pytest.mark.parametrize("reverse", [False, True])
def test_adc2_wifi_note_follows_pin_functions_even_on_rejected_wires(reverse):
    esp = module_library()["modules"][0]
    for pin in esp["pins"]:
        wire = {"from": "display.SDA", "to": f"mcu.{pin['id']}"}
        if reverse:
            wire = {"from": wire["to"], "to": wire["from"]}
        plan = build_device_plan(_with([wire]))
        notes = [f for f in plan["findings"] if f["rule"] == "adc2_wifi"]
        assert bool(notes) == ("ADC2_CH" in pin["function"])
        for note in notes:
            assert note["severity"] == "info" and note["wire"] == "wire-01"
            assert f"mcu.{pin['name']}" in note["message"]
            assert "analog reads" in note["message"] and "while Wi-Fi is running" in note["message"]
            assert "Digital use such as I2C is not affected" in note["message"]
            assert any(source["url"] in note["basis"] for source in esp["sources"] if "ESP-IDF ADC docs" in source["label"])


@pytest.mark.parametrize("width,clearance", [(27, 1), (90, 0.2), (90, 3)])
def test_antenna_note_reports_the_existing_layout_gap(width, clearance):
    spec = copy.deepcopy(EXAMPLE)
    spec["case"]["clearance_mm"] = clearance
    spec["modules"][1]["overrides"] = {"pcb_mm": {"x": width}}
    plan = build_device_plan(spec)
    board = next(m for m in plan["modules"] if m["id"] == "mcu")
    gap = round(plan["case"]["inner_mm"]["x"] / 2 - board["box"]["x1"] - board["overhang_mm"]["antenna_end"], 3)
    note = next(f for f in plan["findings"] if f["rule"] == "antenna_keepout")
    assert note["severity"] == "info"
    assert "marks a keepout zone at the antenna end" in note["message"]
    assert "figure note gives no distance to a case wall" in note["message"]
    assert f"is {gap:g} mm" in note["message"]
    assert module_library()["modules"][0]["keep_clear"][0]["source"] in note["basis"]
    assert "enough" not in note["message"]


def test_display_seating_labels_glass_handling_as_general_practice():
    step = next(s for s in build_device_plan(EXAMPLE)["steps"] if s["kind"] == "place" and s["parts"] == ["display"])
    assert "circuit-board edges, not by the glass" in step["instruction"]
    assert "Never put force on the glass" in step["instruction"]
    assert "General practice, not from the datasheet" in step["instruction"]


def test_kit_fit_note_names_typical_sizes_and_male_pins_once():
    notes = [f for f in build_device_plan(EXAMPLE)["findings"] if f["rule"] == "kit_fit"]
    assert len(notes) == 1 and notes[0]["severity"] == "info"
    text = notes[0]["message"]
    assert all(value in text for value in ("case uses typical values, not measurements", "14 mm jumper housing", "10 mm wire bend", "14 x 8 mm USB overmold", "1.6 mm PCB", "8.5 mm under-board header", "actual kit", "male pins on both ends"))
