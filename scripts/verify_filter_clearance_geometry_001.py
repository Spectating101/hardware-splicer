#!/usr/bin/env python3
"""Render genuine OpenSCAD clearance solids; verify actual mesh bounds with trimesh.

This models occupancy and illustrative access clearance, NOT a pressure vessel,
filter housing design, rated mounting assembly or manufacturable fixture.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import trimesh

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.filter_component_preflight import canonical,clearance_scad

def digest(x:bytes)->str: return hashlib.sha256(x).hexdigest()

def validate_project(p:Path)->dict:
    receipt=json.loads((p/"COMPONENT_PACKAGE_RECEIPT.json").read_text())
    if receipt.get("schema_version")!="hardware_splicer.filter_component_package_receipt.v1":
        raise ValueError("incorrect component source receipt")
    for name,row in receipt["files"].items():
        blob=(p/name).read_bytes()
        if digest(blob)!=row["sha256"] or len(blob)!=row["bytes"]:
            raise ValueError("component source artifact changed: "+name)
    report=json.loads((p/"COMPONENT_PREFLIGHT.json").read_text())
    if report.get("schema_version")!="hardware_splicer.nonpotable_filter_component_preflight.v1":
        raise ValueError("unexpected preflight report")
    if report["source_spec_sha256"]!=receipt["source_spec_sha256"] or report["component_reference_sha256"]!=receipt["component_reference_sha256"]:
        raise ValueError("inconsistent source identity")
    if clearance_scad(report).encode()!=(p/"clearance.scad").read_bytes():
        raise ValueError("CAD is not reproducible from component report")
    if report["native_pressure_containing_part_generated"] or report["pressure_activation_authorized"] or report["human_consumption_authorized"]:
        raise ValueError("CAD incorrectly claims physical operation")
    if (p/"RENDERED_CLEARANCE_EVIDENCE.json").exists():
        raise FileExistsError("previous geometry evidence cannot be overwritten")
    binary=shutil.which("openscad")
    if binary is None: raise ValueError("missing real OpenSCAD CLI")
    v=subprocess.run([binary,"--version"],capture_output=True,text=True,check=True)
    blobs={}
    info={}
    dimensions={
        "housing":(118.0,308.0,0.0,308.0),
        "service":(118.0,float(report["conceptual_service_corridor_mm"]["height"]),
                   -float(report["conceptual_service_corridor_mm"]["height"]),0.0),
    }
    with tempfile.TemporaryDirectory(prefix="hs-filter-scad-") as tmp:
        for name,(diameter,height,minz,maxz) in dimensions.items():
            target=p/("clearance_"+name+".stl")
            if target.exists():raise FileExistsError("existing STL cannot be overwritten")
            cmd=[binary,"-o",str(target),"-D",f'part="{name}"',str(p/"clearance.scad")]
            run=subprocess.run(cmd,capture_output=True,text=True,check=False,timeout=120)
            if run.returncode or not target.is_file():
                raise ValueError("OpenSCAD render failed: "+(run.stderr+run.stdout)[-2500:])
            mesh=trimesh.load_mesh(str(target),file_type="stl",force="mesh")
            if not mesh.is_watertight or not mesh.is_winding_consistent or not mesh.is_volume:
                raise ValueError("native clearance mesh invalid: "+name)
            extent=mesh.extents
            bounds=mesh.bounds
            if (any(not math.isclose(float(extent[i]),value,abs_tol=0.1)
                    for i,value in enumerate((diameter,diameter,height)))
                or not math.isclose(float(bounds[0,2]),minz,abs_tol=0.1)
                or not math.isclose(float(bounds[1,2]),maxz,abs_tol=0.1)):
                raise ValueError("native clearance dimensions do not match component document: "+name)
            ideal=math.pi*(diameter/2)**2*height
            if not math.isclose(mesh.volume,ideal,rel_tol=0.005):
                raise ValueError("native clearance solid volume invalid: "+name)
            contents=target.read_bytes()
            blobs[name]=digest(contents)
            info[name]={
                "stl_filename":target.name,
                "sha256":digest(contents),
                "bytes":len(contents),
                "dimensions_mm":[round(float(v),3) for v in extent],
                "z_bounds_mm":[round(float(bounds[0,2]),3),round(float(bounds[1,2]),3)],
                "mesh_volume_mm3":round(float(mesh.volume),3),
                "watertight":True,"winding_consistent":True,
            }
    output={
        "schema_version":"hardware_splicer.filter_clearance_native_cad_evidence.v1",
        "source_spec_sha256":receipt["source_spec_sha256"],
        "component_reference_sha256":receipt["component_reference_sha256"],
        "cad_source_sha256":digest((p/"clearance.scad").read_bytes()),
        "renderer":"OpenSCAD CLI",
        "renderer_version":v.stdout.strip() or v.stderr.strip(),
        "inspector_version":trimesh.__version__,
        "solids":info,
        "catalog_envelope_dimensions_verified_in_rendered_mesh":True,
        "physical_product_measured":False,
        "installation_clearance_verified":False,
        "physical_fit_verified":False,
        "mounting_holes_modeled":False,
        "hydraulic_model_executed":False,
        "pressure_containing_design_generated":False,
        "manufacturing_authorized":False,
        "water_activation_authorized":False,
        "human_consumption_authorized":False,
    }
    (p/"RENDERED_CLEARANCE_EVIDENCE.json").write_bytes(canonical(output))
    return output

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",required=True,type=Path)
    args=parser.parse_args()
    try: print(json.dumps(validate_project(args.project),indent=2,sort_keys=True))
    except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as e:
        print("NATIVE CLEARANCE VERIFICATION REFUSED:",e,file=sys.stderr)
        return 1
    return 0

if __name__=="__main__":
    raise SystemExit(main())
