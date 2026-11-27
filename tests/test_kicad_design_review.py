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
    gate = ("Net-(Q3-G)", [("Q3", "1", "G", "input"), ("U1", "10", "GPIO10", "bidirectional")])  # driven, as on the real board (by Q4)
    reversed_ = netlist([PMOS, MCU], [("+VSW", [("Q3", "3", "D", "passive")]), ("UG_PWR", [("Q3", "2", "S", "passive")]), gate])
    assert rules(reversed_) == ["mosfet_source_drain"]
    correct = netlist([PMOS, MCU], [("+VSW", [("Q3", "2", "S", "passive")]), ("UG_PWR", [("Q3", "3", "D", "passive")]), gate])
    assert rules(correct) == []


def test_deliberate_drain_on_supply_circuits_are_not_flagged():
    """Patterns from known-good open boards: PiUPS's common-source pair and Beepy's VBUS/battery load-sharing switch."""
    q2 = ("Q2", "IRF7404", "Transistor_FET", "IRF7404", "P-Channel MOSFET")
    pair = netlist([PMOS, q2], [("+5V", [("Q3", "3", "D", "passive")]), ("Net-(Q3-S)", [("Q3", "2", "S", "passive"), ("Q2", "2", "S", "passive")]),
                                ("V_UPS", [("Q2", "3", "D", "passive")]), ("Net-(Q3-G)", [("Q3", "1", "G", "input"), ("Q2", "1", "G", "input")])])
    assert rules(pair) == []
    load_sharing = netlist([PMOS, MCU], [("+BATT", [("Q3", "3", "D", "passive")]), ("Net-(D1-K)", [("Q3", "2", "S", "passive")]),
                                         ("VBUS", [("Q3", "1", "G", "input"), ("U1", "2", "VBUS", "power_in")])])
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
    guard = netlist([PMOS, MCU], [("VCC", [("Q3", "3", "D", "passive")]), ("Net-(Q1-S)", [("Q3", "2", "S", "passive")]),
                                  ("GND", [("Q3", "1", "G", "input"), ("U1", "1", "GND", "power_in")])])
    assert rules(guard) == []
    via_resistor = netlist([PMOS, ("R1", "100k", "Device", "R", "Resistor")],
                           [("VCC", [("Q3", "3", "D", "passive")]), ("Net-(Q1-S)", [("Q3", "2", "S", "passive")]),
                            ("Net-(Q3-G)", [("Q3", "1", "G", "input"), ("R1", "1", "", "passive")]), ("GND", [("R1", "2", "", "passive")])])
    assert rules(via_resistor) == []
    nmos = ("Q4", "AO3400A", "Transistor_FET", "AO3400A", "N-Channel MOSFET")
    low_side_guard = netlist([nmos, MCU], [("GND", [("Q4", "3", "D", "passive"), ("U1", "1", "GND", "power_in")]), ("BAT-", [("Q4", "2", "S", "passive")]),
                                           ("+BATT", [("Q4", "1", "G", "input"), ("U1", "2", "VBAT", "power_in")])])
    assert rules(low_side_guard) == []


def test_a_receptacle_named_by_part_number_is_known_by_its_cc_pins():
    """Allegra42/ZEReader-KiCad 13fb744f and brenocq/bldc-motor 526db53d: CUI UJ20-C and a 12402012E212A receptacle."""
    usb = ("J5", "UJ20-C-H-G-SMT-TR", "UJ20-C-H-G-SMT-TR", "UJ20-C-H-G-SMT-TR", "")
    pins = [("UJ20-C-H-G-SMT-TR", "UJ20-C-H-G-SMT-TR", [("A5", "CC1", "bidirectional"), ("B5", "CC2", "bidirectional")])]
    assert rules(netlist([usb], [], pins)) == ["usb_c_cc_no_pulldown"] * 2
    controller = ("U3", "HUSB238", "Interface_USB", "HUSB238", "USB PD sink controller")
    cpins = [("Interface_USB", "HUSB238", [("1", "CC1", "bidirectional"), ("2", "CC2", "bidirectional")])]
    assert rules(netlist([controller], [], cpins)) == []


def test_usb_c_data_wired_on_one_row_only_is_flagged():
    """FPGA-Research/FABulous_board c64a369c joined the second D+/D- pins 'to allow a reversible plugging'."""
    usb = ("U4", "USB_C_Receptacle_USB2.0", "Connector", "USB_C_Receptacle_USB2.0", "USB 2.0-only Type-C Receptacle connector")
    rd = [("R1", "5.1k", "Device", "R", "Resistor"), ("R2", "5.1k", "Device", "R", "Resistor")]
    pins = [("Connector", "USB_C_Receptacle_USB2.0", [("A5", "CC1", "bidirectional"), ("B5", "CC2", "bidirectional"), ("A6", "D+", "bidirectional"),
                                                       ("B6", "D+", "bidirectional"), ("A7", "D-", "bidirectional"), ("B7", "D-", "bidirectional")])]
    mcu = ("U1", "RP2040", "MCU_RaspberryPi", "RP2040", "MCU")
    cc = [("CC1", [("U4", "A5", "CC1", "bidirectional"), ("R1", "1", "", "passive")]), ("CC2", [("U4", "B5", "CC2", "bidirectional"), ("R2", "1", "", "passive")]),
          ("GND", [("R1", "2", "", "passive"), ("R2", "2", "", "passive")])]
    one_row = netlist([usb, mcu, *rd], [*cc, ("USB_DP", [("U4", "B6", "D+", "bidirectional"), ("U1", "47", "USB_DP", "bidirectional")]),
                                        ("USB_DM", [("U4", "A7", "D-", "bidirectional"), ("U1", "46", "USB_DM", "bidirectional")])], pins)
    assert rules(one_row) == ["usb_c_data_one_side"] * 2
    both = netlist([usb, mcu, *rd], [*cc, ("USB_DP", [("U4", "A6", "D+", "bidirectional"), ("U4", "B6", "D+", "bidirectional"), ("U1", "47", "USB_DP", "bidirectional")]),
                                     ("USB_DM", [("U4", "A7", "D-", "bidirectional"), ("U4", "B7", "D-", "bidirectional"), ("U1", "46", "USB_DM", "bidirectional")])], pins)
    assert rules(both) == []


def test_sda_and_scl_on_one_net_is_a_short():
    """bitaxeorg/bitaxeGamma a75fdfd7 'fixed SDA/SCL short' (KiCad ERC saw two labels on one net)."""
    parts = [("U5", "EMC2101", "Sensor_Temperature", "EMC2101", "Fan controller, I2C"), ("U8", "INA260", "Sensor_Energy", "INA260", "Power monitor, I2C"),
             ("R1", "4.7k", "Device", "R", "Resistor")]
    short = netlist(parts, [("SCL", [("U5", "8", "SMDATA", "bidirectional"), ("U5", "7", "SMCLK", "input"), ("U8", "9", "SCL", "input"),
                                     ("U8", "8", "SDA", "bidirectional"), ("R1", "1", "", "passive")]), ("+3V3", [("R1", "2", "", "passive")])])
    assert rules(short) == ["i2c_sda_scl_short"]


def test_a_forgotten_input_floats_but_marked_and_gpio_pins_do_not():
    """DuPAL-PAL-DUmper/DuPAL_Board 218f80b8 'Fix missing connection on a shifter': U9's CE was left open."""
    shifter = ("U9", "74HC165", "74xx", "74HC165", "Parallel-in shift register")
    mcu = ("U1", "RP2040", "MCU_RaspberryPi", "RP2040", "MCU")
    forgotten = netlist([shifter, mcu], [("unconnected-(U9-CE-Pad15)", [("U9", "15", "CE", "input")]),
                                         ("unconnected-(U1-GPIO7-Pad9)", [("U1", "9", "GPIO7", "input")])])
    assert rules(forgotten) == ["input_pin_floating"]
    marked = netlist([shifter], [("unconnected-(U9-CE-Pad15)", [("U9", "15", "CE", "input+no_connect")])])
    assert rules(marked) == []
    charger = ("U9", "BQ25895RTWR", "Battery_Management", "BQ25895", "Charger")  # azlan-works/Argo leaves QON open: it has an internal pull-up
    found = review(netlist([charger], [("unconnected-(U9-QON-Pad12)", [("U9", "12", "QON", "input")])]))["findings"]
    assert [(f["rule"], f["severity"]) for f in found] == [("input_pin_floating", "info")]


def test_an_i2c_bus_known_only_by_its_net_name_needs_a_pull_up_too():
    """StuartF303/vandaemon 0f5083fa 'fit the I2C pull-ups': GPIO pins to a connector, named /MCU/I2C_SDA."""
    mcu = ("U1", "ESP32-C3", "MCU_Espressif", "ESP32-C3", "MCU")
    header = ("J13", "Conn_01x04", "Connector_Generic", "Conn_01x04", "Generic connector")
    bare = netlist([mcu, header], [("/MCU/I2C_SDA", [("U1", "20", "IO12", "bidirectional"), ("J13", "3", "Pin_3", "passive")])])
    assert [(f["rule"], f["severity"]) for f in review(bare)["findings"]] == [("i2c_no_pullup", "info")]  # the far side may hold the pull-ups
    sensor = ("U2", "SHT40", "Sensor_Humidity", "SHT40", "Humidity sensor")
    on_board = netlist([mcu, sensor], [("/MCU/I2C_SDA", [("U1", "20", "IO12", "bidirectional"), ("U2", "3", "DATA", "bidirectional")])])
    assert rules(on_board) == ["i2c_no_pullup"]
    pulled = netlist([mcu, header, ("R45", "4.7k", "Device", "R", "Resistor")],
                     [("/MCU/I2C_SDA", [("U1", "20", "IO12", "bidirectional"), ("J13", "3", "Pin_3", "passive"), ("R45", "1", "", "passive")]),
                      ("+3V3", [("R45", "2", "", "passive")])])
    assert rules(pulled) == []


def test_part_kinds_need_whole_words():
    """beagleboard/capes: an Eagle RESISTOR-(INCH)-0402 was read as an N-channel MOSFET because of 'nch' in 'inch'."""
    from hardware_splicer.kicad_design_review import _kind

    eagle_r = {"lib": "TechLab-eagle-import", "part": "RESISTOR-(INCH)-0402", "description": "Basic SMD Resistors", "value": "4.7k", "pins": []}
    assert _kind(eagle_r, "R24") == "resistor"
    for description, kind in (("P-Channel MOSFET", "pmos"), ("-30V P-Ch MOSFET", "pmos"), ("N-Channel MOSFET, SOT-23", "nmos"), ("30V N-CH", "nmos")):
        assert _kind({"lib": "Transistor_FET", "part": "X", "description": description, "value": "", "pins": []}, "Q1") == kind, description


def test_component_footprints_and_part_number_fields_are_read():
    """KiCad 9 writes part fields both as (fields (field ...)) and as (property ...); either way they reach the model."""
    text = """(export (version "E")
      (components
        (comp (ref "R14") (value "5.1k") (footprint "Resistor_SMD:R_0402_1005Metric")
          (fields (field (name "LCSC Part") "C25905") (field (name "Datasheet")))
          (libsource (lib "Device") (part "R_US") (description "Resistor"))
          (property (name "PARTNO") (value "RMCF0402JT5K10"))))
      (libparts) (nets))"""
    comp = parse_netlist(text)["components"]["R14"]
    assert comp["footprint"] == "Resistor_SMD:R_0402_1005Metric"
    assert comp["fields"]["LCSC Part"] == "C25905" and comp["fields"]["PARTNO"] == "RMCF0402JT5K10"


# ---- datasheet pull rules (2026-11-27), each modelled on a real fix commit --------------------------------------------

RES = ("R9", "10k", "Device", "R", "Resistor")
PROG_HEADER = ("J5", "Conn_01x05", "Connector", "Conn_01x05", "Generic connector")


def test_esp32_chip_pu_that_only_reaches_a_header_floats():
    # elkel53930/extraice4 1c2461b8: CHIP_PU went to a programming header only; the fix added a 10 k pull-up.
    bare = netlist([MCU, PROG_HEADER], [("/CHIP_PU", [("U1", "4", "CHIP_PU", "input"), ("J5", "3", "Pin_3", "passive")])])
    found = review(bare)["findings"]
    assert [f["rule"] for f in found] == ["esp32_enable_floating"] and "must not be left floating" in found[0]["basis"]
    pulled = netlist([MCU, PROG_HEADER, RES], [("/CHIP_PU", [("U1", "4", "CHIP_PU", "input"), ("J5", "3", "Pin_3", "passive"), ("R9", "1", "", "passive")]),
                                          ("+3V3", [("R9", "2", "", "passive")])])
    assert rules(pulled) == []
    supervisor = netlist([MCU, ("U8", "TPS3839", "Power_Supervisor", "TPS3839", "supervisor")],
                         [("/EN", [("U1", "4", "EN", "input"), ("U8", "3", "~{RESET}", "output")])])
    assert rules(supervisor) == []
    devkit = netlist([("U1", "ESP32-DevKitC", "MCU_Module", "ESP32-DevKitC", "dev board"), PROG_HEADER],
                     [("/EN", [("U1", "2", "EN", "input"), ("J5", "3", "Pin_3", "passive")])])
    assert rules(devkit) == []


def test_z80_int_and_busreq_need_a_pullup_but_nmi_is_not_claimed():
    z80 = ("U10", "Z84C0020", "CPU", "Z80CPU", "Z80 CPU")
    bare = netlist([z80, PROG_HEADER], [("/INT", [("U10", "16", "~{INT}", "input"), ("J5", "1", "Pin_1", "passive")]),
                                   ("/NMI", [("U10", "17", "~{NMI}", "input"), ("J5", "2", "Pin_2", "passive")])])
    found = review(bare)["findings"]
    assert [(f["rule"], f["net"]) for f in found] == [("z80_wired_or_no_pullup", "/INT")]  # UM0080 says nothing of the kind for NMI
    pulled = netlist([z80, PROG_HEADER, RES], [("/INT", [("U10", "16", "~{INT}", "input"), ("J5", "1", "Pin_1", "passive"), ("R9", "1", "", "passive")]),
                                          ("+5V", [("R9", "2", "", "passive")])])
    assert rules(pulled) == []


def test_mdio_follows_zero_ohm_links_and_defers_to_a_module_edge():
    # antmicro/dc-scm-osm-l-carrier-card 5f320f74: the PHY's MDIO reached the module only through a 0 ohm link; the fix
    # added 1.5 k to 3.3 V.
    phy = ("U7", "RTL8211FDI-CG", "Interface_Ethernet", "RTL8211F", "Gigabit PHY")
    link = ("R110", "R_0R_0402", "Device", "R", "Resistor")
    som = ("U1", "OSM-L_Carrier-side", "OSM", "OSM-L", "module connector")
    lone = netlist([phy], [("/MDIO", [("U7", "24", "MDIO", "bidirectional")])])
    assert [f["severity"] for f in review(lone)["findings"] if f["rule"] == "mdio_no_pullup"] == ["warning"]
    via_link = netlist([phy, link, som], [("/MDIO", [("U7", "24", "MDIO", "bidirectional"), ("R110", "2", "", "passive")]),
                                          ("/RGMII.MDIO", [("R110", "1", "", "passive"), ("U1", "C7", "ETH_MDIO", "passive")])])
    found = [f for f in review(via_link)["findings"] if f["rule"] == "mdio_no_pullup"]
    assert len(found) == 1 and found[0]["severity"] == "info" and "U1" in found[0]["message"]
    fixed = netlist([phy, link, som, ("R219", "R_1k5_0402", "Device", "R", "Resistor")],
                    [("/MDIO", [("U7", "24", "MDIO", "bidirectional"), ("R110", "2", "", "passive"), ("R219", "1", "", "passive")]),
                     ("/RGMII.MDIO", [("R110", "1", "", "passive"), ("U1", "C7", "ETH_MDIO", "passive")]), ("+3V3", [("R219", "2", "", "passive")])])
    assert "mdio_no_pullup" not in rules(fixed)


# ---- swaps visible from pin functions (2026-11-27) ------------------------------------------------------------------

def test_usb_d_plus_meeting_d_minus_is_an_error_but_an_esd_channel_is_not():
    # cheyao/icepi-sbc 2f939f5f: the SoC's USB_D0+ met the connector's D- and the hub's D+.
    soc = ("U1", "H3", "MCU", "H3", "SoC")
    usb = ("J2", "USB_A", "Connector", "USB_A", "USB connector")
    crossed = netlist([soc, usb], [("/USB_D0+", [("U1", "5", "USB_D0+", "bidirectional"), ("J2", "3", "D-", "passive")])])
    found = review(crossed)["findings"]
    assert [(f["severity"], f["rule"]) for f in found] == [("error", "diff_pair_polarity_swap")]
    straight = netlist([soc, usb], [("/USB_D0+", [("U1", "5", "USB_D0+", "bidirectional"), ("J2", "3", "D+", "passive")])])
    assert rules(straight) == []
    # CM4 IO board: a TPD4EUSB30 clamp channel named D2+ sits on D-; its channels carry no polarity.
    esd = ("U4", "TPD4EUSB30", "CM4IO", "TPD4EUSB30", "4-Channel ESD Protection for Super-Speed USB 3.0 Interface")
    hub = ("U13", "VL805", "Interface_USB", "VL805", "USB hub")
    clamp = netlist([esd, hub, usb], [("/USBD_N", [("J2", "2", "D-", "passive"), ("U13", "9", "HSD1_M", "bidirectional"),
                                                   ("U4", "2", "D2+", "passive")])])
    assert rules(clamp) == []


def test_a_crossed_high_speed_lane_is_a_warning():
    soc = ("U14", "SoC", "MCU", "SoC", "SoC")
    mux = ("U16", "Redriver", "Interface", "PI3EQX", "redriver")
    lane = netlist([soc, mux], [("/PCIE_TX0", [("U14", "1", "PCIe_A_HSO0_P", "output"), ("U16", "2", "TX0_N", "input")])])
    assert [(f["severity"], f["rule"]) for f in review(lane)["findings"]] == [("warning", "diff_pair_polarity_swap")]


def test_sda_meeting_scl_is_caught_when_the_symbol_types_the_pins_passive():
    # antmicro/osm-l-bmc-som d755ff2e: the PMIC's SCL (typed passive) met the EEPROM's SDA.
    pmic = ("U13", "PCA9450", "Power_Management", "PCA9450", "PMIC")
    eeprom = ("U16", "24C02", "Memory_EEPROM", "24C02", "EEPROM")
    swapped = netlist([pmic, eeprom], [("/PMIC_I2C.SCL", [("U13", "10", "SCL", "passive"), ("U16", "5", "SDA", "bidirectional")])])
    assert "i2c_sda_scl_short" in rules(swapped)


DIODE = ("D1", "1N4148", "Diode", "1N4148", "Small signal diode")
DIODE_PINS = ("Diode", "1N4148", [("1", "K", "passive"), ("2", "A", "passive")])


def test_a_diode_forward_biased_from_a_rail_to_ground_is_an_error_but_a_drop_between_rails_is_not():
    short = netlist([DIODE], [("+3V3", [("D1", "2", "A", "passive"), ("U9", "1", "VDD", "power_in")]), ("GND", [("D1", "1", "K", "passive")])], [DIODE_PINS])
    assert "diode_forward_across_rails" in rules(short)
    clamp = netlist([DIODE], [("GND", [("D1", "2", "A", "passive")]), ("+3V3", [("D1", "1", "K", "passive")])], [DIODE_PINS])
    assert rules(clamp) == []
    drop = netlist([DIODE], [("+5V", [("D1", "2", "A", "passive")]), ("/4.6V", [("D1", "1", "K", "passive")])], [DIODE_PINS])
    assert rules(drop) == []


def test_an_led_with_its_anode_on_ground_can_never_light():
    led = ("D2", "Red", "Device", "LED", "Light emitting diode")
    pins = ("Device", "LED", [("1", "K", "passive"), ("2", "A", "passive")])
    backwards = netlist([led], [("GND", [("D2", "2", "A", "passive")]), ("/LED", [("D2", "1", "K", "passive"), ("R1", "1", "", "passive")])], [pins])
    assert rules(backwards) == ["led_reversed"]
    forwards = netlist([led], [("GND", [("D2", "1", "K", "passive")]), ("/LED", [("D2", "2", "A", "passive"), ("R1", "1", "", "passive")])], [pins])
    assert rules(forwards) == []


def test_an_npn_with_its_collector_on_ground_is_flagged():
    npn = ("Q5", "2N3904", "Transistor_BJT", "2N3904", "Small Signal NPN Transistor")
    pins = ("Transistor_BJT", "2N3904", [("1", "E", "passive"), ("2", "B", "passive"), ("3", "C", "passive")])
    flipped = netlist([npn], [("/~{RESET}", [("Q5", "1", "E", "passive")]), ("GND", [("Q5", "3", "C", "passive")])], [pins])
    assert rules(flipped) == ["bjt_collector_emitter_reversed"]
    right = netlist([npn], [("/~{RESET}", [("Q5", "3", "C", "passive")]), ("GND", [("Q5", "1", "E", "passive")])], [pins])
    assert rules(right) == []


def test_power_pins_on_the_wrong_rail_but_not_a_stacked_chips_local_ground():
    ldo = ("U2", "LDO", "Regulator_Linear", "LP5907", "LDO")
    on_rail = netlist([ldo], [("/A-2V5", [("U2", "2", "GND", "power_in"), ("C2", "2", "", "passive")])])
    assert rules(on_rail) == ["ground_pin_on_supply"]
    asic = ("IC4", "BM1397", "Miner", "BM1397", "ASIC")
    grounded = netlist([asic], [("GND", [("IC4", "33", "VDD", "power_in"), ("C1", "2", "", "passive")])])
    assert rules(grounded) == ["supply_pin_on_ground"]
    stacked = netlist([asic], [("/BM1397-1/GND1", [("IC4", "33", "VDD", "power_in"), ("C1", "2", "", "passive")])])
    assert rules(stacked) == []


ESD = ("U6", "USBLC6-2SC6", "Power_Protection", "USBLC6-2SC6", "ESD protection")
ESD_PINS = ("Power_Protection", "USBLC6-2SC6", [("1", "I/O1", "passive"), ("6", "I/O1", "passive"), ("3", "I/O2", "passive"), ("4", "I/O2", "passive")])


def test_a_pass_through_clamp_that_joins_d_plus_to_d_minus_is_flagged_but_flow_through_is_not():
    crossed = netlist([ESD], [("USB_D-", [("U6", "1", "I/O1", "passive"), ("U4", "13", "USB_D-", "bidirectional")]),
                              ("USB_D+", [("U6", "6", "I/O1", "passive"), ("U4", "14", "USB_D+", "bidirectional")])], [ESD_PINS])
    assert rules(crossed) == ["joined_pins_split"]
    flow = netlist([ESD], [("DU-", [("U6", "1", "I/O1", "passive"), ("J1", "A7", "D-", "bidirectional")]),
                           ("D-", [("U6", "6", "I/O1", "passive"), ("U4", "13", "USB_D-", "bidirectional")])], [ESD_PINS])
    assert rules(flow) == []


def test_a_net_named_sda_on_an_scl_pin_is_flagged():
    bridge = ("U3", "SN65DSI84", "Interface", "SN65DSI84", "DSI to LVDS bridge")
    swapped = netlist([bridge], [("/DSICtrl_1V8.SDA", [("U3", "15", "SCL", "input"), ("R4", "1", "", "passive")]),
                                 ("/DSICtrl_1V8.SCL", [("U3", "16", "SDA", "bidirectional"), ("R5", "1", "", "passive")])])
    assert rules(swapped) == ["net_name_pin_mismatch", "net_name_pin_mismatch"]
    right = netlist([bridge], [("/DSICtrl_1V8.SDA", [("U3", "16", "SDA", "bidirectional"), ("R4", "1", "", "passive")])])
    assert "net_name_pin_mismatch" not in rules(right)


def test_a_part_number_whose_kicad_symbol_numbers_pins_differently_is_flagged():
    from hardware_splicer.part_lookup import libraries_available, symbol_pins

    if not libraries_available():
        pytest.skip("KiCad's symbol libraries are not installed")
    theirs = {p["number"]: p["name"] for p in symbol_pins("Transistor_FET", "AO3401A", limit=None)["pins"]}
    assert theirs == {"1": "G", "2": "S", "3": "D"}
    fet = ("Q3", "AO3401A", "Device", "Q_PMOS_GDS", "P-MOSFET")
    gds = ("Device", "Q_PMOS_GDS", [("1", "G", "input"), ("2", "D", "passive"), ("3", "S", "passive")])
    wrong = netlist([fet], [("/G", [("Q3", "1", "G", "input")])], [gds])
    assert "pinout_differs_from_kicad_library" in rules(wrong)
    gsd = ("Device", "Q_PMOS_GSD", [("1", "G", "input"), ("2", "S", "passive"), ("3", "D", "passive")])
    right = netlist([("Q3", "AO3401A", "Device", "Q_PMOS_GSD", "P-MOSFET")], [("/G", [("Q3", "1", "G", "input")])], [gsd])
    assert "pinout_differs_from_kicad_library" not in rules(right)
