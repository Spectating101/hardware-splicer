"""Adversarial invariants for CM5 V2.21 4V+auxiliary5V electrical bring-up."""
import json
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET
import pytest
from hardware_splicer.cm5_power_boot_gate import assess, BringupGateError

BASE=Path(__file__).resolve().parents[1]/"examples/cyberdeck/compute_carrier/cm5_reference"
NEW=BASE/"bringup_candidate"
OLD=BASE/"integrated_candidate"
XML=(NEW/"BRINGUP_NATIVE_NETLIST.xml").read_bytes()
REF=(OLD/"INTEGRATED_NATIVE_NETLIST.xml").read_bytes()
PINOUT=json.loads((BASE/"vendor_pin_names.json").read_text())
ERC=(NEW/"BRINGUP_ERC_OPEN.txt").read_bytes()
OLD_ERC=(OLD/"INTEGRATED_ERC_OPEN.txt").read_bytes()
META=json.loads((NEW/"bringup_manifest.json").read_text())
RECEIPT=json.loads((NEW/"bringup_validation.json").read_text())

def check(new=XML,old=REF,pinout=PINOUT,erc=ERC,base_erc=OLD_ERC,meta=META):
    return assess(new,old,pinout,erc,base_erc,meta)

def mutate(fn):
    root=ET.fromstring(XML)
    fn(root)
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)

def net(root,name):
    return next(n for n in root.findall("./nets/net") if n.get("name")==name)

def test_verified_native_kicad_export_exact_receipt():
    a=check()
    assert a==RECEIPT
    assert a["five_volt_auxiliary_contact"]==106
    assert a["five_volt_link_ref"]=="R7"
    assert len(a["four_keys_checked"])==4
    assert a["unchanged_original_connections"]==143
    assert a["newly_connected_contacts"]==23
    assert a["erc_open_findings"]["pin_not_connected"]==167
    assert not a["erc_clean"] and not a["fabrication_authorized"]

def test_auxiliary_5v_not_short_circuited_into_4v():
    def short(root):
        node=next(v for v in net(root,"/5V_HDMI").findall("node") if v.get("ref")=="U3")
        net(root,"/5V_HDMI").remove(node)
        net(root,"/VCC_SYSIN").append(node)
    with pytest.raises(BringupGateError,match="5V_HDMI|SYSIN"):
        check(new=mutate(short))

def test_auxiliary_5v_must_not_bypass_series_link():
    def bypass(root):
        node=next(v for v in net(root,"/5V_HDMI").findall("node") if v.get("ref")=="U3")
        net(root,"/5V_HDMI").remove(node)
        net(root,"/VCC5V0_SYS").append(node)
    with pytest.raises(BringupGateError,match="5V_HDMI|auxiliary"):
        check(new=mutate(bypass))

def test_wrong_pin106_revision_is_rejected():
    p=deepcopy(PINOUT)
    p["pin_names"]["106"]="NC"
    with pytest.raises(BringupGateError,match="pin106"):
        check(pinout=p)

@pytest.mark.parametrize("signal,ref",[
    ("PWRON_L","SW1"),("RESET_L","SW2"),
    ("SARADC_VIN0_BOOT","SW3"),
    ("SARADC_VIN1_KEY/RECOVERY","SW4"),
])
def test_button_miswiring_fails(signal,ref):
    def sever(root):
        n=net(root,"/"+signal)
        node=next(v for v in n.findall("node") if v.get("ref")=="U3")
        n.remove(node)
    with pytest.raises(BringupGateError,match=signal.replace("/","/")[:8]):
        check(new=mutate(sever))

def test_button_ground_missing_detected():
    def missing(root):
        n=net(root,"/GND")
        n.remove(next(v for v in n.findall("node") if v.get("ref")=="SW3"))
    with pytest.raises(BringupGateError,match="GND"):
        check(new=mutate(missing))

def test_upstream_usb_current_limit_must_remain_unchanged():
    def modified(root):
        n=net(root,"/ILIM_USB")
        n.remove(next(v for v in n.findall("node") if v.get("ref")=="U2"))
    with pytest.raises(BringupGateError,match="original connected|upstream"):
        check(new=mutate(modified))

def test_nc290_cannot_be_coopted():
    def corrupt(root):
        ET.SubElement(net(root,"/VCC5V0_SYS"),"node",ref="U3",pin="290")
    with pytest.raises(BringupGateError,match="newly driven|NC290|shorted across nets"):
        check(new=mutate(corrupt))

@pytest.mark.parametrize("flag",[
    "fabrication_authorized","power_on_tested","pcb_routed",
    "gpio_vref_qualified","input_protection_present",
])
def test_metadata_must_not_falsely_certify(flag):
    m=deepcopy(META)
    m[flag]=True
    with pytest.raises(BringupGateError,match="release qualification"):
        check(meta=m)

def test_native_erc_issues_not_suppressed():
    altered=ERC.replace(b"[pin_not_connected]",b"[not_an_error]")
    with pytest.raises(BringupGateError,match="unconnected pin delta"):
        check(erc=altered)

def test_actual_no_fab_schematic_and_local_vendor_switch_are_present():
    sch=(NEW/"CM5_POWER_BOOT_ELECTRIC_NOT_FOR_FAB.kicad_sch").read_text()
    assert sch.count('(lib_id "HS_CM5_OFFICIAL:Radxa_CM5")')==3
    assert sch.count('(lib_id "Switch:SW_Push")')==4
    assert (NEW/"HS_Switch_Reference.kicad_sym").exists()
    assert not list(NEW.glob("*.kicad_pcb"))
    assert "NOT FOR FAB" in (NEW/"README.md").read_text()
