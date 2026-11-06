"""Independent KiCad-exported schematic contract and adversarial validation."""
from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest

from hardware_splicer.cm5_bench_netlist_gate import (
    BenchSchematicError, EXPECTED, EXPECTED_GROUND_PINS, validate,
)

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/"examples/cyberdeck/compute_carrier/cm5_reference"
NETLIST=(D/"CM5_BENCH_HARNESS_NETLIST_EVIDENCE.xml").read_bytes()
ERC=(D/"CM5_BENCH_HARNESS_ERC_OPEN.txt").read_bytes()
RECEIPT=json.loads((D/"bench_harness_native_validation.json").read_text())
SCH=(D/"CM5_BENCH_HARNESS_NOT_FOR_FAB.kicad_sch").read_text()

def tamper(change) -> bytes:
    root=ET.fromstring(NETLIST)
    change(root)
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)

def test_native_kicad_connections_require_six_live_4v_pins():
    result=validate(NETLIST,ERC)
    assert result["verified_4v_input_contacts"]==[77,79,81,83,85,87]
    assert result["verified_ground_contacts"]==76
    assert result["no_4v_to_ground_short"]
    assert result["pin290_unconnected"]
    assert result==RECEIPT

def test_power_supply_connects_j1_and_both_decouplers():
    root=ET.fromstring(NETLIST)
    power=next(n for n in root.findall(".//nets/net") if n.get("name")=="/VCC_SYSIN")
    assert {(n.get("ref"),n.get("pin")) for n in power.findall("node")}==EXPECTED["/VCC_SYSIN"]
    assert not (set(EXPECTED["/VCC_SYSIN"]) & set(EXPECTED["/GND"]))
    assert len(EXPECTED["/VCC_SYSIN"])==9

def test_data_only_port_never_claims_five_volt_switch():
    r=validate(NETLIST,ERC)
    assert r["usb_vbus_not_present"]
    assert r["usb2_host0_data_pins"]==[263,265]
    assert all(n in r["required_net_labels"] for n in ("/USB20_HOST0_DP","/USB20_HOST0_DM"))
    assert "USB2_HOST0_SIGNAL_ONLY_NO_VBUS" in SCH

def test_debug_rx_and_tx_are_not_swapped():
    r=validate(NETLIST,ERC)
    assert r["uart2_pins"]==[51,55]
    assert "UART2_LOGIC_LEVEL_NOT_VERIFIED" in SCH

def test_no_false_manufacturing_claim_or_empty_erc():
    r=validate(NETLIST,ERC)
    assert not r["erc_clean"] and not r["safe_to_fabricate"] and not r["release_authorized"]
    assert r["erc_open_findings"]["pin_not_connected"]>=100
    assert r["erc_open_findings"]["power_pin_not_driven"]>=1
    assert "V2.21 PIN 290=NC" in SCH

def test_wrong_power_connector_pin_is_rejected():
    def mutate(root):
        net=next(n for n in root.findall(".//nets/net") if n.get("name")=="/VCC_SYSIN")
        next(n for n in net.findall("node") if n.get("ref")=="J1").set("pin","2")
    with pytest.raises(BenchSchematicError,match="VCC_SYSIN"):
        validate(tamper(mutate),ERC)

def test_missing_module_power_contact_rejected():
    def mutate(root):
        net=next(n for n in root.findall(".//nets/net") if n.get("name")=="/VCC_SYSIN")
        net.remove(next(n for n in net.findall("node") if n.get("ref")=="U1" and n.get("pin")=="83"))
    with pytest.raises(BenchSchematicError,match="VCC_SYSIN"):
        validate(tamper(mutate),ERC)

def test_usb_differential_pair_swap_rejected():
    def mutate(root):
        net=next(n for n in root.findall(".//nets/net") if n.get("name")=="/USB20_HOST0_DP")
        next(n for n in net.findall("node") if n.get("ref")=="U1").set("pin","265")
    with pytest.raises(BenchSchematicError,match="USB20_HOST0_DP"):
        validate(tamper(mutate),ERC)

def test_no_connect_pin290_cannot_become_active():
    def mutate(root):
        net=next(n for n in root.findall(".//nets/net") if n.get("name")=="/UART2_RX_M0")
        ET.SubElement(net,"node",ref="U1",pin="290")
    with pytest.raises(BenchSchematicError,match="UART2_RX_M0|290"):
        validate(tamper(mutate),ERC)

def test_ground_separation_cannot_be_silently_accepted():
    def mutate(root):
        net=next(n for n in root.findall(".//nets/net") if n.get("name")=="/GND")
        ET.SubElement(net,"node",ref="J1",pin="1")
    with pytest.raises(BenchSchematicError,match="overlap|multiple"):
        validate(tamper(mutate),ERC)

def test_critical_open_erc_findings_must_remain_explicit():
    erc=ERC.replace(b"[pin_not_connected]",b"[no_markers_for_unconnected]")
    with pytest.raises(BenchSchematicError,match="incomplete schematic"):
        validate(NETLIST,erc)

def test_erc_label_conflict_must_fail():
    erc=ERC+b"\n[multiple_net_names]: 4V and GND tied together\n"
    with pytest.raises(BenchSchematicError,match="conflicting net"):
        validate(NETLIST,erc)

def test_no_unvalidated_4v_to_5v_conversion():
    assert not RECEIPT["standalone_linux_boot_tested"]
    assert RECEIPT["power_external_regulated_4v_3a_only"]
    assert not RECEIPT["usb_vbus_not_present"] is False
    assert "MAX CURRENT NOT VERIFIED" in SCH

def test_cache_is_genuine_native_xml_and_erc_evidence():
    root=ET.fromstring(NETLIST)
    assert root.tag=="export"
    components={c.get("ref") for c in root.findall(".//components/comp")}
    assert {"U1","J1","J2","J3","C1","C2"}.issubset(components)
    assert len(ERC)>1000 and b"ERC report" in ERC
