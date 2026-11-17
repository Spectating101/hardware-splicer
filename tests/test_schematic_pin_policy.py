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


def test_connected_pin_never_gets_a_no_connect_even_when_policy_lists_it() -> None:
    # The policy lists MOSFET VOUT+ for this build, but here the pump is wired to it.
    netlist = _netlist(
        [("U1", "mosfet-irlz44n"), ("M1", "cooling_fan_5v")],
        {"LOAD": ["U1.VOUT+", "M1.VCC"]},
    )
    flagged = _nc(netlist, "automatic_plant_watering")
    assert "U1.VOUT+" not in flagged
    assert "U1.VOUT-" in flagged  # still open, and listed for the build


def test_unlisted_unconnected_pin_stays_open_for_kicad_to_report() -> None:
    # indicator_or_task_light never mentions the MOSFET SIG pin, so it must not be hidden.
    netlist = _netlist([("U3", "mosfet-irlz44n")], {})
    assert "U3.SIG" not in _nc(netlist, "indicator_or_task_light")
    # ...and without a build id nothing build-specific applies at all.
    assert "U3.VOUT+" not in _nc(netlist, None)


def test_off_board_terminal_applies_only_to_the_build_that_names_it() -> None:
    netlist = _netlist([("U3", "mosfet-irlz44n")], {})
    assert {"U3.VOUT+", "U3.VOUT-"} <= _nc(netlist, "automatic_plant_watering")
    assert "U3.SIG" not in _nc(netlist, "automatic_plant_watering")
    assert "U3.VOUT+" not in _nc(netlist, "robot_drive_base")


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

