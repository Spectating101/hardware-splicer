"""Fresh KiCad CLI re-export of a pinned C64 schematic source, no model.

The snapshot is only accepted when every selected original net name and
individual terminal matches the actual KiCad 9 XML output from exact
source file bytes. The CLI annotation warning is recorded, not hidden.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from hardware_splicer.repair_investigator import load_case, file_sha256

HERE=Path(__file__).resolve().parent
CASE=HERE/"c64_250407/case.json"

def verify(*,case:Path,caption_file:Path,checkout:Path)->dict:
    manifest,snap=load_case(case,captions_vtt=caption_file,schematic_checkout=checkout)
    version=subprocess.run(["kicad-cli","--version"],capture_output=True,text=True,
                           check=True,timeout=20).stdout.strip()
    if version!=snap["kicad_version"]:
        raise ValueError("source snapshot must be reverified for this KiCad version: "+version)
    with tempfile.TemporaryDirectory() as tmp:
        outfile=Path(tmp)/"source.xml"
        proc=subprocess.run([
            "kicad-cli","sch","export","netlist","--format","kicadxml",
            "-o",str(outfile),str(checkout/"250407_.kicad_sch")
        ],capture_output=True,text=True,timeout=120,check=False)
        if proc.returncode!=0:
            raise ValueError("original KiCad source failed fresh netlist export: "+proc.stderr[:400])
        # An annotation warning is not license to silently correct net pins.
        warning=("annotation errors" in (proc.stderr+"\n"+proc.stdout).lower())
        if not warning and snap.get("kicad_export_warning"):
            raise ValueError("upstream KiCad annotation-warning status changed")
        rt=ET.parse(outfile).getroot()
        comps=rt.findall("./components/comp")
        nets=rt.findall("./nets/net")
        if len(comps)!=snap["full_netlist_component_count"] or len(nets)!=snap["full_netlist_net_count"]:
            raise ValueError("fresh KiCad netlist sizes differ from source snapshot")
        actual={}
        for item in nets:
            actual[item.get("name")]=sorted([
                {"ref":x.get("ref"),"pin":x.get("pin")}
                for x in item.findall("node")
            ],key=lambda x:(x["ref"],x["pin"]))
        for row in snap["selected_nets"]:
            if actual.get(row["name"])!=row["pins"]:
                raise ValueError("fresh source KiCad pin connection is different from snapshot: "+row["name"])
        return {
            "schema":"hs.repair_investigator.kicad_source_reexport.v1",
            "upstream_commit":snap["source_commit"],
            "source_license":snap["source_license"],
            "kicad_cli_version":version,
            "selected_nets_exactly_verified":len(snap["selected_nets"]),
            "actual_selected_pin_instances":sum(len(n["pins"]) for n in snap["selected_nets"]),
            "full_original_components":len(comps),
            "full_original_nets":len(nets),
            "kicad_warning_annotation_errors":warning,
            "original_source_manifest_sha256":file_sha256(case),
            "public_board_revision_verified_on_target":False,
            "no_physical_measurements":True,
        }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--case",type=Path,default=CASE)
    p.add_argument("--captions-vtt",type=Path,required=True)
    p.add_argument("--schematic-checkout",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(verify(case=a.case,caption_file=a.captions_vtt,
                            checkout=a.schematic_checkout),indent=2))
if __name__=="__main__":main()
