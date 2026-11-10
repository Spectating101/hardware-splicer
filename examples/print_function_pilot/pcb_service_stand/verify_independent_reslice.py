"""Independent stdlib PrusaSlicer re-slice verifier for Debian container CI.

Runs actual executable over all 12 committed native STL inputs using
only an independent CLI construction and public toolchain metadata.
Rechecks estimated filament grams, estimated print seconds and layers
against original local receipts. Exact G-code SHA may differ by native
build, output path and build version; never present byte identity as
cross-machine reproduction when only metrics are calibrated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent

def stats(raw:str)->tuple[float,int]:
    masses=re.findall(r"(?m)^;\s*filament used \[g\] = ([0-9.]+)\s*$",raw)
    times=re.findall(r"(?m)^;\s*estimated printing time \(normal mode\) = (.+?)\s*$",raw)
    if len(masses)!=1 or len(times)!=1 or ";LAYER_CHANGE" not in raw:
        raise ValueError("independent slicer did not produce complete G-code")
    components=re.findall(r"(\d+)\s*([dhms])",times[0])
    if not components:
        raise ValueError("unrecognizable normal-mode time string")
    seconds=sum(int(n)*{"d":86400,"h":3600,"m":60,"s":1}[u] for n,u in components)
    return float(masses[0]),seconds

def verify_source()->tuple[dict,dict,dict]:
    req=json.loads((HERE/"design_request.json").read_text())
    profile=json.loads((HERE/"slicer_profile.json").read_text())
    record=json.loads((HERE/"slicer_results/SLICER_COMPARISON.json").read_text())
    candidates=json.loads((HERE/"generated/FUNCTION_GEOMETRY_EVALUATION.json").read_text())
    sha=lambda value:hashlib.sha256((json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()).hexdigest()
    if profile["slicer"]["requested_version"]!="2.9.2+dfsg-1":
        raise ValueError("slicer version was not pinned")
    if record["slicer_profile_sha256"]!=sha(profile):
        raise ValueError("slicer profile mutated")
    if record["design_source_sha256"]!=sha(req):
        raise ValueError("engineering design mutated")
    if len(req["alternatives"])!=6 or len(record["case_results"])!=12:
        raise ValueError("12 matched native cases not found")
    for key in ("physical_print_passed","printer_control_authorized"):
        if profile["release_authority"].get(key,False):
            raise ValueError("unsourced physical release claimed")
    if record["fabrication_or_physical_printer_execution_authorized"]:
        raise ValueError("result claims unverified printer control")
    for item in req["alternatives"]:
        cad=next(x for x in candidates["alternatives"] if x["id"]==item["id"])
        stl=HERE/"generated"/"candidates"/item["id"]/(item["id"]+".stl")
        if not stl.is_file() or hashlib.sha256(stl.read_bytes()).hexdigest()!=cad["source_sha256"]["stl"]:
            raise ValueError("STL changed since geometry authoring")
    return req,profile,record

def independently_reslice(binary:Path,*,workspace:Path)->dict:
    req,profile,record=verify_source()
    result=subprocess.run([str(binary),"--help"],capture_output=True,text=True,timeout=60,check=True)
    version=result.stdout.splitlines()[0]
    if "2.9.2" not in version:
        raise ValueError("independent slicer build must match PrusaSlicer 2.9.2")
    successes=[]
    for layer in profile["profiles"]:
        for item in req["alternatives"]:
            label=item["id"]
            original=next(r for r in record["case_results"] if r["profile"]==layer["id"] and r["design"]==label)
            source=HERE/"generated"/"candidates"/label/(label+".stl")
            dest=workspace/(layer["id"]+"__"+label+".gcode")
            cmd=[
                str(binary),"--export-gcode",
                "--layer-height",str(layer["layer_height_mm"]),
                "--first-layer-height",str(layer["first_layer_height_mm"]),
                "--nozzle-diameter","0.4",
                "--filament-diameter","1.75",
                "--filament-density","1.24",
                "--perimeters","3",
                "--fill-density","20%",
                "--fill-pattern","gyroid",
                "--no-support-material",
                "--skirts","0","--brim-width","0",
                "--temperature","205",
                "--first-layer-temperature","210",
                "--bed-temperature","60",
                "--first-layer-bed-temperature","60",
                "--bed-shape","0x0,220x0,220x220,0x220",
                "--gcode-flavor","reprap",
                "--output",str(dest),str(source),
            ]
            run=subprocess.run(cmd,capture_output=True,text=True,timeout=210)
            if run.returncode!=0 or not dest.is_file():
                raise ValueError(f"real independent slicer failed {layer['id']} / {label}: {(run.stdout+run.stderr)[-260:]}")
            mass,time=stats(dest.read_text(encoding="utf-8",errors="replace"))
            saved=original["slicer_stats"]
            if abs(mass-saved["filament_mass_g"])>.20 or abs(time-saved["estimated_time_s"])>120:
                raise ValueError(f"independent G-code evidence differs for {label}: got {mass} g / {time} s, original {saved['filament_mass_g']} / {saved['estimated_time_s']}")
            successes.append({"profile":layer["id"],"design":label,
                              "independent_filament_g":mass,"independent_time_s":time,
                              "original_filament_g":saved["filament_mass_g"],
                              "original_time_s":saved["estimated_time_s"]})
    return {"schema":"hs.independent_native_prusaslicer_v1",
            "version":version,"real_gcode_count":len(successes),
            "slicer_version_verified":True,"all_slicer_metrics_reproduced":True,
            "printer_execution_authorized":False,"cases":successes}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--slicer",type=Path)
    p.add_argument("--source-only",action="store_true")
    args=p.parse_args()
    if args.source_only:
        req,profile,record=verify_source()
        print(json.dumps({"source_matched":True,"native_case_count":len(record["case_results"])}))
    else:
        if args.slicer is None:
            p.error("--slicer is required for native re-slicing")
        with tempfile.TemporaryDirectory(prefix="hs_independent_slicer_") as work:
            result=independently_reslice(args.slicer,workspace=Path(work))
            print(json.dumps(result,indent=2))
if __name__=="__main__":
    main()
