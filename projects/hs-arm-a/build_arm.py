#!/usr/bin/env python3
"""HS-ARM-A: a 5-axis desktop arm with a gripper, built around DYNAMIXEL X430 servos. Generates every printed part,
the assembly, a URDF with CAD-derived masses, and the checks that close the design loop.

    .cache/hardware-splicer/digital-native-venv/bin/python projects/hs-arm-a/build_arm.py [--out projects/hs-arm-a]
    .cache/hardware-splicer/digital-native-venv/bin/python projects/hs-arm-a/build_arm.py --servo sts3215 --out projects/hs-arm-a/rev-b

Rev B (``--servo sts3215``) is the same arm on Feetech STS3215 servos, the SO-ARM100/101's actuator: 55 g each and about
US$14 against US$270 for an XM430. Its geometry is measured from SO-ARM100's STS3215_03a.step (Apache-2.0, commit
141aea7b): body 45.4 x 24.8 mm and 35.4 mm along the horn axis (Feetech lists 45.2*24.7*35), horn axis 12.5 mm from the
body centre, horn radius 10.0 mm and 1.0 mm proud of the body envelope, rear idler disc inside the envelope.

Geometry basis
* Servo body 46.5 x 28.5 x 34 mm (ROBOTIS e-manual, XM430-W350 and XL430-W250 "Dimensions (W x H x D)").
* Horn: diameter 19.5 mm, 6.4 mm proud of the body, axis 12 mm from the body centre along its 46.5 mm length. Measured
  from the XM430 body in ROBOTIS's OpenMANIPULATOR-X model (link1.stl, Apache-2.0), whose joint1 origin also sits 12 mm
  off the body centre.
* Idler horn on the back face: 4 mm thick, same diameter (assumed; ROBOTIS's hinge frames need an idler horn per its
  e-manual, but its drawing could not be downloaded).
* Rev A: horn bolt circle and servo side-screw positions are NOT modelled; drill them from the real horn. Rev B cuts
  them: horn screws on the STS3215's measured 9.8 mm square (with a head recess reachable from the servo pocket) and body
  screws into its 1.5 mm pilots, with SO-101's clearances (see FAMILIES["sts3215"]["holes"]).

Everything printed is PLA. Its mass uses a density of 1.24 g/cm3 and a 60 % effective fill (both assumed). Servo masses
are the cited ones.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import cadquery as cq
import numpy as np

HERE = Path(__file__).resolve().parent

# --- cited and measured servo geometry (mm) -------------------------------------------------------------------------
FAMILIES = {
    "x430": {"body": (46.5, 28.5, 34.0), "horn_off": 12.0, "horn_r": 9.75, "horn_h": 6.4, "idler_h": 4.0,
             "joints": {"base_yaw": "XM430-W350-T", "shoulder": "XM430-W350-T", "elbow": "XM430-W350-T",
                        "wrist_pitch": "XL430-W250-T", "wrist_roll": "XL430-W250-T", "gripper": "XL430-W250-T"},
             "name": "hs_arm_a", "yaw_servo": "XM430-W350-T"},
    "sts3215": {"body": (45.4, 24.8, 35.4), "horn_off": 12.5, "horn_r": 10.0, "horn_h": 1.0, "idler_h": 0.0,
                "joints": {j: "STS3215-12V" for j in ("base_yaw", "shoulder", "elbow", "wrist_pitch", "wrist_roll", "gripper")},
                "name": "hs_arm_a_rev_b", "yaw_servo": "STS3215-12V",
                # Measured from STS3215_03a.step (servo frame: horn axis at the origin, body toward -x). The horn and the rear
                # disc each carry four 2.5 mm holes on a 9.8 mm square about the axis; each body face has 1.5 mm pilot holes
                # (M2 self-tapping) at the x given, y +-10.2. Clearances are the ones SO-101's printed Upper_arm_SO101.step
                # cuts for the same servo: 3.0 mm horn holes on the same square, a 3.2 mm centre bore, 2.0 mm body holes.
                "holes": {"horn_half": 4.9, "horn_d": 3.0, "centre_d": 3.2, "horn_head_d": 6.0, "body_d": 2.0, "body_head_d": 4.5,
                          "pilot_y": 10.2, "pilot_x": {"horn_face": (-29.0, -8.3), "back_face": (-32.8, -8.3)}}},
}
# The leader (teleoperation input) is rev B's arm moved by hand: same geometry, so joint angles map one to one, with
# low-ratio STS3215s a hand can backdrive (LeRobot's SO-101 leader table, Apache-2.0) and a handle and trigger in place of
# the gripper jaw. It runs with torque off, so the powered torque rule does not apply to it.
FAMILIES["sts3215_leader"] = {**FAMILIES["sts3215"], "name": "hs_arm_a_rev_b_leader", "yaw_servo": "STS3215-C044", "leader": True,
                              "joints": {"base_yaw": "STS3215-C044", "shoulder": "STS3215-C001", "elbow": "STS3215-C044",
                                         "wrist_pitch": "STS3215-C046", "wrist_roll": "STS3215-C046", "gripper": "STS3215-C046"}}
BODY_L, BODY_W, BODY_D = FAMILIES["x430"]["body"]
HORN_OFF = 12.0          # horn axis from body centre, along the length
HORN_R, HORN_H = 9.75, 6.4
IDLER_H = 4.0            # assumed
SERVOS = {"XM430-W350-T": {"mass_kg": 0.082, "stall_nm_12v": 4.1, "stall_a_12v": 2.3, "radial_load_n_at_10mm": 40.0},
          "XL430-W250-T": {"mass_kg": 0.0572, "stall_nm_12v": 1.5, "stall_a_12v": 1.4, "radial_load_n_at_10mm": None},
          # Feetech listing ST-3215-C018 (55 g, 30 kg.cm at 12 V) and Waveshare's wiki (2.7 A locked-rotor); no side-load rating
          "STS3215-12V": {"mass_kg": 0.055, "stall_nm_12v": 2.942, "stall_a_12v": 2.7, "radial_load_n_at_10mm": None},
          # Leader variants (7.4 V body, same 55 g): SO-ARM100 README gives 16.5 kg.cm at 6 V for the 1/345 (C001); the
          # 1/191 (C044) and 1/147 (C046) publish no torque here. Stall currents unknown.
          "STS3215-C001": {"mass_kg": 0.055, "stall_nm_12v": 16.5 * 0.0980665, "stall_a_12v": None, "radial_load_n_at_10mm": None},
          "STS3215-C044": {"mass_kg": 0.055, "stall_nm_12v": None, "stall_a_12v": None, "radial_load_n_at_10mm": None},
          "STS3215-C046": {"mass_kg": 0.055, "stall_nm_12v": None, "stall_a_12v": None, "radial_load_n_at_10mm": None}}
NAME = "hs_arm_a"
YAW_SERVO = "XM430-W350-T"

# --- design parameters ----------------------------------------------------------------------------------------------
P = {
    "upper_arm_mm": 110.0,     # shoulder axis to elbow axis
    "forearm_mm": 100.0,       # elbow axis to wrist-pitch axis
    "wrist_mm": 72.0,          # wrist-pitch axis to wrist-roll horn face; wrist_link needs at least 68.3
    "wall": 3.0, "plate": 4.0, "clear": 0.3, "hub_r": 20.0,
    "ring_r": 44.0, "payload_kg": 0.15, "safety_factor": 1.5, "max_stall_share": 0.5,
    "pla_g_cm3": 1.24, "fill": 0.6, "bed_mm": (220.0, 220.0, 250.0),
}
JOINT_SERVO = dict(FAMILIES["x430"]["joints"])

C = P["clear"]


def use_servo(family: str) -> None:
    """Set the servo geometry every part is built around (module globals, so the part functions read one source)."""
    global BODY_L, BODY_W, BODY_D, HORN_OFF, HORN_R, HORN_H, IDLER_H, JOINT_SERVO, NAME, YAW_SERVO
    global HALF_IN, HALF_OUT, CHEEK_POS, CHEEK_NEG, HORN_GAP, IDLER_GAP, HOLES, LEADER
    f = FAMILIES[family]
    LEADER = bool(f.get("leader"))
    HOLES = f.get("holes")
    BODY_L, BODY_W, BODY_D = f["body"]
    HORN_OFF, HORN_R, HORN_H, IDLER_H = f["horn_off"], f["horn_r"], f["horn_h"], f["idler_h"]
    JOINT_SERVO, NAME, YAW_SERVO = dict(f["joints"]), f["name"], f["yaw_servo"]
    HALF_IN = BODY_D / 2 + C                 # cradle inner half-width across the body depth
    HALF_OUT = HALF_IN + P["wall"]
    # A cheek plate must clear the next link's cradle wall (rev A's X430 horn and idler give 0.7 mm). A servo whose horn
    # sits nearly flush (STS3215, 1.0 mm) needs the cheek held out by a boss of horn radius, printed with the cheek.
    HORN_GAP = max(HORN_H, round(HALF_OUT + 0.7 - BODY_D / 2, 2))
    IDLER_GAP = max(IDLER_H, round(HALF_OUT + 0.7 - BODY_D / 2, 2))
    CHEEK_POS = (BODY_D / 2 + HORN_GAP, BODY_D / 2 + HORN_GAP + P["plate"])          # horn-side cheek, along the axis
    CHEEK_NEG = (-(BODY_D / 2 + IDLER_GAP + P["plate"]), -(BODY_D / 2 + IDLER_GAP))  # idler-side cheek


HOLES = None
LEADER = False
FASTENER_CUTS = None
use_servo("x430")


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0)).val()


def cyl(r, axis, a0, a1, centre):
    """Cylinder of radius r along a world axis ('x','y','z') from a0 to a1 (axis coordinate), through centre."""
    d = {"x": cq.Vector(1, 0, 0), "y": cq.Vector(0, 1, 0), "z": cq.Vector(0, 0, 1)}[axis]
    base = cq.Vector(*centre)
    base = base + d * (a0 - base.dot(d))
    return cq.Solid.makeCylinder(r, a1 - a0, base, d)


def frame(axis, body_dir):
    """Columns: local x, y, z in world. Local z = axis; the body centre lies along -local x."""
    z = np.array(axis, float)
    x = -np.array(body_dir, float)
    return np.column_stack([x, np.cross(z, x), z])


def place(shape, rot, origin):
    from OCP.gp import gp_Trsf
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    r = [[float(v) for v in row] for row in rot]
    trsf = gp_Trsf()
    trsf.SetValues(r[0][0], r[0][1], r[0][2], float(origin[0]), r[1][0], r[1][1], r[1][2], float(origin[1]),
                   r[2][0], r[2][1], r[2][2], float(origin[2]))
    return cq.Shape.cast(BRepBuilderAPI_Transform(shape.wrapped, trsf, True).Shape())


def servo(point, axis, body_dir):
    """Servo envelope with the axis through `point`, the body centred on point along the axis."""
    body = box(-HORN_OFF - BODY_L / 2, -HORN_OFF + BODY_L / 2, -BODY_W / 2, BODY_W / 2, -BODY_D / 2, BODY_D / 2)
    extras = [cyl(HORN_R, "z", BODY_D / 2, BODY_D / 2 + HORN_H, (0, 0, 0))]
    if IDLER_H > 0:  # an idler inside the body envelope (STS3215) adds nothing
        extras.append(cyl(HORN_R, "z", -BODY_D / 2 - IDLER_H, -BODY_D / 2, (0, 0, 0)))
    solid = body.fuse(*extras).clean()
    return place(solid, frame(axis, body_dir), point)


def fastener_tools(placement, idler_cheek, body_faces=("horn_face", "back_face")):
    """Hole solids for one servo, in world space: horn screws through the driven part's plate (head recess beyond it),
    the rear-disc screws when the driven part has an idler-side cheek, and body screws through the holder's walls
    (rear half of the body only: the front half is left free for the next link's cheeks)."""
    point, axis, body_dir = placement
    h = HOLES
    horn_face = BODY_D / 2 + HORN_H
    plate_out = BODY_D / 2 + HORN_GAP + P["plate"]           # outer face of a horn-side cheek
    recess = plate_out - 1.8                                  # head recess 1.8 mm deep, open beyond the plate
    tools = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            c = (sx * h["horn_half"], sy * h["horn_half"], 0)
            tools.append(("horn", cyl(h["horn_d"] / 2, "z", horn_face - 0.01, plate_out + 0.5, c)))
            tools.append(("horn", cyl(h["horn_head_d"] / 2, "z", recess, recess + 40.0, c)))
            if idler_cheek:
                tools.append(("idler", cyl(h["horn_d"] / 2, "z", CHEEK_NEG[0] - 0.5, -BODY_D / 2 + 0.01, c)))
                tools.append(("idler", cyl(h["horn_head_d"] / 2, "z", CHEEK_NEG[0] - 0.5, CHEEK_NEG[0] + 1.8, c)))
    tools.append(("horn", cyl(h["centre_d"] / 2, "z", horn_face - 0.01, plate_out + 0.5, (0, 0, 0))))
    for face, sign in (("horn_face", 1), ("back_face", -1)):
        if face not in body_faces:
            continue
        for x in h["pilot_x"][face]:
            if x > -HORN_OFF:
                continue
            for y in (-h["pilot_y"], h["pilot_y"]):
                a0, a1 = BODY_D / 2 - 0.01, BODY_D / 2 + 8.0
                tools.append(("body", cyl(h["body_d"] / 2, "z", *sorted((sign * a0, sign * a1)), (x, y, 0))))
                b0, b1 = BODY_D / 2 + 4.0, BODY_D / 2 + 9.0   # counterbore where the holder is thicker than a cradle wall
                tools.append(("body", cyl(h["body_head_d"] / 2, "z", *sorted((sign * b0, sign * b1)), (x, y, 0))))
    rot = frame(axis, body_dir)
    return [(kind, place(t, rot, point)) for kind, t in tools]


def cut_fasteners(printed, placements, idler_cheeks, body_faces):
    """Cut every servo's fastener holes from the printed parts; report which part each set of holes went into."""
    cuts = {}
    for name, placement in placements.items():
        for kind, tool in fastener_tools(placement, name in idler_cheeks, body_faces[name]):
            for part, shape in printed.items():
                after = shape.cut(tool)
                removed = shape.Volume() - after.Volume()
                if removed > 1e-3:
                    printed[part] = after
                    key = f"{name}:{kind}"
                    cuts.setdefault(key, {}).setdefault(part, 0.0)
                    cuts[key][part] += removed
    return {k: {p: round(v, 1) for p, v in d.items()} for k, d in sorted(cuts.items())}


def union(*shapes):
    out = shapes[0]
    for s in shapes[1:]:
        out = out.fuse(s)
    return out.clean()


# --- parts ---------------------------------------------------------------------------------------------------------
def cheeks_y(px, pz, x_end):
    """Two cheek plates around a +Y pitch axis at (px, *, pz), running forward to x_end."""
    r = P["hub_r"]
    parts = []
    for y0, y1 in (CHEEK_POS, CHEEK_NEG):
        parts += [cyl(r, "y", y0, y1, (px, 0, pz)), box(px, x_end, y0, y1, pz - r, pz + r)]
    if HORN_GAP > HORN_H:   # boss from the horn face out to the cheek
        parts.append(cyl(HORN_R, "y", BODY_D / 2 + HORN_H, CHEEK_POS[0] + 0.01, (px, 0, pz)))
    if IDLER_GAP > IDLER_H:  # boss from the idler face out to the cheek
        parts.append(cyl(HORN_R, "y", CHEEK_NEG[1] - 0.01, -(BODY_D / 2 + IDLER_H), (px, 0, pz)))
    return parts


def tube_x(x0, x1, pz, half_z=16.0):
    y0, y1 = CHEEK_NEG[0], CHEEK_POS[1]
    outer = box(x0, x1, y0, y1, pz - half_z, pz + half_z)
    w = P["wall"]
    inner = box(x0 + w, x1 - w, y0 + w, y1 - w, pz - half_z + w, pz + half_z - w)
    return outer.cut(inner)


def cradle_x(axis_x, pz, x_back_wall):
    """Holds a +Y-axis servo whose body runs back (-X) from its axis; the servo slides in from the front."""
    back = axis_x - HORN_OFF - BODY_L / 2 - C
    front = axis_x - HORN_OFF  # grip the rear half of the body, keep the front free for the next link's cheeks
    w = P["wall"]
    hz = BODY_W / 2 + C
    outer = box(x_back_wall, front, -HALF_OUT, HALF_OUT, pz - hz - w, pz + hz + w)
    pocket = box(back, front + 1, -HALF_IN, HALF_IN, pz - hz, pz + hz)
    return outer.cut(pocket)


def pitch_link(p0, length):
    """Driven by the servo at p0 (+Y axis), holds the next +Y servo at p0 + (length, 0, 0)."""
    px, _, pz = p0
    nx = px + length
    back_wall = nx - HORN_OFF - BODY_L / 2 - C - P["wall"]
    start = px + P["hub_r"] + 6
    if back_wall <= start + 5:
        raise ValueError(f"link of {length} mm is too short for its cheeks and cradle")
    return union(*cheeks_y(px, pz, start + P["wall"]), tube_x(start, back_wall + P["wall"], pz),
                 cradle_x(nx, pz, back_wall))


def wrist_link(p3, p4):
    """Driven by wrist pitch at p3, holds the wrist-roll servo (axis +X, body below) with its horn face at p4."""
    px, _, pz = p3
    w, c = P["wall"], C
    start = px + P["hub_r"] + 6
    rear = p4[0] - BODY_D - c          # roll body back face
    if rear - w <= start + 5:
        raise ValueError("wrist too short for the roll servo")
    hz_lo, hz_hi = p4[2] - HORN_OFF - BODY_L / 2 - c, p4[2] - HORN_OFF + BODY_L / 2 + c
    hy = BODY_W / 2 + c
    outer = box(rear - w, p4[0] - 14, -hy - w, hy + w, hz_lo - w, hz_hi + w)
    pocket = box(rear, p4[0] + 1, -hy, hy, hz_lo, hz_hi)
    return union(*cheeks_y(px, pz, start + w), tube_x(start, rear, pz), outer.cut(pocket))


def gripper_parts(p4):
    """Plate on the roll horn, a bracket for the gripper servo (+Y axis, body back toward the wrist), a fixed jaw.
    Returns (base solid, gripper axis point, tool point, moving jaw solid at closed pose)."""
    w, c = P["wall"], C
    face = p4[0] + HORN_H
    plate = cyl(P["hub_r"], "x", face, face + P["plate"], p4)
    g = (face + P["plate"] + BODY_L / 2 + HORN_OFF + c + w, 0.0, p4[2] + 22.0)
    gx, _, gz = g
    back = gx - HORN_OFF - BODY_L / 2 - c
    hz = BODY_W / 2 + c
    bracket = box(face + P["plate"] - 0.01, gx - HORN_OFF, -HALF_OUT, HALF_OUT, gz - hz - w, gz + hz + w).cut(
        box(back, gx - HORN_OFF + 1, -HALF_IN, HALF_IN, gz - hz, gz + hz))
    web = box(face, back, -HALF_OUT, HALF_OUT, p4[2] - 20, gz - hz)        # ties the plate to the bracket underside
    tool = (gx + 45.0, 0.0, p4[2])
    if LEADER:
        # A handle hangs below the bracket where the fixed jaw was, and the gripper servo turns a short trigger under the
        # index finger instead of a jaw (SO-101's leader does the same with Handle_SO101 and Trigger_SO101).
        hx = face + P["plate"] + 14.0
        handle = union(cyl(13.0, "z", p4[2] - 95.0, p4[2] - 19.0, (hx, 0.0, 0.0)), box(face, hx + 13.0, -8, 8, p4[2] - 24.0, p4[2] - 14.0))
        trigger = union(*cheeks_y(gx, gz, gx + P["hub_r"]),
                        box(gx + math.hypot(BODY_L / 2 - HORN_OFF, BODY_W / 2) + 1.5, gx + 34.0, CHEEK_NEG[0], CHEEK_POS[1], gz - 4, gz + 2),
                        box(gx + 28.0, gx + 34.0, -6, 6, gz - 30.0, gz + 2))
        return union(plate, bracket, web, handle), g, (hx, 0.0, p4[2] - 57.0), trigger
    fixed_jaw = union(box(face, tool[0] + 8, -8, 8, p4[2] - 20, p4[2] - 14),   # runs under the web to the horn plate
                      box(tool[0], tool[0] + 8, -8, 8, p4[2] - 20, p4[2] - 2))
    jaw = union(*cheeks_y(gx, gz, gx + P["hub_r"]),
                # the bar crossing the jaw starts outside the servo body's swing radius (front corners at 18.2 mm)
                box(gx + math.hypot(BODY_L / 2 - HORN_OFF, BODY_W / 2) + 1.5, tool[0] + 8, CHEEK_NEG[0], CHEEK_POS[1], gz - 4, gz + 2),
                box(tool[0], tool[0] + 8, -8, 8, p4[2] + 2, gz + 2))
    return union(plate, bracket, web, fixed_jaw), g, tool, jaw


def base_parts():
    """Base plate and housing for the upright yaw servo; returns (housing, yaw joint point, turntable, shoulder point)."""
    w, c, plate_t = P["wall"], C, 6.0
    yaw_face = plate_t + BODY_D            # body sits on the plate, horn up
    yaw_pt = (0.0, 0.0, plate_t + BODY_D / 2)
    hx0, hx1 = -HORN_OFF - BODY_L / 2 - c, -HORN_OFF + BODY_L / 2 + c
    hy = BODY_W / 2 + c
    housing = union(box(-75, 75, -75, 75, 0, plate_t),
                    box(hx0 - w, hx1 + w, -hy - w, hy + w, plate_t, yaw_face - 4).cut(box(hx0, hx1, -hy, hy, plate_t, yaw_face)))
    for sx in (-60, 60):
        for sy in (-60, 60):
            housing = housing.cut(cyl(2.75, "z", -1, plate_t + 1, (sx, sy, 0)))  # M5 clearance for clamping to a bench
    top = yaw_face + HORN_H
    disc_t = 5.0
    # Support ring: the turntable rides on a 1 mm PTFE washer on this ring, so the arm's overturning moment goes into the
    # housing instead of the servo's output bearing (rated only 40 N side load at 10 mm).
    ring_in, ring_out = P["ring_r"] - 4.0, P["ring_r"]
    ring = cyl(ring_out, "z", plate_t, top - 1.0, (0, 0, 0)).cut(cyl(ring_in, "z", plate_t - 1, top, (0, 0, 0)))
    housing = union(housing, ring)
    shoulder_pt = (0.0, 0.0, top + disc_t + w + HORN_OFF + BODY_L / 2 + c)
    sz = shoulder_pt[2]
    hx = BODY_W / 2 + c
    cradle = box(-hx - w, hx + w, -HALF_OUT, HALF_OUT, top + disc_t - 0.01, sz - HORN_OFF).cut(
        box(-hx, hx, -HALF_IN, HALF_IN, sz - HORN_OFF - BODY_L / 2 - c, sz - HORN_OFF + 1))
    turntable = union(cyl(P["ring_r"], "z", top, top + disc_t, (0, 0, 0)), cradle)
    return housing, yaw_pt, turntable, shoulder_pt


def build():
    housing, yaw_pt, turntable, p1 = base_parts()
    p2 = (p1[0] + P["upper_arm_mm"], 0.0, p1[2])
    p3 = (p2[0] + P["forearm_mm"], 0.0, p1[2])
    p4 = (p3[0] + P["wrist_mm"], 0.0, p1[2])
    grip_base, g, tool, jaw = gripper_parts(p4)
    placements = {
        "base_yaw": (yaw_pt, (0, 0, 1), (-1, 0, 0)),
        "shoulder": (p1, (0, 1, 0), (0, 0, -1)),
        "elbow": (p2, (0, 1, 0), (-1, 0, 0)),
        "wrist_pitch": (p3, (0, 1, 0), (-1, 0, 0)),
        "wrist_roll": ((p4[0] - BODY_D / 2, 0.0, p4[2]), (1, 0, 0), (0, 0, -1)),
        "gripper": (g, (0, 1, 0), (-1, 0, 0)),
    }
    s = {name: servo(*pl) for name, pl in placements.items()}
    printed = {"base_housing": housing, "turntable": turntable, "upper_arm": pitch_link(p1, P["upper_arm_mm"]),
               "forearm": pitch_link(p2, P["forearm_mm"]), "wrist": wrist_link(p3, p4), "gripper_base": grip_base,
               "gripper_jaw": jaw}
    global FASTENER_CUTS
    # The pitch joints drive two-cheek links, which also screw to the servo's rear disc. Body screws go only where a wall
    # holds that face: the yaw servo stands on the base plate (its top face is free under the turntable) and the roll
    # servo's cradle closes only behind it.
    both = ("horn_face", "back_face")
    body_faces = {"base_yaw": ("back_face",), "wrist_roll": ("back_face",), "shoulder": both, "elbow": both,
                  "wrist_pitch": both, "gripper": both}
    FASTENER_CUTS = cut_fasteners(printed, placements, {"shoulder", "elbow", "wrist_pitch", "gripper"}, body_faces) if HOLES else None
    # URDF links: (printed parts, servos carried), joint (name, type, point, axis, child)
    links = {"base_link": (["base_housing"], ["base_yaw"]), "turntable_link": (["turntable"], ["shoulder"]),
             "upper_arm_link": (["upper_arm"], ["elbow"]), "forearm_link": (["forearm"], ["wrist_pitch"]),
             "wrist_link": (["wrist"], ["wrist_roll"]), "gripper_link": (["gripper_base"], ["gripper"]),
             "jaw_link": (["gripper_jaw"], [])}
    joints = [("base_yaw", "base_link", "turntable_link", (0.0, 0.0, yaw_pt[2] + BODY_D / 2), (0, 0, 1)),
              ("shoulder", "turntable_link", "upper_arm_link", p1, (0, 1, 0)),
              ("elbow", "upper_arm_link", "forearm_link", p2, (0, 1, 0)),
              ("wrist_pitch", "forearm_link", "wrist_link", p3, (0, 1, 0)),
              ("wrist_roll", "wrist_link", "gripper_link", p4, (1, 0, 0)),
              ("gripper", "gripper_link", "jaw_link", g, (0, -1, 0))]
    return printed, s, links, joints, tool


# --- outputs and checks --------------------------------------------------------------------------------------------
def mesh_of(shape, tol=0.2):
    import trimesh
    verts, tris = shape.tessellate(tol, 0.3)
    return trimesh.Trimesh(np.array([v.toTuple() for v in verts]), np.array(tris), process=True)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=HERE)
    parser.add_argument("--servo", choices=sorted(FAMILIES), default="x430")
    args = parser.parse_args(argv)
    use_servo(args.servo)
    out = args.out
    for sub in ("print", "cad", "urdf/meshes"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    printed, servos, links, joints, tool = build()

    import trimesh
    meshes = {}
    report = {"parts": {}}
    for name, shape in printed.items():
        cq.exporters.export(shape, str(out / "print" / f"{name}.step"))
        m = mesh_of(shape)
        meshes[name] = m
        bb = shape.BoundingBox()
        dims = sorted([bb.xlen, bb.ylen, bb.zlen])
        bed = sorted(P["bed_mm"])
        vol_cm3 = shape.Volume() / 1000
        report["parts"][name] = {"volume_cm3": round(vol_cm3, 2), "mass_g": round(vol_cm3 * P["pla_g_cm3"] * P["fill"], 1),
                                 "bbox_mm": [round(bb.xlen, 1), round(bb.ylen, 1), round(bb.zlen, 1)],
                                 "fits_bed": all(d <= b for d, b in zip(dims, bed)), "valid_solid": shape.isValid(),
                                 "single_body": len(shape.Solids()) == 1}
        if len(shape.Solids()) != 1:
            raise SystemExit(f"{name} is {len(shape.Solids())} separate bodies; a printed part must be one piece")
        m.export(out / "print" / f"{name}.stl")
    for name, shape in servos.items():
        meshes["servo_" + name] = mesh_of(shape)

    # assembly (zero pose)
    scene = trimesh.Scene()
    for name, m in meshes.items():
        mm = m.copy()
        mm.visual.face_colors = [60, 60, 66, 255] if name.startswith("servo_") else [214, 120, 52, 255]
        scene.add_geometry(mm, node_name=name, geom_name=name)
    scene.export(out / "cad" / f"{NAME.upper()}_ASSEMBLY.glb")

    # URDF: link frames are world-aligned and sit at their parent joint; meshes are moved into those frames.
    origin = {"base_link": np.zeros(3)}
    for jname, parent, child, pt, axis in joints:
        origin[child] = np.array(pt, float)
    mass = {}
    com_world = {}
    inertial = {}
    for link, (parts, carried) in links.items():
        pieces = [meshes[p] for p in parts] + [meshes["servo_" + s] for s in carried]
        part_mass = [report["parts"][p]["mass_g"] / 1000 for p in parts] + [SERVOS[JOINT_SERVO[s]]["mass_kg"] for s in carried]
        coms = [pc.center_mass if pc.is_volume else pc.bounds.mean(0) for pc in pieces]
        total = sum(part_mass)
        com = sum(mk * ck for mk, ck in zip(part_mass, coms)) / total
        mass[link], com_world[link] = total, com
        combined = trimesh.util.concatenate([pc.copy() for pc in pieces])
        combined.apply_translation(-origin[link])
        combined.export(out / "urdf" / "meshes" / f"{link}.stl")
        # box inertia from the combined extents, about the CoM (a proxy, stated in the URDF comment)
        e = combined.extents / 1000
        inertial[link] = [total / 12 * (e[1] ** 2 + e[2] ** 2), total / 12 * (e[0] ** 2 + e[2] ** 2), total / 12 * (e[0] ** 2 + e[1] ** 2)]
    lines = ['<?xml version="1.0"?>', f'<robot name="{NAME}">',
             "  <!-- Generated by projects/hs-arm-a/build_arm.py. Masses: printed PLA at assumed density and fill plus cited servo "
             "masses. Inertia: box proxy from mesh extents. Joint limits come from motion_sweep (see verification.json). -->"]
    limits = json.loads((out / "joint_limits.json").read_text()) if (out / "joint_limits.json").is_file() else {}
    for link in links:
        com = (com_world[link] - origin[link]) / 1000
        ixx, iyy, izz = inertial[link]
        lines += [f'  <link name="{link}">',
                  f'    <inertial><origin xyz="{com[0]:.5f} {com[1]:.5f} {com[2]:.5f}"/><mass value="{mass[link]:.4f}"/>'
                  f'<inertia ixx="{ixx:.3e}" iyy="{iyy:.3e}" izz="{izz:.3e}" ixy="0" ixz="0" iyz="0"/></inertial>',
                  f'    <visual><geometry><mesh filename="meshes/{link}.stl" scale="0.001 0.001 0.001"/></geometry></visual>',
                  f'    <collision><geometry><mesh filename="meshes/{link}.stl" scale="0.001 0.001 0.001"/></geometry></collision>',
                  "  </link>"]
    for jname, parent, child, pt, axis in joints:
        rel = (np.array(pt) - origin[parent]) / 1000
        lo, hi = limits.get(jname, (-150.0, 150.0) if jname != "gripper" else (0.0, 70.0))
        servo_spec = SERVOS[JOINT_SERVO[jname]]
        lines += [f'  <joint name="{jname}" type="revolute"><parent link="{parent}"/><child link="{child}"/>',
                  f'    <origin xyz="{rel[0]:.5f} {rel[1]:.5f} {rel[2]:.5f}" rpy="0 0 0"/><axis xyz="{axis[0]} {axis[1]} {axis[2]}"/>',
                  f'    <limit lower="{math.radians(lo):.5f}" upper="{math.radians(hi):.5f}" effort="{servo_spec["stall_nm_12v"] or 0}" velocity="1.0"/></joint>']
    lines.append("</robot>")
    (out / "urdf" / f"{NAME}.urdf").write_text("\n".join(lines) + "\n")

    # static torque at each pitch joint, arm stretched horizontally, from CAD centres of mass
    g = 9.80665
    chain = ["turntable_link", "upper_arm_link", "forearm_link", "wrist_link", "gripper_link", "jaw_link"]
    torque = {}
    for jname, parent, child, pt, axis in joints:
        if jname not in ("shoulder", "elbow", "wrist_pitch"):
            continue
        beyond = chain[chain.index(child):]
        t = sum(mass[l] * g * (com_world[l][0] - pt[0]) / 1000 for l in beyond) + P["payload_kg"] * g * (tool[0] - pt[0]) / 1000
        need = t * P["safety_factor"]
        stall = SERVOS[JOINT_SERVO[jname]]["stall_nm_12v"]
        torque[jname] = {"static_nm": round(t, 4), "with_safety_factor_nm": round(need, 4), "servo": JOINT_SERVO[jname],
                         "stall_nm": stall, "stall_share": round(need / stall, 3) if stall else None,
                         "pass": (need <= P["max_stall_share"] * stall) if stall and not LEADER else None}
    # base yaw: overturning moment of everything above the yaw horn, against the horn's rated side load
    above = chain
    moment = sum(mass[l] * g * (com_world[l][0]) / 1000 for l in above) + P["payload_kg"] * g * tool[0] / 1000
    side_load = SERVOS[YAW_SERVO]["radial_load_n_at_10mm"]
    yaw_rating = side_load * 0.010 if side_load else None
    base_kg = mass["base_link"]
    tip = {"arm_moment_nm": round(moment, 3), "base_kg": round(base_kg, 3),
           "base_restoring_nm": round(base_kg * g * 0.075, 3),
           "free_standing_stable": base_kg * g * 0.075 >= moment,
           "basis": "worst case: arm stretched over a base edge 75 mm from the yaw axis; the restoring moment is the base's own weight"}
    # holding current at the stretched pose: current scales with torque between no load and stall (approximation)
    known = [j for j in torque if SERVOS[JOINT_SERVO[j]]["stall_a_12v"] and SERVOS[JOINT_SERVO[j]]["stall_nm_12v"]]
    holding_a = sum(SERVOS[JOINT_SERVO[j]]["stall_a_12v"] * torque[j]["static_nm"] / SERVOS[JOINT_SERVO[j]]["stall_nm_12v"] for j in known)
    stall_all_a = sum(SERVOS[JOINT_SERVO[j]]["stall_a_12v"] or 0 for j in JOINT_SERVO)
    reach = math.hypot(tool[0], tool[1])
    verification = {
        "schema": "hardware_splicer.arm_build_verification.v1", "role": "leader" if LEADER else "follower",
        "parameters": P | {"bed_mm": list(P["bed_mm"])}, "servos": JOINT_SERVO,
        "servo_geometry": {"body_mm": [BODY_L, BODY_W, BODY_D], "horn_offset_mm": HORN_OFF, "horn_r_mm": HORN_R,
                           "horn_proud_mm": HORN_H, "idler_mm": IDLER_H,
                           "cheek_boss_mm": {"horn_side": round(HORN_GAP - HORN_H, 2), "idler_side": round(IDLER_GAP - IDLER_H, 2)}},
        "parts": report["parts"],
        "mass_kg": {l: round(m, 4) for l, m in mass.items()}, "moving_mass_kg": round(sum(mass[l] for l in chain), 4),
        "reach_mm": {"tool_from_yaw_axis": round(reach, 1), "tool_height_mm": round(tool[2], 1)},
        "static_torque": torque,
        "base_yaw_overturning": {"moment_nm": round(moment, 3), "servo_side_load_rating_nm": yaw_rating,
                                 "ratio_if_horn_carried_it": round(moment / yaw_rating, 2) if yaw_rating else None,
                                 "design_response": f"support ring r={P['ring_r']} mm under the turntable with a 1 mm PTFE washer carries it",
                                 "basis": ("XM430 e-manual 'Radial Load 40 [N] (10 [mm] away from the horn)' taken as a moment"
                                           if yaw_rating else f"{YAW_SERVO}: no published side-load rating; the support ring carries it")},
        "tip_over": tip,
        "power": {"holding_a_stretched": round(holding_a, 2), "all_stalled_a": round(stall_all_a, 2),
                  "basis": "current proportional to torque up to the cited stall current at 12 V (approximation)"},
        "fasteners": ({"cut_mm3": FASTENER_CUTS, "holes": HOLES,
                       "basis": "STS3215_03a.step hole positions; SO-101 Upper_arm_SO101.step clearances"} if HOLES else None),
        "unmodelled": (["horn bolt circle and servo side screws"] if not HOLES else ["screw heads in the motion sweep"]) +
                      ["idler horn thickness (4 mm assumed)" if IDLER_H else "rear disc thread size (2.5 mm holes in the model)",
                       "cables, screws, horns' own mass", "print strength (no FEM on the links yet)"],
    }
    (out / "verification.json").write_text(json.dumps(verification, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)) + "\n")
    print(json.dumps({k: verification[k] for k in ("reach_mm", "moving_mass_kg", "base_yaw_overturning", "tip_over")}, indent=1, default=lambda o: o.item()))
    print({n: (p["mass_g"], p["bbox_mm"], p["fits_bed"], p["valid_solid"], p["single_body"]) for n, p in report["parts"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
