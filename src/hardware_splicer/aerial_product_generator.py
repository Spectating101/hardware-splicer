"""Native HS 65/75mm quadrotor product design, not a third-party frame wrapper.

Mecha-Splicer writes original full-airframe parametric CAD + battery cradle;
HS robot_topology binds 4 rotor/motor identities; OpenSCAD only meshes the
HS CAD; trimesh measures exported physical geometry. Existing Crazyflie
simulation is labeled generic and is NOT calibrated to these new frames.
Physical printing/flight/authority are never asserted by file generation.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
MECHA=REPO/"apps/mecha-splicer/src"
if str(MECHA) not in sys.path: sys.path.insert(0,str(MECHA))
from mecha_splicer.bundle import generate_bundle
from .robot_topology import build_robot_topology


def _load(p): return json.loads(Path(p).read_text())
def _write(p,obj): Path(p).write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n")
def _sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def request_from_prompt(p):
    text=p.lower()
    options=[n for n in (65,75) if f"{n}mm" in text or f"{n} mm" in text]
    if len(options)!=1 or not any(s in text for s in ("drone","quadcopter","whoop")):
        raise ValueError("Specify '65mm drone' or '75mm drone'. Only these two hardware profiles are sourced.")
    return REPO/f"examples/drone_lab/design_requests/hs_native_{options[0]}mm.json"


def _contract(r):
    a=r["dimensions"];m=r["motor"];p=r["propeller"];f=r["controller"];b=r["battery"]
    size=float(a["wheelbase_mm"])
    if not 60 <= size <= 95: raise ValueError("microdrone wheelbase outside 60-95mm bounded HS design envelope")
    if not 30 <= float(a["prop_diameter_mm"]) <= 42:
        raise ValueError("only 30-42mm propeller class is supported by this native geometry/parts family")
    if any(int(x["cells"])!=1 for x in (m,f,b)): raise ValueError("only 1S equipment supported")
    if m["quantity"]!=4 or float(m["mount_pcd_mm"])!=float(a["motor_bolt_pcd_mm"]):
        raise ValueError("four motors and matching mounting bolt PCD required")
    if float(a["fc_mount_pitch_mm"])!=float(f["fc_mount_pitch_mm"]):
        raise ValueError("controller hole pitch is inconsistent with CAD")
    if float(a["prop_diameter_mm"])!=float(p["diameter_mm"]) or float(m["shaft_mm"])!=float(p["shaft_mm"]):
        raise ValueError("actual propeller/shaft dimensions incompatible")
    for x in (m,p,f):
        if not x.get("source","").startswith("https://"): raise ValueError("missing vendor source")
    current=m.get("max_current_a")
    if current is not None and float(current)>float(f["esc_current_a"]):
        raise ValueError("source-reported peak motor current exceeds ESC rating")
    if r.get("hardware_printed") or r.get("hardware_tested"):
        raise ValueError("unverified physical authority claimed in input")
    return {"status":"dimensional_contract_candidate",
            "motor_current":"unverified" if current is None else "supplier_report_only",
            "powered_hardware_verified":False}


def _render_preview(mesh,p,title):
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig=plt.figure(figsize=(10,5),dpi=130,facecolor="#121e2a")
    polygons=mesh.vertices[mesh.faces]
    for i,(elev,azim) in enumerate(((28,35),(90,-90))):
        ax=fig.add_subplot(1,2,i+1,projection="3d")
        ax.set_facecolor("#121e2a")
        ax.add_collection3d(Poly3DCollection(polygons,facecolor="#5abdc3",edgecolors="none",linewidths=0))
        span=float(max(mesh.extents))*.55
        ax.set(xlim=(-span,span),ylim=(-span,span),zlim=(-span*.3,span*.65))
        ax.set_box_aspect((1,1,.6));ax.set_axis_off()
        ax.view_init(elev=elev,azim=azim)
        ax.set_title("ISOMETRIC" if i==0 else "TOP VIEW",color="white")
    fig.text(.5,.04,title+" | native HS geometry, no real flight",ha="center",color="#c1d1dd")
    fig.savefig(p,bbox_inches="tight",facecolor=fig.get_facecolor())
    plt.close(fig)


def produce(request:Path,out:Path,openscad:Path,flight_source:Path|None=None,simulate=True):
    import trimesh
    r=_load(request)
    if r.get("schema_version")!="hardware_splicer.aerial_product_request.v1":
        raise ValueError("unknown design request schema")
    electrical=_contract(r)
    out.mkdir(parents=True,exist_ok=True)
    product=r["product_id"];a=r["dimensions"]
    cad=out/"HS_ORIGINAL_MECHANICAL"
    body={"project_name":product,"mode":"prototype","process":"fdm",
          "aerial_frame":{"name":product+"-unibody",**a}}
    bundle=generate_bundle(body,out_dir=cad)
    if bundle["blockers"] or set(bundle["outputs"])!={"aerial_frame.scad","battery_cradle.scad"}:
        raise ValueError("native Mecha-Splicer refused geometry: "+str(bundle["dfm"]))
    meshes={}
    for stem in ("aerial_frame","battery_cradle"):
        scad=cad/(stem+".scad");stl=cad/(stem+".stl")
        cmd=[str(openscad),"--export-format","binstl","-o",str(stl),str(scad)]
        proc=subprocess.run(cmd,capture_output=True,text=True,timeout=180,
                            env={**os.environ,"QT_QPA_PLATFORM":"offscreen"})
        if proc.returncode or not stl.is_file(): raise RuntimeError("cannot render native geometry: "+proc.stderr[-1200:])
        mesh=trimesh.load_mesh(stl,force="mesh",process=True)
        if not (mesh.is_watertight and mesh.is_volume and mesh.is_winding_consistent and len(mesh.split())==1):
            raise RuntimeError("not a valid single closed printable solid: "+stem)
        meshes[stem]=mesh

    frame=meshes["aerial_frame"];cradle=meshes["battery_cradle"]
    mass=round(frame.volume*.001*float(r.get("print_density_g_cm3",1.27)),2)
    intake={"project_name":product,"goal":r["goal"],"constraints":{"rotor_count":4},
            "available_parts":[{"type":"motor","role":"actuator","quantity":4,
                                "module_id":"motor-"+product,"name":r["motor"]["model"]},
                               {"type":"imu","role":"sensor","quantity":1,"module_id":"matrix1s-imu"}]}
    top=build_robot_topology(intake,hinted_genre="aerial_robot")
    if len(top.actuators)!=4: raise RuntimeError("HS did not create 4 actual actuator identities")
    _write(out/"HS_ROBOT_TOPOLOGY.json",top.model_dump(mode="json"))
    _write(out/"INPUT_PRODUCT_SPEC.json",r)
    parts=[
        ("Native HS 3D-printed aircraft frame",1,"aerial_frame.stl","Hardware Splicer"),
        ("Native HS printed battery cradle",1,"battery_cradle.stl","Hardware Splicer"),
        (r["controller"]["model"],1,"flight_controller",r["controller"]["source"]),
        (r["motor"]["model"],4,"motor",r["motor"]["source"]),
        (r["propeller"]["name"],4,"propellers",r["propeller"]["source"]),
        (f"1S {r['battery']['capacity_mah']}mAh BT2.0 verified LiPo/LiHV pack",2,"battery","actual pack dimensions must be measured"),
        (r["radio"],1,"radio","2.4GHz regional and firmware compatibility must be confirmed"),
        ("1S appropriate chemistry BT2.0 charger",1,"charger","charger and pack chemistry must match"),
        ("Correct length M1.4 motor screws",12,"motor_fasteners","verify screws do not contact motor windings"),
        ("FC vibration damping and battery strap",1,"retainers","actual physical fit unverified"),
    ]
    with (out/"REAL_PARTS_BOM.csv").open("w",newline="") as f:
        w=csv.writer(f);w.writerow(["component","quantity","role","origin"]);w.writerows(parts)
    scene=trimesh.Scene()
    scene.add_geometry(frame,geom_name="HS_NATIVE_WHOOP_FRAME")
    shift=trimesh.transformations.translation_matrix([float(frame.extents[0])*.8,0,0])
    scene.add_geometry(cradle,geom_name="HS_CRADLE_SEPARATE_PIECE",transform=shift)
    (out/"HS_PRODUCT_SCENE.glb").write_bytes(scene.export(file_type="glb"))
    _render_preview(frame,out/"FRAME_PREVIEW.png",product)

    (out/"ASSEMBLY.md").write_text(
        "# "+product+" — build from native HS CAD\n\n"
        "1. Slice HS_ORIGINAL_MECHANICAL/aerial_frame.stl and battery_cradle.stl; inspect upper hoop bridge supports.\n"
        "2. Physically print and WEIGH; evaluate strength, FDM tolerances and printed guard deflection.\n"
        "3. Measure actual battery, M1.4 motor bolt PCD, 1mm prop shafts, and Matrix 1S hole pitch.\n"
        "4. With props REMOVED dry-fit motors, FC, wiring, pack and removable battery cradle.\n"
        "5. Verify exact FC firmware target, ESC current, battery connector, ELRS binding and failsafe.\n"
        "6. Props OFF test gyro and motor mapping/direction; only then evaluate guarded indoor flight.\n\n"
        "NOT TESTED: real fit, print strength, battery retention, thrust, ESC draw, center of mass, failsafe or flight.\n"
        "Simulation (if included) is for upstream Crazyflie, NOT this new physical design.\n")

    reference=None
    if simulate:
        if not flight_source or not (flight_source/"gym_pybullet_drones/envs/CtrlAviary.py").is_file():
            raise ValueError("upstream flight model source required")
        folder=out/"CRAZYFLIE_SIM_NOT_THIS_AIRFRAME"
        cmd=[sys.executable,str(REPO/"examples/drone_lab/flight_lab.py"),
             "--mode","demo","--out",str(folder)]
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=120,
                         env={**os.environ,"PYTHONPATH":str(flight_source)+os.pathsep+
                              os.environ.get("PYTHONPATH","")})
        if p.returncode: raise RuntimeError("control reference simulation failed: "+p.stderr[-800:])
        reference=_load(folder/"flight_summary.json")
        reference["native_airframe_dynamics_calibrated"]=False
        _write(folder/"flight_summary.json",reference)

    verdict={
        "product_id":product,"new_HS_airframe_geometry":True,
        "other_people_airframe_reused":False,"atech_used":False,
        "native_engines":["mecha_splicer.bundle.generate_bundle",
                          "mecha_splicer.engines.aerial.generate_aerial_frame_scad",
                          "hardware_splicer.robot_topology.build_robot_topology"],
        "CAD_frame_extents_mm":[round(float(x),2) for x in frame.extents],
        "CAD_frame_estimated_PETG_mass_g":mass,
        "CAD_cradle_estimated_PETG_mass_g":round(float(cradle.volume)*.001*1.27,2),
        "CAD_frame_closed_mesh":True,"CAD_cradle_closed_mesh":True,
        "component_contract":electrical,
        "reference_flight_for_Crazyflie_only":bool(reference),
        "physical_printed":False,"flight_tested":False,"flight_authorized":False,
        "missing":["actual printed strength and impact behavior",
                   "motor and propeller physical fit","verified battery chemistry and dimensions",
                   "actual ESC draw and thrust","measured all-up mass / CG",
                   "radio failsafe and safely guarded first hover"],
    }
    _write(out/"PRODUCT_RESULT.json",verdict)
    (out/"START_HERE.md").write_text(
        "# "+product+"\n\n"
        "HS independently generated actual PRINTABLE FRAME STL and editable parametric OpenSCAD.\n"
        "Open FRAME_PREVIEW.png, HS_PRODUCT_SCENE.glb, and ASSEMBLY.md.\n"
        "Use REAL_PARTS_BOM.csv to source compatible components and check dimensions.\n"
        "This is an original HS frame, not the imported vsergeev airframe.\n"
        "No physical print, part fit, powered electronics or real flight has occurred.\n")
    archive=out.parent/(out.name+"-PRODUCT.zip")
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(out.rglob("*")):
            if p.is_file():z.write(p,p.relative_to(out.parent))
    return {"product":product,"airframe_stl":str(cad/"aerial_frame.stl"),
            "wheelbase_mm":a["wheelbase_mm"],"prop_mm":a["prop_diameter_mm"],
            "frame_mass_estimated_g":mass,"native_HS_CAD":True,
            "physical_drone_flown":False,"product_zip":str(archive),
            "zip_sha256":_sha(archive)}


def main():
    ap=argparse.ArgumentParser()
    grp=ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--request",type=Path)
    grp.add_argument("--prompt")
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--openscad",type=Path,required=True)
    ap.add_argument("--flight-source",type=Path)
    ap.add_argument("--no-flight",action="store_true")
    a=ap.parse_args()
    req=a.request or request_from_prompt(a.prompt)
    print(json.dumps(produce(req.resolve(),a.out.resolve(),
                             a.openscad.expanduser(),
                             a.flight_source.resolve() if a.flight_source else None,
                             simulate=not a.no_flight),indent=2))


if __name__=="__main__":main()
