"""Printable four-wheel skid-steer rover chassis around cited parts, with the checks that decide whether it works.

    <python with cadquery> -m hardware_splicer.rover_chassis --params params.json --out DIR

Geometry from makers' drawings (each in SOURCES):

* Pololu 25D gearmotor (no encoder): gearbox and motor 25.0 / 24.4 mm diameter, gearbox 21 mm long at 34:1-47:1, motor
  30.8 mm, output shaft 4.0 mm x 12.5 mm, 80-100 g;
* Pololu 25D bracket pair #2676: L bracket, 52 x 21.7 mm base with 3.3 mm holes on a 6.35 mm pitch, shaft axis 14.5 mm
  from the base's mounting face;
* Hobby TT gearmotor (``motor: "tt"``, Adafruit 3777 diagram): body 70 x 22.44 x 18.6 mm, output shaft 5.4 mm (3.7 mm
  across the flats) with 8.7 mm out of one face and 9.3 mm out of the other, two 3.0 mm holes 17.6 mm apart through the
  gearbox 22.55 mm behind the shaft, 30.6 g. It bolts with two M3 screws to a printed rib under the plate;
* Pololu ball caster with 1/2 in ball #953 (``caster: "pololu_953"``): 13.5 mm tall without spacers, two 2.3 mm holes
  14.7 mm apart (M2), 9 g;
* Raspberry Pi Zero 2 W: 65 x 30 mm, M2.5 holes 3.5 mm in from each edge (58 x 23 mm);
* Raspberry Pi Camera Module 3: 25 x 23.86 mm board, 2.2 mm holes; field of view 66 x 41 degrees (standard lens).

Part masses not on those drawings (battery, electronics, wheels) are inputs, reported back as declared.

Checks: fits the print bed; lowest point (motor) above ground; wheels clear the plate; static tip-over angle forward,
back and sideways against the slope the drive was sized for; the chassis nose outside the camera's lower field of view.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import cadquery as cq

SOURCES = {
    "pololu_25d": "https://www.pololu.com/file/0J1829/pololu-25d-metal-gearmotors-rev-2-0.pdf (Rev 2.0, July 2026), page 2",
    "pololu_2676": "https://www.pololu.com/file/0J825/2676-bracket-dimensions.pdf (bkt04c, 21 Oct 2014)",
    "rpi_zero2w": "https://datasheets.raspberrypi.com/rpizero2/raspberry-pi-zero-2-w-mechanical-drawing.pdf",
    "rpi_cam3": "https://datasheets.raspberrypi.com/camera/camera-module-3-standard-mechanical-drawing.pdf",
    "pololu_2692": "https://www.pololu.com/file/0J959/2692-dimensions.pdf (cst05, 18 Sept 2015)",
    "adafruit_3777": "https://cdn-shop.adafruit.com/product-files/3777/3777_diagram.jpg (product page https://www.adafruit.com/product/3777)",
    "pololu_953": "https://www.pololu.com/file/0J1638/pololu-ball-caster-with-0-500in-ball.pdf (cst01c/d, 5 Feb 2019)",
}
TT = {"body_l": 70.0, "body_h": 22.44, "body_t": 18.6, "shaft_out": 8.7, "shaft_in": 9.3, "shaft_d": 5.4,
      "hole_d": 3.0, "hole_pitch": 17.6, "hole_behind_shaft": 22.55, "shaft_to_rear": 55.95, "shaft_to_front": 14.05,
      "mass_g": 30.6, "rib_t": 4.0}
CASTERS = {"pololu_2692": {"height": 29.0, "base_d": 34.0, "holes": "circle3", "hole_d": 3.2, "hole_circle_d": 14.0},
           "pololu_953": {"height": 13.5, "base_d": 20.3, "holes": "pair", "hole_d": 2.3, "hole_pitch": 14.7}}
CASTER = {"height": 29.0, "base_d": 34.0, "hole_d": 3.2, "hole_circle_d": 14.0}
MOTOR = {"gearbox_d": 25.0, "motor_d": 24.4, "gearbox_l_47": 21.0, "motor_l": 30.8, "rear_l": 1.5 + 4.2, "shaft_d": 4.0,
         "shaft_l": 12.5, "mass_g_max": 100.0}
BRACKET = {"base_l": 52.0, "base_w": 21.7, "base_t": 2.0, "face_h": 27.0, "axis_from_base": 14.5, "hole_d": 3.3,
           "hole_pitch": 6.35, "first_hole_from_face": 6.4}
PI = {"l": 65.0, "w": 30.0, "hole_in": 3.5, "hole_d": 2.75}
CAM = {"w": 25.0, "h": 23.862, "hole_d": 2.2, "hfov_deg": 66.0, "vfov_deg": 41.0}
DEFAULTS = {
    "wheel_d": 80.0, "wheel_w": 10.0, "plate_l": 180.0, "plate_w": 120.0, "plate_t": 4.0, "wheelbase": 120.0,
    "battery_mass_g": 150.0, "battery_box": [80.0, 60.0, 22.0], "electronics_mass_g": 60.0, "wheel_mass_g": 25.0,
    "mast_h": 60.0, "camera_tilt_down_deg": 15.0, "pla_density_g_cm3": 1.24, "infill_fraction": 0.6,
    "design_slope_deg": 15.0, "hub_offset": 2.0, "drive": "4wd", "caster_mass_g": 15.0, "motor": "pololu_25d",
    "caster": "pololu_2692", "bed": [220.0, 220.0, 250.0], "min_ground_clearance": 15.0, "min_wheel_gap": 3.0,
}


def axis_drop(p: dict) -> float:
    """How far below the plate's underside the wheel axis sits: the Pololu bracket's 14.5 mm, or half a TT motor's height."""
    return TT["body_h"] / 2 if p["motor"] == "tt" else BRACKET["axis_from_base"]


def build(p: dict) -> dict:
    w, l, t = p["plate_w"], p["plate_l"], p["plate_t"]
    plate = cq.Workplane("XY").box(l, w, t).translate((0, 0, t / 2)).edges("|Z").fillet(6)
    # Each bracket hangs under the plate with its upright face flush with the plate's side edge; its 52 mm base (and the
    # motor lying on it) runs inward across the chassis, and the shaft passes out through the face to the wheel.
    axle_x = [-p["wheelbase"] / 2, p["wheelbase"] / 2] if p["drive"] == "4wd" else [-p["wheelbase"] / 2]
    face_y = w / 2  # outer surface of each bracket's upright face
    if p["motor"] != "tt" and 2 * BRACKET["base_l"] > w:
        raise ValueError(f"plate_w {w} mm cannot take two {BRACKET['base_l']} mm brackets facing each other")
    tt = p["motor"] == "tt"
    if p["motor"] not in ("pololu_25d", "tt"):
        raise ValueError(f"motor must be pololu_25d or tt, not {p['motor']!r}")
    ribs = []
    if tt:
        # Each TT motor lies fore-aft under the plate, outer face flush with the plate edge, shaft at the axle, body
        # running forward; a printed rib on its inner face takes the two M3 bolts and passes the inner shaft stub.
        axis_z = -TT["body_h"] / 2
        for x in axle_x:
            for sy in (-1, 1):
                y_in = face_y - TT["body_t"]
                y0, y1 = sorted((sy * y_in, sy * (y_in - TT["rib_t"])))
                hole_x = x + TT["hole_behind_shaft"]
                rib = cq.Workplane("XY").box(TT["hole_behind_shaft"] + 12, TT["rib_t"], TT["body_h"] + 0.01).translate(
                    (x + TT["hole_behind_shaft"] / 2, (y0 + y1) / 2, -TT["body_h"] / 2 + 0.005))
                rib = rib.faces(">Y" if sy > 0 else "<Y").workplane(centerOption="CenterOfBoundBox").pushPoints(
                    [(sy * (hole_x - (x + TT["hole_behind_shaft"] / 2)), dz) for dz in (-TT["hole_pitch"] / 2, TT["hole_pitch"] / 2)]).hole(3.2)
                rib = rib.cut(cq.Workplane("XZ").circle(4.0).extrude(30, both=True).translate((x, 0, axis_z)))
                ribs.append(rib)
        if 2 * (TT["body_t"] + TT["rib_t"]) > w:
            raise ValueError(f"plate_w {w} mm cannot take two TT motors and their ribs")
    else:
        holes = []
        for x in axle_x:
            for sy in (-1, 1):
                for k in (1, 5):  # first and fifth hole of the bracket's row of seven
                    holes.append((x, sy * (face_y - BRACKET["first_hole_from_face"] - (k - 1) * BRACKET["hole_pitch"])))
        plate = plate.faces(">Z").workplane().pushPoints(holes).hole(BRACKET["hole_d"])
    # Pi Zero 2 W standoff holes (M2.5) centred behind the mast; battery strap slots.
    pi_c = (-10.0, 0.0)
    pi_holes = [(pi_c[0] + sx * (PI["l"] / 2 - PI["hole_in"]), pi_c[1] + sy * (PI["w"] / 2 - PI["hole_in"])) for sx in (-1, 1) for sy in (-1, 1)]
    plate = plate.faces(">Z").workplane().pushPoints(pi_holes).hole(PI["hole_d"])
    plate = plate.faces(">Z").workplane().pushPoints([(-l / 2 + 55, sy * 34) for sy in (-1, 1)]).slot2D(20, 4, 0).cutThruAll()
    # Camera mast at the front: an upright with the Camera Module 3 hole pattern, tilted down.
    mast_x = l / 2 - 12
    mast = cq.Workplane("XY").box(6, CAM["w"] + 8, p["mast_h"]).translate((mast_x, 0, t + p["mast_h"] / 2))
    cam_z = t + p["mast_h"] - CAM["h"] / 2 - 2
    mast = mast.faces(">X").workplane(centerOption="CenterOfBoundBox").pushPoints(
        [(sy * 10.5, cam_z - (t + p["mast_h"] / 2) + dz) for sy in (-1, 1) for dz in (-6.25, 6.25)]).hole(CAM["hole_d"])
    body = plate.union(mast)
    for rib in ribs:
        body = body.union(rib)
    caster_x = None
    boss_t = 0.0
    if p["drive"] == "2wd_caster":
        # Pololu #2692 at the front: three 3.2 mm holes on a 14 mm circle, on a printed boss that makes up the difference
        # between the plate's underside height (wheel radius - 14.5 mm bracket drop) and the caster's 29 mm.
        caster = CASTERS[p["caster"]]
        caster_x = p["wheelbase"] / 2
        boss_t = (p["wheel_d"] / 2 - axis_drop(p)) - caster["height"]
        if caster["holes"] == "circle3":
            pts = [(caster_x + caster["hole_circle_d"] / 2 * math.cos(math.radians(90 + 120 * k)),
                    caster["hole_circle_d"] / 2 * math.sin(math.radians(90 + 120 * k))) for k in range(3)]
        else:
            pts = [(caster_x, sy * caster["hole_pitch"] / 2) for sy in (-1, 1)]
        if boss_t > 0.2:
            boss = cq.Workplane("XY").circle(caster["base_d"] / 2 + 2).extrude(-boss_t).translate((caster_x, 0, 0))
            body = body.union(boss)
        body = body.faces(">Z").workplane().pushPoints(pts).hole(caster["hole_d"])
    return {"body": body, "axle_x": axle_x, "face_y": face_y, "mast_x": mast_x, "cam_z": cam_z, "caster_x": caster_x, "boss_t": boss_t}


def check(p: dict, g: dict) -> dict:
    body = g["body"].val()
    bb = body.BoundingBox()
    vol_cm3 = body.Volume() / 1000.0
    printed_g = vol_cm3 * p["pla_density_g_cm3"] * p["infill_fraction"]
    r = p["wheel_d"] / 2
    tt = p["motor"] == "tt"
    plate_bottom_z = r - axis_drop(p)  # the shaft axis hangs this far below the plate
    lowest_motor = r - (TT["body_h"] / 2 if tt else MOTOR["gearbox_d"] / 2)
    ground_clearance = min(plate_bottom_z, lowest_motor)
    # Wheels sit outside the bracket face, spaced by the hub (declared); the 12.5 mm shaft must reach through the wheel.
    wheel_inner_y = g["face_y"] + p["hub_offset"]
    shaft_reach = (TT["shaft_out"] - p["hub_offset"] - p["wheel_w"]) if tt else (MOTOR["shaft_l"] - BRACKET["base_t"] - p["hub_offset"] - p["wheel_w"])
    wheel_gap = wheel_inner_y - p["plate_w"] / 2
    track = 2 * (wheel_inner_y + p["wheel_w"] / 2)
    # Centre of gravity: printed body, four motors on their axes, battery on top behind the Pi, electronics, wheels.
    masses = [(printed_g, plate_bottom_z + bb.zmax / 2, 0.0)]
    motor_g = TT["mass_g"] if tt else MOTOR["mass_g_max"]
    # two motors per driven axle; a TT motor's mass sits at its body centre, ahead of the shaft
    motor_dx = (TT["shaft_to_rear"] - TT["shaft_to_front"]) / 2 if tt else 0.0
    masses += [(motor_g, r, x + motor_dx) for x in g["axle_x"] for _ in (0, 1)]
    masses += [(p["wheel_mass_g"], r, x) for x in g["axle_x"] for _ in (0, 1)]
    masses += [(p["battery_mass_g"], plate_bottom_z + p["plate_t"] + p["battery_box"][2] / 2, -p["plate_l"] / 2 + 55)]
    masses += [(p["electronics_mass_g"], plate_bottom_z + p["plate_t"] + 8, -10.0)]
    total = sum(m for m, _, _ in masses)
    cg_z = sum(m * z for m, z, _ in masses) / total
    cg_x = sum(m * x for m, _, x in masses) / total
    if g["caster_x"] is not None:
        masses.append((p["caster_mass_g"], CASTERS[p["caster"]]["height"] / 2, g["caster_x"]))
        total = sum(m for m, _, _ in masses)
        cg_z = sum(m * z for m, z, _ in masses) / total
        cg_x = sum(m * x for m, _, x in masses) / total
    # Support polygon from the ground contacts; the static tip angle over each edge is atan(distance from the centre of
    # gravity's ground projection to the edge / CG height).
    half = track / 2
    if g["caster_x"] is None:
        support = [(g["axle_x"][0], -half), (g["axle_x"][1], -half), (g["axle_x"][1], half), (g["axle_x"][0], half)]
    else:
        support = [(g["axle_x"][0], -half), (g["caster_x"], 0.0), (g["axle_x"][0], half)]
    edges = {}
    for (ax, ay), (bx, by) in zip(support, support[1:] + support[:1]):
        dist = abs((bx - ax) * (ay - 0.0) - (ax - cg_x) * (by - ay)) / math.hypot(bx - ax, by - ay)
        side = "backward" if ax == bx and ax < cg_x else ("forward" if ax == bx else "sideways")
        edges[side] = min(edges.get(side, 1e9), math.degrees(math.atan2(dist, cg_z)))
    if g["caster_x"] is not None:  # the two edges to the caster are the forward-sideways tipping lines
        edges["forward"] = edges.pop("sideways")
        edges["sideways"] = edges["forward"]
    tip_fwd, tip_back, tip_side = edges.get("forward"), edges.get("backward"), edges.get("sideways")
    # Camera: lower edge of the vertical field of view must clear the chassis nose.
    cam_z_abs = plate_bottom_z + g["cam_z"]
    lower_ray = math.radians(p["camera_tilt_down_deg"] + CAM["vfov_deg"] / 2)
    nose_dx = p["plate_l"] / 2 - g["mast_x"]
    nose_dz = cam_z_abs - (plate_bottom_z + p["plate_t"])
    ray_drop_at_nose = math.tan(lower_ray) * nose_dx
    nose_in_view = ray_drop_at_nose > nose_dz  # the nose is above the lower edge-ray, so inside the picture
    ground_seen_at_mm = (cam_z_abs / math.tan(lower_ray)) if lower_ray > 0 else None
    bed = p["bed"]
    fits = (bb.xlen <= bed[0] and bb.ylen <= bed[1] and bb.zlen <= bed[2]) or (bb.ylen <= bed[0] and bb.xlen <= bed[1] and bb.zlen <= bed[2])
    problems = []
    if not fits:
        problems.append(f"printed part {bb.xlen:.0f} x {bb.ylen:.0f} x {bb.zlen:.0f} mm does not fit the {bed[0]:.0f} x {bed[1]:.0f} bed")
    if ground_clearance < p["min_ground_clearance"]:
        problems.append(f"ground clearance {ground_clearance:.1f} mm < {p['min_ground_clearance']} mm")
    if wheel_gap < p["min_wheel_gap"]:
        problems.append(f"wheel to plate gap {wheel_gap:.1f} mm < {p['min_wheel_gap']} mm")
    for name, ang in (("forward", tip_fwd), ("backward", tip_back), ("sideways", tip_side)):
        if ang < p["design_slope_deg"]:
            problems.append(f"tips {name} at {ang:.1f} deg, below the {p['design_slope_deg']} deg design slope")
    if g["caster_x"] is not None and g["boss_t"] < -0.2:
        problems.append(f"the {CASTERS[p['caster']]['height']:g} mm caster is {-g['boss_t']:.1f} mm taller than the plate's height above ground: the rover rocks on it")
    if tt and p["wheel_d"] / 2 < TT["body_h"] / 2 + p["min_ground_clearance"]:
        pass  # covered by the ground clearance check
    if not tt and shaft_reach < -p["wheel_w"] / 2:
        problems.append(f"the 12.5 mm shaft does not reach half way through the wheel ({shaft_reach:.1f} mm): use a narrower wheel or smaller hub offset")
    if nose_in_view:
        problems.append("chassis nose inside the camera's lower field of view: reduce tilt, raise the mast or shorten the nose")
    return {
        "printed_part_mm": [round(bb.xlen, 1), round(bb.ylen, 1), round(bb.zlen, 1)], "fits_bed": fits,
        "printed_mass_g": round(printed_g, 1), "all_up_mass_g": round(total, 1),
        "mass_basis": {"motors": "TT 30.6 g each (Adafruit, cited)" if tt else "Pololu max 100 g each (cited)", "battery_g": f"{p['battery_mass_g']} declared",
                       "electronics_g": f"{p['electronics_mass_g']} declared", "wheels_g": f"{p['wheel_mass_g']} each declared", "caster_g": f"{p['caster_mass_g']} declared" if g["caster_x"] is not None else None,
                       "print": f"PLA {p['pla_density_g_cm3']} g/cm3 x {p['infill_fraction']} effective fill (assumed)"},
        "drive": p["drive"], "motor": p["motor"],
        "wheel_fit": ("TT wheel pressed on the motor's own D shaft (made for it); the 8.7 mm stub's reach is reported, not checked"
                      if tt else "wheel on a hub on the 4 mm shaft"),
        "caster_boss_mm": round(g["boss_t"], 1) if g["caster_x"] is not None else None,
        "ground_clearance_mm": round(ground_clearance, 1), "wheel_to_plate_gap_mm": round(wheel_gap, 1), "shaft_reach_beyond_wheel_mm": round(shaft_reach, 1), "track_mm": round(track, 1),
        "cg_mm": {"x": round(cg_x, 1), "z": round(cg_z, 1)},
        "static_tip_angle_deg": {"forward": round(tip_fwd, 1), "backward": round(tip_back, 1), "sideways": round(tip_side, 1)},
        "camera": {"height_mm": round(cam_z_abs, 1), "tilt_down_deg": p["camera_tilt_down_deg"], "nose_in_view": nose_in_view,
                   "nearest_ground_seen_mm_ahead": round(ground_seen_at_mm, 1) if ground_seen_at_mm else None},
        "problems": problems,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--params", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    given = json.loads(a.params.read_text()) if a.params and a.params.is_file() else {}
    unknown = sorted(set(given) - set(DEFAULTS))
    p = {**DEFAULTS, **{k: v for k, v in given.items() if k in DEFAULTS}}
    g = build(p)
    res = check(p, g)
    a.out.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(g["body"], str(a.out / "rover_chassis.step"))
    cq.exporters.export(g["body"], str(a.out / "rover_chassis.stl"))
    res.update({"params": p, "params_declared": sorted(given), "unknown_params_ignored": unknown,
                "files": ["rover_chassis.step", "rover_chassis.stl"], "sources": list(SOURCES.values()),
                "summary": (f"{res['all_up_mass_g']:.0f} g, clearance {res['ground_clearance_mm']} mm, tips at "
                            f"{min(res['static_tip_angle_deg'].values()):.0f} deg, {len(res['problems'])} problems"),
                "claim_boundary": ("CAD and static calculations only. Print strength, traction, wheel slip, battery life and the "
                                   "camera image need a printed, driven rover.")})
    if unknown:
        res["problems"].append(f"unknown parameters ignored: {unknown}")
    (a.out / "chassis_checks.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
