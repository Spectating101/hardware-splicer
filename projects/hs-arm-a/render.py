#!/usr/bin/env python3
"""Render HS-ARM-A from its URDF at named poses (matplotlib, headless): render.py [--out DIR]."""
import argparse
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

HERE = Path(__file__).resolve().parent
POSES = {"zero": {}, "pick_top_down_150mm": {"shoulder": -60.0, "elbow": 58.0, "wrist_pitch": 92.0, "gripper": 35.0},
         "reach_angled_300mm": {"base_yaw": 35.0, "shoulder": -30.0, "elbow": 30.0, "wrist_pitch": 45.0, "gripper": 20.0}}


def rot(axis, q):
    return trimesh.transformations.rotation_matrix(q, axis)


def fk(root, q):
    joints = {j.find("child").get("link"): j for j in root.findall("joint")}
    pose = {"base_link": np.eye(4)}

    def world(link):
        if link in pose:
            return pose[link]
        j = joints[link]
        parent = world(j.find("parent").get("link"))
        t = np.eye(4)
        t[:3, 3] = [float(v) * 1000 for v in j.find("origin").get("xyz").split()]
        axis = [float(v) for v in j.find("axis").get("xyz").split()]
        pose[link] = parent @ t @ rot(axis, math.radians(q.get(j.get("name"), 0.0)))
        return pose[link]

    return {l.get("name"): world(l.get("name")) for l in root.findall("link")}


def draw(ax, root, q):
    light = np.array([0.4, -0.5, 0.75]) / np.linalg.norm([0.4, -0.5, 0.75])
    colours = [(0.35, 0.36, 0.4), (0.84, 0.47, 0.2), (0.2, 0.5, 0.62), (0.84, 0.47, 0.2), (0.2, 0.5, 0.62), (0.84, 0.47, 0.2), (0.55, 0.4, 0.7)]
    for i, (link, t) in enumerate(fk(root, q).items()):
        m = trimesh.load(HERE / "urdf" / "meshes" / f"{link}.stl")
        m.apply_transform(t)
        shade = 0.45 + 0.55 * np.clip(m.face_normals @ light, 0, 1)
        base = np.array(colours[i % len(colours)])
        ax.add_collection3d(Poly3DCollection(m.triangles, facecolors=np.clip(shade[:, None] * base, 0, 1), linewidths=0))
    ax.set(xlim=(-90, 390), ylim=(-240, 240), zlim=(0, 300))
    ax.set_box_aspect((480, 480, 300))
    ax.view_init(elev=18, azim=-62)
    ax.dist = 6.5
    ax.set_axis_off()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=HERE / "renders")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    root = ET.parse(HERE / "urdf" / "hs_arm_a.urdf").getroot()
    fig = plt.figure(figsize=(18, 6.4))
    for i, (name, q) in enumerate(POSES.items()):
        ax = fig.add_subplot(1, 3, i + 1, projection="3d")
        draw(ax, root, q)
        ax.set_title(name.replace("_", " "))
    fig.tight_layout()
    fig.savefig(args.out / "HS_ARM_A_POSES.png", dpi=110)
    print(args.out / "HS_ARM_A_POSES.png")


if __name__ == "__main__":
    main()
