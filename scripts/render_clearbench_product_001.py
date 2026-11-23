#!/usr/bin/env python3
"""Render complete product scene in native OpenSCAD; check independent STL bounds.

All solids remain illustrative non-rated geometry. The preview is a product-
level assembled concept, not a physical prototype or printable filtration rig.
"""
from __future__ import annotations
import argparse,hashlib,json,math,shutil,subprocess,sys
from pathlib import Path

import trimesh

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def verify(root:Path)->dict:
    root=Path(root)
    receipt=json.loads((root/"PRODUCT_RECEIPT.json").read_text())
    if receipt.get("schema_version")!="hardware_splicer.product_demonstrator_receipt.v1":
        raise ValueError("unknown product source receipt")
    for name,ref in receipt["files"].items():
        b=(root/name).read_bytes()
        if sha(b)!=ref["sha256"] or len(b)!=ref["bytes"]:
            raise ValueError("tampered product source: "+name)
    spec=json.loads((root/"PRODUCT_SPEC.json").read_text())
    arch=json.loads((root/"PRODUCT_ARCHITECTURE.json").read_text())
    if arch.get("product_spec_sha256")!=receipt["product_spec_sha256"] or arch.get("release_tier")!="DIGITAL_PRODUCT_DEMONSTRATOR_ONLY":
        raise ValueError("wrong product identity/readiness")
    if any(arch["physical_authority"].values()):
        raise ValueError("physical authority forged")
    exe=shutil.which("openscad")
    if not exe:raise ValueError("real OpenSCAD CLI not installed")
    tool=subprocess.run([exe,"--version"],capture_output=True,text=True,check=True)
    dimensions={
      "tray":([450,260,14],[0,14]),
      "panel":([450,12,716],[14,730]),
      "housing":([118,118,308],[228,536]),
      "service":([118,118,150],[78,228]),
      "sample":([66,66,75],[32,107]),
    }
    src=root/"PRODUCT_SCENE.scad"
    evidence={}
    for name,(target_size,target_z) in dimensions.items():
        p=root/("concept_"+name+".stl")
        if p.exists():raise FileExistsError("refuse overwriting previous product geometry")
        run=subprocess.run([exe,"-o",str(p),"-D",f'part="{name}"',str(src)],
            capture_output=True,text=True,timeout=120)
        if run.returncode!=0 or not p.is_file():
            raise ValueError("native OpenSCAD component failed: "+name+" "+run.stderr[-1500:])
        mesh=trimesh.load_mesh(str(p),force="mesh",file_type="stl")
        if not mesh.is_watertight or not mesh.is_winding_consistent or not mesh.is_volume:
            raise ValueError("non-watertight native concept geometry: "+name)
        if not all(math.isclose(float(mesh.extents[i]),v,abs_tol=0.15)
                   for i,v in enumerate(target_size)):
            raise ValueError("concept component dimensions drift: "+name)
        if not all(math.isclose(float(mesh.bounds[i,2]),v,abs_tol=0.15)
                   for i,v in enumerate(target_z)):
            raise ValueError("concept component height position invalid: "+name)
        b=p.read_bytes()
        evidence[name]={
          "file":p.name,"sha256":sha(b),"bytes":len(b),
          "extent_mm":[round(float(x),2) for x in mesh.extents],
          "z_bounds_mm":[round(float(x),2) for x in mesh.bounds[:,2]],
          "watertight":True,"winding_consistent":True,
          "conceptual_cad_not_fabrication_validated":True
        }
    image=root/"CLEARBENCH_S1_PRODUCT_PREVIEW.png"
    if image.exists():raise FileExistsError("refuse overwriting product scene image")
    xvfb=shutil.which("xvfb-run")
    command=([xvfb,"-a"] if xvfb else []) + [exe,"-o",str(image),
        "-D",'part="assembly"', "--imgsize","1500,1150",
        "--projection","p","--viewall","--autocenter",
        "--colorscheme","Tomorrow","--camera","700,-950,930,0,0,370",
        str(src)]
    render=subprocess.run(command,capture_output=True,text=True,timeout=150)
    if render.returncode!=0 or not image.is_file() or image.stat().st_size<6000:
        raise ValueError("complete product scene PNG render failed: "+render.stderr[-1900:])
    record={
      "schema_version":"hardware_splicer.whole_product_native_render.v1",
      "product_id":spec["product_id"],
      "source_spec_sha256":receipt["source_spec_sha256"],
      "product_spec_sha256":receipt["product_spec_sha256"],
      "product_scene_sha256":sha(src.read_bytes()),
      "renderer":"OpenSCAD CLI",
      "renderer_version":tool.stdout.strip() or tool.stderr.strip(),
      "trimesh_version":trimesh.__version__,
      "complete_product_assembly_image":{
          "file":image.name,"sha256":sha(image.read_bytes()),"bytes":image.stat().st_size,
          "shows_integrated_operator_facing_digital_assembly":True,
          "physically_constructed_device":False,
      },
      "independently_checked_native_geometry":evidence,
      "source_housing_envelope_not_internal_geometry":True,
      "diagrammatic_inlet_outlet_routes_only":True,
      "native_pressure_containment_created":False,
      "bracket_fit_and_load_verified":False,
      "real_sample_water_treated":False,
      "product_build_ready":False,
      "physical_authority_granted":False,
    }
    path=root/"PRODUCT_RENDER_EVIDENCE.json"
    if path.exists():raise FileExistsError("cannot overwrite native product proof")
    path.write_text(json.dumps(record,indent=2,sort_keys=True)+"\n")
    return record

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project",type=Path,required=True)
    a=p.parse_args()
    try: print(json.dumps(verify(a.project),indent=2,sort_keys=True))
    except (OSError,ValueError,subprocess.SubprocessError,KeyError,TypeError) as e:
        print("WHOLE PRODUCT CAD REFUSED:",e,file=sys.stderr)
        raise SystemExit(1)
