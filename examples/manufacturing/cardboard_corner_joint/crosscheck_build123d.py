"""Optional independent CAD API recreation of Manufacturing Challenge 01.

Uses the already-available build123d project in HS's external CAD ecosystem.
Compare exact BREP volume, shape bounds and mesh integrity to the CadQuery
generator; both tools use OpenCascade and this is NOT independent structural FEA.
Requires: build123d==0.13.0, trimesh, libGL.
Run: python crosscheck_build123d.py [output_directory]
"""
from pathlib import Path
import json
import sys
from build123d import Box, Cylinder, Pos, export_stl, export_step
import trimesh

out = Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent / "crosscheck_outputs"
out.mkdir(parents=True, exist_ok=True)
stock_thickness, clearance, wall = 3.0, 0.30, 2.4
end, stop, height, mount_hole = 42.0, 12.0, 24.0, 4.2
gap = stock_thickness + 2*clearance
half = gap/2 + wall
x_arm = Pos((end-half)/2, 0, height/2) * Box(end+half, 2*half, height)
y_arm = Pos(0, (end-half)/2, height/2) * Box(2*half, end+half, height)
slot_x = Pos((stop+end+1)/2, 0, height/2) * Box(end+1-stop, gap, height+2)
slot_y = Pos(0, (stop+end+1)/2, height/2) * Box(gap, end+1-stop, height+2)
hole = Pos(0, 0, height/2) * Cylinder(mount_hole/2, height+2)
part = (x_arm+y_arm)-slot_x-slot_y-hole
export_stl(part,str(out/"build123d_joint.stl"))
export_step(part,str(out/"build123d_joint.step"))
mesh=trimesh.load_mesh(str(out/"build123d_joint.stl"))
expected=11417.894
report={
    "engine":"build123d/0.13.0",
    "model_volume_mm3":round(float(part.volume),6),
    "cadquery_reference_volume_mm3":expected,
    "volume_difference_mm3":round(float(part.volume)-expected,6),
    "bounds_mm":[round(float(v),3) for v in mesh.extents],
    "watertight":bool(mesh.is_watertight),
    "triangles":int(len(mesh.faces)),
    "physical_fit_verified":False,
    "physical_strength_verified":False,
}
print(json.dumps(report,indent=2))
if (abs(part.volume-expected)>0.02
        or not mesh.is_watertight
        or any(abs(float(a)-float(b))>0.02
               for a,b in zip(mesh.extents,[46.2,46.2,24.0]))):
    raise SystemExit("Independent API CAD geometry comparison failed")
