"""Guard active USB VBUS switch successor against silent pin/limit regressions."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
from xml.etree import ElementTree as ET
import pytest

from hardware_splicer.cm5_sgm2590_successor_gate import (
    assess, SuccessorGateError, decode, PINMAP, PART
)

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"examples/cyberdeck/compute_carrier/cm5_reference"
CAND=BASE/"sgm2590_candidate"
NEW=(CAND/"CM5_SGM2590_NATIVE_NETLIST.xml").read_bytes()
OLD=(BASE/"CM5_5V4V_USB_REFERENCE_NETLIST.xml").read_bytes()
ERC=(CAND/"CM5_SGM2590_ERC.txt").read_bytes()
CONTRACT=json.loads((CAND/"sgm2590_source_contract.json").read_text())
PINOUT=json.loads((BASE/"vendor_pin_names.json").read_text())
REPORT=json.loads((CAND/"sgm2590_validation.json").read_text())

def xml_change(fn):
    root=ET.fromstring(NEW)
    fn(root)
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)

def test_active_manufacturer_supported_replacement_and_netlist_equivalence():
    result=assess(NEW,OLD,ERC,CONTRACT,PINOUT)
    assert result==REPORT
    assert result["successor_model"]==PART
    assert result["manufacturer_recommended_replacement"]
    assert result["source_io_net_topology_unchanged"]
    assert result["validated_power_usb_nets"]==14
    assert not result["assembly_authorized"]

def test_full_successor_sot23_5_physical_pin_functions():
    nets,parts,chips=decode(NEW)
    assert chips["SGM2590"]==PINMAP
    assert "SGM2576" not in chips
    assert parts["U2"].startswith("SGM2590XN5G_TR_ACTIVE")
    assert parts["R6"]=="4.53k_1pct_USB_ILIM"

def test_current_limit_uses_new_not_obsolete_equation():
    assert abs(REPORT["new_current_limit_typical_a"]-1.5)<0.001
    assert abs(REPORT["old_current_limit_reference_a"]-1.4468)<0.001
    assert REPORT["new_current_limit_typical_a"]!=REPORT["old_current_limit_reference_a"]

def test_wrong_model_mislabeled_as_successor_fails():
    c=deepcopy(CONTRACT);c["usb_switch_mpn"]="SGM2576YN5G/TR"
    with pytest.raises(SuccessorGateError,match="active part"):
        assess(NEW,OLD,ERC,c,PINOUT)

def test_critical_programming_pin_cannot_be_called_ocb():
    def mutate(root):
        chip=next(x for x in root.findall(".//libpart") if x.get("part")=="SGM2590")
        pin=next(x for x in chip.findall("./pins/pin") if x.get("num")=="3")
        pin.set("name","OCB")
    with pytest.raises(SuccessorGateError,match="5 electrical"):
        assess(xml_change(mutate),OLD,ERC,CONTRACT,PINOUT)

def test_wrong_sgm_port_vbus_routing_fails():
    def mutate(root):
        net=next(x for x in root.findall("./nets/net") if x.get("name")=="/USB_VBUS_SW")
        pin=next(x for x in net.findall("node") if x.get("ref")=="U2")
        pin.set("pin","5")
    with pytest.raises(SuccessorGateError,match="USB_VBUS_SW"):
        assess(xml_change(mutate),OLD,ERC,CONTRACT,PINOUT)

def test_change_of_unswitched_regulator_vin_fails():
    def mutate(root):
        net=next(x for x in root.findall("./nets/net") if x.get("name")=="/VCC5V0_SYS")
        pin=next(x for x in net.findall("node") if x.get("ref")=="U1")
        pin.set("pin","7")
    with pytest.raises(SuccessorGateError,match="VCC5V0_SYS"):
        assess(xml_change(mutate),OLD,ERC,CONTRACT,PINOUT)

def test_old_4v_regulator_topology_must_survive_upgrade():
    def mutate(root):
        comp=next(x for x in root.findall("./components/comp") if x.get("ref")=="R1")
        comp.find("value").text="68k_UNAPPROVED"
    with pytest.raises(SuccessorGateError,match="BOM"):
        assess(xml_change(mutate),OLD,ERC,CONTRACT,PINOUT)

def test_no_assumption_of_pin_to_pad_land_pattern_or_thermal_approval():
    assert not REPORT["exact_pcb_landpattern_tested"]
    assert not REPORT["input_power_and_sgm_switch_tested"]
    c=deepcopy(CONTRACT);c["replacement_footprint_dimension_compared"]=True
    with pytest.raises(SuccessorGateError,match="footprint_dimension"):
        assess(NEW,OLD,ERC,c,PINOUT)

def test_current_limit_formula_exponent_cannot_be_dropped():
    c=deepcopy(CONTRACT);c["usb_ilim_typical_a"]=6800/4530
    with pytest.raises(SuccessorGateError,match="nonlinear"):
        assess(NEW,OLD,ERC,c,PINOUT)

def test_esp32_or_other_pinout_cannot_be_spliced_in():
    c=deepcopy(PINOUT);c["pin_names"]["97"]="GPIO1_A0"
    with pytest.raises(SuccessorGateError,match="pad mapping"):
        assess(NEW,OLD,ERC,CONTRACT,c)

def test_erc_non_symbol_finding_rejected():
    e=ERC+b"\n[multiple_net_names]: unsafe power rail alias\n"
    with pytest.raises(SuccessorGateError,match="ERC"):
        assess(NEW,OLD,e,CONTRACT,PINOUT)

def test_nonproduction_complete_evidence_files_exist():
    assert (CAND/"CM5_SGM2590_USB_POWER_NOT_FOR_FAB.kicad_sch").exists()
    assert (CAND/"HS_Power.kicad_sym").exists()
    assert (CAND/"sym-lib-table").exists()
    assert CONTRACT["sgm2590_recommended_successor_ref"]=="https://www.sg-micro.com/product/SGM2590"
    assert not CONTRACT["supplier_actual_order_placed"]
    assert not CONTRACT["fabrication_authorized"]
