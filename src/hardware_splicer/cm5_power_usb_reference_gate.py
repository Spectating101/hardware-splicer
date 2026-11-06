"""Fail-closed KiCad power and USB reference electrical-net verifier.

This checks a native KiCad exported XML netlist, NOT a fabricated carrier.
Design is explicitly non-production: SGM2576 is obsolete, USB ESD and
module connector/PD, inductor and PMIC loop/thermal qualification pending.
"""
from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
import re
from xml.etree import ElementTree as ET

SCHEMA="hs.cm5_5v4v_usb_power_netlist_gate.v1"
NETS={
 "/VCC5V0_SYS":{("J1","1"),("U1","1"),("U2","5"),("C1","1"),("C2","1"),("C8","1"),("R3","1")},
 "/VCC_SYSIN":{("J2","1"),("U1","5"),("L1","2"),("R1","1"),("C3","1"),("C4","1"),("C5","1")},
 "/GND":{("J1","2"),("J2","2"),("J2","6"),("J3","4"),("U1","2"),("U1","10"),("U2","2"),
         ("C1","2"),("C2","2"),("C3","2"),("C4","2"),("C5","2"),("C7","2"),("C8","2"),("C9","2"),
         ("R2","2"),("R4","2"),("R6","2")},
 "/SW_MPS":{("U1","7"),("L1","1"),("C6","2")},
 "/BST_MPS":{("U1","8"),("R5","1")},
 "/BST_SERIES":{("R5","2"),("C6","1")},
 "/VCC_MPS":{("U1","9"),("C7","1")},
 "/FB_MPS":{("U1","11"),("R1","2"),("R2","1")},
 "/EN_MPS":{("U1","12"),("R3","2"),("R4","1")},
 "/ILIM_USB":{("U2","3"),("R6","1")},
 "/USB_HOST_PWREN_H":{("J2","5"),("U2","4")},
 "/USB_VBUS_SW":{("U2","1"),("J3","1"),("C9","1")},
 "/USB20_HOST0_DP":{("J2","3"),("J3","3")},
 "/USB20_HOST0_DM":{("J2","4"),("J3","2")},
}
CHIPS={"U1":{"1":"VIN","2":"PGND","3":"PG","4":"NC","5":"VOUT","6":"MODE",
             "7":"SW","8":"BST","9":"VCC","10":"AGND","11":"FB","12":"EN"},
       "U2":{"1":"VOUT","2":"GND","3":"ILIM","4":"EN","5":"VIN"}}

class PowerUsbValidationError(ValueError):
    pass

def validate(netlist:bytes,erc:bytes,contract:dict) -> dict:
    try: root=ET.fromstring(netlist)
    except ET.ParseError as e:raise PowerUsbValidationError("not KiCad XML netlist") from e
    if root.tag!="export":raise PowerUsbValidationError("wrong native netlist root")
    nets={}
    member_to_net={}
    for net in root.findall("./nets/net"):
        name=net.get("name")
        if not name or name in nets:raise PowerUsbValidationError("duplicate or empty net name")
        nodes={(x.get("ref"),x.get("pin")) for x in net.findall("node")}
        for node in nodes:
            if node in member_to_net:
                raise PowerUsbValidationError(f"physical contact {node} on two electrical nets")
            member_to_net[node]=name
        nets[name]=nodes
    for name, expected in NETS.items():
        if nets.get(name)!=expected:
            raise PowerUsbValidationError(f"unexpected KiCad net {name}: {nets.get(name)}")
    for a,b in [("/VCC5V0_SYS","/VCC_SYSIN"),("/VCC5V0_SYS","/USB_VBUS_SW"),("/GND","/VCC_SYSIN")]:
        if nets[a]&nets[b]:raise PowerUsbValidationError(f"short across {a} and {b}")
    for device,expected in CHIPS.items():
        pin_names={p.get("num"):p.get("name") for p in root.findall(f".//libpart[@part='{('MP8759GD' if device=='U1' else 'SGM2576')}']/pins/pin")}
        # For KiCad 9 native XML, libparts may use part with part's symbol name.
        if pin_names!=expected:
            raise PowerUsbValidationError(f"{device} component electrical pin identity differs from datasheet")
    for pin in ("3","4","6"):
        name=member_to_net.get(("U1",pin),"")
        if name and not name.startswith("unconnected-"):
            raise PowerUsbValidationError(f"MP8759 optional/NC pin {pin} unexpectedly connected")
    shield=member_to_net.get(("J3","5"),"")
    if shield and not shield.startswith("unconnected-"):
        raise PowerUsbValidationError("USB shield grounding requires an explicit EMI design review")
    comps={c.get("ref"):c.findtext("value","") for c in root.findall("./components/comp")}
    if len(comps)!=21:
        raise PowerUsbValidationError("missing reference schematic components")
    if set(comps)!={"J1","J2","J3","U1","U2","L1",*(f"R{i}" for i in range(1,7)),*(f"C{i}" for i in range(1,10))}:
        raise PowerUsbValidationError("unexpected BOM count or reference designator")
    if "OBSOLETE" not in comps["U2"] or comps["U1"].startswith("SGM"):
        raise PowerUsbValidationError("unqualified obsolete switch misidentified")
    if "ILIM" not in comps["R6"] or "4.7k" not in comps["R6"]:
        raise PowerUsbValidationError("SGM2576 programmable current limit value missing")
    if "1.5uH" not in comps["L1"] or "UNVERIFIED" not in comps["L1"]:
        raise PowerUsbValidationError("inductor saturation rating must be held for review")
    required=("regulator","usb_switch","usb_switch_status","usb_pin3_name_vendor_datasheet",
              "usb_pin3_name_reference_pdf","expected_nominal_vout_v","usb_ilim_typical_a")
    if any(k not in contract for k in required):raise PowerUsbValidationError("missing evidence contract")
    if contract["regulator"]!="MP8759GD-Z" or contract["usb_switch"]!="SGM2576":
        raise PowerUsbValidationError("non-approved part in contract")
    if contract["usb_switch_status"]!="OBSOLETE":
        raise PowerUsbValidationError("unqualified switch status concealed")
    if (contract["usb_pin3_name_vendor_datasheet"]!="ILIM" or
            contract["usb_pin3_name_reference_pdf"]!="OCB"):
        raise PowerUsbValidationError("source-vendor pin3 discrepancy hidden")
    if contract["feedback_high_ohm"]!=47000 or contract["feedback_low_ohm"]!=8200:
        raise PowerUsbValidationError("source feedback divider unexpectedly changed")
    vout=0.6*(1+47000/8200)
    ilimit=6800/4700
    if not math.isclose(contract["expected_nominal_vout_v"],vout,rel_tol=1e-12):
        raise PowerUsbValidationError("false regulator reference voltage computation")
    if not math.isclose(contract["usb_ilim_typical_a"],ilimit,rel_tol=1e-12):
        raise PowerUsbValidationError("false switch typical programmed current")
    if not 3.6<vout<5.2 or contract["regulator_min_vin_v"]!=4.5:
        raise PowerUsbValidationError("power design out of scope")
    report=erc.decode("utf-8")
    findings=dict(Counter(re.findall(r"^\[([^\]]+)\]:",report,re.MULTILINE)))
    # Symbol-table warnings do not prove invalid topology but remain as
    # config bugs; never suppress genuine electrical or off-grid issues.
    if any(code!="lib_symbol_issues" for code in findings):
        raise PowerUsbValidationError(f"KiCad real ERC violations remain: {findings}")
    if contract["fabrication_authorized"] or contract["power_up_test_passed"]:
        raise PowerUsbValidationError("unverified design falsely authorized for fabrication/power")
    if any(contract.get(k,False) for k in
           ("usb_esd_present","full_bom_mpn_footprints_qualified","rated_inductor_selected")):
        raise PowerUsbValidationError("source contract asserts unsupported implementation")
    return {
        "schema":SCHEMA,"native_electrical_nets_checked":len(NETS),
        "component_count":len(comps),
        "power_rail_5v_and_4v_separate":True,"regulated_4v_referenced_rail_connected":True,
        "usb_vbus_after_switch":True,"usb_enable_on_cm5_host_pwren":True,
        "sgm_pin3_vendor_datasheet_name":"ILIM",
        "sgm_pin3_reference_label_conflicts":True,
        "feedback_vout_nominal_v":vout,"usb_ilim_nominal_a":ilimit,
        "erc_only_symbol_registration_warnings":True,
        "erc_findings":findings,
        "usb_esd_tested":False,"regulator_power_up_tested":False,
        "input_supply_droop_characterized":False,
        "switch_alternative_sourced":False,
        "board_fabrication_authorized":False,
        "next_gate":"Qualify available USB switch replacement; resolve ESD/shield, 5V 5A supply margin, 1.5uH saturation, PMIC loop/signal integrity and assembly design before PCB."
    }

def main()->None:
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--netlist",required=True,type=Path)
    ap.add_argument("--erc",required=True,type=Path)
    ap.add_argument("--contract",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    a=ap.parse_args()
    r=validate(a.netlist.read_bytes(),a.erc.read_bytes(),json.loads(a.contract.read_text()))
    a.output.write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps(r,indent=2))
if __name__=="__main__":main()
