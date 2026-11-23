"""Layout probe (not a CAD revision): Fielddeck 5-inch with the power bank moved to the rear bay."""
import json, sys, numpy as np, trimesh, manifold3d
root, out = sys.argv[1], sys.argv[2]
src = f"{root}/projects/cyberdeck-real-trial-20261020/display_swap"
scene = trimesh.load(f"{src}/cad/FIELDDECK_5.glb", force="scene")
side = json.load(open(f"{src}/parts.json"))
scale = side.get("glb_scale_to_mm", 1)
node_of = {p["part_id"]: p["node_name"] for p in side["parts"]}
DROP = float(sys.argv[3]) if len(sys.argv) > 3 else 11.6
TOP = 61.0 - DROP                       # new tray top / face bottom
def world(node):
    tf, g = scene.graph[node]; m = scene.geometry[g].copy(); m.apply_transform(tf); m.apply_scale(scale); return m
new = trimesh.Scene(); report = {"drop_mm": DROP, "moved": {}, "trimmed": {}}
for pid, node in node_of.items():
    if node not in scene.graph.nodes_geometry: continue
    m = world(node)
    if pid == "power-bank-nominal-envelope":
        # lay it along x in the rear bay: 104 x 52.3 x 26, clear of seam plates (z 3-6) and the Pi (x < 62)
        lo = m.bounds[0]; m.apply_translation(-lo)
        # chosen from the collision search (search.py): same orientation, 1 mm nest allowance kept clear
        m.apply_translation(-m.bounds[0] + [213.0, 171.0, 3.5]); report["moved"][pid] = np.round(m.bounds, 1).tolist()
    elif any(pid.startswith(p) for p in ("display", "keyboard", "fan-envelope", "fan-guard", "face-")):
        m.apply_translation([0, 0, -DROP]); report["moved"][pid] = f"down {DROP} mm"
    elif pid == "fan-duct":
        lo, hi = m.bounds  # shorten the duct from its top so the fan still sits on it
        cut = manifold3d.Manifold.cube([hi[0] - lo[0] + 2, hi[1] - lo[1] + 2, hi[2] - DROP - lo[2]]).translate([lo[0] - 1, lo[1] - 1, lo[2]])
        mm = manifold3d.Manifold(manifold3d.Mesh(np.asarray(m.vertices, np.float32), np.asarray(m.faces, np.uint32)))
        r = (mm ^ cut).to_mesh(); m = trimesh.Trimesh(np.asarray(r.vert_properties)[:, :3], np.asarray(r.tri_verts)); report["trimmed"][pid] = f"top cut {DROP} mm"
    elif pid.startswith("tray-"):
        m.merge_vertices()
        lo, hi = m.bounds
        before = m.volume if m.is_watertight else None
        cut = manifold3d.Manifold.cube([hi[0] - lo[0] + 2, hi[1] - lo[1] + 2, TOP - lo[2]]).translate([lo[0] - 1, lo[1] - 1, lo[2]])
        mm = manifold3d.Manifold(manifold3d.Mesh(np.asarray(m.vertices, np.float32), np.asarray(m.faces, np.uint32)))
        r = (mm ^ cut).to_mesh(); m = trimesh.Trimesh(np.asarray(r.vert_properties)[:, :3], np.asarray(r.tri_verts))
        report["trimmed"][pid] = {"before_mm3": round(before) if before else None, "after_mm3": round(m.volume)}
    new.add_geometry(m, node_name=node, geom_name=node)
new.export(f"{out}/probe.glb")
side2 = dict(side, glb_scale_to_mm=1)
json.dump(side2, open(f"{out}/parts.json", "w"))
lo = np.min([g.bounds[0] for g in new.dump()], 0); hi = np.max([g.bounds[1] for g in new.dump()], 0)
report["size_mm"] = np.round(hi - lo, 1).tolist()
print(json.dumps(report, indent=1))
