"""Slicer trials for actual mating-hinge components, not fake material proxies.

Slice selected and backup reference hinge *separately* under two
uncalibrated profiles. No source G-code is released to a printer.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from hardware_splicer.functional_hinge_audit import audit
from hardware_splicer.function_print_slicer import read_statistics
from hardware_splicer.function_print_geometry import canonical,file_sha

HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--slicer",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--record",type=Path,default=HERE/"native_fdm_results.json")
    a=p.parse_args()
    if a.out.exists() or a.record.exists():
        p.error("refusing overwrite of source-frozen native slicer experiment")
    spec=json.loads((HERE/"reference_spec.json").read_text())
    profile=json.loads((HERE/"fdm_profile.json").read_text())
    if (profile["schema"]!="hs.unverified_hinge_fdm_v1"
        or profile["project_id"]!=spec["project_id"]
        or any(profile["authority"].values())
        or profile["materials"]!={"filament":"illustrative generic PLA",
          "density_g_cm3":1.24,"nozzle_mm":.4,"filament_mm":1.75,
          "infill_percent":20,"infill_pattern":"gyroid","perimeters":3,"supports":False}
        or profile["profiles"]!=[{"id":"std_020","layer_mm":.2},{"id":"draft_028","layer_mm":.28}]):
        raise ValueError("unqualified or changed FDM source profile")
    native=audit(spec,HERE/"generated")
    if native["source_ranked_winner"]!="balanced_60":
        raise ValueError("slicer run cannot silently choose a different CAD source")
    if not a.slicer.is_file():
        raise ValueError("native PrusaSlicer executable missing")
    help=subprocess.run([str(a.slicer),"--help"],capture_output=True,text=True,timeout=30,check=True).stdout.splitlines()[0]
    if "PrusaSlicer-2.9.2" not in help:
        raise ValueError("native slicer version changed")
    with open(a.slicer,"rb") as f:
        slicer_sha=hashlib.file_digest(f,"sha256").hexdigest()
    a.out.mkdir(parents=True)
    trial=[]
    evaluation=json.loads((HERE/"generated/HINGE_EVALUATION.json").read_text())
    for layer in profile["profiles"]:
        for design in ("balanced_60","reinforced_64"):
            ref=next(x for x in evaluation["candidates"] if x["id"]==design)
            if not ref["nominal_mechanism_feasible"]:
                raise ValueError("cannot slice physically ineligible design as a winner")
            for part in ("lower_leaf","upper_leaf"):
                stl=HERE/"generated/candidates"/design/(part+".stl")
                if file_sha(stl)!=ref["printed_files"][part]["stl_sha256"]:
                    raise ValueError("not source-authorized native part")
                gcode=a.out/(layer["id"]+"__"+design+"__"+part+".gcode")
                cmd=[str(a.slicer),"--export-gcode",
                  "--layer-height",str(layer["layer_mm"]),
                  "--first-layer-height",str(layer["layer_mm"]),
                  "--nozzle-diameter","0.4","--filament-diameter","1.75",
                  "--filament-density","1.24",
                  "--perimeters","3","--fill-density","20%","--fill-pattern","gyroid",
                  "--no-support-material","--skirts","0","--brim-width","0",
                  "--temperature","205","--first-layer-temperature","210",
                  "--bed-temperature","60","--first-layer-bed-temperature","60",
                  "--bed-shape","0x0,220x0,220x220,0x220",
                  "--gcode-flavor","reprap","--output",str(gcode),str(stl)]
                result=subprocess.run(cmd,capture_output=True,text=True,timeout=240)
                row={"layer_profile":layer["id"],"design":design,"printed_part":part,
                     "source_STL_sha256":file_sha(stl),
                     "slicer_exit_code":result.returncode,
                     "slicer_log_tail":(result.stdout+"\n"+result.stderr)[-400:],
                     "gcode_authorized_for_hardware":False}
                if result.returncode!=0 or not gcode.exists():
                    row["status"]="failed"
                    trial.append(row)
                    continue
                out=gcode.read_text(encoding="utf-8",errors="replace")
                row.update({"status":"sliced",
                    "native_slicer_report":read_statistics(out,layer={
                        "layer_height_mm":layer["layer_mm"],
                        "first_layer_height_mm":layer["layer_mm"]}),
                    "gcode_sha256":file_sha(gcode),
                    "gcode_bytes":gcode.stat().st_size})
                trial.append(row)
                print("SLICED",layer["id"],design,part,
                    row["native_slicer_report"]["filament_mass_g"],"g",flush=True)
    summary=[]
    for layer in profile["profiles"]:
        for design in ("balanced_60","reinforced_64"):
            entries=[x for x in trial if x["layer_profile"]==layer["id"] and x["design"]==design]
            if len(entries)!=2 or any(x.get("status")!="sliced" for x in entries):
                continue
            summary.append({
               "profile":layer["id"],"design":design,
               "slicer_estimated_two_part_filament_g":round(sum(
                   x["native_slicer_report"]["filament_mass_g"] for x in entries),3),
               "slicer_estimated_two_print_jobs_seconds":sum(
                   x["native_slicer_report"]["estimated_time_s"] for x in entries),
               "metal_pin_not_in_slicer_mass":True,
               "horizontal_hinge_bore_overhang_physically_qualified":False,
            })
    verdict={
        "schema":"hs.cyberdeck_hinge_actual_slicer_trial.v1",
        "source_spec_sha256":hashlib.sha256(canonical(spec)).hexdigest(),
        "source_profile_sha256":hashlib.sha256(canonical(profile)).hexdigest(),
        "original_source_CAD_audit":native,
        "slicer_version":help,"native_slicer_executable_sha256":slicer_sha,
        "real_native_slicer_job_count":len(trial),
        "all_model_slices_succeeded":len(trial)==8 and all(x["status"]=="sliced" for x in trial),
        "source_jobs":trial,"summaries":summary,
        "no_physical_printer_or_hardware_calibration":True,
        "gcode_file_bytes_not_committed":True,
        "no_routed_cable_or_shaft_retention_test":True,
        "fabrication_released":False,
    }
    a.record.write_bytes(canonical(verdict))
    print(json.dumps({"summary":summary,"success":verdict["all_model_slices_succeeded"]},indent=2))
    if not verdict["all_model_slices_succeeded"]:
        raise SystemExit("Native slicer failed an attempted hinge candidate; results frozen")
if __name__=="__main__":main()
