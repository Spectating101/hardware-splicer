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


def test_deliberate_drain_on_supply_circuits_are_not_flagged():
    """Patterns from known-good open boards: PiUPS's common-source pair and Beepy's VBUS/battery load-sharing switch."""
    q2 = ("Q2", "IRF7404", "Transistor_FET", "IRF7404", "P-Channel MOSFET")
    pair = netlist([PMOS, q2], [("+5V", [("Q3", "3", "D", "passive")]), ("Net-(Q3-S)", [("Q3", "2", "S", "passive"), ("Q2", "2", "S", "passive")]),
                                ("V_UPS", [("Q2", "3", "D", "passive")]), ("Net-(Q3-G)", [("Q3", "1", "G", "input"), ("Q2", "1", "G", "input")])])
    assert rules(pair) == []
    load_sharing = netlist([PMOS], [("+BATT", [("Q3", "3", "D", "passive")]), ("Net-(D1-K)", [("Q3", "2", "S", "passive")]), ("VBUS", [("Q3", "1", "G", "input")])])
    assert rules(load_sharing) == []


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


FLIPPER = {"J20": {"board": "flipper-devices-gpio-device-flipper-zero"}}
ESP = ("U1", "ESP32-C3", "RF_Module", "ESP32-C3-MINI-1", "module")
HEADER = ("J20", "Conn_01x10", "Connector_Generic", "Conn_01x10", "Generic connector")


def _backpack(tx_function, rx_function):
    """The ten pins a Flipper Zero backpack (Chrismettal/flipper-zero-backpacks) puts on header positions 9-18."""
    return netlist([ESP, HEADER], [
        ("Ext_+3.3V", [("J20", "1", "Pin_1", "passive")]), ("SWCLK", [("J20", "2", "Pin_2", "passive")]),
        ("GND", [("J20", "3", "Pin_3", "passive"), ("J20", "10", "Pin_10", "passive")]), ("SWDIO", [("J20", "4", "Pin_4", "passive")]),
        ("TX", [("J20", "5", "Pin_5", "passive"), ("U1", "37", tx_function, "bidirectional")]),
        ("RX", [("J20", "6", "Pin_6", "passive"), ("U1", "38", rx_function, "bidirectional")]),
    ])


def test_a_declared_mate_catches_tx_wired_to_tx_across_the_connector():
    swapped = review(_backpack("TXD0", "RXD0"), FLIPPER)
    found = {f["rule"] for f in swapped["findings"]}
    assert found == {"uart_tx_to_tx_across_connector", "uart_rx_to_rx_across_connector"}
    assert all("pin offset 8, inferred from" in f["basis"] and "Black Wire" in f["basis"] for f in swapped["findings"])
    assert review(_backpack("RXD0", "TXD0"), FLIPPER)["findings"] == []


def test_without_a_declaration_or_an_alignment_nothing_is_guessed():
    assert review(_backpack("TXD0", "RXD0"))["findings"] == []
    lone = netlist([ESP, HEADER], [("TX", [("J20", "5", "Pin_5", "passive"), ("U1", "37", "TXD0", "bidirectional")])])
    assert [f["rule"] for f in review(lone, FLIPPER)["findings"]] == ["mate_unaligned"]
    assert [f["rule"] for f in review(lone, {"J20": {"board": "no-such-board"}})["findings"]] == ["mate_unknown"]
