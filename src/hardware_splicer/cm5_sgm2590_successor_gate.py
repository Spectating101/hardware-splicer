"""Validate supported SGM2590 replacement against source CM5 power netlist.

The manufacturer nominates the active SGM2590 as successor to obsolete
SGM2576. Equivalent five electrical pin functions are independently checked
against the vendor's April 2025 datasheet. This is NOT an approval of exact
land pattern, power margin, EMI/ESD, or physical manufacturability.
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from math import isclose

from hardware_splicer.cm5_power_usb_reference_gate import NETS, CHIPS

SCHEMA="hs.cm5_sgm2590_successor_gate.v1"
PINMAP={"1":"VOUT","2":"GND","3":"ILIM","4":"EN","5":"VIN"}
DATASHEET_URL="https://www.sg-micro.com/rect/assets/28859410-24d5-43f6-8723-76d4c3a5d0e7/SGM2590_SGM2590D.pdf"
PART="SGM2590XN5G/TR"
CLASSIC_MPN="SGM2576YN5G/TR"

class SuccessorGateError(ValueError):
    pass

def decode(netlist:bytes)->tuple[dict,dict,dict]:
    try:root=ET.fromstring(netlist)
    except ET.ParseError as e:raise SuccessorGateError("invalid native KiCad XML") from e
    if root.tag!="export":raise SuccessorGateError("not KiCad exported XML")
    nets={}
    for n in root.findall("./nets/net"):
        name=n.get("name")
        if not name or name in nets:raise SuccessorGateError("duplicate net")
        nets[name]={(x.get("ref"),x.get("pin")) for x in n.findall("node")}
    comp={c.get("ref"):c.findtext("value","") for c in root.findall("./components/comp")}
    chips={}
    for l in root.findall("./libparts/libpart"):
        chips[l.get("part")]={p.get("num"):p.get("name") for p in l.findall("./pins/pin")}
    return nets,comp,chips

def assess(successor_bytes:bytes, predecessor_bytes:bytes, erc:bytes,
           source:dict, pinout:dict)->dict:
    current,parts,chips=decode(successor_bytes)
    previous,old_parts,old_chips=decode(predecessor_bytes)
    for name,expected in NETS.items():
        if current.get(name)!=expected:
            raise SuccessorGateError(f"new physical net {name} differs from audited reference")
        if current.get(name)!=previous.get(name):
            raise SuccessorGateError(f"SGM replacement changed motherboard reference connectivity {name}")
    if len(parts)!=21 or set(parts)!=set(old_parts):
        raise SuccessorGateError("unexplained candidate BOM change")
    if any(parts[k]!=old_parts[k] for k in parts if k not in {"U2","R6"}):
        raise SuccessorGateError("unexpected non-switch BOM/logic change")
    if chips.get("SGM2590")!=PINMAP:
        raise SuccessorGateError("SGM2590 5 electrical functions or pin numbers wrong")
    if chips.get("SGM2576") is not None:
        raise SuccessorGateError("obsolete switch library remains in new schematic")
    if chips.get("MP8759GD")!=CHIPS["U1"]:
        raise SuccessorGateError("MP8759 pin identity changed during successor swap")
    if "SGM2590XN5G" not in parts["U2"] or "ACTIVE" not in parts["U2"]:
        raise SuccessorGateError("successor model not explicitly sourced")
    if not parts["R6"].startswith("4.53k"):
        raise SuccessorGateError("source current-limit resistor not applied")
    if source.get("usb_switch_mpn")!=PART or source.get("usb_switch")!="SGM2590":
        raise SuccessorGateError("candidate missing active part identity")
    if (source.get("usb_switch_status")!="ACTIVE_VIA_MANUFACTURER_PRODUCT_PAGE"
          or source.get("usb_switch_manufacturer_recommends_replacing")!="SGM2576"):
        raise SuccessorGateError("SGMICRO recommendation not recorded")
    if source.get("sgm2590_datasheet_url")!=DATASHEET_URL:
        raise SuccessorGateError("manufacturer datasheet source missing")
    if (source.get("usb_switch_pin3_name_vendor_datasheet")!="ILIM"
          or source.get("usb_pin3_name_reference_pdf")!="OCB"):
        raise SuccessorGateError("manufacturer/reference pin3 naming mismatch hidden")
    if source.get("usb_rilim_ohm")!=4530:
        raise SuccessorGateError("changed current-limit resistor unqualified")
    expected_ma=6612/(4.53**0.982)
    if not isclose(source.get("usb_ilim_typical_a",0),expected_ma/1000,abs_tol=0.00001):
        raise SuccessorGateError("wrong SGM2590 nonlinear current-limit law")
    if pinout.get("manufacturer_revision")!="V2.21":
        raise SuccessorGateError("unknown host module pinout revision")
    mapping=pinout.get("pin_names",{})
    if {mapping.get(str(i)) for i in (97,263,265)} != {
        "USB_HOST_PWREN_H","USB20_HOST0_DP","USB20_HOST0_DM"
    }:
        raise SuccessorGateError("CM5 physical host-control and data pad mapping changed")
    flags=dict(Counter(re.findall(r"^\[([^\]]+)\]:",erc.decode("utf-8"),re.MULTILINE)))
    if set(flags)-{"lib_symbol_issues"}:
        raise SuccessorGateError("remaining KiCad ERC electrical violations")
    for key in ("fabrication_authorized","usb_esd_present",
                "replacement_thermal_behavior_validated","replacement_footprint_dimension_compared",
                "full_bom_mpn_footprints_qualified","supplier_actual_order_placed"):
        if source.get(key) is not False:
            raise SuccessorGateError(f"{key}: unsupported build readiness claim")
    return {
        "schema":SCHEMA,
        "successor_model":PART,"predecessor_model":CLASSIC_MPN,
        "manufacturer_recommended_replacement":True,
        "five_pin_functions_equivalent":True,
        "source_io_net_topology_unchanged":True,
        "validated_power_usb_nets":len(NETS),
        "other_component_values_unchanged":True,
        "current_limit_r_kohm":4.53,
        "new_current_limit_typical_a":expected_ma/1000,
        "old_current_limit_reference_a":6800/4700,
        "erc_electrical_net_findings":0,
        "erc_library_config_warnings":flags.get("lib_symbol_issues",0),
        "input_power_and_sgm_switch_tested":False,
        "esd_and_emi_qualified":False,
        "exact_pcb_landpattern_tested":False,
        "assembly_authorized":False,
        "next_gate":"Qualify SGM2590 package land pattern and thermal/current limits, add USB DP/DM ESD protection and regulator input protection, then integrate with physical CM5 connector."
    }

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    for a in ("--new-netlist","--old-netlist","--erc","--contract","--pinout","--output"):
        p.add_argument(a,required=True,type=Path)
    args=p.parse_args()
    result=assess(args.new_netlist.read_bytes(),args.old_netlist.read_bytes(),
                  args.erc.read_bytes(),json.loads(args.contract.read_text()),
                  json.loads(args.pinout.read_text()))
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
