"""Checks on any KiCad netlist, aimed at the bug classes other checkers missed on real fix commits."""

from __future__ import annotations

import pytest

from hardware_splicer.kicad_design_review import KicadReviewError, parse_netlist, review, review_schematic


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


def test_usb_c_source_ports_and_controller_terminated_cc_are_not_warnings():
    """Patterns from piecol/CM5_MINIMA_REV2: a host port with 22k Rp, and CC wired straight to the CM5 module."""
    usb = ("J1", "USB_C_Receptacle_USB2.0", "Connector", "USB_C_Receptacle_USB2.0", "USB 2.0-only Type-C Receptacle connector")
    pins = [("Connector", "USB_C_Receptacle_USB2.0", [("A5", "CC1", "bidirectional"), ("B5", "CC2", "bidirectional")])]
    rp = [("R1", "22k", "Device", "R", "Resistor"), ("R2", "22k", "Device", "R", "Resistor")]
    host = netlist([usb, *rp], [("CC1", [("J1", "A5", "CC1", "bidirectional"), ("R1", "1", "", "passive")]), ("CC2", [("J1", "B5", "CC2", "bidirectional"), ("R2", "1", "", "passive")]),
                                ("+5V", [("R1", "2", "", "passive"), ("R2", "2", "", "passive")])], pins)
    assert rules(host) == []
    cm5 = ("M1", "ComputeModule5-CM5", "CM5IO", "ComputeModule5-CM5", "Raspberry Pi Compute Module 5")
    module = netlist([usb, cm5], [("CC1", [("J1", "A5", "CC1", "bidirectional"), ("M1", "94", "CC1", "passive")]),
                                  ("CC2", [("J1", "B5", "CC2", "bidirectional"), ("M1", "96", "CC2", "passive")])], pins)
    found = review(module)["findings"]
    assert [(f["rule"], f["severity"]) for f in found] == [("usb_c_cc_no_pulldown", "info")] * 2
    esd = ("U2", "USBLC6-2SC6", "Power_Protection", "USBLC6-2SC6", "Very low capacitance ESD protection diode")
    clamped = netlist([usb, esd], [("CC1", [("J1", "A5", "CC1", "bidirectional"), ("U2", "1", "IO1", "passive")]),
                                   ("CC2", [("J1", "B5", "CC2", "bidirectional"), ("U2", "3", "IO2", "passive")])], pins)
    assert [(f["rule"], f["severity"]) for f in review(clamped)["findings"]] == [("usb_c_cc_no_pulldown", "warning")] * 2


def test_a_repeated_connector_supply_pin_may_stay_open_when_its_twin_is_wired():
    pi = ("J4", "Raspberry_Pi_2_3", "Connector", "Raspberry_Pi_2_3", "expansion header for Raspberry Pi 2 & 3")
    reg = ("U6", "AP2112K-3.3", "Regulator_Linear", "AP2112K-3.3", "LDO")
    board = netlist([pi, reg], [("Pi_3v3", [("J4", "1", "3V3", "power_in"), ("U6", "5", "VOUT", "power_out")]), ("unconnected-(J4-3V3-Pad17)", [("J4", "17", "3V3", "power_in")])])
    assert rules(board) == []
    alone = netlist([reg], [("unconnected-(U6-VIN-Pad1)", [("U6", "1", "VIN", "power_in")])])
    assert rules(alone) == ["power_pin_unconnected"]


def test_unannotated_parts_give_one_note_instead_of_findings():
    """bschwind/key-ripper: every resistor is 'R?', so the CC resistors cannot be traced."""
    usb = ("U?", "TYPE-C-31-M-12", "Connector", "USB_C_Receptacle", "USB Type-C receptacle")
    pins = [("Connector", "USB_C_Receptacle", [("A5", "CC1", "bidirectional"), ("B5", "CC2", "bidirectional")])]
    board = netlist([usb, ("R?", "10k", "Device", "R", "Resistor")], [("CC1", [("U?", "A5", "CC1", "bidirectional"), ("R?", "1", "", "passive")]),
                                                                    ("CC2", [("U?", "B5", "CC2", "bidirectional"), ("R?", "1", "", "passive")])], pins)
    found = review(board)["findings"]
    assert [f["rule"] for f in found] == ["unannotated"] and "2 check(s)" in found[0]["message"]


def test_a_newer_schematic_than_kicad_cli_reads_says_which_kicad_it_needs(tmp_path, monkeypatch):
    fake = tmp_path / "kicad-cli"
    fake.write_text("#!/bin/sh\necho 'Failed to load schematic' >&2\nexit 1\n")
    fake.chmod(0o755)
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_CLI", str(fake))
    sch = tmp_path / "board.kicad_sch"
    sch.write_text('(kicad_sch\n\t(version 20260306)\n\t(generator "eeschema")\n)\n')
    with pytest.raises(KicadReviewError, match="needs KiCad 10"):
        review_schematic(sch)


def test_imported_resistors_count_by_designator_and_value():
    """azlan-works/Argo (EasyEDA Pro import): 5.1k Rd parts carry only a manufacturer part number."""
    usb = ("PWR", "TYPEC-304J-BCP16", "argo-v2-easyedapro", "TYPEC-304J-BCP16", "")
    pins = [("argo-v2-easyedapro", "TYPEC-304J-BCP16", [("A5", "CC1", "unspecified"), ("B5", "CC2", "unspecified")])]
    rd = [("R6", "5.1kΩ", "argo-v2-easyedapro", "0402WGF5101TCE", ""), ("R7", "5.1kΩ", "argo-v2-easyedapro", "0402WGF5101TCE", "")]
    board = netlist([usb, *rd], [("Net-(PWR-CC1)", [("PWR", "A5", "CC1_A5", "bidirectional"), ("R6", "1", "1_1", "passive")]),
                                 ("Net-(PWR-CC2)", [("PWR", "B5", "CC2_B5", "bidirectional"), ("R7", "1", "1_1", "passive")]),
                                 ("GND", [("R6", "2", "2_2", "passive"), ("R7", "2", "2_2", "passive")])], pins)
    assert rules(board) == []
    capacitors = [("R6", "100nF", "argo-v2-easyedapro", "CL05B104KO5NNNC", ""), ("R7", "100nF", "argo-v2-easyedapro", "CL05B104KO5NNNC", "")]
    wrong = netlist([usb, *capacitors], [("Net-(PWR-CC1)", [("PWR", "A5", "CC1_A5", "bidirectional"), ("R6", "1", "1_1", "passive")]),
                                         ("Net-(PWR-CC2)", [("PWR", "B5", "CC2_B5", "bidirectional"), ("R7", "1", "1_1", "passive")]),
                                         ("GND", [("R6", "2", "2_2", "passive"), ("R7", "2", "2_2", "passive")])], pins)
    assert rules(wrong) == ["usb_c_cc_no_pulldown"] * 2


def test_a_pull_up_to_a_regulator_output_counts_whatever_the_net_is_called():
    """azlan-works/Argo pulls its I2C bus up to VREF, the output of a TLV70430 whose pins carry no power type."""
    ldo = ("U13", "TLV70430DBVR", "argo-v2-easyedapro", "TLV70430DBVR", "")
    imu = [("U23", "LSM6DSV16XTR", "argo-v2-easyedapro", "LSM6DSV16XTR", ""), ("U24", "LIS3MDLTR", "argo-v2-easyedapro", "LIS3MDLTR", "")]
    pull = ("R41", "10kΩ", "argo-v2-easyedapro", "RC0201FR-0710KL", "")
    bus = [("U23", "14", "SDA_14", "unspecified"), ("U24", "11", "SDA/SDI/SDO_11", "unspecified"), ("R41", "2", "2_2", "unspecified")]
    pulled = netlist([ldo, *imu, pull], [("GPIO2", bus), ("VREF", [("R41", "1", "1_1", "unspecified"), ("U13", "3", "OUT_3", "unspecified")])])
    assert rules(pulled) == []
    floating = netlist([ldo, *imu, pull], [("GPIO2", bus), ("VREF", [("R41", "1", "1_1", "unspecified"), ("U13", "1", "IN_1", "unspecified")])])
    assert rules(floating) == ["i2c_no_pullup"]


def test_rails_written_with_a_point_or_an_embedded_3v3_count_as_supplies():
    """beagleboard/capes pulls I2C up to 3.3V and anyshake/explorer to D+3V3; both were read as missing pull-ups."""
    from hardware_splicer.kicad_design_review import SUPPLY

    for name in ("3.3V", "/3.3V", "1.8V", "/MCU Controller/D+3V3", "P3V3", "+3.3V", "VCC_IO"):
        assert SUPPLY.search(name), name
    for name in ("P1.26(I2C2.SDA)", "GPIO3", "/USB/CC1", "MOTOR_A", "IO12_20"):
        assert not SUPPLY.search(name), name


def test_a_pull_up_through_a_solder_jumper_counts():
    """CIRCUITSTATE/AQEYE-SB-D1: 5.1k pull-ups reach +3.3V through JP1 (I2C_PUE), a pull-up enable jumper."""
    parts = [("U1", "SCD40-D-R2", "Sensor_Gas", "SCD40", "CO2 sensor, I2C"), ("U2", "SGP40-D-R4", "Sensor_Gas", "SGP40", "VOC sensor, I2C"),
             ("R3", "5.1K", "Device", "R", "Resistor"), ("JP1", "I2C_PUE", "Jumper", "SolderJumper_2_Open", "Solder jumper")]
    board = netlist(parts, [("/I2C_SCL", [("U1", "9", "SCL", "input"), ("U2", "6", "SCL", "input"), ("R3", "1", "", "passive")]),
                            ("Net-(JP1-A)", [("R3", "2", "", "passive"), ("JP1", "1", "A", "passive")]), ("+3.3V", [("JP1", "2", "B", "passive")])])
    assert rules(board) == []


def test_alternative_bus_transceivers_sharing_rxd_are_not_a_uart_error():
    """Zektopic/ESP32S3-mini-DATALOGGER (held out): an ISO1050 and a TJA1051 share RX-CAN and TX-CAN, one fitted at a time."""
    parts = [("U401", "ISO1050DUB", "Interface_CAN_LIN", "ISO1050DUB", "Isolated CAN Transceiver, SOP-8"),
             ("U402", "TJA1051T", "Interface_CAN_LIN", "TJA1051T", "High-Speed CAN Transceiver, silent mode")]
    board = netlist(parts, [("RX-CAN", [("U401", "2", "RXD", "output"), ("U402", "4", "RXD", "output")]),
                            ("TX-CAN", [("U401", "3", "TXD", "input"), ("U402", "1", "TXD", "input")])])
    assert rules(board) == []
    mcus = [("U1", "ESP32-S3", "RF_Module", "ESP32-S3-MINI-1", "MCU"), ("U2", "RP2040", "MCU_RaspberryPi", "RP2040", "MCU")]
    assert rules(netlist(mcus, [("TX", [("U1", "37", "TXD0", "bidirectional"), ("U2", "2", "UART0_TX", "bidirectional")])])) == ["uart_tx_to_tx"]


def test_reverse_polarity_protection_mosfets_are_not_flagged():
    """Miceuz/rs485-moist-sensor: Q1's drain takes VCC from the connector, its source feeds the LDO, its gate sits on GND."""
    guard = netlist([PMOS], [("VCC", [("Q3", "3", "D", "passive")]), ("Net-(Q1-S)", [("Q3", "2", "S", "passive")]), ("GND", [("Q3", "1", "G", "input")])])
    assert rules(guard) == []
    via_resistor = netlist([PMOS, ("R1", "100k", "Device", "R", "Resistor")],
                           [("VCC", [("Q3", "3", "D", "passive")]), ("Net-(Q1-S)", [("Q3", "2", "S", "passive")]),
                            ("Net-(Q3-G)", [("Q3", "1", "G", "input"), ("R1", "1", "", "passive")]), ("GND", [("R1", "2", "", "passive")])])
    assert rules(via_resistor) == []
    nmos = ("Q4", "AO3400A", "Transistor_FET", "AO3400A", "N-Channel MOSFET")
    low_side_guard = netlist([nmos], [("GND", [("Q4", "3", "D", "passive")]), ("BAT-", [("Q4", "2", "S", "passive")]), ("+BATT", [("Q4", "1", "G", "input")])])
    assert rules(low_side_guard) == []


def test_a_receptacle_named_by_part_number_is_known_by_its_cc_pins():
    """Allegra42/ZEReader-KiCad 13fb744f and brenocq/bldc-motor 526db53d: CUI UJ20-C and a 12402012E212A receptacle."""
    usb = ("J5", "UJ20-C-H-G-SMT-TR", "UJ20-C-H-G-SMT-TR", "UJ20-C-H-G-SMT-TR", "")
    pins = [("UJ20-C-H-G-SMT-TR", "UJ20-C-H-G-SMT-TR", [("A5", "CC1", "bidirectional"), ("B5", "CC2", "bidirectional")])]
    assert rules(netlist([usb], [], pins)) == ["usb_c_cc_no_pulldown"] * 2
    controller = ("U3", "HUSB238", "Interface_USB", "HUSB238", "USB PD sink controller")
    cpins = [("Interface_USB", "HUSB238", [("1", "CC1", "bidirectional"), ("2", "CC2", "bidirectional")])]
    assert rules(netlist([controller], [], cpins)) == []
