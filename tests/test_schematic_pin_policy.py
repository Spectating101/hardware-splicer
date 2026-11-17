"""Emitter rules for no-connects, PWR_FLAGs and pin directions (no KiCad needed)."""

from __future__ import annotations

import re
from typing import Iterable

from hardware_splicer.integrations.schematic_export import netlist_to_kicad_schematic
from hardware_splicer.integrations.schematic_pin_policy import (
    catalog_pins,
    pin_electrical_type,
    plan_no_connects,
    plan_power_flags,
)
from hardware_splicer.netlist.ir import CircuitNetlist, ComponentInstance, Net, PinRef


def _netlist(components: Iterable[tuple[str, str]], nets: dict[str, Iterable[str]]) -> CircuitNetlist:
    return CircuitNetlist(
        components=[ComponentInstance(ref=ref, module_id=mid) for ref, mid in components],
        nets=[
            Net(name=name, pins=[PinRef(*key.split(".", 1)) for key in keys])
            for name, keys in nets.items()
        ],
    )


def _nc(netlist: CircuitNetlist, build_id: str | None = None) -> set[str]:
    return {f"{p.ref}.{p.pin}" for p in plan_no_connects(netlist, build_id=build_id)}


# ---- no-connect rules -------------------------------------------------------------------------


def _recipe_netlist(build_id: str) -> CircuitNetlist:
    from hardware_splicer.netlist.lower import build_graph_to_netlist
    from hardware_splicer.plan_to_graph import splice_plan_to_build_graph

    graph, _id, _notes, _warnings = splice_plan_to_build_graph({"target": {"recommended_build_id": build_id}})
    return build_graph_to_netlist(graph)


def test_connected_pin_never_gets_a_no_connect_even_when_policy_lists_it() -> None:
    from hardware_splicer.integrations.schematic_pin_policy import load_policy

    # Module-level policy lists MOSFET VOUT+ and VOUT-, but here the pump is wired to VOUT+.
    policy = {**load_policy(), "module_pins": {"mosfet-irlz44n": {
        "VOUT+": {"disposition": "off_board_terminal", "reason": "test"},
        "VOUT-": {"disposition": "off_board_terminal", "reason": "test"},
    }}}
    netlist = _netlist(
        [("U1", "mosfet-irlz44n"), ("M1", "cooling_fan_5v")],
        {"LOAD": ["U1.VOUT+", "M1.VCC"]},
    )
    flagged = {f"{p.ref}.{p.pin}" for p in plan_no_connects(netlist, policy=policy)}
    assert "U1.VOUT+" not in flagged
    assert "U1.VOUT-" in flagged  # still open, and listed


def test_unlisted_unconnected_pin_stays_open_for_kicad_to_report() -> None:
    # indicator_or_task_light never mentions the MOSFET SIG pin, so it must not be hidden.
    netlist = _netlist([("U3", "mosfet-irlz44n")], {})
    assert "U3.SIG" not in _nc(netlist, "indicator_or_task_light")
    # ...and without a build id nothing build-specific applies at all.
    assert "U3.VOUT+" not in _nc(netlist, None)


def test_off_board_terminal_applies_only_to_the_recipe_that_names_it() -> None:
    plant = _recipe_netlist("automatic_plant_watering")
    mosfet = next(c.ref for c in plant.components if c.module_id == "mosfet-irlz44n")
    flagged = _nc(plant, "automatic_plant_watering")
    assert {f"{mosfet}.VOUT+", f"{mosfet}.VOUT-"} <= flagged
    assert f"{mosfet}.SIG" not in flagged
    # The same recipe netlist under another build's name gets none of the plant's terminals.
    assert f"{mosfet}.VOUT+" not in _nc(plant, "robot_drive_base")
    assert f"{mosfet}.VOUT+" not in _nc(plant, None)


def test_mcu_general_purpose_io_is_optional_but_its_supply_pins_are_not() -> None:
    netlist = _netlist([("U1", "esp32-devkit")], {})
    flagged = _nc(netlist)
    assert {"U1.GPIO4", "U1.GPIO34", "U1.GPIO21"} <= flagged
    # A dev board's VIN and GND are supply pins a design needs; they are never auto-flagged.
    assert "U1.VIN" not in flagged and "U1.GND" not in flagged


def test_power_and_ground_pins_of_non_mcu_modules_are_not_blanket_flagged() -> None:
    netlist = _netlist([("U1", "ldo-ams1117-3v3")], {})
    assert _nc(netlist) == set()


def test_pin_note_marking_a_pin_optional_is_honoured() -> None:
    netlist = _netlist([("U1", "soil_moisture")], {})
    flagged = _nc(netlist)
    assert "U1.D0" in flagged  # note: "Digital output (optional)"
    assert "U1.A0" not in flagged and "U1.VCC" not in flagged


def test_alternate_supply_input_is_optional_only_while_the_primary_is_connected() -> None:
    open_both = _netlist([("U1", "rpi-pico")], {})
    assert "U1.VSYS" not in _nc(open_both)
    vbus_fed = _netlist([("J1", "usb-power-5v"), ("U1", "rpi-pico")], {"VBUS": ["J1.V+", "U1.VBUS"]})
    assert "U1.VSYS" in _nc(vbus_fed)


def test_emitted_schematic_places_no_connects_only_on_planned_unconnected_pins() -> None:
    netlist = _netlist(
        [("U1", "esp32-devkit"), ("U2", "soil_moisture")],
        {"SENSE": ["U2.A0", "U1.GPIO34"], "+3V3": ["U1.3V3", "U2.VCC"], "GND": ["U1.GND", "U2.GND"]},
    )
    text = netlist_to_kicad_schematic(netlist, build_id="sensor_logger")
    planned = plan_no_connects(netlist, build_id="sensor_logger")
    assert text.count("(no_connect") == len(planned)
    # Every connected pin has a wire stub at its location; none of those coordinates carries an NC.
    wire_ends = set(re.findall(r"\(pts \(xy ([\d.\-]+ [\d.\-]+)\)", text))
    nc_at = set(re.findall(r"\(no_connect\s+\(at ([\d.\-]+ [\d.\-]+)\)", text))
    assert wire_ends and nc_at
    assert not (wire_ends & nc_at)


# ---- PWR_FLAG rules ---------------------------------------------------------------------------


def _flagged_nets(netlist: CircuitNetlist) -> dict[str, str]:
    return {p.net: p.source for p in plan_power_flags(netlist)}


def test_ground_net_fed_by_an_off_board_connector_gets_one_flag_naming_the_source() -> None:
    netlist = _netlist(
        [("J1", "usb-power-5v"), ("U1", "esp32-devkit")],
        {"GND": ["J1.GND", "U1.GND"], "+5V": ["J1.V+", "U1.VIN"]},
    )
    plans = plan_power_flags(netlist)
    assert [p.net for p in plans] == ["GND"]  # +5V already has a power output (J1.V+)
    assert plans[0].ref == "J1" and "usb-power-5v" in plans[0].source


def test_ground_net_with_no_documented_source_gets_no_flag() -> None:
    # Two sensors tied together with no connector, regulator or other source anywhere.
    netlist = _netlist(
        [("U1", "soil_moisture"), ("U2", "bme280")],
        {"GND": ["U1.GND", "U2.GND"]},
    )
    assert plan_power_flags(netlist) == []


def test_net_already_driven_by_a_power_output_gets_no_flag() -> None:
    netlist = _netlist(
        [("U1", "esp32-devkit"), ("U2", "bme280")],
        {"+3V3": ["U1.3V3", "U2.VCC"]},
    )
    assert plan_power_flags(netlist) == []


def test_regulator_ground_is_flagged_only_through_a_fed_common_ground() -> None:
    fed = _netlist(
        [("J1", "dc-barrel-12v"), ("U2", "buck-mp1584"), ("U3", "mosfet-irlz44n")],
        {
            "GND": ["J1.GND", "U2.IN-"],
            "GND_2": ["U2.OUT-", "U3.VIN-"],
        },
    )
    flags = _flagged_nets(fed)
    assert set(flags) == {"GND", "GND_2"}
    assert "common with IN-" in flags["GND_2"]

    unfed = _netlist(
        [("U2", "buck-mp1584"), ("U3", "mosfet-irlz44n")],
        {"GND": ["U2.IN-"], "GND_2": ["U2.OUT-", "U3.VIN-"]},
    )
    assert _flagged_nets(unfed) == {}


def test_switched_mosfet_return_feeds_the_load_ground_net() -> None:
    netlist = _netlist(
        [("U5", "mosfet-irlz44n"), ("M1", "cooling_fan_5v")],
        {"GND_2": ["U5.VOUT-", "M1.GND"]},
    )
    flags = _flagged_nets(netlist)
    assert set(flags) == {"GND_2"} and "VOUT-" in flags["GND_2"]


def test_external_supply_pin_gets_its_own_flagged_stub_net_only_while_unconnected() -> None:
    open_pin = _netlist([("U1", "ch340-usb-ttl")], {})
    stubs = [p for p in plan_power_flags(open_pin) if p.stub]
    assert [(p.ref, p.pin) for p in stubs] == [("U1", "USB")]

    wired = _netlist([("U1", "ch340-usb-ttl"), ("J1", "usb-power-5v")], {"VBUS": ["J1.V+", "U1.USB"]})
    assert not [p for p in plan_power_flags(wired) if p.stub]


def test_flags_are_not_emitted_for_a_design_that_needs_none() -> None:
    netlist = _netlist(
        [("U1", "esp32-devkit"), ("U2", "bme280")],
        {"+3V3": ["U1.3V3", "U2.VCC"]},
    )
    text = netlist_to_kicad_schematic(netlist)
    assert "PWR_FLAG" not in text


def test_each_planned_flag_is_one_instance_in_the_schematic() -> None:
    netlist = _netlist(
        [("J1", "usb-power-5v"), ("U1", "esp32-devkit")],
        {"GND": ["J1.GND", "U1.GND"], "+5V": ["J1.V+", "U1.VIN"]},
    )
    text = netlist_to_kicad_schematic(netlist)
    assert text.count('(lib_id "power:PWR_FLAG")') == 1
    assert text.count('(symbol "power:PWR_FLAG"') == 1


# ---- pin direction ----------------------------------------------------------------------------


def _pin(module_id: str, pin_id: str) -> dict:
    return next(p for p in catalog_pins(module_id) if p["id"] == pin_id)


def test_servo_control_pin_is_an_input_and_analog_sensor_output_is_an_output() -> None:
    assert pin_electrical_type("sg90", _pin("sg90", "SIG")) == "input"
    assert pin_electrical_type("soil_moisture", _pin("soil_moisture", "A0")) == "output"


def test_mcu_pins_keep_their_role_based_types() -> None:
    assert pin_electrical_type("rpi-pico", _pin("rpi-pico", "GP0")) == "output"
    assert pin_electrical_type("esp32-devkit", _pin("esp32-devkit", "GPIO34")) == "input"
    assert pin_electrical_type("esp32-devkit", _pin("esp32-devkit", "GPIO4")) == "bidirectional"


# ---- generic (non-catalog) symbol pin geometry ------------------------------------------------


def _wire_ends(text: str) -> set[tuple[float, float]]:
    return {
        (float(x), float(y))
        for x, y in re.findall(r"\(wire\s+\(pts \(xy ([\d.\-]+) ([\d.\-]+)\)", text)
    }


def test_resistor_wire_stubs_start_on_the_generic_symbols_real_pin_ends() -> None:
    # Device:R has its pins at (0, +/-2.54) in library coordinates (+Y up). The component sits
    # at the sheet origin below; sheet Y grows downward, so pin 1 is at y-2.54 and pin 2 at y+2.54.
    netlist = _netlist(
        [("R1", "resistor-4_7k")],
        {"A": ["R1.1"], "B": ["R1.2"]},
    )
    text = netlist_to_kicad_schematic(netlist)
    at = re.search(r'\(lib_id "Device:R"\)\s+\(at ([\d.\-]+) ([\d.\-]+) 0\)', text)
    assert at, "resistor should use the embedded Device:R symbol"
    x, y = float(at.group(1)), float(at.group(2))
    assert (x, round(y - 2.54, 4)) in {(a, round(b, 4)) for a, b in _wire_ends(text)}
    assert (x, round(y + 2.54, 4)) in {(a, round(b, 4)) for a, b in _wire_ends(text)}


def _label_at(text: str, name: str) -> tuple[float, float]:
    match = re.search(rf'\(label "{re.escape(name)}" \(at ([\d.\-]+) ([\d.\-]+) 180\)', text)
    assert match, name
    return round(float(match.group(1)), 4), round(float(match.group(2)), 4)


def test_module_block_fallback_pins_use_the_library_y_inversion() -> None:
    netlist = _netlist([("U9", "not-a-catalog-module")], {"A": ["U9.1"], "B": ["U9.2"]})
    text = netlist_to_kicad_schematic(netlist)
    at = re.search(r'\(lib_id "HS:ModuleBlock"\)\s+\(at ([\d.\-]+) ([\d.\-]+) 0\)', text)
    assert at
    x, y = float(at.group(1)), float(at.group(2))
    # HS block symbols put pin 1 at library (-7.62, +2.54) and pin 2 at (-7.62, -2.54); with the
    # sheet's downward Y that is y-2.54 for pin 1 and y+2.54 for pin 2 (label sits 5.08 further left).
    assert _label_at(text, "A") == (round(x - 7.62 - 5.08, 4), round(y - 2.54, 4))
    assert _label_at(text, "B") == (round(x - 7.62 - 5.08, 4), round(y + 2.54, 4))


# ---- load termination classification ----------------------------------------------------------


def test_every_off_board_no_connect_states_it_lands_on_the_breakouts_own_terminal() -> None:
    from hardware_splicer.integrations.schematic_pin_policy import load_policy

    policy = load_policy()
    terminal_modules = set(policy["load_termination"]["breakout_terminal_modules"])
    seen = 0
    for build_id, modules in policy["build_pins"].items():
        for module_id, pins in modules.items():
            for pin_id, entry in pins.items():
                if entry["disposition"] in {"off_board_terminal", "optional_cell"}:
                    seen += 1
                    assert entry.get("termination") == "breakout_terminal", (build_id, module_id, pin_id)
                    assert module_id in terminal_modules, (build_id, module_id, pin_id)
    assert seen > 0


def test_pins_that_reach_the_carrier_through_a_connector_never_get_a_no_connect() -> None:
    from hardware_splicer.integrations.schematic_pin_policy import load_policy

    policy = load_policy()
    carrier = policy["load_termination"]["carrier_connector_pins"]
    for build_id, modules in policy["build_pins"].items():
        for module_id, pins in modules.items():
            overlap = set(pins) & set(carrier.get(module_id, {}).get("pins", []))
            assert not overlap, (build_id, module_id, overlap)
    # And the recipes really do wire each of those pins to its connector part.
    import json
    from pathlib import Path

    data = Path(__file__).resolve().parents[1] / "src" / "hardware_splicer" / "data" / "catalog_recipes.json"
    recipes = json.loads(data.read_text(encoding="utf-8"))["recipes"]
    for module_id, info in carrier.items():
        recipe = recipes[info["build"]]
        roles = {m["role"]: m["moduleId"] for m in recipe["modules"]}
        wired = {
            (roles[w["from"]["role"]], w["from"]["pin"]) for w in recipe["wires"]
        } | {(roles[w["to"]["role"]], w["to"]["pin"]) for w in recipe["wires"]}
        for pin in info["pins"]:
            assert (module_id, pin) in wired, (module_id, pin)
        assert info["connector"] in roles.values()


def test_recipe_specific_no_connects_need_the_netlist_to_come_from_that_recipe() -> None:
    from hardware_splicer.netlist.lower import build_graph_to_netlist
    from hardware_splicer.plan_to_graph import splice_plan_to_build_graph

    # An arbitrary netlist that merely carries the catalog build name inherits nothing.
    arbitrary = _netlist([("U6", "mosfet-irlz44n")], {})
    assert "U6.VOUT+" not in _nc(arbitrary, "automatic_plant_watering")
    # The real recipe netlist does get its documented terminals.
    graph, _id, _n, _w = splice_plan_to_build_graph({"target": {"recommended_build_id": "automatic_plant_watering"}})
    real = build_graph_to_netlist(graph)
    mosfet = next(c.ref for c in real.components if c.module_id == "mosfet-irlz44n")
    assert f"{mosfet}.VOUT+" in _nc(real, "automatic_plant_watering")
    # A recipe netlist with an extra wire is no longer that recipe.
    tampered = CircuitNetlist.from_dict(real.to_dict())
    tampered.nets.append(Net(name="EXTRA", pins=[PinRef(mosfet, "SIG"), PinRef(mosfet, "GND")]))
    assert f"{mosfet}.VOUT+" not in _nc(tampered, "automatic_plant_watering")


def test_l298n_5v_is_left_for_erc_unless_the_recipe_states_jumper_and_motor_supply() -> None:
    import json
    from pathlib import Path

    from hardware_splicer.integrations.schematic_pin_policy import load_policy
    from hardware_splicer.netlist.lower import build_graph_to_netlist
    from hardware_splicer.plan_to_graph import splice_plan_to_build_graph

    # No build context: the 5V terminal is an unflagged open pin (it may need an external supply).
    assert "U5.5V" not in _nc(_netlist([("U5", "l298n")], {}))
    assert "U5.5V" not in _nc(_netlist([("U5", "l298n")], {}), "robot_drive_base")
    # The module-level blanket entry is gone; only the robot recipe may state it.
    assert "5V" not in (load_policy().get("module_pins") or {}).get("l298n", {})
    graph, _id, _n, _w = splice_plan_to_build_graph({"target": {"recommended_build_id": "robot_drive_base"}})
    real = build_graph_to_netlist(graph)
    l298 = next(c.ref for c in real.components if c.module_id == "l298n")
    assert f"{l298}.5V" in _nc(real, "robot_drive_base")
    # The recipe really states the fitted jumper and a motor supply inside the 78M05 range.
    data = Path(__file__).resolve().parents[1] / "src" / "hardware_splicer" / "data" / "catalog_recipes.json"
    note = " ".join(json.loads(data.read_text(encoding="utf-8"))["recipes"]["robot_drive_base"]["notes"])
    assert "5V_EN jumper" in note and "7-12 V" in note
    # If the recipe stopped saying so, the no-connect would disappear with it.
    policy = json.loads(json.dumps(load_policy()))
    policy["build_pins"]["robot_drive_base"]["l298n"]["5V"]["requires_recipe_note"] = "jumper removed"
    assert f"{l298}.5V" not in {
        f"{p.ref}.{p.pin}" for p in plan_no_connects(real, build_id="robot_drive_base", policy=policy)
    }
