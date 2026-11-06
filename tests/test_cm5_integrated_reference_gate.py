"""Adversarial source comparisons for CM5 physically numbered SoM integration."""
from __future__ import annotations
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from copy import deepcopy
import pytest

from hardware_splicer.cm5_integrated_reference_gate import (
    assess, IntegratedGateError
)

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"examples/cyberdeck/compute_carrier/cm5_reference"
DIR=BASE/"integrated_candidate"
XML=(DIR/"INTEGRATED_NATIVE_NETLIST.xml").read_bytes()
REF=(BASE/"sgm2590_candidate/CM5_SGM2590_NATIVE_NETLIST.xml").read_bytes()
PINOUT=json.loads((BASE/"vendor_pin_names.json").read_text())
ERC=(DIR/"INTEGRATED_ERC_OPEN.txt").read_bytes()
MANIFEST=json.loads((DIR/"integration_manifest.json").read_text())
RECEIPT=json.loads((DIR/"integrated_validation.json").read_text())

def corrupt(fn)->bytes:
    root=ET.fromstring(XML)
    fn(root)
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)

def net(root,name):
    return next(n for n in root.findall("./nets/net") if n.get("name")==name)

def test_full_official_cm5_symbol_replaces_logical_only_harness():
    r=assess(XML,REF,PINOUT,ERC,MANIFEST)
    assert r==RECEIPT
    assert r["real_cm5_symbol_pin_count"]==300
    assert r["physical_ground_pins"]==76
    assert r["physical_vcc_sysin_pins"]==[77,79,81,83,85,87]
    assert r["physical_usb_power_enable_pins"]==[97]
    assert r["physical_usb_dp_pins"]==[263]
    assert r["physical_usb_dm_pins"]==[265]
    assert r["pin290_held_nc"]

def test_regulator_buck_and_usb_switch_circuits_remain_unchanged():
    root=ET.fromstring(XML)
    nets={n.get("name"):{(v.get("ref"),v.get("pin")) for v in n.findall("./node")}
          for n in root.findall("./nets/net")}
    for name in ("/SW_MPS","/BST_MPS","/FB_MPS","/EN_MPS","/USB_VBUS_SW"):
        assert nets[name]
        assert all(ref!="U3" for ref,pin in nets[name])
    assert ("U3","77") in nets["/VCC_SYSIN"]
    assert ("U3","97") in nets["/USB_HOST_PWREN_H"]
    assert ("U3","263") in nets["/USB20_HOST0_DP"]
    assert ("U3","265") in nets["/USB20_HOST0_DM"]

def test_unreviewed_pins_remain_erc_release_blockers():
    assert RECEIPT["erc_open_findings"]["pin_not_connected"]>=100
    assert RECEIPT["erc_open_findings"]["power_pin_not_driven"]>=1
    assert not RECEIPT["erc_clean"]
    assert not RECEIPT["fabrication_authorized"]
    assert not RECEIPT["high_speed_routing_test"]
    assert not RECEIPT["physical_power_test"]

def test_missing_one_vcc_sysin_pin_detected():
    def fn(root):
        n=net(root,"/VCC_SYSIN")
        n.remove(next(v for v in n.findall("node") if v.get("ref")=="U3" and v.get("pin")=="83"))
    with pytest.raises(IntegratedGateError,match="VCC_SYSIN"):
        assess(corrupt(fn),REF,PINOUT,ERC,MANIFEST)

def test_one_ground_label_on_5v_detected():
    def fn(root):
        n=net(root,"/GND")
        ET.SubElement(n,"node",ref="J1",pin="1")
    with pytest.raises(IntegratedGateError,match="contact|GND"):
        assess(corrupt(fn),REF,PINOUT,ERC,MANIFEST)

def test_wrong_usb_data_polarity_rejected():
    def fn(root):
        n=net(root,"/USB20_HOST0_DM")
        next(v for v in n.findall("node") if v.get("ref")=="U3").set("pin","263")
    with pytest.raises(IntegratedGateError,match="contact|DM"):
        assess(corrupt(fn),REF,PINOUT,ERC,MANIFEST)

def test_missing_power_enable_detected():
    def fn(root):
        n=net(root,"/USB_HOST_PWREN_H")
        n.remove(next(v for v in n.findall("node") if v.get("ref")=="U3"))
    with pytest.raises(IntegratedGateError,match="PWREN"):
        assess(corrupt(fn),REF,PINOUT,ERC,MANIFEST)

def test_cm5_manufacturer_pin290_must_stay_nc():
    def fn(root):
        n=net(root,"/USB_VBUS_SW")
        ET.SubElement(n,"node",ref="U3",pin="290")
    with pytest.raises(IntegratedGateError,match="USB_VBUS_SW|290"):
        assess(corrupt(fn),REF,PINOUT,ERC,MANIFEST)

def test_metadata_false_manufacturing_claim_rejected():
    modified=deepcopy(MANIFEST)
    modified["fabrication_authorized"]=True
    with pytest.raises(IntegratedGateError,match="authorized"):
        assess(XML,REF,PINOUT,ERC,modified)

def test_manufacturer_pin_labels_must_match_libpart():
    def fn(root):
        p=next(x for x in root.findall(".//libpart[@part='Radxa_CM5']/pins/pin") if x.get("num")=="97")
        p.set("name","UNVERIFIED")
    with pytest.raises(IntegratedGateError,match="vendor workbook"):
        assess(corrupt(fn),REF,PINOUT,ERC,MANIFEST)

def test_not_masking_unconnected_pin_erc():
    bad=ERC.replace(b"[pin_not_connected]",b"[unmentioned_error]")
    with pytest.raises(IntegratedGateError,match="ERC open"):
        assess(XML,REF,PINOUT,bad,MANIFEST)

def test_known_power_short_rejected_by_native_erc():
    bad=ERC+b"\n[multiple_net_names]: shorted input to output\n"
    with pytest.raises(IntegratedGateError,match="conflict"):
        assess(XML,REF,PINOUT,bad,MANIFEST)

def test_native_kicad_study_not_fabricated_board():
    sch=(DIR/"CM5_FULL_SYMBOL_POWER_USB_NOT_FOR_FAB.kicad_sch").read_text()
    assert "(kicad_sch" in sch
    assert sch.count('(lib_id "HS_CM5_OFFICIAL:Radxa_CM5")')==3
    assert (DIR/"HS_CM5_OFFICIAL.kicad_sym").exists()
    assert not list(DIR.glob("*.kicad_pcb"))
