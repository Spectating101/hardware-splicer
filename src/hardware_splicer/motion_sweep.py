"""Range-of-motion clash sweep for a robot or mechanism described by URDF: does anything run into anything?

Runs as a standalone script in the native CAD interpreter (numpy, scipy, trimesh, manifold3d), like scene_fit:

    python motion_sweep.py --urdf ROBOT.urdf [--steps 25] [--pose joint=value ...] [--pair a,b ...]

Each movable joint is swept from its lower to its upper limit with every other joint held at the start pose (0, or
--pose, clamped to limits). Listed --pair joints are swept together on a grid. At every step every mesh is placed by
forward kinematics, and every two meshes on different links are measured:

* ``overlap`` (mm^3): exact intersection volume of the two solids (manifold3d). Links joined by a joint usually touch
  or interpenetrate slightly in the model, so for those pairs only the growth over the start pose counts.
* ``gap`` (mm): minimum surface distance from dense samples (an upper bound; see scene_fit).

The report gives, per joint: the steps where a clash appears, the worst one, and the smallest clearance between links
that are not joined, with the joint value at which each happens. The basis is the URDF's own geometry and limits.
It is not a dynamics or strength check, and a clash in a coarse collision mesh may not exist on the real parts.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import xml.etree.ElementTree as ET
from itertools import combinations, product
from pathlib import Path

VERSION = "motion-sweep.v1"
CLASH_MM3 = 1.0        # an overlap under this is meshing noise
NEAR_MM = 5.0          # clearance is reported only for meshes closer than this
SPACING_MM = 1.0


def _scene_fit():
    spec = importlib.util.spec_from_file_location("hs_scene_fit", Path(__file__).with_name("scene_fit.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _floats(text, default):
    return [float(v) for v in text.split()] if text else list(default)


def _transform(xyz, rpy):
    import numpy as np

    r, p, y = rpy
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    m = np.eye(4)
    m[:3, :3] = [[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                 [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                 [-sp, cp * sr, cp * cr]]
    m[:3, 3] = xyz
    return m


def _axis_motion(axis, kind, value):
    import numpy as np

    axis = np.asarray(axis, dtype=float)
    axis = axis / (np.linalg.norm(axis) or 1.0)
    m = np.eye(4)
    if kind == "prismatic":
        m[:3, 3] = axis * value
        return m
    x, y, z = axis
    c, s, t = math.cos(value), math.sin(value), 1 - math.cos(value)
    m[:3, :3] = [[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
                 [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
                 [t * x * z - s * y, t * y * z + s * x, t * z * z + c]]
    return m


def parse_urdf(path: Path) -> dict:
    """Links with their collision meshes (visual when there is none) and joints with origin, axis and limits."""
    root = ET.parse(path).getroot()
    links = {}
    for link in root.findall("link"):
        elements = link.findall("collision") or link.findall("visual")
        meshes = []
        for element in elements:
            mesh = element.find("geometry/mesh")
            if mesh is None:
                continue
            origin = element.find("origin")
            name = mesh.get("filename", "").replace("package://", "")
            meshes.append({"file": name, "scale": _floats(mesh.get("scale"), (1, 1, 1)),
                           "xyz": _floats(origin.get("xyz") if origin is not None else None, (0, 0, 0)),
                           "rpy": _floats(origin.get("rpy") if origin is not None else None, (0, 0, 0))})
        links[link.get("name")] = meshes
    joints = []
    for joint in root.findall("joint"):
        origin, axis, limit = joint.find("origin"), joint.find("axis"), joint.find("limit")
        kind = joint.get("type")
        lower = float(limit.get("lower", 0)) if limit is not None else 0.0
        upper = float(limit.get("upper", 0)) if limit is not None else 0.0
        if kind == "continuous":
            lower, upper = -math.pi, math.pi
        joints.append({"name": joint.get("name"), "type": kind, "parent": joint.find("parent").get("link"),
                       "child": joint.find("child").get("link"),
                       "xyz": _floats(origin.get("xyz") if origin is not None else None, (0, 0, 0)),
                       "rpy": _floats(origin.get("rpy") if origin is not None else None, (0, 0, 0)),
                       "axis": _floats(axis.get("xyz") if axis is not None else None, (1, 0, 0)), "lower": lower, "upper": upper})
    return {"links": links, "joints": joints}


def link_poses(model: dict, q: dict) -> dict:
    """World transform of every link for joint values q (radians or metres)."""
    import numpy as np

    children = {j["child"] for j in model["joints"]}
    roots = [name for name in model["links"] if name not in children]
    poses = {name: np.eye(4) for name in roots}
    pending = list(model["joints"])
    while pending:
        progressed = False
        for joint in list(pending):
            if joint["parent"] in poses:
                motion = np.eye(4) if joint["type"] == "fixed" else _axis_motion(joint["axis"], joint["type"], q.get(joint["name"], 0.0))
                poses[joint["child"]] = poses[joint["parent"]] @ _transform(joint["xyz"], joint["rpy"]) @ motion
                pending.remove(joint)
                progressed = True
        if not progressed:
            raise ValueError("URDF joints do not form a tree from a root link")
    return poses


def _load_bodies(model: dict, base: Path, to_mm: float) -> list[dict]:
    import numpy as np
    import trimesh

    bodies = []
    for link, meshes in model["links"].items():
        for index, item in enumerate(meshes):
            path = (base / item["file"]).resolve()
            if not path.is_file():
                raise FileNotFoundError(f"{link}: mesh {item['file']} not found next to the URDF")
            mesh = trimesh.load(path, force="mesh")
            mesh.apply_scale(item["scale"])
            mesh.apply_transform(_transform(item["xyz"], item["rpy"]))
            mesh.apply_scale(to_mm)
            points, _ = trimesh.sample.sample_surface(mesh, int(min(20000, max(300, mesh.area / SPACING_MM ** 2))), seed=7)
            bodies.append({"id": f"{link}/{Path(item['file']).stem}" + (f"#{index}" if index else ""), "link": link, "mesh": mesh,
                           "points": np.vstack([mesh.vertices, points])})
    return bodies


def _placed(body: dict, pose, to_mm: float):
    import numpy as np

    m = pose.copy()
    m[:3, 3] *= to_mm
    mesh = body["mesh"].copy()
    mesh.apply_transform(m)
    points = body["points"] @ m[:3, :3].T + m[:3, 3]
    return {"mesh": mesh, "points": points, "bounds": mesh.bounds, "id": body["id"], "link": body["link"]}, np


def _measure(bodies: list[dict], poses: dict, to_mm: float, fit) -> dict:
    """Overlap volume and gap for every pair of meshes on different links at one pose."""
    from scipy.spatial import cKDTree

    placed = [_placed(b, poses[b["link"]], to_mm)[0] for b in bodies]
    out = {}
    for a, b in combinations(placed, 2):
        if a["link"] == b["link"]:
            continue
        if fit._aabb_gap(a["bounds"], b["bounds"]) > NEAR_MM:
            continue
        volume = fit._overlap_volume(a["mesh"], b["mesh"]) if fit._aabb_gap(a["bounds"], b["bounds"]) == 0 else 0.0
        qa = fit._near_points(a["points"], b["bounds"], NEAR_MM)
        qb = fit._near_points(b["points"], a["bounds"], NEAR_MM)
        gap = math.inf
        if len(qa) and len(qb):
            gap = float(cKDTree(qb).query(qa, k=1)[0].min())
        out[(a["id"], b["id"])] = {"links": (a["link"], b["link"]), "overlap_mm3": volume, "gap_mm": gap}
    return out


def sweep(urdf: Path, steps: int = 25, pose: dict | None = None, pairs: list[tuple[str, str]] | None = None, to_mm: float | None = None,
          only: list[str] | None = None, window: dict | None = None) -> dict:
    model = parse_urdf(urdf)
    movable = [j for j in model["joints"] if j["type"] in ("revolute", "continuous", "prismatic")]
    start = {j["name"]: min(max((pose or {}).get(j["name"], 0.0), j["lower"]), j["upper"]) for j in movable}
    if to_mm is None:  # URDF is metres by convention; a model already in millimetres is far larger than a metre
        to_mm = 1000.0
    bodies = _load_bodies(model, urdf.parent, to_mm)
    joined = {frozenset((j["parent"], j["child"])) for j in model["joints"]}
    fit = _scene_fit()
    baseline = _measure(bodies, link_poses(model, start), to_mm, fit)

    def clashes(measured):
        found = []
        for key, row in measured.items():
            base = baseline.get(key, {"overlap_mm3": 0.0})["overlap_mm3"] or 0.0
            volume = row["overlap_mm3"]
            if volume is None:
                continue
            adjacent = frozenset(row["links"]) in joined
            excess = volume - base if adjacent else volume
            if excess > CLASH_MM3:
                found.append({"a": key[0], "b": key[1], "joined": adjacent, "overlap_mm3": round(volume, 1),
                              "over_start_mm3": round(excess, 1)})
        return found

    def nearest(measured):
        rows = [(row["gap_mm"], key) for key, row in measured.items()
                if frozenset(row["links"]) not in joined and (row["overlap_mm3"] or 0) <= CLASH_MM3]
        return min(rows) if rows else (math.inf, None)

    # window narrows one joint's sweep (to find where a clash starts); only limits which joints are swept
    plans = [((j["name"],), [(v,) for v in _range({**j, **dict(zip(("lower", "upper"), (window or {}).get(j["name"], (j["lower"], j["upper"]))))}, steps)])
             for j in movable if not only or j["name"] in only]
    by_name = {j["name"]: j for j in movable}
    for a, b in pairs or []:
        grid = max(5, int(math.sqrt(steps)) + 1)
        plans.append(((a, b), list(product(_range(by_name[a], grid), _range(by_name[b], grid)))))
    reports = []
    for names, values in plans:
        hits, best_gap = [], (math.inf, None, None)
        for vals in values:
            q = dict(start)
            q.update(dict(zip(names, vals)))
            measured = _measure(bodies, link_poses(model, q), to_mm, fit)
            for clash in clashes(measured):
                hits.append({"at": [round(v, 4) for v in vals], **clash})
            gap, key = nearest(measured)
            if gap < best_gap[0]:
                best_gap = (gap, key, [round(v, 4) for v in vals])
        worst = max(hits, key=lambda h: h["over_start_mm3"]) if hits else None
        clashed = {tuple(h["at"]) for h in hits}
        clear_range = None
        if len(names) == 1:
            # The unbroken clear stretch around the start pose: a clash in the middle splits the range.
            ok = [tuple(round(x, 4) for x in v) not in clashed for v in values]
            here = min(range(len(values)), key=lambda i: abs(values[i][0] - start[names[0]]))
            if ok[here]:
                lo = hi = here
                while lo > 0 and ok[lo - 1]:
                    lo -= 1
                while hi < len(values) - 1 and ok[hi + 1]:
                    hi += 1
                clear_range = [round(values[lo][0], 4), round(values[hi][0], 4)]
        reports.append({
            "joints": list(names),
            "range": [[by_name[n]["lower"], by_name[n]["upper"]] for n in names],
            "steps": len(values),
            "clash_steps": len({tuple(h["at"]) for h in hits}),
            "worst_clash": worst,
            "clashing_pairs": sorted({f"{h['a']} / {h['b']}" for h in hits}),
            "clear_range": clear_range,
            "min_clearance_mm": None if best_gap[1] is None else round(best_gap[0], 2),
            "min_clearance_pair": None if best_gap[1] is None else " / ".join(best_gap[1]),
            "min_clearance_at": best_gap[2],
        })
    return {
        "schema_version": VERSION,
        "urdf": str(urdf.name),
        "units": "joint values in radians (metres for prismatic); volumes mm^3; gaps mm",
        "start_pose": {k: round(v, 4) for k, v in start.items()},
        "meshes": len(bodies),
        "claim_boundary": ("Geometry from the URDF's own meshes and joint limits, one joint (or listed pair) at a time from the start "
                           "pose. Not a dynamics, strength or wiring check; a clash in a simplified mesh may not exist on real parts, "
                           "and a pose not sampled is not checked."),
        "sweeps": reports,
    }


def _range(joint: dict, steps: int) -> list[float]:
    lo, hi = joint["lower"], joint["upper"]
    if steps < 2 or hi <= lo:
        return [lo]
    return [lo + (hi - lo) * i / (steps - 1) for i in range(steps)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=25)
    parser.add_argument("--pose", nargs="*", default=[], help="joint=value start pose")
    parser.add_argument("--pair", nargs="*", default=[], help="a,b joints swept together on a grid")
    parser.add_argument("--to-mm", type=float, default=None, help="model units to mm (default 1000: URDF metres)")
    parser.add_argument("--only", nargs="*", default=None, help="sweep only these joints")
    parser.add_argument("--window", nargs="*", default=[], help="joint=lo:hi to sweep part of a range")
    args = parser.parse_args(argv)
    pose = {k: float(v) for k, v in (item.split("=", 1) for item in args.pose)}
    pairs = [tuple(item.split(",", 1)) for item in args.pair]
    window = {k: tuple(float(x) for x in v.split(":")) for k, v in (item.split("=", 1) for item in args.window)}
    print(json.dumps(sweep(args.urdf, args.steps, pose, pairs, args.to_mm, args.only, window), indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
