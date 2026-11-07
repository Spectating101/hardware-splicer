"""Native OpenSCAD nominal/worst-case LCD proxy collision study.

Uses real CGAL intersections for panel-to-panel & panel-to-opposite-shell
across hinge poses and a self-shell/vendor +0.5mm tolerance control.
These are boxes, NOT a validated vendor STEP, live FPC or hardware sweep.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def _run_cgal(openscad:str, src:Path, out:Path)->dict:
    cmd=[openscad]
    if openscad.endswith(".AppImage"):
        cmd.append("--appimage-extract-and-run")
    p=subprocess.run(cmd+["--export-format","binstl","-o",str(out),str(src)],
                     capture_output=True,text=True,timeout=120)
    marker="Current top level object is empty."
    # OpenSCAD 2021 can exit nonzero for a valid empty CSG intersection.
    if not out.exists() and marker in p.stderr+p.stdout:
        return {"intersection":"EMPTY","file_sha256":None,"mesh_bytes":0}
    if p.returncode!=0:
        raise RuntimeError(f"OpenSCAD CGAL failed: {p.stderr[-600:]}")
    if out.exists():
        data=out.read_bytes()
        if len(data)<84:
            raise RuntimeError("bad STL output")
        return {"intersection":"NONEMPTY","file_sha256":hashlib.sha256(data).hexdigest(),
                "mesh_bytes":len(data)}
    if marker in p.stderr+p.stdout:
        return {"intersection":"EMPTY","file_sha256":None,"mesh_bytes":0}
    raise RuntimeError("OpenSCAD returned neither a valid collision mesh nor its empty marker")


def run(specfile:Path, native_mecha:Path, openscad:str, out:Path)->dict:
    p=json.loads(specfile.read_text())["clamshell_terminal"]
    if p.get("hinge_style")!="inset_side_pins" or p.get("compute_architecture")!="cm4_dual_dsi":
        raise ValueError("LCD CGAL sweep requires HS native CM4 inset hinge")
    if p.get("case_w_mm")!=155 or p.get("case_d_mm")!=80:
        raise ValueError("must test actual 155x80 closed package")
    if p.get("input_surface_mode")!="dual_touch":
        raise ValueError("physical keyboard not accepted")
    if p.get("display_board_w_mm")!=127.6 or p.get("display_board_d_mm")!=73.3:
        raise ValueError("vendor panel envelope changed")
    w,d=p["case_w_mm"],p["case_d_mm"]
    upper_z=p["base_h_mm"]+p["closed_gap_mm"]
    nominal_t=3.45
    worst_t=3.95
    x=(w-127.6)/2
    y=(d-73.3)/2
    pivot_y=d-p["hinge_inset_from_rear_mm"]
    pivot_z=p["base_h_mm"]+p["closed_gap_mm"]/2
    for name in ("base_shell.scad","lid_shell.scad"):
        if not (native_mecha/name).is_file():
            raise ValueError("native HS OpenSCAD mesh source missing: "+name)
    base_src=(native_mecha/"base_shell.scad").resolve()
    lid_src=(native_mecha/"lid_shell.scad").resolve()
    head=(
        f"use <{base_src}>\nuse <{lid_src}>\n"
        f"module lower_panel() {{ translate([{x},{y},{p['base_h_mm']-nominal_t}]) cube([127.6,73.3,{nominal_t}]); }}\n"
        f"module upper_panel() {{ translate([{x},{y},{upper_z}]) cube([127.6,73.3,{nominal_t}]); }}\n"
        "module lower_assembly(){ union(){ base_shell(); lower_panel(); }}\n"
        "module upper_assembly(){ union(){ lid_shell(); upper_panel(); }}\n"
    )
    angles=[0,-30,-60,-90,-135,-165]
    poses=[]
    with tempfile.TemporaryDirectory(prefix="hs-real-cgal-panel-") as temp:
        t=Path(temp)
        for angle in angles:
            script=t/"crosshalf.scad"
            output=t/"crosshalf.stl"
            output.unlink(missing_ok=True)
            scene=(head+"intersection(){ lower_assembly(); "+
                f"translate([0,{pivot_y},{pivot_z}]) rotate([{angle},0,0]) "+
                f"translate([0,-{pivot_y},-{pivot_z}]) upper_assembly(); }}\n")
            script.write_text(scene)
            result=_run_cgal(openscad,script,output)
            poses.append({"angle_deg":angle,**result})
        # Worst-case panel with the *same* nominal upper tray must intrude into
        # the upper lid floor; this is intentionally a negative control.
        src=t/"lid_vendor_max.scad"
        dst=t/"lid_vendor_max.stl"
        src.write_text(head+f"intersection(){{ lid_shell(); translate([{x},{y},{upper_z}]) cube([127.6,73.3,{worst_t}]); }}\n")
        control=_run_cgal(openscad,src,dst)
    report={
        "schema":"hardware_splicer.inset_hinge_panel_collision_cgal.v1",
        "generator":"real OpenSCAD/CGAL multi-body intersection not hand-drawn animation",
        "panels":"Winstar WF50DTYA3MNG10-000: 2 separate rigid screens, no physical keyboard",
        "nominal_screen_mm":[127.6,73.3,nominal_t],
        "manufacturer_max_screen_mm":[127.6,73.3,worst_t],
        "angles":poses,
        "nominal_two_half_CGAL_collision_free":all(x["intersection"]=="EMPTY" for x in poses),
        "vendor_max_panel_inside_nominal_lid":control,
        "vendor_max_panel_collides_with_lid_floor":control["intersection"]=="NONEMPTY",
        "internal_battery_vs_LCD_collision_verified":False,
        "FPC_dynamic_collision_verified":False,
        "real_components_installed":False,
        "physical_build_authorized":False,
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+"\n")
    return report


def main()->None:
    a=argparse.ArgumentParser()
    a.add_argument("--spec",type=Path,required=True)
    a.add_argument("--native-mecha",type=Path,required=True)
    a.add_argument("--openscad",default=shutil.which("openscad"))
    a.add_argument("--out",type=Path,required=True)
    v=a.parse_args()
    if not v.openscad:
        raise SystemExit("real OpenSCAD executable required; simulation cannot be invented")
    result=run(v.spec,v.native_mecha,v.openscad,v.out)
    print(json.dumps({
        "nominal_two_half_CGAL_collision_free":result["nominal_two_half_CGAL_collision_free"],
        "vendor_max_panel_collides_with_lid_floor":result["vendor_max_panel_collides_with_lid_floor"],
        "panel_flex_qualified":result["FPC_dynamic_collision_verified"],
        "build_authorized":result["physical_build_authorized"],
    },indent=2))


if __name__=="__main__":
    main()
