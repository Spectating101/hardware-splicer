"""Independent netlist acceptance gate for Radxa CM5 V2.21 auxiliary 5V and keys.

Proves electrical net identity only. It does not endorse KiCad footprints,
thermal, input drop, ESD, SI, PCB, or manufacture.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET

SCHEMA = "hs.cm5_power_boot_gate.v1"
KEYS = (
    ("PWRON_L", 99, "R8", "SW1", "PWRON"),
    ("RESET_L", 92, "R9", "SW2", "RESET"),
    ("SARADC_VIN0_BOOT", 93, "R10", "SW3", "MASKROM"),
    ("SARADC_VIN1_KEY/RECOVERY", 226, "R11", "SW4", "RECOVERY"),
)


class BringupGateError(ValueError):
    pass


def _parse(raw: bytes):
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise BringupGateError("invalid native KiCad XML") from e
    if root.tag != "export":
        raise BringupGateError("not a native KiCad export")
    nets, index = {}, {}
    for item in root.findall("./nets/net"):
        name = item.get("name")
        if not name or name in nets:
            raise BringupGateError("duplicate/empty electrical net")
        nodes = {(node.get("ref"), node.get("pin")) for node in item.findall("node")}
        if len(nodes) != len(item.findall("node")):
            raise BringupGateError("duplicate physical contact within net")
        for node in nodes:
            if node in index:
                raise BringupGateError(f"physical node shorted across nets: {node}")
            index[node] = name
        nets[name] = nodes
    comps = {c.get("ref"):c.findtext("value","") for c in root.findall("./components/comp")}
    return root, nets, index, comps


def assess(candidate: bytes, upstream: bytes, pinout: dict,
           erc: bytes, baseline_erc: bytes, manifest: dict) -> dict:
    root, nets, index, parts = _parse(candidate)
    old_root, oldnets, oldindex, oldparts = _parse(upstream)
    if pinout.get("manufacturer_revision") != "V2.21":
        raise BringupGateError("unqualified module revision")
    names = {int(n):v for n,v in pinout.get("pin_names",{}).items()}
    if set(names) != set(range(1,301)) or names.get(106)!="5V_HDMI":
        raise BringupGateError("manufacturer V2.21 pin106 auxiliary 5V mismatch")
    if manifest.get("schema") != "hs.cm5_power_boot_bringup.v1":
        raise BringupGateError("unqualified bringup manifest")
    if manifest.get("manufacturer_revision") != "V2.21" or manifest.get("auxiliary_5v_pin") != 106:
        raise BringupGateError("invalid metadata revision/pin")
    for flag in (
        "gpio_vref_qualified","flash_voltage_qualified",
        "input_protection_present","usb_data_esd_present",
        "current_limit_measured","buck_droop_test_passed",
        "power_on_tested","full_erc_clean","pcb_routed",
        "fabrication_authorized"
    ):
        if manifest.get(flag) is not False:
            raise BringupGateError(f"unearned release qualification {flag}")
    oldconnected={node:name for node,name in oldindex.items() if not name.startswith("unconnected-")}
    for node, name in oldconnected.items():
        if index.get(node) != name:
            raise BringupGateError(f"original connected pad moved: {node} {name}")
    for name, prior in oldnets.items():
        if not name.startswith("unconnected-") and not prior.issubset(nets.get(name,set())):
            raise BringupGateError(f"upstream power/USB net changed: {name}")
    original = set(oldparts)
    expected_new = {"R7","R8","R9","R10","R11","SW1","SW2","SW3","SW4"}
    if set(parts)-original != expected_new or original-set(parts):
        raise BringupGateError("additional or missing components")
    if any(parts[r] != oldparts[r] for r in original):
        raise BringupGateError("original regulator/switch/symbol component modified")
    if "0R_" not in parts["R7"] or not all("100R_" in parts[f"R{n}"] for n in range(8,12)):
        raise BringupGateError("series resistor value changed")

    def net(name, expect):
        actual = nets.get("/"+name)
        if actual != expect:
            raise BringupGateError(f"{name} wrong pins: {actual}; expected {expect}")

    net("5V_HDMI",{("R7","2"),("U3","106")})
    baseline_5v = oldnets.get("/VCC5V0_SYS",set())
    if not {("J1","1"),("U1","1"),("U2","5")}.issubset(baseline_5v):
        raise BringupGateError("unqualified external 5V provenance")
    if nets.get("/VCC5V0_SYS") != baseline_5v | {("R7","1")}:
        raise BringupGateError("auxiliary HDMI rail not isolated by R7")
    for name,pin,r,sw,label in KEYS:
        if names.get(pin) != name:
            raise BringupGateError(f"manufacturer function {pin} changed")
        net(name,{("U3",str(pin)),(r,"1")})
        net(f"BTN_{label}_GND_ON_PRESS",{(r,"2"),(sw,"1")})
    if nets.get("/GND") != oldnets["/GND"] | {(f"SW{i}","2") for i in range(1,5)}:
        raise BringupGateError("push-button return is not the original GND")
    newly_assigned = {(r,p) for (r,p),name in index.items() if not name.startswith("unconnected-") and (r,p) not in oldconnected}
    allowed = {
        ("U3","106"),("R7","1"),("R7","2"),
        *(("U3",str(pin)) for _,pin,*_ in KEYS),
        *((r,str(i)) for _,_,r,_,_ in KEYS for i in (1,2)),
        *((s,str(i)) for _,_,_,s,_ in KEYS for i in (1,2)),
    }
    if newly_assigned != allowed:
        raise BringupGateError("unexpected/missing newly driven physical pads")
    if ("U3","290") in index and not index[("U3","290")].startswith("unconnected-"):
        raise BringupGateError("manufacturer NC290 connected")
    cm5 = next((l for l in root.findall("./libparts/libpart")
                if l.get("part")=="Radxa_CM5"), None)
    if cm5 is None or {int(p.get("num")):p.get("name") for p in cm5.findall("./pins/pin")} != names:
        raise BringupGateError("CM5 library symbol differs from official pinout")
    counts = dict(Counter(re.findall(r"^\[([^\]]+)\]:",erc.decode(),re.M)))
    previous = dict(Counter(re.findall(r"^\[([^\]]+)\]:",baseline_erc.decode(),re.M)))
    forbidden = {"multiple_net_names","pin_to_pin","endpoint_off_grid",
                 "unconnected_wire_endpoint","label_dangling"}
    if forbidden.intersection(counts):
        raise BringupGateError("ERC electrical conflict")
    if counts.get("pin_not_connected") != previous.get("pin_not_connected",0)-5:
        raise BringupGateError("unconnected pin delta hides errors")
    if counts.get("power_pin_not_driven",0) < 1:
        raise BringupGateError("incomplete power domains falsely green")
    if "SW_Push" not in root.findtext("./libparts/libpart[@part='SW_Push']/description","SW_Push") and not any(
        l.get("part")=="SW_Push" for l in root.findall("./libparts/libpart")
    ):
        raise BringupGateError("momentary switch symbol missing")
    return {
        "schema":SCHEMA,
        "manufacturer_revision":"V2.21",
        "five_volt_auxiliary_contact":106,
        "five_volt_link_ref":"R7",
        "five_volt_upstream_preserved":True,
        "four_keys_checked":{name:pin for name,pin,*_ in KEYS},
        "unchanged_original_connections":len(oldconnected),
        "newly_connected_contacts":len(newly_assigned),
        "erc_open_findings":counts,
        "previous_erc_open_findings":previous,
        "erc_clean":False,
        "rated_footprints":False,
        "input_protection":False,
        "usb_data_esd":False,
        "gpio_flash_power_domains_qualified":False,
        "regulator_load_test":False,
        "real_hardware_boot_test":False,
        "board_routed":False,
        "fabrication_authorized":False,
    }


if __name__=="__main__":
    import argparse
    a=argparse.ArgumentParser()
    for name in ("candidate","upstream","pinout","erc","baseline_erc","manifest","output"):
        a.add_argument("--"+name.replace("_","-"),type=Path,required=True)
    p=vars(a.parse_args())
    result=assess(p["candidate"].read_bytes(),p["upstream"].read_bytes(),
                  json.loads(p["pinout"].read_text()),p["erc"].read_bytes(),
                  p["baseline_erc"].read_bytes(),json.loads(p["manifest"].read_text()))
    p["output"].write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
