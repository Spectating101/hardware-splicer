"""Generate a real Mecha-Splicer folding terminal candidate and CAD mesh audit.

No software run can make physical firmware, keyboard, battery or hinge work.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import sys

from mecha_splicer.bundle import generate_bundle

HERE=Path(__file__).resolve().parent


def audit_stl(path:Path)->dict:
    data=path.read_bytes()
    if len(data)<84: raise ValueError("STL header missing")
    n=struct.unpack_from("<I",data,80)[0]
    if n<=0 or len(data)!=84+50*n:raise ValueError("Invalid binary STL record count")
    edges=Counter()
    lo=[math.inf]*3
    hi=[-math.inf]*3
    volume=0.0
    for i in range(n):
        o=84+50*i
        a,b,c=[struct.unpack_from("<fff",data,o+x) for x in (12,24,36)]
        verts=(a,b,c)
        for v in verts:
            for axis in range(3):
                lo[axis]=min(lo[axis],v[axis])
                hi[axis]=max(hi[axis],v[axis])
        quantized=[tuple(round(x,4) for x in v) for v in verts]
        for j,k in ((0,1),(1,2),(2,0)):
            edges[tuple(sorted((quantized[j],quantized[k])))]+=1
        v1=(b[1]*c[2]-b[2]*c[1],b[2]*c[0]-b[0]*c[2],b[0]*c[1]-b[1]*c[0])
        volume+=sum(a[k]*v1[k] for k in range(3))/6
    bad=sum(1 for x in edges.values() if x!=2)
    if bad: raise ValueError(f"Mesh open/non-manifold: {bad} edges with incidence !=2")
    return {
       "status":"CGAL_OPENSCAD_MESH_GEOMETRY_ONLY",
       "sha256":hashlib.sha256(data).hexdigest(),
       "triangle_count":n,"nonmanifold_edges":bad,
       "bbox_mm":[round(hi[k]-lo[k],2) for k in range(3)],
       "bbox_min_mm":[round(x,2) for x in lo],
       "bbox_max_mm":[round(x,2) for x in hi],
       "signed_volume_cm3":round(volume/1000,3),
       "CAD_validated":True,"physically_printed":False,
       "physical_fit_verified":False
    }


def run(spec_path:Path,output:Path,openscad:str)->dict:
    spec=json.loads(spec_path.read_text(encoding="utf-8"))
    bundle=generate_bundle(spec,out_dir=output)
    # Normalize the native BOM CSV CRLF to LF for reproducible evidence diffs.
    csv_path=output/"bom.csv"
    csv_path.write_bytes(csv_path.read_bytes().replace(b"\r\n",b"\n"))
    is_dual = spec["clamshell_terminal"].get("input_surface_mode") == "dual_touch"
    expect={"base_shell.scad","lid_shell.scad","clamshell_open_preview.scad"}
    if is_dual:
        expect.add("dual_touch_visual_preview.scad")
    if bundle["blockers"] or set(bundle["outputs"])!=expect:
        raise ValueError(f"Native HS bundle did not provide exact clamshell parts: {bundle}")
    mesh={}
    for part in ("base_shell","lid_shell"):
        src=output/(part+".scad")
        dst=output/(part+".stl")
        cmd=[openscad]
        if openscad.endswith(".AppImage"):
            cmd.append("--appimage-extract-and-run")
        subprocess.run(cmd+["--export-format","binstl","-o",str(dst),str(src)],
             check=True,capture_output=True,text=True,timeout=120)
        mesh[part]=audit_stl(dst)

    # Preview uses native parts at specified open angle, exported separately.
    cmd=[openscad]
    if openscad.endswith(".AppImage"):
        cmd.append("--appimage-extract-and-run")
    subprocess.run(cmd+["--export-format","binstl","-o",
           str(output/"clamshell_open_preview.stl"),
           str(output/"clamshell_open_preview.scad")],
           check=True,capture_output=True,text=True,timeout=120)

    p=spec["clamshell_terminal"]
    is_inset = p.get("hinge_style") == "inset_side_pins"
    hinge_y=(p["case_d_mm"]-p["hinge_inset_from_rear_mm"] if is_inset
             else p["case_d_mm"]+p["hinge_y_offset_mm"])
    # Real CGAL boolean geometry test at 6 actual hinge poses. OpenSCAD
    # produces no STL when the intersection object is empty.
    angles=[0,-30,-60,-90,-135,-165]
    sweep=[]
    with tempfile.TemporaryDirectory(prefix="hs-hinge-check-") as td:
        for angle in angles:
            scene=Path(td)/"collision.scad"
            coll=Path(td)/"intersection.stl"
            scene.write_text(
                "use <"+str((output/"base_shell.scad").resolve())+">\n"
                "use <"+str((output/"lid_shell.scad").resolve())+">\n"
                "intersection() {\n"
                "base_shell();\n"
                f"translate([0,{hinge_y},{p['base_h_mm']+p['closed_gap_mm']/2}])"
                f" rotate([{angle},0,0])"
                f" translate([0,-{hinge_y},"
                f"-{p['base_h_mm']+p['closed_gap_mm']/2}]) lid_shell();\n"
                "}\n", encoding="utf-8")
            cmd=[openscad]
            if openscad.endswith(".AppImage"):
                cmd.append("--appimage-extract-and-run")
            result=subprocess.run(cmd+["--export-format","binstl","-o",str(coll),str(scene)],
                 capture_output=True,text=True,timeout=90,check=False)
            is_empty=("Current top level object is empty." in result.stderr+
                      result.stdout)
            if coll.exists() or not is_empty:
                raise ValueError(f"Hinge pose {angle} collision or invalid CGAL run: "
                     f"stl_exists={coll.exists()} stderr={result.stderr[-250:]}")
            sweep.append({"angle_deg":angle,"interference_mesh":"EMPTY",
                          "cad_clearance_pass":True})
    # A second Waveshare board has its own touch controller. Do NOT treat the
    # dual-board RS485 link as a CardKB 5V I2C level-shifter problem.
    voltage_plan=None
    if not is_dual:
        # Existing HS engineering planner (not a custom shifter design):
        # the generic ESP32-devkit registry entry stands in for ESP32-S3.
        sys.path.insert(0,str(HERE.parents[1]/"src"))
        from hardware_splicer.sdk import plan_level_shift_circuit
        voltage_plan=plan_level_shift_circuit({
        "goal":"ESP32-S3 3.3V I2C to external 5V CardKB keyboard; SCL/SDA",
        "signal_requirements":[{
            "type":"i2c","controller_voltage_v":3.3,
            "peripheral_voltage_v":5.0,"channels":2,
        }],
        "allowed_modules":["usb-power-5v","esp32-devkit","level-shifter-4ch"],
        "notes":"Catalog ESP32 devkit proxy, CardKB exact module not in registry; vendor wires NOT pinned",
    })
        if voltage_plan["result"] not in ("ready_for_review","blocked"):
            raise ValueError("HS electrical synthesis unexpectedly authorized without bench proof")
        if any(g["status"]!="open" for g in voltage_plan["verification_gates"]):
            raise ValueError("Pre-hardware electrical measurement gates must remain OPEN")
        (output/"hs_level_shift_review.json").write_text(
            json.dumps(voltage_plan,indent=2)+"\n",encoding="utf-8")
    envelope={
       "width_mm":p["case_w_mm"],
       "depth_without_hinge_mm":p["case_d_mm"],
       "closed_thickness_mm":round(p["base_h_mm"]+p["lid_h_mm"]+p["closed_gap_mm"],2),
       "hinge_projection_mm":round((p["hinge_outer_d_mm"]/2-p["hinge_inset_from_rear_mm"])
           if is_inset else p["hinge_y_offset_mm"]+p["hinge_outer_d_mm"]/2,2),
       "hinge_style":p.get("hinge_style","external_three_knuckle"),
       "hinge_axis_y_mm":round(hinge_y,3),
       "display_board_outer_footprint_mm":[p["display_board_w_mm"],p["display_board_d_mm"]],
       "lower_board_footprint_mm": ([p["lower_touch_board_w_mm"],p["lower_touch_board_d_mm"]]
           if is_dual else [p["keyboard_w_mm"],p["keyboard_d_mm"]]),
       "lower_input_type":"dual_touch" if is_dual else "physical_keyboard",
       "battery_not_yet_integrated":True,
       "vendor_board_mounting_holes_unknown":True,
       "port_access_cutouts_unverified":True
    }
    report={
      "schema":"hs.clamshell_ssh_cad.v1","generator":"native mecha_splicer.bundle.generate_bundle",
      "spec":str(spec_path.relative_to(HERE)),
      "native_outputs":bundle["outputs"],
      "native_dfm":bundle["dfm"],
      "native_bom":bundle["bom"],
      "native_hs_level_shift_result":(voltage_plan["result"] if voltage_plan else "NOT_APPLICABLE_RS485_LINK"),
      "native_hs_level_shift_measurement_gates_open":(len(voltage_plan["verification_gates"]) if voltage_plan else 0),
      "native_hs_level_shift_caveat":("Existing generic ESP32-devkit logic surrogate, not exact Waveshare pinout" if voltage_plan
             else "Dual Waveshare boards use onboard SP3485 RS485; A/B, reference, power and firmware still unverified"),
      "mesh":mesh,
      "cgal_interference_sweep":sweep,
      "closed_envelope":envelope,
      "electrical_wiring_not_ready":True,
      "firmware_ssh_connected_to_optiplex":False,
      "physical_hinge_sweep_tested":False,
      "physical_fit_tested":False,
      "actual_unit_assembled":False,
      "usage_notes":"CGAL manifold checks prove geometry only. No vendor pin-length, battery, USB cutout or internal stacking proof."
    }
    (output/"design_evidence.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--spec",type=Path,default=HERE/"clamshell_ssh_terminal.json")
    p.add_argument("--out",type=Path,default=HERE/"evidence"/"native_mecha")
    p.add_argument("--openscad",default=shutil.which("openscad"))
    a=p.parse_args()
    if not a.openscad:raise SystemExit("Real OpenSCAD CLI required; do not fabricate STL output")
    res=run(a.spec,a.out,a.openscad)
    print("Native HS CAD generated, CGAL exported both meshes")
    print("Closed nominal envelope",res["closed_envelope"])
    for k,v in res["mesh"].items():
      print(k,"triangles",v["triangle_count"],"bbox",v["bbox_mm"],
            "vol cm3",v["signed_volume_cm3"],"nonmanifold",v["nonmanifold_edges"])
    print("CGAL hinge collisions checked",len(res["cgal_interference_sweep"]),
          "poses; all empty")
    print("HS electrical",res["native_hs_level_shift_result"],
          "open meter/continuity gates",res["native_hs_level_shift_measurement_gates_open"])
    print("HARDWARE VERIFIED:",res["actual_unit_assembled"],
          "SSH PROVEN:",res["firmware_ssh_connected_to_optiplex"])
if __name__=="__main__":main()
