"""Independent electrical acceptance gate for integrated CM5 + MP8759 + SGM2590.

Validate authentic KiCad XML netlists against the already audited reference
power stage and the authoritative 300-pin manufacturer V2.21 contact table.
This validates mapped net identity ONLY; no layout, transient, SI, EMI or
power-up tests have been conducted.
"""
from __future__ import annotations
from collections import Counter
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET

SCHEMA="hs.cm5_integrated_reference_gate.v1"
REQUIRED={"VCC_SYSIN":{77,79,81,83,85,87},
          "GND":set(),
          "USB_HOST_PWREN_H":{97},
          "USB20_HOST0_DP":{263},
          "USB20_HOST0_DM":{265}}
class IntegratedGateError(ValueError):
    pass

def scan(raw:bytes)->tuple[ET.Element,dict[str,set[tuple[str,str]]]]:
    try: root=ET.fromstring(raw)
    except ET.ParseError as e:raise IntegratedGateError("invalid KiCad XML netlist") from e
    if root.tag!="export":raise IntegratedGateError("unexpected KiCad export")
    nets={}
    index={}
    for n in root.findall("./nets/net"):
        name=n.get("name")
        if not name or name in nets:raise IntegratedGateError("duplicate/empty net")
        nodes={(v.get("ref"),v.get("pin")) for v in n.findall("./node")}
        for node in nodes:
            if node in index:raise IntegratedGateError(f"contact {node} exists on two nets")
            index[node]=name
        nets[name]=nodes
    return root,nets

def assess(integrated:bytes,original:bytes,pinout:dict,erc:bytes,manifest:dict)->dict:
    newroot,nets=scan(integrated)
    _,old=scan(original)
    if manifest.get("schema")!="hs.cm5_integrated_power_usb_schematic.v1":
        raise IntegratedGateError("unknown integration evidence schema")
    if pinout.get("manufacturer_revision")!="V2.21":
        raise IntegratedGateError("incorrect manufacturer revision")
    names={str(k):v for k,v in pinout.get("pin_names",{}).items()}
    if set(names)!={str(x) for x in range(1,301)}:
        raise IntegratedGateError("missing official 300-pin map")
    for name,prior in old.items():
        if not name.startswith("/"):continue
        now=nets.get(name)
        if now is None or not prior.issubset(now):
            raise IntegratedGateError(f"lost original source-backed electrical net {name}")
        added={pin for ref,pin in now-prior if ref=="U3"}
        if any(ref!="U3" for ref,pin in now-prior):
            raise IntegratedGateError(f"unexplained component/net connection change {name}")
        if name[1:] in REQUIRED and name!="/GND":
            expect={str(n) for n in REQUIRED[name[1:]]}
        elif name=="/GND":
            expect={n for n,label in names.items() if label=="GND"}
        else:
            expect=set()
        if added!=expect:
            raise IntegratedGateError(f"{name} U3 pad assignments wrong; actual {added}")
    full={name:{str(n) for ref,n in members if ref=="U3"}
          for name,members in nets.items()}
    counted={n:label for n,label in names.items()
             if label in ("GND","VCC_SYSIN","USB_HOST_PWREN_H","USB20_HOST0_DP","USB20_HOST0_DM")}
    allassigned={n for name,pins in full.items() for n in pins if not name.startswith("unconnected-")}
    if allassigned!=set(counted):
        raise IntegratedGateError("unexpected or missing actively driven CM5 contacts")
    if "290" in allassigned:
        raise IntegratedGateError("manufacturer NC pin 290 connected")
    actual_grounds=full.get("/GND",set())
    if len(actual_grounds)!=76:
        raise IntegratedGateError("CM5 ground contact quantity mismatch")
    vendor_libs={x.get("lib"):x for x in newroot.findall("./libparts/libpart")}
    cm5=next((x for x in newroot.findall("./libparts/libpart") if x.get("part")=="Radxa_CM5"),None)
    if cm5 is None:
        raise IntegratedGateError("actual manufacturer CM5 symbol absent from native netlist")
    pin_names={p.get("num"):p.get("name") for p in cm5.findall("./pins/pin")}
    if pin_names!=names:
        raise IntegratedGateError("CM5 symbol pin functions differ from vendor workbook")
    comp={c.get("ref"):c.findtext("value","") for c in newroot.findall("./components/comp")}
    if "U3" not in comp or "CM5" not in comp["U3"]:
        raise IntegratedGateError("no actual CM5 placed component")
    if set(comp)!={*{c.get("ref") for c in ET.fromstring(original).findall("./components/comp")},"U3"}:
        raise IntegratedGateError("unexpected overall BOM modification")
    errors=dict(Counter(re.findall(r"^\[([^\]]+)\]:",erc.decode("utf-8"),re.MULTILINE)))
    if any(k in errors for k in ("multiple_net_names","pin_to_pin","endpoint_off_grid","unconnected_wire_endpoint")):
        raise IntegratedGateError(f"real ERC has topology/off-grid conflict {errors}")
    if errors.get("pin_not_connected",0)<100 or errors.get("power_pin_not_driven",0)<1:
        raise IntegratedGateError("incomplete board's ERC open issues hidden")
    if manifest.get("fabrication_authorized") is not False or manifest.get("routed_board") is not False:
        raise IntegratedGateError("unverified design falsely authorized")
    return {"schema":SCHEMA,"cm5_manufacturer_rev":"V2.21",
            "real_cm5_symbol_pin_count":len(pin_names),
            "physical_vcc_sysin_pins":sorted(map(int,full["/VCC_SYSIN"])),
            "physical_ground_pins":len(actual_grounds),
            "physical_usb_power_enable_pins":sorted(map(int,full["/USB_HOST_PWREN_H"])),
            "physical_usb_dp_pins":sorted(map(int,full["/USB20_HOST0_DP"])),
            "physical_usb_dm_pins":sorted(map(int,full["/USB20_HOST0_DM"])),
            "pin290_held_nc":True,
            "upstream_power_usb_circuit_unchanged":True,
            "erc_open_findings":errors,
            "erc_clean":False,
            "rated_mating_connector_assessed":False,
            "physical_power_test":False,
            "high_speed_routing_test":False,
            "fabrication_authorized":False,
            "next_gate":"Review GPIO/boot/reset, USB ESD and current budget, module revision and 300-pin physical footprint. Then design routed PCB and run ERC/DRC/SI and measured boot."
    }

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    for x in ("--integrated","--reference","--pinout","--erc","--manifest","--output"):
        p.add_argument(x,required=True,type=Path)
    a=p.parse_args()
    out=assess(a.integrated.read_bytes(),a.reference.read_bytes(),
               json.loads(a.pinout.read_text()),a.erc.read_bytes(),
               json.loads(a.manifest.read_text()))
    a.output.write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out,indent=2))
