#!/usr/bin/env python3
"""Where can HS-ARM-A pick an object off the table? Planar inverse kinematics of shoulder, elbow and wrist pitch within
the swept joint limits (joint_limits.json), for a grasp point 20 mm above the table at a given radius and approach angle.

The arm's geometry comes from verification.json and build_arm.py's parameters. A pose counts only if the elbow and wrist
axes stay at least 20 mm above the table (half a servo body) and outside the base (75 mm) when below 60 mm height.
Combined poses are not collision-swept here; motion_sweep checks each joint's range from the zero pose.
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    v = json.loads((HERE / "verification.json").read_text())
    lim = json.loads((HERE / "joint_limits.json").read_text())
    p = v["parameters"]
    l1, l2 = p["upper_arm_mm"], p["forearm_mm"]
    z1 = v["reach_mm"]["tool_height_mm"]                       # shoulder axis height (tool is level with it at zero)
    d = v["reach_mm"]["tool_from_yaw_axis"] - l1 - l2          # wrist-pitch axis to grasp point
    # elevation = -joint angle (positive joint rotation about +Y tips +X downward)
    e1r = (-lim["shoulder"][1], -lim["shoulder"][0])
    e2r = (-lim["elbow"][1], -lim["elbow"][0])
    e3r = (-lim["wrist_pitch"][1], -lim["wrist_pitch"][0])
    grasp_z = 20.0

    def solve(r, phi):
        wx, wz = r - d * math.cos(math.radians(phi)), grasp_z - d * math.sin(math.radians(phi))
        dx, dz = wx, wz - z1
        dist = math.hypot(dx, dz)
        if dist > l1 + l2 or dist < abs(l1 - l2):
            return None
        for sign in (1, -1):  # elbow up / down
            c2 = (dist ** 2 - l1 ** 2 - l2 ** 2) / (2 * l1 * l2)
            e2 = sign * math.degrees(math.acos(max(-1, min(1, c2))))
            e1 = math.degrees(math.atan2(dz, dx) - math.atan2(l2 * math.sin(math.radians(e2)), l1 + l2 * math.cos(math.radians(e2))))
            e3 = phi - e1 - e2
            ok = all(lo <= e <= hi for e, (lo, hi) in ((e1, e1r), (e2, e2r), (e3, e3r)))
            ex, ez = l1 * math.cos(math.radians(e1)), z1 + l1 * math.sin(math.radians(e1))
            clear = all(z >= 20 and (z >= 60 or x >= 75) for x, z in ((ex, ez), (wx, wz)))
            if ok and clear:
                return {"shoulder": round(-e1, 1), "elbow": round(-e2, 1), "wrist_pitch": round(-e3, 1)}
        return None

    rows = {}
    for name, phi in (("top_down", -90), ("angled_45", -45), ("horizontal", 0)):
        ok = [r for r in range(60, 401, 5) if solve(r, phi)]
        rows[name] = {"approach_deg_below_horizontal": -phi, "radius_mm": [min(ok), max(ok)] if ok else None,
                      "example": {r: solve(r, phi) for r in (ok[:1] + ok[-1:])} if ok else None}
    any_angle = [r for r in range(60, 401, 5) if any(solve(r, phi) for phi in range(-90, 1, 5))]
    out = {"grasp_height_mm": grasp_z, "wrist_to_grasp_mm": round(d, 1), "by_approach": rows,
           "any_approach_radius_mm": [min(any_angle), max(any_angle)] if any_angle else None}
    v["pick_workspace"] = out
    (HERE / "verification.json").write_text(json.dumps(v, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
