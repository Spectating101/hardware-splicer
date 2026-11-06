"""Check KiCad-exported CM5 bring-up schematic nets and outstanding ERC gates.

All network identities must be sourced from a real KiCad native netlist, not
a home-grown assumption about label adjacency or a custom ERC exception.
An intentional, safety-critical NOT_FOR_FAB contract is part of this output.
"""
from __future__ import annotations
from collections import Counter
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

SCHEMA="hs.cm5_native_connected_bench_gate.v1"
EXPECTED={
    "/VCC_SYSIN": {("J1","1"),("C1","1"),("C2","1"),
                   *(( "U1",str(n)) for n in (77,79,81,83,85,87))},
    "/GND": {("J1","2"),("J2","3"),("J3","3"),("C1","2"),("C2","2")},
    "/USB20_HOST0_DP":{("U1","263"),("J2","1")},
    "/USB20_HOST0_DM":{("U1","265"),("J2","2")},
    "/UART2_TX_M0":{("U1","55"),("J3","1")},
    "/UART2_RX_M0":{("U1","51"),("J3","2")},
}
EXPECTED_GROUND_PINS=76


class BenchSchematicError(ValueError):
    """Incomplete, incorrectly mapped, or falsely released KiCad evidence."""


def validate(netlist: bytes, erc: bytes) -> dict:
    try: root=ET.fromstring(netlist)
    except ET.ParseError as exc: raise BenchSchematicError("KiCad netlist invalid XML") from exc
    if root.tag!="export":
        raise BenchSchematicError("not a KiCad netlist export")
    nets={}
    for net in root.findall(".//nets/net"):
        name=net.get("name")
        if not name or name in nets: raise BenchSchematicError("empty or duplicate KiCad net")
        nodes={(node.get("ref"),node.get("pin")) for node in net.findall("node")}
        nets[name]=nodes
    if not all(name in nets for name in EXPECTED):
        raise BenchSchematicError("required source nets are absent")
    for name, required in EXPECTED.items():
        if name=="/GND":
            if not required.issubset(nets[name]):
                raise BenchSchematicError("GND nodes mismatch")
            ground={pin for ref,pin in nets[name] if ref=="U1"}
            if len(ground)!=EXPECTED_GROUND_PINS:
                raise BenchSchematicError("not all CM5 ground contacts tied to GND")
        elif nets[name]!=required:
            raise BenchSchematicError(f"{name}: wrong connected pin mapping: {nets[name]}")
    # This catches unintentional labels or physical shorts that tied a
    # 4V supply to ground, which happened during initial fixture drafting.
    for name,nodes in nets.items():
        if name not in ("/GND","/VCC_SYSIN"):
            if {("J1","1"),("J1","2")} & nodes:
                raise BenchSchematicError("power connector pins shorted or misplaced")
    if nets["/GND"] & nets["/VCC_SYSIN"]:
        raise BenchSchematicError("supply and GND nets overlap")
    conflicts={}
    allnodes={}
    for name,nodes in nets.items():
        for key in nodes:
            if key in allnodes:conflicts[key]=(name,allnodes[key])
            allnodes[key]=name
    if conflicts:
        raise BenchSchematicError("physical pin present on multiple different nets")
    pin290_net=allnodes.get(("U1","290"))
    if pin290_net and not pin290_net.startswith("unconnected-"):
        raise BenchSchematicError("manufacturer V2.21 NC pin 290 illegally routed")
    values={c.get("ref"):c.findtext("value") for c in root.findall(".//components/comp")}
    for ref in ("U1","J1","J2","J3","C1","C2"):
        if ref not in values:raise BenchSchematicError(f"missing design part {ref}")
    if not values["J2"].startswith("USB2_HOST0_SIGNAL_ONLY_NO_VBUS"):
        raise BenchSchematicError("USB breakout must explicitly have no VBUS")
    if "UNQUALIFIED" not in values["C1"] or "UNQUALIFIED" not in values["C2"]:
        raise BenchSchematicError("unqualified capacitors cannot masquerade as approved BOM")
    if "REGULATED_4V_3A" not in values["J1"]:
        raise BenchSchematicError("CM5 requires explicit external current-limited regulator")
    erc_text=erc.decode("utf-8")
    counts=dict(Counter(re.findall(r"^\[([^\]]+)\]:",erc_text,re.MULTILINE)))
    if counts.get("pin_not_connected",0)<50:
        raise BenchSchematicError("incomplete schematic cannot claim complete pin connectivity")
    if counts.get("pin_not_driven",0)<1 or counts.get("power_pin_not_driven",0)<1:
        raise BenchSchematicError("incomplete power/logic qualification somehow removed")
    if counts.get("multiple_net_names",0)>0:
        raise BenchSchematicError("ERC still finds conflicting net labels")
    if counts.get("endpoint_off_grid",0)>0:
        raise BenchSchematicError("off-grid fixture should be repaired before output")
    return {
        "schema":SCHEMA,
        "source":"native_kicad_cli_schematic_export_and_erc",
        "required_net_labels":sorted(EXPECTED),
        "verified_4v_input_contacts":[77,79,81,83,85,87],
        "verified_ground_contacts":EXPECTED_GROUND_PINS,
        "usb2_host0_data_pins":[263,265],
        "uart2_pins":[51,55],
        "no_4v_to_ground_short":True,
        "pin290_unconnected":True,
        "power_external_regulated_4v_3a_only":True,
        "usb_vbus_not_present":True,
        "erc_open_findings":counts,
        "erc_clean":False,
        "standalone_linux_boot_tested":False,
        "physical_assembly_tested":False,
        "release_authorized":False,
        "safe_to_fabricate":False,
        "next_gate":"Resolve power and USB VBUS/ESD, qualify UART levels, review all unused pins/electrical types and revision, then rerun full schematic ERC and electrical review."
    }


if __name__=="__main__":
    import argparse
    a=argparse.ArgumentParser()
    a.add_argument("--netlist",required=True,type=Path)
    a.add_argument("--erc",required=True,type=Path)
    a.add_argument("--output",required=True,type=Path)
    opts=a.parse_args()
    r=validate(opts.netlist.read_bytes(),opts.erc.read_bytes())
    opts.output.parent.mkdir(parents=True,exist_ok=True)
    opts.output.write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps(r,indent=2))
