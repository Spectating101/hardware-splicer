"""Checks on any KiCad netlist, aimed at the bug classes other checkers missed on real fix commits."""

from __future__ import annotations

import pytest

from hardware_splicer.kicad_design_review import KicadReviewError, parse_netlist, review


def netlist(comps, nets, libparts=()):
    c = "".join(f'(comp (ref "{r}") (value "{v}") (libsource (lib "{lib}") (part "{part}") (description "{d}")))' for r, v, lib, part, d in comps)
    lp = "".join(f'(libpart (lib "{lib}") (part "{part}") (pins ' + "".join(f'(pin (num "{n}") (name "{nm}") (type "{t}"))' for n, nm, t in pins) + "))"
                 for lib, part, pins in libparts)
    n = "".join(f'(net (code "{i}") (name "{name}") ' + "".join(f'(node (ref "{r}") (pin "{p}") (pinfunction "{f}") (pintype "{t}"))' for r, p, f, t in nodes) + ")"
                for i, (name, nodes) in enumerate(nets))
    return parse_netlist(f"(export (version \"E\") (components {c}) (libparts {lp}) (nets {n}))")


def rules(model):
    return [f["rule"] for f in review(model)["findings"]]


MCU = ("U1", "ESP32", "MCU", "ESP32-S3", "microcontroller")
BRIDGE = ("U2", "CH340", "Interface_USB", "CH340C", "USB to UART")


def test_tx_joined_to_tx_is_an_error_and_tx_to_rx_is_not():
    bad = netlist([MCU, BRIDGE], [("/TX", [("U1", "37", "U0TXD/GPIO43", "bidirectional"), ("U2", "2", "TXD", "output")])])
    assert rules(bad) == ["uart_tx_to_tx"]
    good = netlist([MCU, BRIDGE], [("/TX", [("U1", "37", "U0TXD/GPIO43", "bidirectional"), ("U2", "3", "RXD", "input")])])
    assert rules(good) == []


def test_net_names_never_decide_direction():
    """A net named RX on a transmit pin is not flagged: names may be written from either end."""
    one_end = netlist([MCU], [("/RX", [("U1", "37", "U0TXD/GPIO43", "bidirectional")])])
    assert rules(one_end) == []


def test_unconnected_power_pin_except_on_modules():
    chip = netlist([("U3", "LDO", "Regulator_Linear", "AP2112K", "LDO")], [("VIN", [("U3", "1", "VIN", "power_in")])])
    assert rules(chip) == ["power_pin_unconnected"]
    pico = netlist([("U4", "Pico", "MCU_Module", "RaspberryPi_Pico", "module")], [("VSYS", [("U4", "39", "VSYS", "power_in")])])
    assert rules(pico) == []


def test_i2c_without_a_pullup_and_with_one():
    sensor = ("U5", "BME280", "Sensor", "BME280", "sensor")
    bare = netlist([MCU, sensor], [("/SDA", [("U1", "8", "GPIO8/SDA", "bidirectional"), ("U5", "3", "SDA", "bidirectional")])])
    assert rules(bare) == ["i2c_no_pullup"] and "UM10204" in review(bare)["findings"][0]["basis"]
    pulled = netlist([MCU, sensor, ("R1", "4.7k", "Device", "R", "Resistor")],
                     [("/SDA", [("U1", "8", "GPIO8/SDA", "bidirectional"), ("U5", "3", "SDA", "bidirectional"), ("R1", "1", "", "passive")]),
                      ("+3V3", [("R1", "2", "", "passive")])])
    assert rules(pulled) == []


PMOS = ("Q3", "AO3401A", "Transistor_FET", "AO3401A", "-4.0A Id, -30V Vds, P-Channel MOSFET, SOT-23")


def test_a_p_channel_switch_with_its_drain_on_the_supply_is_flagged():
    """The real fix in ebastler/zmk-designguide 1b4583ed: drain on +VSW, source on the load."""
    reversed_ = netlist([PMOS], [("+VSW", [("Q3", "3", "D", "passive")]), ("UG_PWR", [("Q3", "2", "S", "passive")]), ("Net-(Q3-G)", [("Q3", "1", "G", "input")])])
    assert rules(reversed_) == ["mosfet_source_drain"]
    correct = netlist([PMOS], [("+VSW", [("Q3", "2", "S", "passive")]), ("UG_PWR", [("Q3", "3", "D", "passive")]), ("Net-(Q3-G)", [("Q3", "1", "G", "input")])])
    assert rules(correct) == []


def test_usb_c_cc_pins_need_a_pulldown_even_when_unwired():
    usb = ("J1", "USB_C_Receptacle_USB2.0", "Connector", "USB_C_Receptacle_USB2.0", "USB 2.0-only Type-C Receptacle connector")
    pins = [("Connector", "USB_C_Receptacle_USB2.0", [("A5", "CC1", "bidirectional"), ("B5", "CC2", "bidirectional"), ("A1", "GND", "passive")])]
    unwired = netlist([usb], [("GND", [("J1", "A1", "GND", "passive")])], pins)
    assert rules(unwired) == ["usb_c_cc_no_pulldown"] * 2
    rd = [("R1", "5.1k", "Device", "R", "Resistor"), ("R2", "5.1k", "Device", "R", "Resistor")]
    wired = netlist([usb, *rd], [("CC1", [("J1", "A5", "CC1", "bidirectional"), ("R1", "1", "", "passive")]),
                                 ("CC2", [("J1", "B5", "CC2", "bidirectional"), ("R2", "1", "", "passive")]),
                                 ("GND", [("J1", "A1", "GND", "passive"), ("R1", "2", "", "passive"), ("R2", "2", "", "passive")])], pins)
    assert rules(wired) == []


def test_not_a_netlist_is_refused():
    with pytest.raises(KicadReviewError):
        parse_netlist("(kicad_sch (version 1))")
