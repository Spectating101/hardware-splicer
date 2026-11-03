"""HS-native whole-product delivery: a buildable 65 mm microdrone package.

The entrypoint, CAD project, robotic topology, component identity, BOM, source
provenance and output package belong to Hardware Splicer. Native Mecha-Splicer
generates a real four-hole alignment fixture as editable CSG; upstream OpenSCAD
renders it to STL. Existing community OpenSCAD defines the flying frame, and
upstream Crazyflie/PyBullet simulates flight. Never substitute simulation for
physical drone validation, safety authority, or a real motor controller.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

from .robot_topology import build_robot_topology

_REPO = Path(__file__).resolve().parents[2]
_MECHA = _REPO / "apps" / "mecha-splicer" / "src"
if str(_MECHA) not in sys.path:
    sys.path.insert(0, str(_MECHA))
from mecha_splicer.bundle import generate_bundle  # noqa: E402


def sha(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def write_json(path: Path, obj: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def _exact_mount_pattern(contract: dict[str, Any]) -> tuple[int, int]:
    raw = str(contract.get("flight_controller_mounting_hole_pattern_mm", ""))
    match = re.fullmatch(r"(\d+)x(\d+)", raw)
    if not match:
        raise ValueError("FC mount must be explicit integer NxN in mm, not inferred")
    x, y = int(match[1]), int(match[2])
    if x <= 0 or y <= 0:
        raise ValueError("invalid FC mount dimensions")
    return x, y


def source_binary_stl_info(path: Path) -> dict[str, Any]:
    """Read actual source STL geometry vertices, without declaring design fit."""
    bounds = [[float("inf")] * 3, [float("-inf")] * 3]
    with path.open("rb") as f:
        f.seek(80)
        tris = struct.unpack("<I", f.read(4))[0]
        if tris < 1 or path.stat().st_size != 84 + 50 * tris:
            raise ValueError(f"not a valid binary triangle STL: {path}")
        f.seek(84)
        for _ in range(tris):
            row = f.read(50)
            for off in (12, 24, 36):
                xyz = struct.unpack_from("<3f", row, off)
                for i, value in enumerate(xyz):
                    bounds[0][i] = min(bounds[0][i], value)
                    bounds[1][i] = max(bounds[1][i], value)
    return {
        "source": path.name,
        "triangles": tris,
        "dimensions_mm": [round(bounds[1][i]-bounds[0][i],3) for i in range(3)],
        "sha256": sha(path),
        "meaning": "actual vendor mesh dimensions, NOT a tested physical fit",
    }


def produce(*, build: Path, out: Path, airframe: Path, flight: Path,
            openscad: Path) -> dict[str, Any]:
    spec = json.loads(build.read_text())
    if spec.get("product_id") != "HS-WHOOP65-1S-V0":
        raise ValueError("this delivery adapter currently supports only the declared HS-WHOOP65-1S-V0")
    if spec.get("state") != "real_hardware_not_acquired_or_assembled":
        raise ValueError("input must not falsely claim field readiness")
    contract = spec["mechanical_electrical_contract"]
    pitch_x, pitch_y = _exact_mount_pattern(contract)
    if int(contract["frame_wheelbase_mm"]) != 65 or int(contract["propeller_diameter_mm"]) != 31:
        raise ValueError("unsupported print-frame geometry; requires a new sourced airframe")
    bom = {row["id"]: row for row in spec["bom"]}
    expected = {"frame","motors","fc_esc","props","battery","charger","radio"}
    if not expected.issubset(bom) or int(bom["motors"]["quantity"]) != 4:
        raise ValueError("complete 4-motor drone component set required")
    if any(row.get("status","") == "PHYSICALLY_VERIFIED" for row in spec["bom"]):
        raise ValueError("physical claims require independently supplied evidence")
    for required in (airframe / "stl" / "65mm_26x26_whoop.stl",
                     airframe / "stl" / "betafpv_c03_26x26_canopy.stl",
                     flight / "gym_pybullet_drones" / "envs" / "CtrlAviary.py"):
        if not required.is_file():
            raise FileNotFoundError(f"missing pinned source: {required}")
    if not openscad.is_file() and not shutil.which(str(openscad)):
        raise FileNotFoundError(f"OpenSCAD executable absent: {openscad}")
    out.mkdir(parents=True, exist_ok=True)

    # Native HS canonical cross-domain topology derives its four actuators and
    # firmware-channel placeholders from real declared parts, not magic strings.
    intake = {
        "project_name": spec["product_id"],
        "goal": spec["objective"],
        "constraints": {"rotor_count": 4},
        "available_parts": [
            {"name": bom["motors"]["component"], "type":"motor",
             "role":"actuator","quantity":4,
             "module_id":"RCINPOWER-0702-27000KV"},
            {"name": "Matrix 1S integrated IMU", "type":"imu",
             "role":"sensor","quantity":1,
             "module_id":"BETAFPV-MATRIX1S-INTEGRATED-GYRO"},
        ],
    }
    topo = build_robot_topology(intake, hinted_genre="aerial_robot")
    if len(topo.actuators) != 4 or topo.robot_genre.value != "aerial_robot":
        raise RuntimeError("native HS topology did not construct four rotor identities")
    topology_path = out / "HS_NATIVE" / "DRONE_ROBOT_TOPOLOGY.json"
    write_json(topology_path, topo.model_dump(mode="json"))

    # Native HS Mecha-Splicer, NOT Atech, produces editable parametric 4-hole
    # alignment fixture. Source parameters come from supplied product specs.
    mecha_spec = {
        "project_name": spec["product_id"] + "-fc-mounting-fixture",
        "mode": "prototype",
        "process": "fdm",
        "mounting_plate": {
            "name": "Matrix1S-26x26-bench-fixture",
            "w_mm": pitch_x + 12, "d_mm": pitch_y + 12,
            "t_mm": 2.4,"pitch_x_mm": pitch_x, "pitch_y_mm": pitch_y,
            "hole_d_mm": 1.8, "window_w_mm": min(pitch_x-9,17),
            "window_d_mm": min(pitch_y-9,17),
        },
        "notes":"Dry-fit fixture only. Do not install on flying aircraft.",
    }
    mech_dir = out / "HS_NATIVE" / "MECHA_SPLICER_FABRICATION"
    mech = generate_bundle(mecha_spec,out_dir=mech_dir)
    if mech["blockers"] or "mounting_plate.scad" not in mech["outputs"]:
        raise RuntimeError("native Mecha-Splicer refused to produce fixture")
    fixture_stl = mech_dir / "mounting_plate.stl"
    env = {**os.environ, "QT_QPA_PLATFORM":"offscreen"}
    process = subprocess.run(
        [str(openscad), "--export-format", "binstl", "-o", str(fixture_stl),str(mech_dir/"mounting_plate.scad")],
        capture_output=True,text=True,timeout=90,env=env,
    )
    if process.returncode or not fixture_stl.is_file() or fixture_stl.stat().st_size < 1000:
        raise RuntimeError(f"OpenSCAD failed to mesh HS-generated fixture: {process.stderr[-1300:]}")
    native_geometry=source_binary_stl_info(fixture_stl)

    # Source an actual printable whole airframe rather than fabricate another
    # approximation. Preserve original author's license and parametric source.
    air_dir = out / "SOURCE_REUSED_AIRFRAME"
    air_dir.mkdir(exist_ok=True)
    source_info = []
    for filename in ("65mm_26x26_whoop.stl","betafpv_c03_26x26_canopy.stl",
                     "betafpv_c03_camera_harness.stl"):
        source = airframe/"stl"/filename
        if not source.is_file():
            raise FileNotFoundError(source)
        copy = air_dir/filename
        shutil.copyfile(source,copy)
        source_info.append(source_binary_stl_info(copy))
    for filename in ("whoop.scad","65mm_26x26_whoop.scad","canopy.scad",
                     "betafpv_c03_26x26_canopy.scad"):
        if (airframe/filename).is_file():
            shutil.copyfile(airframe/filename,air_dir/filename)
    (air_dir/"CREDIT.txt").write_text(
        "Unmodified printable airframe/canopy/harness from\n"
        "https://github.com/vsergeev/3d-parametric-whoop\n"
        "License per original author: CC BY 4.0. These are not original HS CAD.\n"
    )

    with (out/"PARTS_TO_BUY.csv").open("w",newline="") as f:
        w=csv.writer(f)
        w.writerow(["component_id","quantity","part_or_hardware","status","supplier_reference"])
        for row in spec["bom"]:
            if int(row["quantity"]) > 0:
                w.writerow([row["id"],row["quantity"],row["component"],row["status"],row["source"]])
    shutil.copyfile(build,out/"HS_PRODUCT_SPEC.json")
    (out/"ASSEMBLE_AND_FLY.md").write_text(
        "# HS-WHOOP65-1S build\n\n"
        "1. Slice SOURCE_REUSED_AIRFRAME/65mm_26x26_whoop.stl using the original author's settings.\n"
        "2. Print HS_NATIVE/MECHA_SPLICER_FABRICATION/mounting_plate.stl as a BENCH FIT jig, not an aircraft part.\n"
        "3. Acquire exactly the supported parts in PARTS_TO_BUY.csv. Check motor/prop/connector and board revisions.\n"
        "4. Dry-fit FC and 4 motors and inspect 31mm prop clearance, unpowered and props OFF.\n"
        "5. Install 1S AIO + matched 0702 motors; use proper 1S LiHV charger, verify polarity.\n"
        "6. Betaflight configuration, receiver binding and motor direction check with props REMOVED.\n"
        "7. Verify radio failsafe and arm switch with props removed; document results.\n"
        "8. Only after physical gates, do a guarded indoor line-of-sight hover and controlled landing.\n\n"
        "**No actual print, radio configuration, electrical measurement or physical flight was performed here.**\n"
        "**The included Crazyflie simulation is not a calibrated digital twin of this brushless airframe.**\n"
    )

    # Whole-product simulation runs under HS. HS deliberately reuses the
    # upstream physical quad model (no duplicate fake dynamics). The controller
    # output is a real rendered 14-second PyBullet demo with motor telemetry.
    sim_dir=out/"FUNCTIONAL_SIMULATED_FLIGHT"
    sim_script=_REPO/"examples"/"drone_lab"/"flight_lab.py"
    if not sim_script.is_file():
        raise FileNotFoundError(sim_script)
    sim_env={**os.environ,"PYTHONPATH":str(flight)+os.pathsep+
             os.environ.get("PYTHONPATH","")}
    sim_process=subprocess.run(
        [sys.executable,str(sim_script),"--mode","demo","--out",str(sim_dir)],
        capture_output=True,text=True,timeout=120,env=sim_env,
    )
    if sim_process.returncode:
        raise RuntimeError(f"real upstream flight simulator failed: {sim_process.stderr[-1300:]}")
    sim=json.loads((sim_dir/"flight_summary.json").read_text())
    if sim["status"] != "simulation_completed" or not (sim["steps"]>100):
        raise RuntimeError("simulator failed to produce full telemetry")
    if not (sim_dir/"real_pybullet_drone_flight.gif").is_file():
        raise RuntimeError("real camera animation missing")
    sim["output_gif"]="FUNCTIONAL_SIMULATED_FLIGHT/real_pybullet_drone_flight.gif"
    sim["output_telemetry"]="FUNCTIONAL_SIMULATED_FLIGHT/flight_telemetry.csv"
    write_json(sim_dir/"flight_summary.json",sim)

    # A product result is files somebody can open/build, not a CI pass count.
    result={
        "product_id":spec["product_id"],
        "delivery":"software_drone_simulation_and_unbuilt_physical_fabrication_kit",
        "hs_native": {
            "robot_topology_engine":"hardware_splicer.robot_topology.build_robot_topology",
            "motors_identified":len(topo.actuators),
            "firmware_channel_placeholders":[a.firmware_channel_id for a in topo.actuators],
            "mechanical_engine":"mecha_splicer.bundle.generate_bundle",
            "mechanical_model": "HS_NATIVE/MECHA_SPLICER_FABRICATION/mounting_plate.scad",
            "manufacturable_fixture_stl":"HS_NATIVE/MECHA_SPLICER_FABRICATION/mounting_plate.stl",
            "native_fixture_geometry":native_geometry,
            "native_mechanical_findings":mech["dfm"],
        },
        "external_tools":{
            "geometry_mesh_renderer":"OpenSCAD (renders native HS SCAD)",
            "original_drone_frame":"vsergeev 3d-parametric-whoop (source reused)",
            "flight_dynamics":"learnsyslab/gym-pybullet-drones upstream Crazyflie + PID",
            "atech_atelier":"NOT USED by this HS-native executable",
        },
        "actual_fabrication_files":source_info,
        "functional_simulation":sim,
        "physical_parts_purchased":False,
        "physical_parts_printed":False,
        "physical_motor_connected":False,
        "physical_drone_flown":False,
        "production_authorized":False,
        "next_action":"Print source airframe and HS native fixture, acquire validated FC/motors, dry-fit and perform props-off checks.",
    }
    write_json(out/"HS_PRODUCT_OUTPUT.json",result)
    archive = out.parent/(out.name+"-DELIVERABLE.zip")
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for file in sorted(out.rglob("*")):
            if file.is_file():
                z.write(file, file.relative_to(out.parent))
    result["deliverable_zip"] = str(archive)
    result["deliverable_zip_sha256"] = sha(archive)
    return result


def main():
    parser=argparse.ArgumentParser(description="Run real HS engines to build a DIY microdrone product package.")
    parser.add_argument("--build",type=Path,default=_REPO/"examples/drone_lab/hs_whoop65_build.json")
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--airframe-source",type=Path,required=True)
    parser.add_argument("--flight-source",type=Path,required=True)
    parser.add_argument("--openscad-bin",type=Path,default=Path("openscad"))
    args=parser.parse_args()
    result=produce(build=args.build.resolve(),out=args.out.resolve(),
                   airframe=args.airframe_source.resolve(),
                   flight=args.flight_source.resolve(),
                   openscad=args.openscad_bin.expanduser())
    print(json.dumps({
        "product_id":result["product_id"],
        "hs_actuators":result["hs_native"]["motors_identified"],
        "hs_native_cad":result["hs_native"]["mechanical_model"],
        "hs_native_printable_fixture":result["hs_native"]["manufacturable_fixture_stl"],
        "source_frame":result["actual_fabrication_files"][0]["source"],
        "simulated_flight_seconds":result["functional_simulation"]["seconds_simulated"],
        "physical_drone_built":False,
        "deliverable":result["deliverable_zip"],
    },indent=2))


if __name__=="__main__":
    main()
