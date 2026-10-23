#!/usr/bin/env python3
"""HS manufacturing challenge 01: two-panel, 90-degree cardboard alignment connector.

External CAD engine reuse: CadQuery (OpenCascade). Units: millimetres.
Safety scope: low-load, non-safety-critical fit/alignment prototype only.
The acceptance report is a DIGITAL validation, not proof of printed fit, strength,
manufacturability by a particular printer, or building an equivalent full structure.

Usage: python generate.py [output_directory]
Dependencies: cadquery, trimesh, numpy
"""
from __future__ import annotations
import hashlib
import json
import math
import sys
from pathlib import Path

import cadquery as cq
import trimesh


PARAMETERS = {
    "stock_thickness_mm": 3.0,         # assumed; measure actual sheets
    "per_side_clearance_mm": 0.30,     # calibration value, not universal
    "wall_mm": 2.4,
    "arm_end_mm": 42.0,
    "insertion_stop_mm": 12.0,
    "height_mm": 24.0,
    "mount_hole_diameter_mm": 4.2,     # for an M4 clearance, confirm hardware
}
COUPON_CLEARANCES_MM = [0.15, 0.30, 0.45]


def box_bounds(xmin, xmax, ymin, ymax, zmin, zmax):
    """Make exact centred CadQuery box from mm edge coordinates."""
    return (cq.Workplane("XY")
            .box(xmax-xmin, ymax-ymin, zmax-zmin)
            .translate(((xmin+xmax)/2, (ymin+ymax)/2, (zmin+zmax)/2)))


def connector(p):
    t = p["stock_thickness_mm"]
    gap = t + 2*p["per_side_clearance_mm"]
    half_outer = gap/2 + p["wall_mm"]
    end = p["arm_end_mm"]
    stop = p["insertion_stop_mm"]
    height = p["height_mm"]
    if not 1.0 <= t <= 8.0 or not 0.10 <= p["per_side_clearance_mm"] <= 1:
        raise ValueError("Stock thickness/clearance out of bounded prototype range")
    if not p["wall_mm"] >= 2.0 or not stop >= 2*half_outer:
        raise ValueError("Wall/hub geometry too small")
    if not end > stop + 10 or not height >= 12:
        raise ValueError("Insufficient sleeve depth or height")

    # Two 90-degree sleeves meet at a monolithic solid hub.
    x_arm = box_bounds(-half_outer, end, -half_outer, half_outer, 0, height)
    y_arm = box_bounds(-half_outer, half_outer, -half_outer, end, 0, height)
    solid = x_arm.union(y_arm)
    # Through-height slots open at the distal end; flat underside for FDM.
    slot_x = box_bounds(stop, end+1, -gap/2, gap/2, -1, height+1)
    slot_y = box_bounds(-gap/2, gap/2, stop, end+1, -1, height+1)
    solid = solid.cut(slot_x).cut(slot_y)
    # Vertical central mounting hole avoids unsupported transverse printed holes.
    central_hole = (cq.Workplane("XY").circle(p["mount_hole_diameter_mm"]/2)
                    .extrude(height+2).translate((0,0,-1)))
    return solid.cut(central_hole), gap


def coupon(clearance_mm, p):
    stock = p["stock_thickness_mm"]
    gap = stock + 2*clearance_mm
    half = gap/2 + p["wall_mm"]
    # 8mm-high and only 20mm long; use to find actual card/printer fit.
    outer = box_bounds(0, 20, -half, half, 0, 8)
    channel = box_bounds(6, 21, -gap/2, gap/2, -1, 9)
    return outer.cut(channel)


def shape_stats(shape, file_path, *, label):
    shape_volume = float(shape.val().Volume())
    solids = shape.solids().vals()
    if len(solids) != 1 or not shape.val().isValid():
        raise AssertionError(f"{label}: invalid BREP or {len(solids)} solids")
    cq.exporters.export(shape, str(file_path), exportType="STL", tolerance=0.025)
    mesh = trimesh.load_mesh(str(file_path), process=True)
    if not mesh.is_watertight or not mesh.is_winding_consistent:
        raise AssertionError(f"{label}: mesh is not watertight/winding consistent")
    if abs(float(mesh.volume)-shape_volume)/shape_volume > 0.025:
        raise AssertionError(f"{label}: STL solid volume deviates over 2.5%")
    if not mesh.is_volume:
        raise AssertionError(f"{label}: mesh is not oriented solid volume")
    return {
        "stl": file_path.name, "sha256": hashlib.sha256(file_path.read_bytes()).hexdigest(),
        "triangles": len(mesh.faces), "watertight": bool(mesh.is_watertight),
        "cad_volume_mm3": round(shape_volume,3),
        "stl_volume_mm3": round(float(mesh.volume),3),
        "bounds_mm": [round(float(x),3) for x in mesh.extents],
    }


def run(output_dir):
    out=Path(output_dir)
    out.mkdir(parents=True,exist_ok=True)
    part,gap=connector(PARAMETERS)
    connector_stl=out/"right_angle_cardboard_joint.stl"
    info=shape_stats(part,connector_stl,label="joint")

    step=out/"right_angle_cardboard_joint.step"
    cq.exporters.export(part,str(step),exportType="STEP")
    imported=cq.importers.importStep(str(step))
    if len(imported.solids().vals()) != 1:
        raise AssertionError("STEP solid body count changed on re-import")
    if abs(float(imported.val().Volume())-part.val().Volume())>0.05:
        raise AssertionError("STEP BREP volume not preserved")

    # Independent exact CAD collision check with the intended inserted sheets.
    # They touch only at the limiting stop face; allow numerically tiny overlap.
    t=PARAMETERS["stock_thickness_mm"]
    h=PARAMETERS["height_mm"]
    x_sheet=box_bounds(PARAMETERS["insertion_stop_mm"]+0.05,
                       PARAMETERS["arm_end_mm"]-0.5,
                       -t/2,t/2,0,h)
    y_sheet=box_bounds(-t/2,t/2,
                       PARAMETERS["insertion_stop_mm"]+0.05,
                       PARAMETERS["arm_end_mm"]-0.5,0,h)
    x_intersection=float(part.intersect(x_sheet).val().Volume())
    y_intersection=float(part.intersect(y_sheet).val().Volume())
    if x_intersection>1e-5 or y_intersection>1e-5:
        raise AssertionError("Nominal board intersects printed connector")

    # Intentionally oversized stock must hit the walls (false-fit negative test).
    fat_t=gap+0.2
    oversized=box_bounds(PARAMETERS["insertion_stop_mm"]+0.05,
                         PARAMETERS["arm_end_mm"]-0.5,
                         -fat_t/2,fat_t/2,0,h)
    oversized_collision=float(part.intersect(oversized).val().Volume())
    if oversized_collision <= 1:
        raise AssertionError("Negative control failed to detect oversized sheet")

    coupons={}
    for clearance in COUPON_CLEARANCES_MM:
        key=f"{clearance:.2f}"
        fn=out/f"fit_coupon_{key}mm_per_side.stl"
        coupons[key]=shape_stats(coupon(clearance,PARAMETERS),fn,label=f"coupon {key}")

    modeled_volume=float(part.val().Volume())
    pla_nominal_density_g_cm3=1.24  # illustrative nominal density only
    solid_upper_mass=modeled_volume/1000*pla_nominal_density_g_cm3
    manifest={
        "challenge_id":"hs_mfg_01_cardboard_corner_joint",
        "source_engine":"CadQuery/OpenCascade",
        "authority":"digital_geometry_verified_only",
        "units":"mm supplied by parametric model; STL file itself is unitless",
        "parameters":PARAMETERS,
        "slot_width_mm":round(gap,3),
        "designed_clearance_each_side_mm":PARAMETERS["per_side_clearance_mm"],
        "connector":info,
        "step":{"name":step.name,"sha256":hashlib.sha256(step.read_bytes()).hexdigest(),
                "reimported_volume_mm3":round(float(imported.val().Volume()),3)},
        "collision_checks":{"nominal_x_sheet_overlap_mm3":round(x_intersection,6),
                            "nominal_y_sheet_overlap_mm3":round(y_intersection,6),
                            "oversize_sheet_overlap_mm3":round(oversized_collision,3),
                            "all_digital_checks_pass":True},
        "fit_coupons":coupons,
        "mass_estimate":{"solid_plastic_upper_bound_g_at_nominal_1_24_g_cm3":round(solid_upper_mass,2),
                         "note":"Not sliced filament mass, not actual waste, not equivalent structural strength"},
        "open_gates":["measure actual sheet thickness",
                      "print coupons on selected machine/material and measure gaps",
                      "test dry fit, retention and hand loading",
                      "check print with slicer for orientation/support/time/filament",
                      "independent physical inspection, revision and signoff"],
        "physical_fit_verified":False,
        "physical_strength_verified":False,
        "fabrication_tested":False,
        "relative_to_competitors_verified":False,
    }
    (out/"verification_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest,indent=2))
    return manifest


if __name__=="__main__":
    run(sys.argv[1] if len(sys.argv)>1 else Path(__file__).parent/"outputs")
