"""Native KiCad reference power+USB gate with adversarial shorts and label tests."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from hardware_splicer.cm5_power_usb_reference_gate import (
    NETS, CHIPS, PowerUsbValidationError, validate,
)

BASE=Path(__file__).resolve().parents[1]/"examples/cyberdeck/compute_carrier/cm5_reference"
XML=(BASE/"CM5_5V4V_USB_REFERENCE_NETLIST.xml").read_bytes()
ERC=(BASE/"CM5_5V4V_USB_REFERENCE_ERC.txt").read_bytes()
CONTRACT=json.loads((BASE/"5v4v_usb_reference_contract.json").read_text())
RECEIPT=json.loads((BASE/"5v4v_usb_reference_validation.json").read_text())

def tamper(changer)->bytes:
    r=ET.fromstring(XML)
    changer(r)
    return ET.tostring(r,encoding="utf-8",xml_declaration=True)

def net(root,name):
    return next(n for n in root.findall("./nets/net") if n.get("name")==name)

def test_genuine_native_netlist_and_source_receipt_match():
    out=validate(XML,ERC,CONTRACT)
    assert out==RECEIPT
    assert out["native_electrical_nets_checked"]==14
    assert out["component_count"]==21
    assert out["power_rail_5v_and_4v_separate"]
    assert out["usb_vbus_after_switch"]
    assert not out["board_fabrication_authorized"]

def test_reference_buck_4v_feeds_output_only_through_inductor():
    assert ("L1","1") in NETS["/SW_MPS"]
    assert ("L1","2") in NETS["/VCC_SYSIN"]
    assert ("U1","5") in NETS["/VCC_SYSIN"]
    assert ("U1","1") in NETS["/VCC5V0_SYS"]
    assert ("U1","8") in NETS["/BST_MPS"]
    assert ("U1","11") in NETS["/FB_MPS"]
    assert ("U1","12") in NETS["/EN_MPS"]

def test_cm5_usb_enable_and_usb_a_power_after_switch():
    assert NETS["/USB_HOST_PWREN_H"]=={("J2","5"),("U2","4")}
    assert NETS["/USB_VBUS_SW"]=={("U2","1"),("J3","1"),("C9","1")}
    assert NETS["/USB20_HOST0_DP"]=={("J2","3"),("J3","3")}
    assert NETS["/USB20_HOST0_DM"]=={("J2","4"),("J3","2")}
    assert NETS["/ILIM_USB"]=={("R6","1"),("U2","3")}

def test_sgm_vendor_pin3_and_rilimit_difference_remains_visible():
    out=validate(XML,ERC,CONTRACT)
    assert out["sgm_pin3_vendor_datasheet_name"]=="ILIM"
    assert out["sgm_pin3_reference_label_conflicts"]
    assert 1.44<out["usb_ilim_nominal_a"]<1.45
    assert CONTRACT["usb_switch_status"]=="OBSOLETE"
    assert not CONTRACT["fabrication_authorized"]

def test_feedback_4v_nominal_and_component_sourcing():
    out=validate(XML,ERC,CONTRACT)
    assert 4.03<out["feedback_vout_nominal_v"]<4.05
    assert CONTRACT["regulator_min_vin_v"]==4.5
    assert not CONTRACT["rated_inductor_selected"]
    assert "monolithicpower.com" in CONTRACT["mp_datasheet"]

def test_power_net_short_in_xml_is_rejected():
    def tweak(root):
        n=net(root,"/GND")
        ET.SubElement(n,"node",ref="J1",pin="1")
    with pytest.raises(PowerUsbValidationError,match="physical contact|net"):
        validate(tamper(tweak),ERC,CONTRACT)

def test_usb_host_dp_dm_crossover_rejected():
    def tweak(root):
        n=net(root,"/USB20_HOST0_DM")
        next(x for x in n.findall("node") if x.get("ref")=="J3").set("pin","3")
    with pytest.raises(PowerUsbValidationError,match="USB20_HOST0_DM|physical contact"):
        validate(tamper(tweak),ERC,CONTRACT)

def test_mp8759_sense_fb_rail_wrong_rejected():
    def tweak(root):
        n=net(root,"/FB_MPS")
        next(x for x in n.findall("node") if x.get("ref")=="U1").set("pin","5")
    with pytest.raises(PowerUsbValidationError,match="FB_MPS|physical contact"):
        validate(tamper(tweak),ERC,CONTRACT)

def test_usb_power_not_permitted_without_loadswitch():
    def tweak(root):
        n=net(root,"/USB_VBUS_SW")
        next(x for x in n.findall("node") if x.get("ref")=="U2").set("pin","5")
    with pytest.raises(PowerUsbValidationError,match="USB_VBUS_SW|physical contact"):
        validate(tamper(tweak),ERC,CONTRACT)

def test_obsolete_switch_disclosure_fail_closed():
    c=deepcopy(CONTRACT);c["usb_switch_status"]="IN_PRODUCTION"
    with pytest.raises(PowerUsbValidationError,match="obsolete|status"):
        validate(XML,ERC,c)

def test_sgm_pin3_claim_ocb_rejected():
    c=deepcopy(CONTRACT);c["usb_pin3_name_vendor_datasheet"]="OCB"
    with pytest.raises(PowerUsbValidationError,match="pin3"):
        validate(XML,ERC,c)

def test_power_feedback_miscalculation_rejected():
    c=deepcopy(CONTRACT);c["expected_nominal_vout_v"]=5.0
    with pytest.raises(PowerUsbValidationError,match="voltage"):
        validate(XML,ERC,c)

def test_mps_symbol_pin_number_swap_rejected():
    def tweak(root):
        lib=next(x for x in root.findall(".//libpart") if x.get("part")=="MP8759GD")
        next(x for x in lib.findall("./pins/pin") if x.get("num")=="7").set("name","VIN")
    with pytest.raises(PowerUsbValidationError,match="identity"):
        validate(tamper(tweak),ERC,CONTRACT)

def test_erc_really_has_no_short_errors_but_config_warning_preserved():
    r=validate(XML,ERC,CONTRACT)
    assert r["erc_findings"]=={"lib_symbol_issues":23}
    with pytest.raises(PowerUsbValidationError,match="ERC"):
        validate(XML,ERC+b"\n[pin_to_pin]: electrical short\n",CONTRACT)

def test_fabrication_and_test_flags_never_fake_success():
    c=deepcopy(CONTRACT);c["fabrication_authorized"]=True
    with pytest.raises(PowerUsbValidationError,match="authorized"):
        validate(XML,ERC,c)
    c=deepcopy(CONTRACT);c["usb_esd_present"]=True
    with pytest.raises(PowerUsbValidationError,match="unsupported"):
        validate(XML,ERC,c)

def test_unrouted_svg_only_and_local_symbol_library_exist():
    sch=(BASE/"CM5_5V4V_USB_REFERENCE_NOT_FOR_FAB.kicad_sch").read_text()
    assert "(kicad_sch" in sch
    assert "SGM2576_OBSOLETE_SUBSTITUTE_NEEDED" in sch
    assert "EXTERNAL REGULATED 5V" in sch
    assert (BASE/"HS_Power.kicad_sym").exists()
    assert (BASE/"sym-lib-table").exists()
