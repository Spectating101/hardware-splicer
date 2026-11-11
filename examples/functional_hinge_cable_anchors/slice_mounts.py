"""Real PrusaSlicer CLI check for four new round-wire mount printable pieces.

Retained G-code is not a released printer program; the generic profile
doesn't qualify mechanically useful cable strain relief or print adhesion.
"""
from __future__ import annotations
import argparse,hashlib,json,subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
INPUT=HERE/"generated"
CASES=["lower_leaf_integral_saddle","lower_removable_saddle_cap",
       "upper_leaf_integral_saddle","upper_removable_saddle_cap"]

def run_native_slicing(executable:Path,out:Path)->dict:
    if out.exists():raise ValueError("never overwrite prior toolpath experiment")
    p=json.loads((INPUT/"ANCHORED_CABLE_TRIAL.json").read_text())
    out.mkdir(parents=True)
    cmd_version=subprocess.run([str(executable),"--help"],capture_output=True,text=True,check=True,timeout=35).stdout.splitlines()[0]
    if "2.9.2" not in cmd_version:
        raise ValueError("native source requires PrusaSlicer 2.9.2")
    from hardware_splicer.function_print_slicer import read_statistics
    from hardware_splicer.function_print_geometry import file_sha
    outputs=[]
    for name in CASES:
        source=INPUT/(name+".stl")
        if file_sha(source)!=p["native_printed_mount_parts"][name]["stl_sha256"]:
            raise ValueError("native printed source STL no longer matches hash")
        gcode=out/(name+".gcode")
        cmd=[str(executable),"--export-gcode",
             "--layer-height","0.2","--first-layer-height","0.2",
             "--nozzle-diameter","0.4","--filament-diameter","1.75",
             "--filament-density","1.24",
             "--perimeters","3","--fill-density","20%","--fill-pattern","gyroid",
             "--no-support-material","--skirts","0","--brim-width","0",
             "--temperature","205","--first-layer-temperature","210",
             "--bed-temperature","60","--first-layer-bed-temperature","60",
             "--bed-shape","0x0,220x0,220x220,0x220","--gcode-flavor","reprap",
             "--output",str(gcode),str(source)]
        run=subprocess.run(cmd,capture_output=True,text=True,timeout=160)
        if run.returncode!=0 or not gcode.is_file():
            raise ValueError("native slicer failed "+name+": "+(run.stdout+run.stderr)[-300:])
        stats=read_statistics(gcode.read_text(encoding="utf-8",errors="replace"),
                              layer={"layer_height_mm":.2,"first_layer_height_mm":.2})
        outputs.append({
            "printed_part":name,
            "source_STL_sha256":file_sha(source),
            "generated_unreleased_Gcode_sha256":file_sha(gcode),
            "slicer_filament_g":stats["filament_mass_g"],
            "slicer_estimated_print_seconds":stats["estimated_time_s"],
            "slicer_layer_markers":stats["layer_markers"],
            "slicer_toolpath_lines":stats["gcode_lines"],
            "profile":"generic PLA, 0.4mm nozzle, 0.2mm layer, 20% gyroid, 3 walls, zero supports; uncalibrated",
            "safe_to_print_without_calibration":False,
        })
    return {
        "schema":"hs.cyberdeck_mount_4_prusaslicer_estimates.v1",
        "source_geometry_spec_sha256":p["source_spec_sha256"],
        "slicer_version":cmd_version,
        "actual_native_gcode_runs":4,
        "run_results":outputs,
        "all_source_geometry_files_verified":True,
        "gcode_released_for_printer":False,
        "round_wire_physical_strain_relief_qualified":False,
        "no_real_m2_hardware_or_display_electrical_assembly":True,
    }

def audit_source_only(data:dict)->dict:
    original=json.loads((INPUT/"ANCHORED_CABLE_TRIAL.json").read_text())
    from hardware_splicer.function_print_geometry import file_sha
    if data["schema"]!="hs.cyberdeck_mount_4_prusaslicer_estimates.v1" or data["actual_native_gcode_runs"]!=4:
        raise ValueError("original native PrusaSlicer source receipts absent")
    if data["source_geometry_spec_sha256"]!=original["source_spec_sha256"]:
        raise ValueError("slicing data not linked to original source")
    if len(data["run_results"])!=4 or [x["printed_part"] for x in data["run_results"]]!=CASES:
        raise ValueError("native slicing sample count changed")
    for entry in data["run_results"]:
        if (entry["source_STL_sha256"]!=file_sha(INPUT/(entry["printed_part"]+".stl"))
            or entry["generated_unreleased_Gcode_sha256"] is None
            or len(entry["generated_unreleased_Gcode_sha256"])!=64
            or entry["slicer_filament_g"]<=0
            or entry["slicer_estimated_print_seconds"]<=0
            or entry["safe_to_print_without_calibration"] is not False):
            raise ValueError("G-code receipt hash or fabrication authority altered")
    if data["gcode_released_for_printer"] is not False:
        raise ValueError("unqualified machine toolpaths cannot be released")
    return {"source_linked_slicer_runs":4,"unverified_printer_release":False}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--slicer",type=Path)
    ap.add_argument("--out",type=Path)
    ap.add_argument("--receipt",type=Path,default=INPUT/"NATIVE_FDM_SLICER.json")
    ap.add_argument("--audit-only",action="store_true")
    args=ap.parse_args()
    if args.audit_only:
        info=audit_source_only(json.loads(args.receipt.read_text()))
    else:
        if not args.slicer or not args.out:ap.error("--slicer and --out required")
        data=run_native_slicing(args.slicer,args.out)
        audit_source_only(data)
        if args.receipt.exists():raise SystemExit("refusing to overwrite original slicer summary")
        args.receipt.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
        info={k:v for k,v in data.items() if k!="run_results"}
        info["results"]=[{"part":r["printed_part"],"mass_g":r["slicer_filament_g"],
                         "time_s":r["slicer_estimated_print_seconds"]} for r in data["run_results"]]
    print(json.dumps(info,indent=2))
if __name__=="__main__":main()
