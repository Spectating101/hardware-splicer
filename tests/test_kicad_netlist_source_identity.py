"""Native KiCad named fields must remain actual references, pads and named nets."""
from pathlib import Path

import pytest

from hardware_splicer.netlist.import_kicad import parse_kicad_netlist
from hardware_splicer.netlist.lower import build_graph_to_netlist, netlist_to_build_graph


ROOT = Path(__file__).resolve().parents[1]


def membership(circuit):
    return {net.name: {(pin.component_ref, pin.pin) for pin in net.pins} for net in circuit.nets}


def test_native_example_keeps_every_original_reference_pad_and_named_net():
    circuit = parse_kicad_netlist((ROOT / "examples/main_ctrl_esp32_servo.net").read_text())
    expected = {
        "VBUS": {("J1", "1"), ("U2", "7"), ("U2", "8"), ("U3", "3")},
        "GND": {("J1", "2"), ("U1", "15"), ("U1", "38"), ("U2", "3"), ("U3", "1"), ("J2", "4"), ("J3", "1"), ("J4", "2")},
        "USB_D+": {("J1", "3"), ("U2", "4")},
        "USB_D-": {("J1", "4"), ("U2", "5")},
        "+3V3": {("U1", "1"), ("U2", "6"), ("U3", "2"), ("J2", "3"), ("R1", "1"), ("R2", "1")},
        "EN": {("U1", "2"), ("R1", "2")},
        "GPIO0": {("U1", "25"), ("R2", "2")},
        "UART_TX": {("U1", "34"), ("U2", "23")},
        "UART_RX": {("U1", "35"), ("U2", "22")},
        "SDA": {("U1", "30"), ("J2", "1")},
        "SCL": {("U1", "31"), ("J2", "2")},
        "SERVO_5V": {("J3", "2"), ("J4", "1")},
        "SERVO_PWM_PAN": {("U1", "27"), ("J3", "3")},
        "SERVO_PWM_TILT": {("U1", "28"), ("J3", "4")},
    }
    assert membership(circuit) == expected
    assert {pin.component_ref for net in circuit.nets for pin in net.pins} <= {comp.ref for comp in circuit.components}
    assert membership(build_graph_to_netlist(netlist_to_build_graph(circuit))) == expected


@pytest.mark.parametrize("net", [
    '(net (name "PRIVATE BUS") (node (pin "EP") (ref "U37") (pinfunction "GND")) (code 9) (node (ref "J42") (pin "A1")))',
    '(net 9 "PRIVATE BUS" (node "U37" "EP") (node "J42" "A1"))',
])
def test_named_reordered_and_legacy_flat_nodes_preserve_alphanumeric_contacts(net):
    text = '(export (components (comp (ref "U37")) (comp (ref "J42"))) (nets ' + net + '))'
    circuit = parse_kicad_netlist(text)
    assert membership(circuit) == {"PRIVATE BUS": {("U37", "EP"), ("J42", "A1")}}


@pytest.mark.parametrize("node", ['(node (ref "U37"))', '(node (pin "EP"))', '(node (ref (nested "U37")) (pin "EP"))'])
def test_incomplete_or_nested_identity_cannot_be_stringified_into_a_fake_contact(node):
    with pytest.raises(ValueError, match="KiCad"):
        parse_kicad_netlist('(export (nets (net (code 1) (name "GND") ' + node + ')))')
