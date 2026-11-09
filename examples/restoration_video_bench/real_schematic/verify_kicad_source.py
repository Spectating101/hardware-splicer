"""Re-export genuine Gekkio KiCad designs and match the committed snapshot.

Never rewrites the pinned source or the reference snapshot. Prevents
a later synthetic fixture from silently replacing real circuit topology.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from hardware_splicer.restoration_schematic_grounding import (
    DATA, SCHEMATIC_MAIN, SCHEMATIC_POWER, load_reference, sha
)

def parse_one(filepath:Path)->dict:
    root=ET.parse(filepath).getroot()
    if root.tag!="export":
        raise ValueError("not a KiCad exported XML netlist")
    comps=sorted([
        {
            "ref":x.attrib["ref"],
            "value":x.findtext("value","").strip(),
            "lib":x.find("libsource").attrib if x.find("libsource") is not None else {},
        } for x in root.findall("./components/comp")
    ],key=lambda e:e["ref"])
    nets=sorted([
        {
            "name":x.attrib["name"],
            "nodes":sorted([
                {"ref":y.attrib["ref"],"pin":y.attrib["pin"]}
                for y in x.findall("node")
            ],key=lambda e:(e["ref"],e["pin"]))
        } for x in root.findall("./nets/net")
    ],key=lambda e:e["name"])
    return {
        "components":comps,"nets":nets,
        "component_count":len(comps),"net_count":len(nets),
        "provenance_kind":"KiCad 9 kicadxml export from Gekkio pinned reverse-engineered schematic; not independently verified against device",
    }

def verify(source_checkout:Path)->dict:
    manifest,expected=load_reference(source_checkout=source_checkout)
    commit=subprocess.run(
        ["git","-C",str(source_checkout),"rev-parse","HEAD"],
        text=True,capture_output=True,timeout=15,check=True
    ).stdout.strip()
    if commit!=manifest["commit"]:
        raise ValueError("Gekkio checkout not pinned to declared commit")
    cli=subprocess.run(["kicad-cli","--version"],capture_output=True,
                       text=True,timeout=15,check=True).stdout.strip()
    if cli!=manifest["kicad_cli_version"]:
        raise ValueError("unexpected KiCad CLI version; output may differ")
    with tempfile.TemporaryDirectory(prefix="hs-real-schematic-") as tmp:
        boards={}
        for board,rel in (
            ("DMG-CPU-06",SCHEMATIC_MAIN),
            ("DC-CONV-DMG-AB",SCHEMATIC_POWER),
        ):
            target=Path(tmp)/(board+".xml")
            result=subprocess.run([
                "kicad-cli","sch","export","netlist","--format","kicadxml",
                "-o",str(target),str(source_checkout/rel),
            ],capture_output=True,text=True,timeout=90,check=False)
            if result.returncode:
                raise RuntimeError("KiCad source netlist export failed: "+result.stderr[:250])
            boards[board]=parse_one(target)
    if boards!=expected["reference_boards"]:
        raise ValueError("freshly re-exported reference nets do not match committed source snapshot")
    return {
        "source_commit":commit,
        "kicad_cli_version":cli,
        "source_license":manifest["license"],
        "snapshot_digest_verified":manifest["derived_snapshot_sha256"],
        "boards":{k:{"components":v["component_count"],"nets":v["net_count"]}
                  for k,v in boards.items()},
        "independent_target_measurements":False,
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-checkout",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(verify(args.source_checkout),indent=2))

if __name__=="__main__":main()
