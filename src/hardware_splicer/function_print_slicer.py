"""Native PrusaSlicer benchmarking of existing HS STEP/STL CAD alternatives.

Run every source-verified candidate in the same uncalibrated fixed printer
profile. Compare actual slicer toolpaths and extrusion statistics, not the
surrogate BRep-volume proxy. Never authorize an actual printer to run G-code.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping

from .function_print_geometry import canonical, file_sha, validate_design, audit_bundle

SCHEMA="hs.fff_slicer_trial_profile.v1"
RESULT="hs.native_slicer_geometry_benchmark.v1"
STAT_RE={
    "filament_length_mm":re.compile(r"^;\s*filament used \[mm\] = ([0-9.]+)\s*$",re.M),
    "filament_volume_cm3":re.compile(r"^;\s*filament used \[cm3\] = ([0-9.]+)\s*$",re.M),
    "filament_mass_g":re.compile(r"^;\s*filament used \[g\] = ([0-9.]+)\s*$",re.M),
    "estimated_time":re.compile(r"^;\s*estimated printing time \(normal mode\) = ([^\r\n]+)",re.M),
}
PROFILE_EXPECTED={
    "support_material":"0","skirts":"0","brim_width":"0",
    "perimeters":"3","fill_density":"20%","fill_pattern":"gyroid",
    "nozzle_diameter":"0.4","filament_diameter":"1.75",
}

def digest_raw(path: Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _assert_valid_profile(profile:Mapping[str,Any],request:Mapping[str,Any])->None:
    if profile.get("schema")!=SCHEMA or profile.get("project_id")!=request["project_id"]:
        raise ValueError("printer source profile does not match mechanical function")
    if profile["slicer"]["name"]!="PrusaSlicer" or not profile["slicer"]["requested_version"].startswith("2.9.2"):
        raise ValueError("unknown slicer authoring contract")
    if profile["filament"]["qualified_for_ESD"] is not False:
        raise ValueError("unqualified FDM plastic may not be marked ESD safe")
    if profile["machine"]["machine_profile_physically_verified"] is not False:
        raise ValueError("machine profile claims unverified physical calibration")
    if any(profile["release_authority"].values()):
        raise ValueError("slicer experiment cannot confer printer release authority")
    opts=profile["fixed_options"]
    fixed={"perimeters":3,"fill_density_percent":20,"fill_pattern":"gyroid",
           "support_material":False,"skirts":0,"brim_width_mm":0,
           "temperature_c":205,"first_layer_temperature_c":210,
           "bed_temperature_c":60,"first_layer_bed_temperature_c":60,
           "gcode_flavor":"reprap"}
    if opts!=fixed or profile["machine"]["nozzle_diameter_mm"]!=.4 or profile["filament"]["diameter_mm"]!=1.75:
        raise ValueError("fixed slicer options no longer match precommitted baseline")
    if profile["filament"]["nominal_density_g_cm3"]!=1.24:
        raise ValueError("slicer nominal material density is not pinned")
    if profile["machine"]["nominal_bed_polygon_mm"]!=[[0,0],[220,0],[220,220],[0,220]]:
        raise ValueError("unknown print bed for this benchmark")
    if profile["profiles"]!=[
        {"id":"standard_020","layer_height_mm":.2,"first_layer_height_mm":.2},
        {"id":"draft_028","layer_height_mm":.28,"first_layer_height_mm":.28},
    ]:
        raise ValueError("preset slicing layer-height comparisons changed")

def _args(prusa:Path,stl:Path,gcode:Path,profile:Mapping[str,Any],layer:Mapping[str,Any])->list[str]:
    fixed=profile["fixed_options"]
    return [
        str(prusa),"--export-gcode",
        "--layer-height",str(layer["layer_height_mm"]),
        "--first-layer-height",str(layer["first_layer_height_mm"]),
        "--nozzle-diameter","0.4","--filament-diameter","1.75",
        "--filament-density","1.24","--perimeters",str(fixed["perimeters"]),
        "--fill-density","20%","--fill-pattern","gyroid",
        "--no-support-material","--skirts","0","--brim-width","0",
        "--temperature","205","--first-layer-temperature","210",
        "--bed-temperature","60","--first-layer-bed-temperature","60",
        "--bed-shape","0x0,220x0,220x220,0x220",
        "--gcode-flavor","reprap","--output",str(gcode),str(stl)
    ]

def read_statistics(raw:str,*,layer:Mapping[str,Any])->dict[str,Any]:
    stats={}
    for name,pattern in STAT_RE.items():
        matches=pattern.findall(raw)
        if len(matches)!=1:
            raise ValueError("G-code is missing unique slicer metadata "+name)
        stats[name]=str(matches[0]) if name=="estimated_time" else float(matches[0])
    if not 0<stats["filament_mass_g"]<1000 or not 0<stats["filament_length_mm"]<500000:
        raise ValueError("not a plausible positive toolpath result")
    if not stats["filament_volume_cm3"]>0:
        raise ValueError("empty G-code toolpath volume")
    if not math.isclose(stats["filament_mass_g"],stats["filament_volume_cm3"]*1.24,rel_tol=.015):
        raise ValueError("slicer reported filament weight inconsistent with source density")
    for label,expected in PROFILE_EXPECTED.items():
        p=re.compile(r"^;\s*"+re.escape(label)+r"\s*=\s*(.+)\s*$",re.M)
        matches=p.findall(raw)
        if len(matches)!=1 or matches[0].strip()!=expected:
            raise ValueError(f"G-code output profile discrepancy {label}: {matches[:2]}")
    for label,expected in (
        ("layer_height",layer["layer_height_mm"]),
        ("first_layer_height",layer["first_layer_height_mm"])
    ):
        matches=re.findall(r"^;\s*"+label+r"\s*=\s*([0-9.]+)\s*$",raw,re.M)
        if len(matches)!=1 or not math.isclose(float(matches[0]),expected,abs_tol=.0001):
            raise ValueError("G-code layer profile mismatch: "+label)
    if not (";LAYER_CHANGE" in raw or ";LAYER:" in raw):
        raise ValueError("toolpath does not have layer markers")
    # PrusaSlicer 2.9.x legitimately emits all extrusion and travel
    # movements as G1, without any G0 lines.
    if "\nG1 " not in raw:
        raise ValueError("toolpath missing normal movement commands")
    # Deterministic script extracts the slicer's time forecast but does not
    # treat it as physical elapsed manufacturing time.
    time=stats["estimated_time"]
    parts=re.findall(r"(\d+)\s*([dhms])",time)
    if not parts:
        raise ValueError("slicer estimated time text is not parseable")
    seconds=sum(int(n)*{"d":86400,"h":3600,"m":60,"s":1}[unit] for n,unit in parts)
    if seconds<=0:
        raise ValueError("nonpositive slicer time")
    stats["estimated_time_s"]=seconds
    stats["gcode_lines"]=raw.count("\n")+1
    stats["layer_markers"]=raw.count(";LAYER_CHANGE")
    return stats

def run_slicer_comparison(req:Mapping[str,Any],profile:Mapping[str,Any],
                          *,cad_dir:Path,bin_path:Path,out:Path)->dict[str,Any]:
    request=validate_design(req)
    _assert_valid_profile(profile,request)
    native_audit=audit_bundle(request,cad_dir)
    if native_audit["native_shape_count"]!=len(request["alternatives"]):
        raise ValueError("not all candidate solids have been independently confirmed")
    if out.exists():
        raise ValueError("no rerolls/overwrite: slicer experiment already exists")
    if not bin_path.is_file() or not bin_path.stat().st_size>0:
        raise ValueError("actual physical slicer binary not present")
    with open(bin_path,"rb") as src:
        binary_hash=hashlib.file_digest(src,"sha256").hexdigest()
    # Matching source distribution is separately declared; only this
    # actual executable identity is independently hash-verified.
    version=subprocess.run([str(bin_path),"--help"],capture_output=True,
                           text=True,timeout=35,check=True).stdout.splitlines()[0]
    if "2.9.2" not in version:
        raise ValueError("unsupported installed native slicer version")
    cad_report=json.loads((cad_dir/"FUNCTION_GEOMETRY_EVALUATION.json").read_text())
    out.mkdir(parents=True)
    cases=[]
    for layer in profile["profiles"]:
        for alt in request["alternatives"]:
            shape=next(x for x in cad_report["alternatives"] if x["id"]==alt["id"])
            source_stl=cad_dir/"candidates"/alt["id"]/(alt["id"]+".stl")
            if file_sha(source_stl)!=shape["source_sha256"]["stl"]:
                raise ValueError("native STL source changed after geometry audit")
            gcode=out/(layer["id"]+"__"+alt["id"]+".gcode")
            args=_args(bin_path,source_stl,gcode,profile,layer)
            run=subprocess.run(args,capture_output=True,text=True,timeout=210)
            row={"profile":layer["id"],"design":alt["id"],
                 "origin_stl_sha256":shape["source_sha256"]["stl"],
                 "slicer_command_args":[
                     ("<SLICER_BIN>" if item==str(bin_path) else
                      "<OUTPUT_GCODE>" if item==str(gcode) else
                      "<SOURCE_STL>" if item==str(source_stl) else item)
                     for item in args
                 ],
                 "slicer_exit_code":run.returncode,
                 "slicer_output_tail":(run.stdout+"\n"+run.stderr)[-450:],
                 "cad_numeric_feasible":shape["numeric_feasible"],
                 "gcode_released_for_physical_printer":False}
            if run.returncode!=0 or not gcode.is_file():
                row.update({"slice_status":"failed","slicer_output_sha256":None})
                cases.append(row)
                continue
            text=gcode.read_text(encoding="utf-8",errors="replace")
            row.update({"slice_status":"valid_gcode",
                        "slicer_output_sha256":file_sha(gcode),
                        "slicer_stats":read_statistics(text,layer=layer),
                        "gcode_bytes":gcode.stat().st_size})
            cases.append(row)
    if any(x["slice_status"]!="valid_gcode" for x in cases):
        # Record all attempted outputs. No reroll until a new experiment.
        success=False
    else:
        success=True
    candidates=[]
    for layer in profile["profiles"]:
        rows=[r for r in cases if r["profile"]==layer["id"] and r["slice_status"]=="valid_gcode"]
        feasible=[r for r in rows if r["cad_numeric_feasible"]]
        ordered=sorted(feasible,key=lambda r:(
            r["slicer_stats"]["filament_mass_g"],
            r["slicer_stats"]["estimated_time_s"],r["design"]
        ))
        baseline=next((r for r in rows if r["design"]=="solid_plate"),None)
        chosen=ordered[0] if ordered else None
        candidates.append({
            "profile":layer["id"],
            "cad_volume_selection":cad_report["selected"],
            "slicer_filament_selection":chosen["design"] if chosen else None,
            "slicer_selection_differs_from_CAD":bool(chosen and chosen["design"]!=cad_report["selected"]),
            "slicer_feasible_rank":[r["design"] for r in ordered],
            "baseline_plate_filament_g":baseline["slicer_stats"]["filament_mass_g"] if baseline else None,
            "selected_filament_g":chosen["slicer_stats"]["filament_mass_g"] if chosen else None,
            "relative_slicer_filament_reduction_pct":round(
                100*(1-chosen["slicer_stats"]["filament_mass_g"]/baseline["slicer_stats"]["filament_mass_g"]),1
            ) if baseline and chosen else None,
            "selected_estimated_print_time_s":chosen["slicer_stats"]["estimated_time_s"] if chosen else None,
        })
    report={
        "schema":RESULT,"project_id":request["project_id"],
        "design_source_sha256":hashlib.sha256(canonical(request)).hexdigest(),
        "slicer_profile_sha256":hashlib.sha256(canonical(profile)).hexdigest(),
        "native_CAD_audit":native_audit,
        "PrusaSlicer_executable_sha256":binary_hash,
        "PrusaSlicer_version_text":version,
        "printer_profile_physically_calibrated":False,
        "all_calls_successful":success,
        "actual_slicer_executed":True,
        "attempt_count":len(cases),
        "case_results":cases,"profile_rankings":candidates,
        "fabrication_or_physical_printer_execution_authorized":False,
        "limitations":[
            "Generic RepRap profile only: no verified target printer, machine acceleration, extruder flow, materials or calibrated thermals.",
            "All printed mass and time values are estimates from G-code, not actual weighed filament or observed print time.",
            "Support material explicitly disabled; absence of generated supports does not prove overhangs are printable.",
            "No ESD qualification, tensile/impact/creep model, thermal FEA, physical fit coupon or printed prototype.",
            "No live physical hardware measurements: board envelope and mass are hypothetical baseline values."
        ]
    }
    (out/"SLICER_COMPARISON.json").write_bytes(canonical(report))
    return report

def audit_slicer_report(req:Mapping[str,Any],profile:Mapping[str,Any],*,cad_dir:Path,
                        out:Path,require_gcode:bool=False)->dict[str,Any]:
    validate_design(req)
    _assert_valid_profile(profile,req)
    report=json.loads((out/"SLICER_COMPARISON.json").read_text())
    if report.get("schema")!=RESULT or not report.get("all_calls_successful") or not report.get("actual_slicer_executed"):
        raise ValueError("slicer experiment did not complete native runs")
    if report["design_source_sha256"]!=hashlib.sha256(canonical(req)).hexdigest() or report["slicer_profile_sha256"]!=hashlib.sha256(canonical(profile)).hexdigest():
        raise ValueError("altered source design or slicer profile")
    if report["native_CAD_audit"]!=audit_bundle(req,cad_dir):
        raise ValueError("slicer trial does not correspond to native geometry audit")
    expected_count=len(req["alternatives"])*len(profile["profiles"])
    if report["attempt_count"]!=expected_count or len(report["case_results"])!=expected_count:
        raise ValueError("slicer trial is incomplete")
    for layer in profile["profiles"]:
        rows=[r for r in report["case_results"] if r["profile"]==layer["id"]]
        if [r["design"] for r in rows]!=[alt["id"] for alt in req["alternatives"]]:
            raise ValueError("actual slice sequence missing, duplicated or swapped")
        for row in rows:
            if row["slice_status"]!="valid_gcode" or row["slicer_exit_code"]!=0:
                raise ValueError("missing successful native slicer execution")
            cad=next(x for x in report["native_CAD_audit"]["verified_candidates"] if x==row["design"])
            part=cad_dir/"candidates"/cad/(cad+".stl")
            if row["origin_stl_sha256"]!=file_sha(part):
                raise ValueError("slice source STL changed since model test")
            if row["gcode_released_for_physical_printer"] is not False:
                raise ValueError("unverified machine G-code cannot be released as trusted fabrication instruction")
            gcode=out/(layer["id"]+"__"+row["design"]+".gcode")
            if require_gcode or gcode.is_file():
                if not gcode.is_file() or file_sha(gcode)!=row["slicer_output_sha256"]:
                    raise ValueError("retained native G-code changed")
                stats=read_statistics(gcode.read_text(encoding="utf-8",errors="replace"),layer=layer)
                if stats!=row["slicer_stats"]:
                    raise ValueError("G-code toolpath statistics did not match sealed results")
        ranking=next(x for x in report["profile_rankings"] if x["profile"]==layer["id"])
        feasible=[r for r in rows if r["cad_numeric_feasible"]]
        sortedrows=sorted(feasible,key=lambda r:(
            r["slicer_stats"]["filament_mass_g"],r["slicer_stats"]["estimated_time_s"],r["design"]
        ))
        if ranking["slicer_feasible_rank"]!=[x["design"] for x in sortedrows] or ranking["slicer_filament_selection"]!=sortedrows[0]["design"]:
            raise ValueError("actual slicer mass ranking was modified after run")
    if report["fabrication_or_physical_printer_execution_authorized"] is not False:
        raise ValueError("slicer experiment promoted unverified fabrication authority")
    return {"schema":"hs.slicer_trial_offline_audit.v1",
            "actual_native_slice_count":expected_count,
            "rankings":report["profile_rankings"],
            "gcode_hashes_verified":require_gcode or all(
                (out/(r["profile"]+"__"+r["design"]+".gcode")).is_file() for r in report["case_results"]
            ),
            "physical_print_authorized":False}
