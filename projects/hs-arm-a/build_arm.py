#!/usr/bin/env python3
"""HS-ARM-A: a 5-axis desktop arm with a gripper, built around DYNAMIXEL X430 servos. Generates every printed part,
the assembly, a URDF with CAD-derived masses, and the checks that close the design loop.

    .cache/hardware-splicer/digital-native-venv/bin/python projects/hs-arm-a/build_arm.py [--out projects/hs-arm-a]

Geometry basis
* Servo body 46.5 x 28.5 x 34 mm (ROBOTIS e-manual, XM430-W350 and XL430-W250 "Dimensions (W x H x D)").
* Horn: diameter 19.5 mm, 6.4 mm proud of the body, axis 12 mm from the body centre along its 46.5 mm length. Measured
  from the XM430 body in ROBOTIS's OpenMANIPULATOR-X model (link1.stl, Apache-2.0), whose joint1 origin also sits 12 mm
  off the body centre.
* Idler horn on the back face: 4 mm thick, same diameter (assumed; ROBOTIS's hinge frames need an idler horn per its
  e-manual, but its drawing could not be downloaded).
* Horn bolt circle and servo side-screw positions are NOT modelled: printed parts carry no holes for them. Drill or
  add them from the real horn (a printed test coupon is generated for that).

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
BODY_L, BODY_W, BODY_D = 46.5, 28.5, 34.0
HORN_OFF = 12.0          # horn axis from body centre, along the length
HORN_R, HORN_H = 9.75, 6.4
IDLER_H = 4.0            # assumed
SERVOS = {"XM430-W350-T": {"mass_kg": 0.082, "stall_nm_12v": 4.1, "stall_a_12v": 2.3, "radial_load_n_at_10mm": 40.0},
          "XL430-W250-T": {"mass_kg": 0.0572, "stall_nm_12v": 1.5, "stall_a_12v": 1.4, "radial_load_n_at_10mm": None}}

# --- design parameters ----------------------------------------------------------------------------------------------
P = {
    "upper_arm_mm": 110.0,     # shoulder axis to elbow axis
    "forearm_mm": 100.0,       # elbow axis to wrist-pitch axis
    "wrist_mm": 72.0,          # wrist-pitch axis to wrist-roll horn face; wrist_link needs at least 68.3
    "wall": 3.0, "plate": 4.0, "clear": 0.3, "hub_r": 20.0,
    "ring_r": 44.0, "payload_kg": 0.15, "safety_factor": 1.5, "max_stall_share": 0.5,
    "pla_g_cm3": 1.24, "fill": 0.6, "bed_mm": (220.0, 220.0, 250.0),
}
JOINT_SERVO = {"base_yaw": "XM430-W350-T", "shoulder": "XM430-W350-T", "elbow": "XM430-W350-T",
               "wrist_pitch": "XL430-W250-T", "wrist_roll": "XL430-W250-T", "gripper": "XL430-W250-T"}

C = P["clear"]
HALF_IN = BODY_D / 2 + C                 # cradle inner half-width across the body depth
HALF_OUT = HALF_IN + P["wall"]
CHEEK_POS = (BODY_D / 2 + HORN_H, BODY_D / 2 + HORN_H + P["plate"])          # horn-side cheek, along the axis
CHEEK_NEG = (-(BODY_D / 2 + IDLER_H + P["plate"]), -(BODY_D / 2 + IDLER_H))  # idler-side cheek


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
    solid = body.fuse(cyl(HORN_R, "z", BODY_D / 2, BODY_D / 2 + HORN_H, (0, 0, 0)),
                      cyl(HORN_R, "z", -BODY_D / 2 - IDLER_H, -BODY_D / 2, (0, 0, 0))).clean()
    return place(solid, frame(axis, body_dir), point)


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
    s = {
        "base_yaw": servo(yaw_pt, (0, 0, 1), (-1, 0, 0)),
        "shoulder": servo(p1, (0, 1, 0), (0, 0, -1)),
        "elbow": servo(p2, (0, 1, 0), (-1, 0, 0)),
        "wrist_pitch": servo(p3, (0, 1, 0), (-1, 0, 0)),
        "wrist_roll": servo((p4[0] - BODY_D / 2, 0.0, p4[2]), (1, 0, 0), (0, 0, -1)),
        "gripper": servo(g, (0, 1, 0), (-1, 0, 0)),
    }
    printed = {"base_housing": housing, "turntable": turntable, "upper_arm": pitch_link(p1, P["upper_arm_mm"]),
               "forearm": pitch_link(p2, P["forearm_mm"]), "wrist": wrist_link(p3, p4), "gripper_base": grip_base,
               "gripper_jaw": jaw}
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
    args = parser.parse_args(argv)
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
    scene.export(out / "cad" / "HS_ARM_A_ASSEMBLY.glb")

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
    lines = ['<?xml version="1.0"?>', '<robot name="hs_arm_a">',
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
                  f'    <limit lower="{math.radians(lo):.5f}" upper="{math.radians(hi):.5f}" effort="{servo_spec["stall_nm_12v"]}" velocity="1.0"/></joint>']
    lines.append("</robot>")
    (out / "urdf" / "hs_arm_a.urdf").write_text("\n".join(lines) + "\n")

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
                         "stall_nm": stall, "stall_share": round(need / stall, 3), "pass": need <= P["max_stall_share"] * stall}
    # base yaw: overturning moment of everything above the yaw horn, against the horn's rated side load
    above = chain
    moment = sum(mass[l] * g * (com_world[l][0]) / 1000 for l in above) + P["payload_kg"] * g * tool[0] / 1000
    yaw_rating = SERVOS["XM430-W350-T"]["radial_load_n_at_10mm"] * 0.010
    base_kg = mass["base_link"]
    tip = {"arm_moment_nm": round(moment, 3), "base_kg": round(base_kg, 3),
           "base_restoring_nm": round(base_kg * g * 0.075, 3),
           "free_standing_stable": base_kg * g * 0.075 >= moment,
           "basis": "worst case: arm stretched over a base edge 75 mm from the yaw axis; the restoring moment is the base's own weight"}
    # holding current at the stretched pose: current scales with torque between no load and stall (approximation)
    holding_a = sum(SERVOS[JOINT_SERVO[j]]["stall_a_12v"] * torque[j]["static_nm"] / SERVOS[JOINT_SERVO[j]]["stall_nm_12v"] for j in torque)
    stall_all_a = sum(SERVOS[JOINT_SERVO[j]]["stall_a_12v"] for j in JOINT_SERVO)
    reach = math.hypot(tool[0], tool[1])
    verification = {
        "schema": "hardware_splicer.arm_build_verification.v1",
        "parameters": P | {"bed_mm": list(P["bed_mm"])}, "servos": JOINT_SERVO,
        "parts": report["parts"],
        "mass_kg": {l: round(m, 4) for l, m in mass.items()}, "moving_mass_kg": round(sum(mass[l] for l in chain), 4),
        "reach_mm": {"tool_from_yaw_axis": round(reach, 1), "tool_height_mm": round(tool[2], 1)},
        "static_torque": torque,
        "base_yaw_overturning": {"moment_nm": round(moment, 3), "servo_side_load_rating_nm": yaw_rating,
                                 "ratio_if_horn_carried_it": round(moment / yaw_rating, 2),
                                 "design_response": f"support ring r={P['ring_r']} mm under the turntable with a 1 mm PTFE washer carries it",
                                 "basis": "XM430 e-manual 'Radial Load 40 [N] (10 [mm] away from the horn)' taken as a moment"},
        "tip_over": tip,
        "power": {"holding_a_stretched": round(holding_a, 2), "all_stalled_a": round(stall_all_a, 2),
                  "basis": "current proportional to torque up to the cited stall current at 12 V (approximation)"},
        "unmodelled": ["horn bolt circle and servo side screws", "idler horn thickness (4 mm assumed)",
                       "cables, screws, horns' own mass", "print strength (no FEM on the links yet)"],
    }
    (out / "verification.json").write_text(json.dumps(verification, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)) + "\n")
    print(json.dumps({k: verification[k] for k in ("reach_mm", "moving_mass_kg", "base_yaw_overturning", "tip_over")}, indent=1, default=lambda o: o.item()))
    print({n: (p["mass_g"], p["bbox_mm"], p["fits_bed"], p["valid_solid"], p["single_body"]) for n, p in report["parts"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
