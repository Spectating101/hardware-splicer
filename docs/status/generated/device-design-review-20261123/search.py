import json, sys, numpy as np, trimesh, manifold3d
scene = trimesh.load(sys.argv[1], force="scene"); side = json.load(open(sys.argv[2]))
DROP = float(sys.argv[3]); disp_bottom = 46.1 - DROP
by = {p["node_name"]: p for p in side["parts"]}
solids = []
for node in scene.graph.nodes_geometry:
    p = by.get(node)
    if not p or p["part_id"] == "power-bank-nominal-envelope": continue
    tf, g = scene.graph[node]; m = scene.geometry[g].copy(); m.apply_transform(tf); m.merge_vertices()
    try: solids.append((p["part_id"], manifold3d.Manifold(manifold3d.Mesh(np.asarray(m.vertices, np.float32), np.asarray(m.faces, np.uint32)))))
    except Exception as e: print("skip", p["part_id"], e)
best = []
for rot, (dx, dy) in (("along x", (105.3, 54.3)), ("along y", (54.3, 105.3))):  # 1 mm nest allowance each side
    for x in np.arange(62, 310 - dx - 3, 2.0):
        for y in np.arange(142, 285 - dy - 3, 2.0):
            for z in np.arange(3.0, 9.0, 0.5):
                top = z + 27.0
                if top + 1.0 > disp_bottom and x + dx > 83.3 and x < 226.7 and y + dy > 164.3: continue
                box = manifold3d.Manifold.cube([dx, dy, 27.0]).translate([x, y, z])
                hit = sum((box ^ s).volume() for _, s in solids)
                if hit < 1e-3:
                    best.append((z, rot, round(x,1), round(y,1), round(top,1))); break
print(len(best), "clear placements (lowest z per x,y); sample:", sorted(best)[:8])
