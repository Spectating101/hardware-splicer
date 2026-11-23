"""Digital pallet-transfer and cold header rehearsal. Coordinates are millimetres."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial.transform import Rotation


ROOT = Path(__file__).resolve().parent
JOINTS = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll")
TOOL = "gripper_frame_joint"
# Downward tool, with a fixed horizontal axis so the pallet keeps its heading.
ORIENTATION = np.array([[0., 1., 0.], [1., 0., 0.], [0., 0., -1.]])


def read(name):
    return json.loads((ROOT / name).read_text())


def write(name, data):
    (ROOT / name).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def chain():
    xml = ET.parse(ROOT / "so101.urdf")
    origins, limits = [], []
    for name in (*JOINTS, TOOL):
        joint = xml.find(f".//joint[@name='{name}']")
        origin = joint.find("origin")
        frame = np.eye(4)
        frame[:3, :3] = Rotation.from_euler("xyz", np.fromstring(origin.get("rpy"), sep=" ")).as_matrix()
        frame[:3, 3] = 1000 * np.fromstring(origin.get("xyz"), sep=" ")
        origins.append(frame)
        if name != TOOL:
            if joint.find("axis").get("xyz") != "0 0 1":
                raise ValueError("Expected the SO-101 local Z joint axis")
            limits.append([float(joint.find("limit").get(k)) for k in ("lower", "upper")])
    return origins, np.array(limits).T


def forward(origins, q):
    frame = np.eye(4)
    for origin, angle in zip(origins, q, strict=False):
        spin = np.eye(4)
        c, s = np.cos(angle), np.sin(angle)
        spin[:2, :2] = [[c, -s], [s, c]]
        frame = frame @ origin @ spin
    return frame @ origins[-1]


def targets(r):
    height = 45.
    raised = height + r["lift_mm"]
    x = r["station_x_mm"]
    poses = [("pick", [210., -65., height]), ("lift", [210., -65., raised]),
             ("carry", [x, 65., raised]), ("place", [x, 65., height]),
             ("withdraw", [x, 65., raised])]
    yield poses[0]
    for (_, a), (action, b) in zip(poses, poses[1:]):
        steps = int(np.ceil(np.linalg.norm(np.subtract(a, b)) / 8))
        for i in range(1, steps + 1):
            yield action, (np.array(a) + np.subtract(b, a) * (i / steps)).tolist()


def header_targets():
    header = read("header.json")
    x0, y0 = header["fixture_xy_datum_kicad_mm"]
    for pin, x, y in header["kicad_xy_mm"]:
        # Board flipped about the fixture Y axis, underside up.
        yield pin, x0 - x, y0 - y
