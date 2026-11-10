"""Independent stdlib runner re-slices actual native hinge STL components.

Does not import HS's primary slicer or ranking implementation. Validates
original source SHA and machine-specific G-code claims against 8 newly
produced toolpaths, then discards new G-code rather than releasing it.
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

def sha(data):
    return hashlib.sha256((json.dumps(data,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()).hexdigest()

def inspect():
    spec=json.loads((HERE/"reference_spec.json").read_text())
    profile=json.loads((HERE/"fdm_profile.json").read_text())
    trial=json.loads((HERE/"native_fdm_results.json").read_text())
    model=json.loads((HERE/"generated/HINGE_EVALUATION.json").read_text())
    if trial["schema"]!="hs.cyberdeck_hinge_actual_slicer_trial.v1" or not trial["all_model_slices_succeeded"]:
        raise ValueError("not a successful real source slicer trial")
    if trial["source_spec_sha256"]!=sha(spec) or trial["source_profile_sha256"]!=sha(profile):
        raise ValueError("source hinge design or printer profile was changed")
    if trial["original_source_CAD_audit"]["source_ranked_winner"]!=model["selected"] or model["selected"]!="balanced_60":
        raise ValueError("source-approved hinge selection changed")
    if trial["fabrication_released"] or trial["no_physical_printer_or_hardware_calibration"] is not True:
        raise ValueError("unverified machine code falsely authorized")
    if len(trial["source_jobs"])!=8:
        raise ValueError("not all eight printable hinge jobs recorded")
    expected=[(profile_row["id"],design,part)
              for profile_row in profile["profiles"]
              for design in ("balanced_60","reinforced_64")
              for part in ("lower_leaf","upper_leaf")]
    got=[(r["layer_profile"],r["design"],r["printed_part"]) for r in trial["source_jobs"]]
    if got!=expected:
        raise ValueError("source trial parts reordered or excluded")
    for job in trial["source_jobs"]:
        cad=next(x for x in model["candidates"] if x["id"]==job["design"])
        p=HERE/"generated"/"candidates"/job["design"]/(job["printed_part"]+".stl")
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        if digest!=job["source_STL_sha256"] or digest!=cad["printed_files"][job["printed_part"]]["stl_sha256"]:
            raise ValueError("actual printed source STL has changed")
        if job["status"]!="sliced" or job["slicer_exit_code"]!=0 or job["gcode_authorized_for_hardware"]:
            raise ValueError("invalid or uncontrolled slicing output")
    return spec,profile,trial

def parse_gcode(raw):
    weight=re.findall(r"(?m)^;\s*filament used \[g\] = ([0-9.]+)\s*$",raw)
    time=re.findall(r"(?m)^;\s*estimated printing time \(normal mode\) = ([^\r\n]+)",raw)
    if len(weight)!=1 or len(time)!=1 or raw.count(";LAYER_CHANGE")<30:
        raise ValueError("independent PrusaSlicer toolpath metadata missing")
    components=re.findall(r"(\d+)\s*([dhms])",time[0])
    if not components:
        raise ValueError("malformed independent elapsed time estimate")
    return float(weight[0]),sum(int(v)*{"d":86400,"h":3600,"m":60,"s":1}[u] for v,u in components)

def run(prusa:Path):
    spec,profile,source=inspect()
    result=subprocess.run([str(prusa),"--help"],capture_output=True,text=True,timeout=35,check=True)
    version=result.stdout.splitlines()[0]
    if "PrusaSlicer-2.9.2" not in version:
        raise ValueError("wrong independent slicer version")
    with tempfile.TemporaryDirectory(prefix="hs_fold_hinge_prusa_") as tmp:
        root=Path(tmp)
        results=[]
        for job in source["source_jobs"]:
            layer=next(x["layer_mm"] for x in profile["profiles"] if x["id"]==job["layer_profile"])
            orig=HERE/"generated"/"candidates"/job["design"]/(job["printed_part"]+".stl")
            dest=root/(job["layer_profile"]+"__"+job["design"]+"__"+job["printed_part"]+".gcode")
            args=[str(prusa),"--export-gcode","--layer-height",str(layer),
                "--first-layer-height",str(layer),"--nozzle-diameter","0.4",
                "--filament-diameter","1.75","--filament-density","1.24",
                "--perimeters","3","--fill-density","20%","--fill-pattern","gyroid",
                "--no-support-material","--skirts","0","--brim-width","0",
                "--temperature","205","--first-layer-temperature","210",
                "--bed-temperature","60","--first-layer-bed-temperature","60",
                "--bed-shape","0x0,220x0,220x220,0x220",
                "--gcode-flavor","reprap","--output",str(dest),str(orig)]
            p=subprocess.run(args,capture_output=True,text=True,timeout=180)
            if p.returncode!=0 or not dest.exists():
                raise ValueError("independent slicer rejected "+
                                 job["design"]+" "+job["printed_part"]+": "+(p.stderr+p.stdout)[-300:])
            weight,time=parse_gcode(dest.read_text(encoding="utf-8",errors="replace"))
            orig_est=job["native_slicer_report"]
            if (abs(weight-orig_est["filament_mass_g"])>.20
                or abs(time-orig_est["estimated_time_s"])>120):
                raise ValueError("independent material/time estimate differs from sealed primary run")
            results.append({"design":job["design"],"part":job["printed_part"],
                            "layer":job["layer_profile"],"reproduced_filament_g":weight,
                            "reproduced_time_s":time})
    return {
      "schema":"hs.cyberdeck_hinge_independent_slicer.v1",
      "actual_native_gcodes_regenerated":len(results),
      "same_source_STL_SHA256_verified":True,
      "filament_mass_and_time_reproduced":True,
      "physical_printer_executed":False,
      "results":results,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--slicer",type=Path)
    p.add_argument("--source-only",action="store_true")
    args=p.parse_args()
    if args.source_only:
        _,_,source=inspect()
        print(json.dumps({"source_verified":True,"slicer_runs":len(source["source_jobs"])}))
    else:
        if args.slicer is None:
            p.error("--slicer required for independent native replication")
        print(json.dumps(run(args.slicer),indent=2))
if __name__=="__main__":main()
