#!/usr/bin/env python3
"""Native FreeCAD collision check: insertion corridors vs actual shell STEP.

Not a mating-connector CAD validation: the corridor is a conservative AABB
from KiCad plus design clearance, with no selected mating harness.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import FreeCAD
import Part

step=Path(os.environ["HS_MOUNTED_SHELL_STEP"])
envelopes=Path(os.environ["HS_MATING_VOLUME_REPORT"])
out=Path(os.environ["HS_NATIVE_MATING_COLLISION_REPORT"])
source=step.read_bytes()
input_json=envelopes.read_bytes()
provided=json.loads(input_json)
assert provided.get("schema")=="hardware_splicer.connector_mating_volume.v1"
shape=Part.Shape()
shape.read(str(step))
if not shape.isValid() or len(shape.Solids)!=1:
    raise SystemExit("Mounted SolidCraft STEP not a valid single shell solid")
checks=[]
for row in provided["connectors"]:
    a=row["3d_insertion_sweep_aabb_mm"]
    ext=[a["max_"+axis]-a["min_"+axis] for axis in ("x","y","z")]
    if any(x<=0 for x in ext):
        raise SystemExit("Invalid insertion corridor dimensions")
    swept=Part.makeBox(
        ext[0],ext[1],ext[2],
        FreeCAD.Vector(a["min_x"],a["min_y"],a["min_z"])
    )
    overlap=shape.common(swept)
    volume=float(overlap.Volume)
    checks.append({
        "ref":row["ref"],"clash_volume_mm3":volume,
        "source_insert_box_mm":a,
        "no_shell_material_in_access_corridor":volume<0.001,
    })
result={
    "schema":"hardware_splicer.native_connector_access_collision.v1",
    "source_step_sha256":"sha256:"+hashlib.sha256(source).hexdigest(),
    "source_connector_report_sha256":"sha256:"+hashlib.sha256(input_json).hexdigest(),
    "engine":"FreeCAD Part.Shape.common",
    "shape_valid":bool(shape.isValid()),
    "connector_count":len(checks),
    "nominal_corridors_shell_clear":all(c["no_shell_material_in_access_corridor"] for c in checks),
    "checks":checks,
    "exact_mating_connector_model_available":False,
    "cable_assembly_selected":False,
    "physical_fit_verified":False,
    "fabrication_authorized":False,
    "release_authorized":False,
}
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
print(json.dumps(result,indent=2))
if not result["nominal_corridors_shell_clear"]:
    raise SystemExit("Native connector approach corridor intersects modeled shell")
