import json, sys, numpy as np, trimesh, manifold3d
scene = trimesh.load(sys.argv[1], force="scene"); side = json.load(open(sys.argv[2])); by = {p["part_id"]: p["node_name"] for p in side["parts"]}
def man(pid):
    tf, g = scene.graph[by[pid]]; m = scene.geometry[g].copy(); m.apply_transform(tf); m.merge_vertices()
    return manifold3d.Manifold(manifold3d.Mesh(np.asarray(m.vertices, np.float32), np.asarray(m.faces, np.uint32)))
for a, b in (("tray-front-left", "keyboard-nominal-envelope"), ("tray-rear-left", "display-spacer-1")):
    r = (man(a) ^ man(b)).to_mesh(); v = np.asarray(r.vert_properties)[:, :3]
    print(a, b, "overlap region", np.round(v.min(0), 1), "..", np.round(v.max(0), 1))
