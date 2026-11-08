"""Inspect the manufacturer-supplied Waveshare 5inch DSI LCD (D) STEP via OpenCascade.

Optional developer dependency: cadquery-ocp (OCP). This is NOT a handcrafted
CAD shape. The original vendor STEP is fetched separately and not redistributed.

Example:
  PYTHONPATH=/path/to/ocp python inspect_waveshare_step.py \
      --step /tmp/5inch-dsi-lcd-d_20241025.stp --out evidence/waveshare_d_step.json

The selected largest-face solid is a geometric heuristic; identifying what
electronics can safely be disassembled needs vendor drawings and real teardown.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def measure_step(path:Path)->dict:
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    reader=STEPControl_Reader()
    if str(reader.ReadFile(str(path)))!="IFSelect_ReturnStatus.IFSelect_RetDone":
        raise ValueError("vendor STEP could not be read")
    if reader.TransferRoots()<1:
        raise ValueError("STEP has no transferable solid assemblies")
    shape=reader.OneShape()
    def bounds(s):
        b=Bnd_Box();BRepBndLib.Add_s(s,b)
        raw=b.Get()
        return [round(float(q),3) for q in raw]
    outer=bounds(shape)
    exp=TopExp_Explorer(shape,TopAbs_SOLID)
    objects=[]
    while exp.More():
        objects.append(bounds(exp.Current()))
        exp.Next()
    if not objects:
        raise ValueError("manufacturer STEP has no solid bodies")
    xy_face=[s for s in objects if (s[3]-s[0])>70 and (s[4]-s[1])>126]
    if len(xy_face)!=1:
        raise ValueError("need one clearly identifiable whole face solid, not a guessed panel")
    face=xy_face[0]
    # Six-dimensional solid bounding min/max is not an accurate tolerance
    # stack and cannot tell which components may safely be relocated.
    # Identify below-front protrusions, but DO NOT claim safe disassembly.
    deep=[s for s in objects if s[2] < -8]
    rest=[s for s in objects if s not in deep]
    nonmount_min=min(s[2] for s in rest)
    max_z=max(s[5] for s in rest)
    out={
        "schema":"hs.vendor_step_waveshare_5inch_D_open_cascade.v1",
        "vendor_model":"Waveshare 5inch DSI LCD (D), 2024-10-25 STEP",
        "source_zip_url":"https://files.waveshare.com/wiki/5inch%20DSI%20LCD%20%28D%29/5inch-dsi-lcd-d_3D.zip",
        "step_file":path.name,
        "step_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
        "analysis_engine":"OpenCascade OCP STEPControl_Reader + BRepBndLib",
        "outer_bbox_xyz_mm":[round(outer[3]-outer[0],3),
                             round(outer[4]-outer[1],3),
                             round(outer[5]-outer[2],3)],
        "outer_bbox_min_xyz_mm":outer[:3],
        "outer_bbox_max_xyz_mm":outer[3:],
        "number_solid_components":len(objects),
        "one_full_face_solid_bbox_mm":[round(face[3]-face[0],3),
                                      round(face[4]-face[1],3),
                                      round(face[5]-face[2],3)],
        "face_solid_identification":"largest continuous 70x126mm solid heuristic, not validated separable panel SKU",
        "deep_z_below_minus_8mm_solid_count":len(deep),
        "remaining_after_omitting_deep_solid_envelope_mm":round(max_z-nonmount_min,3),
        "claim_safe_to_remove_standoffs":False,
        "module_2x_full_assembly_Z_mm":round(2*(outer[5]-outer[2]),3),
        "module_2x_without_deep_solid_Z_mm":round(2*(max_z-nonmount_min),3),
        "panel_2x_face_solid_Z_mm":round(2*(face[5]-face[2]),3),
        "manufacturer_backlight_and_circuitry_present_in_face_only":None,
        "software_driver_after_disassembly_qualified":False,
        "fabrication_qualified":False,
    }
    return out


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--step",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    opt=parser.parse_args()
    result=measure_step(opt.step)
    opt.out.parent.mkdir(parents=True,exist_ok=True)
    opt.out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in (
       "outer_bbox_xyz_mm","one_full_face_solid_bbox_mm",
       "remaining_after_omitting_deep_solid_envelope_mm",
       "number_solid_components","module_2x_full_assembly_Z_mm")},indent=2))


if __name__=="__main__":
    main()
